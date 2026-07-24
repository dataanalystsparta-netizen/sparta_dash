import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ==============================================================================
# PAGE CONFIG & STYLES
# ==============================================================================
st.set_page_config(
    page_title="Executive Lead Conversion Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for sticky headers, executive styling, and badges
st.markdown("""
<style>
    /* Sticky Table Headers */
    .stTable table thead tr th, 
    .custom-table th,
    .monthly-kpi-table th,
    .custom-perf-table th {
        position: sticky;
        top: 0;
        z-index: 10;
        background-color: #1e293b !important;
        color: #ffffff !important;
        box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.4);
    }
    
    /* Table Container Scroll Constraint for Sticky Headers */
    .table-container {
        max-height: 550px;
        overflow-y: auto;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }

    /* Executive Metric Card Styling */
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Status Pills */
    .pill-green {
        background-color: #dcfce7;
        color: #15803d;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .pill-yellow {
        background-color: #fef9c3;
        color: #a16207;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .pill-red {
        background-color: #fee2e2;
        color: #b91c1c;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* Advisor Tag Badges */
    .badge-new {
        background-color: #3b82f6;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 6px;
    }
    .badge-cs {
        background-color: #8b5cf6;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 6px;
    }
    .badge-left {
        background-color: #64748b;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CONFIG & TAG DEFINITIONS
# ==============================================================================
NEW_ADVISORS = []
CUSTOMER_SERVICE_ADVISORS = []
LEFT_ADVISORS = []

def count_status(df, column, target_status):
    if column not in df.columns:
        return 0
    return (df[column].astype(str).str.strip().str.lower() == str(target_status).lower()).sum()

# ==============================================================================
# DATA LOADING & PREPARATION
# ==============================================================================
@st.cache_data(ttl=300)
def load_data():
    # Load primary datasets (Adjust file paths/sheet names if using database/API)
    try:
        app_df = pd.read_csv("applications.csv")
    except Exception:
        app_df = pd.DataFrame()

    try:
        portal_df = pd.read_csv("portal.csv")
    except Exception:
        portal_df = pd.DataFrame()

    return app_df, portal_df

master_raw_df, sparta2_df = load_data()

# Clean and establish datetime period sorting columns
for df in [master_raw_df, sparta2_df]:
    if not df.empty and "Sale Date" in df.columns:
        df["Sale Date Clean"] = pd.to_datetime(df["Sale Date"], errors="coerce")
        df["Period_Sort"] = df["Sale Date Clean"].dt.to_period("M").dt.to_timestamp()
    elif not df.empty:
        df["Period_Sort"] = pd.NaT

master_df = master_raw_df.copy()

# ==============================================================================
# HEADER & TOP DATE FILTERS
# ==============================================================================
st.title("📊 Lead Conversion & Performance Ledger")
st.caption("Pipeline Velocity & Executive Advisor Metrics")

# Primary Date Range Filter (Top of Page)
col_d1, col_d2, col_spacer = st.columns([2, 2, 4])

with col_d1:
    start_date = st.date_input(
        "📅 Start Date",
        value=datetime(2026, 1, 1),
        key="top_start_date"
    )

with col_d2:
    end_date = st.date_input(
        "📅 End Date",
        value=datetime.today(),
        key="top_end_date"
    )

st.markdown("---")

# Filter main master_df for Advisor Matrix using top filters
if not master_df.empty and "Sale Date Clean" in master_df.columns:
    master_df = master_df[
        (master_df["Sale Date Clean"].dt.date >= start_date) &
        (master_df["Sale Date Clean"].dt.date <= end_date)
    ]

# ==============================================================================
# SECTION 1: MONTHLY KPI BREAKDOWN (2026)
# ==============================================================================
st.subheader("📅 Monthly KPI Breakdown (2026)")

# ==============================================================================
# SECTION 1: MONTHLY KPI BREAKDOWN (2026)
# ==============================================================================
st.subheader("📅 Monthly KPI Breakdown (2026)")

# (Data loading and aggregation logic for Monthly KPIs continues in Part 2)


# ==========================================================
# MONTHLY KPI BREAKDOWN TABLE (2026 ONLY, INDEPENDENT OF TOP FILTERS)
# ==========================================================

# Second Copy of Start and End Date Filters (Above Monthly KPI Table)
col_m_d1, col_m_d2, _ = st.columns([2, 2, 4])
with col_m_d1:
    m_start_date = st.date_input(
        "📅 Start Date (KPI Focus)",
        value=datetime(2026, 1, 1),
        key="kpi_start_date"
    )
with col_m_d2:
    m_end_date = st.date_input(
        "📅 End Date (KPI Focus)",
        value=datetime.today(),
        key="kpi_end_date"
    )

# Filter for year 2026 exclusively
monthly_app_df = master_raw_df.dropna(subset=["Period_Sort"]).copy()
monthly_app_df = monthly_app_df[
    (monthly_app_df["Period_Sort"].dt.year == 2026) &
    (monthly_app_df["Period_Sort"].dt.date >= m_start_date) &
    (monthly_app_df["Period_Sort"].dt.date <= m_end_date)
]

monthly_portal_df = sparta2_df.dropna(subset=["Period_Sort"]).copy()
monthly_portal_df = monthly_portal_df[
    (monthly_portal_df["Period_Sort"].dt.year == 2026) &
    (monthly_portal_df["Period_Sort"].dt.date >= m_start_date) &
    (monthly_portal_df["Period_Sort"].dt.date <= m_end_date)
]

all_periods = sorted(list(set(monthly_app_df["Period_Sort"]).union(set(monthly_portal_df["Period_Sort"]))), reverse=True)

if all_periods:
    monthly_rows = []
    for period in all_periods:
        m_str = period.strftime("%B %Y")
        
        m_app = monthly_app_df[monthly_app_df["Period_Sort"] == period]
        m_portal = monthly_portal_df[monthly_portal_df["Period_Sort"] == period]
        
        m_total_apps = len(m_app)
        
        m_qa_approved = count_status(m_app, "Quality Status Clean", "Approved")
        m_qa_rework = count_status(m_app, "Quality Status Clean", "Rework")
        m_qa_cancelled = count_status(m_app, "Quality Status Clean", "Cancelled")
        m_qa_pending = count_status(m_app, "Quality Status Clean", "Pending")
        
        m_wc_done = count_status(m_app, "Welcome Status Clean", "Done")
        m_wc_cancelled = count_status(m_app, "Welcome Status Clean", "Cancelled")
        m_wc_pending = count_status(m_app, "Welcome Status Clean", "Pending")
        
        m_p_live = count_status(m_portal, "Portal Status Clean", "Live")
        m_p_committed = count_status(m_portal, "Portal Status Clean", "Committed")
        m_p_cancelled = count_status(m_portal, "Portal Status Clean", "Cancelled")
        
        monthly_rows.append({
            "MONTH": m_str,
            "APPLICATIONS": m_total_apps,
            "QA APPROVED": m_qa_approved,
            "QA Pass Rate % Val": (m_qa_approved / m_total_apps * 100) if m_total_apps > 0 else 0.0,
            "QA REWORK": m_qa_rework,
            "QA CANCELLED": m_qa_cancelled,
            "QA PENDING": m_qa_pending,
            "WELCOME DONE": m_wc_done,
            "Welcome Done % Val": (m_wc_done / m_total_apps * 100) if m_total_apps > 0 else 0.0,
            "WELCOME CANCELLED": m_wc_cancelled,
            "WELCOME PENDING": m_wc_pending,
            "COMMITTED REM.": m_p_committed,
            "LIVE": m_p_live,
            "Live Conversion % Val": (m_p_live / m_total_apps * 100) if m_total_apps > 0 else 0.0,
            "LIVE CANCELLED": m_p_cancelled
        })
    
    monthly_summary_df = pd.DataFrame(monthly_rows)
    
    # Calculate totals for summary row
    tot_apps = monthly_summary_df["APPLICATIONS"].sum()
    tot_qa_app = monthly_summary_df["QA APPROVED"].sum()
    tot_wc_done = monthly_summary_df["WELCOME DONE"].sum()
    tot_live = monthly_summary_df["LIVE"].sum()
    
    totals_row = {
        "MONTH": "Total",
        "APPLICATIONS": tot_apps,
        "QA APPROVED": tot_qa_app,
        "QA Pass Rate % Val": (tot_qa_app / tot_apps * 100) if tot_apps > 0 else 0.0,
        "QA REWORK": monthly_summary_df["QA REWORK"].sum(),
        "QA CANCELLED": monthly_summary_df["QA CANCELLED"].sum(),
        "QA PENDING": monthly_summary_df["QA PENDING"].sum(),
        "WELCOME DONE": tot_wc_done,
        "Welcome Done % Val": (tot_wc_done / tot_apps * 100) if tot_apps > 0 else 0.0,
        "WELCOME CANCELLED": monthly_summary_df["WELCOME CANCELLED"].sum(),
        "WELCOME PENDING": monthly_summary_df["WELCOME PENDING"].sum(),
        "COMMITTED REM.": monthly_summary_df["COMMITTED REM."].sum(),
        "LIVE": tot_live,
        "Live Conversion % Val": (tot_live / tot_apps * 100) if tot_apps > 0 else 0.0,
        "LIVE CANCELLED": monthly_summary_df["LIVE CANCELLED"].sum(),
    }
    monthly_summary_df = pd.concat([monthly_summary_df, pd.DataFrame([totals_row])], ignore_index=True)
    
    # Helpers for percentage pills
    def render_monthly_qa_pill(val_float):
        val_str = f"{val_float:.1f}%"
        if val_float >= 75.0:
            bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
        elif val_float >= 51.0:
            bg, color, border = "#fef3c7", "#b45309", "#fde68a"
        else:
            bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
        return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 2px 8px; font-weight: 700; font-size: 0.78rem; display: inline-block;">{val_str}</span>'

    def render_monthly_welcome_pill(val_float):
        val_str = f"{val_float:.1f}%"
        if val_float >= 61.0:
            bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
        elif val_float >= 51.0:
            bg, color, border = "#fef3c7", "#b45309", "#fde68a"
        else:
            bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
        return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 2px 8px; font-weight: 700; font-size: 0.78rem; display: inline-block;">{val_str}</span>'

    def render_monthly_live_pill(val_float):
        val_str = f"{val_float:.1f}%"
        if val_float >= 41.0:
            bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
        elif val_float >= 21.0:
            bg, color, border = "#fef3c7", "#b45309", "#fde68a"
        else:
            bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
        return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 2px 8px; font-weight: 700; font-size: 0.78rem; display: inline-block;">{val_str}</span>'

    # Color-coded headers
    m_header_styles = {
        "MONTH": "background-color: #f1f5f9; color: #334155;",
        "APPLICATIONS": "background-color: #eff6ff; color: #1e40af;",
        "QA APPROVED": "background-color: #f0fdf4; color: #15803d;",
        "QA Pass Rate %": "background-color: #f0fdf4; color: #15803d;",
        "QA REWORK": "background-color: #fefce8; color: #a16207;",
        "QA CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
        "QA PENDING": "background-color: #fff7ed; color: #c2410c;",
        "WELCOME DONE": "background-color: #f0fdf4; color: #15803d;",
        "Welcome Done %": "background-color: #f0fdf4; color: #15803d;",
        "WELCOME CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
        "WELCOME PENDING": "background-color: #fefce8; color: #a16207;",
        "COMMITTED REM.": "background-color: #fff7ed; color: #c2410c;",
        "LIVE": "background-color: #f0fdfa; color: #0f766e;",
        "Live Conversion %": "background-color: #f0fdfa; color: #0f766e;",
        "LIVE CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
    }

    display_columns = [
        "MONTH", "APPLICATIONS", "QA APPROVED", "QA Pass Rate %",
        "QA REWORK", "QA CANCELLED", "QA PENDING", "WELCOME DONE",
        "Welcome Done %", "WELCOME CANCELLED", "WELCOME PENDING",
        "COMMITTED REM.", "LIVE", "Live Conversion %", "LIVE CANCELLED"
    ]

    m_html = """
    <style>
        .monthly-kpi-table-container {
            width: 100%;
            max-height: 500px;
            overflow-y: auto;
            overflow-x: auto;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
            margin-bottom: 20px;
        }
        .monthly-kpi-table {
            width: 100%;
            border-collapse: collapse;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 0.88rem;
            background-color: #ffffff;
        }
        .monthly-kpi-table th {
            padding: 12px 14px;
            font-weight: 800;
            font-size: 0.78rem;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            text-align: center;
            border-bottom: 2px solid #e2e8f0;
            border-right: 1px solid #f1f5f9;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .monthly-kpi-table th:first-child {
            text-align: left;
        }
        .monthly-kpi-table td {
            padding: 10px 14px;
            text-align: center;
            border-bottom: 1px solid #f1f5f9;
            border-right: 1px solid #f8fafc;
            color: #1e293b;
        }
        .monthly-kpi-table td:first-child {
            text-align: left;
            font-weight: 700;
            color: #0f172a;
        }
        .monthly-kpi-table tr:last-child {
            font-weight: 800;
            background-color: #f8fafc;
            border-top: 2px solid #cbd5e1;
            position: sticky;
            bottom: 0;
            z-index: 5;
        }
        .monthly-kpi-table tr:hover:not(:last-child) {
            background-color: #f8fafc;
        }
    </style>
    <div class="monthly-kpi-table-container">
        <table class="monthly-kpi-table">
            <thead>
                <tr>
    """
    for col_name in display_columns:
        th_style = m_header_styles.get(col_name, "background-color: #f8fafc; color: #475569;")
        m_html += f'<th style="{th_style}">{col_name}</th>'
    m_html += "</tr></thead><tbody>"
    
    for _, row in monthly_summary_df.iterrows():
        m_html += "<tr>"
        for col_name in display_columns:
            if col_name == "MONTH":
                m_html += f"<td>{row['MONTH']}</td>"
            elif col_name == "QA Pass Rate %":
                pill = render_monthly_qa_pill(row["QA Pass Rate % Val"])
                m_html += f"<td>{pill}</td>"
            elif col_name == "Welcome Done %":
                pill = render_monthly_welcome_pill(row["Welcome Done % Val"])
                m_html += f"<td>{pill}</td>"
            elif col_name == "Live Conversion %":
                pill = render_monthly_live_pill(row["Live Conversion % Val"])
                m_html += f"<td>{pill}</td>"
            else:
                val = row[col_name]
                formatted_val = "-" if val == 0 else f"{val:,}"
                m_html += f"<td>{formatted_val}</td>"
        m_html += "</tr>"
        
    m_html += "</tbody></table></div>"
    st.markdown(m_html, unsafe_allow_html=True)
else:
    st.info("No 2026 monthly data available for the selected date range.")

# ==========================================================
# TAG VISIBILITY FILTERS (MOVED BELOW MONTHLY KPI TABLE)
# ==========================================================

st.divider()
st.subheader("🏷️ Advisor Tag Visibility Filters")

col_tf1, col_tf2, col_tf3, col_tf4 = st.columns(4)

with col_tf1:
    include_new = st.checkbox("Include New Advisors", value=True)
with col_tf2:
    include_cs = st.checkbox("Include Customer Service", value=True)
with col_tf3:
    include_left = st.checkbox("Include Left Advisors", value=False)
with col_tf4:
    include_untagged = st.checkbox("Include Standard/Untagged", value=True)

st.markdown("---")

# ==========================================================
# ADVISOR PERFORMANCE MATRIX (WITH STICKY HEADERS)
# ==========================================================

st.subheader("👥 Sales Executive Performance Breakdown")

if "Advisor" in master_df.columns and not master_df.empty:

    # 1. Aggregate metrics
    advisor_summary = (
        master_df.groupby("Advisor", dropna=False)
        .agg(
            Applications=("Advisor", "count"),
            QA_Approved=("Quality Status Clean", lambda x: (x == "Approved").sum()),
            QA_Rework=("Quality Status Clean", lambda x: (x == "Rework").sum()),
            QA_Cancelled=("Quality Status Clean", lambda x: (x == "Cancelled").sum()),
            QA_Pending=("Quality Status Clean", lambda x: (x == "Pending").sum()),
            Welcome_Done=("Welcome Status Clean", lambda x: (x == "Done").sum()),
            Welcome_Cancelled=("Welcome Status Clean", lambda x: (x == "Cancelled").sum()),
            Welcome_Pending=("Welcome Status Clean", lambda x: (x == "Pending").sum()),
            Committed=("Portal Status Clean", lambda x: (x == "Committed").sum()),
            Live=("Portal Status Clean", lambda x: (x == "Live").sum()),
            Live_Cancelled=("Portal Status Clean", lambda x: (x == "Cancelled").sum()),
        )
        .reset_index()
    )

    # 2. Filter rows based on tag inclusion checkboxes
    def filter_tagged_rows(row):
        name = str(row["Advisor"]).strip().lower()
        
        is_new = name in [a.strip().lower() for a in NEW_ADVISORS]
        is_cs = name in [a.strip().lower() for a in CUSTOMER_SERVICE_ADVISORS]
        is_left = name in [a.strip().lower() for a in LEFT_ADVISORS]
        is_tagged = is_new or is_cs or is_left
        
        if is_new and not include_new:
            return False
        if is_cs and not include_cs:
            return False
        if is_left and not include_left:
            return False
        if not is_tagged and not include_untagged:
            return False
        return True

    advisor_summary = advisor_summary[advisor_summary.apply(filter_tagged_rows, axis=1)].copy()

    if advisor_summary.empty:
        st.info("No sales records match the selected tag filters.")
    else:
        # 3. Calculate percentage floats BEFORE column rename
        advisor_summary["QA Pass Rate % Val"] = (
            (advisor_summary["QA_Approved"] / advisor_summary["Applications"].replace(0, np.nan)) * 100
        ).fillna(0.0)

        advisor_summary["Welcome Done % Val"] = (
            (advisor_summary["Welcome_Done"] / advisor_summary["Applications"].replace(0, np.nan)) * 100
        ).fillna(0.0)

        advisor_summary["Live Conversion % Val"] = (
            (advisor_summary["Live"] / advisor_summary["Applications"].replace(0, np.nan)) * 100
        ).fillna(0.0)

        # 4. Rename columns
        advisor_summary = advisor_summary.rename(
            columns={
                "Advisor": "SALES EXECUTIVE",
                "Applications": "APPLICATIONS",
                "QA_Approved": "QA APPROVED",
                "QA_Rework": "QA REWORK",
                "QA_Cancelled": "QA CANCELLED",
                "QA_Pending": "QA PENDING",
                "Welcome_Done": "WELCOME DONE",
                "Welcome_Cancelled": "WELCOME CANCELLED",
                "Welcome_Pending": "WELCOME PENDING",
                "Committed": "COMMITTED REM.",
                "Live": "LIVE",
                "Live_Cancelled": "LIVE CANCELLED",
            }
        )

        advisor_summary["SALES EXECUTIVE"] = (
            advisor_summary["SALES EXECUTIVE"]
            .replace("", "Unassigned")
            .fillna("Unassigned")
        )
        advisor_summary = advisor_summary.sort_values(by="APPLICATIONS", ascending=False)

        # Determine visible columns (Hide zero-sum columns)
        numeric_cols = [
            "APPLICATIONS", "QA APPROVED", "QA REWORK", "QA CANCELLED", "QA PENDING",
            "WELCOME DONE", "WELCOME CANCELLED", "WELCOME PENDING", "COMMITTED REM.", "LIVE", "LIVE CANCELLED"
        ]

        base_col_order = [
            "SALES EXECUTIVE", "APPLICATIONS", "QA APPROVED", "QA Pass Rate %",
            "QA REWORK", "QA CANCELLED", "QA PENDING", "WELCOME DONE", "Welcome Done %",
            "WELCOME CANCELLED", "WELCOME PENDING", "COMMITTED REM.",
            "LIVE", "LIVE CANCELLED", "Live Conversion %"
        ]

        visible_cols = ["SALES EXECUTIVE"]
        for col in base_col_order[1:]:
            if col in numeric_cols:
                if (advisor_summary[col] > 0).any():
                    visible_cols.append(col)
            elif col == "QA Pass Rate %":
                if "QA APPROVED" in visible_cols:
                    visible_cols.append(col)
            elif col == "Welcome Done %":
                if "WELCOME DONE" in visible_cols:
                    visible_cols.append(col)
            elif col == "Live Conversion %":
                if "LIVE" in visible_cols:
                    visible_cols.append(col)

        # 5. Helpers to style percentage badges
        def render_qa_pill(val_float):
            val_str = f"{val_float:.1f}%"
            if val_float >= 75.0:
                bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
            elif val_float >= 51.0:
                bg, color, border = "#fef3c7", "#b45309", "#fde68a"
            else:
                bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
            return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 3px 12px; font-weight: 700; font-size: 0.82rem; display: inline-block;">{val_str}</span>'

        def render_welcome_pill(val_float):
            val_str = f"{val_float:.1f}%"
            if val_float >= 61.0:
                bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
            elif val_float >= 51.0:
                bg, color, border = "#fef3c7", "#b45309", "#fde68a"
            else:
                bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
            return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 3px 12px; font-weight: 700; font-size: 0.82rem; display: inline-block;">{val_str}</span>'

        def render_live_pill(val_float):
            val_str = f"{val_float:.1f}%"
            if val_float >= 41.0:
                bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
            elif val_float >= 21.0:
                bg, color, border = "#fef3c7", "#b45309", "#fde68a"
            else:
                bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
            return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 3px 12px; font-weight: 700; font-size: 0.82rem; display: inline-block;">{val_str}</span>'

        # Header styling configuration
        header_styles = {
            "SALES EXECUTIVE": "background-color: #f1f5f9; color: #334155;",
            "APPLICATIONS": "background-color: #eff6ff; color: #1e40af;",
            "QA APPROVED": "background-color: #f0fdf4; color: #15803d;",
            "QA Pass Rate %": "background-color: #f0fdf4; color: #15803d;",
            "QA REWORK": "background-color: #fefce8; color: #a16207;",
            "QA CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
            "QA PENDING": "background-color: #fff7ed; color: #c2410c;",
            "WELCOME DONE": "background-color: #f0fdf4; color: #15803d;",
            "Welcome Done %": "background-color: #f0fdf4; color: #15803d;",
            "WELCOME CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
            "WELCOME PENDING": "background-color: #fefce8; color: #a16207;",
            "COMMITTED REM.": "background-color: #fff7ed; color: #c2410c;",
            "LIVE": "background-color: #f0fdfa; color: #0f766e;",
            "LIVE CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
            "Live Conversion %": "background-color: #f0fdfa; color: #0f766e;",
        }

        # 6. Generate Custom HTML Table with Sticky Headers
        html_code = """
        <style>
            .custom-perf-table-container {
                width: 100%;
                max-height: 550px;
                overflow-y: auto;
                overflow-x: auto;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.02);
                margin-bottom: 20px;
            }
            .custom-perf-table {
                width: 100%;
                border-collapse: collapse;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 0.88rem;
                background-color: #ffffff;
            }
            .custom-perf-table th {
                padding: 12px 14px;
                font-weight: 800;
                font-size: 0.78rem;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                border-right: 1px solid #f1f5f9;
                position: sticky;
                top: 0;
                z-index: 10;
            }
            .custom-perf-table th:first-child {
                text-align: left;
            }
            .custom-perf-table td {
                padding: 10px 14px;
                text-align: center;
                border-bottom: 1px solid #f1f5f9;
                border-right: 1px solid #f8fafc;
                color: #1e293b;
            }
            .custom-perf-table td:first-child {
                text-align: left;
                font-weight: 700;
                color: #0f172a;
            }
            .custom-perf-table tr:hover {
                background-color: #f8fafc;
            }
            .new-tag {
                background-color: #ede9fe;
                color: #6d28d9;
                font-size: 0.68rem;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 6px;
                margin-left: 6px;
                display: inline-block;
                vertical-align: middle;
            }
            .cs-tag {
                background-color: #e0f2fe;
                color: #0369a1;
                font-size: 0.68rem;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 6px;
                margin-left: 6px;
                display: inline-block;
                vertical-align: middle;
            }
            .left-tag {
                background-color: #fee2e2;
                color: #991b1b;
                font-size: 0.68rem;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 6px;
                margin-left: 6px;
                display: inline-block;
                vertical-align: middle;
            }
        </style>
        <div class="custom-perf-table-container">
            <table class="custom-perf-table">
                <thead>
                    <tr>
        """

        # Add header row
        for col in visible_cols:
            style = header_styles.get(col, "background-color: #f8fafc; color: #475569;")
            html_code += f'<th style="{style}">{col}</th>'
        html_code += "</tr></thead><tbody>"

        # Add data rows
        for _, row in advisor_summary.iterrows():
            html_code += "<tr>"
            for col in visible_cols:
                if col == "SALES EXECUTIVE":
                    name = str(row[col])
                    clean_name = name.strip().lower()
                    
                    is_new = clean_name in [a.strip().lower() for a in NEW_ADVISORS]
                    is_cs = clean_name in [a.strip().lower() for a in CUSTOMER_SERVICE_ADVISORS]
                    is_left = clean_name in [a.strip().lower() for a in LEFT_ADVISORS]
                    
                    tags_html = ""
                    if is_new:
                        tags_html += '<span class="new-tag">New</span>'
                    if is_cs:
                        tags_html += '<span class="cs-tag">Customer Service</span>'
                    if is_left:
                        tags_html += '<span class="left-tag">Left</span>'
                        
                    html_code += f"<td>{name}{tags_html}</td>"

                elif col == "QA Pass Rate %":
                    pill_html = render_qa_pill(row["QA Pass Rate % Val"])
                    html_code += f"<td>{pill_html}</td>"

                elif col == "Welcome Done %":
                    pill_html = render_welcome_pill(row["Welcome Done % Val"])
                    html_code += f"<td>{pill_html}</td>"

                elif col == "Live Conversion %":
                    pill_html = render_live_pill(row["Live Conversion % Val"])
                    html_code += f"<td>{pill_html}</td>"

                else:
                    val = row[col]
                    formatted_val = "-" if val == 0 else f"{val:,}"
                    html_code += f"<td>{formatted_val}</td>"

            html_code += "</tr>"

        html_code += "</tbody></table></div>"

        # Render table
        st.markdown(html_code, unsafe_allow_html=True)

else:
    st.info("No sales records available for the selected date or month filter.")

