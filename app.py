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

# Custom CSS for Native st.metric Styling matching card design + soft background tints
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

    /* TOP ACCENT STRIPS + SOFT LIGHT BACKGROUNDS BY COLUMN (1 to 11) */
    
    /* Col 1: Applications (Soft Blue) */
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] { 
        border-top: 4px solid #3b82f6 !important; 
        background-color: #eff6ff !important; 
    }
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetricDelta"] { color: #1d4ed8 !important; }

    /* Col 2: QA Approved (Soft Green) */
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] { 
        border-top: 4px solid #10b981 !important; 
        background-color: #f0fdf4 !important; 
    }
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetricDelta"] { color: #15803d !important; }

    /* Col 3: QA Rework (Soft Yellow) */
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; 
        background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 4: QA Cancelled (Soft Red) */
    [data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; 
        background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(4) [data-testid="stMetricDelta"] { color: #b91c1c !important; }

    /* Col 5: QA Pending (Soft Orange/Yellow) */
    [data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"] { 
        border-top: 4px solid #f97316 !important; 
        background-color: #fff7ed !important; 
    }
    [data-testid="stColumn"]:nth-child(5) [data-testid="stMetricDelta"] { color: #c2410c !important; }

    /* Col 6: Welcome Done (Soft Green) */
    [data-testid="stColumn"]:nth-child(6) [data-testid="stMetric"] { 
        border-top: 4px solid #10b981 !important; 
        background-color: #f0fdf4 !important; 
    }
    [data-testid="stColumn"]:nth-child(6) [data-testid="stMetricDelta"] { color: #15803d !important; }

    /* Col 7: Welcome Cancel (Soft Red) */
    [data-testid="stColumn"]:nth-child(7) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; 
        background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(7) [data-testid="stMetricDelta"] { color: #b91c1c !important; }

    /* Col 8: Welcome Pend. (Soft Yellow) */
    [data-testid="stColumn"]:nth-child(8) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; 
        background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(8) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 9: Live (Soft Teal) */
    [data-testid="stColumn"]:nth-child(9) [data-testid="stMetric"] { 
        border-top: 4px solid #14b8a6 !important; 
        background-color: #f0fdfa !important; 
    }
    [data-testid="stColumn"]:nth-child(9) [data-testid="stMetricDelta"] { color: #0f766e !important; }

    /* Col 10: Committed (Soft Yellow) */
    [data-testid="stColumn"]:nth-child(10) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; 
        background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(10) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 11: Live Cancelled (Soft Red) */
    [data-testid="stColumn"]:nth-child(11) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; 
        background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(11) [data-testid="stMetricDelta"] { color: #b91c1c !important; }

    /* CUSTOM ADVISOR MATRIX TABLE STYLING */
    .sparta-table-container {
        width: 100%;
        overflow-x: auto;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        margin-top: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .sparta-table {
        width: 100%;
        border-collapse: collapse;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 13px;
        color: #1e293b;
    }
    .sparta-table th {
        padding: 12px 14px;
        font-weight: 800;
        font-size: 11px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        border-bottom: 2px solid #cbd5e1;
        border-right: 1px solid #e2e8f0;
        text-align: center;
    }
    .sparta-table td {
        padding: 10px 14px;
        border-bottom: 1px solid #f1f5f9;
        border-right: 1px solid #f1f5f9;
        text-align: center;
    }
    .sparta-table tr:hover {
        background-color: #f8fafc;
    }
    
    /* Executive Header Colors */
    .th-exec { background-color: #f1f5f9; color: #334155; text-align: left !important; }
    .th-apps { background-color: #eff6ff; color: #1d4ed8; }
    .th-qa-app { background-color: #f0fdf4; color: #15803d; }
    .th-qa-rate { background-color: #f0fdf4; color: #15803d; }
    .th-comm { background-color: #fff7ed; color: #c2410c; }
    .th-live { background-color: #f0fdfa; color: #0f766e; }
    .th-conv { background-color: #f0fdfa; color: #0f766e; }

    /* Column Specific Text Styling */
    .td-exec { text-align: left !important; font-weight: 700; color: #0f172a; }
    .td-bold { font-weight: 700; color: #334155; }

    /* Status Pills / Badges */
    .badge-new {
        background-color: #dbeafe;
        color: #1e40af;
        font-size: 9px;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 8px;
        text-transform: uppercase;
    }
    .pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 11.5px;
        width: 65px;
        text-align: center;
    }
    .pill-green { background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .pill-yellow { background-color: #fef9c3; color: #a16207; border: 1px solid #fef08a; }
    .pill-red { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }

    .tr-total {
        background-color: #f8fafc;
        font-weight: 800;
        border-top: 2px solid #cbd5e1;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# CONSTANTS
# ==========================================================

SPREADSHEET_ID = "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ"

APPLICATION_SHEET = "Sparta"
LIVE_SHEET = "Sparta2"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]

# ==========================================================
# GOOGLE SHEETS CONNECTION
# ==========================================================

def get_google_service():
    """Generates a fresh service object to prevent stale TCP sockets in Streamlit Cloud."""
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)

# ==========================================================
# GENERIC SHEET LOADER
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sheet(sheet_name):

    service = get_google_service()

    try:
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=SPREADSHEET_ID,
                range=sheet_name
            )
            .execute()
        )
    except Exception:
        # Retry with fresh service instance if socket dropped
        service = get_google_service()
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=SPREADSHEET_ID,
                range=sheet_name
            )
            .execute()
        )

    values = result.get("values", [])

    if not values:
        return pd.DataFrame()

    headers = values[0]
    rows = values[1:]

    max_cols = len(headers)
    cleaned_rows = []

    for row in rows:
        if len(row) < max_cols:
            row.extend([""] * (max_cols - len(row)))
        elif len(row) > max_cols:
            row = row[:max_cols]
        cleaned_rows.append(row)

    return pd.DataFrame(cleaned_rows, columns=headers)

# ==========================================================
# HELPER & DATA CLEANING FUNCTIONS
# ==========================================================

def clean_phone(series):
    return (
        series.astype(str)
        .str.replace(r"\D", "", regex=True)
        .str.lstrip("0")
        .str.strip()
    )

def parse_mixed_dates(val):
    """
    Robust element-wise parser for mixed ISO (YYYY-MM-DD) and UK (DD/MM/YYYY) formats.
    Ensures 2026-01-12 and 12/01/2026 both parse to 12th January 2026.
    """
    if pd.isna(val) or str(val).strip() in ["", "(blank)", "nan", "none"]:
        return pd.NaT
    
    val_str = str(val).strip()
    
    # 1. Check for ISO Format: YYYY-MM-DD (e.g. 2026-01-12 00:00:00)
    iso_match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", val_str)
    if iso_match:
        year, month, day = iso_match.groups()
        try:
            return pd.Timestamp(year=int(year), month=int(month), day=int(day))
        except ValueError:
            pass

    # 2. Check for UK Format: DD/MM/YYYY (e.g. 12/01/2026)
    uk_match = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", val_str)
    if uk_match:
        day, month, year = uk_match.groups()
        try:
            return pd.Timestamp(year=int(year), month=int(month), day=int(day))
        except ValueError:
            pass

    # Fallback parser
    return pd.to_datetime(val_str, errors="coerce", dayfirst=True)

def parse_date_to_datetime(series):
    """Applies the mixed date parser safely across a series."""
    return series.apply(parse_mixed_dates)

def format_date_ddmmyyyy(series):
    """Parses dates safely and converts them into standardized dd/mm/yyyy strings."""
    parsed = parse_date_to_datetime(series)
    return parsed.dt.strftime("%d/%m/%Y").fillna("")

def categorize_quality_status(val):
    if pd.isna(val):
        return "Pending"
    
    val_str = str(val).strip().lower()
    
    if val_str in ["", "(blank)", "nan", "none"]:
        return "Pending"
    
    # Approved
    if "appr" in val_str:
        return "Approved"
    
    # Rework
    if "rework" in val_str:
        return "Rework"
    
    # Cancelled / Rejected
    if any(k in val_str for k in ["cancel", "reject", "hold", "duplicat", "inbound", "n/a", "rec in accessible"]):
        return "Cancelled"
    
    return "Cancelled"

def categorize_welcome_status(val):
    if pd.isna(val):
        return "Pending"
    
    val_str = str(val).strip().lower()
    
    if val_str in ["", "(blank)", "nan", "none"]:
        return "Pending"
    
    # Done
    if "done" in val_str:
        return "Done"
    
    # Cancelled / Rejected
    if any(k in val_str for k in ["cancel", "reject", "hold"]):
        return "Cancelled"
    
    # Pending
    if any(k in val_str for k in ["pending", "follow", "paperwork", "wrong", "ring"]):
        return "Pending"
    
    return "Pending"

def categorize_portal_status(val):
    """
    Standardizes Portal / Live status.
    Explicitly categorizes both 'Cancelled' and 'Rejected' (and variants) as 'Cancelled'.
    """
    if pd.isna(val):
        return "Committed"
    
    val_str = str(val).strip().lower()
    
    if val_str in ["", "(blank)", "nan", "none"]:
        return "Committed"
    
    # Cancelled: Cancelled, Rejected, To be cancelled
    if any(k in val_str for k in ["cancel", "reject"]):
        return "Cancelled"
    
    # Live: Live, Active, Completed
    if any(k in val_str for k in ["live", "active", "completed"]):
        return "Live"
    
    # Committed: Pending, In Progress, Processing, etc.
    if any(k in val_str for k in ["commit", "pending", "in progress", "processing"]):
        return "Committed"
    
    return "Committed"

# ==========================================================
# APP HEADER
# ==========================================================

st.title("📊 Sparta Sales Dashboard")

st.caption(
    f"Last refresh : {datetime.now().strftime('%d %b %Y %H:%M:%S')}"
)

st.divider()

# ==========================================================
# LOAD APPLICATION SHEET
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sparta():

    df = load_sheet(APPLICATION_SHEET)

    rename_map = {
        "Advisor": "Advisor",
        "Sale Date": "Sale Date",
        "Customer Name": "Customer Name",
        "CLI": "Telephone No.",
        "Quality Date": "Quality Date",
        "Quality Status": "Quality Status",
        "Quality Remarks": "Quality Remarks",
        "Welcome call Remarks": "Welcome Remarks",
        "Status": "Welcome Status",
        "Cancellation Sub-text": "Welcome Cancellation",
        "WCD date": "Welcome Date",
        "Provisioning": "Provisioning Status",
        "Prov Date": "Provisioning Date",
        "Current Provider": "Current Provider",
        "Packageoffered": "Package",
        "Dashboard_Month": "Dashboard Month",
        "Standardized_Date": "Standardized Date"
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    keep_columns = [c for c in list(rename_map.values()) if c in df.columns]

    df = df[keep_columns].copy()
    df["Telephone No."] = clean_phone(df["Telephone No."])

    # Keep parsed Datetime object for internal calculations
    df["Sale Date Clean"] = parse_date_to_datetime(df["Sale Date"])

    # Format all display date columns explicitly to dd/mm/yyyy string format
    date_columns = [
        "Sale Date",
        "Quality Date",
        "Welcome Date",
        "Provisioning Date",
        "Standardized Date"
    ]

    for col in date_columns:
        if col in df.columns:
            df[col] = format_date_ddmmyyyy(df[col])

    # Standardize Quality and Welcome Statuses using clean categorization logic
    if "Quality Status" in df.columns:
        df["Quality Status Clean"] = df["Quality Status"].apply(categorize_quality_status)
    if "Welcome Status" in df.columns:
        df["Welcome Status Clean"] = df["Welcome Status"].apply(categorize_welcome_status)

    return df

# ==========================================================
# LOAD PORTAL SHEET
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sparta2():

    df = load_sheet(LIVE_SHEET)

    rename_map = {
        "Sale Date": "Sale Date",
        "Telephone No.": "Telephone No.",
        "Committed Date": "Live Date",
        "Status": "Portal Status",
        "LetterStatus": "Letter Status",
        "CallStatus": "Call Status",
        "Comments": "Comments",
        "Voice of Customer": "Voice of Customer",
        "Cancellation Reason": "Portal Cancellation",
        "Dashboard_Month": "Dashboard Month",
        "Standardized_Date": "Standardized Date"
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    keep_columns = [c for c in list(rename_map.values()) if c in df.columns]
    df = df[keep_columns].copy()

    df["Telephone No."] = clean_phone(df["Telephone No."])

    # Parse Portal Sheet's independent Sale Date
    if "Sale Date" in df.columns:
        df["Sale Date Clean"] = parse_date_to_datetime(df["Sale Date"])
        df["Sale Date"] = format_date_ddmmyyyy(df["Sale Date"])

    # Format all portal dates to dd/mm/yyyy
    for date_col in ["Live Date", "Standardized Date"]:
        if date_col in df.columns:
            df[date_col] = format_date_ddmmyyyy(df[date_col])

    # Standardize Portal/Live Status
    if "Portal Status" in df.columns:
        df["Portal Status Clean"] = df["Portal Status"].apply(categorize_portal_status)

    return df

# ==========================================================
# LOAD BOTH DATASETS
# ==========================================================

with st.spinner("Loading Google Sheets..."):
    sparta_df = load_sparta()
    sparta2_df = load_sparta2()

# ==========================================================
# BUILD MASTER DATASET
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def build_master_dataframe(app_df, portal_df):
    apps = app_df.copy()
    portal = portal_df.copy()

    portal = portal[portal["Telephone No."] != ""].copy() if "Telephone No." in portal.columns else portal

    portal = portal.drop_duplicates(
        subset="Telephone No.",
        keep="last"
    )

    master = apps.merge(
        portal,
        on="Telephone No.",
        how="left",
        suffixes=("", "_portal")
    )

    return master

master_raw_df = build_master_dataframe(
    sparta_df,
    sparta2_df
)

# ==========================================================
# TOP DATE & MONTH FILTER SECTION
# ==========================================================

st.subheader("📅 Dashboard Filters")

valid_dates = master_raw_df["Sale Date Clean"].dropna() if "Sale Date Clean" in master_raw_df.columns else pd.Series()
min_date = valid_dates.min().date() if not valid_dates.empty else datetime.today().date()
max_date = valid_dates.max().date() if not valid_dates.empty else datetime.today().date()

# Dynamic Month List extraction (YYYY-MM)
if not valid_dates.empty:
    available_months = valid_dates.dt.strftime("%B %Y").unique().tolist()
    # Sort months chronologically
    sorted_months = sorted(available_months, key=lambda x: datetime.strptime(x, "%B %Y"))
else:
    sorted_months = []

filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])

with filter_col1:
    month_option = st.selectbox(
        "Select Month",
        options=["All Months"] + sorted_months,
        index=0
    )

with filter_col2:
    start_date = st.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"
    )

with filter_col3:
    end_date = st.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"
    )

# Filter Logic based on Month dropdown and Date range
master_df = master_raw_df.copy()
filtered_portal_df = sparta2_df.copy()

if month_option != "All Months" and "Sale Date Clean" in master_df.columns:
    month_dt = datetime.strptime(month_option, "%B %Y")
    month_mask = (master_df["Sale Date Clean"].dt.year == month_dt.year) & (master_df["Sale Date Clean"].dt.month == month_dt.month)
    master_df = master_df[month_mask]

    if "Sale Date Clean" in filtered_portal_df.columns:
        p_month_mask = (filtered_portal_df["Sale Date Clean"].dt.year == month_dt.year) & (filtered_portal_df["Sale Date Clean"].dt.month == month_dt.month)
        filtered_portal_df = filtered_portal_df[p_month_mask]
else:
    if start_date <= end_date and "Sale Date Clean" in master_df.columns:
        date_mask = (
            (master_df["Sale Date Clean"].dt.date >= start_date) & 
            (master_df["Sale Date Clean"].dt.date <= end_date)
        )
        master_df = master_df[date_mask].copy()
        
        if "Sale Date Clean" in filtered_portal_df.columns:
            portal_date_mask = (
                (filtered_portal_df["Sale Date Clean"].dt.date >= start_date) & 
                (filtered_portal_df["Sale Date Clean"].dt.date <= end_date)
            )
            filtered_portal_df = filtered_portal_df[portal_date_mask].copy()

# ==========================================================
# TOP KPI SECTION (ST.METRIC 11 COLUMNS)
# ==========================================================

st.subheader("📌 Key Performance Indicators")

def count_status(df, column, target_val):
    if column not in df.columns:
        return 0
    return (df[column] == target_val).sum()

def get_pct(part, total):
    if total == 0:
        return "0.0%"
    return f"{(part / total * 100):.1f}%"

# Denominators
total_applications = len(master_df)
portal_total = len(filtered_portal_df)

# Application & Welcome Call KPIs (from master_df)
q_approved = count_status(master_df, "Quality Status Clean", "Approved")
q_rework = count_status(master_df, "Quality Status Clean", "Rework")
q_cancelled = count_status(master_df, "Quality Status Clean", "Cancelled")
q_pending = count_status(master_df, "Quality Status Clean", "Pending")

wc_done = count_status(master_df, "Welcome Status Clean", "Done")
wc_cancelled = count_status(master_df, "Welcome Status Clean", "Cancelled")
wc_pending = count_status(master_df, "Welcome Status Clean", "Pending")

# Portal / Live KPIs (from filtered_portal_df)
portal_live = count_status(filtered_portal_df, "Portal Status Clean", "Live")
portal_committed = count_status(filtered_portal_df, "Portal Status Clean", "Committed")
portal_cancelled = count_status(filtered_portal_df, "Portal Status Clean", "Cancelled")

cols = st.columns(11)

kpis = [
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

for col, (label, val, delta_sub) in zip(cols, kpis):
    with col:
        st.metric(
            label=label,
            value=f"{val:,}",
            delta=delta_sub
        )

# ==========================================================
# CUSTOM ADVISOR PERFORMANCE MATRIX (STYLED HTML TABLE)
# ==========================================================

st.divider()
st.subheader("👤 Sales Executive Performance Matrix")

if "Advisor" in master_df.columns and not master_df.empty:
    
    # 1. Group by Advisor and calculate metrics
    adv_df = master_df.groupby("Advisor", dropna=False).agg(
        Apps=("Advisor", "count"),
        QA_Approved=("Quality Status Clean", lambda x: (x == "Approved").sum()),
        Committed_Rem=("Portal Status Clean", lambda x: (x == "Committed").sum()),
        Live=("Portal Status Clean", lambda x: (x == "Live").sum())
    ).reset_index()

    # Clean empty advisor names
    adv_df["Advisor"] = adv_df["Advisor"].fillna("Unknown").replace("", "Unknown")
    
    # Sort alphabetically by Advisor Name
    adv_df = adv_df.sort_values(by="Advisor", ascending=True)

    # Build HTML Rows
    table_rows = []
    
    tot_apps = adv_df["Apps"].sum()
    tot_qa_app = adv_df["QA_Approved"].sum()
    tot_comm = adv_df["Committed_Rem"].sum()
    tot_live = adv_df["Live"].sum()

    for _, row in adv_df.iterrows():
        name = row["Advisor"]
        apps = row["Apps"]
        qa_app = row["QA_Approved"]
        comm = row["Committed_Rem"]
        live = row["Live"]

        # Percentages
        qa_rate = (qa_app / apps * 100) if apps > 0 else 0.0
        live_conv = (live / apps * 100) if apps > 0 else 0.0

        # "New" badge for lower production/new agents (e.g. <= 10 apps)
        badge_html = '<span class="badge-new">New</span>' if apps <= 10 else ''

        # Badge Pill Styling for QA Pass Rate %
        if qa_rate >= 65:
            qa_pill = f'<span class="pill pill-green">{qa_rate:.1f}%</span>'
        elif qa_rate >= 50:
            qa_pill = f'<span class="pill pill-yellow">{qa_rate:.1f}%</span>'
        else:
            qa_pill = f'<span class="pill pill-red">{qa_rate:.1f}%</span>'

        # Badge Pill Styling for Live Conversion %
        if live_conv >= 14:
            conv_pill = f'<span class="pill pill-green">{live_conv:.1f}%</span>'
        elif live_conv >= 8:
            conv_pill = f'<span class="pill pill-yellow">{live_conv:.1f}%</span>'
        else:
            conv_pill = f'<span class="pill pill-red">{live_conv:.1f}%</span>'

        row_html = f"""
        <tr>
            <td class="td-exec">{name}{badge_html}</td>
            <td class="td-bold">{apps}</td>
            <td>{qa_app}</td>
            <td>{qa_pill}</td>
            <td>{comm}</td>
            <td>{live}</td>
            <td>{conv_pill}</td>
        </tr>
        """
        table_rows.append(row_html)

    # Overall Summary Row Percentages
    tot_qa_rate = (tot_qa_app / tot_apps * 100) if tot_apps > 0 else 0.0
    tot_live_conv = (tot_live / tot_apps * 100) if tot_apps > 0 else 0.0

    tot_qa_pill = f'<span class="pill pill-green">{tot_qa_rate:.1f}%</span>' if tot_qa_rate >= 65 else f'<span class="pill pill-yellow">{tot_qa_rate:.1f}%</span>'
    tot_conv_pill = f'<span class="pill pill-green">{tot_live_conv:.1f}%</span>' if tot_live_conv >= 14 else f'<span class="pill pill-yellow">{tot_live_conv:.1f}%</span>'

    summary_row_html = f"""
    <tr class="tr-total">
        <td class="td-exec">TOTAL / AVERAGE</td>
        <td class="td-bold">{tot_apps}</td>
        <td>{tot_qa_app}</td>
        <td>{tot_qa_pill}</td>
        <td>{tot_comm}</td>
        <td>{tot_live}</td>
        <td>{tot_conv_pill}</td>
    </tr>
    """

    # Assemble Full Styled HTML Table
    table_html = f"""
    <div class="sparta-table-container">
        <table class="sparta-table">
            <thead>
                <tr>
                    <th class="th-exec">SALES EXECUTIVE</th>
                    <th class="th-apps">APPLICATIONS</th>
                    <th class="th-qa-app">QA APPROVED</th>
                    <th class="th-qa-rate">QA PASS RATE %</th>
                    <th class="th-comm">COMMITTED REM.</th>
                    <th class="th-live">LIVE</th>
                    <th class="th-conv">LIVE CONVERSION %</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
                {summary_row_html}
            </tbody>
        </table>
    </div>
    """

    st.markdown(table_html, unsafe_allow_html=True)

else:
    st.info("No Advisor records found for the selected filter.")

# ==========================================================
# KPI DEBUG & STATUS BREAKDOWN DRILLDOWN
# ==========================================================

st.divider()

with st.expander("🔍 KPI Status Breakdown & Mapping Inspector", expanded=False):
    st.markdown("### Raw vs Cleaned Status Audit")
    
    col_debug1, col_debug2, col_debug3 = st.columns(3)
    
    with col_debug1:
        st.subheader("1. Quality Status Breakdown")
        q_cols = [c for c in ["Quality Status", "Quality Status Clean"] if c in master_df.columns]
        if q_cols:
            q_breakdown = (
                master_df.groupby(q_cols, dropna=False)
                .size()
                .reset_index(name="Record Count")
                .sort_values(by="Record Count", ascending=False)
            )
            st.dataframe(q_breakdown, use_container_width=True, hide_index=True)

    with col_debug2:
        st.subheader("2. Welcome Status Breakdown")
        w_cols = [c for c in ["Welcome Status", "Welcome Status Clean"] if c in master_df.columns]
        if w_cols:
            w_breakdown = (
                master_df.groupby(w_cols, dropna=False)
                .size()
                .reset_index(name="Record Count")
                .sort_values(by="Record Count", ascending=False)
            )
            st.dataframe(w_breakdown, use_container_width=True, hide_index=True)

    with col_debug3:
        st.subheader("3. Portal / Live Status Breakdown")
        p_cols = [c for c in ["Portal Status", "Portal Status Clean"] if c in filtered_portal_df.columns]
        if p_cols:
            p_breakdown = (
                filtered_portal_df.groupby(p_cols, dropna=False)
                .size()
                .reset_index(name="Record Count")
                .sort_values(by="Record Count", ascending=False)
            )
            st.dataframe(p_breakdown, use_container_width=True, hide_index=True)

    st.divider()

    total_apps = len(master_df)
    matched_apps = master_df["Portal Status"].notna().sum() if "Portal Status" in master_df.columns else 0
    unmatched_apps = total_apps - matched_apps

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Applications (Filtered)", f"{total_apps:,}")
    m_col2.metric("Matched in Sparta2 (Portal)", f"{matched_apps:,}")
    m_col3.metric(
        "Unmatched / Missing in Sparta2", 
        f"{unmatched_apps:,}", 
        delta="Not in Portal" if unmatched_apps > 0 else "100% Matched",
        delta_color="inverse" if unmatched_apps > 0 else "normal"
    )

# Cleanup temporary datetime parse columns after calculations and preview
if "Sale Date Clean" in master_df.columns:
    master_df = master_df.drop(columns=["Sale Date Clean"])
if "Sale Date Clean" in filtered_portal_df.columns:
    filtered_portal_df = filtered_portal_df.drop(columns=["Sale Date Clean"])

# ==========================================================
# DATA PREVIEW
# ==========================================================

st.divider()
st.header("📂 Data Preview")

tab1, tab2, tab3 = st.tabs([
    "Applications",
    "Portal",
    "Master Dataset"
])

# Clean sparta preview copy
preview_sparta = sparta_df.drop(columns=["Sale Date Clean"]) if "Sale Date Clean" in sparta_df.columns else sparta_df
filtered_sparta = preview_sparta[
    (sparta_df["Sale Date Clean"].dt.date >= start_date) & 
    (sparta_df["Sale Date Clean"].dt.date <= end_date)
] if "Sale Date Clean" in sparta_df.columns and start_date <= end_date else preview_sparta

preview_portal = sparta2_df.drop(columns=["Sale Date Clean"]) if "Sale Date Clean" in sparta2_df.columns else sparta2_df

with tab1:
    st.caption(f"{len(filtered_sparta):,} records (Filtered)")
    st.dataframe(
        filtered_sparta,
        use_container_width=True,
        height=500,
        hide_index=True
    )

with tab2:
    st.caption(f"{len(preview_portal):,} records")
    st.dataframe(
        preview_portal,
        use_container_width=True,
        height=500,
        hide_index=True
    )

with tab3:
    st.caption(f"{len(master_df):,} merged records (Filtered)")
    st.dataframe(
        master_df,
        use_container_width=True,
        height=600,
        hide_index=True
    )

# ==========================================================
# FOOTER
# ==========================================================

st.divider()

st.success("✅ Data loaded successfully")

st.caption(
    f"Dashboard refreshed at "
    f"{datetime.now().strftime('%d %b %Y %H:%M:%S')}"
)
