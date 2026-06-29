"""
theme.py — On The Apex visual identity.

Single source of truth for:
  - Brand colours
  - Google Fonts injection (Saira / Saira Condensed / Spline Sans Mono)
  - Streamlit CSS overrides
  - Plotly figure defaults (apply_ota_layout)
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# ── Brand palette ─────────────────────────────────────────────────────────────

RED       = "#E00000"
RED_BRIGHT = "#FF1A1A"
DARK      = "#0A0A0A"
SURFACE   = "#161616"
SURFACE2  = "#1E1E1E"
BORDER    = "#2A2A2A"
TEXT      = "#FFFFFF"
TEXT_DIM  = "#888888"
TEXT_MUTED = "#444444"

# Plotly
GRID_COLOR  = "#1E1E1E"
AXIS_COLOR  = "#555555"
HOVER_BG    = "#161616"


# ── Logo helpers ──────────────────────────────────────────────────────────────

def _svg_to_data_uri(path: str) -> str:
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:image/svg+xml;base64,{b64}"


def logo_data_uri(variant: str = "white") -> str:
    """Return a data URI for the logo SVG. variant: 'white' or 'black'."""
    fname = f"colour-{variant}.svg"
    candidates = [
        Path(__file__).parent / fname,
        Path(fname),
    ]
    for p in candidates:
        if p.exists():
            return _svg_to_data_uri(str(p))
    return ""


# ── CSS ───────────────────────────────────────────────────────────────────────

_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Saira:ital,wght@0,100..900;1,100..900&"
    "family=Saira+Condensed:wght@300;400;500;600;700;900&"
    "family=Spline+Sans+Mono:ital,wght@0,300..700;1,300..700&"
    "display=swap"
)

_CSS = """
/* ── Reset & base ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: 'Saira', sans-serif !important;
}}

/* ── Numbers & timing — monospace everywhere ──────────────────────────── */
.stMetric label, .stMetric [data-testid="stMetricValue"] {{
    font-family: 'Spline Sans Mono', monospace !important;
}}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: {SURFACE} !important;
    border-right: 1px solid {BORDER} !important;
}}

[data-testid="stSidebar"] > div:first-child {{
    padding-top: 0 !important;
}}

/* Sidebar logo container */
.ota-logo-wrap {{
    background: {DARK};
    padding: 18px 20px 14px 20px;
    margin: 0 0 4px 0;
    border-bottom: 2px solid {RED};
    position: relative;
    overflow: hidden;
}}

/* Speed-stripe accent behind logo (diagonal parallelogram) */
.ota-logo-wrap::after {{
    content: '';
    position: absolute;
    right: -10px;
    top: 0;
    bottom: 0;
    width: 48px;
    background: {RED};
    transform: skewX(-14deg);
    opacity: 0.15;
}}

.ota-logo-wrap img {{
    width: 100%;
    height: auto;
    display: block;
    position: relative;
    z-index: 1;
}}

/* Sidebar labels */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-size: 0.72rem !important;
    color: {TEXT_DIM} !important;
}}

/* Sidebar divider */
[data-testid="stSidebar"] hr {{
    border-color: {BORDER} !important;
    margin: 8px 0 !important;
}}

/* ── Section headings (h2, h3) ────────────────────────────────────────── */
h1 {{
    font-family: 'Saira', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
    font-size: 2rem !important;
}}

h2 {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    font-size: 1.1rem !important;
    color: {TEXT_DIM} !important;
    padding-bottom: 6px !important;
    border-bottom: 1px solid {BORDER} !important;
    margin-bottom: 12px !important;
}}

h3 {{
    font-family: 'Saira', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
}}

/* ── Metric cards ─────────────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {SURFACE} !important;
    border-top: 2px solid {RED} !important;
    border-radius: 0 !important;
    padding: 14px 18px 12px 18px !important;
}}

[data-testid="stMetric"] label {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    font-size: 0.68rem !important;
    color: {TEXT_DIM} !important;
}}

[data-testid="stMetricValue"] {{
    font-family: 'Spline Sans Mono', monospace !important;
    font-weight: 600 !important;
    font-size: 2rem !important;
    color: {TEXT} !important;
    letter-spacing: -0.02em !important;
}}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {{
    border-bottom: 1px solid {BORDER} !important;
    gap: 0 !important;
}}

[data-testid="stTabs"] [role="tab"] {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-size: 0.78rem !important;
    color: {TEXT_DIM} !important;
    padding: 8px 20px !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    transition: color 0.15s, border-color 0.15s !important;
}}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: {TEXT} !important;
    border-bottom-color: {RED} !important;
    background: transparent !important;
}}

[data-testid="stTabs"] [role="tab"]:hover {{
    color: {TEXT} !important;
    border-bottom-color: {RED_BRIGHT} !important;
    background: transparent !important;
}}

/* ── Dataframes / tables ──────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    font-family: 'Spline Sans Mono', monospace !important;
    font-size: 0.8rem !important;
}}

[data-testid="stDataFrame"] thead th {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-size: 0.7rem !important;
    color: {TEXT_DIM} !important;
    background: {SURFACE2} !important;
    border-bottom: 1px solid {BORDER} !important;
}}

/* ── Selectboxes & multiselects ───────────────────────────────────────── */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stSlider"] label,
[data-testid="stRadio"] label {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-size: 0.72rem !important;
    color: {TEXT_DIM} !important;
}}

