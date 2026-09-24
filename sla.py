"""
SPARTA PENDING OPERATIONS DASHBOARD
===================================

Separate operational dashboard for tracking CURRENT PENDING SALES.

Queues:
    1. Pending Quality
    2. Pending Welcome Call
    3. Pending Committed Call
    4. Pending Provisioning

IMPORTANT:
    This dashboard deliberately does NOT define an SLA.
    There are no SLA targets, breach calculations, overdue labels,
    scoring systems or performance judgements.

The dashboard simply answers:

    "Which sales are currently pending, and where are they pending?"

Data sources:
    - Google Sheet: Sparta
    - Google Sheet: Sparta2

This is intentionally separate from the main Sparta Sales Dashboard.
"""

# ============================================================
# IMPORTS
# ============================================================

import logging
import re
import time
from datetime import datetime, date
from html import escape
from typing import List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("sparta_pending_dashboard")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)

logger.setLevel(logging.INFO)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Sparta Pending Operations",
    page_icon="⏳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown(
    """
    <style>

    /* --------------------------------------------------------
       GLOBAL
       -------------------------------------------------------- */

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1600px;
    }

    .main-title {
        font-size: 2.05rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.15rem;
        letter-spacing: -0.6px;
    }

    .main-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        margin-bottom: 1.3rem;
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: #0f172a;
        margin-top: 0.5rem;
        margin-bottom: 0.65rem;
    }

    /* --------------------------------------------------------
       KPI CARDS
       -------------------------------------------------------- */

    .pending-card {
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 17px 18px 15px 18px;
        background: #ffffff;
        min-height: 125px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .pending-card:hover {
        box-shadow: 0 5px 16px rgba(15, 23, 42, 0.07);
    }

    .pending-card-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .pending-card-title {
        font-size: 0.72rem;
        font-weight: 800;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.65px;
    }

    .pending-card-icon {
        font-size: 1.35rem;
    }

    .pending-card-number {
        font-size: 2rem;
        font-weight: 850;
        color: #0f172a;
        margin-top: 8px;
        line-height: 1;
    }

    .pending-card-description {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 8px;
    }

    .card-quality {
        border-top: 4px solid #f97316;
    }

    .card-welcome {
        border-top: 4px solid #eab308;
    }

    .card-committed {
        border-top: 4px solid #3b82f6;
    }

    .card-provisioning {
        border-top: 4px solid #8b5cf6;
    }

    .card-total {
        border-top: 4px solid #64748b;
    }

    /* --------------------------------------------------------
       QUEUE BADGES
       -------------------------------------------------------- */

    .queue-badge {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 800;
        white-space: nowrap;
    }

    .queue-quality {
        background: #fff7ed;
        color: #c2410c;
        border: 1px solid #fed7aa;
    }

    .queue-welcome {
        background: #fefce8;
        color: #a16207;
        border: 1px solid #fde68a;
    }

    .queue-committed {
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }

    .queue-provisioning {
        background: #f5f3ff;
        color: #6d28d9;
        border: 1px solid #ddd6fe;
    }

    /* --------------------------------------------------------
       TABLE
       -------------------------------------------------------- */

    .queue-table-wrapper {
        width: 100%;
        overflow: auto;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #ffffff;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
    }

    .queue-table {
        width: 100%;
        border-collapse: collapse;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Roboto,
            Arial,
            sans-serif;
        font-size: 0.84rem;
        background: #ffffff;
    }

    .queue-table th {
        position: sticky;
        top: 0;
        z-index: 5;
        padding: 11px 12px;
        text-align: left;
        font-size: 0.71rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.45px;
        color: #475569;
        background: #f8fafc;
        border-bottom: 2px solid #e2e8f0;
        white-space: nowrap;
        cursor: pointer;
    }

    .queue-table th:hover {
        background: #f1f5f9;
    }

    .queue-table td {
        padding: 10px 12px;
        border-bottom: 1px solid #f1f5f9;
        color: #334155;
        vertical-align: middle;
    }

    .queue-table tr:hover td {
        background: #f8fafc;
    }

    .queue-table td.customer {
        font-weight: 750;
        color: #0f172a;
        white-space: nowrap;
    }

    .queue-table td.phone {
        font-family: monospace;
        font-size: 0.8rem;
        color: #475569;
        white-space: nowrap;
    }

    .queue-table td.date {
        white-space: nowrap;
        color: #475569;
    }

    .queue-table td.status {
        max-width: 260px;
        white-space: normal;
    }

    /* --------------------------------------------------------
       FILTER BOX
       -------------------------------------------------------- */

    .filter-box {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 16px 6px 16px;
        background: #f8fafc;
        margin-bottom: 18px;
    }

    /* --------------------------------------------------------
       EMPTY STATE
       -------------------------------------------------------- */

    .empty-state {
        border: 1px dashed #cbd5e1;
        border-radius: 12px;
        padding: 38px 20px;
        text-align: center;
        background: #f8fafc;
        color: #64748b;
    }

    .empty-state-icon {
        font-size: 2rem;
        margin-bottom: 8px;
    }

    .empty-state-title {
        font-weight: 800;
        color: #334155;
        font-size: 1rem;
    }

    .empty-state-text {
        font-size: 0.82rem;
        margin-top: 4px;
    }

    /* --------------------------------------------------------
       DIVIDER
       -------------------------------------------------------- */

    hr {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 1.4rem 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CONFIGURATION
# ============================================================

SPREADSHEET_ID = st.secrets.get(
    "SPREADSHEET_ID",
    "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ",
)

APPLICATION_SHEET = st.secrets.get(
    "APPLICATION_SHEET",
    "Sparta",
)

LIVE_SHEET = st.secrets.get(
    "LIVE_SHEET",
    "Sparta2",
)

SCOPES: List[str] = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]


# ============================================================
# ADVISOR TAGS
# ============================================================

NEW_ADVISORS = [
    "Aryan",
    "Shivam",
]

CUSTOMER_SERVICE_ADVISORS = [
    "Aman",
    "Ravi Inbound",
    "Santosh Joshi",
    "Vijender",
    "Laxmi Narayan",
    "Alex",
]

LEFT_ADVISORS = [
    "Gaurav",
    "Guru",
    "Niki",
    "Shaheen",
    "Manmeet",
    "Gungun",
    "Rani",
    "Archana",
    "Deepali",
    "Sushanshu",
    "Supreme",
    "Tokivi",
    "Sangeeta",
    "Vijay",
    "Khushbu",
    "Kushal",
    "Nishant",
    "Pawan",
    "Mehak",
    "Khushboo",
    "Ashima",
    "Aarti",
    "Abhay",
    "Diwakar",
    "Manshay",
    "Khusboo",
    "Manmet",
    "Lakshay",
    "Sneha",
    "Swarali",
    "Monica",
    "Paras",
    "Veer",
    "Yash",
    "Sudhanshu",
    "Rishabh",
    "Krrish",
    "Anshu",
    "Edwin",
    "Sravan",
    "Seema",
    "Prateek",
]

NEW_ADVISORS_SET = {
    x.strip().lower() for x in NEW_ADVISORS
}

CS_ADVISORS_SET = {
    x.strip().lower() for x in CUSTOMER_SERVICE_ADVISORS
}

LEFT_ADVISORS_SET = {
    x.strip().lower() for x in LEFT_ADVISORS
}


# ============================================================
# GOOGLE SHEETS CLIENT
# ============================================================

@st.cache_resource
def get_google_service():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError(
            "Missing gcp_service_account in Streamlit secrets."
        )

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )

    service = build(
        "sheets",
        "v4",
        credentials=credentials,
        cache_discovery=False,
    )

    logger.info("Google Sheets client created")

    return service


# ============================================================
# SHEET LOADER
# ============================================================

def load_sheet(
    sheet_name: str,
    max_retries: int = 3,
    backoff: float = 1.0,
) -> pd.DataFrame:

    service = get_google_service()

    for attempt in range(1, max_retries + 1):

        try:

            result = (
                service
                .spreadsheets()
                .values()
                .get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=sheet_name,
                )
                .execute()
            )

            values = result.get("values", [])

            if not values:
                return pd.DataFrame()

            headers = values[0]
            rows = values[1:]

            max_cols = len(headers)

            cleaned_rows = [
                (
                    row + [""] * (max_cols - len(row))
                    if len(row) < max_cols
                    else row[:max_cols]
                )
                for row in rows
            ]

            df = pd.DataFrame(
                cleaned_rows,
                columns=headers,
            )

            logger.info(
                "Loaded sheet '%s' with %d rows",
                sheet_name,
                len(df),
            )

            return df

        except HttpError as e:

            logger.warning(
                "HttpError reading %s attempt %d/%d: %s",
                sheet_name,
                attempt,
                max_retries,
                e,
            )

        except Exception as e:

            logger.exception(
                "Unexpected error reading %s: %s",
                sheet_name,
                e,
            )

        if attempt < max_retries:
            time.sleep(
                backoff * (2 ** (attempt - 1))
            )

    raise RuntimeError(
        f"Failed to load sheet {sheet_name}"
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_sheet_cached(sheet_name: str) -> pd.DataFrame:
    return load_sheet(sheet_name)


# ============================================================
# CLEANING HELPERS
# ============================================================

PHONE_RE = re.compile(r"\D")


def clean_phone(series: pd.Series) -> pd.Series:

    return (
        series
        .fillna("")
        .astype(str)
        .str.replace(
            PHONE_RE,
            "",
            regex=True,
        )
        .str.lstrip("0")
        .str.strip()
    )


def parse_mixed_date(value):

    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    if text.lower() in {
        "",
        "(blank)",
        "nan",
        "none",
    }:
        return pd.NaT

    iso_match = re.match(
        r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        text,
    )

    if iso_match:

        year, month, day = iso_match.groups()

        try:
            return pd.Timestamp(
                year=int(year),
                month=int(month),
                day=int(day),
            )
        except ValueError:
            pass

    uk_match = re.match(
        r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})",
        text,
    )

    if uk_match:

        day, month, year = uk_match.groups()

        try:
            return pd.Timestamp(
                year=int(year),
                month=int(month),
                day=int(day),
            )
        except ValueError:
            pass

    return pd.to_datetime(
        text,
        errors="coerce",
        dayfirst=True,
    )


def parse_date_series(series: pd.Series) -> pd.Series:
    return series.apply(parse_mixed_date)


def format_date(value):

    if pd.isna(value):
        return ""

    try:
        return pd.Timestamp(value).strftime(
            "%d/%m/%Y"
        )
    except Exception:
        return ""


# ============================================================
# STATUS CATEGORISATION
# ============================================================

def categorize_quality_status(series: pd.Series):

    s = (
        series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    pending = s.isin(
        [
            "",
            "(blank)",
            "nan",
            "none",
        ]
    )

    approved = s.str.contains(
        "appr",
        na=False,
    )

    rework = s.str.contains(
        "rework",
        na=False,
    )

    cancelled = s.str.contains(
        r"cancel|reject|hold|duplicat|inbound|n/a|rec in accessible",
        na=False,
    )

    return pd.Series(
        np.select(
            [
                pending,
                approved,
                rework,
                cancelled,
            ],
            [
                "Pending",
                "Approved",
                "Rework",
                "Cancelled",
            ],
            default="Cancelled",
        ),
        index=series.index,
    )


def categorize_welcome_status(series: pd.Series):

    s = (
        series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    pending = (
        s.isin(
            [
                "",
                "(blank)",
                "nan",
                "none",
            ]
        )
        |
        s.str.contains(
            r"pending|follow|paperwork|wrong|ring",
            na=False,
        )
    )

    done = s.str.contains(
        "done",
        na=False,
    )

    cancelled = s.str.contains(
        r"cancel|reject|hold",
        na=False,
    )

    return pd.Series(
        np.select(
            [
                pending,
                done,
                cancelled,
            ],
            [
                "Pending",
                "Done",
                "Cancelled",
            ],
            default="Pending",
        ),
        index=series.index,
    )


def categorize_portal_status(series: pd.Series):

    s = (
        series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    committed = (
        s.isin(
            [
                "",
                "(blank)",
                "nan",
                "none",
            ]
        )
        |
        s.str.contains(
            r"commit|in progress|processing",
            na=False,
        )
    )

    cancelled = s.str.contains(
        r"cancel|reject",
        na=False,
    )

    live = s.str.contains(
        r"live|pending|active|completed",
        na=False,
    )

    return pd.Series(
        np.select(
            [
                cancelled,
                live,
                committed,
            ],
            [
                "Cancelled",
                "Live",
                "Committed",
            ],
            default="Committed",
        ),
        index=series.index,
    )


# ============================================================
# PROVISIONING CLASSIFICATION
# ============================================================

def categorize_provisioning_status(series: pd.Series):

    """
    Draft provisioning categorisation.

    This does NOT represent an SLA.

    It simply attempts to identify:
        - Pending
        - Completed
        - Cancelled

    Any unrecognised status is kept as Pending so that the
    dashboard errs toward showing something requiring attention
    rather than silently hiding it.
    """

    s = (
        series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    cancelled = s.str.contains(
        r"cancel|reject|failed|fail",
        na=False,
    )

    completed = s.str.contains(
        r"complete|completed|done|live|installed|activated|provisioned",
        na=False,
    )

    return pd.Series(
        np.select(
            [
                cancelled,
                completed,
            ],
            [
                "Cancelled",
                "Completed",
            ],
            default="Pending",
        ),
        index=series.index,
    )


# ============================================================
# LOAD APPLICATION SHEET
# ============================================================

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_sparta() -> pd.DataFrame:

    df = load_sheet_cached(
        APPLICATION_SHEET
    )

    if df.empty:
        return df

    rename_map = {

        "Advisor":
            "Advisor",

        "Quality Officer":
            "Quality Officer",

        "Welcome Call By":
            "Welcome Call By",

        "Sale Date":
            "Sale Date",

        "Customer Name":
            "Customer Name",

        "CLI":
            "Telephone No.",

        "Quality Date":
            "Quality Date",

        "Quality Status":
            "Quality Status",

        "Quality Remarks":
            "Quality Remarks",

        "Welcome call Remarks":
            "Welcome Remarks",

        "Status":
            "Welcome Status",

        "Cancellation Sub-text":
            "Welcome Cancellation",

        "WCD date":
            "Welcome Date",

        "Provisioning":
            "Provisioning Status",

        "Prov Date":
            "Provisioning Date",

        "Current Provider":
            "Current Provider",

        "Packageoffered":
            "Package",

        "Dashboard_Month":
            "Dashboard Month",

        "Standardized_Date":
            "Standardized Date",
    }

    df = df.rename(
        columns={
            k: v
            for k, v in rename_map.items()
            if k in df.columns
        }
    )

    keep_columns = [
        c
        for c in rename_map.values()
        if c in df.columns
    ]

    df = df[keep_columns].copy()

    # Phone
    if "Telephone No." in df.columns:

        df["Telephone No."] = clean_phone(
            df["Telephone No."]
        )

    # Sale date
    if "Sale Date" in df.columns:

        df["Sale Date Clean"] = (
            parse_date_series(
                df["Sale Date"]
            )
        )

        df["Sale Date"] = (
            df["Sale Date Clean"]
            .apply(format_date)
        )

    # Other dates
    for col in [
        "Quality Date",
        "Welcome Date",
        "Provisioning Date",
        "Standardized Date",
    ]:

        if col in df.columns:

            parsed = parse_date_series(
                df[col]
            )

            df[f"{col} Clean"] = parsed

            df[col] = parsed.apply(
                format_date
            )

    # Quality
    if "Quality Status" in df.columns:

        df["Quality Status Clean"] = (
            categorize_quality_status(
                df["Quality Status"]
            )
        )

    # Welcome
    if "Welcome Status" in df.columns:

        df["Welcome Status Clean"] = (
            categorize_welcome_status(
                df["Welcome Status"]
            )
        )

    # Provisioning
    if "Provisioning Status" in df.columns:

        df["Provisioning Status Clean"] = (
            categorize_provisioning_status(
                df["Provisioning Status"]
            )
        )

    # Guarantee important columns
    for col in [
        "Advisor",
        "Quality Officer",
        "Welcome Call By",
        "Customer Name",
        "Telephone No.",
        "Quality Status",
        "Quality Remarks",
        "Welcome Status",
        "Welcome Remarks",
        "Welcome Cancellation",
        "Provisioning Status",
        "Current Provider",
        "Package",
    ]:

        if col not in df.columns:
            df[col] = ""

    return df


# ============================================================
# LOAD PORTAL SHEET
# ============================================================

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_sparta2() -> pd.DataFrame:

    df = load_sheet_cached(
        LIVE_SHEET
    )

    if df.empty:
        return df

    rename_map = {

        "Sale Date":
            "Sale Date",

        "Telephone No.":
            "Telephone No.",

        "Committed Date":
            "Live Date",

        "Status":
            "Portal Status",

        "LetterStatus":
            "Letter Status",

        "CallStatus":
            "Call Status",

        "Comments":
            "Comments",

        "Voice of Customer":
            "Voice of Customer",

        "Cancellation Reason":
            "Portal Cancellation",

        "Dashboard_Month":
            "Dashboard Month",

        "Standardized_Date":
            "Standardized Date",
    }

    df = df.rename(
        columns={
            k: v
            for k, v in rename_map.items()
            if k in df.columns
        }
    )

    keep_columns = [
        c
        for c in rename_map.values()
        if c in df.columns
    ]

    df = df[keep_columns].copy()

    if "Telephone No." in df.columns:

        df["Telephone No."] = clean_phone(
            df["Telephone No."]
        )

    if "Sale Date" in df.columns:

        df["Sale Date Clean"] = (
            parse_date_series(
                df["Sale Date"]
            )
        )

        df["Sale Date"] = (
            df["Sale Date Clean"]
            .apply(format_date)
        )

    for col in [
        "Live Date",
        "Standardized Date",
    ]:

        if col in df.columns:

            parsed = parse_date_series(
                df[col]
            )

            df[f"{col} Clean"] = parsed

            df[col] = parsed.apply(
                format_date
            )

    if "Portal Status" in df.columns:

        df["Portal Status Clean"] = (
            categorize_portal_status(
                df["Portal Status"]
            )
        )

    for col in [
        "Portal Status",
        "Letter Status",
        "Call Status",
        "Comments",
        "Voice of Customer",
        "Portal Cancellation",
        "Telephone No.",
    ]:

        if col not in df.columns:
            df[col] = ""

    return df


# ============================================================
# LOAD DATA
# ============================================================

with st.spinner(
    "Loading Sparta operational data..."
):

    try:

        sparta_df = load_sparta()
        sparta2_df = load_sparta2()

    except Exception as e:

        logger.exception(
            "Failed to load data: %s",
            e,
        )

        st.error(
            "Unable to load the Google Sheets data."
        )

        st.stop()


# ============================================================
# MASTER MERGE
# ============================================================

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def build_master(
    applications: pd.DataFrame,
    portal: pd.DataFrame,
) -> pd.DataFrame:

    apps = applications.copy()
    portal_copy = portal.copy()

    if (
        "Telephone No." in portal_copy.columns
    ):

        portal_copy = portal_copy[
            portal_copy["Telephone No."]
            .fillna("")
            .astype(str)
            .str.strip()
            != ""
        ].copy()

        portal_copy = (
            portal_copy
            .drop_duplicates(
                subset="Telephone No.",
                keep="last",
            )
        )

    if (
        "Telephone No." in apps.columns
        and
        "Telephone No." in portal_copy.columns
    ):

        master = apps.merge(
            portal_copy,
            on="Telephone No.",
            how="left",
            suffixes=(
                "",
                "_portal",
            ),
        )

    else:

        master = apps.copy()

    return master


master_df = build_master(
    sparta_df,
    sparta2_df,
)


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="main-title">
        ⏳ Sparta Pending Operations
    </div>

    <div class="main-subtitle">
        Current sales requiring action — showing exactly where each
        sale is pending.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# REFRESH / SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## ⚙️ Dashboard Controls"
    )

    st.caption(
        "This dashboard tracks pending work only. "
        "No SLA thresholds are applied."
    )

    st.divider()

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True,
    ):

        st.cache_data.clear()

        st.rerun()

    st.divider()

    st.markdown(
        "### Data Sources"
    )

    st.caption(
        f"Applications: `{APPLICATION_SHEET}`"
    )

    st.caption(
        f"Portal: `{LIVE_SHEET}`"
    )

    st.divider()

    st.caption(
        f"Last dashboard run:\n"
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )


# ============================================================
# SAFETY CHECK
# ============================================================

if master_df.empty:

    st.warning(
        "No application records were found."
    )

    st.stop()


# ============================================================
# BUILD PENDING QUEUES
# ============================================================

# ------------------------------------------------------------
# QUALITY
# ------------------------------------------------------------

if "Quality Status Clean" in master_df.columns:

    quality_pending_df = master_df[
        master_df["Quality Status Clean"]
        == "Pending"
    ].copy()

else:

    quality_pending_df = master_df.iloc[0:0].copy()


# ------------------------------------------------------------
# WELCOME
# ------------------------------------------------------------

if "Welcome Status Clean" in master_df.columns:

    welcome_pending_df = master_df[
        master_df["Welcome Status Clean"]
        == "Pending"
    ].copy()

else:

    welcome_pending_df = master_df.iloc[0:0].copy()


# ------------------------------------------------------------
# COMMITTED
# ------------------------------------------------------------

if "Portal Status Clean" in master_df.columns:

    committed_pending_df = master_df[
        master_df["Portal Status Clean"]
        == "Committed"
    ].copy()

else:

    committed_pending_df = master_df.iloc[0:0].copy()


# ------------------------------------------------------------
# PROVISIONING
# ------------------------------------------------------------

if "Provisioning Status Clean" in master_df.columns:

    provisioning_pending_df = master_df[
        master_df["Provisioning Status Clean"]
        == "Pending"
    ].copy()

else:

    provisioning_pending_df = master_df.iloc[0:0].copy()


# ============================================================
# FILTER CONTROLS
# ============================================================

st.markdown(
    '<div class="section-title">🔎 Filters</div>',
    unsafe_allow_html=True,
)

with st.container():

    st.markdown(
        '<div class="filter-box">',
        unsafe_allow_html=True,
    )

    filter_1, filter_2, filter_3, filter_4 = st.columns(
        [1.4, 1.0, 1.0, 1.6]
    )

    # --------------------------------------------------------
    # Advisor
    # --------------------------------------------------------

    with filter_1:

        advisor_values = sorted(
            [
                str(x).strip()
                for x in master_df["Advisor"]
                .dropna()
                .unique()
                if str(x).strip()
            ],
            key=lambda x: x.lower(),
        )

        selected_advisors = st.multiselect(
            "Advisor",
            options=advisor_values,
            placeholder="All advisors",
        )

    # --------------------------------------------------------
    # From
    # --------------------------------------------------------

    valid_sale_dates = (
        master_df["Sale Date Clean"]
        .dropna()
        if "Sale Date Clean" in master_df.columns
        else pd.Series(
            dtype="datetime64[ns]"
        )
    )

    default_start = (
        valid_sale_dates.min().date()
        if not valid_sale_dates.empty
        else date.today()
    )

    default_end = (
        valid_sale_dates.max().date()
        if not valid_sale_dates.empty
        else date.today()
    )

    with filter_2:

        start_date = st.date_input(
            "Sale Date From",
            value=default_start,
            format="DD/MM/YYYY",
        )

    # --------------------------------------------------------
    # To
    # --------------------------------------------------------

    with filter_3:

        end_date = st.date_input(
            "Sale Date To",
            value=default_end,
            format="DD/MM/YYYY",
        )

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    with filter_4:

        search_text = st.text_input(
            "Search",
            placeholder="Customer or telephone number...",
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# FILTER FUNCTION
# ============================================================

def apply_filters(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.copy()

    result = df.copy()

    # --------------------------------------------------------
    # Advisor
    # --------------------------------------------------------

    if selected_advisors:

        advisor_norm = {
            x.strip().lower()
            for x in selected_advisors
        }

        result = result[
            result["Advisor"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(advisor_norm)
        ].copy()

    # --------------------------------------------------------
    # Sale date
    # --------------------------------------------------------

    if "Sale Date Clean" in result.columns:

        result = result[
            result["Sale Date Clean"].notna()
        ].copy()

        if start_date <= end_date:

            result = result[
                (
                    result["Sale Date Clean"].dt.date
                    >= start_date
                )
                &
                (
                    result["Sale Date Clean"].dt.date
                    <= end_date
                )
            ].copy()

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    search = str(
        search_text or ""
    ).strip().lower()

    if search:

        customer = (
            result["Customer Name"]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        phone = (
            result["Telephone No."]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        advisor = (
            result["Advisor"]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        result = result[
            customer.str.contains(
                search,
                na=False,
            )
            |
            phone.str.contains(
                search,
                na=False,
            )
            |
            advisor.str.contains(
                search,
                na=False,
            )
        ].copy()

    return result


quality_pending_df = apply_filters(
    quality_pending_df
)

welcome_pending_df = apply_filters(
    welcome_pending_df
)

committed_pending_df = apply_filters(
    committed_pending_df
)

provisioning_pending_df = apply_filters(
    provisioning_pending_df
)


# ============================================================
# KPI COUNTS
# ============================================================

quality_count = len(
    quality_pending_df
)

welcome_count = len(
    welcome_pending_df
)

committed_count = len(
    committed_pending_df
)

provisioning_count = len(
    provisioning_pending_df
)


# ============================================================
# ALL PENDING UNIQUE SALES
# ============================================================

pending_frames = []

for queue_name, queue_df in [
    (
        "Pending Quality",
        quality_pending_df,
    ),
    (
        "Pending Welcome",
        welcome_pending_df,
    ),
    (
        "Pending Committed",
        committed_pending_df,
    ),
    (
        "Pending Provisioning",
        provisioning_pending_df,
    ),
]:

    if not queue_df.empty:

        temp = queue_df.copy()

        temp["Pending Area"] = queue_name

        pending_frames.append(
            temp
        )


if pending_frames:

    all_pending_long = pd.concat(
        pending_frames,
        ignore_index=True,
    )

else:

    all_pending_long = (
        master_df.iloc[0:0].copy()
    )

    all_pending_long["Pending Area"] = ""


# ============================================================
# UNIQUE SALES TOTAL
# ============================================================

if (
    not all_pending_long.empty
    and
    "Telephone No." in all_pending_long.columns
):

    valid_pending_phones = (
        all_pending_long[
            all_pending_long["Telephone No."]
            .fillna("")
            .astype(str)
            .str.strip()
            != ""
        ]
    )

    unique_pending_sales = (
        valid_pending_phones[
            "Telephone No."
        ]
        .nunique()
    )

    # If there are rows without phone numbers,
    # retain them as individual records.
    blank_phone_rows = (
        all_pending_long[
            all_pending_long["Telephone No."]
            .fillna("")
            .astype(str)
            .str.strip()
            == ""
        ]
    )

    unique_pending_sales += len(
        blank_phone_rows
    )

else:

    unique_pending_sales = len(
        all_pending_long
    )


# ============================================================
# KPI HEADER
# ============================================================

st.markdown(
    '<div class="section-title">📌 Current Pending Work</div>',
    unsafe_allow_html=True,
)

kpi_columns = st.columns(5)


def render_kpi(
    column,
    icon,
    title,
    count,
    description,
    card_class,
):

    with column:

        st.markdown(
            f"""
            <div class="pending-card {card_class}">

                <div class="pending-card-top">

                    <div class="pending-card-title">
                        {escape(title)}
                    </div>

                    <div class="pending-card-icon">
                        {icon}
                    </div>

                </div>

                <div class="pending-card-number">
                    {count:,}
                </div>

                <div class="pending-card-description">
                    {escape(description)}
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


