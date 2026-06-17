"""
Pull Google Ads performance via the official Google Ads API.

Fetches CAMPAIGN- and AD-GROUP-level metrics for two 7-day windows (current week
and the prior week) so every row carries week-over-week deltas. New campaigns and
ad groups are picked up automatically — nothing is hardcoded; we report on whatever
is currently enabled in the account.

Returns a normalized payload; nothing downstream needs to know about micros, GAQL,
or the SDK.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from google.ads.googleads.client import GoogleAdsClient

MICROS = 1_000_000

# Cost fields come back in micros (1/1,000,000 of the account currency).
CAMPAIGN_GAQL = """
SELECT
  campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
  campaign_budget.amount_micros,
  metrics.impressions, metrics.clicks, metrics.ctr, metrics.average_cpc,
  metrics.average_cpm, metrics.cost_micros, metrics.conversions,
  metrics.conversions_value, metrics.cost_per_conversion,
  metrics.search_impression_share
FROM campaign
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND campaign.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
"""

ADGROUP_GAQL = """
SELECT
  campaign.name, ad_group.id, ad_group.name, ad_group.status,
  metrics.impressions, metrics.clicks, metrics.ctr, metrics.average_cpc,
  metrics.average_cpm, metrics.cost_micros, metrics.conversions,
  metrics.cost_per_conversion
FROM ad_group
WHERE segments.date BETWEEN '{start}' AND '{end}'
  AND ad_group.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