/* ── Buttons ──────────────────────────────────────────────────────────── */
[data-testid="baseButton-secondary"] {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    border: 1px solid {BORDER} !important;
}}

[data-testid="baseButton-primary"] {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    background: {RED} !important;
    border: none !important;
}}

/* ── Captions & small text ────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] {{
    font-family: 'Saira Condensed', sans-serif !important;
    color: {TEXT_DIM} !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.02em !important;
}}

/* ── Toggle / checkbox ────────────────────────────────────────────────── */
[data-testid="stToggle"] label {{
    font-family: 'Saira Condensed', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
}}

/* ── Info / warning / error boxes ────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 0 !important;
    border-left-width: 3px !important;
    font-family: 'Saira', sans-serif !important;
}}

/* ── Main content padding ─────────────────────────────────────────────── */
.main .block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
}}
""".format(
    RED=RED, RED_BRIGHT=RED_BRIGHT,
    DARK=DARK, SURFACE=SURFACE, SURFACE2=SURFACE2,
    BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
)


def inject_theme():
    """Call once at app startup to inject fonts and CSS."""
    # Google Fonts
    st.markdown(
        f'<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="{_FONTS_URL}" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    # CSS overrides
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def inject_sidebar_logo():
    """Render the white OTA logo in the sidebar header."""
    uri = logo_data_uri("white")
    if uri:
        st.markdown(
            f'<div class="ota-logo-wrap"><img src="{uri}" alt="On The Apex"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p style="font-family:\'Saira\',sans-serif;font-weight:800;'
            f'font-size:1.1rem;color:{TEXT};margin:0;">ON THE APEX</p>',
            unsafe_allow_html=True,
        )


# ── Plotly theme ──────────────────────────────────────────────────────────────

OTA_PLOTLY_LAYOUT = dict(
    paper_bgcolor=DARK,
    plot_bgcolor="#111111",
    font=dict(
        family="'Spline Sans Mono', monospace",
        color=TEXT,
        size=12,
    ),
    title=dict(
        font=dict(
            family="'Saira', sans-serif",
            size=16,
            color=TEXT,
        ),
        x=0,
        xanchor="left",
        pad=dict(l=4),
    ),
    xaxis=dict(
        color=AXIS_COLOR,
        gridcolor=GRID_COLOR,
        linecolor=BORDER,
        tickfont=dict(family="'Spline Sans Mono', monospace", size=11, color=TEXT_DIM),
        title_font=dict(family="'Saira Condensed', sans-serif", size=11,
                        color=TEXT_DIM),
        zeroline=False,
    ),
    yaxis=dict(
        color=AXIS_COLOR,
        gridcolor=GRID_COLOR,
        linecolor=BORDER,
        tickfont=dict(family="'Spline Sans Mono', monospace", size=11, color=TEXT_DIM),
        title_font=dict(family="'Saira Condensed', sans-serif", size=11,
                        color=TEXT_DIM),
        zeroline=False,
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor=BORDER,
        borderwidth=1,
        font=dict(family="'Saira Condensed', sans-serif", size=11, color=TEXT_DIM),
    ),
    hoverlabel=dict(
        bgcolor=SURFACE,
        bordercolor=RED,
        font=dict(family="'Spline Sans Mono', monospace", size=11, color=TEXT),
    ),
    colorway=[
        RED, "#FFFFFF", "#888888", "#FF6B00", "#00C4FF",
        "#B4E600", "#9B59B6", "#F39C12", "#1ABC9C", "#E74C3C",
    ],
    margin=dict(l=48, r=24, t=48, b=48),
)


def apply_ota_layout(fig, **overrides):
    """Apply the On The Apex Plotly theme to a figure, with optional overrides."""
    layout = {**OTA_PLOTLY_LAYOUT, **overrides}

    # Handle nested axis overrides properly
    for axis in ("xaxis", "yaxis", "xaxis2", "yaxis2"):
        if axis in overrides:
            base = dict(OTA_PLOTLY_LAYOUT.get(axis, {}))
            base.update(overrides[axis])
            layout[axis] = base

    fig.update_layout(**layout)
    return fig
