"""
SPARTA PENDING OPERATIONS — GOOGLE SHEET QUEUE
================================================

Live operational queue driven by the CRM data mirrored into Google Sheets.

Workflow:

    Quality
        ↓ QA-Approved
    Welcome
        ↓ Welcome Approved
    Provisioning
        ↓ Connectivity: Committed / Connectivity: Order Provisioned
    Dispatch
        ↓ Dispatch Approved
    Confirmation
        ↓ Confirmation Approved / Confirmed / Complete
    Live / Onboarding

Queue rules:

    1. Quality
       Only QA-Pending is counted.

    2. Welcome
       Only opens after QA-Approved.
       - Welcome Followup = separate queue
       - Welcome Pending = explicit Welcome Pending
         OR blank after QA-Approved

    3. Provisioning
       Only opens after Welcome Approved.
       - Provisioning Pending = explicit Pending
         OR blank after Welcome Approved

    4. Dispatch
       Only opens after Provisioning reaches:
       - Connectivity: Committed
       - Connectivity: Order Provisioned

       Dispatch Pending =
       explicit Dispatch Pending
       OR blank after provisioning is ready.

    5. Confirmation
       Only opens after Dispatch Approved.

       Confirmation Pending =
       explicit Confirmation Pending
       OR blank after Dispatch Approved.

    Blank statuses are therefore used internally to determine
    whether the next stage is pending, but blanks are never
    displayed as their own category.

No:
    - Manual entry
    - Manual resolution state
    - SLA calculation
    - Ageing / breach / RAG logic
"""

from datetime import datetime, date
import re

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st


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
# CONFIG
# ============================================================

SPREADSHEET_ID = st.secrets.get(
    "SPREADSHEET_ID",
    "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ",
).strip()

CRM_MIRROR_WORKSHEET_GID = int(
    st.secrets.get(
        "CRM_MIRROR_WORKSHEET_GID",
        "1647226826",
    )
)

DATA_CACHE_TTL = int(
    st.secrets.get(
        "DATA_CACHE_TTL_SECONDS",
        300,
    )
)


# ============================================================
# EXACT GOOGLE SHEET HEADERS
# ============================================================

API_COLUMNS = {
    "sale_date": "Sale Date",
    "advisor": "Advisor (Created Username)",
    "customer": "Customer Name",
    "phone": "Phone Number",

    "quality": "Quality Status",
    "quality_remarks": "Quality Remarks (Quality Comments)",

    "welcome": "Welcome Call Status",
    "welcome_remarks": "Welcome Call Remarks (Welcome Comments)",

    "provisioning": "Provisioning Status",
    "provisioning_remarks": "Provisioning Remarks (Provisioning Comments)",

    "dispatch": "LetterStatus (Dispatch Status)",

    "confirmation": "Confirmation Status",
    "confirmation_comment": "Confirmation Comment",

    "live": "Committed (Live) Status (Onboarding Status)",

    "quality_cancel": "Cancellation Reason - quality",
    "welcome_cancel": "Cancellation Reason - welcome",
    "provisioning_cancel": "Cancellation/Rejection Reason - Provisioning",
    "dispatch_cancel": "Cancellation/Rejection Reason - Dispatch",
    "confirmation_cancel": "Cancellation/Rejection Reason - Confirmation",
    "onboarding_cancel": "Cancellation/Rejection Reason - Onboarding",
    "potential_cancel": "Cancellation/Rejection Reason - Potential Opportunity",
}


# ============================================================
# REQUIRED / OPTIONAL HEADERS
# ============================================================

REQUIRED_HEADERS = [
    API_COLUMNS["sale_date"],
    API_COLUMNS["advisor"],
    API_COLUMNS["customer"],
    API_COLUMNS["phone"],
    API_COLUMNS["quality"],
    API_COLUMNS["welcome"],
    API_COLUMNS["provisioning"],
    API_COLUMNS["dispatch"],
    API_COLUMNS["confirmation"],
    API_COLUMNS["live"],
]

OPTIONAL_HEADERS = [
    API_COLUMNS["quality_remarks"],
    API_COLUMNS["welcome_remarks"],
    API_COLUMNS["provisioning_remarks"],
    API_COLUMNS["confirmation_comment"],
    API_COLUMNS["quality_cancel"],
    API_COLUMNS["welcome_cancel"],
    API_COLUMNS["provisioning_cancel"],
    API_COLUMNS["dispatch_cancel"],
    API_COLUMNS["confirmation_cancel"],
    API_COLUMNS["onboarding_cancel"],
    API_COLUMNS["potential_cancel"],
]


# ============================================================
# STAGES
# ============================================================