render_kpi(
    kpi_columns[0],
    "🧪",
    "Pending Quality",
    quality_count,
    "Sales currently awaiting Quality",
    "card-quality",
)

render_kpi(
    kpi_columns[1],
    "📞",
    "Pending Welcome",
    welcome_count,
    "Sales currently awaiting Welcome",
    "card-welcome",
)

render_kpi(
    kpi_columns[2],
    "📱",
    "Pending Committed",
    committed_count,
    "Sales currently remaining in Committed",
    "card-committed",
)

render_kpi(
    kpi_columns[3],
    "⚙️",
    "Pending Provisioning",
    provisioning_count,
    "Sales currently awaiting provisioning",
    "card-provisioning",
)

render_kpi(
    kpi_columns[4],
    "⏳",
    "Pending Sales",
    unique_pending_sales,
    "Unique sales appearing in pending queues",
    "card-total",
)


# ============================================================
# QUEUE SUMMARY
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">🗂️ Pending Queue Summary</div>',
    unsafe_allow_html=True,
)

summary_rows = [
    {
        "AREA": "🧪 Quality",
        "PENDING": quality_count,
        "DESCRIPTION": "Awaiting Quality review",
    },
    {
        "AREA": "📞 Welcome",
        "PENDING": welcome_count,
        "DESCRIPTION": "Awaiting Welcome Call",
    },
    {
        "AREA": "📱 Committed",
        "PENDING": committed_count,
        "DESCRIPTION": "Awaiting movement from Committed",
    },
    {
        "AREA": "⚙️ Provisioning",
        "PENDING": provisioning_count,
        "DESCRIPTION": "Awaiting provisioning completion",
    },
]

