"""
Central configuration for the weekly Google Ads → Claude → Dashboard pipeline.

Everything sensitive comes from environment variables (set as GitHub Actions
secrets in production). Business targets live here so they're easy to tune.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val  # type: ignore[return-value]


@dataclass
class Config:
    # --- Google Ads API ---
    # These map 1:1 to the fields google-ads.yaml expects. We read them from the
    # environment so the same code works locally and in CI without a file on disk.
    gads_developer_token: str = field(default_factory=lambda: _env("GADS_DEVELOPER_TOKEN", required=True))
    gads_client_id: str = field(default_factory=lambda: _env("GADS_CLIENT_ID", required=True))
    gads_client_secret: str = field(default_factory=lambda: _env("GADS_CLIENT_SECRET", required=True))
    gads_refresh_token: str = field(default_factory=lambda: _env("GADS_REFRESH_TOKEN", required=True))
    gads_login_customer_id: str = field(default_factory=lambda: _env("GADS_LOGIN_CUSTOMER_ID", ""))  # MCC, digits only
    gads_customer_id: str = field(default_factory=lambda: _env("GADS_CUSTOMER_ID", required=True))      # account, digits only

    # --- Google Sheets ---
    sheet_id: str = field(default_factory=lambda: _env("SHEET_ID", required=True))
    # Path to a service-account JSON key file, OR set GOOGLE_SA_JSON to the raw JSON.
    google_sa_file: str = field(default_factory=lambda: _env("GOOGLE_SA_FILE", "service_account.json"))

    # --- Anthropic ---
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-sonnet-4-6"))

    # --- Email delivery (SMTP, provider-agnostic) ---
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD", ""))
    mail_from: str = field(default_factory=lambda: _env("MAIL_FROM", "paid-media-bot@openclinica.com"))
    # Comma-separated list of recipients.
    mail_to: list[str] = field(
        default_factory=lambda: [a.strip() for a in _env("MAIL_TO", "").split(",") if a.strip()]
    )

    # --- Business targets (used by Claude to judge efficiency) ---
    # Set these to your actual paid-media goals. Leave 0 to let Claude infer.
    target_cpa_usd: float = field(default_factory=lambda: float(_env("TARGET_CPA_USD", "150")))   # cost per demo/lead
    target_roas: float = field(default_factory=lambda: float(_env("TARGET_ROAS", "0")))           # if you track revenue
    currency: str = field(default_factory=lambda: _env("CURRENCY", "USD"))

    # Skip delivery (useful for local dry runs); still writes Sheet + HTML.
    dry_run: bool = field(default_factory=lambda: _env("DRY_RUN", "false").lower() == "true")


# Lazily constructed so importing this module doesn't require env vars to be set
# (e.g. when only rendering the dashboard from sample data).
def load() -> "Config":
    return Config()