STAGES = [
    "Quality",
    "Welcome",
    "Provisioning",
    "Dispatch",
    "Confirmation",
    "Live / Onboarding",
    "Potential Opportunity",
]

STAGE_ICONS = {
    "Quality": "🧪",
    "Welcome": "📞",
    "Provisioning": "⚙️",
    "Dispatch": "✉️",
    "Confirmation": "✅",
    "Live / Onboarding": "📡",
    "Potential Opportunity": "🎯",
}


# ============================================================
# WORKFLOW GATES
# ============================================================

QUALITY_APPROVED_STATUS = "qa approved"
WELCOME_APPROVED_STATUS = "welcome approved"
DISPATCH_APPROVED_STATUS = "dispatch approved"

PROVISIONING_READY_FOR_DISPATCH = {
    "connectivity committed",
    "connectivity order provisioned",
}


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1540px;
        padding-top: 1.25rem;
        padding-bottom: 2.2rem;
    }

    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px 12px;
        min-height: 108px;
        box-shadow: 0 4px 14px rgba(15,23,42,.045);
    }

    [data-testid="stMetricLabel"] {
        font-size: .66rem !important;
        font-weight: 850 !important;
        text-transform: uppercase !important;
        letter-spacing: .45px !important;
    }

    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-size: 1.85rem !important;
        font-weight: 900 !important;
    }

    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 5px 16px rgba(15,23,42,.035);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def safe_text(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return (
        str(value)
        .replace("\xa0", " ")
        .replace("\ufeff", "")
        .strip()
    )


def normalize_header(value) -> str:
    return re.sub(
        r"\s+",
        " ",
        safe_text(value),
    ).strip()


def normalize_status(value) -> str:
    text = safe_text(value).lower()

    text = text.replace("&", " and ")
    text = text.replace("|", " | ")
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_display_text(value) -> str:
    text = safe_text(value)

    text = (
        text
        .replace("<br>", " | ")
        .replace("<br/>", " | ")
        .replace("<br />", " | ")
    )

    text = re.sub(r"\s+", " ", text).strip()

    if text.lower() in {
        "nan",
        "none",
        "null",
        "nat",
    }:
        return ""

    return text


def clean_phone(value) -> str:
    text = safe_text(value)

    if not text:
        return ""

    text = re.sub(r"\.0+$", "", text)

    digits = re.sub(r"\D", "", text)

    if digits.startswith("44") and len(digits) in {11, 12}:
        digits = "0" + digits[2:]

    return digits or text


# ============================================================
# DATE HELPERS
# ============================================================

def parse_date(value):

    if value is None:
        return pd.NaT

    try:
        if pd.isna(value):
            return pd.NaT
    except Exception:
        pass

    text = safe_text(value)

    if not text:
        return pd.NaT

    for fmt in (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%m-%y",
        "%d/%m/%y",
    ):
        try:
            parsed = pd.to_datetime(
                text,
                format=fmt,
                errors="coerce",
            )

            if not pd.isna(parsed):
                return parsed

        except Exception:
            pass

    try:
        return pd.to_datetime(
            text,
            errors="coerce",
            dayfirst=True,
            format="mixed",
        )
    except Exception:
        return pd.to_datetime(
            text,
            errors="coerce",
            dayfirst=True,
        )


def format_date(value) -> str:

    parsed = parse_date(value)

    if pd.isna(parsed):
        return ""

    return parsed.strftime(
        "%d/%m/%Y"
    )


# ============================================================
# STATUS HELPERS
# ============================================================

def is_blank(value) -> bool:
    return normalize_status(value) == ""


def is_exact_status(value, expected) -> bool:
    return (
        normalize_status(value)
        == normalize_status(expected)
    )


def contains_pending(value) -> bool:
    return "pending" in normalize_status(value)


# ============================================================
# WORKFLOW GATES
# ============================================================

def quality_approved(value) -> bool:
    return is_exact_status(
        value,
        QUALITY_APPROVED_STATUS,
    )


def welcome_approved(value) -> bool:
    return is_exact_status(
        value,
        WELCOME_APPROVED_STATUS,
    )


def provisioning_ready_for_dispatch(value) -> bool:
    return (
        normalize_status(value)
        in PROVISIONING_READY_FOR_DISPATCH
    )


def dispatch_approved(value) -> bool:
    return is_exact_status(
        value,
        DISPATCH_APPROVED_STATUS,
    )


def confirmation_completed(value) -> bool:

    status = normalize_status(value)

    if not status:
        return False

    return any(
        term in status
        for term in [
            "approved",
            "confirmed",
            "confirmation complete",
            "complete",
            "completed",
        ]
    )


# ============================================================
# PENDING STAGE CLASSIFICATION
# ============================================================
#
# IMPORTANT:
#
# A blank downstream status is NOT displayed as "Blank".
#
# Instead:
#
#     QA-Approved + Welcome blank
#         -> Welcome = Pending
#
#     Welcome Approved + Provisioning blank
#         -> Provisioning = Pending
#
#     Provisioning Ready + Dispatch blank
#         -> Dispatch = Pending
#
#     Dispatch Approved + Confirmation blank
#         -> Confirmation = Pending
#
# This means the sale has reached that stage and is genuinely
# waiting there.


def classify_pending_stages(row) -> dict:

    result = {}

    quality = safe_text(
        row.get(
            API_COLUMNS["quality"],
            "",
        )
    )

    welcome = safe_text(
        row.get(
            API_COLUMNS["welcome"],
            "",
        )
    )

    provisioning = safe_text(
        row.get(
            API_COLUMNS["provisioning"],
            "",
        )
    )

    dispatch = safe_text(
        row.get(
            API_COLUMNS["dispatch"],
            "",
        )
    )

    confirmation = safe_text(
        row.get(
            API_COLUMNS["confirmation"],
            "",
        )
    )

    live = safe_text(
        row.get(
            API_COLUMNS["live"],
            "",
        )
    )

    # ========================================================
    # 1. QUALITY
    # ========================================================

    if normalize_status(quality) == "qa pending":
        result["Quality"] = "QA-Pending"

    # ========================================================
    # 2. WELCOME
    # ========================================================

    if quality_approved(quality):

        welcome_status = normalize_status(
            welcome
        )

        if welcome_status == "welcome followup":
            result["Welcome"] = "Followup"

        elif welcome_status == "welcome pending":
            result["Welcome"] = "Pending"

        elif not welcome_status:
            result["Welcome"] = "Pending"

    # ========================================================
    # 3. PROVISIONING
    # ========================================================

    if welcome_approved(welcome):

        provisioning_status = normalize_status(
            provisioning
        )

        if not provisioning_status:
            result["Provisioning"] = "Pending"

        elif contains_pending(
            provisioning_status
        ):
            result["Provisioning"] = "Pending"

    # ========================================================
    # 4. DISPATCH
    # ========================================================

    if provisioning_ready_for_dispatch(
        provisioning
    ):

        dispatch_status = normalize_status(
            dispatch
        )

        if not dispatch_status:
            result["Dispatch"] = "Pending"

        elif "dispatch pending" in dispatch_status:
            result["Dispatch"] = "Pending"

        elif "pending" in dispatch_status:
            result["Dispatch"] = "Pending"

    # ========================================================
    # 5. CONFIRMATION
    # ========================================================

    if dispatch_approved(dispatch):

        confirmation_status = normalize_status(
            confirmation
        )

        if not confirmation_status:
            result["Confirmation"] = "Pending"

        elif contains_pending(
            confirmation_status
        ):
            result["Confirmation"] = "Pending"

    # ========================================================
    # 6. LIVE / ONBOARDING
    # ========================================================

    if confirmation_completed(
        confirmation
    ):

        live_status = normalize_status(
            live
        )

        if not live_status:
            result["Live / Onboarding"] = "Pending"

        elif any(
            term in live_status
            for term in [
                "pending",
                "follow up",
                "followup",
                "in progress",
                "processing",
                "committed",
            ]
        ):
            result["Live / Onboarding"] = clean_display_text(
                live
            )

    # ========================================================
    # 7. POTENTIAL OPPORTUNITY
    # ========================================================

    fields = [
        API_COLUMNS["provisioning"],
        API_COLUMNS["welcome"],
        API_COLUMNS["quality_cancel"],
        API_COLUMNS["welcome_cancel"],
        API_COLUMNS["provisioning_cancel"],
        API_COLUMNS["potential_cancel"],
    ]

    for field in fields:

        if field not in row.index:
            continue

        if (
            "potential opportunity"
            in normalize_status(
                row[field]
            )
        ):
            result[
                "Potential Opportunity"
            ] = "Potential Opportunity"

            break

    return result


# ============================================================
# DISPLAY HELPERS
# ============================================================

def status_display(row, stage):

    mapping = {
        "Quality": API_COLUMNS["quality"],
        "Welcome": API_COLUMNS["welcome"],
        "Provisioning": API_COLUMNS["provisioning"],
        "Dispatch": API_COLUMNS["dispatch"],
        "Confirmation": API_COLUMNS["confirmation"],
        "Live / Onboarding": API_COLUMNS["live"],
    }

    if stage == "Potential Opportunity":
        return "Potential Opportunity"

    return clean_display_text(
        row.get(
            mapping.get(stage, ""),
            "",
        )
    )


def remarks_display(row, stage):

    mapping = {
        "Quality": API_COLUMNS["quality_remarks"],
        "Welcome": API_COLUMNS["welcome_remarks"],
        "Provisioning": API_COLUMNS["provisioning_remarks"],
        "Dispatch": API_COLUMNS["dispatch_cancel"],
        "Confirmation": API_COLUMNS["confirmation_comment"],
        "Live / Onboarding": API_COLUMNS["onboarding_cancel"],
        "Potential Opportunity": API_COLUMNS["potential_cancel"],
    }

    return clean_display_text(
        row.get(
            mapping.get(stage, ""),
            "",
        )
    )


# ============================================================
# RECORD KEY
# ============================================================

def make_record_key(
    sale_date,
    phone,
):

    parsed = parse_date(
        sale_date
    )

    date_part = (
        parsed.strftime(
            "%Y-%m-%d"
        )
        if not pd.isna(parsed)
        else ""
    )

    phone_part = clean_phone(
        phone
    )

    return (
        f"{date_part}|{phone_part}"
    )


# ============================================================
# BUILD QUEUE
# ============================================================

def build_queue_dataframe(
    source_df,
):

    rows = []

    for _, row in source_df.iterrows():

        stage_reasons = (
            classify_pending_stages(
                row
            )
        )

        if not stage_reasons:
            continue

        pending_stages = list(
            stage_reasons.keys()
        )

        pending_detail = "; ".join(
            f"{stage}: {reason}"
            for stage, reason
            in stage_reasons.items()
        )

        rows.append(
            {
                "Sale Date":
                    parse_date(
                        row.get(
                            API_COLUMNS[
                                "sale_date"
                            ]
                        )
                    ),

                "Advisor":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "advisor"
                            ]
                        )
                    ),

                "Customer Name":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "customer"
                            ]
                        )
                    ),

                "Phone Number":
                    clean_phone(
                        row.get(
                            API_COLUMNS[
                                "phone"
                            ]
                        )
                    ),

                "Pending Stage(s)":
                    ", ".join(
                        pending_stages
                    ),

                "Pending Detail":
                    pending_detail,

                "Pending Count":
                    len(
                        pending_stages
                    ),

                "Quality Status":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "quality"
                            ]
                        )
                    ),

                "Welcome Call Status":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "welcome"
                            ]
                        )
                    ),

                "Provisioning Status":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "provisioning"
                            ]
                        )
                    ),

                "Dispatch Status":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "dispatch"
                            ]
                        )
                    ),

                "Confirmation Status":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "confirmation"
                            ]
                        )
                    ),

                "Live / Onboarding Status":
                    clean_display_text(
                        row.get(
                            API_COLUMNS[
                                "live"
                            ]
                        )
                    ),

                "_QualityReason":
                    stage_reasons.get(
                        "Quality",
                        "",
                    ),

                "_WelcomeReason":
                    stage_reasons.get(
                        "Welcome",
                        "",
                    ),

                "_ProvisioningReason":
                    stage_reasons.get(
                        "Provisioning",
                        "",
                    ),

                "_DispatchReason":
                    stage_reasons.get(
                        "Dispatch",
                        "",
                    ),

                "_ConfirmationReason":
                    stage_reasons.get(
                        "Confirmation",
                        "",
                    ),

                "_LiveReason":
                    stage_reasons.get(
                        "Live / Onboarding",
                        "",
                    ),

                "_PotentialReason":
                    stage_reasons.get(
                        "Potential Opportunity",
                        "",
                    ),

                "Record Key":
                    make_record_key(
                        row.get(
                            API_COLUMNS[
                                "sale_date"
                            ]
                        ),
                        row.get(
                            API_COLUMNS[
                                "phone"
                            ]
                        ),
                    ),
            }
        )

    columns = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",
        "Pending Stage(s)",
        "Pending Detail",
        "Pending Count",
        "Quality Status",
        "Welcome Call Status",
        "Provisioning Status",
        "Dispatch Status",
        "Confirmation Status",
        "Live / Onboarding Status",
        "_QualityReason",
        "_WelcomeReason",
        "_ProvisioningReason",
        "_DispatchReason",
        "_ConfirmationReason",
        "_LiveReason",
        "_PotentialReason",
        "Record Key",
    ]

    if not rows:
        return pd.DataFrame(
            columns=columns
        )

    result = pd.DataFrame(
        rows
    )

    result = result.sort_values(
        by=[
            "Sale Date",
            "Customer Name",
        ],
        ascending=[
            False,
            True,
        ],
        na_position="last",
    ).reset_index(
        drop=True
    )

    return result[columns]


