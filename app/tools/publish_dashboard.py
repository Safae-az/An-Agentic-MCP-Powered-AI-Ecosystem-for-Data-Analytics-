from __future__ import annotations

import json
import math
import os
from datetime import datetime
from html import escape
from typing import Any


# ─── SVG icon system ─────────────────────────────────────────────────────────

_IB: dict[str, str] = {
    "home":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    "bar":       '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
    "line":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "pie":       '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>',
    "scatter":   '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="8" r="2"/><circle cx="17" cy="6" r="2"/><circle cx="11" cy="16" r="2"/><circle cx="4" cy="17" r="2"/><circle cx="19" cy="14" r="2"/></svg>',
    "bulb":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>',
    "folder":    '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    "bell":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    "trophy":    '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>',
    "grid":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    "target":    '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    "dollar":    '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    "percent":   '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>',
    "users":     '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "calendar":  '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    "star":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    "maximize":  '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>',
    "minus-sq":  '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
    "plus-sq":   '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
    "download":  '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    "sun":       '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
    "moon":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
    "x":         '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    "layout":    '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>',
    "brain":     '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>',
    "file":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    "arrow-r":   '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
    "chevron-r": '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    "monitor":   '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    "alert-tri": '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    "check-ok":  '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    "package":   '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    "hash":      '<svg width="__Z__" height="__Z__" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>',
}


