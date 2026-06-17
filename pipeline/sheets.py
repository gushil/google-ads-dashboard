"""
Consolidate the weekly snapshot into a structured Google Sheet — the central
layer the spec calls for. Tabs:

  Data       append-only campaign history, keyed by run_date (longitudinal trends)
  Latest     campaigns for the most recent run (overwritten each week)
  AdGroups   ad-group rows for the most recent run (overwritten each week)
  Insights   the latest Claude analysis as JSON + timestamp (audit / re-render)

New campaigns and ad groups flow in automatically — rows are written for whatever
the API returned, with no predefined list to maintain.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CAMP_HEADERS = [
    "run_date", "window_start", "window_end", "campaign_id", "campaign", "status",
    "channel", "daily_budget", "impressions", "clicks", "ctr", "avg_cpc", "cpm",
    "cost", "conversions", "conv_value", "cost_per_lead", "search_impr_share",
    "wow_cost_%", "wow_clicks_%", "wow_conv_%", "wow_cpl_%",
]
AG_HEADERS = [
    "run_date", "campaign", "ad_group", "status", "impressions", "clicks", "ctr",
    "avg_cpc", "cpm", "cost", "conversions", "cost_per_lead",
    "wow_cost_%", "wow_conv_%", "wow_cpl_%",
]


def _creds(cfg) -> Credentials:
    raw = os.environ.get("GOOGLE_SA_JSON")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return Credentials.from_service_account_file(cfg.google_sa_file, scopes=SCOPES)


def _ws(sh, title: str, headers: list[str]):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=2000, cols=max(len(headers), 4))
        ws.append_row(headers)
    if headers and ws.row_values(1) != headers:
        ws.update("A1", [headers])
    return ws


def write(cfg, data: dict[str, Any]) -> str:
    """Append history + refresh Latest/AdGroups tabs. Returns the sheet URL."""
    gc = gspread.authorize(_creds(cfg))
    sh = gc.open_by_key(cfg.sheet_id)
    run_date = dt.date.today().isoformat()
    cw = data["current_window"]

    def camp_row(c):
        w = c["wow"]
        return [run_date, cw["start"], cw["end"], c["campaign_id"], c["campaign"], c["status"],
                c["channel"], c["daily_budget"], c["impressions"], c["clicks"], c["ctr"],
                c["avg_cpc"], c["cpm"], c["cost"], c["conversions"], c["conv_value"],
                c["cost_per_conv"], c["search_impr_share"], w["cost"], w["clicks"],
                w["conversions"], w["cost_per_conv"]]

    def ag_row(a):
        w = a["wow"]
        return [run_date, a["campaign"], a["ad_group"], a["status"], a["impressions"],
                a["clicks"], a["ctr"], a["avg_cpc"], a["cpm"], a["cost"], a["conversions"],
                a["cost_per_conv"], w["cost"], w["conversions"], w["cost_per_conv"]]

    camp_rows = [camp_row(c) for c in data["campaigns"]]
    ag_rows = [ag_row(a) for a in data["ad_groups"]]

    data_ws = _ws(sh, "Data", CAMP_HEADERS)
    if camp_rows:
        data_ws.append_rows(camp_rows, value_input_option="USER_ENTERED")

    latest = _ws(sh, "Latest", CAMP_HEADERS)
    latest.batch_clear(["A2:Z10000"])
    if camp_rows:
        latest.update(f"A2", camp_rows, value_input_option="USER_ENTERED")

    ag_ws = _ws(sh, "AdGroups", AG_HEADERS)
    ag_ws.batch_clear(["A2:Z20000"])
    if ag_rows:
        ag_ws.update(f"A2", ag_rows, value_input_option="USER_ENTERED")

    return f"https://docs.google.com/spreadsheets/d/{cfg.sheet_id}"


def write_insights(cfg, insights: dict[str, Any]) -> None:
    """Persist the latest analysis JSON so the web app can re-render after a restart."""
    gc = gspread.authorize(_creds(cfg))
    sh = gc.open_by_key(cfg.sheet_id)
    ws = _ws(sh, "Insights", ["generated_at", "json"])
    ws.batch_clear(["A2:B100"])
    ws.update("A2", [[dt.datetime.utcnow().isoformat(), json.dumps(insights)]])
