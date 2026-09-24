"""
SPARTA PENDING OPERATIONS DASHBOARD
===================================

Purpose
-------
A separate operational dashboard showing CURRENTLY PENDING SALES.

Pending logic
-------------
QUALITY
    Quality Status is blank
    AND
    Quality Remarks is blank

WELCOME
    Welcome call Remarks is blank
    AND
    Status is blank

PROVISIONING
    Status = "Done"
    AND
    Provisioning != "Processed"

COMMITTED
    CallStatus is blank
    AND
    Comments is blank

There are deliberately NO SLA targets, deadlines, breach calculations,
RAG status, ageing calculations or performance scores.

The dashboard simply answers:

    WHICH SALES ARE PENDING?
    WHERE ARE THEY PENDING?

Manual Pending Sales
--------------------
Because current / previous day sales may not yet exist in the source sheet,
manual pending sales can be entered for any stage and any date.

Manual entries are retained for the current Streamlit browser session and
are included in all pending counts and tables.

Data sources
------------
    Sparta  -> Applications / Quality / Welcome / Provisioning
    Sparta2 -> Committed / CallStatus / Comments
"""

# ============================================================
# IMPORTS
# ============================================================

import logging
import re
import time
from datetime import date, datetime
from html import escape
from typing import List
from zoneinfo import ZoneInfo

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
        logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"
        )
    )
    logger.addHandler(handler)

logger.setLevel(logging.INFO)


