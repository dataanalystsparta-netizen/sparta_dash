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

# Custom CSS for Single-Line Flexbox Strip
st.markdown("""
<style>
    .kpi-row-container {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
        width: 100% !important;
        overflow-x: auto !important;
        padding: 4px 0px 10px 0px !important;
    }
    .kpi-tile-single {
        flex: 1 1 0 !important;
        min-width: 90px !important;
        background-color: #ffffff !important;
        border-radius: 6px !important;
        padding: 6px 2px !important;
        border: 1px solid #e2e8f0 !important;
        border-top: 3px solid #2563eb !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
        text-align: center !important;
        height: 74px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        box-sizing: border-box !important;
    }
    .kpi-tile-title {
        font-size: 0.55rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        color: #64748b !important;
        letter-spacing: 0.2px !important;
        margin-bottom: 2px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        width: 100% !important;
    }
    .kpi-tile-value {
        font-size: 1.1rem !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        line-height: 1.1 !important;
        margin-bottom: 2px !important;
    }
    .kpi-tile-subtext {
        font-size: 0.6rem !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        white-space: nowrap !important;
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

def make_kpi_card_html(title, value, subtext, color="#2563eb"):
    return f"""<div class="kpi-tile-single" style="border-top-color: {color};">
        <div class="kpi-tile-title" title="{title}">{title}</div>
        <div class="kpi-tile-value">{value:,}</div>
        <div class="kpi-tile-subtext" style="color: {color};">{subtext}</div>
    </div>"""

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
# TOP KPI SECTION (SINGLE LINE HTML FIX)
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

# Category Colors
COLOR_OVERVIEW = "#2563eb"   # Blue
COLOR_QUALITY = "#059669"    # Green
COLOR_WELCOME = "#d97706"    # Amber
COLOR_COMMITTED = "#0d9488"  # Teal

# Generate all tile strings
cards_list = [
    make_kpi_card_html("Applications", total_applications, "100% Base", COLOR_OVERVIEW),
    make_kpi_card_html("Quality Approved", q_approved, f"{get_pct(q_approved, total_applications)} Qualified", COLOR_QUALITY),
    make_kpi_card_html("Quality Rework", q_rework, f"{get_pct(q_rework, total_applications)} In Rework", COLOR_QUALITY),
    make_kpi_card_html("Quality Cancelled", q_cancelled, f"{get_pct(q_cancelled, total_applications)} Rejected", COLOR_QUALITY),
    make_kpi_card_html("Welcome Done", wc_done, f"{get_pct(wc_done, total_applications)} Completed", COLOR_WELCOME),
    make_kpi_card_html("Welcome Cancelled", wc_cancelled, f"{get_pct(wc_cancelled, total_applications)} Cancelled", COLOR_WELCOME),
    make_kpi_card_html("Welcome Pending", wc_pending, f"{get_pct(wc_pending, total_applications)} Pending", COLOR_WELCOME),
    make_kpi_card_html("Live Deals", portal_live, f"{get_pct(portal_live, total_applications)} Converted", COLOR_COMMITTED),
    make_kpi_card_html("Committed Rem.", portal_committed, f"{get_pct(portal_committed, total_applications)} In-Pipeline", COLOR_COMMITTED),
    make_kpi_card_html("Committed Cancelled", portal_cancelled, f"{get_pct(portal_cancelled, total_applications)} Churned", COLOR_COMMITTED),
    make_kpi_card_html("Committed Pending", portal_pending, f"{get_pct(portal_pending, total_applications)} Pending Action", COLOR_COMMITTED)
]

# Joined inside a single HTML wrapper block
kpis_html_wrapper = f'<div class="kpi-row-container">{"".join(cards_list)}</div>'

# Render directly
st.markdown(kpis_html_wrapper, unsafe_allow_html=True)


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