def _ic(name: str, sz: int = 16) -> str:
    return _IB.get(name, "").replace("__Z__", str(sz))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _asset_href(path: str, output_dir: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://", "data:", "#")):
        return path
    try:
        return os.path.relpath(path, output_dir).replace(os.sep, "/")
    except Exception:
        return path.replace(os.sep, "/")


def _safe_id(label: str) -> str:
    text = "".join(c.lower() if c.isalnum() else "-" for c in str(label))
    text = "-".join(p for p in text.split("-") if p)
    return text or "section"


def _human_title(key: str) -> str:
    text = str(key).replace("_", " ").replace("-", " ").replace(".", " / ")
    return " ".join(text.split()).title() or "KPI"


def _is_number(value: Any) -> bool:
    try:
        if value is None or value == "":
            return False
        float(value)
        return True
    except Exception:
        return False


def _guess_kind(key: str) -> str:
    k = str(key).lower()
    if any(w in k for w in ["rate", "ratio", "percent", "score", "quality", "churn", "attrition"]):
        return "percent"
    if any(w in k for w in ["sales", "revenue", "salary", "price", "amount", "profit", "cost", "balance", "ca"]):
        return "currency"
    return "number"


def _fmt_value(value: Any, kind: str = "number") -> str:
    try:
        n = float(value)
    except Exception:
        return "-"
    if kind == "percent":
        if abs(n) <= 1:
            n *= 100
        return f"{n:.1f}%"
    if kind == "currency":
        return f"{n:,.0f}" if abs(n) >= 1000 else f"{n:,.2f}"
    return f"{int(n):,}" if n.is_integer() else f"{n:,.2f}"


def _kind_icon(kind: str, key: str) -> str:
    k = str(key).lower()
    if kind == "currency":
        return _ic("dollar", 20)
    if kind == "percent":
        return _ic("percent", 20)
    if any(w in k for w in ["count", "nb", "employee", "customer", "user", "order", "total"]):
        return _ic("users", 20)
    if any(w in k for w in ["age", "time", "year", "month", "day", "date"]):
        return _ic("calendar", 20)
    if any(w in k for w in ["score", "quality", "rating", "satisfaction"]):
        return _ic("star", 20)
    return _ic("bar", 20)


def _hex_to_rgba(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    except Exception:
        return "90,248,232"


def _sparkline(value: float, w: int = 150, h: int = 44) -> str:
    seed = abs(int(value * 1000)) % 997 + 1
    pts = []
    for i in range(6):
        frac = ((seed * (i + 3) * 7) % 89) / 89.0
        x = (i / 5) * w
        y = h - 4 - frac * (h - 10)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _ring(pct: float, color: str = "#5af8e8") -> str:
    r = 14
    c = 2 * math.pi * r
    dash = min(pct / 100.0, 1.0) * c
    gap = max(c - dash, 0)
    return (
        f'<svg width="36" height="36" viewBox="0 0 36 36">'
        f'<circle cx="18" cy="18" r="{r}" fill="none" stroke="rgba(148,163,184,.18)" stroke-width="3"/>'
        f'<circle cx="18" cy="18" r="{r}" fill="none" stroke="{color}" stroke-width="3"'
        f' stroke-dasharray="{dash:.1f} {gap:.1f}" stroke-linecap="round" transform="rotate(-90 18 18)"/>'
        f'</svg>'
    )


# ─── Data helpers ─────────────────────────────────────────────────────────────

def _normalise_charts(charts: list | None, output_dir: str) -> list[dict]:
    out: list[dict] = []
    for i, c in enumerate(charts or [], 1):
        if not isinstance(c, dict):
            continue
        c = dict(c)
        c["title"] = c.get("title") or f"Chart {i}"
        c["slot"] = c.get("slot") or f"chart_{i}"
        c["source_key"] = c.get("source_key") or c.get("slot") or f"chart_{i}"
        c["chart_type"] = c.get("chart_type") or "chart"
        c["chart_href"] = _asset_href(str(c.get("chart_path", "")), output_dir)
        c["png_href"] = _asset_href(str(c.get("png_path", "")), output_dir)
        out.append(c)
    return out


def _fallback_metrics(kpis: dict) -> list[dict]:
    out: list[dict] = []
    for key, val in kpis.items():
        if str(key).startswith("_") or not _is_number(val):
            continue
        out.append({"key": str(key), "label": _human_title(str(key)), "value": float(val), "kind": _guess_kind(str(key))})
        if len(out) >= 8:
            break
    return out


# ─── Render helpers ───────────────────────────────────────────────────────────

_MC = ["#5af8e8", "#4cff9a", "#a887ff", "#ffd166", "#ff647c", "#00d5ff", "#ec4899", "#10b981"]

_CI = {"bar": "bar", "line": "line", "pie": "pie", "scatter": "scatter", "chart": "bar"}


def _render_metric_cards(kpis: dict) -> str:
    metrics = kpis.get("_dashboard_metrics") or _fallback_metrics(kpis)
    if not metrics:
        return '<section class="metric-card"><p class="metric-label">No KPI</p></section>'

    nums = [abs(float(m.get("value", 0))) for m in metrics if _is_number(m.get("value"))]
    max_val = max(nums) if nums else 1.0
    cards: list[str] = []

    for i, m in enumerate(metrics[:8]):
        key = str(m.get("key", "kpi"))
        label = str(m.get("label") or _human_title(key))
        val = m.get("value")
        kind = str(m.get("kind") or _guess_kind(key))
        color = _MC[i % len(_MC)]
        icon_svg = _kind_icon(kind, key)
        fmt = _fmt_value(val, kind)
        pct = min(abs(float(val)) / max_val * 100, 100) if _is_number(val) else 0
        raw = str(float(val)) if _is_number(val) else "0"
        rgba = _hex_to_rgba(color)
        spark = _sparkline(float(val) if _is_number(val) else 0)

        cards.append(
            f'<section class="metric-card reveal" style="--mc-color:{color}">'
            f'<div class="metric-head">'
            f'<span class="metric-icon" style="background:rgba({rgba},.15);color:{color}">{icon_svg}</span>'
            f'<div style="flex:1;min-width:0">'
            f'<p class="metric-label">{escape(label)}</p>'
            f'<span class="metric-value counter" data-target="{escape(raw)}" data-fmt="{kind}"'
            f' onclick="copyMetric(this)" title="Click to copy">{escape(fmt)}</span>'
            f'<p class="metric-delta" style="color:{color}">{_ic("bar",10)} {kind.title()}</p>'
            f'</div>'
            f'<div class="metric-ring">{_ring(pct, color)}</div>'
            f'</div>'
            f'<div class="metric-foot">'
            f'<svg viewBox="0 0 150 44" class="sparkline">'
            f'<defs><linearGradient id="sg{i}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0%" stop-color="{color}" stop-opacity="0.25"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="1"/>'
            f'</linearGradient></defs>'
            f'<polyline fill="none" stroke="url(#sg{i})" stroke-width="2.2"'
            f' stroke-linecap="round" stroke-linejoin="round" points="{spark}"/>'
            f'</svg>'
            f'</div>'
            f'</section>'
        )
    return "\n".join(cards)


def _render_chart_preview(chart: dict, index: int) -> str:
    """Static preview card for Overview tab — no iframe, no duplicate IDs."""
    title = str(chart.get("title") or f"Chart {index}")
    source_key = str(chart.get("source_key") or chart.get("slot") or f"chart_{index}")
    description = str(chart.get("description") or f"Source: {source_key}")
    chart_type = str(chart.get("chart_type") or "chart")
    icon_name = _CI.get(chart_type, "bar")
    color = _MC[(index - 1) % len(_MC)]
    rgba = _hex_to_rgba(color)

    return (
        f'<article class="panel chart-preview reveal" onclick="switchTab(\'analytics\')" tabindex="0">'
        f'<div class="preview-icon" style="background:rgba({rgba},.12);color:{color}">'
        f'{_ic(icon_name, 28)}'
        f'</div>'
        f'<h2 class="preview-title">{escape(title)}</h2>'
        f'<p class="panel-sub">{escape(description)}</p>'
        f'<div class="chart-btn view-btn">{_ic("arrow-r",13)} View in Analytics</div>'
        f'</article>'
    )


def _render_one_chart(chart: dict, index: int) -> str:
    """Full chart panel with iframe for Analytics tab."""
    title = str(chart.get("title") or f"Chart {index}")
    source_key = str(chart.get("source_key") or chart.get("slot") or f"chart_{index}")
    description = str(chart.get("description") or f"Source: {source_key}")
    chart_type = str(chart.get("chart_type") or "chart")
    chart_id = _safe_id(source_key)
    icon_name = _CI.get(chart_type, "bar")

    dl_btn = ""
    if chart.get("chart_href"):
        dl_btn = (
            f'<a class="chart-btn" href="{escape(chart["chart_href"])}" download title="Download HTML">'
            f'{_ic("download",13)}</a>'
        )

    fs_btn = (
        f'<button class="chart-btn" onclick="openChartFs(\'{escape(chart_id)}\')" title="Fullscreen">'
        f'{_ic("maximize",13)}</button>'
    )
    col_btn = (
        f'<button class="chart-btn" id="collapse-{escape(chart_id)}"'
        f' onclick="togglePanel(\'{escape(chart_id)}\')" title="Collapse">'
        f'{_ic("minus-sq",13)}</button>'
    )

    if chart.get("chart_href"):
        embed = (
            f'<div class="chart-skeleton" id="skel-{escape(chart_id)}">Loading chart&hellip;</div>'
            f'<iframe id="iframe-{escape(chart_id)}"'
            f' src="{escape(chart["chart_href"])}"'
            f' style="width:100%;height:400px;border:0;border-radius:12px;background:transparent;display:none;"'
            f' onload="iframeLoaded(\'{escape(chart_id)}\')"'
            f' onerror="iframeError(\'{escape(chart_id)}\')">'
            f'</iframe>'
        )
    else:
        embed = '<div class="empty">Chart artifact not available.</div>'

    span = "span-2" if index == 1 else ""
    return (
        f'<article class="panel {span} reveal" id="{escape(chart_id)}">'
        f'<div class="panel-header">'
        f'<div class="panel-header-left">'
        f'<span class="chart-type-icon" style="color:var(--accent)">{_ic(icon_name,20)}</span>'
        f'<div style="min-width:0"><h2>{escape(title)}</h2>'
        f'<p class="panel-sub">{escape(description)}</p></div>'
        f'</div>'
        f'<div class="panel-header-right">'
        f'<span class="badge">{escape(chart_type)}</span>'
        f'{col_btn}{fs_btn}{dl_btn}'
        f'</div>'
        f'</div>'
        f'<div class="chart-box" id="body-{escape(chart_id)}">{embed}</div>'
        f'</article>'
    )


def _render_previews(charts: list[dict]) -> str:
    if not charts:
        return '<article class="panel empty">No charts generated.</article>'
    return "\n".join(_render_chart_preview(c, i) for i, c in enumerate(charts, 1))


def _render_charts(charts: list[dict]) -> str:
    if not charts:
        return '<article class="panel span-2 empty">No charts generated.</article>'
    return "\n".join(_render_one_chart(c, i) for i, c in enumerate(charts, 1))


def _render_top_table(kpis: dict) -> str:
    metrics = kpis.get("_dashboard_metrics") or _fallback_metrics(kpis)
    if not metrics:
        return "<tr><td colspan='3'>No metrics available.</td></tr>"
    nums = [abs(float(m.get("value", 0))) for m in metrics if _is_number(m.get("value"))]
    max_val = max(nums or [1])
    rows: list[str] = []
    for idx, m in enumerate(metrics[:10], 1):
        key = str(m.get("key", "kpi"))
        label = str(m.get("label") or _human_title(key))
        val = m.get("value")
        kind = str(m.get("kind") or _guess_kind(key))
        pct = min(abs(float(val)) / max_val * 100, 100) if _is_number(val) else 0
        color = _MC[(idx - 1) % len(_MC)]
        rows.append(
            f'<tr><td><div class="ranked-metric">'
            f'<span class="rank-num">{idx:02d}</span>'
            f'<div style="min-width:0"><strong>{escape(label)}</strong>'
            f'<div class="bar"><i style="width:{pct:.1f}%;background:{color}"></i></div>'
            f'</div></div></td>'
            f'<td style="font-weight:800;color:{color}">{escape(_fmt_value(val, kind))}</td>'
            f'<td style="color:var(--muted)">{pct:.1f}%</td></tr>'
        )
    return "\n".join(rows)


def _render_alerts(alertes: list) -> str:
    if not alertes:
        return (
            f'<div class="alert ok"><strong>{_ic("check-ok",15)} All systems healthy</strong>'
            f'<p>No active alerts. All KPI thresholds within normal range.</p></div>'
        )
    blocks: list[str] = []
    for a in alertes[:8]:
        if not isinstance(a, dict):
            blocks.append(f'<div class="alert warning"><strong>{_ic("alert-tri",15)} Alert</strong><p>{escape(str(a))}</p></div>')
            continue
        title = a.get("kpi") or a.get("title") or "KPI Alert"
        msg = a.get("message") or a.get("description") or str(a)
        level = str(a.get("niveau") or a.get("level") or "warning").lower()
        blocks.append(
            f'<div class="alert {escape(level)}">'
            f'<strong>{_ic("alert-tri",15)} {escape(str(title))}</strong>'
            f'<p>{escape(str(msg))}</p></div>'
        )
    return "\n".join(blocks)


def _render_insights(insights: list) -> str:
    cleaned = [str(i).strip() for i in insights if str(i).strip() and set(str(i).strip()) > {"=", "-", "_"}][:10]
    if not cleaned:
        cleaned = ["Dashboard generated from the latest insights.json payload."]
    return "\n".join(f"<li>{escape(t)}</li>" for t in cleaned)


def _render_exports(output_path: str, output_dir: str, payload_path: str, manifest_path: str, charts: list[dict]) -> str:
    cards = [
        ("Dashboard HTML", "Main interactive dashboard", _asset_href(output_path, output_dir), "dashboard.html"),
        ("Payload JSON", "KPI data payload", _asset_href(payload_path, output_dir), "dashboard_payload.json"),
        ("Manifest JSON", "Artifact inventory", _asset_href(manifest_path, output_dir), "dashboard_artifacts_manifest.json"),
    ]
    for idx, c in enumerate(charts, 1):
        if c.get("chart_href"):
            cards.append((f"Chart {idx} HTML", str(c.get("title") or "Chart"), c["chart_href"], f"chart_{idx}.html"))
        if c.get("png_href"):
            cards.append((f"Chart {idx} PNG", str(c.get("title") or "Chart"), c["png_href"], f"chart_{idx}.png"))
    parts = [
        f'<div class="asset-card reveal"><strong>{_ic("file",15)} {escape(t)}</strong>'
        f'<span>{escape(s)}</span>'
        f'<a class="asset-btn" href="{escape(h)}" download="{escape(fn)}">{_ic("download",13)} Download</a></div>'
        for t, s, h, fn in cards
    ]
    return "\n".join(parts)


# ─── Main ─────────────────────────────────────────────────────────────────────

def publish_dashboard(
    charts: list[dict],
    run_id: str,
    kpis: dict | None = None,
    alertes: list[dict] | None = None,
    insights: list[str] | None = None,
    agent_context: dict | None = None,
) -> dict:
    try:
        kpis = kpis or {}
        alertes = alertes or []
        insights = insights or []
        agent_context = agent_context or {}

        output_path = f"runs/{run_id}/artifacts/dashboard.html"
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        payload_path = f"runs/{run_id}/artifacts/dashboard_payload.json"
        manifest_path = f"runs/{run_id}/artifacts/dashboard_artifacts_manifest.json"

        nc = _normalise_charts(charts, output_dir)
        print("[publish_dashboard] charts:", len(nc), [c.get("slot") for c in nc])

        domain = _human_title(str(
            kpis.get("_dashboard_domain") or agent_context.get("domain") or kpis.get("domain_detected") or "Business"
        ))
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        hero_metrics = kpis.get("_dashboard_metrics") or _fallback_metrics(kpis)

        # Build hero stats HTML
        hero_stats_html = ""
        for m in hero_metrics[:4]:
            lbl = str(m.get("label") or _human_title(str(m.get("key", ""))))
            val = m.get("value")
            knd = str(m.get("kind") or _guess_kind(str(m.get("key", ""))))
            raw = str(float(val)) if _is_number(val) else "0"
            hero_stats_html += (
                f'<div class="hero-stat">'
                f'<div class="hero-stat-label">{escape(lbl)}</div>'
                f'<div class="hero-stat-value counter" data-target="{escape(raw)}" data-fmt="{knd}">'
                f'{escape(_fmt_value(val, knd))}</div>'
                f'</div>'
            )

        metric_cards_html = _render_metric_cards(kpis)
        # Overview: preview cards only (NO iframes → no duplicate IDs)
        overview_html = _render_previews(nc)
        # Analytics: full iframe panels
        all_charts_html = _render_charts(nc)
        top_table_html = _render_top_table(kpis)
        alerts_html = _render_alerts(alertes)
        insights_html = _render_insights(insights)

        original_keys = agent_context.get("original_kpi_keys") or kpis.get("_original_kpi_keys", [])
        chart_keys = agent_context.get("chart_series_keys") or [c.get("source_key") for c in nc if c.get("source_key")]
        pipeline = " &rarr; ".join(agent_context.get("received_from", ["data_scientist"]) + ["bi_agent"])

        export_cards_html = _render_exports(output_path, output_dir, payload_path, manifest_path, nc)

        flow_steps = "".join(
            f'<div class="flow-step"><span class="flow-index">{i+1}</span>'
            f'<span class="flow-label">{escape(s)}</span></div>'
            for i, s in enumerate(agent_context.get("flow", ["Data Engineer", "Data Scientist", "BI Agent", "Reporter"]))
        )

        nb_charts = len(nc)
        nb_metrics = len(hero_metrics[:8])
        nb_alerts = len(alertes)

        # ── CSS (plain string — CSS braces are literal) ──────────────────────
        css = """
:root{--bg:#050713;--sidebar:#07111f;--card:#0b192f;--card-alt:#10223d;
--glass:rgba(8,18,38,0.78);--glass-border:rgba(111,255,233,0.22);
--text:#f6fbff;--muted:#91a4bc;--border:rgba(111,255,233,0.16);
--accent:#5af8e8;--accent2:#4cff9a;--success:#4cff9a;--warning:#ffd166;--danger:#ff647c;
--shadow:0 26px 80px rgba(0,0,0,.42);--glow:0 0 34px rgba(90,248,232,.18);--blur:blur(16px);--drawer:248px;
--topbar-h:54px;--banner-h:36px;}
body.light{--bg:#f0f4f8;--sidebar:#fff;--card:#fff;--card-alt:#f7f9fc;
--glass:rgba(255,255,255,0.84);--glass-border:rgba(15,23,42,0.10);
--text:#132136;--muted:#5f728a;--border:rgba(15,23,42,0.10);
--accent:#0891b2;--accent2:#16a34a;--shadow:0 12px 32px rgba(0,0,0,.08);--glow:0 0 0 rgba(0,0,0,0);}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{min-height:100vh;font-family:Inter,Segoe UI,Arial,sans-serif;color:var(--text);
background:var(--bg);overflow-x:hidden;position:relative;transition:background .3s,color .3s;}
body::before{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
background:radial-gradient(ellipse 62% 52% at 8% 4%,rgba(90,248,232,.18),transparent),
radial-gradient(ellipse 55% 45% at 92% 0%,rgba(76,255,154,.12),transparent),
linear-gradient(180deg,var(--bg),#03040b 80%);
animation:meshMove 22s ease-in-out infinite alternate;}
body::after{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
background:linear-gradient(rgba(255,255,255,.02) 1px,transparent 1px),
linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
background-size:56px 56px;mask-image:linear-gradient(to bottom,black 0%,transparent 86%);}
body.light::before{background:
radial-gradient(ellipse 65% 55% at 9% 4%,rgba(37,99,235,.08),transparent),
radial-gradient(ellipse 55% 45% at 92% 0%,rgba(124,58,237,.07),transparent),
linear-gradient(180deg,#f0f4f8,#e2eaf4 80%);
animation:meshMoveLt 22s ease-in-out infinite alternate;}
@keyframes meshMove{0%{background-position:0% 0%,100% 0%,0% 0%}
40%{background-position:6% 9%,94% 6%,0% 0%}100%{background-position:18% 12%,80% 3%,0% 0%}}
@keyframes meshMoveLt{0%{background-position:0% 0%,100% 0%,0% 0%}
100%{background-position:18% 10%,82% 2%,0% 0%}}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.reveal{animation:fadeUp .55s ease both}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
a{color:inherit;text-decoration:none}
svg{display:inline-block;vertical-align:middle;flex-shrink:0}
.shell{display:grid;grid-template-columns:var(--drawer) 1fr;min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;padding:18px 14px;
background:linear-gradient(180deg,rgba(7,17,31,.98),rgba(3,8,20,.96));
border-right:1px solid var(--border);overflow-y:auto;z-index:40;
display:flex;flex-direction:column;}
body.light .sidebar{background:#fff;border-right-color:var(--border)}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:24px;
padding-bottom:18px;border-bottom:1px solid var(--border);}
.brand-badge{width:40px;height:40px;border-radius:14px;flex:0 0 auto;
background:linear-gradient(135deg,var(--accent),var(--accent2));
box-shadow:0 0 24px rgba(90,248,232,.48);
display:grid;place-items:center;color:#04111f;}
.brand strong{font-size:15px;letter-spacing:.2px;display:block}
.brand small{font-size:11px;color:var(--muted);margin-top:2px;display:block}
.nav-label{font-size:10px;letter-spacing:.14em;text-transform:uppercase;
color:var(--muted);font-weight:800;padding:14px 10px 6px;opacity:.55;}
.nav{display:grid;gap:3px}
.nav a{display:flex;align-items:center;gap:10px;padding:10px 11px;border-radius:12px;
color:var(--muted);font-weight:700;font-size:13px;transition:all .18s;cursor:pointer;}
.nav a:hover,.nav a.active{background:rgba(90,248,232,.11);color:var(--text)}
.nav-icon{font-size:16px;flex:0 0 auto;width:20px;display:flex;align-items:center;justify-content:center}
.sidebar-footer{margin-top:auto;padding-top:14px;border-top:1px solid var(--border);
font-size:11px;color:var(--muted);line-height:1.7;}
.page{padding:0 22px 36px;max-width:1720px;width:100%;margin:0 auto}
.topbar-fixed{position:sticky;top:0;z-index:30;height:var(--topbar-h);
background:rgba(7,17,31,.90);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
border-bottom:1px solid var(--border);display:flex;align-items:center;
justify-content:space-between;gap:16px;padding:0 22px;margin:0 -22px;}
body.light .topbar-fixed{background:rgba(240,244,248,.93)}
.breadcrumb{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:700}
.bc-root{color:var(--muted)}.bc-domain{color:var(--text)}
.topbar-meta{font-size:11px;color:var(--muted);white-space:nowrap}
.topbar-actions{display:flex;align-items:center;gap:8px}
.btn-icon{width:32px;height:32px;border-radius:10px;border:1px solid var(--border);
background:var(--glass);backdrop-filter:var(--blur);color:var(--text);
cursor:pointer;display:grid;place-items:center;transition:all .18s;}
.btn-icon:hover{border-color:var(--accent);background:rgba(90,248,232,.14)}
.summary-banner{position:sticky;top:var(--topbar-h);z-index:29;height:var(--banner-h);
background:rgba(5,13,24,.84);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
border-bottom:1px solid var(--border);display:flex;align-items:center;gap:14px;
padding:0 22px;font-size:12px;font-weight:700;margin:0 -22px;}
body.light .summary-banner{background:rgba(240,244,248,.90)}
.sb-item{display:flex;align-items:center;gap:6px}
.sb-dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex:0 0 auto}
.dot-blue{background:var(--accent);box-shadow:0 0 0 3px rgba(90,248,232,.18)}
.dot-green{background:var(--success);box-shadow:0 0 0 3px rgba(76,255,154,.18)}
.dot-amber{background:var(--warning);box-shadow:0 0 0 3px rgba(255,209,102,.18)}
.dot-purple{background:#a887ff;box-shadow:0 0 0 3px rgba(168,135,255,.18)}
.sb-div{width:1px;height:14px;background:var(--border)}
.tab-bar{display:flex;gap:2px;padding:14px 0 0;margin-bottom:16px;border-bottom:1px solid var(--border);}
.tab-btn{padding:9px 20px;border-radius:12px 12px 0 0;border:1px solid transparent;
border-bottom:none;background:none;color:var(--muted);font-family:inherit;
font-size:13px;font-weight:700;cursor:pointer;transition:all .18s;
position:relative;bottom:-1px;display:inline-flex;align-items:center;gap:7px;}
.tab-btn:hover{color:var(--text);background:rgba(90,248,232,.07)}
.tab-btn.active{background:var(--glass);backdrop-filter:var(--blur);color:var(--text);border-color:var(--border);}
.tab-pane{display:none}.tab-pane.active{display:block}
.section-heading{margin:0 0 16px;padding-bottom:10px;border-bottom:2px solid;
border-image:linear-gradient(90deg,var(--accent),var(--accent2),transparent) 1;}
.section-heading .eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.15em;
color:var(--accent);font-weight:800;margin-bottom:4px;}
.section-heading h2{font-size:20px;letter-spacing:-.3px;color:var(--text)}
.hero{position:relative;border:1px solid var(--glass-border);border-radius:18px;
background:linear-gradient(135deg,rgba(8,18,38,.86),rgba(5,9,23,.58)),
radial-gradient(circle at 82% 22%,rgba(90,248,232,.16),transparent 34%);
backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
box-shadow:var(--shadow),var(--glow),inset 0 1px 0 rgba(255,255,255,.08);padding:30px;margin-bottom:18px;overflow:hidden;}
.hero::after{content:'';position:absolute;top:-40px;right:-40px;width:220px;height:220px;
border-radius:50%;pointer-events:none;
background:radial-gradient(circle,rgba(90,248,232,.14),transparent 70%);}
.hero::before{content:'';position:absolute;left:0;right:0;bottom:0;height:3px;
background:linear-gradient(90deg,transparent,var(--accent),var(--accent2),transparent);
box-shadow:0 0 24px rgba(90,248,232,.75);}
.eyebrow{text-transform:uppercase;letter-spacing:.18em;color:var(--accent);font-size:11px;font-weight:800;margin-bottom:8px}
.headline{font-size:36px;line-height:1.05;margin:0 0 10px;letter-spacing:-1px;
background:linear-gradient(135deg,var(--text) 55%,var(--accent));
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.subtitle{color:var(--muted);line-height:1.7;max-width:900px;font-size:14px}
.hero-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:22px}
.hero-stat{border:1px solid var(--glass-border);border-radius:18px;
background:rgba(255,255,255,.04);padding:14px;transition:transform .2s,box-shadow .2s;}
.hero-stat:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(90,248,232,.14)}
.hero-stat-label{font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:800}
.hero-stat-value{font-size:22px;font-weight:800;margin-top:6px;color:var(--accent);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.grid{display:grid;gap:16px}
.metrics{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:16px}
.charts-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.metric-card{--mc-color:var(--accent);position:relative;border:1px solid var(--glass-border);
border-radius:16px;background:linear-gradient(180deg,rgba(255,255,255,.04),transparent),var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
box-shadow:var(--shadow);padding:18px;min-height:130px;overflow:hidden;
transition:transform .2s,box-shadow .2s,border-color .2s;}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
background:linear-gradient(90deg,var(--mc-color),transparent);border-radius:22px 22px 0 0;}
.metric-card:hover{transform:translateY(-3px);box-shadow:0 20px 44px rgba(0,0,0,.24),0 0 24px rgba(90,248,232,.12);border-color:var(--mc-color);}
.metric-head{display:flex;align-items:flex-start;gap:11px}
.metric-icon{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;flex:0 0 auto;}
.metric-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.1em;font-weight:800;margin:0 0 4px}
.metric-value{font-size:24px;font-weight:800;color:var(--text);cursor:pointer;
display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
transition:opacity .15s,color .15s;}
.metric-value:hover{opacity:.75;color:var(--mc-color)}
.metric-delta{margin:4px 0 0;font-size:11px;font-weight:800;display:flex;align-items:center;gap:4px}
.metric-ring{flex:0 0 auto;margin-left:auto}
.metric-foot{margin-top:10px}.sparkline{width:100%;height:44px;opacity:.85}
.metric-search-bar{margin-bottom:12px}
.metric-search-input{padding:9px 14px;border-radius:12px;border:1px solid var(--border);
background:var(--glass);backdrop-filter:var(--blur);color:var(--text);
font-size:13px;font-family:inherit;outline:none;transition:border-color .18s,box-shadow .18s;
width:100%;max-width:360px;}
.metric-search-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(90,248,232,.12)}
.metric-search-input::placeholder{color:var(--muted)}
.panel{position:relative;border:1px solid var(--glass-border);border-radius:16px;
background:linear-gradient(180deg,rgba(255,255,255,.035),transparent),var(--glass);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
box-shadow:var(--shadow);padding:18px;min-height:200px;overflow:hidden;
transition:border-color .2s,box-shadow .2s;}
.panel:hover{border-color:rgba(90,248,232,.34);box-shadow:var(--shadow),0 0 28px rgba(90,248,232,.1)}
.panel-header{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:14px}
.panel-header-left{display:flex;align-items:flex-start;gap:10px;min-width:0;flex:1}
.chart-type-icon{flex:0 0 auto;margin-top:2px}
.panel-header h2{font-size:16px;margin:0 0 4px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.panel-sub{margin:0;color:var(--muted);font-size:12px;line-height:1.4}
.panel-header-right{display:flex;align-items:center;gap:6px;flex-shrink:0}
.badge{border:1px solid var(--border);background:rgba(90,248,232,.08);color:var(--accent);
border-radius:999px;padding:4px 10px;font-size:11px;font-weight:800;white-space:nowrap;}
.chart-btn{display:inline-flex;align-items:center;gap:5px;padding:5px 10px;border-radius:8px;
border:1px solid var(--border);background:rgba(90,248,232,.08);color:var(--accent);
font-size:12px;font-weight:700;font-family:inherit;cursor:pointer;text-decoration:none;
white-space:nowrap;transition:background .18s,transform .12s,border-color .18s;}
.chart-btn:hover{background:rgba(90,248,232,.18);border-color:var(--accent);transform:translateY(-1px)}
.chart-box{min-height:280px}
.chart-skeleton{height:390px;border-radius:12px;display:flex;align-items:center;
justify-content:center;color:var(--muted);font-size:13px;font-weight:700;
background:linear-gradient(90deg,rgba(148,163,184,.06) 25%,rgba(148,163,184,.13) 50%,rgba(148,163,184,.06) 75%);
background-size:200% 100%;animation:shimmer 1.8s infinite linear;}
.chart-preview{cursor:pointer;display:flex;flex-direction:column;align-items:center;
justify-content:center;text-align:center;gap:14px;min-height:220px;padding:32px 24px;}
.chart-preview:hover{transform:translateY(-4px);border-color:var(--accent);}
.preview-icon{width:64px;height:64px;border-radius:20px;display:grid;place-items:center;}
.preview-title{font-size:16px;color:var(--text);font-weight:700}
.view-btn{margin-top:4px}
.chart-fs-overlay{position:fixed;inset:0;z-index:9999;background:rgba(7,17,31,.93);
backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);
display:none;align-items:center;justify-content:center;}
.chart-fs-overlay.open{display:flex}
.chart-fs-inner{position:relative;width:92vw;height:87vh;background:var(--card);
border-radius:24px;border:1px solid var(--glass-border);padding:18px;
display:flex;flex-direction:column;box-shadow:0 40px 80px rgba(0,0,0,.5);}
.chart-fs-title{font-size:16px;font-weight:800;color:var(--text);margin-bottom:12px;flex:0 0 auto}
.chart-fs-close{position:absolute;top:14px;right:14px;width:34px;height:34px;border-radius:50%;
background:rgba(148,163,184,.12);border:1px solid var(--border);cursor:pointer;color:var(--text);
display:flex;align-items:center;justify-content:center;transition:background .18s,color .18s;z-index:10;}
.chart-fs-close:hover{background:rgba(249,115,22,.22);color:#f97316}
.chart-fs-mount{flex:1;min-height:0}
.chart-fs-mount iframe{width:100%;height:100%;border:0;background:transparent;border-radius:12px}
.span-2{grid-column:span 2}.span-full{grid-column:1/-1}
.table{width:100%;border-collapse:collapse;margin-top:8px}
.table th{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);
text-align:left;padding:10px 8px;border-bottom:1px solid var(--border);font-weight:800;}
.table td{padding:11px 8px;border-bottom:1px solid var(--border);font-size:13px}
.table tr:last-child td{border-bottom:none}
.table tr:hover td{background:rgba(90,248,232,.04)}
.ranked-metric{display:grid;grid-template-columns:32px 1fr;gap:10px;align-items:center}
.rank-num{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;
font-size:11px;font-weight:900;color:var(--accent);background:rgba(90,248,232,.1);}
.bar{height:5px;border-radius:999px;background:rgba(148,163,184,.15);overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;border-radius:inherit}
.alert{padding:13px 15px;border:1px solid var(--border);border-radius:16px;
background:rgba(255,255,255,.03);margin-bottom:10px;transition:transform .18s;}
.alert:hover{transform:translateX(3px)}
.alert strong{display:block;margin-bottom:4px;font-size:13px;display:flex;align-items:center;gap:6px}
.alert p{margin:0;color:var(--muted);font-size:12px;line-height:1.5}
.alert.ok{border-color:rgba(34,197,94,.25);background:rgba(34,197,94,.06)}
.alert.warning{border-color:rgba(245,158,11,.28);background:rgba(245,158,11,.06)}
.alert.critical,.alert.error{border-color:rgba(249,115,22,.28);background:rgba(249,115,22,.06)}
.insight-box ul{padding-left:0;margin:10px 0 0;list-style:none}
.insight-box li{margin-bottom:9px;color:var(--muted);font-size:13px;line-height:1.65;
padding:8px 12px;border-left:3px solid var(--accent);
background:rgba(90,248,232,.04);border-radius:0 10px 10px 0;}
.flow-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:14px}
.flow-step{display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:12px;
border:1px solid rgba(90,248,232,.18);background:rgba(90,248,232,.06);}
.flow-index{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;
background:rgba(90,248,232,.16);font-size:11px;font-weight:900;color:var(--accent);flex:0 0 auto;}
.flow-label{font-size:11px;font-weight:700;color:var(--muted)}
.meta{color:var(--muted);line-height:1.8;font-size:13px}.meta strong{color:var(--text)}
.asset-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.asset-card{border:1px solid var(--glass-border);border-radius:18px;padding:16px;
background:var(--glass);backdrop-filter:var(--blur);
transition:transform .18s,box-shadow .18s,border-color .18s;}
.asset-card:hover{transform:translateY(-3px);box-shadow:0 14px 30px rgba(90,248,232,.14);border-color:rgba(90,248,232,.3)}
.asset-card strong{display:block;margin-bottom:4px;font-size:13px;display:flex;align-items:center;gap:5px}
.asset-card span{display:block;color:var(--muted);font-size:12px;margin-bottom:14px}
.asset-btn{border:1px solid var(--border);background:rgba(90,248,232,.08);color:var(--accent);
border-radius:10px;padding:7px 12px;display:inline-flex;align-items:center;gap:6px;
font-size:12px;font-weight:800;font-family:inherit;transition:all .18s;text-decoration:none;}
.asset-btn:hover{border-color:var(--accent);background:rgba(90,248,232,.18);transform:translateY(-1px)}
.toast{position:fixed;right:22px;bottom:22px;max-width:340px;padding:12px 16px;
border-radius:14px;z-index:10000;border:1px solid rgba(90,248,232,.25);
background:rgba(8,19,34,.96);backdrop-filter:var(--blur);color:#fff;font-size:13px;
font-weight:700;box-shadow:0 16px 40px rgba(0,0,0,.3);opacity:0;transform:translateY(16px);
pointer-events:none;transition:all .22s;}
.toast.show{opacity:1;transform:translateY(0)}
.empty{padding:32px;border:1px dashed var(--border);border-radius:16px;
color:var(--muted);text-align:center;font-weight:700;font-size:13px;}
@media(max-width:1380px){.metrics{grid-template-columns:repeat(3,minmax(0,1fr))}
.hero-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
.asset-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.flow-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:1100px){.shell{grid-template-columns:1fr}.sidebar{display:none}
.span-2{grid-column:span 1}.charts-grid{grid-template-columns:1fr}
.page{padding:0 14px 24px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:720px){.metrics,.hero-stats,.asset-card-grid,.flow-grid{grid-template-columns:1fr}
.headline{font-size:26px}.tab-btn{padding:8px 12px;font-size:12px}
.metric-search-input{max-width:100%}}
"""

        # ── JS (plain string — JS braces are literal) ────────────────────────
        js = """
function setTheme(t) {
    document.body.classList.toggle('light', t === 'light');
    var btn = document.getElementById('themeBtn');
    if (btn) btn.innerHTML = (t === 'light') ? moonIcon : sunIcon;
    try { localStorage.setItem('kpiops-theme', t); } catch(e) {}
}
function toggleTheme() {
    setTheme(document.body.classList.contains('light') ? 'dark' : 'light');
}
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(function(b) {
        b.classList.toggle('active', b.dataset.tab === name);
    });
    document.querySelectorAll('.tab-pane').forEach(function(p) {
        p.classList.toggle('active', p.id === 'tab-' + name);
    });
    // Fix: ensure any already-loaded iframes in the newly visible tab become visible
    setTimeout(function() {
        var pane = document.getElementById('tab-' + name);
        if (pane) {
            pane.querySelectorAll('iframe').forEach(function(fr) {
                if (fr.src && fr.src !== 'about:blank') {
                    iframeLoaded(fr.id.replace('iframe-', ''));
                }
            });
        }
    }, 60);
    if (name === 'overview') { setTimeout(startCounters, 80); }
    try { localStorage.setItem('kpiops-tab', name); } catch(e) {}
    setupObserver();
}
function showToast(msg) {
    var t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(window._toast);
    window._toast = setTimeout(function() { t.classList.remove('show'); }, 2800);
}
function fmtNum(n, fmt) {
    if (fmt === 'percent') { var v = Math.abs(n) <= 1 ? n * 100 : n; return v.toFixed(1) + '%'; }
    if (fmt === 'currency') {
        if (Math.abs(n) >= 1000) return n.toLocaleString('en-US', {maximumFractionDigits: 0});
        return n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }
    if (Math.abs(n - Math.round(n)) < 0.001) return Math.round(n).toLocaleString('en-US');
    return n.toLocaleString('en-US', {maximumFractionDigits: 2});
}
function animateCounter(el) {
    var target = parseFloat(el.dataset.target);
    if (isNaN(target)) return;
    var fmt = el.dataset.fmt || 'number', dur = 1100, startT = null;
    function step(ts) {
        if (!startT) startT = ts;
        var p = Math.min((ts - startT) / dur, 1);
        p = 1 - Math.pow(1 - p, 3);
        el.textContent = fmtNum(p * target, fmt);
        if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}
function startCounters() {
    document.querySelectorAll('.tab-pane.active .counter, .hero-stat-value.counter').forEach(animateCounter);
}
function filterMetrics(q) {
    q = q.toLowerCase().trim();
    document.querySelectorAll('.metric-card').forEach(function(card) {
        var lbl = (card.querySelector('.metric-label') || {}).textContent || '';
        card.style.display = (!q || lbl.toLowerCase().includes(q)) ? '' : 'none';
    });
}
function copyMetric(el) {
    var text = el.dataset.target || el.textContent.trim();
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text)
            .then(function() { showToast('Copied: ' + el.textContent.trim()); })
            .catch(function() { showToast('Copy failed.'); });
    } else { showToast('Copy not supported.'); }
}
function iframeLoaded(id) {
    var skel = document.getElementById('skel-' + id);
    var fr   = document.getElementById('iframe-' + id);
    if (skel) skel.style.display = 'none';
    if (fr)   fr.style.display = 'block';
}
function iframeError(id) {
    var skel = document.getElementById('skel-' + id);
    if (skel) {
        skel.style.animation = 'none'; skel.style.background = 'none';
        skel.innerHTML = '<div class="empty">Chart failed to load.</div>';
    }
}
function togglePanel(id) {
    var body = document.getElementById('body-' + id);
    var btn  = document.getElementById('collapse-' + id);
    if (!body) return;
    var open = body.style.display === 'none';
    body.style.display = open ? '' : 'none';
    if (btn) btn.innerHTML = (open ? collapseIcon : expandIcon) + (open ? '' : '');
}
function openChartFs(id) {
    var overlay = document.getElementById('chart-fs-overlay');
    var mount   = document.getElementById('chart-fs-mount');
    var titleEl = document.getElementById('chart-fs-title');
    var fr      = document.getElementById('iframe-' + id);
    var panel   = document.getElementById(id);
    if (!overlay || !fr) return;
    mount.innerHTML = '';
    var clone = document.createElement('iframe');
    clone.src = fr.src;
    clone.style.cssText = 'width:100%;height:100%;border:0;background:transparent;border-radius:12px;';
    mount.appendChild(clone);
    if (titleEl && panel) { var h2 = panel.querySelector('h2'); titleEl.textContent = h2 ? h2.textContent : ''; }
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
}
function closeChartFs() {
    var overlay = document.getElementById('chart-fs-overlay');
    if (overlay) { overlay.classList.remove('open'); document.getElementById('chart-fs-mount').innerHTML = ''; }
    document.body.style.overflow = '';
}
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeChartFs(); });
var _obs = null;
function setupObserver() {
    if (_obs) _obs.disconnect();
    var secs = document.querySelectorAll('.tab-pane.active section[id],.tab-pane.active article[id]');
    if (!secs.length) return;
    _obs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
            if (e.isIntersecting) {
                document.querySelectorAll('.nav a').forEach(function(a) {
                    a.classList.toggle('active', a.getAttribute('href') === '#' + e.target.id);
                });
            }
        });
    }, { threshold: 0.2, rootMargin: '-54px 0px -50% 0px' });
    secs.forEach(function(s) { _obs.observe(s); });
}
function updateBanner() {
    var charts  = document.querySelectorAll('.panel').length;
    var metrics = document.querySelectorAll('.metric-card').length;
    var alerts  = document.querySelectorAll('.alert.warning,.alert.critical,.alert.error').length;
    var el;
    el = document.getElementById('sb-charts');  if (el) el.textContent = charts  + ' charts';
    el = document.getElementById('sb-metrics'); if (el) el.textContent = metrics + ' metrics';
    el = document.getElementById('sb-alerts');  if (el) el.textContent = alerts  + ' alerts';
}
function staggerReveal() {
    document.querySelectorAll('.reveal').forEach(function(el, i) {
        el.style.animationDelay = (Math.min(i, 12) * 0.045) + 's';
    });
}
document.addEventListener('DOMContentLoaded', function() {
    var theme = ''; try { theme = localStorage.getItem('kpiops-theme') || ''; } catch(e) {}
    setTheme(theme || 'dark');
    var tab = ''; try { tab = localStorage.getItem('kpiops-tab') || ''; } catch(e) {}
    switchTab(tab || 'overview');
    setTimeout(startCounters, 160);
    updateBanner(); staggerReveal(); setupObserver();
});
"""

        # Icon strings for JS (injected as variables)
        sun_icon_svg = _ic("sun", 16).replace("'", "\\'")
        moon_icon_svg = _ic("moon", 16).replace("'", "\\'")
        collapse_icon_svg = _ic("minus-sq", 13).replace("'", "\\'")
        expand_icon_svg = _ic("plus-sq", 13).replace("'", "\\'")

        js_icons = (
            f"var sunIcon='{sun_icon_svg}';"
            f"var moonIcon='{moon_icon_svg}';"
            f"var collapseIcon='{collapse_icon_svg}';"
            f"var expandIcon='{expand_icon_svg}';"
        )

        # ── HTML (f-string) ──────────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>KPI Ops &mdash; {escape(domain)} Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>{css}</style>
</head>
<body>
<div class="shell">

<aside class="sidebar">
  <div class="brand">
    <div class="brand-badge">{_ic("monitor", 22)}</div>
    <div><strong>KPI Ops</strong><small>Agentic BI Workspace</small></div>
  </div>
  <div class="nav-label">Navigation</div>
  <nav class="nav">
    <a onclick="switchTab('overview')" href="#tab-overview">
      <span class="nav-icon">{_ic("layout")}</span>Overview
    </a>
    <a onclick="switchTab('analytics')" href="#tab-analytics">
      <span class="nav-icon">{_ic("bar")}</span>Analytics
    </a>
    <a onclick="switchTab('insights')" href="#tab-insights">
      <span class="nav-icon">{_ic("bulb")}</span>Insights
    </a>
    <a onclick="switchTab('exports')" href="#tab-exports">
      <span class="nav-icon">{_ic("folder")}</span>Exports
    </a>
  </nav>
  <div class="nav-label">Sections</div>
  <nav class="nav">
    <a onclick="switchTab('overview')" href="#hero-section">
      <span class="nav-icon">{_ic("target")}</span>Executive View
    </a>
    <a onclick="switchTab('overview')" href="#metrics-section">
      <span class="nav-icon">{_ic("grid")}</span>KPI Cards
    </a>
    <a onclick="switchTab('analytics')" href="#charts-section">
      <span class="nav-icon">{_ic("bar")}</span>Charts
    </a>
    <a onclick="switchTab('analytics')" href="#top-metrics">
      <span class="nav-icon">{_ic("trophy")}</span>Top Metrics
    </a>
    <a onclick="switchTab('insights')" href="#alerts-section">
      <span class="nav-icon">{_ic("bell")}</span>Alerts
    </a>
  </nav>
  <div class="sidebar-footer">
    <small>Generated: {escape(created_at)}<br/>Run: {escape(run_id)}</small>
  </div>
</aside>

<main class="page">

  <div class="topbar-fixed">
    <div class="breadcrumb">
      <span class="bc-root">KPI Ops</span>
      <span style="color:var(--muted);opacity:.4">{_ic("chevron-r",12)}</span>
      <span class="bc-domain">{escape(domain)}</span>
    </div>
    <div class="topbar-meta">Run {escape(run_id)} &nbsp;&middot;&nbsp; {escape(created_at)}</div>
    <div class="topbar-actions">
      <button class="btn-icon" id="themeBtn" onclick="toggleTheme()" title="Toggle light / dark">
        {_ic("sun", 16)}
      </button>
    </div>
  </div>

  <div class="summary-banner">
    <div class="sb-item"><span class="sb-dot dot-blue"></span><span id="sb-charts">{nb_charts} charts</span></div>
    <div class="sb-div"></div>
    <div class="sb-item"><span class="sb-dot dot-green"></span><span id="sb-metrics">{nb_metrics} metrics</span></div>
    <div class="sb-div"></div>
    <div class="sb-item"><span class="sb-dot dot-amber"></span><span id="sb-alerts">{nb_alerts} alerts</span></div>
    <div class="sb-div"></div>
    <div class="sb-item"><span class="sb-dot dot-purple"></span><span>Domain: {escape(domain)}</span></div>
  </div>

  <div class="tab-bar" role="tablist">
    <button class="tab-btn active" data-tab="overview"  onclick="switchTab('overview')"  role="tab">{_ic("layout",14)} Overview</button>
    <button class="tab-btn"        data-tab="analytics" onclick="switchTab('analytics')" role="tab">{_ic("bar",14)} Analytics</button>
    <button class="tab-btn"        data-tab="insights"  onclick="switchTab('insights')"  role="tab">{_ic("bulb",14)} Insights</button>
    <button class="tab-btn"        data-tab="exports"   onclick="switchTab('exports')"   role="tab">{_ic("folder",14)} Exports</button>
  </div>

  <!-- OVERVIEW TAB -->
  <div id="tab-overview" class="tab-pane active">
    <section class="hero reveal" id="hero-section">
      <div class="eyebrow">Autonomous BI Dashboard</div>
      <h1 class="headline">{escape(domain)} Overview</h1>
      <p class="subtitle">Agentic BI pipeline &mdash; automatic KPI detection, distribution analysis and interactive chart generation.</p>
      <div class="hero-stats">{hero_stats_html}</div>
    </section>
    <div class="section-heading reveal">
      <div class="eyebrow">Key Performance Indicators</div>
      <h2>Metric Cards</h2>
    </div>
    <div class="metric-search-bar">
      <input class="metric-search-input" type="text" id="metric-search"
             placeholder="Filter metrics..." oninput="filterMetrics(this.value)"/>
    </div>
    <section class="grid metrics" id="metrics-section">{metric_cards_html}</section>
    <div class="section-heading reveal">
      <div class="eyebrow">Chart Highlights</div>
      <h2>Featured Charts &mdash; click to open Analytics</h2>
    </div>
    <section class="grid charts-grid" id="overview-charts">{overview_html}</section>
  </div>

  <!-- ANALYTICS TAB -->
  <div id="tab-analytics" class="tab-pane">
    <div class="section-heading reveal">
      <div class="eyebrow">Visualizations</div>
      <h2>All Charts</h2>
    </div>
    <section class="grid charts-grid" id="charts-section">{all_charts_html}</section>
    <section class="grid" style="margin-top:16px" id="top-metrics">
      <article class="panel span-2 reveal">
        <div class="panel-header">
          <div class="panel-header-left">
            <span class="chart-type-icon" style="color:var(--accent)">{_ic("trophy",20)}</span>
            <div><h2>Top Metrics</h2><p class="panel-sub">KPIs ranked by absolute value.</p></div>
          </div>
          <span class="badge">Auto-detected</span>
        </div>
        <table class="table">
          <thead><tr><th>Metric</th><th>Value</th><th>Share</th></tr></thead>
          <tbody>{top_table_html}</tbody>
        </table>
      </article>
    </section>
  </div>

  <!-- INSIGHTS TAB -->
  <div id="tab-insights" class="tab-pane">
    <section class="grid" id="alerts-section" style="margin-bottom:16px">
      <article class="panel span-full reveal">
        <div class="panel-header">
          <div class="panel-header-left">
            <span class="chart-type-icon" style="color:var(--accent)">{_ic("bell",20)}</span>
            <div><h2>Alerts &amp; Monitoring</h2><p class="panel-sub">Active KPI threshold violations.</p></div>
          </div>
          <span class="badge">{nb_alerts} active</span>
        </div>
        {alerts_html}
      </article>
    </section>
    <section class="grid" id="insights-section" style="margin-bottom:16px">
      <article class="panel reveal" style="grid-column:span 2">
        <div class="panel-header">
          <div class="panel-header-left">
            <span class="chart-type-icon" style="color:var(--accent)">{_ic("bulb",20)}</span>
            <div><h2>AI Insights</h2><p class="panel-sub">Narrative analysis from the Data Scientist agent.</p></div>
          </div>
          <span class="badge">Agent handoff</span>
        </div>
        <div class="insight-box"><ul>{insights_html}</ul></div>
        <div class="flow-grid">{flow_steps}</div>
        <p class="meta" style="margin-top:12px">Pipeline: {escape(pipeline)}</p>
      </article>
      <article class="panel reveal" style="grid-column:span 2">
        <div class="panel-header">
          <div class="panel-header-left">
            <span class="chart-type-icon" style="color:var(--accent)">{_ic("brain",20)}</span>
            <div><h2>Adaptive Mapping</h2><p class="panel-sub">How the BI Agent interpreted the JSON structure.</p></div>
          </div>
          <span class="badge">BI Agent</span>
        </div>
        <div class="meta">
          <strong>Original KPI keys:</strong> {escape(", ".join(map(str, original_keys)) or "&mdash;")}<br/>
          <strong>Chart series:</strong> {escape(", ".join(map(str, chart_keys)) or "&mdash;")}<br/>
          <strong>Charts generated:</strong> {nb_charts} &nbsp;&middot;&nbsp;
          <strong>Run:</strong> {escape(run_id)} &nbsp;&middot;&nbsp;
          <strong>Generated:</strong> {escape(created_at)}
        </div>
      </article>
    </section>
  </div>

  <!-- EXPORTS TAB -->
  <div id="tab-exports" class="tab-pane">
    <div class="section-heading reveal">
      <div class="eyebrow">Downloads</div>
      <h2>Export Center</h2>
    </div>
    <section id="asset-center">
      <article class="panel span-full reveal">
        <div class="panel-header">
          <div class="panel-header-left">
            <span class="chart-type-icon" style="color:var(--accent)">{_ic("package",20)}</span>
            <div><h2>Generated Artifacts</h2><p class="panel-sub">Dashboard files, chart HTMLs, and data payloads.</p></div>
          </div>
          <span class="badge">{nb_charts + 3} files</span>
        </div>
        <div class="asset-card-grid">{export_cards_html}</div>
      </article>
    </section>
  </div>

</main>
</div>

<div id="chart-fs-overlay" class="chart-fs-overlay" onclick="if(event.target===this)closeChartFs()">
  <div class="chart-fs-inner">
    <div id="chart-fs-title" class="chart-fs-title"></div>
    <button class="chart-fs-close" onclick="closeChartFs()">{_ic("x", 18)}</button>
    <div id="chart-fs-mount" class="chart-fs-mount"></div>
  </div>
</div>

<div id="toast" class="toast"></div>
<script>{js_icons}</script>
<script>{js}</script>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump({"run_id": run_id, "dashboard_path": output_path, "kpis": kpis,
                       "alertes": alertes, "insights": insights, "agent_context": agent_context,
                       "charts": nc}, f, indent=2, ensure_ascii=False)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"run_id": run_id, "dashboard_path": output_path,
                       "payload_path": payload_path, "manifest_path": manifest_path,
                       "charts": [{"title": c.get("title"), "slot": c.get("slot"),
                                   "source_key": c.get("source_key"), "chart_type": c.get("chart_type"),
                                   "html": c.get("chart_path"), "html_href": c.get("chart_href")} for c in nc]},
                      f, indent=2, ensure_ascii=False)

        return {"dashboard_path": output_path, "payload_path": payload_path,
                "manifest_path": manifest_path, "nb_charts": nb_charts, "published": True}

    except Exception as exc:
        return {"error": str(exc), "published": False}