# ============================================================
# TIMEZONE
# ============================================================

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


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

    .block-container {
        padding-top: 1.35rem;
        padding-bottom: 2rem;
        max-width: 1650px;
    }

    .main-title {
        font-size: 2rem;
        font-weight: 850;
        color: #0f172a;
        letter-spacing: -0.7px;
        margin-bottom: 2px;
    }

    .main-subtitle {
        color: #64748b;
        font-size: 0.92rem;
        margin-bottom: 1.1rem;
    }

    .small-muted {
        color: #64748b;
        font-size: 0.78rem;
    }

    .section-title {
        font-size: 1.2rem;
        font-weight: 800;
        color: #0f172a;
        margin-top: 0.25rem;
        margin-bottom: 0.5rem;
    }

    .filter-panel {
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px 4px 16px;
        background: #f8fafc;
    }

    .manual-panel {
        border: 1px solid #dbeafe;
        border-radius: 14px;
        padding: 4px 10px 6px 10px;
        background: #f8fbff;
    }

    .empty-box {
        border: 1px dashed #cbd5e1;
        border-radius: 14px;
        padding: 35px 20px;
        text-align: center;
        background: #f8fafc;
    }

    .empty-icon {
        font-size: 2rem;
        margin-bottom: 6px;
    }

    .empty-title {
        font-weight: 800;
        color: #334155;
        font-size: 1rem;
    }

    .empty-description {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 4px;
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
# STAGE DEFINITIONS
# ============================================================

STAGE_OPTIONS = [
    "Quality",
    "Welcome",
    "Committed",
    "Provisioning",
]


STAGE_LABELS = {
    "Quality": "🧪 Quality",
    "Welcome": "📞 Welcome",
    "Committed": "📱 Committed",
    "Provisioning": "⚙️ Provisioning",
}


STAGE_DESCRIPTIONS = {
    "Quality": "Quality Status + Quality Remarks are blank",
    "Welcome": "Welcome call Remarks + Status are blank",
    "Committed": "CallStatus + Comments are blank",
    "Provisioning": "Status = Done and Provisioning is not Processed",
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

    return build(
        "sheets",
        "v4",
        credentials=credentials,
        cache_discovery=False,
    )


# ============================================================
# GOOGLE SHEET LOADER
# ============================================================

def load_sheet(
    sheet_name: str,
    max_retries: int = 3,
    backoff: float = 1.0,
) -> pd.DataFrame:

    service = get_google_service()

    for attempt in range(
        1,
        max_retries + 1,
    ):

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

            values = result.get(
                "values",
                [],
            )

            if not values:
                return pd.DataFrame()

            headers = values[0]
            rows = values[1:]

            max_columns = len(headers)

            cleaned_rows = []

            for row in rows:

                if len(row) < max_columns:
                    row = (
                        row
                        + [""] * (
                            max_columns - len(row)
                        )
                    )

                else:
                    row = row[:max_columns]

                cleaned_rows.append(row)

            return pd.DataFrame(
                cleaned_rows,
                columns=headers,
            )

        except HttpError as exc:

            logger.warning(
                "Google Sheets error %s attempt %d/%d: %s",
                sheet_name,
                attempt,
                max_retries,
                exc,
            )

        except Exception as exc:

            logger.exception(
                "Unexpected Google Sheets error: %s",
                exc,
            )

        if attempt < max_retries:
            time.sleep(
                backoff * (
                    2 ** (attempt - 1)
                )
            )

    raise RuntimeError(
        f"Unable to load sheet '{sheet_name}' "
        f"after {max_retries} attempts."
    )


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_sheet_cached(
    sheet_name: str,
) -> pd.DataFrame:

    return load_sheet(sheet_name)


# ============================================================
# BASIC CLEANING
# ============================================================

PHONE_RE = re.compile(r"\D")


def clean_phone_value(value) -> str:

    if pd.isna(value):
        return ""

    return (
        PHONE_RE
        .sub("", str(value))
        .lstrip("0")
        .strip()
    )


def clean_phone_series(
    series: pd.Series,
) -> pd.Series:

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


def is_blank_value(value) -> bool:

    if pd.isna(value):
        return True

    return str(value).strip() == ""


def normalised_text(value) -> str:

    if pd.isna(value):
        return ""

    return (
        str(value)
        .strip()
        .lower()
    )


def format_date_value(value) -> str:

    if pd.isna(value):
        return ""

    try:
        return pd.Timestamp(value).strftime(
            "%d/%m/%Y"
        )
    except Exception:
        return ""


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

        year, month, day = (
            iso_match.groups()
        )

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

        day, month, year = (
            uk_match.groups()
        )

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


def parse_date_series(
    series: pd.Series,
) -> pd.Series:

    return series.apply(
        parse_mixed_date
    )


# ============================================================
# ENSURE COLUMNS
# ============================================================

def ensure_columns(
    df: pd.DataFrame,
    columns: List[str],
) -> pd.DataFrame:

    df = df.copy()

    for column in columns:

        if column not in df.columns:
            df[column] = ""

    return df


# ============================================================
# LOAD SPARTA APPLICATION SHEET
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

    required = [
        "Advisor",
        "Quality Officer",
        "Welcome Call By",
        "Sale Date",
        "Customer Name",
        "CLI",
        "Quality Date",
        "Quality Status",
        "Quality Remarks",
        "Welcome call Remarks",
        "Status",
        "Cancellation Sub-text",
        "WCD date",
        "Provisioning",
        "Prov Date",
        "Current Provider",
        "Packageoffered",
    ]

    df = ensure_columns(
        df,
        required,
    )

    df = df.copy()

    # --------------------------------------------------------
    # Normalised phone
    # --------------------------------------------------------

    df["_Phone"] = clean_phone_series(
        df["CLI"]
    )

    # --------------------------------------------------------
    # Sale date
    # --------------------------------------------------------

    df["_SaleDate"] = parse_date_series(
        df["Sale Date"]
    )

    # --------------------------------------------------------
    # Useful display dates
    # --------------------------------------------------------

    df["_SaleDateDisplay"] = (
        df["_SaleDate"]
        .apply(format_date_value)
    )

    df["_QualityDate"] = parse_date_series(
        df["Quality Date"]
    )

    df["_WelcomeDate"] = parse_date_series(
        df["WCD date"]
    )

    df["_ProvisioningDate"] = parse_date_series(
        df["Prov Date"]
    )

    return df


# ============================================================
# LOAD SPARTA2
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

    required = [
        "Sale Date",
        "Telephone No.",
        "Committed Date",
        "Status",
        "LetterStatus",
        "CallStatus",
        "Comments",
        "Voice of Customer",
        "Cancellation Reason",
    ]

    df = ensure_columns(
        df,
        required,
    )

    df = df.copy()

    # --------------------------------------------------------
    # Normalised phone
    # --------------------------------------------------------

    df["_Phone"] = clean_phone_series(
        df["Telephone No."]
    )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    df["_SaleDate"] = parse_date_series(
        df["Sale Date"]
    )

    df["_SaleDateDisplay"] = (
        df["_SaleDate"]
        .apply(format_date_value)
    )

    df["_CommittedDate"] = parse_date_series(
        df["Committed Date"]
    )

    return df


# ============================================================
# LOAD DATA
# ============================================================

with st.spinner(
    "Loading Sparta data..."
):

    try:

        sparta_df = load_sparta()
        sparta2_df = load_sparta2()

    except Exception as exc:

        logger.exception(
            "Failed loading source data: %s",
            exc,
        )

        st.error(
            "Unable to load the Sparta Google Sheets."
        )

        st.stop()


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="main-title">
        ⏳ Sparta Pending Operations
    </div>

    <div class="main-subtitle">
        Current pending sales, organised by exactly where they are waiting
        for action.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Dashboard Controls")

    st.caption(
        "This dashboard does not define or calculate any SLA."
    )

    st.divider()

    if st.button(
        "🔄 Refresh Source Data",
        use_container_width=True,
    ):

        st.cache_data.clear()

        st.rerun()

    st.divider()

    st.markdown(
        "**Source Sheets**"
    )

    st.caption(
        f"Applications: `{APPLICATION_SHEET}`"
    )

    st.caption(
        f"Committed: `{LIVE_SHEET}`"
    )

    st.divider()

    st.caption(
        "Manual pending entries are retained "
        "for the current browser session."
    )


# ============================================================
# MANUAL PENDING ENTRIES
# ============================================================

if (
    "manual_pending_rows"
    not in st.session_state
):

    st.session_state[
        "manual_pending_rows"
    ] = pd.DataFrame(
        {
            "Date": pd.Series(
                dtype="datetime64[ns]"
            ),
            "Stage": pd.Series(
                dtype="string"
            ),
            "Customer Name": pd.Series(
                dtype="string"
            ),
            "Telephone No.": pd.Series(
                dtype="string"
            ),
            "Advisor": pd.Series(
                dtype="string"
            ),
            "Notes": pd.Series(
                dtype="string"
            ),
        }
    )


st.divider()

with st.expander(
    "➕ Add / Edit Manual Pending Sales",
    expanded=False,
):

    st.info(
        "Use this when a sale is missing from the source sheet, "
        "especially for the current or previous date. "
        "Add one row per pending stage. "
        "Manual entries are included immediately in the dashboard."
    )

    manual_edit = st.data_editor(
        st.session_state[
            "manual_pending_rows"
        ],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="manual_pending_editor",
        column_config={
            "Date": st.column_config.DateColumn(
                "Date",
                format="DD/MM/YYYY",
                required=True,
            ),
            "Stage": st.column_config.SelectboxColumn(
                "Stage",
                options=STAGE_OPTIONS,
                required=True,
            ),
            "Customer Name": st.column_config.TextColumn(
                "Customer Name",
            ),
            "Telephone No.": st.column_config.TextColumn(
                "Telephone No.",
            ),
            "Advisor": st.column_config.TextColumn(
                "Advisor",
            ),
            "Notes": st.column_config.TextColumn(
                "Notes",
                width="large",
            ),
        },
    )

    st.session_state[
        "manual_pending_rows"
    ] = manual_edit.copy()

    manual_count = len(
        manual_edit
    )

    if manual_count:

        st.caption(
            f"{manual_count:,} manual pending row"
            f"{'' if manual_count == 1 else 's'} "
            "currently entered."
        )

    else:

        st.caption(
            "No manual pending sales have been entered."
        )


# ============================================================
# FILTER RANGE
# ============================================================

st.subheader("🔎 Filters")

filter_panel = st.container(
    border=True
)

with filter_panel:

    col1, col2, col3, col4 = st.columns(
        [1.15, 1.0, 1.0, 1.55]
    )

    # --------------------------------------------------------
    # Advisor options
    # --------------------------------------------------------

    advisor_series = sparta_df[
        "Advisor"
    ].fillna("").astype(str).str.strip()

    advisor_options = sorted(
        [
            x for x in
            advisor_series.unique()
            if x
        ],
        key=lambda x: x.lower(),
    )

    with col1:

        selected_advisors = st.multiselect(
            "Advisor",
            options=advisor_options,
            placeholder="All advisors",
        )

    # --------------------------------------------------------
    # Determine sensible default date range
    # --------------------------------------------------------

    source_dates = []

    if (
        "_SaleDate"
        in sparta_df.columns
    ):

        source_dates.extend(
            sparta_df[
                "_SaleDate"
            ]
            .dropna()
            .tolist()
        )

    if (
        "_SaleDate"
        in sparta2_df.columns
    ):

        source_dates.extend(
            sparta2_df[
                "_SaleDate"
            ]
            .dropna()
            .tolist()
        )

    manual_dates = []

    manual_source = (
        st.session_state[
            "manual_pending_rows"
        ]
        if "manual_pending_rows"
        in st.session_state
        else pd.DataFrame()
    )

    if (
        not manual_source.empty
        and "Date" in manual_source.columns
    ):

        manual_dates.extend(
            pd.to_datetime(
                manual_source[
                    "Date"
                ],
                errors="coerce",
            )
            .dropna()
            .tolist()
        )

    all_known_dates = (
        source_dates
        + manual_dates
    )

    today = now_ist().date()

    if all_known_dates:

        earliest_date = min(
            pd.Timestamp(x).date()
            for x in all_known_dates
        )

        latest_date = max(
            pd.Timestamp(x).date()
            for x in all_known_dates
        )

        # Always allow today's manual/current-date records
        # even when today's sale does not yet exist in the sheet.
        min_filter_date = min(
            earliest_date,
            today,
        )

        max_filter_date = max(
            latest_date,
            today,
        )

    else:

        min_filter_date = today
        max_filter_date = today

    with col2:

        start_date = st.date_input(
            "Sale Date From",
            value=min_filter_date,
            min_value=min_filter_date,
            max_value=max_filter_date,
            format="DD/MM/YYYY",
        )

    with col3:

        end_date = st.date_input(
            "Sale Date To",
            value=max_filter_date,
            min_value=min_filter_date,
            max_value=max_filter_date,
            format="DD/MM/YYYY",
        )

    with col4:

        search_text = st.text_input(
            "Search",
            placeholder="Customer, phone or advisor...",
        )


# ============================================================
# VALIDATE FILTER DATES
# ============================================================

if start_date > end_date:

    st.error(
        "Start Date must be earlier than or equal to End Date."
    )

    st.stop()


# ============================================================
# BUILD MANUAL DATA
# ============================================================

def prepare_manual_entries(
    manual_df: pd.DataFrame,
) -> pd.DataFrame:

    if manual_df.empty:

        return pd.DataFrame(
            columns=[
                "_SaleDate",
                "_Phone",
                "Customer Name",
                "Advisor",
                "Pending Stage",
                "Notes",
                "Source",
                "_SaleKey",
            ]
        )

    result = manual_df.copy()

    result["Date"] = pd.to_datetime(
        result["Date"],
        errors="coerce",
    )

    result = result[
        result["Date"].notna()
    ].copy()

    if result.empty:

        return pd.DataFrame(
            columns=[
                "_SaleDate",
                "_Phone",
                "Customer Name",
                "Advisor",
                "Pending Stage",
                "Notes",
                "Source",
                "_SaleKey",
            ]
        )

    result["_SaleDate"] = result[
        "Date"
    ]

    result["_Phone"] = (
        result[
            "Telephone No."
        ]
        .fillna("")
        .astype(str)
        .apply(
            clean_phone_value
        )
    )

    result["Customer Name"] = (
        result[
            "Customer Name"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result["Advisor"] = (
        result[
            "Advisor"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result["Pending Stage"] = (
        result[
            "Stage"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result["Notes"] = (
        result[
            "Notes"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result["Source"] = "Manual"

    result["_SaleKey"] = result.apply(
        make_sale_key,
        axis=1,
    )

    return result[
        [
            "_SaleDate",
            "_Phone",
            "Customer Name",
            "Advisor",
            "Pending Stage",
            "Notes",
            "Source",
            "_SaleKey",
        ]
    ].copy()


# ============================================================
# SALE KEY
# ============================================================

def make_sale_key(
    row,
) -> str:

    phone = clean_phone_value(
        row.get(
            "_Phone",
            "",
        )
    )

    sale_date = row.get(
        "_SaleDate",
        pd.NaT,
    )

    date_part = ""

    if not pd.isna(sale_date):

        try:
            date_part = pd.Timestamp(
                sale_date
            ).strftime(
                "%Y%m%d"
            )
        except Exception:
            date_part = ""

    if phone:

        return (
            f"PHONE|{phone}|"
            f"{date_part}"
        )

    customer = normalised_text(
        row.get(
            "Customer Name",
            "",
        )
    )

    if customer:

        return (
            f"NAME|{customer}|"
            f"{date_part}"
        )

    return (
        f"ROW|"
        f"{date_part}|"
        f"{id(row)}"
    )


# ============================================================
# AUTO QUEUE BUILDERS
# ============================================================

def quality_pending_auto(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.iloc[0:0].copy()

    status_blank = (
        df["Quality Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
    )

    remarks_blank = (
        df["Quality Remarks"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
    )

    result = df[
        status_blank & remarks_blank
    ].copy()

    result["_PendingStage"] = "Quality"

    result["_Source"] = "Automatic"

    return result


def welcome_pending_auto(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.iloc[0:0].copy()

    remarks_blank = (
        df["Welcome call Remarks"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
    )

    status_blank = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
    )

    result = df[
        remarks_blank & status_blank
    ].copy()

    result["_PendingStage"] = "Welcome"

    result["_Source"] = "Automatic"

    return result


def provisioning_pending_auto(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.iloc[0:0].copy()

    status_done = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("done")
    )

    provisioning_not_processed = (
        df["Provisioning"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .ne("processed")
    )

    result = df[
        status_done
        & provisioning_not_processed
    ].copy()

    result["_PendingStage"] = "Provisioning"

    result["_Source"] = "Automatic"

    return result


def committed_pending_auto(
    portal_df: pd.DataFrame,
) -> pd.DataFrame:

    if portal_df.empty:
        return portal_df.iloc[0:0].copy()

    call_status_blank = (
        portal_df["CallStatus"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
    )

    comments_blank = (
        portal_df["Comments"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
    )

    result = portal_df[
        call_status_blank
        & comments_blank
    ].copy()

    result["_PendingStage"] = "Committed"

    result["_Source"] = "Automatic"

    return result


# ============================================================
# AUTO QUEUES
# ============================================================

quality_auto = quality_pending_auto(
    sparta_df
)

welcome_auto = welcome_pending_auto(
    sparta_df
)

provisioning_auto = provisioning_pending_auto(
    sparta_df
)

committed_auto = committed_pending_auto(
    sparta2_df
)


# ============================================================
# ENRICH COMMITTED WITH APPLICATION DETAILS
# ============================================================

application_lookup_columns = [
    "_Phone",
    "Customer Name",
    "Advisor",
    "_SaleDate",
    "Current Provider",
    "Packageoffered",
]


apps_for_lookup = sparta_df[
    [
        c
        for c in application_lookup_columns
        if c in sparta_df.columns
    ]
].copy()


if not apps_for_lookup.empty:

    apps_for_lookup = (
        apps_for_lookup
        .sort_values(
            "_SaleDate",
            na_position="first",
        )
        .drop_duplicates(
            subset="_Phone",
            keep="last",
        )
    )

    committed_auto = committed_auto.merge(
        apps_for_lookup,
        on="_Phone",
        how="left",
        suffixes=(
            "",
            "_app",
        ),
    )

    # Use application-side customer information
    # only where the portal row itself has none.
    if "Customer Name" not in committed_auto.columns:
        committed_auto["Customer Name"] = ""

    if "Advisor" not in committed_auto.columns:
        committed_auto["Advisor"] = ""

    if "_SaleDate" not in committed_auto.columns:
        committed_auto["_SaleDate"] = pd.NaT


# ============================================================
# MANUAL ENTRIES
# ============================================================

manual_entries = prepare_manual_entries(
    st.session_state[
        "manual_pending_rows"
    ]
)


# ============================================================
# FILTER AUTOMATIC DATA
# ============================================================

def within_date_range(
    series: pd.Series,
) -> pd.Series:

    dates = pd.to_datetime(
        series,
        errors="coerce",
    )

    # Convert the Streamlit date_input values to
    # pandas timestamps so both sides of the comparison
    # use the same datetime type.
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    return (
        dates.notna()
        &
        (dates >= start_ts)
        &
        (dates < end_ts + pd.Timedelta(days=1))
    )

def filter_by_advisor(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.copy()

    if not selected_advisors:
        return df.copy()

    selected = {
        normalised_text(x)
        for x in selected_advisors
    }

    advisor_values = (
        df["Advisor"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return df[
        advisor_values.isin(
            selected
        )
    ].copy()


def filter_by_search(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.copy()

    query = (
        str(search_text or "")
        .strip()
        .lower()
    )

    if not query:
        return df.copy()

    customer = (
        df["Customer Name"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    phone = (
        df["_Phone"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    advisor = (
        df["Advisor"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    notes = (
        df.get(
            "Notes",
            pd.Series(
                "",
                index=df.index,
            ),
        )
        .fillna("")
        .astype(str)
        .str.lower()
    )

    return df[
        customer.str.contains(
            query,
            na=False,
        )
        |
        phone.str.contains(
            query,
            na=False,
        )
        |
        advisor.str.contains(
            query,
            na=False,
        )
        |
        notes.str.contains(
            query,
            na=False,
        )
    ].copy()


def apply_common_filters(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.copy()

    if "_SaleDate" in df.columns:

        result = df[
            within_date_range(
                df["_SaleDate"]
            )
        ].copy()

    else:

        result = df.copy()

    result = filter_by_advisor(
        result
    )

    result = filter_by_search(
        result
    )

    return result


quality_auto = apply_common_filters(
    quality_auto
)

welcome_auto = apply_common_filters(
    welcome_auto
)

provisioning_auto = apply_common_filters(
    provisioning_auto
)

committed_auto = apply_common_filters(
    committed_auto
)


# ============================================================
# FILTER MANUAL ENTRIES
# ============================================================

def filter_manual_entries(
    df: pd.DataFrame,
    stage: str,
) -> pd.DataFrame:

    if df.empty:
        return df.copy()

    result = df[
        df["Pending Stage"]
        .astype(str)
        .str.strip()
        .eq(stage)
    ].copy()

    result = result[
        within_date_range(
            result["_SaleDate"]
        )
    ].copy()

    if selected_advisors:

        selected = {
            normalised_text(x)
            for x in selected_advisors
        }

        advisor_values = (
            result["Advisor"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        result = result[
            advisor_values.isin(
                selected
            )
        ].copy()

    query = (
        str(search_text or "")
        .strip()
        .lower()
    )

    if query:

        customer = (
            result[
                "Customer Name"
            ]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        phone = (
            result[
                "_Phone"
            ]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        advisor = (
            result[
                "Advisor"
            ]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        notes = (
            result[
                "Notes"
            ]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        result = result[
            customer.str.contains(
                query,
                na=False,
            )
            |
            phone.str.contains(
                query,
                na=False,
            )
            |
            advisor.str.contains(
                query,
                na=False,
            )
            |
            notes.str.contains(
                query,
                na=False,
            )
        ].copy()

    return result


manual_quality = filter_manual_entries(
    manual_entries,
    "Quality",
)

manual_welcome = filter_manual_entries(
    manual_entries,
    "Welcome",
)

manual_committed = filter_manual_entries(
    manual_entries,
    "Committed",
)

manual_provisioning = filter_manual_entries(
    manual_entries,
    "Provisioning",
)


# ============================================================
# ADD SALE KEYS TO AUTO DATA
# ============================================================

def add_auto_sale_keys(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df.copy()

    result = df.copy()

    result["_SaleKey"] = result.apply(
        make_sale_key,
        axis=1,
    )

    return result


quality_auto = add_auto_sale_keys(
    quality_auto
)

welcome_auto = add_auto_sale_keys(
    welcome_auto
)

provisioning_auto = add_auto_sale_keys(
    provisioning_auto
)

committed_auto = add_auto_sale_keys(
    committed_auto
)


# ============================================================
# MERGE AUTO + MANUAL WITHOUT DOUBLE COUNTING
# ============================================================

def combine_stage_queue(
    auto_df: pd.DataFrame,
    manual_df: pd.DataFrame,
    stage: str,
) -> pd.DataFrame:

    auto = auto_df.copy()
    manual = manual_df.copy()

    # --------------------------------------------------------
    # Normalise auto records
    # --------------------------------------------------------

    if not auto.empty:

        auto["_Source"] = "Automatic"
        auto["_PendingStage"] = stage

    # --------------------------------------------------------
    # Convert manual to common structure
    # --------------------------------------------------------

    manual_common = []

    if not manual.empty:

        for _, row in manual.iterrows():

            manual_common.append(
                {
                    "_SaleDate":
                        row["_SaleDate"],

                    "_Phone":
                        row["_Phone"],

                    "Customer Name":
                        row["Customer Name"],

                    "Advisor":
                        row["Advisor"],

                    "_PendingStage":
                        stage,

                    "Notes":
                        row["Notes"],

                    "_Source":
                        "Manual",

                    "_SaleKey":
                        row["_SaleKey"],
                }
            )

    manual_common_df = pd.DataFrame(
        manual_common
    )

    if auto.empty:

        combined = manual_common_df

    elif manual_common_df.empty:

        combined = auto

    else:

        # Automatic row is kept in preference to a duplicate
        # manual row because the source contains the complete record.
        combined = pd.concat(
            [
                auto,
                manual_common_df,
            ],
            ignore_index=True,
            sort=False,
        )

    if combined.empty:
        return combined

    combined = (
        combined
        .drop_duplicates(
            subset="_SaleKey",
            keep="first",
        )
        .reset_index(drop=True)
    )

    return combined


quality_queue = combine_stage_queue(
    quality_auto,
    manual_quality,
    "Quality",
)

welcome_queue = combine_stage_queue(
    welcome_auto,
    manual_welcome,
    "Welcome",
)

committed_queue = combine_stage_queue(
    committed_auto,
    manual_committed,
    "Committed",
)

provisioning_queue = combine_stage_queue(
    provisioning_auto,
    manual_provisioning,
    "Provisioning",
)


# ============================================================
# BUILD UNIQUE OVERALL PENDING SALES
# ============================================================

all_queue_frames = []

for queue_df in [
    quality_queue,
    welcome_queue,
    committed_queue,
    provisioning_queue,
]:

    if not queue_df.empty:

        temp = queue_df.copy()

        all_queue_frames.append(
            temp
        )


if all_queue_frames:

    all_pending_long = pd.concat(
        all_queue_frames,
        ignore_index=True,
        sort=False,
    )

else:

    all_pending_long = pd.DataFrame()


if not all_pending_long.empty:

    all_pending_unique = (
        all_pending_long
        .sort_values(
            "_SaleDate",
            na_position="last",
        )
        .drop_duplicates(
            subset="_SaleKey",
            keep="first",
        )
        .copy()
    )

else:

    all_pending_unique = pd.DataFrame()


# ============================================================
# KPI COUNTS
# ============================================================

quality_count = len(
    quality_queue
)

welcome_count = len(
    welcome_queue
)

committed_count = len(
    committed_queue
)

provisioning_count = len(
    provisioning_queue
)

unique_pending_count = len(
    all_pending_unique
)


# ============================================================
# KPI CARD HTML
# Rendered in components.html so the browser never displays
# the markup as raw HTML in the main Streamlit document.
# ============================================================

def build_kpi_html():

    cards = [
        {
            "title": "Pending Quality",
            "icon": "🧪",
            "number": quality_count,
            "description": "Sales currently awaiting Quality",
            "class": "quality",
        },
        {
            "title": "Pending Welcome",
            "icon": "📞",
            "number": welcome_count,
            "description": "Sales currently awaiting Welcome",
            "class": "welcome",
        },
        {
            "title": "Pending Committed",
            "icon": "📱",
            "number": committed_count,
            "description": "Sales currently awaiting Committed action",
            "class": "committed",
        },
        {
            "title": "Pending Provisioning",
            "icon": "⚙️",
            "number": provisioning_count,
            "description": "Sales currently awaiting provisioning",
            "class": "provisioning",
        },
        {
            "title": "Pending Sales",
            "icon": "⏳",
            "number": unique_pending_count,
            "description": "Unique sales appearing in pending queues",
            "class": "total",
        },
    ]

    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>

    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        padding: 4px 2px 6px 2px;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Roboto,
            Arial,
            sans-serif;
        background: transparent;
    }

    .cards {
        width: 100%;
        display: flex;
        gap: 12px;
    }

    .card {
        flex: 1 1 0;
        min-width: 0;
        height: 126px;
        border-radius: 14px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.05);
        padding: 15px 16px;
        position: relative;
        overflow: hidden;
    }

    .card::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        height: 4px;
    }

    .card.quality::before {
        background: #f97316;
    }

    .card.welcome::before {
        background: #eab308;
    }

    .card.committed::before {
        background: #3b82f6;
    }

    .card.provisioning::before {
        background: #8b5cf6;
    }

    .card.total::before {
        background: #64748b;
    }

    .top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .title {
        color: #64748b;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.7px;
        text-transform: uppercase;
    }

    .icon {
        font-size: 21px;
        line-height: 1;
    }

    .number {
        color: #0f172a;
        font-size: 31px;
        line-height: 1;
        font-weight: 850;
        margin-top: 16px;
        letter-spacing: -0.7px;
    }

    .description {
        color: #94a3b8;
        font-size: 11px;
        margin-top: 9px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    @media (max-width: 1100px) {
        .cards {
            flex-wrap: wrap;
        }

        .card {
            flex: 1 1 calc(50% - 8px);
        }
    }

    </style>
    </head>

    <body>

    <div class="cards">
    """

    for card in cards:

        html += f"""
        <div class="card {card["class"]}">

            <div class="top-row">

                <div class="title">
                    {escape(card["title"])}
                </div>

                <div class="icon">
                    {escape(card["icon"])}
                </div>

            </div>

            <div class="number">
                {int(card["number"]):,}
            </div>

            <div class="description">
                {escape(card["description"])}
            </div>

        </div>
        """

    html += """
    </div>

    </body>
    </html>
    """

    return html


components.html(
    build_kpi_html(),
    height=145,
    scrolling=False,
)


# ============================================================
# PENDING LOGIC SUMMARY
# ============================================================

with st.expander(
    "ℹ️ Pending logic used by this dashboard",
    expanded=False,
):

    logic_df = pd.DataFrame(
        [
            [
                "🧪 Quality",
                "Quality Status blank AND Quality Remarks blank",
            ],
            [
                "📞 Welcome",
                "Welcome call Remarks blank AND Status blank",
            ],
            [
                "📱 Committed",
                "CallStatus blank AND Comments blank",
            ],
            [
                "⚙️ Provisioning",
                'Status = "Done" AND Provisioning != "Processed"',
            ],
        ],
        columns=[
            "AREA",
            "PENDING CONDITION",
        ],
    )

    st.dataframe(
        logic_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "AREA": st.column_config.TextColumn(
                "AREA",
                width="medium",
            ),
            "PENDING CONDITION": st.column_config.TextColumn(
                "PENDING CONDITION",
                width="large",
            ),
        },
    )


# ============================================================
# TABLE PREPARATION
# ============================================================

def prepare_display_table(
    df: pd.DataFrame,
    stage: str,
) -> pd.DataFrame:

    if df.empty:

        return pd.DataFrame(
            columns=[
                "CUSTOMER",
                "TELEPHONE",
                "ADVISOR",
                "SALE DATE",
                "SOURCE",
                "PENDING CONDITION",
                "DETAILS",
            ]
        )

    result = pd.DataFrame(
        index=df.index
    )

    result["CUSTOMER"] = (
        df["Customer Name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace(
            "",
            "Unnamed Customer",
        )
    )

    result["TELEPHONE"] = (
        df["_Phone"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result["ADVISOR"] = (
        df["Advisor"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace(
            "",
            "Unassigned",
        )
    )

    result["SALE DATE"] = (
        pd.to_datetime(
            df["_SaleDate"],
            errors="coerce",
        )
        .apply(
            format_date_value
        )
    )

    result["SOURCE"] = (
        df["_Source"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # Stage-specific reason / details
    # --------------------------------------------------------

    if stage == "Quality":

        result["PENDING CONDITION"] = (
            "Quality Status blank + Quality Remarks blank"
        )

        auto_status = (
            df.get(
                "Quality Status",
                pd.Series(
                    "",
                    index=df.index,
                ),
            )
            .fillna("")
            .astype(str)
            .str.strip()
        )

        auto_remarks = (
            df.get(
                "Quality Remarks",
                pd.Series(
                    "",
                    index=df.index,
                ),
            )
            .fillna("")
            .astype(str)
            .str.strip()
        )

        details = []

        for idx in df.index:

            if (
                str(
                    df.loc[idx, "_Source"]
                )
                == "Manual"
            ):

                notes = str(
                    df.loc[idx].get(
                        "Notes",
                        "",
                    )
                ).strip()

                details.append(
                    notes
                    if notes
                    else "Manual pending entry"
                )

            else:

                status_value = (
                    auto_status.loc[idx]
                    if idx in auto_status.index
                    else ""
                )

                remarks_value = (
                    auto_remarks.loc[idx]
                    if idx in auto_remarks.index
                    else ""
                )

                details.append(
                    "Status blank"
                    + " • "
                    + "Remarks blank"
                )

        result["DETAILS"] = details

    elif stage == "Welcome":

        result["PENDING CONDITION"] = (
            "Welcome call Remarks blank + Status blank"
        )

        details = []

        for idx in df.index:

            if (
                str(
                    df.loc[idx, "_Source"]
                )
                == "Manual"
            ):

                notes = str(
                    df.loc[idx].get(
                        "Notes",
                        "",
                    )
                ).strip()

                details.append(
                    notes
                    if notes
                    else "Manual pending entry"
                )

            else:

                details.append(
                    "Welcome Remarks blank"
                    " • "
                    "Status blank"
                )

        result["DETAILS"] = details

    elif stage == "Committed":

        result["PENDING CONDITION"] = (
            "CallStatus blank + Comments blank"
        )

        details = []

        for idx in df.index:

            if (
                str(
                    df.loc[idx, "_Source"]
                )
                == "Manual"
            ):

                notes = str(
                    df.loc[idx].get(
                        "Notes",
                        "",
                    )
                ).strip()

                details.append(
                    notes
                    if notes
                    else "Manual pending entry"
                )

            else:

                details.append(
                    "CallStatus blank"
                    " • "
                    "Comments blank"
                )

        result["DETAILS"] = details

    else:

        result["PENDING CONDITION"] = (
            'Status = "Done" + Provisioning != "Processed"'
        )

        details = []

        for idx in df.index:

            if (
                str(
                    df.loc[idx, "_Source"]
                )
                == "Manual"
            ):

                notes = str(
                    df.loc[idx].get(
                        "Notes",
                        "",
                    )
                ).strip()

                details.append(
                    notes
                    if notes
                    else "Manual pending entry"
                )

            else:

                provisioning_value = str(
                    df.loc[idx].get(
                        "Provisioning",
                        "",
                    )
                ).strip()

                details.append(
                    f'Status = Done'
                    f" • "
                    f'Provisioning = '
                    f'{provisioning_value or "(blank)"}'
                )

        result["DETAILS"] = details

    return result.reset_index(
        drop=True
    )


# ============================================================
# TABLE RENDERER
# ============================================================

def render_queue_table(
    df: pd.DataFrame,
    stage: str,
    table_id: str,
):

    display_df = prepare_display_table(
        df,
        stage,
    )

    if display_df.empty:

        st.markdown(
            f"""
            <div class="empty-box">

                <div class="empty-icon">
                    ✅
                </div>

                <div class="empty-title">
                    Nothing pending in {escape(stage)}
                </div>

                <div class="empty-description">
                    No sales match the current filters.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        return

    # Native Streamlit dataframe is intentionally used here:
    # it provides reliable sorting, scrolling and text handling
    # without exposing HTML markup to the user.

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(
            650,
            max(
                180,
                90 + len(display_df) * 38,
            ),
        ),
        column_config={
            "CUSTOMER": st.column_config.TextColumn(
                "CUSTOMER",
                width="medium",
            ),
            "TELEPHONE": st.column_config.TextColumn(
                "TELEPHONE",
                width="small",
            ),
            "ADVISOR": st.column_config.TextColumn(
                "ADVISOR",
                width="medium",
            ),
            "SALE DATE": st.column_config.TextColumn(
                "SALE DATE",
                width="small",
            ),
            "SOURCE": st.column_config.TextColumn(
                "SOURCE",
                width="small",
            ),
            "PENDING CONDITION": st.column_config.TextColumn(
                "PENDING CONDITION",
                width="large",
            ),
            "DETAILS": st.column_config.TextColumn(
                "DETAILS",
                width="large",
            ),
        },
    )


# ============================================================
# ALL PENDING TABLE
# ============================================================

def build_all_pending_display(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:

        return pd.DataFrame(
            columns=[
                "CUSTOMER",
                "TELEPHONE",
                "ADVISOR",
                "SALE DATE",
                "PENDING WHERE",
                "SOURCE",
                "DETAILS",
            ]
        )

    rows = []

    grouped = df.groupby(
        "_SaleKey",
        dropna=False,
    )

    for _, group in grouped:

        first = group.iloc[0]

        customer = str(
            first.get(
                "Customer Name",
                "",
            )
        ).strip()

        phone = str(
            first.get(
                "_Phone",
                "",
            )
        ).strip()

        advisor = str(
            first.get(
                "Advisor",
                "",
            )
        ).strip()

        sale_date = first.get(
            "_SaleDate",
            pd.NaT,
        )

        if not customer:
            customer = "Unnamed Customer"

        if not advisor:
            advisor = "Unassigned"

        stages = []

        for stage in group[
            "_PendingStage"
        ].dropna():

            stage = str(stage).strip()

            if (
                stage
                and stage not in stages
            ):
                stages.append(stage)

        sources = []

        for source in group[
            "_Source"
        ].dropna():

            source = str(source).strip()

            if (
                source
                and source not in sources
            ):
                sources.append(source)

        notes = []

        for _, source_row in group.iterrows():

            if (
                str(
                    source_row.get(
                        "_Source",
                        "",
                    )
                )
                == "Manual"
            ):

                note = str(
                    source_row.get(
                        "Notes",
                        "",
                    )
                ).strip()

                if (
                    note
                    and note not in notes
                ):

                    notes.append(note)

        if notes:

            detail = " • ".join(notes)

        else:

            detail = (
                "Pending in: "
                + ", ".join(
                    stages
                )
            )

        rows.append(
            {
                "CUSTOMER": customer,
                "TELEPHONE": phone,
                "ADVISOR": advisor,
                "SALE DATE":
                    format_date_value(
                        sale_date
                    ),
                "PENDING WHERE":
                    " • ".join(
                        STAGE_LABELS.get(
                            x,
                            x,
                        )
                        for x in stages
                    ),
                "SOURCE":
                    " + ".join(
                        sources
                    ),
                "DETAILS":
                    detail,
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# TABS
# ============================================================

st.divider()

st.subheader(
    "📋 Pending Work Queues"
)

tab_all, tab_quality, tab_welcome, tab_committed, tab_provisioning = (
    st.tabs(
        [
            f"⏳ All Pending ({unique_pending_count:,})",
            f"🧪 Quality ({quality_count:,})",
            f"📞 Welcome ({welcome_count:,})",
            f"📱 Committed ({committed_count:,})",
            f"⚙️ Provisioning ({provisioning_count:,})",
        ]
    )
)


# ============================================================
# ALL PENDING
# ============================================================

with tab_all:

    st.caption(
        "Each sale is shown once here even if it is pending in "
        "more than one area."
    )

    all_display = build_all_pending_display(
        all_pending_long
    )

    if all_display.empty:

        st.markdown(
            """
            <div class="empty-box">

                <div class="empty-icon">
                    🎉
                </div>

                <div class="empty-title">
                    No pending sales
                </div>

                <div class="empty-description">
                    Nothing pending matches the current filters.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.dataframe(
            all_display,
            use_container_width=True,
            hide_index=True,
            height=min(
                680,
                max(
                    200,
                    100 + len(all_display) * 38,
                ),
            ),
            column_config={
                "CUSTOMER": st.column_config.TextColumn(
                    "CUSTOMER",
                    width="medium",
                ),
                "TELEPHONE": st.column_config.TextColumn(
                    "TELEPHONE",
                    width="small",
                ),
                "ADVISOR": st.column_config.TextColumn(
                    "ADVISOR",
                    width="medium",
                ),
                "SALE DATE": st.column_config.TextColumn(
                    "SALE DATE",
                    width="small",
                ),
                "PENDING WHERE": st.column_config.TextColumn(
                    "PENDING WHERE",
                    width="medium",
                ),
                "SOURCE": st.column_config.TextColumn(
                    "SOURCE",
                    width="small",
                ),
                "DETAILS": st.column_config.TextColumn(
                    "DETAILS",
                    width="large",
                ),
            },
        )


# ============================================================
# QUALITY
# ============================================================

with tab_quality:

    st.caption(
        "Pending when both Quality Status and Quality Remarks "
        "are blank."
    )

    render_queue_table(
        quality_queue,
        "Quality",
        "quality-table",
    )


# ============================================================
# WELCOME
# ============================================================

with tab_welcome:

    st.caption(
        "Pending when both Welcome call Remarks and Status "
        "are blank."
    )

    render_queue_table(
        welcome_queue,
        "Welcome",
        "welcome-table",
    )


# ============================================================
# COMMITTED
# ============================================================

with tab_committed:

    st.caption(
        "Pending when both CallStatus and Comments are blank."
    )

    render_queue_table(
        committed_queue,
        "Committed",
        "committed-table",
    )


# ============================================================
# PROVISIONING
# ============================================================

with tab_provisioning:

    st.caption(
        'Pending when Status is "Done" and Provisioning is '
        'anything other than "Processed".'
    )

    render_queue_table(
        provisioning_queue,
        "Provisioning",
        "provisioning-table",
    )


# ============================================================
# ADVISOR BREAKDOWN
# ============================================================

st.divider()

st.subheader(
    "👥 Pending Work by Advisor"
)


advisor_frames = []


for stage, queue_df in [
    (
        "Quality",
        quality_queue,
    ),
    (
        "Welcome",
        welcome_queue,
    ),
    (
        "Committed",
        committed_queue,
    ),
    (
        "Provisioning",
        provisioning_queue,
    ),
]:

    if queue_df.empty:
        continue

    temp = queue_df[
        [
            "Advisor",
            "_SaleKey",
        ]
    ].copy()

    temp["Advisor"] = (
        temp["Advisor"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace(
            "",
            "Unassigned",
        )
    )

    temp["Stage"] = stage

    temp = (
        temp
        .drop_duplicates()
    )

    advisor_frames.append(
        temp
    )


if advisor_frames:

    advisor_long = pd.concat(
        advisor_frames,
        ignore_index=True,
    )

    advisor_pivot = (
        advisor_long
        .groupby(
            [
                "Advisor",
                "Stage",
            ],
            dropna=False,
        )
        .size()
        .unstack(
            fill_value=0
        )
        .reset_index()
    )

    for stage in STAGE_OPTIONS:

        if stage not in advisor_pivot.columns:
            advisor_pivot[stage] = 0

    advisor_pivot["TOTAL PENDING"] = (
        advisor_pivot[
            STAGE_OPTIONS
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
            "Quality": "QUALITY",
            "Welcome": "WELCOME",
            "Committed": "COMMITTED",
            "Provisioning": "PROVISIONING",
        }
    )

    advisor_display = advisor_pivot[
        [
            "Advisor",
            "QUALITY",
            "WELCOME",
            "COMMITTED",
            "PROVISIONING",
            "TOTAL PENDING",
        ]
    ].copy()

    # Convert zeros to dash for cleaner presentation
    for column in [
        "QUALITY",
        "WELCOME",
        "COMMITTED",
        "PROVISIONING",
        "TOTAL PENDING",
    ]:

        advisor_display[column] = (
            advisor_display[column]
            .astype(int)
        )

    st.dataframe(
        advisor_display,
        use_container_width=True,
        hide_index=True,
        height=min(
            620,
            max(
                190,
                95 + len(advisor_display) * 38,
            ),
        ),
        column_config={
            "Advisor": st.column_config.TextColumn(
                "ADVISOR",
                width="medium",
            ),
            "QUALITY": st.column_config.NumberColumn(
                "QUALITY",
                format="%d",
            ),
            "WELCOME": st.column_config.NumberColumn(
                "WELCOME",
                format="%d",
            ),
            "COMMITTED": st.column_config.NumberColumn(
                "COMMITTED",
                format="%d",
            ),
            "PROVISIONING": st.column_config.NumberColumn(
                "PROVISIONING",
                format="%d",
            ),
            "TOTAL PENDING": st.column_config.NumberColumn(
                "TOTAL PENDING",
                format="%d",
            ),
        },
    )

else:

    st.info(
        "No pending work matches the current filters."
    )


# ============================================================
# MANUAL ENTRY SUMMARY
# ============================================================

manual_total = len(
    st.session_state[
        "manual_pending_rows"
    ]
)

if manual_total:

    st.divider()

    st.subheader(
        "📝 Manual Pending Entries"
    )

    st.caption(
        f"{manual_total:,} manual row"
        f"{'' if manual_total == 1 else 's'} "
        "currently stored in this browser session."
    )

    manual_summary = (
        st.session_state[
            "manual_pending_rows"
        ]
        .copy()
    )

    manual_summary["Date"] = pd.to_datetime(
        manual_summary["Date"],
        errors="coerce",
    ).dt.strftime(
        "%d/%m/%Y"
    )

    st.dataframe(
        manual_summary[
            [
                "Date",
                "Stage",
                "Customer Name",
                "Telephone No.",
                "Advisor",
                "Notes",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        height=min(
            400,
            max(
                130,
                80 + len(manual_summary) * 36,
            ),
        ),
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

footer_left, footer_right = st.columns(
    [1, 1]
)

with footer_left:

    st.caption(
        "Sparta Pending Operations Dashboard"
    )

with footer_right:

    st.caption(
        "Dashboard refreshed: "
        + now_ist().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
        + " IST"
    )