# ============================================================
# GOOGLE SHEET
# ============================================================

def load_google_sheet_data():

    info = st.secrets[
        "gcp_service_account"
    ]

    creds = (
        Credentials
        .from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )
    )

    client = gspread.authorize(
        creds
    )

    spreadsheet = client.open_by_key(
        SPREADSHEET_ID
    )

    try:

        worksheet = (
            spreadsheet
            .get_worksheet_by_id(
                CRM_MIRROR_WORKSHEET_GID
            )
        )

    except Exception as exc:

        raise RuntimeError(
            "Could not open Google Sheet "
            f"worksheet GID "
            f"{CRM_MIRROR_WORKSHEET_GID}: "
            f"{exc}"
        ) from exc

    records = (
        worksheet.get_all_records()
    )

    df = pd.DataFrame(
        records
    )

    if df.empty:
        raise ValueError(
            "The CRM mirror Google Sheet "
            "contains no records."
        )

    df.columns = [
        normalize_header(c)
        for c in df.columns
    ]

    missing = [
        c
        for c in REQUIRED_HEADERS
        if c not in df.columns
    ]

    if missing:

        raise ValueError(
            "Google Sheet is missing "
            "required CRM columns: "
            + ", ".join(missing)
        )

    fetched_at = (
        datetime.now()
        .strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )

    return (
        df,
        fetched_at,
    )


