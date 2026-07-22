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

# Custom CSS matching the image style exactly
st.markdown("""
<style>
    /* CSS Grid Container to enforce true horizontal flex layout across 11 tiles */
    .kpi-row {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
        width: 100% !important;
        margin-bottom: 15px !important;
    }
    .kpi-card-styled {
        flex: 1 1 0 !important;
        min-width: 0 !important;
        background-color: #ffffff !important;
        border-radius: 8px !important;
        padding: 10px 4px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
        text-align: center !important;
        height: 88px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        box-sizing: border-box !important;
    }
    
    /* Category Top Borders matching image style */
    .border-overview { border-top: 4px solid #4f46e5 !important; } /* Indigo/Blue */
    .border-quality  { border-top: 4px solid #10b981 !important; } /* Emerald Green */
    .border-welcome  { border-top: 4px solid #f59e0b !important; } /* Amber/Yellow */
    .border-portal   { border-top: 4px solid #0d9488 !important; } /* Teal */

    .kpi-title-styled {
        font-size: 0.58rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        color: #64748b !important;
        letter-spacing: 0.3px !important;
        margin-bottom: 3px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        width: 100% !important;
    }
    .kpi-value-styled {
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        line-height: 1.0 !important;
        margin-bottom: 4px !important;
    }
    .kpi-subtext-styled {
        font-size: 0.62rem !important;
        font-weight: 700 !important;
        line-height: 1 !important;
        white-space: nowrap !important;
    }
    
    /* Subtext colors */
    .text-overview { color: #4f46e5 !important; }
    .text-quality  { color: #059669 !important; }
    .text-welcome  { color: #d97706 !important; }
    .text-portal   { color: #0d9488 !important; }
    .text-red      { color: #dc2626 !important; }
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

def render_kpi_card_html(title, value, subtext, border_class, text_class):
    return f"""
    <div class="kpi-card-styled {border_class}">
        <div class="kpi-title-styled" title="{title}">{title}</div>
        <div class="kpi-value-styled">{value:,}</div>
        <div class="kpi-subtext-styled {text_class}">{subtext}</div>
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
# TOP KPI SECTION (MATCHING IMAGE STYLING IN 1 ROW)
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

# 11 Card Definitions matching the visual style
card_definitions = [
    ("Applications", total_applications, "100% Pipeline Base", "border-overview", "text-overview"),
    ("Quality Approved", q_approved, f"{get_pct(q_approved, total_applications)} Qualification Rate", "border-quality", "text-quality"),
    ("Quality Rework", q_rework, f"{get_pct(q_rework, total_applications)} In Rework", "border-quality", "text-welcome"),
    ("Quality Cancelled", q_cancelled, f"{get_pct(q_cancelled, total_applications)} Rejected", "border-quality", "text-red"),
    ("Welcome Done", wc_done, f"{get_pct(wc_done, total_applications)} Completed", "border-welcome", "text-welcome"),
    ("Welcome Cancel", wc_cancelled, f"{get_pct(wc_cancelled, total_applications)} Cancelled", "border-welcome", "text-red"),
    ("Welcome Pend.", wc_pending, f"{get_pct(wc_pending, total_applications)} Pending", "border-welcome", "text-welcome"),
    ("Live Deals", portal_live, f"{get_pct(portal_live, total_applications)} Final Conversion", "border-portal", "text-portal"),
    ("Committed Rem.", portal_committed, f"{get_pct(portal_committed, total_applications)} In-Pipeline", "border-portal", "text-portal"),
    ("Comm. Cancel", portal_cancelled, f"{get_pct(portal_cancelled, total_applications)} Churned", "border-portal", "text-red"),
    ("Comm. Pend.", portal_pending, f"{get_pct(portal_pending, total_applications)} Pending Action", "border-portal", "text-portal")
]

# Generate single row wrapper with all 11 cards inside
cards_html = "".join([render_kpi_card_html(*config) for config in card_definitions])
row_wrapper = f'<div class="kpi-row">{cards_html}</div>'

st.markdown(row_wrapper, unsafe_allow_html=True)


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
