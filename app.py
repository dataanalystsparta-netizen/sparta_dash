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

# Custom CSS for Dynamic Card Colors
st.markdown("""
<style>
    /* Base Metric Card Styling */
    [data-testid="stMetric"] {
        border-radius: 6px !important;
        padding: 8px 6px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
        border: 1px solid #cbd5e1 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.62rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        color: #1e293b !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
        font-weight: 800 !important;
        color: #0f172a !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.65rem !important;
        font-weight: 700 !important;
    }

    /* Col 1: Applications (Blue) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] {
        background-color: #eff6ff !important;
        border-top: 4px solid #2563eb !important;
    }

    /* Cols 2, 5, 8: Approved / Passed / Live (Green) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(8) [data-testid="stMetric"] {
        background-color: #f0fdf4 !important;
        border-top: 4px solid #16a34a !important;
    }

    /* Cols 3, 7, 9, 11: Rework / Pending (Yellow/Amber) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(7) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(9) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(11) [data-testid="stMetric"] {
        background-color: #fefce8 !important;
        border-top: 4px solid #ca8a04 !important;
    }

    /* Cols 4, 6, 10: Cancelled / Rejected (Red) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(6) [data-testid="stMetric"],
    div[data-testid="stHorizontalBlock"] > div:nth-child(10) [data-testid="stMetric"] {
        background-color: #fef2f2 !important;
        border-top: 4px solid #dc2626 !important;
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
# HELPER FUNCTIONS
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
# TOP KPI SECTION (11 NATIVE METRICS - COLOR CODED)
# ==========================================================

st.subheader("📌 Key Performance Indicators")

def count_status(df, column, values):
    if column not in df.columns:
        return 0
    return df[column].astype(str).str.strip().str.lower().isin([v.lower() for v in values]).sum()

def get_pct(part, total):
    if total == 0:
        return "0.0%"
    return f"{(part / total * 100):.1f}%"

# Metrics Calculations
total_applications = len(master_df)

q_approved = count_status(master_df, "Quality Status", ["Approved", "Pass", "Passed"])
q_rework = count_status(master_df, "Quality Status", ["Rework", "Pending Rework"])
q_cancelled = count_status(master_df, "Quality Status", ["Cancelled", "Cancel", "Rejected"])

wc_done = count_status(master_df, "Welcome Status", ["Done", "Passed", "Completed", "WC Done"])
wc_cancelled = count_status(master_df, "Welcome Status", ["Cancelled", "Cancel", "Rejected"])
wc_pending = count_status(master_df, "Welcome Status", ["Pending", "In Progress", ""])

portal_live = count_status(master_df, "Portal Status", ["Live", "Connected"])
portal_committed = count_status(master_df, "Portal Status", ["Committed", "Order Placed"])
portal_cancelled = count_status(master_df, "Portal Status", ["Cancelled", "Cancel", "Rejected"])
portal_pending = count_status(master_df, "Portal Status", ["Pending", "In Progress", ""])

# Define 11 equal-width columns
cols = st.columns(11)

# 1. Base (Blue)
with cols[0]:
    st.metric(label="Applications", value=f"{total_applications:,}", delta="100% Base")

# 2. QA Approved (Green)
with cols[1]:
    st.metric(label="QA Approved", value=f"{q_approved:,}", delta=get_pct(q_approved, total_applications))

# 3. QA Rework (Yellow)
with cols[2]:
    st.metric(label="QA Rework", value=f"{q_rework:,}", delta=get_pct(q_rework, total_applications))

# 4. QA Cancelled (Red)
with cols[3]:
    st.metric(label="QA Cancelled", value=f"{q_cancelled:,}", delta=get_pct(q_cancelled, total_applications), delta_color="inverse")

# 5. Welcome Done (Green)
with cols[4]:
    st.metric(label="Welcome Done", value=f"{wc_done:,}", delta=get_pct(wc_done, total_applications))

# 6. Welcome Cancel (Red)
with cols[5]:
    st.metric(label="Welcome Cancel", value=f"{wc_cancelled:,}", delta=get_pct(wc_cancelled, total_applications), delta_color="inverse")

# 7. Welcome Pending (Yellow)
with cols[6]:
    st.metric(label="Welcome Pend.", value=f"{wc_pending:,}", delta=get_pct(wc_pending, total_applications))

# 8. Live Deals (Green)
with cols[7]:
    st.metric(label="Live Deals", value=f"{portal_live:,}", delta=get_pct(portal_live, total_applications))

# 9. Committed Rem. (Yellow)
with cols[8]:
    st.metric(label="Committed Rem.", value=f"{portal_committed:,}", delta=get_pct(portal_committed, total_applications))

# 10. Comm. Cancel (Red)
with cols[9]:
    st.metric(label="Comm. Cancel", value=f"{portal_cancelled:,}", delta=get_pct(portal_cancelled, total_applications), delta_color="inverse")

# 11. Comm. Pending (Yellow)
with cols[10]:
    st.metric(label="Comm. Pend.", value=f"{portal_pending:,}", delta=get_pct(portal_pending, total_applications))


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
