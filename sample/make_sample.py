"""
Render a realistic SAMPLE dashboard offline (no API access).

Representative OpenClinica B2B clinical-software data at campaign AND ad-group
level, plus an insights block in the exact schema pipeline/insights.py emits.

    python sample/make_sample.py  ->  sample/sample_dashboard.html
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import dashboard  # noqa: E402


def pct(cur, prior):
    return None if not prior else round((cur - prior) / prior * 100, 1)


# campaign: name, channel, budget, impr, clicks, cost, conv, p_impr, p_clicks, p_cost, p_conv, sis
RAW = [
    ("Brand – OpenClinica",        "SEARCH", 40,   9120, 612, 318.40, 14.0,  8480, 540, 286.10, 12.0, 0.92),
    ("EDC Software",               "SEARCH", 220, 41250, 980, 4185.00, 11.0, 38900, 1010, 3620.00, 15.0, 0.41),
    ("eConsent Solutions",         "SEARCH", 120, 18600, 430, 1996.50, 7.0, 17200, 405, 1710.00, 6.0, 0.58),
    ("CTMS / Clinical Trial Mgmt", "SEARCH", 110, 22400, 510, 2310.00, 4.0, 21000, 470, 1980.00, 5.0, 0.33),
    ("ePRO / eCOA",                "SEARCH", 90,  14300, 360, 1422.00, 5.0, 13050, 330, 1210.50, 4.0, 0.49),
    ("Competitor – Medidata",      "SEARCH", 160, 26800, 690, 5040.00, 2.0, 19500, 470, 3290.00, 3.0, 0.27),
    ("Decentralized Trials (DCT)", "DISPLAY", 70, 88200, 540, 918.00, 1.0, 61000, 360, 612.00, 1.0, 0.0),
]

# ad_group: name, parent campaign, impr, clicks, cost, conv, p_cost, p_conv
RAW_AG = [
    ("Phrase – edc software",          "EDC Software", 22100, 540, 2160.00, 8.0, 1980.00, 11.0),
    ("Broad – clinical data capture",  "EDC Software", 19150, 440, 2025.00, 3.0, 1640.00, 4.0),
    ("Exact – econsent platform",      "eConsent Solutions", 10400, 250, 1150.00, 5.0, 980.00, 4.0),
    ("Phrase – electronic consent",    "eConsent Solutions", 8200, 180, 846.50, 2.0, 730.00, 2.0),
    ("Broad – medidata alternative",   "Competitor – Medidata", 18900, 470, 3640.00, 1.0, 2210.00, 2.0),
    ("Exact – medidata competitor",    "Competitor – Medidata", 7900, 220, 1400.00, 1.0, 1080.00, 1.0),
    ("Brand – core terms",             "Brand – OpenClinica", 9120, 612, 318.40, 14.0, 286.10, 12.0),
    ("Broad – ctms software",          "CTMS / Clinical Trial Mgmt", 22400, 510, 2310.00, 4.0, 1980.00, 5.0),
    ("Phrase – epro solution",         "ePRO / eCOA", 14300, 360, 1422.00, 5.0, 1210.50, 4.0),
]


def campaign_obj(row):
    name, ch, budget, impr, clicks, cost, conv, p_impr, p_clicks, p_cost, p_conv, sis = row
    ctr = round(clicks / impr, 4) if impr else 0
    cpa = round(cost / conv, 2) if conv else 0
    p_cpa = round(p_cost / p_conv, 2) if p_conv else 0
    return {
        "campaign_id": abs(hash(name)) % 10**9, "campaign": name, "status": "ENABLED",
        "channel": ch, "daily_budget": budget, "impressions": impr, "clicks": clicks,
        "ctr": ctr, "avg_cpc": round(cost / clicks, 2) if clicks else 0,
        "cpm": round(cost / impr * 1000, 2) if impr else 0, "cost": round(cost, 2),
        "conversions": conv, "conv_value": 0.0, "cost_per_conv": cpa, "search_impr_share": sis,
        "prior": {"cost": p_cost, "clicks": p_clicks, "conversions": p_conv,
                  "cost_per_conv": p_cpa, "ctr": round(p_clicks / p_impr, 4) if p_impr else 0},
        "wow": {"cost": pct(cost, p_cost), "clicks": pct(clicks, p_clicks),
                "conversions": pct(conv, p_conv), "cost_per_conv": pct(cpa, p_cpa),
                "ctr": pct(ctr, round(p_clicks / p_impr, 4) if p_impr else 0)},
    }


def adgroup_obj(row):
    name, camp, impr, clicks, cost, conv, p_cost, p_conv = row
    cpa = round(cost / conv, 2) if conv else 0
    p_cpa = round(p_cost / p_conv, 2) if p_conv else 0
    return {
        "ad_group_id": abs(hash(name)) % 10**9, "ad_group": name, "campaign": camp,
        "status": "ENABLED", "impressions": impr, "clicks": clicks,
        "ctr": round(clicks / impr, 4) if impr else 0,
        "avg_cpc": round(cost / clicks, 2) if clicks else 0,
        "cpm": round(cost / impr * 1000, 2) if impr else 0, "cost": round(cost, 2),
        "conversions": conv, "cost_per_conv": cpa,
        "prior": {"cost": p_cost, "conversions": p_conv},
        "wow": {"cost": pct(cost, p_cost), "conversions": pct(conv, p_conv),
                "cost_per_conv": pct(cpa, p_cpa)},
    }


campaigns = [campaign_obj(r) for r in RAW]
ad_groups = [adgroup_obj(r) for r in RAW_AG]

spend = sum(c["cost"] for c in campaigns); clicks = sum(c["clicks"] for c in campaigns)
impr = sum(c["impressions"] for c in campaigns); conv = sum(c["conversions"] for c in campaigns)
p_spend = sum(c["prior"]["cost"] for c in campaigns); p_clicks = sum(c["prior"]["clicks"] for c in campaigns)
p_conv = sum(c["prior"]["conversions"] for c in campaigns)

data = {
    "current_window": {"start": "2026-06-09", "end": "2026-06-15"},
    "prior_window": {"start": "2026-06-02", "end": "2026-06-08"},
    "currency": "USD",
    "totals": {
        "spend": round(spend, 2), "clicks": clicks, "impressions": impr, "conversions": conv,
        "ctr": round(clicks / impr, 4), "cpc": round(spend / clicks, 2),
        "cpm": round(spend / impr * 1000, 2), "cost_per_conv": round(spend / conv, 2),
        "wow": {"spend": pct(spend, p_spend), "clicks": pct(clicks, p_clicks),
                "conversions": pct(conv, p_conv),
                "cost_per_conv": pct(spend / conv, p_spend / p_conv),
                "cpc": pct(spend / clicks, p_spend / p_clicks)},
    },
    "campaigns": campaigns, "ad_groups": ad_groups,
}

insights = {
    "headline": "Spend up 21% but leads slipped 4% — CPL inefficiency concentrated in Competitor & CTMS",
    "executive_summary": (
        "Total spend rose to $16,190 (+21% WoW) while qualified leads fell to 44 (−4%), pushing blended "
        "CPL to $368 — 145% above the $150 target. The damage is concentrated: Competitor – Medidata "
        "absorbed $5,040 (+53%) for 2 leads, and its 'broad – medidata alternative' ad group alone burned "
        "$3,640 for a single lead. Brand and eConsent are the bright spots and are budget-capped. Shifting "
        "~$2,000/week from Competitor to eConsent and Brand should recover lead volume at no extra spend."
    ),
    "trends": [
        {"title": "Spend outpacing leads a third straight week", "direction": "up", "metric": "spend",
         "detail": "Spend +21% WoW while leads −4%; the gap has widened each of the last three weeks — efficiency erosion, not a blip."},
        {"title": "Blended CPC creeping up", "direction": "up", "metric": "cpc",
         "detail": "Average CPC rose ~9% as Competitor broad-match auctions got more expensive; watch for further inflation."},
        {"title": "Display (DCT) reach up, value flat", "direction": "flat", "metric": "conversions",
         "detail": "DCT impressions +45% but still 1 lead — useful for awareness, not yet pipeline."},
    ],
    "anomalies": [
        {"campaign": "Competitor – Medidata", "title": "Spend +53% with leads down to 2", "severity": "high",
         "detail": "Cost jumped $3,290 → $5,040 while leads fell 3 → 2 (CPL $2,520). No documented bid/budget change — check for an auction shift or broad-match query expansion."},
        {"campaign": "EDC Software", "title": "Leads dropped 27% on higher spend", "severity": "medium",
         "detail": "Spend +16% but leads 15 → 11. CTR held, so the loss is post-click — review landing page or form changes from the last 10 days."},
    ],
    "top_performers": [
        {"entity": "Brand – OpenClinica", "level": "campaign", "key_metric": "CPL $22.74 · 14 leads",
         "why": "Most efficient line by 6x; CTR climbing to 6.7%. Capped at $40/day, so it's leaving cheap leads on the table."},
        {"entity": "Exact – econsent platform", "level": "ad_group", "key_metric": "CPL $230 · 5 leads",
         "why": "Tight exact-match ad group beating target inside eConsent; the scalable core of that campaign."},
        {"entity": "eConsent Solutions", "level": "campaign", "key_metric": "CPL $285 · 7 leads (+17%)",
         "why": "Near target and growing while losing impression share to budget (search IS 58%) — clear headroom."},
    ],
    "underperformers": [
        {"entity": "Broad – medidata alternative", "level": "ad_group",
         "issue": "$3,640 for 1 lead (CPL $3,640) — the single worst unit in the account.",
         "recommendation": "Pause or convert to phrase/exact on the 2 converting terms; add competitor product-line negatives."},
        {"entity": "CTMS / Clinical Trial Mgmt", "level": "campaign",
         "issue": "$2,310 for 4 leads (CPL $578) with healthy impression share — a relevance problem, not a cap.",
         "recommendation": "Audit search terms for off-intent queries; shift 30% of budget to EDC, which converts at ~half the CPL."},
    ],
    "budget_inefficiencies": [
        {"campaign": "Competitor – Medidata", "issue": "CPL 16x over target", "est_monthly_waste_usd": 18000,
         "detail": "$5,040 for 2 leads ($2,520 CPL vs $150 target); ~$20k/mo run-rate for ~8 leads.",
         "recommendation": "Cap daily budget at $80, tighten to exact/phrase on the 3 best terms, add negatives, reallocate to eConsent."},
        {"campaign": "CTMS / Clinical Trial Mgmt", "issue": "Spend +17% with only 4 leads", "est_monthly_waste_usd": 6000,
         "detail": "$2,310 for 4 leads ($578 CPL). Impression share is healthy (33%), so this is relevance/landing, not a cap.",
         "recommendation": "Pause the lowest-CTR ad group and move 30% of budget to EDC."},
    ],
    "opportunities": [
        {"title": "eConsent is budget-capped while hitting target", "priority": "high",
         "detail": "7 leads at $285 CPL with meaningful impression share lost to budget (search IS 58%).",
         "recommended_action": "Raise daily budget $120 → $170 and re-test top-of-page bids.",
         "expected_impact": "≈ +3–4 leads/week at/near target CPL"},
        {"title": "Protect and scale Brand", "priority": "medium",
         "detail": "Brand converts at $22.74 — 6x more efficient than blended — and is capped at $40/day.",
         "recommended_action": "Lift Brand to $60/day, confirm 100% IS, add conquesting sitelinks.",
         "expected_impact": "Cheap incremental leads; defends against competitor brand bidding"},
        {"title": "Account-wide match-type + negatives audit", "priority": "medium",
         "detail": "Both major CPL problems trace to broad reach; a match-type tightening is the fastest lever.",
         "recommended_action": "Move broad terms with CPL > 2x target to phrase/exact; layer negatives.",
         "expected_impact": "Est. 10–15% blended CPL reduction in two weeks"},
    ],
    "recommended_actions": [
        {"action": "Cap Competitor – Medidata at $80/day; reallocate to eConsent", "priority": "high",
         "rationale": "Largest single source of waste; net-neutral on spend, lead-positive."},
        {"action": "Raise eConsent budget to $170/day", "priority": "high",
         "rationale": "On-target campaign losing volume purely to a budget cap."},
        {"action": "Investigate EDC Software lead drop (landing/form)", "priority": "medium",
         "rationale": "CTR steady but leads −27% points to a post-click regression."},
        {"action": "Run an account-wide match-type + negatives audit", "priority": "medium",
         "rationale": "Addresses the root cause behind both major CPL anomalies."},
    ],
}

html = dashboard.render(data, insights,
                        sheet_url="https://docs.google.com/spreadsheets/d/EXAMPLE_SHEET_ID",
                        model="claude-sonnet-4-6", target_cpa=150.0)
out = Path(__file__).resolve().parent / "sample_dashboard.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({len(html):,} bytes)")