summary_df = pd.DataFrame(
    summary_rows
)

summary_html = """
<div class="queue-table-wrapper">
<table class="queue-table">
<thead>
<tr>
    <th>AREA</th>
    <th>PENDING</th>
    <th>DESCRIPTION</th>
</tr>
</thead>
<tbody>
"""

for _, row in summary_df.iterrows():

    summary_html += f"""
    <tr>
        <td class="customer">
            {escape(str(row["AREA"]))}
        </td>

        <td>
            <strong>
                {int(row["PENDING"]):,}
            </strong>
        </td>

        <td>
            {escape(str(row["DESCRIPTION"]))}
        </td>
    </tr>
    """

summary_html += """
</tbody>
</table>
</div>
"""

components.html(
    summary_html,
    height=270,
    scrolling=False,
)


# ============================================================
# TABLE PREPARATION
# ============================================================

def build_queue_display(
    df: pd.DataFrame,
    queue_name: str,
) -> pd.DataFrame:

    if df.empty:

        return pd.DataFrame(
            columns=[
                "CUSTOMER",
                "TELEPHONE",
                "ADVISOR",
                "SALE DATE",
                "PENDING AREA",
                "STATUS",
                "DETAILS",
            ]
        )

    result = pd.DataFrame()

    result["CUSTOMER"] = (
        df["Customer Name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "Unnamed Customer")
    )

    result["TELEPHONE"] = (
        df["Telephone No."]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result["ADVISOR"] = (
        df["Advisor"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "Unassigned")
    )

    if "Sale Date Clean" in df.columns:

        result["SALE DATE"] = (
            df["Sale Date Clean"]
            .apply(format_date)
        )

    else:

        result["SALE DATE"] = ""

    result["PENDING AREA"] = queue_name

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if queue_name == "Pending Quality":

        result["STATUS"] = (
            df["Quality Status"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        result["DETAILS"] = (
            df["Quality Remarks"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    elif queue_name == "Pending Welcome":

        result["STATUS"] = (
            df["Welcome Status"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        result["DETAILS"] = (
            df["Welcome Remarks"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    elif queue_name == "Pending Committed":

        result["STATUS"] = (
            df["Portal Status"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        portal_comments = (
            df["Comments"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        call_status = (
            df["Call Status"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        result["DETAILS"] = (
            portal_comments
            .where(
                portal_comments != "",
                call_status,
            )
        )

    else:

        result["STATUS"] = (
            df["Provisioning Status"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        result["DETAILS"] = (
            df["Current Provider"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    result["STATUS"] = (
        result["STATUS"]
        .replace("", "Not specified")
    )

    result["DETAILS"] = (
        result["DETAILS"]
        .replace("", "—")
    )

    return result


# ============================================================
# HTML TABLE RENDERER
# ============================================================

def render_queue_table(
    df: pd.DataFrame,
    queue_name: str,
    table_id: str,
):

    display_df = build_queue_display(
        df,
        queue_name,
    )

    if display_df.empty:

        st.markdown(
            f"""
            <div class="empty-state">

                <div class="empty-state-icon">
                    ✅
                </div>

                <div class="empty-state-title">
                    Nothing pending here
                </div>

                <div class="empty-state-text">
                    There are currently no sales in the
                    {escape(queue_name)} queue matching
                    the selected filters.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        return

    html = f"""
    <style>

    #{table_id}-wrapper {{
        width: 100%;
        max-height: 650px;
        overflow: auto;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #fff;
    }}

    #{table_id} {{
        width: 100%;
        border-collapse: collapse;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Roboto,
            Arial,
            sans-serif;
        font-size: 0.83rem;
    }}

    #{table_id} th {{
        position: sticky;
        top: 0;
        z-index: 5;
        padding: 11px 12px;
        background: #f8fafc;
        color: #475569;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        border-bottom: 2px solid #e2e8f0;
        cursor: pointer;
        white-space: nowrap;
    }}

    #{table_id} th:hover {{
        background: #f1f5f9;
    }}

    #{table_id} td {{
        padding: 10px 12px;
        border-bottom: 1px solid #f1f5f9;
        color: #334155;
        vertical-align: top;
    }}

    #{table_id} tr:hover td {{
        background: #f8fafc;
    }}

    #{table_id} td.customer {{
        font-weight: 750;
        color: #0f172a;
        white-space: nowrap;
    }}

    #{table_id} td.phone {{
        font-family: monospace;
        white-space: nowrap;
    }}

    #{table_id} td.date {{
        white-space: nowrap;
    }}

    #{table_id} td.status {{
        font-weight: 650;
    }}

    .badge {{
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 0.66rem;
        font-weight: 800;
        white-space: nowrap;
    }}

    .badge-quality {{
        background: #fff7ed;
        color: #c2410c;
        border: 1px solid #fed7aa;
    }}

    .badge-welcome {{
        background: #fefce8;
        color: #a16207;
        border: 1px solid #fde68a;
    }}

    .badge-committed {{
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }}

    .badge-provisioning {{
        background: #f5f3ff;
        color: #6d28d9;
        border: 1px solid #ddd6fe;
    }}

    </style>

    <div id="{table_id}-wrapper">

    <table id="{table_id}">

    <thead>
    <tr>
    """

    columns = list(
        display_df.columns
    )

    for col in columns:

        html += (
            f'<th onclick="sortTable('
            f"'{table_id}', "
            f"{columns.index(col)}"
            f')">'
            f"{escape(col)}"
            f"</th>"
        )

    html += """
    </tr>
    </thead>
    <tbody>
    """

    queue_badge_class = {
        "Pending Quality":
            "badge-quality",

        "Pending Welcome":
            "badge-welcome",

        "Pending Committed":
            "badge-committed",

        "Pending Provisioning":
            "badge-provisioning",
    }.get(
        queue_name,
        "badge-quality",
    )

    for _, row in display_df.iterrows():

        html += "<tr>"

        for col in columns:

            value = row[col]

            if pd.isna(value):
                value = ""

            value = str(value)

            if col == "CUSTOMER":

                html += (
                    '<td class="customer">'
                    + escape(value)
                    + "</td>"
                )

            elif col == "TELEPHONE":

                html += (
                    '<td class="phone">'
                    + escape(value)
                    + "</td>"
                )

            elif col == "SALE DATE":

                html += (
                    '<td class="date">'
                    + escape(value)
                    + "</td>"
                )

            elif col == "PENDING AREA":

                html += (
                    f'<td>'
                    f'<span class="badge {queue_badge_class}">'
                    f'{escape(value)}'
                    f'</span>'
                    f'</td>'
                )

            elif col == "STATUS":

                html += (
                    '<td class="status">'
                    + escape(value)
                    + "</td>"
                )

            else:

                html += (
                    "<td>"
                    + escape(value)
                    + "</td>"
                )

        html += "</tr>"

    html += """
    </tbody>
    </table>
    </div>

    <script>

    function sortTable(tableId, columnIndex) {

        const table =
            document.getElementById(tableId);

        const tbody =
            table.tBodies[0];

        const rows =
            Array.from(tbody.rows);

        const currentDirection =
            table.getAttribute(
                "data-sort-direction"
            ) || "desc";

        const currentColumn =
            table.getAttribute(
                "data-sort-column"
            );

        let direction = "asc";

        if (
            currentColumn === String(columnIndex)
            &&
            currentDirection === "asc"
        ) {
            direction = "desc";
        }

        rows.sort(function(a, b) {

            const aText =
                a.cells[columnIndex]
                .innerText
                .trim();

            const bText =
                b.cells[columnIndex]
                .innerText
                .trim();

            const aNum =
                parseFloat(
                    aText.replace(/,/g, "")
                );

            const bNum =
                parseFloat(
                    bText.replace(/,/g, "")
                );

            if (
                !isNaN(aNum)
                &&
                !isNaN(bNum)
            ) {

                return direction === "asc"
                    ? aNum - bNum
                    : bNum - aNum;
            }

            return direction === "asc"
                ? aText.localeCompare(bText)
                : bText.localeCompare(aText);

        });

        rows.forEach(
            row => tbody.appendChild(row)
        );

        table.setAttribute(
            "data-sort-column",
            columnIndex
        );

        table.setAttribute(
            "data-sort-direction",
            direction
        );
    }

    </script>
    """

    table_height = min(
        700,
        max(
            180,
            75 + len(display_df) * 40,
        ),
    )

    components.html(
        html,
        height=table_height,
        scrolling=False,
    )


# ============================================================
# TABS
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">📋 Pending Work Queues</div>',
    unsafe_allow_html=True,
)

tab_all, tab_quality, tab_welcome, tab_committed, tab_prov = st.tabs(
    [
        "⏳ All Pending",
        "🧪 Quality",
        "📞 Welcome",
        "📱 Committed",
        "⚙️ Provisioning",
    ]
)


# ============================================================
# ALL PENDING TAB
# ============================================================

with tab_all:

    st.markdown(
        f"""
        **{unique_pending_sales:,} unique pending sales**
        across the four operational queues.
        """,
    )

    if all_pending_long.empty:

        st.markdown(
            """
            <div class="empty-state">

                <div class="empty-state-icon">
                    🎉
                </div>

                <div class="empty-state-title">
                    No pending sales
                </div>

                <div class="empty-state-text">
                    There are currently no pending sales
                    matching the selected filters.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        all_display = all_pending_long.copy()

        # ----------------------------------------------------
        # De-duplicate by phone for the overall queue.
        # Keep every queue assignment separately in a readable
        # "Pending Area" value.
        # ----------------------------------------------------

        if "Telephone No." in all_display.columns:

            all_display["Telephone No."] = (
                all_display["Telephone No."]
                .fillna("")
                .astype(str)
            )

        grouping_columns = [
            c
            for c in [
                "Telephone No.",
                "Customer Name",
                "Advisor",
                "Sale Date Clean",
            ]
            if c in all_display.columns
        ]

        if grouping_columns:

            grouped = []

            for keys, group in all_display.groupby(
                grouping_columns,
                dropna=False,
            ):

                if not isinstance(keys, tuple):
                    keys = (keys,)

                record = {}

                for col, value in zip(
                    grouping_columns,
                    keys,
                ):
                    record[col] = value

                areas = []

                for area in group[
                    "Pending Area"
                ].dropna().astype(str):

                    if area not in areas:
                        areas.append(area)

                record[
                    "Pending Area"
                ] = areas

                # Keep useful raw information
                for source_col in [
                    "Quality Status",
                    "Welcome Status",
                    "Portal Status",
                    "Provisioning Status",
                ]:

                    if source_col in group.columns:

                        values = (
                            group[source_col]
                            .fillna("")
                            .astype(str)
                            .str.strip()
                        )

                        values = [
                            x
                            for x in values
                            if x
                        ]

                        record[
                            source_col
                        ] = (
                            " | ".join(
                                dict.fromkeys(values)
                            )
                            if values
                            else ""
                        )

                grouped.append(record)

            all_unique = pd.DataFrame(
                grouped
            )

        else:

            all_unique = all_display.copy()

        # ----------------------------------------------------
        # Prepare display
        # ----------------------------------------------------

        output = pd.DataFrame()

        output["CUSTOMER"] = (
            all_unique.get(
                "Customer Name",
                pd.Series(
                    index=all_unique.index,
                    dtype=str,
                ),
            )
            .fillna("")
            .astype(str)
            .replace(
                "",
                "Unnamed Customer",
            )
        )

        output["TELEPHONE"] = (
            all_unique.get(
                "Telephone No.",
                pd.Series(
                    index=all_unique.index,
                    dtype=str,
                ),
            )
            .fillna("")
            .astype(str)
        )

        output["ADVISOR"] = (
            all_unique.get(
                "Advisor",
                pd.Series(
                    index=all_unique.index,
                    dtype=str,
                ),
            )
            .fillna("")
            .astype(str)
            .replace(
                "",
                "Unassigned",
            )
        )

        if "Sale Date Clean" in all_unique.columns:

            output["SALE DATE"] = (
                all_unique[
                    "Sale Date Clean"
                ]
                .apply(format_date)
            )

        else:

            output["SALE DATE"] = ""

        output["PENDING WHERE"] = (
            all_unique[
                "Pending Area"
            ]
            .apply(
                lambda x:
                    " + ".join(x)
                    if isinstance(x, list)
                    else str(x)
            )
        )

        status_parts = []

        for _, row in all_unique.iterrows():

            parts = []

            for source_col, label in [
                (
                    "Quality Status",
                    "Quality",
                ),
                (
                    "Welcome Status",
                    "Welcome",
                ),
                (
                    "Portal Status",
                    "Committed",
                ),
                (
                    "Provisioning Status",
                    "Provisioning",
                ),
            ]:

                value = str(
                    row.get(
                        source_col,
                        "",
                    )
                ).strip()

                if value:

                    parts.append(
                        f"{label}: {value}"
                    )

            status_parts.append(
                " | ".join(parts)
            )

        output["STATUS / DETAIL"] = (
            status_parts
        )

        # ----------------------------------------------------
        # Render
        # ----------------------------------------------------

        html = """
        <style>

        #all-pending-wrapper {
            width: 100%;
            max-height: 680px;
            overflow: auto;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            background: #fff;
        }

        #all-pending-table {
            width: 100%;
            border-collapse: collapse;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Roboto,
                Arial,
                sans-serif;
            font-size: 0.83rem;
        }

        #all-pending-table th {
            position: sticky;
            top: 0;
            z-index: 5;
            padding: 11px 12px;
            background: #f8fafc;
            color: #475569;
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            border-bottom: 2px solid #e2e8f0;
            cursor: pointer;
            white-space: nowrap;
        }

        #all-pending-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #f1f5f9;
            color: #334155;
            vertical-align: top;
        }

        #all-pending-table tr:hover td {
            background: #f8fafc;
        }

        .all-customer {
            font-weight: 750;
            color: #0f172a;
            white-space: nowrap;
        }

        .all-phone {
            font-family: monospace;
            white-space: nowrap;
        }

        .all-date {
            white-space: nowrap;
        }

        .where-cell {
            min-width: 260px;
        }

        .where-badge {
            display: inline-block;
            margin: 2px 4px 2px 0;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 0.64rem;
            font-weight: 800;
        }

        .where-quality {
            background: #fff7ed;
            color: #c2410c;
        }

        .where-welcome {
            background: #fefce8;
            color: #a16207;
        }

        .where-committed {
            background: #eff6ff;
            color: #1d4ed8;
        }

        .where-provisioning {
            background: #f5f3ff;
            color: #6d28d9;
        }

        </style>

        <div id="all-pending-wrapper">

        <table id="all-pending-table">

        <thead>
        <tr>
            <th onclick="sortAllPending(0)">CUSTOMER</th>
            <th onclick="sortAllPending(1)">TELEPHONE</th>
            <th onclick="sortAllPending(2)">ADVISOR</th>
            <th onclick="sortAllPending(3)">SALE DATE</th>
            <th onclick="sortAllPending(4)">PENDING WHERE</th>
            <th onclick="sortAllPending(5)">STATUS / DETAIL</th>
        </tr>
        </thead>

        <tbody>
        """

        for _, row in output.iterrows():

            areas = str(
                row["PENDING WHERE"]
            ).split(" + ")

            badges = ""

            for area in areas:

                area_lower = (
                    area.lower()
                )

                if "quality" in area_lower:
                    cls = "where-quality"

                elif "welcome" in area_lower:
                    cls = "where-welcome"

                elif "committed" in area_lower:
                    cls = "where-committed"

                else:
                    cls = "where-provisioning"

                badges += (
                    f'<span class="where-badge {cls}">'
                    f'{escape(area)}'
                    f'</span>'
                )

            html += f"""
            <tr>

                <td class="all-customer">
                    {escape(str(row["CUSTOMER"]))}
                </td>

                <td class="all-phone">
                    {escape(str(row["TELEPHONE"]))}
                </td>

                <td>
                    {escape(str(row["ADVISOR"]))}
                </td>

                <td class="all-date">
                    {escape(str(row["SALE DATE"]))}
                </td>

                <td class="where-cell">
                    {badges}
                </td>

                <td>
                    {escape(str(row["STATUS / DETAIL"]))}
                </td>

            </tr>
            """

        html += """
        </tbody>
        </table>
        </div>

        <script>

        function sortAllPending(columnIndex) {

            const table =
                document.getElementById(
                    "all-pending-table"
                );

            const tbody =
                table.tBodies[0];

            const rows =
                Array.from(tbody.rows);

            const currentDirection =
                table.getAttribute(
                    "data-sort-direction"
                ) || "desc";

            const currentColumn =
                table.getAttribute(
                    "data-sort-column"
                );

            let direction = "asc";

            if (
                currentColumn === String(columnIndex)
                &&
                currentDirection === "asc"
            ) {
                direction = "desc";
            }

            rows.sort(function(a, b) {

                const aText =
                    a.cells[columnIndex]
                    .innerText
                    .trim();

                const bText =
                    b.cells[columnIndex]
                    .innerText
                    .trim();

                const aNum =
                    parseFloat(
                        aText.replace(/,/g, "")
                    );

                const bNum =
                    parseFloat(
                        bText.replace(/,/g, "")
                    );

                if (
                    !isNaN(aNum)
                    &&
                    !isNaN(bNum)
                ) {

                    return direction === "asc"
                        ? aNum - bNum
                        : bNum - aNum;
                }

                return direction === "asc"
                    ? aText.localeCompare(bText)
                    : bText.localeCompare(aText);

            });

            rows.forEach(
                row => tbody.appendChild(row)
            );

            table.setAttribute(
                "data-sort-column",
                columnIndex
            );

            table.setAttribute(
                "data-sort-direction",
                direction
            );
        }

        </script>
        """

        height = min(
            720,
            max(
                220,
                90 + len(output) * 40,
            ),
        )

        components.html(
            html,
            height=height,
            scrolling=False,
        )


# ============================================================
# QUALITY TAB
# ============================================================

with tab_quality:

    st.markdown(
        f"""
        **{quality_count:,} sales** currently pending Quality.
        """
    )

    render_queue_table(
        quality_pending_df,
        "Pending Quality",
        "quality-pending-table",
    )


# ============================================================
# WELCOME TAB
# ============================================================

with tab_welcome:

    st.markdown(
        f"""
        **{welcome_count:,} sales** currently pending Welcome Call.
        """
    )

    render_queue_table(
        welcome_pending_df,
        "Pending Welcome",
        "welcome-pending-table",
    )


# ============================================================
# COMMITTED TAB
# ============================================================

with tab_committed:

    st.markdown(
        f"""
        **{committed_count:,} sales** currently remaining in Committed.
        """
    )

    render_queue_table(
        committed_pending_df,
        "Pending Committed",
        "committed-pending-table",
    )


# ============================================================
# PROVISIONING TAB
# ============================================================

with tab_prov:

    st.markdown(
        f"""
        **{provisioning_count:,} sales** currently pending Provisioning.
        """
    )

    render_queue_table(
        provisioning_pending_df,
        "Pending Provisioning",
        "provisioning-pending-table",
    )


# ============================================================
# ADVISOR BREAKDOWN
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">👥 Pending Work by Advisor</div>',
    unsafe_allow_html=True,
)


