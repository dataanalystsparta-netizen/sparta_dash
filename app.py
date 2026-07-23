import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ==========================================================
# PAGE CONFIGURATION
# ==========================================================
st.set_page_config(
    page_title="Sparta Sales & Performance Dashboard",
    page_icon="📊",
    layout="wide"
)

# ==========================================================
# GOOGLE SHEETS CONNECTION & DATA LOADING
# ==========================================================
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=600)
def load_data():
    client = get_gspread_client()
    
    # Load Applications Sheet
    sheet1 = client.open("Sparta Sales Dashboard").worksheet("Applications")
    data1 = sheet1.get_all_records()
    df1 = pd.DataFrame(data1)
    
    # Load Portal Sheet
    sheet2 = client.open("Sparta Sales Dashboard").worksheet("Portal")
    data2 = sheet2.get_all_records()
    df2 = pd.DataFrame(data2)
    
    return df1, df2

try:
    sparta_df, sparta2_df = load_data()
except Exception as e:
    st.error(f"Failed to load data from Google Sheets: {e}")
    st.stop()

# ==========================================================
# DATA CLEANING & STANDARDIZATION HELPERS
# ==========================================================
def clean_status(val):
    if pd.isna(val) or str(val).strip() == "":
        return "Pending"
    s = str(val).strip().title()
    if s in ["Approved", "Approve", "Pass", "Clean"]:
        return "Approved"
    elif s in ["Rework", "Review"]:
        return "Rework"
    elif s in ["Cancelled", "Canceled", "Cancel", "Declined"]:
        return "Cancelled"
    elif s in ["Done", "Completed", "Success"]:
        return "Done"
    elif s in ["Live", "Active"]:
        return "Live"
    elif s in ["Committed", "Commit"]:
        return "Committed"
    return s

# Clean Status Columns if they exist
if "Quality Status" in sparta_df.columns:
    sparta_df["Quality Status Clean"] = sparta_df["Quality Status"].apply(clean_status)
else:
    sparta_df["Quality Status Clean"] = "Pending"

if "Welcome Status" in sparta_df.columns:
    sparta_df["Welcome Status Clean"] = sparta_df["Welcome Status"].apply(clean_status)
else:
    sparta_df["Welcome Status Clean"] = "Pending"

if "Portal Status" in sparta2_df.columns:
    sparta2_df["Portal Status Clean"] = sparta2_df["Portal Status"].apply(clean_status)
else:
    sparta2_df["Portal Status Clean"] = "Pending"

# Standardize Date Columns for sorting and merging
def parse_dates(df, date_col):
    if date_col in df.columns:
        return pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
    return pd.Series([pd.NaT] * len(df))

sparta_df["Period_Sort"] = parse_dates(sparta_df, "Sale Date")
sparta2_df["Period_Sort"] = parse_dates(sparta2_df, "Sale Date")

# Merge or setup Master view
master_raw_df = sparta_df.copy()

# ==========================================================
# SIDEBAR FILTERS
# ==========================================================
st.sidebar.header("🔍 Global Filters")

# Date Filters
min_date = master_raw_df["Period_Sort"].min()
max_date = master_raw_df["Period_Sort"].max()

if pd.isna(min_date):
    min_date = datetime(2026, 1, 1)
if pd.isna(max_date):
    max_date = datetime.now()

start_date, end_date = st.sidebar.date_input(
    "Date Range",
    [min_date.date(), max_date.date()]
)

# Advisor groupings configuration
NEW_ADVISORS = []
CUSTOMER_SERVICE_ADVISORS = []
LEFT_ADVISORS = []

# Filter Master Data by Date
filtered_app_df = master_raw_df.copy()
if start_date and end_date:
    filtered_app_df = filtered_app_df[
        (filtered_app_df["Period_Sort"].dt.date >= start_date) &
        (filtered_app_df["Period_Sort"].dt.date <= end_date)
    ]

filtered_portal_df = sparta2_df.copy()
if start_date and end_date:
    filtered_portal_df = filtered_portal_df[
        (filtered_portal_df["Period_Sort"].dt.date >= start_date) &
        (filtered_portal_df["Period_Sort"].dt.date <= end_date)
    ]

master_df = filtered_app_df.copy()

# ==========================================================
# MAIN DASHBOARD HEADER & KPI CARDS
# ==========================================================
st.title("📊 Sparta Sales & Performance Dashboard")
st.markdown("Real-time operational overview tracking applications, QA status, welcome workflows, and live conversions.")

# Helper for counting statuses safely
def count_status(df, col, target):
    if col in df.columns:
        return int((df[col] == target).sum())
    return 0

