"""
Weekly refresh job: Google Ads -> Google Sheet -> Claude -> branded HTML.

Writes the rendered dashboard to DATA_DIR (a Railway volume in production) where
the web service serves it, persists the analysis JSON back to the Sheet, and
optionally emails the team a link/copy.

Run locally:  python run_weekly.py
On Railway:   called weekly by the in-app scheduler (app.py) or a Railway cron.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import config
from pipeline import dashboard, deliver, fetch_ads, insights, sheets

DATA_DIR = Path(os.environ.get("DATA_DIR", "output"))


def run() -> dict:
    cfg = config.load()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/5] Fetching Google Ads data (campaigns + ad groups, current + prior week)...")
    data = fetch_ads.fetch(cfg)
    print(f"      {len(data['campaigns'])} campaigns, {len(data['ad_groups'])} ad groups, "
          f"spend {cfg.currency} {data['totals']['spend']:,.2f}")

    print("[2/5] Consolidating into Google Sheet...")
    try:
        sheet_url = sheets.write(cfg, data)
    except Exception as e:  # noqa: BLE001
        print(f"      WARN: sheet write failed: {e}")
        sheet_url = f"https://docs.google.com/spreadsheets/d/{cfg.sheet_id}"

    print("[3/5] Generating insights with Claude...")
    ins = insights.generate(cfg, data)
    try:
        sheets.write_insights(cfg, ins)
    except Exception as e:  # noqa: BLE001
        print(f"      WARN: insights persist failed: {e}")

    print("[4/5] Rendering branded dashboard...")
    html = dashboard.render(data, ins, sheet_url=sheet_url, model=cfg.model,
                            target_cpa=cfg.target_cpa_usd)
    (DATA_DIR / "latest.html").write_text(html, encoding="utf-8")
    print(f"      wrote {DATA_DIR / 'latest.html'}")

    print("[5/5] Optional email delivery...")
    public_url = os.environ.get("PUBLIC_URL", "")
    subject = f"Paid Media Weekly - {ins.get('headline', 'Google Ads performance')}"
    body_note = f"\n\nLive dashboard: {public_url}" if public_url else ""
    deliver.send(cfg, html, subject, extra_note=body_note)

    print("Done.")
    return {"campaigns": len(data["campaigns"]), "ad_groups": len(data["ad_groups"]),
            "spend": data["totals"]["spend"]}


if __name__ == "__main__":
    try:
        run()
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
