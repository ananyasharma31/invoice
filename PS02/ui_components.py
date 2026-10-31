"""
UI Components & Visual Styling Module
Provides modern SaaS design tokens, custom FinTech CSS, interactive Altair charts,
KPI metric cards, and pipeline progress steppers for Streamlit.
"""

import altair as alt
import pandas as pd
import streamlit as st
from typing import Optional, Dict, Any


def get_custom_css() -> str:
    """Returns ultra-modern FinTech SaaS CSS stylesheet for Streamlit."""
    return """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
        /* Base Typography */
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #1E293B;
        }

        /* Top Header & Hero Card */
        .hero-banner {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #312E81 100%);
            border-radius: 16px;
            padding: 26px 32px;
            color: #ffffff;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15), 0 8px 10px -6px rgba(15, 23, 42, 0.1);
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .hero-banner::after {
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, rgba(99, 102, 241, 0) 70%);
            border-radius: 50%;
            pointer-events: none;
        }
        .hero-title {
            font-size: 2.1rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin: 0;
            background: linear-gradient(135deg, #FFFFFF 0%, #E2E8F0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero-subtitle {
            font-size: 1.02rem;
            color: #94A3B8;
            margin-top: 8px;
            max-width: 820px;
            line-height: 1.5;
        }
        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(129, 140, 248, 0.4);
            color: #C7D2FE;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 12px;
        }
        .status-dot {
            width: 7px;
            height: 7px;
            background-color: #10B981;
            border-radius: 50%;
            box-shadow: 0 0 8px #10B981;
        }

        /* Modern Stepper Progress Component */
        .stepper-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 12px 20px;
            margin-bottom: 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .step-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.88rem;
            font-weight: 600;
            color: #64748B;
        }
        .step-item.active {
            color: #4F46E5;
        }
        .step-circle {
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            background: #F1F5F9;
            color: #64748B;
            font-weight: 700;
        }
        .step-item.active .step-circle {
            background: #4F46E5;
            color: #FFFFFF;
            box-shadow: 0 0 10px rgba(79, 70, 229, 0.35);
        }
        .step-divider {
            flex: 1;
            height: 2px;
            background: #E2E8F0;
            margin: 0 14px;
        }

        /* High-Impact Metric Cards */
        .kpi-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.04);
            position: relative;
            transition: all 0.25s ease;
            height: 100%;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px -2px rgba(0, 0, 0, 0.06);
            border-color: #CBD5E1;
        }
        .kpi-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .kpi-title {
            font-size: 0.84rem;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .kpi-icon-badge {
            width: 34px;
            height: 34px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }
        .kpi-value {
            font-size: 1.75rem;
            font-weight: 800;
            color: #0F172A;
            letter-spacing: -0.02em;
            line-height: 1.1;
        }
        .kpi-subtext {
            font-size: 0.8rem;
            color: #94A3B8;
            margin-top: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .kpi-trend-positive {
            color: #10B981;
            font-weight: 600;
        }

        /* Glass Accents */
        .accent-indigo { border-top: 4px solid #4F46E5; }
        .accent-emerald { border-top: 4px solid #10B981; }
        .accent-amber { border-top: 4px solid #F59E0B; }
        .accent-rose { border-top: 4px solid #EF4444; }
        .accent-sky { border-top: 4px solid #0EA5E9; }

        /* Status Badges */
        .pill-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 700;
            text-align: center;
        }
        .pill-high { background: #DCFCE7; color: #166534; border: 1px solid #BBF7D0; }
        .pill-medium { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
        .pill-review { background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; }
        .pill-paid { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
        .pill-partially-paid { background: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
        .pill-unpaid { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }

        /* Streamlit Tabs Customization */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
            padding: 4px 0 12px 0;
            border-bottom: 2px solid #E2E8F0;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 8px 18px;
            font-weight: 600;
            font-size: 0.92rem;
            color: #64748B;
            border: 1px solid transparent;
            background-color: #F8FAFC;
            transition: all 0.2s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: #1E293B;
            background-color: #EEF2F6;
        }
        .stTabs [aria-selected="true"] {
            background-color: #4F46E5 !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);
        }

        /* Buttons Enhancement */
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            letter-spacing: 0.01em;
            transition: all 0.2s ease;
        }
        .stButton>button[kind="primary"] {
            background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%);
            border: none;
            box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3);
        }
        .stButton>button[kind="primary"]:hover {
            box-shadow: 0 6px 14px rgba(79, 70, 229, 0.4);
            transform: translateY(-1px);
        }

        /* Chart container */
        .chart-box {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.03);
            margin-bottom: 20px;
        }
        .chart-title {
            font-size: 0.96rem;
            font-weight: 700;
            color: #0F172A;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
    </style>
    """


