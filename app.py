# ==========================================================
# SPARTA SALES DASHBOARD V2
# Part 1 - Imports + Google Sheets Connection
# ==========================================================

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
# DATA DIAGNOSTICS
# ==========================================================

st.subheader("📋 Data Diagnostics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Applications",
        f"{len(sparta_df):,}"
    )

with col2:
    st.metric(
        "Portal Records",
        f"{len(sparta2_df):,}"
    )

with col3:
    st.metric(
        "Master Records",
        f"{len(master_df):,}"
    )

with col4:
    live_count = master_df["Portal Status"].notna().sum()

    st.metric(
        "Matched Portal Records",
        f"{live_count:,}"
    )


st.divider()


# ==========================================================
# DATA QUALITY CHECKS
# ==========================================================

quality_col1, quality_col2 = st.columns(2)

with quality_col1:

    duplicate_apps = (
        sparta_df["Telephone No."]
        .duplicated()
        .sum()
    )

    duplicate_portal = (
        sparta2_df["Telephone No."]
        .duplicated()
        .sum()
    )

    st.write("### Phone Number Checks")

    st.write(f"Duplicate Numbers (Applications): **{duplicate_apps:,}**")

    st.write(f"Duplicate Numbers (Portal): **{duplicate_portal:,}**")

    st.write(f"Unique Advisors: **{master_df['Advisor'].nunique()}**")

with quality_col2:

    unmatched = master_df["Portal Status"].isna().sum()

    quality_counts = (
        master_df["Quality Status"]
        .fillna("Blank")
        .value_counts()
    )

    st.write("### Lifecycle Checks")

    st.write(f"Applications without Portal Record: **{unmatched:,}**")

    st.write("")

    st.write("Quality Status Distribution")

    st.dataframe(
        quality_counts.rename("Count"),
        use_container_width=True
    )


st.divider()


# ==========================================================
# COLUMN INFORMATION
# ==========================================================

with st.expander("📄 Master Data Columns"):

    column_df = pd.DataFrame({

        "Column": master_df.columns,
        "Data Type": master_df.dtypes.astype(str)

    })

    st.dataframe(
        column_df,
        use_container_width=True,
        hide_index=True
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



# ==========================================================
# GLOBAL FILTERS
# ==========================================================

st.sidebar.header("🔍 Dashboard Filters")

# -------------------------------
# DATE FILTER
# -------------------------------

min_date = master_df["Sale Date"].min()
max_date = master_df["Sale Date"].max()

date_range = st.sidebar.date_input(
    "Sale Date",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# -------------------------------
# ADVISOR FILTER
# -------------------------------

advisor_list = sorted(
    master_df["Advisor"]
    .dropna()
    .unique()
    .tolist()
)

selected_advisors = st.sidebar.multiselect(
    "Advisor",
    advisor_list,
    default=advisor_list
)

# -------------------------------
# QUALITY FILTER
# -------------------------------

quality_list = sorted(
    master_df["Quality Status"]
    .fillna("Blank")
    .unique()
    .tolist()
)

selected_quality = st.sidebar.multiselect(
    "Quality Status",
    quality_list,
    default=quality_list
)

# -------------------------------
# WELCOME FILTER
# -------------------------------

welcome_list = sorted(
    master_df["Welcome Status"]
    .fillna("Blank")
    .unique()
    .tolist()
)

selected_welcome = st.sidebar.multiselect(
    "Welcome Status",
    welcome_list,
    default=welcome_list
)

# -------------------------------
# PORTAL FILTER
# -------------------------------

portal_list = sorted(
    master_df["Portal Status"]
    .fillna("Blank")
    .unique()
    .tolist()
)

selected_portal = st.sidebar.multiselect(
    "Portal Status",
    portal_list,
    default=portal_list
)

# -------------------------------
# CURRENT PROVIDER
# -------------------------------

provider_list = sorted(
    master_df["Current Provider"]
    .fillna("Blank")
    .unique()
    .tolist()
)

selected_provider = st.sidebar.multiselect(
    "Current Provider",
    provider_list,
    default=provider_list
)

# -------------------------------
# PACKAGE
# -------------------------------

package_list = sorted(
    master_df["Package"]
    .fillna("Blank")
    .unique()
    .tolist()
)

selected_package = st.sidebar.multiselect(
    "Package",
    package_list,
    default=package_list
)


