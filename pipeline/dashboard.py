"""
Render the branded HTML dashboard from metrics + Claude insights.

All number/markup formatting lives here as Jinja globals so the template stays
declarative. Insight text is auto-escaped; helper output is returned as Markup.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Product palette for the campaign-name dot (cosmetic, brand-consistent).
_CHANNEL_COLORS = [
    ("edc", "#F68533"), ("consent", "#A5009F"), ("epro", "#FFA800"), ("pro", "#FFA800"),
    ("ecoa", "#FFA800"), ("ehr", "#F46700"), ("unite", "#F46700"), ("report", "#F4422A"),
    ("analytic", "#F4422A"), ("enroll", "#D63085"), ("random", "#272948"), ("brand", "#F46700"),
    ("competitor", "#7D7F91"),
]


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"${v:,.0f}"
    return f"${v:,.2f}"


def _num(v: float | int | None) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and v != int(v):
        return f"{v:,.1f}"
    return f"{int(v):,}"


def _pctval(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.2f}%"


def _delta(value: float | None, up_is_good: bool | None = True) -> Markup:
    """Render a WoW % change as a colored, arrowed span.

    up_is_good=True  → up green / down red (clicks, conversions)
    up_is_good=False → up red / down green (CPA)
    up_is_good=None  → neutral grey (spend — direction isn't inherently good/bad)
    """
    if value is None:
        return Markup('<span class="d-flat">new</span>')
    arrow = "↑" if value > 0 else ("↓" if value < 0 else "→")
    if up_is_good is None or value == 0:
        cls = "d-flat"
    elif (value > 0) == up_is_good:
        cls = "d-up"
    else:
        cls = "d-down"
    return Markup(f'<span class="{cls}">{arrow} {abs(value):.1f}%</span>')


def _kpi(label: str, value: str, wow: float | None, up_is_good: bool | None = True) -> Markup:
    sub = _delta(wow, up_is_good) if wow is not None else Markup('<span class="d-flat">—</span>')
    return Markup(
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub} <span class="meta" '
        f'style="color:var(--oc-rhythm);font-weight:500">vs last wk</span></div></div>'
    )


def _channel_color(name: str) -> str:
    low = (name or "").lower()
    for key, color in _CHANNEL_COLORS:
        if key in low:
            return color
    return "#333760"


def render(data: dict[str, Any], insights: dict[str, Any], *, sheet_url: str,
           model: str, target_cpa: float) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.globals.update(
        money=_money, num=_num, pctval=_pctval, delta=_delta, kpi=_kpi,
        channel_color=_channel_color,
    )
    tmpl = env.get_template("dashboard.html.j2")
    return tmpl.render(
        data=data,
        insights=insights,
        sheet_url=sheet_url,
        model=model,
        target_cpa=target_cpa,
        generated_at=dt.datetime.now().strftime("%b %d, %Y %H:%M"),
    )
