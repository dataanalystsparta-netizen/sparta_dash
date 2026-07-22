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

# Custom CSS for Modern KPI Cards
st.markdown("""
<style>
    .kpi-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px 20px;
        border-left: 5px solid #007bff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .kpi-card-title {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #6c757d;
        letter-spacing: 0.5px;
    }
    .kpi-card-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
        margin-top: 5px;
    }
    .kpi-subtext {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 8px;
    }
    .stat-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 4px;
    }
    .badge-success { background-color: #d1e7dd; color: #0f5132; }
    .badge-warning { background-color: #fff3cd; color: #664d03; }
    .badge-danger { background-color: #f8d7da; color: #842029; }
    .badge-info { background-color: #cff4fc; color: #055160; }
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

@st.cache_resource(show_spinner=False)
def get_google_service():

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    service = build(
        "sheets",
        "v4",
        credentials=credentials
    )

    return service

# ==========================================================
# GENERIC SHEET LOADER
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sheet(sheet_name):

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

    # Ensure every row has the same number of columns
    max_cols = len(headers)

    cleaned_rows = []

    for row in rows:

        if len(row) < max_cols:
            row.extend([""] * (max_cols - len(row)))

        elif len(row) > max_cols:
            row = row[:max_cols]

        cleaned_rows.append(row)

    df = pd.DataFrame(
        cleaned_rows,
        columns=headers
    )

    return df

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

    # Clean phone numbers

    df["Telephone No."] = clean_phone(df["Telephone No."])

    # Parse dates

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

    # Remove duplicate phone numbers from portal sheet
    # (keep the latest record if duplicates exist)

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

    # LEFT JOIN
    master = apps.merge(
        portal,
        on="Telephone No.",
        how="left",
        suffixes=("", "_portal")
    )

    return master


# ==========================================================
# CREATE MASTER DF
# ==========================================================

master_df = build_master_dataframe(
    sparta_df,
    sparta2_df
)

# ==========================================================
# TOP KPI SECTION
# ==========================================================

st.subheader("📌 Key Performance Indicators")

# Calculate KPI Metrics cleanly from master_df
total_applications = len(master_df)

# Helper for case-insensitive exact matching
def count_status(df, column, values):
    if column not in df.columns:
        return 0
    return df[column].astype(str).str.strip().str.lower().isin([v.lower() for v in values]).sum()

# Quality Metrics
q_approved = count_status(master_df, "Quality Status", ["Approved", "Pass", "Passed"])
q_rework = count_status(master_df, "Quality Status", ["Rework", "Pending Rework"])
q_cancelled = count_status(master_df, "Quality Status", ["Cancelled", "Cancel", "Rejected"])

# Welcome Call Metrics
wc_done = count_status(master_df, "Welcome Status", ["Done", "Passed", "Completed", "WC Done"])
wc_cancelled = count_status(master_df, "Welcome Status", ["Cancelled", "Cancel", "Rejected"])
wc_pending = count_status(master_df, "Welcome Status", ["Pending", "In Progress", ""])

# Committed / Portal Metrics
portal_live = count_status(master_df, "Portal Status", ["Live", "Connected"])
portal_cancelled = count_status(master_df, "Portal Status", ["Cancelled", "Cancel", "Rejected"])
portal_committed = count_status(master_df, "Portal Status", ["Committed", "Order Placed"])
portal_pending = count_status(master_df, "Portal Status", ["Pending", "In Progress", ""])

# Render 4 Cards in Row
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #007bff;">
        <div class="kpi-card-title">Total Applications</div>
        <div class="kpi-card-value">{total_applications:,}</div>
        <div class="kpi-subtext">Total submitted leads</div>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #198754;">
        <div class="kpi-card-title">Quality Breakdown</div>
        <div class="kpi-card-value">{q_approved:,} <span style="font-size: 0.9rem; font-weight: normal;">Approved</span></div>
        <div class="kpi-subtext">
            <span class="stat-badge badge-warning">Rework: {q_rework:,}</span>
            <span class="stat-badge badge-danger">Cancelled: {q_cancelled:,}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #ffc107;">
        <div class="kpi-card-title">Welcome Call</div>
        <div class="kpi-card-value">{wc_done:,} <span style="font-size: 0.9rem; font-weight: normal;">Done</span></div>
        <div class="kpi-subtext">
            <span class="stat-badge badge-danger">Cancelled: {wc_cancelled:,}</span>
            <span class="stat-badge badge-info">Pending: {wc_pending:,}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with kpi4:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #0dcaf0;">
        <div class="kpi-card-title">Committed Lifecycle</div>
        <div class="kpi-card-value">{portal_live:,} <span style="font-size: 0.9rem; font-weight: normal;">Live</span></div>
        <div class="kpi-subtext">
            <span class="stat-badge badge-success">Committed: {portal_committed:,}</span>
            <span class="stat-badge badge-danger">Cancelled: {portal_cancelled:,}</span>
            <span class="stat-badge badge-info">Pending: {portal_pending:,}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

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
