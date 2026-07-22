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

# Custom CSS for Native st.metric Styling matching your card design + soft background tints
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

    /* TOP ACCENT STRIPS + SOFT LIGHT BACKGROUNDS BY COLUMN (1 to 12) */
    
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

    /* Col 9: Live Deals (Soft Teal) */
    [data-testid="stColumn"]:nth-child(9) [data-testid="stMetric"] { 
        border-top: 4px solid #14b8a6 !important; 
        background-color: #f0fdfa !important; 
    }
    [data-testid="stColumn"]:nth-child(9) [data-testid="stMetricDelta"] { color: #0f766e !important; }

    /* Col 10: Committed Rem. (Soft Yellow) */
    [data-testid="stColumn"]:nth-child(10) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; 
        background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(10) [data-testid="stMetricDelta"] { color: #b45309 !important; }

    /* Col 11: Comm. Cancel (Soft Red) */
    [data-testid="stColumn"]:nth-child(11) [data-testid="stMetric"] { 
        border-top: 4px solid #ef4444 !important; 
        background-color: #fef2f2 !important; 
    }
    [data-testid="stColumn"]:nth-child(11) [data-testid="stMetricDelta"] { color: #b91c1c !important; }

    /* Col 12: Comm. Pend. (Soft Yellow) */
    [data-testid="stColumn"]:nth-child(12) [data-testid="stMetric"] { 
        border-top: 4px solid #f59e0b !important; 
        background-color: #fefce8 !important; 
    }
    [data-testid="stColumn"]:nth-child(12) [data-testid="stMetricDelta"] { color: #b45309 !important; }
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
        .str.strip()
    )

def parse_date(series):
    return pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True
    )

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
    
    # Cancelled (Hold, Duplicate, Reject, Cancel, Inbound, N/A, Rec in accessible, etc.)
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
    
    # Cancelled (Rejected, Hold, Cancel)
    if any(k in val_str for k in ["cancel", "reject", "hold"]):
        return "Cancelled"
    
    # Pending (Pending, Follow up, Paperwork, Wrong no, Ringing)
    if any(k in val_str for k in ["pending", "follow", "paperwork", "wrong", "ring"]):
        return "Pending"
    
    return "Pending"

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

    df = df.rename(columns=rename_map)

    keep_columns = [
        "Advisor",
        "Sale Date",
        "Customer Name",
        "Telephone No.",
        "Quality Date",
        "Quality Status",
        "Quality Remarks",
        "Welcome Remarks",
        "Welcome Status",
        "Welcome Cancellation",
        "Welcome Date",
        "Provisioning Status",
        "Provisioning Date",
        "Current Provider",
        "Package",
        "Dashboard Month",
        "Standardized Date"
    ]

    df = df[keep_columns].copy()
    df["Telephone No."] = clean_phone(df["Telephone No."])

    date_columns = [
        "Sale Date",
        "Quality Date",
        "Welcome Date",
        "Provisioning Date",
        "Standardized Date"
    ]

    for col in date_columns:
        df[col] = parse_date(df[col])

    # Standardize Quality and Welcome Statuses using clean categorization logic
    df["Quality Status Clean"] = df["Quality Status"].apply(categorize_quality_status)
    df["Welcome Status Clean"] = df["Welcome Status"].apply(categorize_welcome_status)

    return df

# ==========================================================
# LOAD PORTAL SHEET
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sparta2():

    df = load_sheet(LIVE_SHEET)

    rename_map = {
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

    df = df.rename(columns=rename_map)

    keep_columns = [
        "Telephone No.",
        "Live Date",
        "Portal Status",
        "Letter Status",
        "Call Status",
        "Comments",
        "Voice of Customer",
        "Portal Cancellation",
        "Dashboard Month",
        "Standardized Date"
    ]

    df = df[keep_columns].copy()
    df["Telephone No."] = clean_phone(df["Telephone No."])
    df["Live Date"] = parse_date(df["Live Date"])
    df["Standardized Date"] = parse_date(df["Standardized Date"])

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

    if "Live Date" in portal.columns:
        portal = portal.sort_values(
            by="Live Date",
            ascending=False,
            na_position="last"
        )

    portal = portal.drop_duplicates(
        subset="Telephone No.",
        keep="first"
    )

    master = apps.merge(
        portal,
        on="Telephone No.",
        how="left",
        suffixes=("", "_portal")
    )

    return master

master_df = build_master_dataframe(
    sparta_df,
    sparta2_df
)

# ==========================================================
# TOP KPI SECTION (ST.METRIC 12 COLUMNS)
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

# Calculations
total_applications = len(master_df)

q_approved = count_status(master_df, "Quality Status Clean", "Approved")
q_rework = count_status(master_df, "Quality Status Clean", "Rework")
q_cancelled = count_status(master_df, "Quality Status Clean", "Cancelled")
q_pending = count_status(master_df, "Quality Status Clean", "Pending")

wc_done = count_status(master_df, "Welcome Status Clean", "Done")
wc_cancelled = count_status(master_df, "Welcome Status Clean", "Cancelled")
wc_pending = count_status(master_df, "Welcome Status Clean", "Pending")

portal_live = (master_df["Portal Status"].astype(str).str.strip().str.lower().isin(["live", "connected"])).sum()
portal_committed = (master_df["Portal Status"].astype(str).str.strip().str.lower().isin(["committed", "order placed"])).sum()
portal_cancelled = (master_df["Portal Status"].astype(str).str.strip().str.lower().isin(["cancelled", "cancel", "rejected"])).sum()
portal_pending = (master_df["Portal Status"].astype(str).str.strip().str.lower().isin(["pending", "in progress", ""])).sum()

# Define 12 Columns
cols = st.columns(12)

# Card Data Definition: (Label, Count Value, Delta Subtext String)
kpis = [
    ("Applications", total_applications, "100% Base"),
    ("Quality Approved", q_approved, f"{get_pct(q_approved, total_applications)} Qualified"),
    ("Quality Rework", q_rework, f"{get_pct(q_rework, total_applications)} In Rework"),
    ("Quality Cancelled", q_cancelled, f"{get_pct(q_cancelled, total_applications)} Rejected"),
    ("Quality Pending", q_pending, f"{get_pct(q_pending, total_applications)} Pending"),
    ("Welcome Done", wc_done, f"{get_pct(wc_done, total_applications)} Completed"),
    ("Welcome Cancelled", wc_cancelled, f"{get_pct(wc_cancelled, total_applications)} Cancelled"),
    ("Welcome Pending", wc_pending, f"{get_pct(wc_pending, total_applications)} Pending"),
    ("Live Deals", portal_live, f"{get_pct(portal_live, total_applications)} Converted"),
    ("Committed Rem.", portal_committed, f"{get_pct(portal_committed, total_applications)} Pipeline"),
    ("Comm. Cancelled", portal_cancelled, f"{get_pct(portal_cancelled, total_applications)} Churned"),
    ("Comm. Pending", portal_pending, f"{get_pct(portal_pending, total_applications)} Pending")
]

# Render through st.metric
for col, (label, val, delta_sub) in zip(cols, kpis):
    with col:
        st.metric(
            label=label,
            value=f"{val:,}",
            delta=delta_sub
        )

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

with tab1:
    st.caption(f"{len(sparta_df):,} records")
    st.dataframe(
        sparta_df,
        use_container_width=True,
        height=500,
        hide_index=True
    )

with tab2:
    st.caption(f"{len(sparta2_df):,} records")
    st.dataframe(
        sparta2_df,
        use_container_width=True,
        height=500,
        hide_index=True
    )

with tab3:
    st.caption(f"{len(master_df):,} merged records")
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
