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

# Custom CSS for Individual KPI Cards
st.markdown("""
<style>
    .single-kpi-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 14px 18px;
        border: 1px solid #e9ecef;
        border-left: 5px solid #007bff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.04);
        margin-bottom: 12px;
    }
    .kpi-title {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #6c757d;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1e293b;
        margin-top: 4px;
    }
    .kpi-category {
        font-size: 0.72rem;
        font-weight: 500;
        color: #a0aec0;
        margin-bottom: 2px;
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

# Helper for card HTML rendering
def render_kpi(category, title, value, border_color="#007bff"):
    return f"""
    <div class="single-kpi-card" style="border-left-color: {border_color};">
        <div class="kpi-category">{category}</div>
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value:,}</div>
    </div>
    """

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
# SEPARATE KPI CARDS SECTION
# ==========================================================

st.subheader("📌 Key Performance Indicators")

# Helper for case-insensitive exact matching
def count_status(df, column, values):
    if column not in df.columns:
        return 0
    return df[column].astype(str).str.strip().str.lower().isin([v.lower() for v in values]).sum()

# Calculations
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

# --- ROW 1: Applications & Quality ---
r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

with r1_col1:
    st.markdown(render_kpi("Overview", "Total Applications", total_applications, "#0d6efd"), unsafe_allow_html=True)

with r1_col2:
    st.markdown(render_kpi("Quality", "Approved", q_approved, "#198754"), unsafe_allow_html=True)

with r1_col3:
    st.markdown(render_kpi("Quality", "Rework", q_rework, "#ffc107"), unsafe_allow_html=True)

with r1_col4:
    st.markdown(render_kpi("Quality", "Cancelled", q_cancelled, "#dc3545"), unsafe_allow_html=True)

# --- ROW 2: Welcome Call ---
r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

with r2_col1:
    st.markdown(render_kpi("Welcome Call", "Done", wc_done, "#198754"), unsafe_allow_html=True)

with r2_col2:
    st.markdown(render_kpi("Welcome Call", "Cancelled", wc_cancelled, "#dc3545"), unsafe_allow_html=True)

with r2_col3:
    st.markdown(render_kpi("Welcome Call", "Pending", wc_pending, "#0dcaf0"), unsafe_allow_html=True)

with r2_col4:
    st.empty()  # Blank space for layout alignment

# --- ROW 3: Committed / Portal Lifecycle ---
r3_col1, r3_col2, r3_col3, r3_col4 = st.columns(4)

with r3_col1:
    st.markdown(render_kpi("Committed", "Live", portal_live, "#198754"), unsafe_allow_html=True)

with r3_col2:
    st.markdown(render_kpi("Committed", "Committed", portal_committed, "#0d6efd"), unsafe_allow_html=True)

with r3_col3:
    st.markdown(render_kpi("Committed", "Cancelled", portal_cancelled, "#dc3545"), unsafe_allow_html=True)

with r3_col4:
    st.markdown(render_kpi("Committed", "Pending", portal_pending, "#0dcaf0"), unsafe_allow_html=True)


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
