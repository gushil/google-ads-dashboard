# OpenClinica — Weekly Paid Media Dashboard

Automated weekly pipeline that pulls Google Ads performance (campaign **and** ad
group level), consolidates it into a Google Sheet, has **Claude** (`claude-sonnet-4-6`)
produce the analysis a human analyst would spend 2–3 hours on, and serves an
**OpenClinica-branded HTML dashboard** to the paid-media team — **deployed on Railway**
with a stable weekly refresh.

```
Google Ads API ─▶ Google Sheet ─▶ Claude analysis ─▶ Branded HTML ─▶ Railway (hosted, weekly)
  fetch_ads.py     sheets.py        insights.py        dashboard.py     app.py + scheduler
                   run_weekly.run() is the single refresh entrypoint (scheduler or cron)
```

**Open `sample/sample_dashboard.html` in a browser** for a full rendered example.

---

## How this maps to the intake form

| Spec step | Implementation |
|---|---|
| **1 Extract** — Google Ads API, weekly | `pipeline/fetch_ads.py` — GAQL for campaigns + ad groups, current vs prior 7 days |
| **2 Load** — Google Sheet, campaign + ad-group rows | `pipeline/sheets.py` — `Data` (history), `Latest`, `AdGroups`, `Insights` tabs |
| **3 Analyze** — Claude reads structured export, WoW + historical | `pipeline/insights.py` — full metric set incl. CPC/CPM/CPL |
| **4 Generate** — summaries, anomalies, top/under, budget, optimization | strict-JSON schema covering all six insight types |
| **5 Deliver** — branded dashboard on Railway | `app.py` serves it; weekly in-app scheduler refreshes it |

**Insight types produced** (each finding names the entity, cites numbers, ends in an action):
performance summary · anomalies (with severity) · **top performers** (ranked) ·
**underperformers** (ranked) · budget-efficiency observations (with $/mo at risk) ·
optimization opportunities (prioritized) · a ranked action checklist.

**Metrics tracked:** Cost, Impressions, Clicks, CTR, CPC, CPM, Leads/Conversions, CPL.

**New campaigns & ad groups are picked up automatically** — the queries report on
whatever is enabled in the account; there is no list to maintain.

---

## Deploy on Railway (primary)

1. **Push this repo** and create a Railway project from it (Nixpacks auto-detects
   `requirements.txt`; `railway.toml` sets the start command + `/healthz` check).
2. **Add a Volume** mounted at `/data` and set `DATA_DIR=/data` so the rendered
   dashboard survives redeploys.
3. **Set environment variables** (see `.env.example`) as Railway Variables:
   the `GADS_*`, `SHEET_ID`, `GOOGLE_SA_JSON`, `ANTHROPIC_API_KEY`, optional `SMTP_*`,
   `TARGET_CPA_USD`, plus `REFRESH_TOKEN` (protects `/refresh`) and optionally
   `REFRESH_CRON` (default `0 13 * * 1` = Mon 13:00 UTC) and `PUBLIC_URL`.
4. **First run:** hit `POST /refresh?token=<REFRESH_TOKEN>` once (or set
   `REFRESH_ON_BOOT=true` for the first deploy) to generate the dashboard immediately.
   After that the in-app scheduler refreshes weekly.

Keep the service at **1 web instance / 1 worker** so the in-process scheduler fires
once. For larger setups, set `RUN_SCHEDULER=false` and add a **separate Railway cron
service** whose command is `python run_weekly.py` — same entrypoint, no double-firing.

**Routes:** `GET /` (dashboard) · `POST /refresh?token=…` (manual refresh) · `GET /healthz`.

---

## Setup details (Google Ads, Sheets, Anthropic)

- **Google Ads API:** developer token (API Center) + a Desktop OAuth client; run
  Google's `generate_user_credentials` once for a refresh token. `GADS_CUSTOMER_ID`
  is the ad account (digits only); `GADS_LOGIN_CUSTOMER_ID` is your MCC if used.
- **Google Sheet:** create a blank Sheet, copy its ID into `SHEET_ID`, create a
  **service account**, and **share the Sheet with its `client_email` as Editor**.
  In CI/Railway paste the JSON key into `GOOGLE_SA_JSON`; locally use `service_account.json`.
- **Anthropic:** set `ANTHROPIC_API_KEY`. Model is `claude-sonnet-4-6` (confirmed in
  the spec); set `CLAUDE_MODEL=claude-opus-4-8` for the deepest analysis.
- **Targets:** set `TARGET_CPA_USD` (your target CPL) so Claude judges efficiency
  against a real goal.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in values
python run_weekly.py            # full pipeline -> output/latest.html
DRY_RUN=true python run_weekly.py   # build + write sheet, skip email
python app.py                   # serve locally at http://localhost:8080
python sample/make_sample.py    # render the offline sample (no APIs needed)
```

---

## Validating the quality bar

The success criteria call for AI insights to align with a human analyst on a known
dataset, and ≥75% time reduction. To validate: run `make_sample.py` (or a real
week), have the analyst review the same week independently, and compare the flagged
anomalies / top / under performers. Tune `pipeline/insights.py`'s `SYSTEM_PROMPT`
(thresholds, tone, what counts as "material") until alignment is satisfactory — the
schema stays fixed so the dashboard keeps rendering.

## Customizing

| Want to… | Edit |
|---|---|
| Change pulled metrics/dimensions | the GAQL queries in `pipeline/fetch_ads.py` |
| Change the analysis (rules, tone, thresholds, schema) | `SYSTEM_PROMPT` in `pipeline/insights.py` |
| Restyle the report | `templates/dashboard.html.j2` (brand tokens wired) |
| Swap/disable email, add Slack | `pipeline/deliver.py` (keep `send(cfg, html, subject)`) |
| Use a separate cron instead of the in-app scheduler | set `RUN_SCHEDULER=false`, run `python run_weekly.py` |

## Notes & limits

- First run has no prior week, so WoW shows "new".
- Email is optional now that the dashboard is hosted; if `SMTP_*` is set, recipients
  also get a copy + a link to the live Railway URL.
- `.github/workflows/weekly-dashboard.yml` is included as an **alternative** scheduler
  (GitHub Actions cron) if you'd rather not run the in-app one.
- Claude's output is decision-support, not auto-execution — the footer says so on
  every report; verify before material spend changes.
