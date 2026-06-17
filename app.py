"""
Railway web service.

Serves the latest OpenClinica-branded dashboard and refreshes it weekly. The
expensive work (Google Ads pull + Claude analysis) runs on a schedule, not on
page loads, so the page is instant and API costs are bounded to one run per week.

Routes
  GET  /          -> latest rendered dashboard (or a branded "pending" page)
  POST /refresh   -> trigger a refresh now (requires ?token=REFRESH_TOKEN)
  GET  /healthz   -> health check for Railway

Scheduling
  An in-process APScheduler cron runs run_weekly.run() on REFRESH_CRON
  (default: Monday 13:00 UTC). For multi-instance setups, disable this
  (RUN_SCHEDULER=false) and use a separate Railway cron service that calls
  `python run_weekly.py` instead — run_weekly is the single entrypoint either way.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, Response, abort, request

app = Flask(__name__)
DATA_DIR = Path(os.environ.get("DATA_DIR", "output"))
LATEST = DATA_DIR / "latest.html"
SAMPLE = Path(__file__).parent / "sample" / "sample_dashboard.html"
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")
_refresh_lock = threading.Lock()

PENDING_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenClinica Paid Media</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;600;800&display=swap" rel="stylesheet">
<style>body{margin:0;font-family:'Outfit',sans-serif;background:#F0F4F8;color:#272948;
display:grid;place-items:center;min-height:100vh;text-align:center}
.box{background:#fff;border:1px solid #D8DCDF;border-radius:12px;padding:48px 40px;max-width:520px}
h1{font-weight:800;font-size:1.6rem;margin:0 0 10px;
background:linear-gradient(135deg,#F46700,#D63085);-webkit-background-clip:text;background-clip:text;color:transparent}
p{font-weight:300;line-height:1.6}</style></head>
<body><div class="box"><h1>Dashboard pending first refresh</h1>
<p>The weekly Google Ads report hasn't been generated yet. It will appear here
automatically after the next scheduled refresh, or trigger one now via the refresh
endpoint.</p></div></body></html>"""


def _do_refresh() -> None:
    if not _refresh_lock.acquire(blocking=False):
        print("[web] refresh already running; skipping.")
        return
    try:
        import run_weekly  # imported here so serving a cached page needs no Ads SDK
        run_weekly.run()
    except Exception as e:  # noqa: BLE001
        print(f"[web] refresh failed: {e}")
    finally:
        _refresh_lock.release()


@app.get("/")
def index() -> Response:
    if LATEST.exists():
        return Response(LATEST.read_text(encoding="utf-8"), mimetype="text/html")
    if SAMPLE.exists():
        return Response(SAMPLE.read_text(encoding="utf-8"), mimetype="text/html")
    return Response(PENDING_PAGE, mimetype="text/html")


@app.post("/refresh")
def refresh() -> Response:
    if not REFRESH_TOKEN or request.args.get("token") != REFRESH_TOKEN:
        abort(403)
    threading.Thread(target=_do_refresh, daemon=True).start()
    return Response('{"status":"refresh started"}', mimetype="application/json")


@app.get("/healthz")
def healthz() -> Response:
    return Response('{"ok":true}', mimetype="application/json")


def _start_scheduler() -> None:
    if os.environ.get("RUN_SCHEDULER", "true").lower() != "true":
        return
    cron = os.environ.get("REFRESH_CRON", "0 13 * * 1")  # Mon 13:00 UTC
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(_do_refresh, CronTrigger.from_crontab(cron), id="weekly_refresh",
                  max_instances=1, coalesce=True)
    sched.start()
    print(f"[web] scheduler started (cron='{cron}' UTC)")
    if os.environ.get("REFRESH_ON_BOOT", "true").lower() == "true" and not LATEST.exists():
        threading.Thread(target=_do_refresh, daemon=True).start()


# Start scheduler at import so it runs under gunicorn too (use a single worker).
_start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