total_applications = len(master_df)
qa_approved = count_status(master_df, "Quality Status Clean", "Approved")
qa_rework = count_status(master_df, "Quality Status Clean", "Rework")
qa_cancelled = count_status(master_df, "Quality Status Clean", "Cancelled")

welcome_done = count_status(master_df, "Welcome Status Clean", "Done")
portal_live = count_status(filtered_portal_df, "Portal Status Clean", "Live")

qa_pass_rate = (qa_approved / total_applications * 100) if total_applications > 0 else 0.0
welcome_rate = (welcome_done / total_applications * 100) if total_applications > 0 else 0.0
live_conversion = (portal_live / total_applications * 100) if total_applications > 0 else 0.0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Applications", f"{total_applications:,}")
col2.metric("QA Approved", f"{qa_approved:,}", f"{qa_pass_rate:.1f}% Pass Rate")
col3.metric("QA Rework", f"{qa_rework:,}")
col4.metric("Welcome Done", f"{welcome_done:,}", f"{welcome_rate:.1f}% Rate")
col5.metric("Live Conversions", f"{portal_live:,}", f"{live_conversion:.1f}% Conversion")

# ==========================================================
# MONTHLY KPI BREAKDOWN TABLE (2026 ONLY, INDEPENDENT OF TOP FILTERS)
# ==========================================================

st.divider()
st.subheader("📅 Monthly KPI Breakdown (2026)")

monthly_app_df = master_raw_df.dropna(subset=["Period_Sort"]).copy()
monthly_app_df = monthly_app_df[monthly_app_df["Period_Sort"].dt.year == 2026]

monthly_portal_df = sparta2_df.dropna(subset=["Period_Sort"]).copy()
monthly_portal_df = monthly_portal_df[monthly_portal_df["Period_Sort"].dt.year == 2026]

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
    st.info("No 2026 monthly data available for the KPI summary table.")

# ==========================================================
# TAG VISIBILITY FILTERS
# ==========================================================

st.markdown("##### ⚙️ Sales Executive View Filters")
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
with filter_col1:
    include_new = st.checkbox("Include New", value=True)
with filter_col2:
    include_cs = st.checkbox("Include Customer Service", value=True)
with filter_col3:
    include_left = st.checkbox("Include Left", value=False)
with filter_col4:
    include_untagged = st.checkbox("Include Untagged", value=True)

# ==========================================================
# ADVISOR PERFORMANCE MATRIX
# ==========================================================

st.divider()
st.subheader("👥 Sales Executive Performance Breakdown")

if "Advisor" in master_df.columns and not master_df.empty:

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
        advisor_summary["QA Pass Rate % Val"] = (
            (advisor_summary["QA_Approved"] / advisor_summary["Applications"].replace(0, np.nan)) * 100
        ).fillna(0.0)

        advisor_summary["Welcome Done % Val"] = (
            (advisor_summary["Welcome_Done"] / advisor_summary["Applications"].replace(0, np.nan)) * 100
        ).fillna(0.0)

        advisor_summary["Live Conversion % Val"] = (
            (advisor_summary["Live"] / advisor_summary["Applications"].replace(0, np.nan)) * 100
        ).fillna(0.0)

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

        html_code = """
        <style>
            .custom-perf-table-container {
                width: 100%;
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

        for col in visible_cols:
            style = header_styles.get(col, "background-color: #f8fafc; color: #475569;")
            html_code += f'<th style="{style}">{col}</th>'
        html_code += "</tr></thead><tbody>"

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
        st.markdown(html_code, unsafe_allow_html=True)

else:
    st.info("No sales records available for the selected date or month filter.")

# ==========================================================
# FOOTER & PREVIEW TABS
# ==========================================================

if "Sale Date Clean" in master_df.columns: master_df = master_df.drop(columns=["Sale Date Clean"])
if "Sale Date Clean" in filtered_portal_df.columns: filtered_portal_df = filtered_portal_df.drop(columns=["Sale Date Clean"])

st.divider()
st.header("📂 Data Preview")

tab1, tab2, tab3 = st.tabs(["Applications", "Portal", "Master Dataset"])

with tab1:
    st.dataframe(sparta_df.drop(columns=["Sale Date Clean"], errors="ignore"), use_container_width=True, height=450, hide_index=True)

with tab2:
    st.dataframe(sparta2_df.drop(columns=["Sale Date Clean"], errors="ignore"), use_container_width=True, height=450, hide_index=True)

with tab3:
    st.dataframe(master_df, use_container_width=True, height=500, hide_index=True)

st.divider()
st.success("✅ Data loaded successfully")
st.caption(f"Dashboard refreshed at {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