def render_hero_banner(title: str, subtitle: str, badge_text: str = "FinTech SaaS Engine v2.4") -> None:
    """Renders a sleek, modern FinTech SaaS hero header."""
    html_code = f"""
    <div class="hero-banner">
        <div class="hero-badge">
            <span class="status-dot"></span>
            <span>{badge_text}</span>
        </div>
        <h1 class="hero-title">{title}</h1>
        <p class="hero-subtitle">{subtitle}</p>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


def render_pipeline_stepper(current_step: int = 1) -> None:
    """Renders a 4-step horizontal visual progress stepper."""
    steps = [
        ("1", "Data Ingestion", "Upload & Clean"),
        ("2", "AI Matching", "RapidFuzz Engine"),
        ("3", "Reconciliation", "Decisions & Ledger"),
        ("4", "Executive Insights", "Reports & KPIs")
    ]

    items_html = []
    for idx, (num, name, desc) in enumerate(steps, start=1):
        is_active = "active" if idx == current_step else ""
        checkmark = "✓" if idx < current_step else num
        items_html.append(f"""
        <div class="step-item {is_active}">
            <div class="step-circle">{checkmark}</div>
            <div>
                <div>{name}</div>
                <div style="font-size: 0.72rem; font-weight: 400; color: #94A3B8;">{desc}</div>
            </div>
        </div>
        """)
        if idx < len(steps):
            items_html.append('<div class="step-divider"></div>')

    stepper_html = f'<div class="stepper-container">{"".join(items_html)}</div>'
    st.markdown(stepper_html, unsafe_allow_html=True)


def render_kpi_card_html(
    title: str,
    value: str,
    subtext: str,
    icon: str,
    accent: str = "indigo",
    icon_bg: str = "#EEF2FF"
) -> str:
    """Returns HTML for an elevated KPI metric card."""
    return f"""
    <div class="kpi-card accent-{accent}">
        <div class="kpi-header">
            <span class="kpi-title">{title}</span>
            <div class="kpi-icon-badge" style="background-color: {icon_bg};">
                {icon}
            </div>
        </div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-subtext">{subtext}</div>
    </div>
    """


def get_settlement_donut_chart(balances_df: pd.DataFrame) -> Optional[alt.Chart]:
    """Generates an interactive Altair donut chart for invoice settlement distribution."""
    if balances_df is None or balances_df.empty or "status" not in balances_df.columns:
        return None

    status_counts = balances_df["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    color_scale = alt.Scale(
        domain=["PAID", "PARTIALLY PAID", "UNPAID", "OVERPAID"],
        range=["#10B981", "#F59E0B", "#EF4444", "#3B82F6"]
    )

    chart = alt.Chart(status_counts).mark_arc(innerRadius=60, stroke="#ffffff", strokeWidth=2).encode(
        theta=alt.Theta(field="Count", type="quantitative"),
        color=alt.Color(field="Status", type="nominal", scale=color_scale, legend=alt.Legend(orient="bottom")),
        tooltip=["Status", "Count"]
    ).properties(height=260)

    return chart


def get_confidence_breakdown_chart(matches_df: pd.DataFrame) -> Optional[alt.Chart]:
    """Generates an Altair donut chart for confidence level distribution."""
    if matches_df is None or matches_df.empty or "confidence" not in matches_df.columns:
        return None

    conf_counts = matches_df["confidence"].value_counts().reset_index()
    conf_counts.columns = ["Confidence", "Matches"]

    color_scale = alt.Scale(
        domain=["High", "Medium", "Review required"],
        range=["#10B981", "#3B82F6", "#EF4444"]
    )

    chart = alt.Chart(conf_counts).mark_arc(innerRadius=60, stroke="#ffffff", strokeWidth=2).encode(
        theta=alt.Theta(field="Matches", type="quantitative"),
        color=alt.Color(field="Confidence", type="nominal", scale=color_scale, legend=alt.Legend(orient="bottom")),
        tooltip=["Confidence", "Matches"]
    ).properties(height=260)

    return chart


def get_financial_breakdown_bar_chart(invoiced: float, paid: float, outstanding: float) -> alt.Chart:
    """Generates an Altair bar chart comparing Invoiced, Paid, and Outstanding amounts."""
    data = pd.DataFrame([
        {"Category": "Total Invoiced", "Amount": invoiced, "Color": "#6366F1"},
        {"Category": "Confirmed Paid", "Amount": paid, "Color": "#10B981"},
        {"Category": "Outstanding", "Amount": max(0.0, outstanding), "Color": "#EF4444"}
    ])

    chart = alt.Chart(data).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
        x=alt.X("Category:N", sort=None, axis=alt.Axis(labelAngle=0, title=None)),
        y=alt.Y("Amount:Q", axis=alt.Axis(title="Amount ($)", format="$,.0f")),
        color=alt.Color("Category:N", scale=alt.Scale(domain=["Total Invoiced", "Confirmed Paid", "Outstanding"], range=["#6366F1", "#10B981", "#EF4444"]), legend=None),
        tooltip=[alt.Tooltip("Category:N"), alt.Tooltip("Amount:Q", format="$,.2f")]
    ).properties(height=260)

    return chart
