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

# Custom CSS for Compact Square KPI Cards
st.markdown("""
<style>
    .kpi-tile-square {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 8px 6px;
        border: 1px solid #e2e8f0;
        border-top: 4px solid #2563eb;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        text-align: center;
        margin-bottom: 8px;
        height: 88px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .kpi-tile-title {
        font-size: 0.62rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #64748b;
        letter-spacing: 0.3px;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
    }
    .kpi-tile-value {
        font-size: 1.3rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
        margin-bottom: 2px;
    }
    .kpi-tile-subtext {
        font-size: 0.68rem;
        font-weight: 600;
        line-height: 1;
        white-space: nowrap;
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

# Square Tile HTML Renderer
def render_square_kpi(title, value, subtext, color="#2563eb"):
    return f"""
    <div class="kpi-tile-square" style="border-top-color: {color};">
        <div class="kpi-tile-title" title="{title}">{title}</div>
        <div class="kpi-tile-value">{value:,}</div>
        <div class="kpi-tile-subtext" style="color: {color};">{subtext}</div>
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
# TOP KPI SECTION (COMPACT SQUARE TILES - 6 PER ROW)
# ==========================================================

st.subheader("📌 Key Performance Indicators")

# Helper for case-insensitive exact matching
def count_status(df, column, values):
    if column not in df.columns:
        return 0
    return df[column].astype(str).str.strip().str.lower().isin([v.lower() for v in values]).sum()

def get_pct(part, total):
    if total == 0:
        return "0.0%"
    return f"{(part / total * 100):.1f}%"

# Calculations
total_applications = len(master_df)

# Quality Counts
q_approved = count_status(master_df, "Quality Status", ["Approved", "Pass", "Passed"])
q_rework = count_status(master_df, "Quality Status", ["Rework", "Pending Rework"])
q_cancelled = count_status(master_df, "Quality Status", ["Cancelled", "Cancel", "Rejected"])

# Welcome Call Counts
wc_done = count_status(master_df, "Welcome Status", ["Done", "Passed", "Completed", "WC Done"])
wc_cancelled = count_status(master_df, "Welcome Status", ["Cancelled", "Cancel", "Rejected"])
wc_pending = count_status(master_df, "Welcome Status", ["Pending", "In Progress", ""])

# Committed / Portal Counts
portal_live = count_status(master_df, "Portal Status", ["Live", "Connected"])
portal_committed = count_status(master_df, "Portal Status", ["Committed", "Order Placed"])
portal_cancelled = count_status(master_df, "Portal Status", ["Cancelled", "Cancel", "Rejected"])
portal_pending = count_status(master_df, "Portal Status", ["Pending", "In Progress", ""])

# Category Color Themes
COLOR_OVERVIEW = "#2563eb"   # Blue
COLOR_QUALITY = "#059669"    # Green
COLOR_WELCOME = "#d97706"    # Amber
COLOR_COMMITTED = "#0d9488"  # Teal

# --- ROW 1 (6 Columns) ---
r1_cols = st.columns(6)

with r1_cols[0]:
    st.markdown(render_square_kpi("Applications", total_applications, "100% Base", COLOR_OVERVIEW), unsafe_allow_html=True)

with r1_cols[1]:
    st.markdown(render_square_kpi("Quality Approved", q_approved, f"{get_pct(q_approved, total_applications)} Qualified", COLOR_QUALITY), unsafe_allow_html=True)

with r1_cols[2]:
    st.markdown(render_square_kpi("Quality Rework", q_rework, f"{get_pct(q_rework, total_applications)} In Rework", COLOR_QUALITY), unsafe_allow_html=True)

with r1_cols[3]:
    st.markdown(render_square_kpi("Quality Cancelled", q_cancelled, f"{get_pct(q_cancelled, total_applications)} Rejected", COLOR_QUALITY), unsafe_allow_html=True)

with r1_cols[4]:
    st.markdown(render_square_kpi("Welcome Done", wc_done, f"{get_pct(wc_done, total_applications)} Completed", COLOR_WELCOME), unsafe_allow_html=True)

with r1_cols[5]:
    st.markdown(render_square_kpi("Welcome Cancelled", wc_cancelled, f"{get_pct(wc_cancelled, total_applications)} Cancelled", COLOR_WELCOME), unsafe_allow_html=True)


# --- ROW 2 (6 Columns) ---
r2_cols = st.columns(6)

with r2_cols[0]:
    st.markdown(render_square_kpi("Welcome Pending", wc_pending, f"{get_pct(wc_pending, total_applications)} Pending", COLOR_WELCOME), unsafe_allow_html=True)

with r2_cols[1]:
    st.markdown(render_square_kpi("Live Deals", portal_live, f"{get_pct(portal_live, total_applications)} Converted", COLOR_COMMITTED), unsafe_allow_html=True)

with r2_cols[2]:
    st.markdown(render_square_kpi("Committed Rem.", portal_committed, f"{get_pct(portal_committed, total_applications)} In-Pipeline", COLOR_COMMITTED), unsafe_allow_html=True)

with r2_cols[3]:
    st.markdown(render_square_kpi("Committed Cancelled", portal_cancelled, f"{get_pct(portal_cancelled, total_applications)} Churned", COLOR_COMMITTED), unsafe_allow_html=True)

with r2_cols[4]:
    st.markdown(render_square_kpi("Committed Pending", portal_pending, f"{get_pct(portal_pending, total_applications)} Pending Action", COLOR_COMMITTED), unsafe_allow_html=True)

with r2_cols[5]:
    st.empty()


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
