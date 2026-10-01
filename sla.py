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
    :root {
        --sparta-bg: #f5f7fb;
        --sparta-card: #ffffff;
        --sparta-border: #e5eaf2;
        --sparta-text: #0f172a;
        --sparta-muted: #64748b;
        --sparta-blue: #2563eb;
        --sparta-blue-2: #4f46e5;
        --sparta-green: #16a34a;
        --sparta-yellow: #d97706;
        --sparta-red: #dc2626;
    }

    .stApp {
        background: radial-gradient(circle at top left, #eef4ff 0%, #f7f9fc 34%, var(--sparta-bg) 100%);
    }

    .block-container {
        max-width: 1560px;
        padding-top: 1rem;
        padding-bottom: 2.6rem;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 55%, #172033 100%);
        border-right: 1px solid rgba(255,255,255,.06);
    }

    [data-testid="stSidebar"] * {
        color: #e2e8f0;
    }

    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(255,255,255,.055);
        border: 1px solid rgba(255,255,255,.08);
        box-shadow: none;
    }

    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
    }

    .sparta-hero {
        position: relative;
        overflow: hidden;
        margin-bottom: 1.15rem;
        padding: 1.35rem 1.45rem;
        border: 1px solid #dbe5f4;
        border-radius: 22px;
        background: linear-gradient(135deg, #0f172a 0%, #172554 58%, #1d4ed8 100%);
        box-shadow: 0 18px 40px rgba(15,23,42,.14);
    }

    .sparta-hero::after {
        content: "";
        position: absolute;
        width: 240px;
        height: 240px;
        right: -80px;
        top: -120px;
        border-radius: 50%;
        background: rgba(255,255,255,.08);
    }

    .sparta-kicker {
        color: #93c5fd;
        font-size: .72rem;
        font-weight: 850;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin-bottom: .18rem;
    }

    .sparta-title {
        color: #ffffff;
        font-size: clamp(1.55rem, 2.5vw, 2.15rem);
        font-weight: 900;
        line-height: 1.08;
        margin: 0;
    }

    .sparta-subtitle {
        color: #cbd5e1;
        font-size: .92rem;
        line-height: 1.48;
        max-width: 900px;
        margin-top: .48rem;
    }

    .sparta-refresh {
        text-align: right;
        color: #cbd5e1;
        font-size: .73rem;
        line-height: 1.35;
        position: relative;
        z-index: 2;
    }

    .sparta-refresh strong {
        display: block;
        color: #ffffff;
        font-size: .86rem;
        margin-top: .15rem;
    }

    .sparta-section {
        margin-top: 1.15rem;
        margin-bottom: .65rem;
    }

    .sparta-section-title {
        color: var(--sparta-text);
        font-size: 1.12rem;
        font-weight: 900;
        letter-spacing: -.01em;
        margin-bottom: .08rem;
    }

    .sparta-section-caption {
        color: var(--sparta-muted);
        font-size: .82rem;
        line-height: 1.45;
    }

    .sparta-card {
        background: rgba(255,255,255,.94);
        border: 1px solid var(--sparta-border);
        border-radius: 18px;
        box-shadow: 0 8px 24px rgba(15,23,42,.055);
    }

    .sparta-kpis {
        display: grid;
        grid-template-columns: repeat(8, minmax(0, 1fr));
        gap: .7rem;
        margin: .55rem 0 .35rem;
    }

    .sparta-kpi {
        position: relative;
        overflow: hidden;
        padding: .85rem .85rem .72rem;
        min-height: 92px;
        border: 1px solid var(--sparta-border);
        border-radius: 16px;
        background: rgba(255,255,255,.96);
        box-shadow: 0 7px 20px rgba(15,23,42,.05);
    }

    .sparta-kpi::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: var(--sparta-blue);
    }

    .sparta-kpi-label {
        color: #64748b;
        font-size: .66rem;
        font-weight: 850;
        letter-spacing: .045em;
        text-transform: uppercase;
        line-height: 1.15;
    }

    .sparta-kpi-value {
        color: #0f172a;
        font-size: 1.42rem;
        font-weight: 900;
        line-height: 1.05;
        margin-top: .3rem;
    }

    .sparta-kpi-sub {
        color: #94a3b8;
        font-size: .64rem;
        margin-top: .28rem;
        white-space: nowrap;
    }

    .sparta-legend {
        display: flex;
        flex-wrap: wrap;
        gap: .5rem;
        margin: .55rem 0 .8rem;
    }

    .sparta-pill {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        padding: .34rem .62rem;
        border-radius: 999px;
        font-size: .7rem;
        font-weight: 800;
        border: 1px solid transparent;
    }

    .sparta-pill.green { background:#ecfdf5; color:#166534; border-color:#bbf7d0; }
    .sparta-pill.yellow { background:#fffbeb; color:#92400e; border-color:#fde68a; }
    .sparta-pill.red { background:#fef2f2; color:#991b1b; border-color:#fecaca; }

    .sparta-filter-box {
        padding: .95rem 1rem .8rem;
        margin-bottom: .9rem;
        border: 1px solid var(--sparta-border);
        border-radius: 18px;
        background: rgba(255,255,255,.9);
        box-shadow: 0 7px 20px rgba(15,23,42,.04);
    }

    [data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid var(--sparta-border);
        box-shadow: 0 8px 24px rgba(15,23,42,.055);
        background: #ffffff;
    }

    [data-testid="stDataFrame"] [role="columnheader"] {
        font-weight: 850;
    }

    .stButton > button, .stDownloadButton > button {
        border-radius: 11px;
        font-weight: 800;
    }

    .stTextInput > div > div,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        border-radius: 11px;
    }

    div[data-testid="stExpander"] {
        border: 1px solid var(--sparta-border);
        border-radius: 16px;
        background: rgba(255,255,255,.86);
        overflow: hidden;
    }

    @media (max-width: 1250px) {
        .sparta-kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    }

    @media (max-width: 720px) {
        .sparta-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .sparta-refresh { text-align: left; margin-top: .5rem; }
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


def potential_opportunity_reason(row) -> str:
    """Return the Potential Opportunity subtype for a CRM row.

    Rework in Quality is treated as Potential Opportunity. Explicit
    Potential Opportunity Followup is kept as a separate subtype.
    """

    quality_status = normalize_status(
        row.get(API_COLUMNS["quality"], "")
    )

    # Every Quality = Rework record belongs to Potential Opportunity.
    if quality_status == "rework":
        # An explicit follow-up marker elsewhere still takes precedence.
        pass

    potential_fields = [
        API_COLUMNS["potential_cancel"],
        API_COLUMNS["quality_cancel"],
        API_COLUMNS["welcome_cancel"],
        API_COLUMNS["provisioning_cancel"],
        API_COLUMNS["dispatch_cancel"],
        API_COLUMNS["confirmation_cancel"],
        API_COLUMNS["onboarding_cancel"],
        API_COLUMNS["provisioning"],
        API_COLUMNS["welcome"],
        API_COLUMNS["quality"],
    ]

    found_potential = False
    found_followup = False

    for field in potential_fields:
        if field not in row.index:
            continue

        status = normalize_status(row[field])
        if not status:
            continue

        # Exact/embedded Potential Opportunity Followup is a separate subtype.
        if (
            "potential opportunity followup" in status
            or "potential opportunity follow up" in status
        ):
            found_potential = True
            found_followup = True
            continue

        # Some CRM exports may store only "Followup" in the dedicated
        # Potential Opportunity reason field.
        if (
            field == API_COLUMNS["potential_cancel"]
            and status in {"followup", "follow up"}
        ):
            found_potential = True
            found_followup = True
            continue

        if "potential opportunity" in status:
            found_potential = True

    if found_followup:
        return "Followup"

    if found_potential or quality_status == "rework":
        return "Pending"

    return ""


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

    quality_status = normalize_status(quality)

    if quality_status == "qa pending":
        result["Quality"] = "QA-Pending"

    # Rework is no longer treated as a Quality queue item.
    # It is routed into Potential Opportunity below.

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

    potential_reason = potential_opportunity_reason(row)

    if potential_reason:
        result["Potential Opportunity"] = potential_reason

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
# TABLE DISPLAY / COLOUR HELPERS
# ============================================================

# These are the column names used inside queue_df / the All Pending table.
# Some CRM source headers differ from the queue display names (notably
# Dispatch and Live / Onboarding), so the display layer must use these
# queue columns rather than the raw API header names.
SEQUENTIAL_STAGE_FIELDS = {
    "Quality": "Quality Status",
    "Welcome": "Welcome Call Status",
    "Provisioning": "Provisioning Status",
    "Dispatch": "Dispatch Status",
    "Confirmation": "Confirmation Status",
    "Live / Onboarding": "Live / Onboarding Status",
}

SEQUENTIAL_STAGE_DISPLAY_COLUMNS = [
    "Quality",
    "Welcome",
    "Provisioning",
    "Dispatch",
    "Confirmation",
    "Live / Onboarding",
]

RED_STATUS_TERMS = (
    "cancel",
    "reject",
    "rejection",
    "qa reject",
    "declined",
    "decline",
    "failed",
    "failure",
)

YELLOW_STATUS_TERMS = (
    "pending",
    "followup",
    "follow up",
    "rework",
    "delay",
    "chasing",
    "ringing",
    "in progress",
    "processing",
    "other work",
    "other-work",
    "potential opportunity",
)

GREEN_STATUS_TERMS = (
    "approved",
    "completed",
    "complete",
    "confirmed",
    "dispatched",
    "provisioned",
    "processed",
    "live",
    "committed",
    "accepted",
    "order provisioned",
)


def all_pending_display_status(row, stage) -> str:
    """Show every sequential workflow stage; blanks become Pending."""
    if stage == "Potential Opportunity":
        reason = safe_text(row.get("_PotentialReason", ""))
        if reason == "Followup":
            return "Followup"
        if reason == "Pending":
            return "Potential Opportunity"
        return "—"

    field = SEQUENTIAL_STAGE_FIELDS.get(stage)
    value = clean_display_text(row.get(field, "")) if field else ""
    return value if value else "Pending"


def status_cell_style(value) -> str:
    """Traffic-light styling for workflow states."""
    text = normalize_status(value)

    if text in {"", "—", "na", "n/a"}:
        return ""

    if any(term in text for term in RED_STATUS_TERMS):
        return (
            "background-color:#fee2e2; color:#991b1b; "
            "font-weight:800; border-left:4px solid #dc2626;"
        )

    if any(term in text for term in GREEN_STATUS_TERMS):
        return (
            "background-color:#dcfce7; color:#166534; "
            "font-weight:800; border-left:4px solid #16a34a;"
        )

    # Anything explicitly pending / in-progress, including blanks converted
    # to Pending, is shown as the active yellow workflow state.
    if any(term in text for term in YELLOW_STATUS_TERMS):
        return (
            "background-color:#fef3c7; color:#92400e; "
            "font-weight:800; border-left:4px solid #f59e0b;"
        )

    # Unknown non-empty states are treated as active work rather than hidden.
    return (
        "background-color:#fef3c7; color:#92400e; "
        "font-weight:800; border-left:4px solid #f59e0b;"
    )


def build_all_pending_display(dataframe) -> pd.DataFrame:
    """Create the workflow-style table used by the main All Pending view."""
    columns = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",
        *SEQUENTIAL_STAGE_DISPLAY_COLUMNS,
        "Potential Opportunity",
    ]

    if dataframe.empty:
        return pd.DataFrame(columns=columns)

    display_rows = []

    for _, row in dataframe.iterrows():
        display_rows.append(
            {
                "Sale Date": row.get("Sale Date"),
                "Advisor": clean_display_text(row.get("Advisor", "")),
                "Customer Name": clean_display_text(row.get("Customer Name", "")),
                "Phone Number": clean_phone(row.get("Phone Number", "")),
                **{
                    stage: all_pending_display_status(row, stage)
                    for stage in SEQUENTIAL_STAGE_DISPLAY_COLUMNS
                },
                "Potential Opportunity": all_pending_display_status(
                    row, "Potential Opportunity"
                ),
            }
        )

    result = pd.DataFrame(display_rows, columns=columns)
    result["Sale Date"] = pd.to_datetime(
        result["Sale Date"], errors="coerce"
    ).dt.strftime("%d/%m/%Y")
    result["Sale Date"] = result["Sale Date"].fillna("")
    return result


def build_date_breakdown(dataframe) -> pd.DataFrame:
    """Daily sale-date view of distinct pending sales and pending stages."""
    columns = [
        "Sale Date",
        "Pending Sales",
        "Quality",
        "Welcome",
        "Provisioning",
        "Dispatch",
        "Confirmation",
        "Live / Onboarding",
        "Potential Opportunity",
    ]

    if dataframe.empty:
        return pd.DataFrame(columns=columns)

    work = dataframe.copy()
    work["_BreakdownDate"] = pd.to_datetime(
        work["Sale Date"], errors="coerce"
    ).dt.normalize()
    work = work[work["_BreakdownDate"].notna()].copy()

    if work.empty:
        return pd.DataFrame(columns=columns)

    records = []
    reason_columns = {
        "Quality": "_QualityReason",
        "Welcome": "_WelcomeReason",
        "Provisioning": "_ProvisioningReason",
        "Dispatch": "_DispatchReason",
        "Confirmation": "_ConfirmationReason",
        "Live / Onboarding": "_LiveReason",
        "Potential Opportunity": "_PotentialReason",
    }

    for day, day_df in work.groupby("_BreakdownDate", sort=False):
        record = {
            "Sale Date": day.strftime("%d/%m/%Y"),
            "Pending Sales": int(day_df["Record Key"].nunique()),
        }
        for stage, reason_col in reason_columns.items():
            record[stage] = int(
                day_df[reason_col]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .sum()
            )
        records.append(record)

    result = pd.DataFrame(records, columns=columns)
    return result.sort_values(
        "Sale Date",
        key=lambda s: pd.to_datetime(s, format="%d/%m/%Y", errors="coerce"),
        ascending=False,
    ).reset_index(drop=True)


def style_workflow_table(dataframe):
    """Apply traffic-light styling only to workflow status columns."""
    return dataframe.style.map(
        status_cell_style,
        subset=[c for c in SEQUENTIAL_STAGE_DISPLAY_COLUMNS + ["Potential Opportunity"]
                if c in dataframe.columns],
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
    [5.2, 1.4],
    vertical_alignment="center",
)

with header_left:
    st.markdown(
        f"""
        <div class="sparta-hero">
            <div class="sparta-kicker">SPARTA CRM · OPERATIONS QUEUE</div>
            <div class="sparta-title">⏳ Sparta Pending Operations</div>
            <div class="sparta-subtitle">
                A live operational view of records waiting at each workflow stage.
                Downstream stages appear only after the preceding stage is completed.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown(
        f"""
        <div class="sparta-hero" style="height:100%;">
            <div class="sparta-refresh">
                Last Google Sheet refresh
                <strong>{fetched_at}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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
                    "Pending Stage(s)",
                    "Pending Detail",
                    "Pending Count",
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
potential_pending_count = count_reason(
    "_PotentialReason",
    "Pending",
)

potential_followup_count = count_reason(
    "_PotentialReason",
    "Followup",
)

potential_count = (
    potential_pending_count + potential_followup_count
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

st.markdown(
    """
    <div class="sparta-section">
        <div class="sparta-section-title">📊 Pending Breakdown</div>
        <div class="sparta-section-caption">
            Distinct pending sales by workflow stage. A sale can appear in more than one stage when multiple stages remain open.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

welcome_total_count = welcome_followup_count + welcome_pending_count

kpi_items = [
    ("🧪", "QA", quality_pending_count, "QA-Pending"),
    ("📞", "Welcome", welcome_total_count, f"{welcome_pending_count:,} pending · {welcome_followup_count:,} follow-up"),
    ("⚙️", "Provisioning", provisioning_pending_count, "Pending"),
    ("✉️", "Dispatch", dispatch_pending_count, "Pending"),
    ("✅", "Confirmation", confirmation_pending_count, "Pending"),
    ("📡", "Onboarding", live_pending_count, "Pending"),
    ("🎯", "Potential", potential_count, f"{potential_pending_count:,} pending · {potential_followup_count:,} follow-up"),
    ("📋", "Pending Sales", len(queue_df), "Distinct sales"),
]

card_html = '<div class="sparta-kpis">'
for icon, label, value, sub in kpi_items:
    card_html += (
        '<div class="sparta-kpi">'
        f'<div class="sparta-kpi-label">{icon} {label}</div>'
        f'<div class="sparta-kpi-value">{value:,}</div>'
        f'<div class="sparta-kpi-sub">{sub}</div>'
        '</div>'
    )
card_html += '</div>'

st.markdown(card_html, unsafe_allow_html=True)

st.markdown(
    """
    <div class="sparta-legend">
        <span class="sparta-pill green">🟢 Completed / moved forward</span>
        <span class="sparta-pill yellow">🟡 Pending / active</span>
        <span class="sparta-pill red">🔴 Ended / rejected</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "Workflow is sequential: QA → Welcome → Provisioning → Dispatch → "
    "Confirmation → Onboarding. Blank downstream statuses are treated as "
    "Pending once the sale has reached that stage."
)

# ============================================================
# FILTERS
# ============================================================

st.markdown(
    """
    <div class="sparta-section">
        <div class="sparta-section-title">🔎 Filters</div>
        <div class="sparta-section-caption">
            Narrow the operational queue by sale date, advisor, search text, or pending workflow stage.
        </div>
    </div>
    <div class="sparta-filter-box">
    """,
    unsafe_allow_html=True,
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


st.markdown("</div>", unsafe_allow_html=True)

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
# DATE-OF-SALE BREAKDOWN
# ============================================================

st.markdown(
    """
    <div class="sparta-section">
        <div class="sparta-section-title">📅 Pending by Sale Date</div>
        <div class="sparta-section-caption">
            Daily view of pending sales and the stages contributing to each sale date. This follows the filters above.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

date_breakdown = build_date_breakdown(filtered_df)

if date_breakdown.empty:
    st.info("No date-wise pending records match the current filters.")
else:
    date_display = date_breakdown.copy()
    date_numeric_cols = [
        "Pending Sales",
        "Quality",
        "Welcome",
        "Provisioning",
        "Dispatch",
        "Confirmation",
        "Live / Onboarding",
        "Potential Opportunity",
    ]

    for col in date_numeric_cols:
        if col in date_display.columns:
            date_display[col] = date_display[col].apply(
                lambda value: "-" if int(value) == 0 else f"{int(value):,}"
            )

    st.dataframe(
        date_display,
        use_container_width=True,
        hide_index=True,
        height=min(430, max(190, 92 + len(date_display) * 34)),
        column_config={
            "Sale Date": st.column_config.TextColumn(
                "SALE DATE", width="small"
            ),
            "Pending Sales": st.column_config.TextColumn(
                "PENDING SALES", width="small"
            ),
            "Quality": st.column_config.TextColumn(
                "QUALITY", width="small"
            ),
            "Welcome": st.column_config.TextColumn(
                "WELCOME", width="small"
            ),
            "Provisioning": st.column_config.TextColumn(
                "PROVISIONING", width="small"
            ),
            "Dispatch": st.column_config.TextColumn(
                "DISPATCH", width="small"
            ),
            "Confirmation": st.column_config.TextColumn(
                "CONFIRMATION", width="small"
            ),
            "Live / Onboarding": st.column_config.TextColumn(
                "ONBOARDING", width="small"
            ),
            "Potential Opportunity": st.column_config.TextColumn(
                "POTENTIAL", width="small"
            ),
        },
    )

# ============================================================
# ALL PENDING STAGE RADIO FILTER
# ============================================================

st.markdown(
    """
    <div class="sparta-section">
        <div class="sparta-section-title">🎯 Quick Pending View</div>
        <div class="sparta-section-caption">
            Select one pending stage to focus the All Pending table.
            “All Pending” is selected by default.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

radio_options = ["All Pending"] + STAGES

radio_reason_columns = {
    "Quality": "_QualityReason",
    "Welcome": "_WelcomeReason",
    "Provisioning": "_ProvisioningReason",
    "Dispatch": "_DispatchReason",
    "Confirmation": "_ConfirmationReason",
    "Live / Onboarding": "_LiveReason",
    "Potential Opportunity": "_PotentialReason",
}

radio_counts = {"All Pending": len(filtered_df)}
for _stage, _reason_col in radio_reason_columns.items():
    radio_counts[_stage] = int(
        filtered_df[_reason_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    ) if not filtered_df.empty else 0

selected_pending_stage = st.radio(
    "Pending stage",
    options=radio_options,
    index=0,
    horizontal=True,
    label_visibility="collapsed",
    format_func=lambda stage: (
        f"All Pending · {radio_counts[stage]:,}"
        if stage == "All Pending"
        else f"{STAGE_ICONS[stage]} {stage} · {radio_counts[stage]:,}"
    ),
)

all_pending_df = filtered_df.copy()

if (
    selected_pending_stage != "All Pending"
    and not all_pending_df.empty
):
    selected_reason_column = radio_reason_columns[selected_pending_stage]
    all_pending_df = all_pending_df[
        all_pending_df[selected_reason_column]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()


# ============================================================
# ALL PENDING
# ============================================================

st.markdown(
    """
    <div class="sparta-section">
        <div class="sparta-section-title">📋 All Pending</div>
        <div class="sparta-section-caption">
            One row per pending sale. Scan the entire workflow path in a single view; downstream blanks are shown as Pending.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

all_display = build_all_pending_display(all_pending_df)

if all_display.empty:
    st.info("No pending records match the current filters.")
else:
    st.dataframe(
        style_workflow_table(all_display),
        use_container_width=True,
        hide_index=True,
        height=min(
            660,
            max(240, 120 + len(all_display) * 35),
        ),
        column_config={
            "Sale Date": st.column_config.TextColumn(
                "SALE DATE", width="small"
            ),
            "Advisor": st.column_config.TextColumn(
                "ADVISOR", width="medium"
            ),
            "Customer Name": st.column_config.TextColumn(
                "CUSTOMER NAME", width="medium"
            ),
            "Phone Number": st.column_config.TextColumn(
                "PHONE NUMBER", width="medium"
            ),
            "Quality": st.column_config.TextColumn(
                "QUALITY", width="medium"
            ),
            "Welcome": st.column_config.TextColumn(
                "WELCOME", width="medium"
            ),
            "Provisioning": st.column_config.TextColumn(
                "PROVISIONING", width="medium"
            ),
            "Dispatch": st.column_config.TextColumn(
                "DISPATCH", width="medium"
            ),
            "Confirmation": st.column_config.TextColumn(
                "CONFIRMATION", width="medium"
            ),
            "Live / Onboarding": st.column_config.TextColumn(
                "LIVE / ONBOARDING", width="medium"
            ),
            "Potential Opportunity": st.column_config.TextColumn(
                "POTENTIAL", width="medium"
            ),
        },
    )


# ============================================================
# RAW STATUS SNAPSHOT
# ============================================================

st.markdown(
    """
    <div class="sparta-section">
        <div class="sparta-section-title">🔍 Current CRM Status</div>
        <div class="sparta-section-caption">
            Optional raw status snapshot for the records currently matching your filters.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander(
    "Open raw CRM status snapshot",
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

footer_left, footer_right = st.columns([3, 1])

with footer_left:
    st.markdown(
        '<div style="color:#64748b;font-size:.74rem;font-weight:700;">Sparta Pending Operations · Live Google Sheet queue</div>', 
        unsafe_allow_html=True,
    )

with footer_right:
    st.markdown(
        f'<div style="color:#94a3b8;font-size:.72rem;text-align:right;">Last fetch · {fetched_at}</div>', 
        unsafe_allow_html=True,
    )