advisor_rows = []

for queue_name, queue_df in [
    (
        "Pending Quality",
        quality_pending_df,
    ),
    (
        "Pending Welcome",
        welcome_pending_df,
    ),
    (
        "Pending Committed",
        committed_pending_df,
    ),
    (
        "Pending Provisioning",
        provisioning_pending_df,
    ),
]:

    if queue_df.empty:
        continue

    if "Advisor" not in queue_df.columns:
        continue

    grouped = (
        queue_df
        .assign(
            AdvisorDisplay=
            queue_df["Advisor"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace(
                "",
                "Unassigned",
            )
        )
        .groupby(
            "AdvisorDisplay"
        )
        .size()
        .reset_index(
            name="Count"
        )
    )

    for _, row in grouped.iterrows():

        advisor_rows.append(
            {
                "Advisor":
                    row["AdvisorDisplay"],

                "Area":
                    queue_name,

                "Pending":
                    int(row["Count"]),
            }
        )


if advisor_rows:

    advisor_queue_df = pd.DataFrame(
        advisor_rows
    )

    advisor_pivot = (
        advisor_queue_df
        .pivot_table(
            index="Advisor",
            columns="Area",
            values="Pending",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    for col in [
        "Pending Quality",
        "Pending Welcome",
        "Pending Committed",
        "Pending Provisioning",
    ]:

        if col not in advisor_pivot.columns:
            advisor_pivot[col] = 0

    advisor_pivot["TOTAL PENDING"] = (
        advisor_pivot[
            [
                "Pending Quality",
                "Pending Welcome",
                "Pending Committed",
                "Pending Provisioning",
            ]
        ].sum(axis=1)
    )

    advisor_pivot = (
        advisor_pivot
        .sort_values(
            "TOTAL PENDING",
            ascending=False,
        )
    )

    advisor_pivot = advisor_pivot.rename(
        columns={
            "Pending Quality":
                "QUALITY",

            "Pending Welcome":
                "WELCOME",

            "Pending Committed":
                "COMMITTED",

            "Pending Provisioning":
                "PROVISIONING",
        }
    )

    # --------------------------------------------------------
    # Render advisor table
    # --------------------------------------------------------

    advisor_columns = [
        "Advisor",
        "QUALITY",
        "WELCOME",
        "COMMITTED",
        "PROVISIONING",
        "TOTAL PENDING",
    ]

    advisor_html = """
    <style>

    #advisor-pending-wrapper {
        width: 100%;
        max-height: 550px;
        overflow: auto;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #fff;
    }

    #advisor-pending-table {
        width: 100%;
        border-collapse: collapse;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Roboto,
            Arial,
            sans-serif;
        font-size: 0.84rem;
    }

    #advisor-pending-table th {
        position: sticky;
        top: 0;
        z-index: 5;
        padding: 11px 12px;
        background: #f8fafc;
        color: #475569;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        border-bottom: 2px solid #e2e8f0;
        cursor: pointer;
    }

    #advisor-pending-table td {
        padding: 10px 12px;
        border-bottom: 1px solid #f1f5f9;
        text-align: center;
    }

    #advisor-pending-table td:first-child {
        text-align: left;
        font-weight: 750;
        color: #0f172a;
    }

    #advisor-pending-table tr:hover td {
        background: #f8fafc;
    }

    .zero-value {
        color: #cbd5e1;
    }

    .pending-total {
        font-weight: 850;
        color: #0f172a;
    }

    </style>

    <div id="advisor-pending-wrapper">

    <table id="advisor-pending-table">

    <thead>
    <tr>
    """

    for index, col in enumerate(
        advisor_columns
    ):

        advisor_html += (
            f'<th onclick="sortAdvisorPending({index})">'
            f'{escape(col)}'
            f'</th>'
        )

    advisor_html += """
    </tr>
    </thead>
    <tbody>
    """

    for _, row in advisor_pivot.iterrows():

        advisor_html += "<tr>"

        for col in advisor_columns:

            value = row.get(
                col,
                0,
            )

            if col == "Advisor":

                advisor_html += (
                    f"<td>"
                    f"{escape(str(value))}"
                    f"</td>"
                )

            else:

                number = int(
                    value or 0
                )

                if number == 0:

                    advisor_html += (
                        '<td class="zero-value">—</td>'
                    )

                elif col == "TOTAL PENDING":

                    advisor_html += (
                        f'<td class="pending-total">'
                        f'{number:,}'
                        f'</td>'
                    )

                else:

                    advisor_html += (
                        f"<td>{number:,}</td>"
                    )

        advisor_html += "</tr>"

    advisor_html += """
    </tbody>
    </table>
    </div>

    <script>

    function sortAdvisorPending(columnIndex) {

        const table =
            document.getElementById(
                "advisor-pending-table"
            );

        const tbody =
            table.tBodies[0];

        const rows =
            Array.from(tbody.rows);

        const currentDirection =
            table.getAttribute(
                "data-sort-direction"
            ) || "desc";

        const currentColumn =
            table.getAttribute(
                "data-sort-column"
            );

        let direction = "asc";

        if (
            currentColumn === String(columnIndex)
            &&
            currentDirection === "asc"
        ) {
            direction = "desc";
        }

        rows.sort(function(a, b) {

            const aText =
                a.cells[columnIndex]
                .innerText
                .trim();

            const bText =
                b.cells[columnIndex]
                .innerText
                .trim();

            const aNum =
                parseFloat(
                    aText.replace(/,/g, "")
                );

            const bNum =
                parseFloat(
                    bText.replace(/,/g, "")
                );

            if (
                !isNaN(aNum)
                &&
                !isNaN(bNum)
            ) {

                return direction === "asc"
                    ? aNum - bNum
                    : bNum - aNum;
            }

            return direction === "asc"
                ? aText.localeCompare(bText)
                : bText.localeCompare(aText);

        });

        rows.forEach(
            row => tbody.appendChild(row)
        );

        table.setAttribute(
            "data-sort-column",
            columnIndex
        );

        table.setAttribute(
            "data-sort-direction",
            direction
        );
    }

    </script>
    """

    components.html(
        advisor_html,
        height=min(
            600,
            max(
                180,
                85 + len(advisor_pivot) * 42,
            ),
        ),
        scrolling=False,
    )

else:

    st.info(
        "No pending work matches the selected filters."
    )


# ============================================================
# DATA QUALITY / CLASSIFICATION NOTE
# ============================================================

st.divider()

with st.expander(
    "ℹ️ How this first draft determines pending work"
):

    st.markdown(
        """
        **Quality**

        A sale appears in Pending Quality when its existing
        Quality Status is categorised as `Pending`.

        **Welcome**

        A sale appears in Pending Welcome when its existing
        Welcome Status is categorised as `Pending`.

        **Committed**

        A sale appears in Pending Committed when the portal/live
        status is categorised as `Committed`.

        **Provisioning**

        A sale appears in Pending Provisioning when its
        Provisioning status is not recognised as completed or
        cancelled.

        This is deliberately **not an SLA calculation**.

        The dashboard does not determine whether a pending item
        is late, breached, urgent or within target.
        It simply shows the current pending state.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

footer_col1, footer_col2 = st.columns(
    [1, 1]
)

with footer_col1:

    st.caption(
        "Sparta Pending Operations Dashboard"
    )

with footer_col2:

    st.caption(
        f"Refreshed: "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