"""


def _client(cfg) -> GoogleAdsClient:
    return GoogleAdsClient.load_from_dict({
        "developer_token": cfg.gads_developer_token,
        "client_id": cfg.gads_client_id,
        "client_secret": cfg.gads_client_secret,
        "refresh_token": cfg.gads_refresh_token,
        "login_customer_id": cfg.gads_login_customer_id or None,
        "use_proto_plus": True,
    })


def _week_bounds(reference: dt.date) -> tuple[tuple[str, str], tuple[str, str]]:
    """(current_week, prior_week) as (start, end) ISO strings.

    Current week = the 7 complete days ending yesterday (never a partial day);
    prior week = the 7 days before that.
    """
    end_cur = reference - dt.timedelta(days=1)
    start_cur = end_cur - dt.timedelta(days=6)
    end_prior = start_cur - dt.timedelta(days=1)
    start_prior = end_prior - dt.timedelta(days=6)
    iso = lambda d: d.isoformat()
    return (iso(start_cur), iso(end_cur)), (iso(start_prior), iso(end_prior))


def _pct_delta(cur: float, prior: float) -> float | None:
    if not prior:
        return None  # undefined / new entity
    return round((cur - prior) / prior * 100, 1)


def _campaign_rows(client, cid, start, end) -> dict[int, dict[str, Any]]:
    svc = client.get_service("GoogleAdsService")
    out: dict[int, dict[str, Any]] = {}
    for batch in svc.search_stream(customer_id=cid, query=CAMPAIGN_GAQL.format(start=start, end=end)):
        for r in batch.results:
            c, m = r.campaign, r.metrics
            out[c.id] = {
                "campaign_id": c.id, "campaign": c.name, "status": c.status.name,
                "channel": c.advertising_channel_type.name,
                "daily_budget": round(r.campaign_budget.amount_micros / MICROS, 2),
                "impressions": int(m.impressions), "clicks": int(m.clicks),
                "ctr": round(m.ctr, 4), "avg_cpc": round(m.average_cpc / MICROS, 2),
                "cpm": round(m.average_cpm / MICROS, 2), "cost": round(m.cost_micros / MICROS, 2),
                "conversions": round(m.conversions, 2), "conv_value": round(m.conversions_value, 2),
                "cost_per_conv": round(m.cost_per_conversion / MICROS, 2) if m.cost_per_conversion else 0.0,
                "search_impr_share": round(m.search_impression_share, 4),
            }
    return out


def _adgroup_rows(client, cid, start, end) -> dict[int, dict[str, Any]]:
    svc = client.get_service("GoogleAdsService")
    out: dict[int, dict[str, Any]] = {}
    for batch in svc.search_stream(customer_id=cid, query=ADGROUP_GAQL.format(start=start, end=end)):
        for r in batch.results:
            a, m = r.ad_group, r.metrics
            out[a.id] = {
                "ad_group_id": a.id, "ad_group": a.name, "campaign": r.campaign.name,
                "status": a.status.name, "impressions": int(m.impressions), "clicks": int(m.clicks),
                "ctr": round(m.ctr, 4), "avg_cpc": round(m.average_cpc / MICROS, 2),
                "cpm": round(m.average_cpm / MICROS, 2), "cost": round(m.cost_micros / MICROS, 2),
                "conversions": round(m.conversions, 2),
                "cost_per_conv": round(m.cost_per_conversion / MICROS, 2) if m.cost_per_conversion else 0.0,
            }
    return out


def _attach_wow(rows: dict[int, dict], prior: dict[int, dict]) -> list[dict]:
    merged = []
    for key, row in rows.items():
        prev = prior.get(key, {})
        row["prior"] = {k: prev.get(k) for k in ("cost", "clicks", "conversions", "cost_per_conv", "ctr")}
        row["wow"] = {
            "cost": _pct_delta(row["cost"], prev.get("cost", 0)),
            "clicks": _pct_delta(row["clicks"], prev.get("clicks", 0)),
            "conversions": _pct_delta(row["conversions"], prev.get("conversions", 0)),
            "cost_per_conv": _pct_delta(row["cost_per_conv"], prev.get("cost_per_conv", 0)),
            "ctr": _pct_delta(row["ctr"], prev.get("ctr", 0)),
        }
        merged.append(row)
    return merged


def fetch(cfg, reference: dt.date | None = None) -> dict[str, Any]:
    reference = reference or dt.date.today()
    (cs, ce), (ps, pe) = _week_bounds(reference)
    client = _client(cfg)
    cid = cfg.gads_customer_id.replace("-", "")

    campaigns = _attach_wow(_campaign_rows(client, cid, cs, ce), _campaign_rows(client, cid, ps, pe))
    ad_groups = _attach_wow(_adgroup_rows(client, cid, cs, ce), _adgroup_rows(client, cid, ps, pe))

    return {
        "current_window": {"start": cs, "end": ce},
        "prior_window": {"start": ps, "end": pe},
        "currency": cfg.currency,
        "totals": _totals(campaigns),
        "campaigns": campaigns,
        "ad_groups": ad_groups,
    }


def _totals(campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    spend = sum(c["cost"] for c in campaigns)
    clicks = sum(c["clicks"] for c in campaigns)
    impr = sum(c["impressions"] for c in campaigns)
    conv = sum(c["conversions"] for c in campaigns)
    p_spend = sum((c["prior"]["cost"] or 0) for c in campaigns)
    p_clicks = sum((c["prior"]["clicks"] or 0) for c in campaigns)
    p_conv = sum((c["prior"]["conversions"] or 0) for c in campaigns)
    return {
        "spend": round(spend, 2), "clicks": clicks, "impressions": impr,
        "conversions": round(conv, 2),
        "ctr": round(clicks / impr, 4) if impr else 0,
        "cpc": round(spend / clicks, 2) if clicks else 0,
        "cpm": round(spend / impr * 1000, 2) if impr else 0,
        "cost_per_conv": round(spend / conv, 2) if conv else 0,  # CPL
        "wow": {
            "spend": _pct_delta(spend, p_spend),
            "clicks": _pct_delta(clicks, p_clicks),
            "conversions": _pct_delta(conv, p_conv),
            "cost_per_conv": _pct_delta(spend / conv if conv else 0, p_spend / p_conv if p_conv else 0),
            "cpc": _pct_delta(spend / clicks if clicks else 0, p_spend / p_clicks if p_clicks else 0),
        },
    }