@st.cache_data(
    ttl=DATA_CACHE_TTL,
    show_spinner=False,
)
def fetch_google_sheet_data():

    return load_google_sheet_data()


# ============================================================
# LOAD
# ============================================================

try:

    sheet_df, fetched_at = (
        fetch_google_sheet_data()
    )

    queue_df = (
        build_queue_dataframe(
            sheet_df
        )
    )

except Exception as exc:

    st.error(
        "Unable to load the Sparta CRM "
        f"Google Sheet: {exc}"
    )

    st.stop()


# ============================================================
# HEADER
# ============================================================

header_left, header_right = st.columns(
    [5, 1],
    vertical_alignment="center",
)

with header_left:

    st.caption(
        "SPARTA CRM · OPERATIONS QUEUE"
    )

    st.title(
        "⏳ Sparta Pending Operations"
    )

    st.write(
        "Live records from the CRM mirror "
        "showing only workflow stages where "
        "work is genuinely pending. "
        "Downstream stages open only after "
        "the previous stage is completed."
    )

with header_right:

    st.caption(
        "Last Google Sheet refresh"
    )

    st.write(
        f"**{fetched_at}**"
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ Queue Controls"
    )

    st.caption(
        "Direct from the CRM mirror Google Sheet"
    )

    st.divider()

    st.metric(
        "Sheet Records",
        f"{len(sheet_df):,}",
    )

    st.metric(
        "Pending Sales",
        f"{len(queue_df):,}",
    )

    st.divider()

    st.caption(
        f"Cache TTL: "
        f"{DATA_CACHE_TTL:,} seconds"
    )

    if st.button(
        "↻ Refresh Google Sheet data",
        use_container_width=True,
    ):

        st.cache_data.clear()
        st.rerun()

    if not queue_df.empty:

        export_df = (
            queue_df
            .drop(
                columns=[
                    "_QualityReason",
                    "_WelcomeReason",
                    "_ProvisioningReason",
                    "_DispatchReason",
                    "_ConfirmationReason",
                    "_LiveReason",
                    "_PotentialReason",
                    "Record Key",
                ],
                errors="ignore",
            )
            .copy()
        )

        export_df[
            "Sale Date"
        ] = (
            pd.to_datetime(
                export_df[
                    "Sale Date"
                ],
                errors="coerce",
            )
            .dt.strftime(
                "%d/%m/%Y"
            )
        )

        export_bytes = (
            export_df
            .to_csv(
                index=False
            )
            .encode(
                "utf-8-sig"
            )
        )

        st.download_button(
            "📥 Export All Pending",
            data=export_bytes,
            file_name="Sparta_Pending_Operations.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# COUNTS
# ============================================================

def count_reason(
    column,
    value,
):

    if queue_df.empty:
        return 0

    return int(
        queue_df[
            column
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq(value)
        .sum()
    )


# Quality
quality_pending_count = count_reason(
    "_QualityReason",
    "QA-Pending",
)


# Welcome
welcome_followup_count = count_reason(
    "_WelcomeReason",
    "Followup",
)

welcome_pending_count = count_reason(
    "_WelcomeReason",
    "Pending",
)


# Provisioning
provisioning_pending_count = count_reason(
    "_ProvisioningReason",
    "Pending",
)


# Dispatch
dispatch_pending_count = count_reason(
    "_DispatchReason",
    "Pending",
)


# Confirmation
confirmation_pending_count = count_reason(
    "_ConfirmationReason",
    "Pending",
)


# Live / Onboarding
live_pending_count = (
    int(
        queue_df[
            "_LiveReason"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    )
    if not queue_df.empty
    else 0
)


# Potential Opportunity
potential_count = (
    int(
        queue_df[
            "_PotentialReason"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    )
    if not queue_df.empty
    else 0
)


stage_counts = {
    "Quality":
        quality_pending_count,

    "Welcome":
        welcome_followup_count
        + welcome_pending_count,

    "Provisioning":
        provisioning_pending_count,

    "Dispatch":
        dispatch_pending_count,

    "Confirmation":
        confirmation_pending_count,

    "Live / Onboarding":
        live_pending_count,

    "Potential Opportunity":
        potential_count,
}


# ============================================================
# KPI SECTION
# ============================================================

st.subheader(
    "📊 Pending Breakdown"
)

st.caption(
    "A blank downstream status becomes Pending only after "
    "the sale has reached that stage. Blank is not shown "
    "as a separate category."
)


row1 = st.columns(
    5,
    gap="small",
)

with row1[0]:
    st.metric(
        "🧪 QA-Pending",
        quality_pending_count,
    )

with row1[1]:
    st.metric(
        "📞 Welcome Followup",
        welcome_followup_count,
    )

with row1[2]:
    st.metric(
        "📞 Welcome Pending",
        welcome_pending_count,
    )

with row1[3]:
    st.metric(
        "⚙️ Provisioning Pending",
        provisioning_pending_count,
    )

with row1[4]:
    st.metric(
        "✉️ Dispatch Pending",
        dispatch_pending_count,
    )


row2 = st.columns(
    4,
    gap="small",
)

with row2[0]:
    st.metric(
        "✅ Confirmation Pending",
        confirmation_pending_count,
    )

with row2[1]:
    st.metric(
        "📡 Live / Onboarding",
        live_pending_count,
    )

with row2[2]:
    st.metric(
        "🎯 Potential Opportunity",
        potential_count,
    )

with row2[3]:
    st.metric(
        "📋 Total Pending Sales",
        len(queue_df),
    )


st.info(
    "Queue logic is sequential: "
    "QA-Pending stays in Quality; only QA-Approved records "
    "enter Welcome; only Welcome Approved records enter "
    "Provisioning; only dispatch-ready provisioning records "
    "enter Dispatch; and only Dispatch Approved records "
    "enter Confirmation."
)


# ============================================================
# FILTERS
# ============================================================

st.subheader(
    "🔎 Filters"
)

st.caption(
    "Filter the pending queues without changing the "
    "underlying CRM data."
)

filter_cols = st.columns(
    [2.0, 1.2, 1.2, 1.2]
)


with filter_cols[0]:

    search_text = st.text_input(
        "Search",
        placeholder=(
            "Customer, phone number or advisor…"
        ),
    )


sale_dates = (
    pd.to_datetime(
        queue_df["Sale Date"],
        errors="coerce",
    )
    if not queue_df.empty
    else pd.Series(
        dtype="datetime64[ns]"
    )
)

valid_dates = sale_dates.dropna()

if not valid_dates.empty:

    min_date = (
        valid_dates.min().date()
    )

    max_date = (
        valid_dates.max().date()
    )

else:

    min_date = date.today()
    max_date = date.today()


with filter_cols[1]:

    date_from = st.date_input(
        "Sale Date From",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY",
    )


with filter_cols[2]:

    date_to = st.date_input(
        "Sale Date To",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY",
    )


with filter_cols[3]:

    advisor_options = (
        sorted(
            [
                x
                for x in (
                    queue_df[
                        "Advisor"
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                if x
            ]
        )
        if not queue_df.empty
        else []
    )

    selected_advisor = st.selectbox(
        "Advisor",
        options=[
            "All Advisors"
        ] + advisor_options,
    )


stage_filter = st.multiselect(
    "Pending Stage",
    options=STAGES,
    format_func=lambda x:
        f"{STAGE_ICONS[x]} {x}",
    placeholder="All pending stages",
)


# ============================================================
# FILTER DATA
# ============================================================

filtered_df = queue_df.copy()

if not filtered_df.empty:

    filtered_df["_SaleDate"] = (
        pd.to_datetime(
            filtered_df[
                "Sale Date"
            ],
            errors="coerce",
        )
    )

    filtered_df = filtered_df[
        filtered_df[
            "_SaleDate"
        ]
        .dt.date
        .between(
            date_from,
            date_to,
            inclusive="both",
        )
    ]

    if (
        selected_advisor
        != "All Advisors"
    ):

        filtered_df = filtered_df[
            filtered_df[
                "Advisor"
            ]
            == selected_advisor
        ]

    if search_text.strip():

        needle = (
            search_text
            .strip()
        )

        blob = (
            filtered_df[
                [
                    "Customer Name",
                    "Phone Number",
                    "Advisor",
                ]
            ]
            .fillna("")
            .astype(str)
            .agg(
                " | ".join,
                axis=1,
            )
        )

        filtered_df = filtered_df[
            blob.str.contains(
                needle,
                case=False,
                regex=False,
                na=False,
            )
        ]

    if stage_filter:

        stage_regex = "|".join(
            re.escape(stage)
            for stage in stage_filter
        )

        filtered_df = filtered_df[
            filtered_df[
                "Pending Stage(s)"
            ]
            .fillna("")
            .str.contains(
                stage_regex,
                regex=True,
                na=False,
            )
        ]

    filtered_df = (
        filtered_df
        .drop(
            columns=[
                "_SaleDate"
            ],
            errors="ignore",
        )
    )


st.caption(
    f"Showing {len(filtered_df):,} "
    f"pending sale(s) from "
    f"{len(queue_df):,} total pending sale(s)."
)


# ============================================================
# ALL PENDING
# ============================================================

st.subheader(
    "📋 All Pending"
)

st.caption(
    "One row per sale. Pending Stage(s) shows only stages "
    "where the sale is genuinely pending."
)

all_display = (
    filtered_df
    .drop(
        columns=[
            "Record Key",
            "_QualityReason",
            "_WelcomeReason",
            "_ProvisioningReason",
            "_DispatchReason",
            "_ConfirmationReason",
            "_LiveReason",
            "_PotentialReason",
        ],
        errors="ignore",
    )
    .copy()
)

if not all_display.empty:

    all_display[
        "Sale Date"
    ] = (
        pd.to_datetime(
            all_display[
                "Sale Date"
            ],
            errors="coerce",
        )
        .dt.strftime(
            "%d/%m/%Y"
        )
    )

    st.dataframe(
        all_display,
        use_container_width=True,
        hide_index=True,
        height=min(
            610,
            max(
                200,
                120
                + len(all_display) * 35,
            ),
        ),
        column_config={

            "Sale Date":
                st.column_config.TextColumn(
                    "SALE DATE",
                    width="small",
                ),

            "Advisor":
                st.column_config.TextColumn(
                    "ADVISOR",
                    width="medium",
                ),

            "Customer Name":
                st.column_config.TextColumn(
                    "CUSTOMER NAME",
                    width="medium",
                ),

            "Phone Number":
                st.column_config.TextColumn(
                    "PHONE NUMBER",
                    width="medium",
                ),

            "Pending Stage(s)":
                st.column_config.TextColumn(
                    "PENDING STAGE(S)",
                    width="large",
                ),

            "Pending Detail":
                st.column_config.TextColumn(
                    "PENDING DETAIL",
                    width="large",
                ),

            "Pending Count":
                st.column_config.NumberColumn(
                    "OPEN STAGES",
                    format="%d",
                    width="small",
                ),
        },
    )

else:

    st.info(
        "No pending records match the current filters."
    )


# ============================================================
# STAGE QUEUES
# ============================================================

st.divider()

st.subheader(
    "🗂️ Stage Queues"
)

st.caption(
    "Each tab contains only sales that have actually reached "
    "that workflow stage and are still pending there."
)


queue_tabs = st.tabs(
    [
        f"{STAGE_ICONS[stage]} "
        f"{stage} "
        f"({stage_counts[stage]:,})"
        for stage in STAGES
    ]
)


stage_reason_columns = {
    "Quality": "_QualityReason",
    "Welcome": "_WelcomeReason",
    "Provisioning": "_ProvisioningReason",
    "Dispatch": "_DispatchReason",
    "Confirmation": "_ConfirmationReason",
    "Live / Onboarding": "_LiveReason",
    "Potential Opportunity": "_PotentialReason",
}


for tab, stage in zip(
    queue_tabs,
    STAGES,
):

    with tab:

        reason_column = (
            stage_reason_columns[
                stage
            ]
        )

        if filtered_df.empty:

            stage_df = pd.DataFrame()

        else:

            stage_df = (
                filtered_df[
                    filtered_df[
                        reason_column
                    ]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .ne("")
                ]
                .copy()
            )

        if stage_df.empty:

            st.success(
                f"No {stage} records are pending "
                "for the current filters."
            )

            continue

        display_rows = []

        for _, row in stage_df.iterrows():

            reason = safe_text(
                row.get(
                    reason_column,
                    "",
                )
            )

            source_rows = sheet_df[
                sheet_df.apply(
                    lambda source_row:
                        make_record_key(
                            source_row.get(
                                API_COLUMNS[
                                    "sale_date"
                                ]
                            ),
                            source_row.get(
                                API_COLUMNS[
                                    "phone"
                                ]
                            ),
                        )
                        == safe_text(
                            row.get(
                                "Record Key",
                                "",
                            )
                        ),
                    axis=1,
                )
            ]

            source_row = (
                source_rows.iloc[-1]
                if not source_rows.empty
                else None
            )

            display_rows.append(
                {
                    "Sale Date":
                        row.get(
                            "Sale Date"
                        ),

                    "Advisor":
                        row.get(
                            "Advisor",
                            "",
                        ),

                    "Customer Name":
                        row.get(
                            "Customer Name",
                            "",
                        ),

                    "Phone Number":
                        row.get(
                            "Phone Number",
                            "",
                        ),

                    "Pending Stage":
                        stage,

                    "Pending Type":
                        reason,

                    "Current Status":
                        (
                            status_display(
                                source_row,
                                stage,
                            )
                            if source_row
                            is not None
                            else ""
                        ),

                    "Remarks / Latest Note":
                        (
                            remarks_display(
                                source_row,
                                stage,
                            )
                            if source_row
                            is not None
                            else ""
                        ),

                    "Other Open Stages":
                        row.get(
                            "Pending Stage(s)",
                            "",
                        ),
                }
            )

        stage_display = pd.DataFrame(
            display_rows
        )

        stage_display[
            "Sale Date"
        ] = (
            pd.to_datetime(
                stage_display[
                    "Sale Date"
                ],
                errors="coerce",
            )
            .dt.strftime(
                "%d/%m/%Y"
            )
        )

        st.dataframe(
            stage_display,
            use_container_width=True,
            hide_index=True,
            height=min(
                620,
                max(
                    220,
                    120
                    + len(stage_display)
                    * 36,
                ),
            ),
            column_config={

                "Sale Date":
                    st.column_config.TextColumn(
                        "SALE DATE",
                        width="small",
                    ),

                "Advisor":
                    st.column_config.TextColumn(
                        "ADVISOR",
                        width="medium",
                    ),

                "Customer Name":
                    st.column_config.TextColumn(
                        "CUSTOMER NAME",
                        width="medium",
                    ),

                "Phone Number":
                    st.column_config.TextColumn(
                        "PHONE NUMBER",
                        width="medium",
                    ),

                "Pending Stage":
                    st.column_config.TextColumn(
                        "STAGE",
                        width="medium",
                    ),

                "Pending Type":
                    st.column_config.TextColumn(
                        "PENDING TYPE",
                        width="medium",
                    ),

                "Current Status":
                    st.column_config.TextColumn(
                        "CURRENT STATUS",
                        width="large",
                    ),

                "Remarks / Latest Note":
                    st.column_config.TextColumn(
                        "REMARKS / LATEST NOTE",
                        width="large",
                    ),

                "Other Open Stages":
                    st.column_config.TextColumn(
                        "OTHER OPEN STAGES",
                        width="large",
                    ),
            },
        )


# ============================================================
# RAW STATUS SNAPSHOT
# ============================================================

st.divider()

with st.expander(
    "🔍 View current CRM status fields",
    expanded=False,
):

    status_snapshot = (
        filtered_df
        .drop(
            columns=[
                "Record Key",
                "_QualityReason",
                "_WelcomeReason",
                "_ProvisioningReason",
                "_DispatchReason",
                "_ConfirmationReason",
                "_LiveReason",
                "_PotentialReason",
            ],
            errors="ignore",
        )
        .copy()
    )

    status_cols = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",
        "Quality Status",
        "Welcome Call Status",
        "Provisioning Status",
        "Dispatch Status",
        "Confirmation Status",
        "Live / Onboarding Status",
        "Pending Stage(s)",
        "Pending Detail",
    ]

    status_cols = [
        c
        for c in status_cols
        if c in status_snapshot.columns
    ]

    status_snapshot = status_snapshot[
        status_cols
    ]

    if not status_snapshot.empty:

        status_snapshot[
            "Sale Date"
        ] = (
            pd.to_datetime(
                status_snapshot[
                    "Sale Date"
                ],
                errors="coerce",
            )
            .dt.strftime(
                "%d/%m/%Y"
            )
        )

    st.dataframe(
        status_snapshot,
        use_container_width=True,
        hide_index=True,
        height=min(
            560,
            max(
                180,
                100
                + len(status_snapshot) * 34,
            ),
        ),
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

footer_left, footer_right = st.columns(2)

with footer_left:

    st.caption(
        "Sparta Pending Operations · "
        "Live Google Sheet queue"
    )

with footer_right:

    st.caption(
        f"Last Google Sheet fetch: "
        f"{fetched_at}"
    )
