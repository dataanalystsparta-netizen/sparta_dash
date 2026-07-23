import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="Sparta Sales Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Native st.metric Styling matching card design + individual soft background tints
st.markdown("""
<style>
    /* Card Container Base */
    [data-testid="stMetric"] {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 8px 4px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        text-align: center !important;
        align-items: center !important;
        justify-content: center !important;
    }

    /* Centered Text Layout */
    [data-testid="stMetric"] > div {
        width: 100%;
        display: flex;
        flex-direction: column;
        align-items: center !important;
        justify-content: center !important;
    }

    /* Card Title (Upper Label) */
    [data-testid="stMetricLabel"] {
        font-size: 0.58rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        color: #475569;
        letter-spacing: 0.3px;
        margin-bottom: 2px;
        justify-content: center !important;
    }
    
    [data-testid="stMetricLabel"] p {
        font-size: 0.58rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
    }

    /* Card Main Value */
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        line-height: 1.1;
        margin-bottom: 2px;
    }

    /* Card Subtext (Delta) */
    [data-testid="stMetricDelta"] {
        font-size: 0.62rem !important;
        font-weight: 700 !important;
        justify-content: center !important;
    }
    
    [data-testid="stMetricDelta"] svg {
        display: none !important; /* Hide native arrow icons */
    }

    /* INDIVIDUAL ACCENT STRIPS + SOFT LIGHT BACKGROUNDS BY COLUMN */
    
    /* Col 1: Soft Blue */
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] { 
        border-top: 4px solid #3b82f6 !important; background-color: #eff6ff !important; 
    }
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetricDelta"] { color: #1d4ed8 !important; }

    /* Col 2: Soft Green */
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] { 
        border-top: 4px solid #10b981 !important; background-color: #f0fdf4 !important; 
    }
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetricDelta"] { color: #15803d !important; }

    /* Col 3: Soft Yellow */
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 4: Soft Red */
    [data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(4) [data-testid="stMetricDelta"] { color: #b91c1c !important; }

    /* Col 5: Soft Orange */
    [data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"] { 
        border-top: 4px solid #f97316 !important; background-color: #fff7ed !important; 
    }
    [data-testid="stColumn"]:nth-child(5) [data-testid="stMetricDelta"] { color: #c2410c !important; }

    /* Col 6: Soft Green */
    [data-testid="stColumn"]:nth-child(6) [data-testid="stMetric"] { 
        border-top: 4px solid #10b981 !important; background-color: #f0fdf4 !important; 
    }
    [data-testid="stColumn"]:nth-child(6) [data-testid="stMetricDelta"] { color: #15803d !important; }

    /* Col 7: Soft Red */
    [data-testid="stColumn"]:nth-child(7) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(7) [data-testid="stMetricDelta"] { color: #b91c1c !important; }

    /* Col 8: Soft Yellow */
    [data-testid="stColumn"]:nth-child(8) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(8) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 9: Soft Teal */
    [data-testid="stColumn"]:nth-child(9) [data-testid="stMetric"] { 
        border-top: 4px solid #14b8a6 !important; background-color: #f0fdfa !important; 
    }
    [data-testid="stColumn"]:nth-child(9) [data-testid="stMetricDelta"] { color: #0f766e !important; }

    /* Col 10: Soft Yellow */
    [data-testid="stColumn"]:nth-child(10) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(10) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 11: Soft Red */
    [data-testid="stColumn"]:nth-child(11) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(11) [data-testid="stMetricDelta"] { color: #b91c1c !important; }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# CONSTANTS & GOOGLE SHEETS CONNECTION
# ==========================================================

SPREADSHEET_ID = "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ"
APPLICATION_SHEET = "Sparta"
LIVE_SHEET = "Sparta2"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def get_google_service():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)

@st.cache_data(ttl=300, show_spinner=False)
def load_sheet(sheet_name):
    service = get_google_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=sheet_name
        ).execute()
    except Exception:
        service = get_google_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=sheet_name
        ).execute()

    values = result.get("values", [])
    if not values:
        return pd.DataFrame()

    headers, rows = values[0], values[1:]
    max_cols = len(headers)
    cleaned_rows = [
        r + [""] * (max_cols - len(r)) if len(r) < max_cols else r[:max_cols]
        for r in rows
    ]
    return pd.DataFrame(cleaned_rows, columns=headers)

# ==========================================================
# HELPER & DATA CLEANING FUNCTIONS
# ==========================================================

def clean_phone(series):
    return series.astype(str).str.replace(r"\D", "", regex=True).str.lstrip("0").str.strip()

def parse_mixed_dates(val):
    if pd.isna(val) or str(val).strip() in ["", "(blank)", "nan", "none"]:
        return pd.NaT
    val_str = str(val).strip()
    iso_match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", val_str)
    if iso_match:
        year, month, day = iso_match.groups()
        try: return pd.Timestamp(year=int(year), month=int(month), day=int(day))
        except ValueError: pass

    uk_match = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", val_str)
    if uk_match:
        day, month, year = uk_match.groups()
        try: return pd.Timestamp(year=int(year), month=int(month), day=int(day))
        except ValueError: pass

    return pd.to_datetime(val_str, errors="coerce", dayfirst=True)

def parse_date_to_datetime(series):
    return series.apply(parse_mixed_dates)

def format_date_ddmmyyyy(series):
    parsed = parse_date_to_datetime(series)
    return parsed.dt.strftime("%d/%m/%Y").fillna("")

def categorize_quality_status(val):
    if pd.isna(val): return "Pending"
    val_str = str(val).strip().lower()
    if val_str in ["", "(blank)", "nan", "none"]: return "Pending"
    if "appr" in val_str: return "Approved"
    if "rework" in val_str: return "Rework"
    if any(k in val_str for k in ["cancel", "reject", "hold", "duplicat", "inbound", "n/a", "rec in accessible"]): return "Cancelled"
    return "Cancelled"

def categorize_welcome_status(val):
    if pd.isna(val): return "Pending"
    val_str = str(val).strip().lower()
    if val_str in ["", "(blank)", "nan", "none"]: return "Pending"
    if "done" in val_str: return "Done"
    if any(k in val_str for k in ["cancel", "reject", "hold"]): return "Cancelled"
    if any(k in val_str for k in ["pending", "follow", "paperwork", "wrong", "ring"]): return "Pending"
    return "Pending"

def categorize_portal_status(val):
    if pd.isna(val): return "Committed"
    val_str = str(val).strip().lower()
    if val_str in ["", "(blank)", "nan", "none"]: return "Committed"
    if any(k in val_str for k in ["cancel", "reject"]): return "Cancelled"
    if any(k in val_str for k in ["live", "active", "completed"]): return "Live"
    if any(k in val_str for k in ["commit", "pending", "in progress", "processing"]): return "Committed"
    return "Committed"

# ==========================================================
# APP HEADER
# ==========================================================

st.title("📊 Sparta Sales Dashboard")
st.caption(f"Last refresh : {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
st.divider()

# ==========================================================
# LOAD DATASETS
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sparta():
    df = load_sheet(APPLICATION_SHEET)
    rename_map = {
        "Advisor": "Advisor", "Sale Date": "Sale Date", "Customer Name": "Customer Name",
        "CLI": "Telephone No.", "Quality Date": "Quality Date", "Quality Status": "Quality Status",
        "Quality Remarks": "Quality Remarks", "Welcome call Remarks": "Welcome Remarks",
        "Status": "Welcome Status", "Cancellation Sub-text": "Welcome Cancellation",
        "WCD date": "Welcome Date", "Provisioning": "Provisioning Status",
        "Prov Date": "Provisioning Date", "Current Provider": "Current Provider",
        "Packageoffered": "Package", "Dashboard_Month": "Dashboard Month",
        "Standardized_Date": "Standardized Date"
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    keep_columns = [c for c in list(rename_map.values()) if c in df.columns]
    df = df[keep_columns].copy()
    df["Telephone No."] = clean_phone(df["Telephone No."])
    df["Sale Date Clean"] = parse_date_to_datetime(df["Sale Date"])

    for col in ["Sale Date", "Quality Date", "Welcome Date", "Provisioning Date", "Standardized Date"]:
        if col in df.columns:
            df[col] = format_date_ddmmyyyy(df[col])

    if "Quality Status" in df.columns: df["Quality Status Clean"] = df["Quality Status"].apply(categorize_quality_status)
    if "Welcome Status" in df.columns: df["Welcome Status Clean"] = df["Welcome Status"].apply(categorize_welcome_status)
    return df

@st.cache_data(ttl=300, show_spinner=False)
def load_sparta2():
    df = load_sheet(LIVE_SHEET)
    rename_map = {
        "Sale Date": "Sale Date", "Telephone No.": "Telephone No.",
        "Committed Date": "Live Date", "Status": "Portal Status",
        "LetterStatus": "Letter Status", "CallStatus": "Call Status",
        "Comments": "Comments", "Voice of Customer": "Voice of Customer",
        "Cancellation Reason": "Portal Cancellation", "Dashboard_Month": "Dashboard Month",
        "Standardized_Date": "Standardized Date"
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    keep_columns = [c for c in list(rename_map.values()) if c in df.columns]
    df = df[keep_columns].copy()
    df["Telephone No."] = clean_phone(df["Telephone No."])

    if "Sale Date" in df.columns:
        df["Sale Date Clean"] = parse_date_to_datetime(df["Sale Date"])
        df["Sale Date"] = format_date_ddmmyyyy(df["Sale Date"])

    for date_col in ["Live Date", "Standardized Date"]:
        if date_col in df.columns:
            df[date_col] = format_date_ddmmyyyy(df[date_col])

    if "Portal Status" in df.columns: df["Portal Status Clean"] = df["Portal Status"].apply(categorize_portal_status)
    return df

with st.spinner("Loading Google Sheets..."):
    sparta_df = load_sparta()
    sparta2_df = load_sparta2()

@st.cache_data(ttl=300, show_spinner=False)
def build_master_dataframe(app_df, portal_df):
    apps = app_df.copy()
    portal = portal_df.copy()
    portal = portal[portal["Telephone No."] != ""].copy() if "Telephone No." in portal.columns else portal
    portal = portal.drop_duplicates(subset="Telephone No.", keep="last")
    return apps.merge(portal, on="Telephone No.", how="left", suffixes=("", "_portal"))

master_raw_df = build_master_dataframe(sparta_df, sparta2_df)

# ==========================================================
# FILTERS SECTION
# ==========================================================

st.subheader("📅 Filters")

if "Sale Date Clean" in master_raw_df.columns and not master_raw_df["Sale Date Clean"].dropna().empty:
    master_raw_df["Month_Year"] = master_raw_df["Sale Date Clean"].dt.strftime("%B %Y")
    available_months = ["All Months"] + list(
        master_raw_df["Sale Date Clean"].dt.to_period("M").drop_duplicates().sort_values(ascending=False).dt.strftime("%B %Y")
    )
else:
    available_months = ["All Months"]

valid_dates = master_raw_df["Sale Date Clean"].dropna() if "Sale Date Clean" in master_raw_df.columns else pd.Series()
min_date = valid_dates.min().date() if not valid_dates.empty else datetime.today().date()
max_date = valid_dates.max().date() if not valid_dates.empty else datetime.today().date()

filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])

with filter_col1:
    selected_month = st.selectbox("Select Month", options=available_months, index=0)

with filter_col2:
    start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

with filter_col3:
    end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

if start_date <= end_date:
    date_mask = (master_raw_df["Sale Date Clean"].dt.date >= start_date) & (master_raw_df["Sale Date Clean"].dt.date <= end_date)
    if selected_month != "All Months":
        date_mask = date_mask & (master_raw_df["Month_Year"] == selected_month)
    master_df = master_raw_df[date_mask].copy()

    if "Sale Date Clean" in sparta2_df.columns:
        sparta2_df["Month_Year"] = sparta2_df["Sale Date Clean"].dt.strftime("%B %Y")
        portal_date_mask = (sparta2_df["Sale Date Clean"].dt.date >= start_date) & (sparta2_df["Sale Date Clean"].dt.date <= end_date)
        if selected_month != "All Months":
            portal_date_mask = portal_date_mask & (sparta2_df["Month_Year"] == selected_month)
        filtered_portal_df = sparta2_df[portal_date_mask].copy()
    else:
        filtered_portal_df = sparta2_df.copy()
else:
    st.error("Error: Start Date must be earlier than or equal to End Date.")
    master_df = master_raw_df.copy()
    filtered_portal_df = sparta2_df.copy()

# ==========================================================
# TOP KPI SECTION (CARDS HIDE WHEN VALUE = 0)
# ==========================================================

st.subheader("📌 Key Performance Indicators")

def count_status(df, column, target_val):
    return (df[column] == target_val).sum() if column in df.columns else 0

def get_pct(part, total):
    return "0.0%" if total == 0 else f"{(part / total * 100):.1f}%"

total_applications = len(master_df)
portal_total = len(filtered_portal_df)

q_approved = count_status(master_df, "Quality Status Clean", "Approved")
q_rework = count_status(master_df, "Quality Status Clean", "Rework")
q_cancelled = count_status(master_df, "Quality Status Clean", "Cancelled")
q_pending = count_status(master_df, "Quality Status Clean", "Pending")

wc_done = count_status(master_df, "Welcome Status Clean", "Done")
wc_cancelled = count_status(master_df, "Welcome Status Clean", "Cancelled")
wc_pending = count_status(master_df, "Welcome Status Clean", "Pending")

portal_live = count_status(filtered_portal_df, "Portal Status Clean", "Live")
portal_committed = count_status(filtered_portal_df, "Portal Status Clean", "Committed")
portal_cancelled = count_status(filtered_portal_df, "Portal Status Clean", "Cancelled")

all_kpis = [
    ("Applications", total_applications, "100% Base"),
    ("Quality Approved", q_approved, f"{get_pct(q_approved, total_applications)} Qualified"),
    ("Quality Rework", q_rework, f"{get_pct(q_rework, total_applications)} In Rework"),
    ("Quality Cancelled", q_cancelled, f"{get_pct(q_cancelled, total_applications)} Rejected"),
    ("Quality Pending", q_pending, f"{get_pct(q_pending, total_applications)} Pending"),
    ("Welcome Done", wc_done, f"{get_pct(wc_done, total_applications)} Completed"),
    ("Welcome Cancelled", wc_cancelled, f"{get_pct(wc_cancelled, total_applications)} Cancelled"),
    ("Welcome Pending", wc_pending, f"{get_pct(wc_pending, total_applications)} Pending"),
    ("Live Status: Live", portal_live, f"{get_pct(portal_live, portal_total)} Live/Pend."),
    ("Live Status: Comm.", portal_committed, f"{get_pct(portal_committed, portal_total)} Pipeline"),
    ("Live Status: Canc.", portal_cancelled, f"{get_pct(portal_cancelled, portal_total)} Churned")
]

# Filter out any KPI where value == 0
visible_kpis = [kpi for kpi in all_kpis if kpi[1] > 0]

if visible_kpis:
    cols = st.columns(len(visible_kpis))
    for col, (label, val, delta_sub) in zip(cols, visible_kpis):
        with col:
            st.metric(label=label, value=f"{val:,}", delta=delta_sub)
else:
    st.info("No active KPIs for the selected filters.")

# ==========================================================
# ADVISOR PERFORMANCE MATRIX (EXACT IMAGE PILL BADGE DESIGN)
# ==========================================================

st.divider()
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

    # 2. Rename columns to match standard layout
    advisor_summary = advisor_summary.rename(columns={
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
        "Live_Cancelled": "LIVE CANCELLED"
    })

    advisor_summary["SALES EXECUTIVE"] = advisor_summary["SALES EXECUTIVE"].replace("", "Unassigned").fillna("Unassigned")
    advisor_summary = advisor_summary.sort_values(by="APPLICATIONS", ascending=False)

    # Calculate percentage floats for sorting/logic
    advisor_summary["QA Pass Rate % Val"] = (
        (advisor_summary["QA APPROVED"] / advisor_summary["APPLICATIONS"].replace(0, np.nan)) * 100
    ).fillna(0.0)
    
    advisor_summary["Live Conversion % Val"] = (
        (advisor_summary["Live"] / advisor_summary["APPLICATIONS"].replace(0, np.nan)) * 100
    ).fillna(0.0)

    # Determine visible columns (Hide columns where sum is 0)
    numeric_cols = [
        "APPLICATIONS", "QA APPROVED", "QA REWORK", "QA CANCELLED", "QA PENDING",
        "WELCOME DONE", "WELCOME CANCELLED", "WELCOME PENDING", "COMMITTED REM.",
        "LIVE", "LIVE CANCELLED"
    ]
    
    base_col_order = [
        "SALES EXECUTIVE",
        "APPLICATIONS",
        "QA APPROVED",
        "QA Pass Rate %",
        "QA REWORK",
        "QA CANCELLED",
        "QA PENDING",
        "WELCOME DONE",
        "WELCOME CANCELLED",
        "WELCOME PENDING",
        "COMMITTED REM.",
        "LIVE",
        "LIVE CANCELLED",
        "Live Conversion %"
    ]

    visible_cols = ["SALES EXECUTIVE"]
    for col in base_col_order[1:]:
        if col in numeric_cols:
            if (advisor_summary[col] > 0).any():
                visible_cols.append(col)
        elif col == "QA Pass Rate %":
            if "QA APPROVED" in visible_cols:
                visible_cols.append(col)
        elif col == "Live Conversion %":
            if "LIVE" in visible_cols:
                visible_cols.append(col)

    # 3. Helper to style percentage badges
    def render_pill(val_float, high_thresh=70.0, mid_thresh=50.0):
        val_str = f"{val_float:.1f}%"
        if val_float >= high_thresh:
            bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
        elif val_float >= mid_thresh:
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
        "WELCOME CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
        "WELCOME PENDING": "background-color: #fefce8; color: #a16207;",
        "COMMITTED REM.": "background-color: #fff7ed; color: #c2410c;",
        "LIVE": "background-color: #f0fdfa; color: #0f766e;",
        "LIVE CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
        "Live Conversion %": "background-color: #f0fdfa; color: #0f766e;"
    }

    # 4. Generate Custom HTML Table
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
                # Add "New" tag if sales executive total applications are <= 5
                is_new = row["APPLICATIONS"] <= 5
                tag_html = '<span class="new-tag">New</span>' if is_new else ""
                html_code += f'<td>{name}{tag_html}</td>'
                
            elif col == "QA Pass Rate %":
                pill_html = render_pill(row["QA Pass Rate % Val"], high_thresh=70.0, mid_thresh=50.0)
                html_code += f'<td>{pill_html}</td>'
                
            elif col == "Live Conversion %":
                pill_html = render_pill(row["Live Conversion % Val"], high_thresh=15.0, mid_thresh=8.0)
                html_code += f'<td>{pill_html}</td>'
                
            else:
                # Format numeric zero as "-"
                val = row[col]
                formatted_val = "-" if val == 0 else f"{val:,}"
                html_code += f'<td>{formatted_val}</td>'
                
        html_code += "</tr>"

    html_code += "</tbody></table></div>"

    # Render directly via st.markdown
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
