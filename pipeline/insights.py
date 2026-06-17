"""
The analyst-in-a-box.

Sends the week's structured Google Ads data to Claude and gets back a strict-JSON
analysis: an executive narrative plus categorized, prioritized findings across
trends, anomalies, budget inefficiencies, and optimization opportunities.

The schema is enforced by prompt + validated on parse so the dashboard renderer
can rely on its shape. If the model returns malformed JSON, we retry once with a
"return ONLY valid JSON" nudge before falling back to a safe empty structure.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

SYSTEM_PROMPT = """\
You are a senior paid-search analyst for OpenClinica, a clinical-trials software \
company (EDC, eConsent/eConsent, ePRO/eCOA, randomization, reporting & analytics). \
Its Google Ads audience is sponsors, CROs, and research sites; "conversions" are \
demo requests and qualified leads, so volumes are low and CPCs/CPAs are high \
relative to consumer accounts.

Each week you review performance at BOTH the campaign and ad-group level and \
produce the analysis a human analyst would otherwise spend 2-3 hours on. You are \
quantitative, specific, and decisive. You work with the full metric set: cost, \
impressions, clicks, CTR, CPC, CPM, conversions (leads), and CPL (cost per lead). \
Every finding names the campaign or ad group involved, cites the numbers that \
justify it, and ends in a concrete action a media buyer can take this week. You do \
not pad the report with generic best-practice filler; if there is nothing material \
in a category, return an empty list for it. Rank top performers and underperformers \
by the metric that best reflects efficiency (usually CPL against target, with volume \
as a tiebreaker).

Judge efficiency against the supplied targets (target CPA / ROAS). Flag a campaign \
as a budget inefficiency when it spends meaningfully while missing target CPA, when \
spend rose but conversions did not, or when it is budget-capped (high impression \
share lost to budget) while hitting target. Estimate monthly waste as \
(spend over target) extrapolated to ~30 days where you can.

Output ONLY a single valid JSON object, no prose before or after, no markdown \
fences, matching exactly this schema:

{
  "executive_summary": "3-5 sentence plain-English narrative of the week for a \
busy stakeholder: what happened, why it matters, what to do.",
  "headline": "one punchy sentence (<=120 chars) for the email subject/banner",
  "trends": [
    {"title": "...", "detail": "...", "direction": "up|down|flat", "metric": "spend|clicks|conversions|cpl|cpc|cpm|ctr|other"}
  ],
  "anomalies": [
    {"campaign": "...", "title": "...", "detail": "...", "severity": "high|medium|low"}
  ],
  "top_performers": [
    {"entity": "...", "level": "campaign|ad_group", "why": "...", "key_metric": "e.g. CPL $22 at 14 leads"}
  ],
  "underperformers": [
    {"entity": "...", "level": "campaign|ad_group", "issue": "...", "recommendation": "..."}
  ],
  "budget_inefficiencies": [
    {"campaign": "...", "issue": "...", "detail": "...", "est_monthly_waste_usd": 0, "recommendation": "..."}
  ],
  "opportunities": [
    {"title": "...", "detail": "...", "recommended_action": "...", "expected_impact": "...", "priority": "high|medium|low"}
  ],
  "recommended_actions": [
    {"action": "...", "rationale": "...", "priority": "high|medium|low"}
  ]
}

Order every list by severity/priority, highest first. Cap each list at 6 items; \
keep only what is material.
"""


def _user_payload(cfg, data: dict[str, Any]) -> str:
    context = {
        "targets": {
            "target_cpa_usd": cfg.target_cpa_usd,
            "target_roas": cfg.target_roas or "not tracked",
            "currency": cfg.currency,
        },
        "current_window": data["current_window"],
        "prior_window": data["prior_window"],
        "account_totals": data["totals"],
        "campaigns": data["campaigns"],
        "ad_groups": data["ad_groups"],
    }
    return (
        "Analyze this week's Google Ads performance. WoW fields are percent change "
        "vs the prior 7 days (null = no prior data / new). Return the JSON object only.\n\n"
        + json.dumps(context, indent=2)
    )


_EMPTY: dict[str, Any] = {
    "executive_summary": "Insight generation was unavailable this run; metrics below are unaffected.",
    "headline": "Weekly Google Ads performance",
    "trends": [], "anomalies": [], "top_performers": [], "underperformers": [],
    "budget_inefficiencies": [], "opportunities": [], "recommended_actions": [],
}

_REQUIRED_LISTS = ("trends", "anomalies", "top_performers", "underperformers",
                   "budget_inefficiencies", "opportunities", "recommended_actions")


def _parse(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    for k in _REQUIRED_LISTS:
        obj.setdefault(k, [])
    obj.setdefault("executive_summary", _EMPTY["executive_summary"])
    obj.setdefault("headline", _EMPTY["headline"])
    return obj


def generate(cfg, data: dict[str, Any]) -> dict[str, Any]:
    if not cfg.anthropic_api_key:
        return _EMPTY
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    user_msg = _user_payload(cfg, data)

    for attempt in range(2):
        suffix = "" if attempt == 0 else "\n\nYour previous reply was not valid JSON. Return ONLY the JSON object."
        resp = client.messages.create(
            model=cfg.model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg + suffix}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        parsed = _parse(text)
        if parsed is not None:
            return parsed
    return _EMPTY
