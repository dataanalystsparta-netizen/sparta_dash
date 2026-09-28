"""
SPARTA PENDING OPERATIONS — GOOGLE SHEET QUEUE
================================================

Live operational queue driven by the CRM data mirrored into Google Sheets.

The dashboard reads the dedicated Google worksheet directly. The CRM API is
upstream of the separate sync process and is not called by this app.

Workflow stages tracked:

    Quality
        ↓
    Welcome
        ↓
    Provisioning
        ↓
    Letter Dispatch
        ↓
    Confirmation
        ↓
    Live / Onboarding

Potential Opportunity remains separately detectable from the CRM fields.

IMPORTANT QUEUE RULE
--------------------

The queue is SEQUENTIAL.

A sale only becomes pending in the next stage after the previous stage has
successfully released it into that stage.

Examples:

    QA-Pending
        → Quality only

    QA-Approved + Welcome Pending
        → Welcome Pending only

    QA-Approved + Welcome Approved + Provisioning blank
        → Provisioning Blank only

    Provisioning = Committed + Dispatch Pending
        → Dispatch Pending only

    Dispatch Approved + Confirmation blank
        → Confirmation Blank only

A blank downstream status is therefore NOT automatically treated as pending.

Blank means:
    "This sale has reached this stage, but the stage has not yet started."

The dashboard deliberately has:
    - NO manual entry
    - NO manual resolution state
    - NO SLA calculation
    - NO ageing / breach / RAG logic
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
    st.secrets.get("CRM_MIRROR_WORKSHEET_GID", "1647226826")
)

DATA_CACHE_TTL = int(
    st.secrets.get("DATA_CACHE_TTL_SECONDS", 300)
)


# ============================================================
# EXACT GOOGLE SHEET HEADERS
# ============================================================

API_COLUMNS = {
    "sale_date": "Sale Date",
    "advisor": "Advisor (Created Username)",
    "customer": "Customer Name",
    "phone": "Phone Number",

    # Workflow
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

    # Reasons
    "quality_cancel": "Cancellation Reason - quality",
    "welcome_cancel": "Cancellation Reason - welcome",
    "provisioning_cancel": "Cancellation/Rejection Reason - Provisioning",
    "dispatch_cancel": "Cancellation/Rejection Reason - Dispatch",
    "confirmation_cancel": "Cancellation/Rejection Reason - Confirmation",
    "onboarding_cancel": "Cancellation/Rejection Reason - Onboarding",
    "potential_cancel": "Cancellation/Rejection Reason - Potential Opportunity",
}


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
# STAGE DEFINITIONS
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

STAGE_COLORS = {
    "Quality": "#f97316",
    "Welcome": "#eab308",
    "Provisioning": "#8b5cf6",
    "Dispatch": "#06b6d4",
    "Confirmation": "#10b981",
    "Live / Onboarding": "#2563eb",
    "Potential Opportunity": "#ec4899",
}


# ============================================================
# QUEUE BUCKET DEFINITIONS
# ============================================================

QUEUE_BUCKETS = {
    "Quality": [
        "QA-Pending",
    ],
    "Welcome": [
        "Welcome Pending",
        "Welcome Followup",
        "Welcome Blank",
    ],
    "Provisioning": [
        "Provisioning Pending",
        "Provisioning Blank",
    ],
    "Dispatch": [
        "Dispatch Pending",
        "Dispatch Blank",
    ],
    "Confirmation": [
        "Confirmation Pending",
        "Confirmation Blank",
    ],
    "Live / Onboarding": [
        "Live / Onboarding Pending",
    ],
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

    .hero {
        padding: 22px 24px;
        border-radius: 20px;
        color: white;
        background:
            radial-gradient(circle at 88% 10%, rgba(6,182,212,.22), transparent 28%),
            radial-gradient(circle at 4% 100%, rgba(59,130,246,.25), transparent 35%),
            linear-gradient(135deg, #09142f 0%, #10275a 60%, #143a70 100%);
        border: 1px solid rgba(255,255,255,.08);
        box-shadow: 0 16px 35px rgba(15,23,42,.11);
        margin-bottom: 16px;
    }

    .hero-kicker {
        font-size: .66rem;
        text-transform: uppercase;
        letter-spacing: 1.6px;
        font-weight: 900;
        color: #8db4ff;
        margin-bottom: 3px;
    }

    .hero-title {
        font-size: 1.75rem;
        font-weight: 900;
        letter-spacing: -.03em;
        margin: 0;
    }

    .hero-subtitle {
        color: #c5d4f3;
        font-size: .82rem;
        margin-top: 6px;
        max-width: 920px;
    }

    .hero-right {
        text-align: right;
        color: #a9bde2;
        font-size: .70rem;
        padding-top: 7px;
    }

    .hero-right strong {
        display: inline-block;
        margin-top: 4px;
        color: #fff;
        font-size: .84rem;
    }

    [data-testid="stMetric"] {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px 12px;
        min-height: 118px;
        box-shadow: 0 4px 14px rgba(15,23,42,.045);
    }

    [data-testid="stMetricLabel"] {
        font-size: .68rem !important;
        font-weight: 850 !important;
        text-transform: uppercase !important;
        letter-spacing: .55px !important;
    }

    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-size: 1.9rem !important;
        font-weight: 900 !important;
    }

    .queue-note {
        border: 1px solid #dbeafe;
        background: #f8fbff;
        border-radius: 12px;
        padding: 11px 14px;
        color: #475569;
        font-size: .80rem;
        margin: 12px 0 16px;
    }

    .section-title {
        color: #0f172a;
        font-size: 1.14rem;
        font-weight: 850;
        margin: 8px 0 3px;
    }

    .section-subtitle {
        color: #64748b;
        font-size: .78rem;
        margin-bottom: 10px;
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

    return str(value).strip()


def normalize_header(value) -> str:
    return re.sub(
        r"\s+",
        " ",
        safe_text(value).replace("\ufeff", ""),
    ).strip()


def normalize_status(value) -> str:
    text = safe_text(value).lower()

    text = text.replace("&", " and ")
    text = text.replace("\u00a0", " ")

    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


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

    return pd.to_datetime(
        text,
        errors="coerce",
        dayfirst=True,
        format="mixed",
    )


def format_date(value) -> str:
    parsed = parse_date(value)

    if pd.isna(parsed):
        return ""

    return parsed.strftime("%d/%m/%Y")


def make_record_key(sale_date, phone) -> str:
    parsed = parse_date(sale_date)

    date_part = (
        parsed.strftime("%Y-%m-%d")
        if not pd.isna(parsed)
        else ""
    )

    phone_part = clean_phone(phone)

    return f"{date_part}|{phone_part}"


# ============================================================
# STATUS HELPERS
# ============================================================

def is_blank(value) -> bool:
    return normalize_status(value) == ""


def is_qa_pending(value) -> bool:
    return normalize_status(value) == "qa pending"


def is_qa_approved(value) -> bool:
    return normalize_status(value) == "qa approved"


def is_welcome_pending(value) -> bool:
    return normalize_status(value) == "welcome pending"


def is_welcome_followup(value) -> bool:
    return normalize_status(value) == "welcome followup"


def is_welcome_approved(value) -> bool:
    return normalize_status(value) == "welcome approved"


def is_provisioning_pending(value) -> bool:
    status = normalize_status(value)

    if not status:
        return False

    # Explicit/open provisioning work.
    if "pending" in status:
        return True

    if "delayed" in status:
        return True

    if "rework" in status:
        return True

    if "send for rework" in status:
        return True

    return False


def is_provisioning_approved(value) -> bool:
    """
    These provisioning outcomes release the record into Dispatch.

    From the CRM sample:
        Connectivity: Committed
        Connectivity: Order Provisioned

    are treated as successful progression.

    Cancelled / delayed / rework / pending statuses do not release the
    record into Dispatch.
    """

    status = normalize_status(value)

    if not status:
        return False

    if "order cancelled" in status:
        return False

    if "cancelled" in status or "canceled" in status:
        return False

    if "rework" in status:
        return False

    if "pending" in status:
        return False

    if "delayed" in status:
        return False

    if "order provisioned" in status:
        return True

    if "committed" in status:
        return True

    return False


def is_dispatch_pending(value) -> bool:
    status = normalize_status(value)

    return status == "dispatch pending"


def is_dispatch_approved(value) -> bool:
    status = normalize_status(value)

    return status == "dispatch approved"


def is_confirmation_pending(value) -> bool:
    status = normalize_status(value)

    return "pending" in status


def is_confirmation_approved(value) -> bool:
    status = normalize_status(value)

    if not status:
        return False

    approval_terms = [
        "approved",
        "confirmed",
        "confirmation complete",
        "completed",
        "complete",
        "done",
    ]

    return any(term in status for term in approval_terms)


def is_live_pending(value) -> bool:
    status = normalize_status(value)

    if not status:
        return True

    if "live" in status:
        return False

    if "active" in status:
        return False

    if "completed" in status:
        return False

    if "complete" in status:
        return False

    if "cancelled" in status or "canceled" in status:
        return False

    return (
        "committed" in status
        or "pending" in status
        or "follow up" in status
        or "followup" in status
        or "processing" in status
        or "in progress" in status
    )


# ============================================================
# POTENTIAL OPPORTUNITY
# ============================================================

def pending_potential_opportunity(row) -> bool:
    """
    Potential Opportunity remains a separate CRM-derived indicator.

    It does not control the main sequential workflow.
    """

    fields = [
        API_COLUMNS["provisioning"],
        API_COLUMNS["welcome"],
        API_COLUMNS["quality_cancel"],
        API_COLUMNS["welcome_cancel"],
        API_COLUMNS["provisioning_cancel"],
        API_COLUMNS["potential_cancel"],
    ]

    for field in fields:
        if field in row.index:
            if "potential opportunity" in normalize_status(row[field]):
                return True

    return False


# ============================================================
# SEQUENTIAL WORKFLOW CLASSIFICATION
# ============================================================

def classify_current_queue(row):
    """
    Determine the CURRENT pending queue for a record.

    This is deliberately sequential.

    The function returns:

        stage
        bucket

    or:

        None, None

    for records which have either:
        - not yet reached a stage,
        - completed the workflow,
        - been rejected,
        - been cancelled,
        - or otherwise have no current open queue.

    IMPORTANT:

    A blank status only counts after the previous stage has qualified.

    Example:

        QA-Pending
            -> Quality / QA-Pending

        QA-Approved + Welcome blank
            -> Welcome / Welcome Blank

        QA-Approved + Welcome Approved + Provisioning blank
            -> Provisioning / Provisioning Blank
    """

    quality = row.get(
        API_COLUMNS["quality"],
        "",
    )

    welcome = row.get(
        API_COLUMNS["welcome"],
        "",
    )

    provisioning = row.get(
        API_COLUMNS["provisioning"],
        "",
    )

    dispatch = row.get(
        API_COLUMNS["dispatch"],
        "",
    )

    confirmation = row.get(
        API_COLUMNS["confirmation"],
        "",
    )

    live = row.get(
        API_COLUMNS["live"],
        "",
    )

    # --------------------------------------------------------
    # 1. QUALITY
    # --------------------------------------------------------

    if is_qa_pending(quality):
        return "Quality", "QA-Pending"

    # Anything other than QA-Approved does NOT move downstream.
    if not is_qa_approved(quality):
        return None, None

    # --------------------------------------------------------
    # 2. WELCOME
    # --------------------------------------------------------

    if is_blank(welcome):
        return "Welcome", "Welcome Blank"

    if is_welcome_pending(welcome):
        return "Welcome", "Welcome Pending"

    if is_welcome_followup(welcome):
        return "Welcome", "Welcome Followup"

    # Welcome rejected / any other non-approved result:
    # do not move into Provisioning.
    if not is_welcome_approved(welcome):
        return None, None

    # --------------------------------------------------------
    # 3. PROVISIONING
    # --------------------------------------------------------

    if is_blank(provisioning):
        return "Provisioning", "Provisioning Blank"

    if is_provisioning_pending(provisioning):
        return "Provisioning", "Provisioning Pending"

    # Only successful provisioning states release the record
    # to Dispatch.
    if not is_provisioning_approved(provisioning):
        return None, None

    # --------------------------------------------------------
    # 4. LETTER DISPATCH
    # --------------------------------------------------------

    if is_blank(dispatch):
        return "Dispatch", "Dispatch Blank"

    if is_dispatch_pending(dispatch):
        return "Dispatch", "Dispatch Pending"

    # Only Dispatch Approved releases the record to Confirmation.
    if not is_dispatch_approved(dispatch):
        return None, None

    # --------------------------------------------------------
    # 5. CONFIRMATION
    # --------------------------------------------------------

    if is_blank(confirmation):
        return "Confirmation", "Confirmation Blank"

    if is_confirmation_pending(confirmation):
        return "Confirmation", "Confirmation Pending"

    # Confirmation must be a qualifying completed/approved state
    # before Live / Onboarding can become active.
    if not is_confirmation_approved(confirmation):
        return None, None

    # --------------------------------------------------------
    # 6. LIVE / ONBOARDING
    # --------------------------------------------------------

    if is_live_pending(live):
        return "Live / Onboarding", "Live / Onboarding Pending"

    return None, None


# ============================================================
# DISPLAY STATUS / REMARKS
# ============================================================

def status_display(row, stage: str) -> str:
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

    field = mapping.get(stage)

    if not field:
        return ""

    return clean_display_text(
        row.get(field, "")
    )


def remarks_display(row, stage: str) -> str:
    mapping = {
        "Quality": API_COLUMNS["quality_remarks"],
        "Welcome": API_COLUMNS["welcome_remarks"],
        "Provisioning": API_COLUMNS["provisioning_remarks"],
        "Dispatch": API_COLUMNS["dispatch_cancel"],
        "Confirmation": API_COLUMNS["confirmation_comment"],
        "Live / Onboarding": API_COLUMNS["onboarding_cancel"],
        "Potential Opportunity": API_COLUMNS["potential_cancel"],
    }

    field = mapping.get(stage)

    if not field:
        return ""

    return clean_display_text(
        row.get(field, "")
    )


# ============================================================
# BUILD QUEUE DATAFRAME
# ============================================================

def build_queue_dataframe(source_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in source_df.iterrows():

        current_stage, queue_bucket = classify_current_queue(row)

        potential_flag = pending_potential_opportunity(row)

        if current_stage is None and not potential_flag:
            continue

        pending_stages = []

        if current_stage:
            pending_stages.append(current_stage)

        if potential_flag:
            pending_stages.append("Potential Opportunity")

        record_key = make_record_key(
            row.get(API_COLUMNS["sale_date"]),
            row.get(API_COLUMNS["phone"]),
        )

        rows.append(
            {
                "Sale Date": parse_date(
                    row.get(API_COLUMNS["sale_date"])
                ),

                "Advisor": clean_display_text(
                    row.get(API_COLUMNS["advisor"])
                ),

                "Customer Name": clean_display_text(
                    row.get(API_COLUMNS["customer"])
                ),

                "Phone Number": clean_phone(
                    row.get(API_COLUMNS["phone"])
                ),

                "Current Pending Stage": current_stage or "",

                "Queue Bucket": queue_bucket or "",

                "Pending Stage(s)": ", ".join(pending_stages),

                "Potential Opportunity": (
                    "Yes" if potential_flag else ""
                ),

                "Pending Count": len(
                    pending_stages
                ),

                "Quality Status": clean_display_text(
                    row.get(API_COLUMNS["quality"])
                ),

                "Welcome Call Status": clean_display_text(
                    row.get(API_COLUMNS["welcome"])
                ),

                "Provisioning Status": clean_display_text(
                    row.get(API_COLUMNS["provisioning"])
                ),

                "Dispatch Status": clean_display_text(
                    row.get(API_COLUMNS["dispatch"])
                ),

                "Confirmation Status": clean_display_text(
                    row.get(API_COLUMNS["confirmation"])
                ),

                "Live / Onboarding Status": clean_display_text(
                    row.get(API_COLUMNS["live"])
                ),

                "Record Key": record_key,
            }
        )

    columns = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",
        "Current Pending Stage",
        "Queue Bucket",
        "Pending Stage(s)",
        "Potential Opportunity",
        "Pending Count",
        "Quality Status",
        "Welcome Call Status",
        "Provisioning Status",
        "Dispatch Status",
        "Confirmation Status",
        "Live / Onboarding Status",
        "Record Key",
    ]

    if not rows:
        return pd.DataFrame(
            columns=columns
        )

    result = pd.DataFrame(rows)

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
    ).reset_index(drop=True)

    return result[columns]


# ============================================================
# LOAD GOOGLE SHEET
# ============================================================

def load_google_sheet_data():
    """
    Load the CRM mirror worksheet directly from Google Sheets.
    """

    info = st.secrets["gcp_service_account"]

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open_by_key(
        SPREADSHEET_ID
    )

    try:
        worksheet = spreadsheet.get_worksheet_by_id(
            CRM_MIRROR_WORKSHEET_GID
        )

    except Exception as exc:
        raise RuntimeError(
            "Could not open Google Sheet worksheet "
            f"GID {CRM_MIRROR_WORKSHEET_GID}: {exc}"
        ) from exc

    records = worksheet.get_all_records()

    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError(
            "The CRM mirror Google Sheet contains no records."
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
            "Google Sheet is missing required CRM columns: "
            + ", ".join(missing)
        )

    fetched_at = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    return df, fetched_at


@st.cache_data(
    ttl=DATA_CACHE_TTL,
    show_spinner=False,
)
def fetch_google_sheet_data():
    return load_google_sheet_data()


# ============================================================
# LOAD DATA
# ============================================================

try:
    sheet_df, fetched_at = fetch_google_sheet_data()

    queue_df = build_queue_dataframe(
        sheet_df
    )

except Exception as exc:
    st.error(
        "Unable to load the Sparta CRM Google Sheet: "
        f"{exc}"
    )
    st.stop()


# ============================================================
# BUILD SOURCE LOOKUP
# ============================================================

source_lookup = {}

for _, source_row in sheet_df.iterrows():
    key = make_record_key(
        source_row.get(
            API_COLUMNS["sale_date"]
        ),
        source_row.get(
            API_COLUMNS["phone"]
        ),
    )

    source_lookup[key] = source_row


# ============================================================
# PAGE HEADER
# ============================================================

st.markdown(
    f"""
    <div class="hero">
        <div style="display:flex;justify-content:space-between;gap:24px;align-items:flex-start;">
            <div>
                <div class="hero-kicker">SPARTA CRM · OPERATIONS QUEUE</div>
                <div class="hero-title">⏳ Sparta Pending Operations</div>
                <div class="hero-subtitle">
                    Sequential workflow queue from the CRM mirror.
                    A sale enters the next queue only after the previous
                    stage has successfully released it.
                </div>
            </div>
            <div class="hero-right">
                Last Google Sheet refresh
                <strong>{fetched_at}</strong>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("### ⚙️ Queue Controls")

    st.caption(
        "Direct from the CRM mirror Google Sheet"
    )

    st.divider()

    st.metric(
        "Sheet Records",
        f"{len(sheet_df):,}",
    )

    st.metric(
        "Active Queue Records",
        f"{len(queue_df):,}",
    )

    st.divider()

    st.caption(
        f"Cache TTL: {DATA_CACHE_TTL:,} seconds"
    )

    if st.button(
        "↻ Refresh Google Sheet data",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()

    if not queue_df.empty:

        export_df_sidebar = queue_df.drop(
            columns=["Record Key"],
            errors="ignore",
        ).copy()

        export_df_sidebar["Sale Date"] = (
            pd.to_datetime(
                export_df_sidebar["Sale Date"],
                errors="coerce",
            )
            .dt.strftime("%d/%m/%Y")
        )

        export_bytes = (
            export_df_sidebar
            .to_csv(index=False)
            .encode("utf-8-sig")
        )

        st.download_button(
            "📥 Export All Pending",
            data=export_bytes,
            file_name="Sparta_Pending_Operations.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# QUEUE COUNTS
# ============================================================

def count_bucket(bucket_name: str) -> int:
    if queue_df.empty:
        return 0

    return int(
        (
            queue_df["Queue Bucket"]
            .fillna("")
            .astype(str)
            == bucket_name
        ).sum()
    )


def count_stage(stage_name: str) -> int:
    if queue_df.empty:
        return 0

    return int(
        (
            queue_df["Current Pending Stage"]
            .fillna("")
            .astype(str)
            == stage_name
        ).sum()
    )


def count_potential() -> int:
    if queue_df.empty:
        return 0

    return int(
        (
            queue_df["Potential Opportunity"]
            .fillna("")
            .astype(str)
            == "Yes"
        ).sum()
    )


# Exact requested counts
quality_qa_pending = count_bucket(
    "QA-Pending"
)

welcome_pending = count_bucket(
    "Welcome Pending"
)

welcome_followup = count_bucket(
    "Welcome Followup"
)

welcome_blank = count_bucket(
    "Welcome Blank"
)

provisioning_pending = count_bucket(
    "Provisioning Pending"
)

provisioning_blank = count_bucket(
    "Provisioning Blank"
)

dispatch_pending = count_bucket(
    "Dispatch Pending"
)

dispatch_blank = count_bucket(
    "Dispatch Blank"
)

confirmation_pending = count_bucket(
    "Confirmation Pending"
)

confirmation_blank = count_bucket(
    "Confirmation Blank"
)

live_pending = count_bucket(
    "Live / Onboarding Pending"
)

potential_count = count_potential()


# ============================================================
# KPI HEADER — ROW 1
# ============================================================

metric_row_1 = st.columns(
    5,
    gap="small",
)

with metric_row_1[0]:
    st.metric(
        "🧪 QA-Pending",
        quality_qa_pending,
    )

with metric_row_1[1]:
    st.metric(
        "📞 Welcome Pending",
        welcome_pending,
    )

with metric_row_1[2]:
    st.metric(
        "📞 Welcome Followup",
        welcome_followup,
    )

with metric_row_1[3]:
    st.metric(
        "📞 Welcome Blank",
        welcome_blank,
    )

with metric_row_1[4]:
    st.metric(
        "⚙️ Provisioning Pending",
        provisioning_pending,
    )


# ============================================================
# KPI HEADER — ROW 2
# ============================================================

metric_row_2 = st.columns(
    5,
    gap="small",
)

with metric_row_2[0]:
    st.metric(
        "⚙️ Provisioning Blank",
        provisioning_blank,
    )

with metric_row_2[1]:
    st.metric(
        "✉️ Dispatch Pending",
        dispatch_pending,
    )

with metric_row_2[2]:
    st.metric(
        "✉️ Dispatch Blank",
        dispatch_blank,
    )

with metric_row_2[3]:
    st.metric(
        "✅ Confirmation Pending",
        confirmation_pending,
    )

with metric_row_2[4]:
    st.metric(
        "✅ Confirmation Blank",
        confirmation_blank,
    )


# ============================================================
# KPI HEADER — ROW 3
# ============================================================

metric_row_3 = st.columns(
    2,
    gap="small",
)

with metric_row_3[0]:
    st.metric(
        "📡 Live / Onboarding Pending",
        live_pending,
    )

with metric_row_3[1]:
    st.metric(
        "🎯 Potential Opportunity",
        potential_count,
    )


# ============================================================
# QUEUE NOTE
# ============================================================

st.markdown(
    """
    <div class="queue-note">
        <b>Sequential queue logic:</b>
        a sale only enters the next workflow stage after the previous
        stage has the required approved/completed status.
        A blank status therefore counts only when that stage has been
        reached. QA-Pending, rejected, rework, cancelled, delayed and
        other non-qualifying states do not push the sale into the next stage.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FILTERS
# ============================================================

st.markdown(
    "<div class='section-title'>🔎 Filters</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='section-subtitle'>
        Filter the active workflow queue without changing the underlying CRM data.
    </div>
    """,
    unsafe_allow_html=True,
)


filter_cols = st.columns(
    [
        2.0,
        1.2,
        1.2,
        1.2,
    ]
)


with filter_cols[0]:

    search_text = st.text_input(
        "Search",
        placeholder="Customer, phone number or advisor…",
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

    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()

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
                for x
                in queue_df["Advisor"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
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
    format_func=lambda x: (
        f"{STAGE_ICONS[x]} {x}"
    ),
    placeholder="All pending stages",
)


bucket_filter = st.multiselect(
    "Queue Type",
    options=[
        "QA-Pending",
        "Welcome Pending",
        "Welcome Followup",
        "Welcome Blank",
        "Provisioning Pending",
        "Provisioning Blank",
        "Dispatch Pending",
        "Dispatch Blank",
        "Confirmation Pending",
        "Confirmation Blank",
        "Live / Onboarding Pending",
    ],
    placeholder="All queue types",
)


# ============================================================
# APPLY FILTERS
# ============================================================

filtered_df = queue_df.copy()

if not filtered_df.empty:

    filtered_df["_SaleDate"] = pd.to_datetime(
        filtered_df["Sale Date"],
        errors="coerce",
    )

    filtered_df = filtered_df[
        filtered_df["_SaleDate"]
        .dt.date
        .between(
            date_from,
            date_to,
            inclusive="both",
        )
    ]

    if selected_advisor != "All Advisors":

        filtered_df = filtered_df[
            filtered_df["Advisor"]
            == selected_advisor
        ]

    if search_text.strip():

        needle = search_text.strip()

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
            .agg(" | ".join, axis=1)
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

        filtered_df = filtered_df[
            filtered_df[
                "Current Pending Stage"
            ].isin(stage_filter)
        ]

    if bucket_filter:

        filtered_df = filtered_df[
            filtered_df[
                "Queue Bucket"
            ].isin(bucket_filter)
        ]

    filtered_df = filtered_df.drop(
        columns=["_SaleDate"],
        errors="ignore",
    )


st.caption(
    f"Showing {len(filtered_df):,} active queue record(s) "
    f"from {len(queue_df):,} total active queue record(s)."
)


# ============================================================
# ALL PENDING TABLE
# ============================================================

st.markdown(
    "<div class='section-title'>📋 Current Pending Queue</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='section-subtitle'>
        One row per sale. The Queue Type identifies why the sale is
        currently waiting at that stage.
    </div>
    """,
    unsafe_allow_html=True,
)


all_display = filtered_df.drop(
    columns=["Record Key"],
    errors="ignore",
).copy()


if not all_display.empty:

    all_display["Sale Date"] = (
        pd.to_datetime(
            all_display["Sale Date"],
            errors="coerce",
        )
        .dt.strftime("%d/%m/%Y")
    )

    display_columns = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",
        "Current Pending Stage",
        "Queue Bucket",
        "Pending Stage(s)",
        "Potential Opportunity",
        "Quality Status",
        "Welcome Call Status",
        "Provisioning Status",
        "Dispatch Status",
        "Confirmation Status",
        "Live / Onboarding Status",
    ]

    display_columns = [
        c
        for c in display_columns
        if c in all_display.columns
    ]

    st.dataframe(
        all_display[display_columns],
        use_container_width=True,
        hide_index=True,
        height=min(
            610,
            max(
                200,
                120 + len(all_display) * 35,
            ),
        ),
        column_config={
            "Sale Date": st.column_config.TextColumn(
                "SALE DATE",
                width="small",
            ),

            "Advisor": st.column_config.TextColumn(
                "ADVISOR",
                width="medium",
            ),

            "Customer Name": st.column_config.TextColumn(
                "CUSTOMER NAME",
                width="medium",
            ),

            "Phone Number": st.column_config.TextColumn(
                "PHONE NUMBER",
                width="medium",
            ),

            "Current Pending Stage": st.column_config.TextColumn(
                "CURRENT STAGE",
                width="medium",
            ),

            "Queue Bucket": st.column_config.TextColumn(
                "QUEUE TYPE",
                width="medium",
            ),

            "Pending Stage(s)": st.column_config.TextColumn(
                "PENDING STAGE(S)",
                width="large",
            ),

            "Potential Opportunity": st.column_config.TextColumn(
                "POTENTIAL OPPORTUNITY",
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

st.markdown(
    "<div class='section-title'>🗂️ Stage Queues</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='section-subtitle'>
        Each sale appears in its CURRENT workflow queue.
        Downstream blank statuses are not shown until the previous
        stage has released the sale.
    </div>
    """,
    unsafe_allow_html=True,
)


queue_tabs = st.tabs(
    [
        (
            f"{STAGE_ICONS[stage]} "
            f"{stage} "
            f"({count_stage(stage):,})"
        )
        for stage in STAGES
    ]
)


for tab, stage in zip(
    queue_tabs,
    STAGES,
):

    with tab:

        # ----------------------------------------------------
        # Potential Opportunity
        # ----------------------------------------------------

        if stage == "Potential Opportunity":

            stage_rows = []

            for _, row in filtered_df.iterrows():

                if safe_text(
                    row.get(
                        "Potential Opportunity"
                    )
                ) != "Yes":
                    continue

                record_key = row.get(
                    "Record Key",
                    "",
                )

                source_row = source_lookup.get(
                    record_key
                )

                stage_rows.append(
                    {
                        "Sale Date": row.get(
                            "Sale Date"
                        ),

                        "Advisor": row.get(
                            "Advisor",
                            "",
                        ),

                        "Customer Name": row.get(
                            "Customer Name",
                            "",
                        ),

                        "Phone Number": row.get(
                            "Phone Number",
                            "",
                        ),

                        "Pending Stage": (
                            "Potential Opportunity"
                        ),

                        "Current Status": (
                            "Potential Opportunity"
                        ),

                        "Remarks / Latest Note": (
                            remarks_display(
                                source_row,
                                "Potential Opportunity",
                            )
                            if source_row is not None
                            else ""
                        ),

                        "Current Workflow Queue": (
                            row.get(
                                "Queue Bucket",
                                "",
                            )
                        ),
                    }
                )

        else:

            stage_rows = []

            for _, row in filtered_df.iterrows():

                if row.get(
                    "Current Pending Stage",
                    "",
                ) != stage:
                    continue

                record_key = row.get(
                    "Record Key",
                    "",
                )

                source_row = source_lookup.get(
                    record_key
                )

                stage_rows.append(
                    {
                        "Sale Date": row.get(
                            "Sale Date"
                        ),

                        "Advisor": row.get(
                            "Advisor",
                            "",
                        ),

                        "Customer Name": row.get(
                            "Customer Name",
                            "",
                        ),

                        "Phone Number": row.get(
                            "Phone Number",
                            "",
                        ),

                        "Pending Stage": stage,

                        "Queue Type": row.get(
                            "Queue Bucket",
                            "",
                        ),

                        "Current Status": (
                            status_display(
                                source_row,
                                stage,
                            )
                            if source_row is not None
                            else ""
                        ),

                        "Remarks / Latest Note": (
                            remarks_display(
                                source_row,
                                stage,
                            )
                            if source_row is not None
                            else ""
                        ),
                    }
                )

        stage_df = pd.DataFrame(
            stage_rows
        )

        if not stage_df.empty:

            stage_df["Sale Date"] = (
                pd.to_datetime(
                    stage_df["Sale Date"],
                    errors="coerce",
                )
                .dt.strftime("%d/%m/%Y")
            )

            st.dataframe(
                stage_df,
                use_container_width=True,
                hide_index=True,
                height=min(
                    620,
                    max(
                        220,
                        120 + len(stage_df) * 36,
                    ),
                ),
                column_config={
                    "Sale Date": st.column_config.TextColumn(
                        "SALE DATE",
                        width="small",
                    ),

                    "Advisor": st.column_config.TextColumn(
                        "ADVISOR",
                        width="medium",
                    ),

                    "Customer Name": st.column_config.TextColumn(
                        "CUSTOMER NAME",
                        width="medium",
                    ),

                    "Phone Number": st.column_config.TextColumn(
                        "PHONE NUMBER",
                        width="medium",
                    ),

                    "Pending Stage": st.column_config.TextColumn(
                        "STAGE",
                        width="medium",
                    ),

                    "Queue Type": st.column_config.TextColumn(
                        "QUEUE TYPE",
                        width="medium",
                    ),

                    "Current Status": st.column_config.TextColumn(
                        "CURRENT STATUS",
                        width="large",
                    ),

                    "Remarks / Latest Note": st.column_config.TextColumn(
                        "REMARKS / LATEST NOTE",
                        width="large",
                    ),

                    "Current Workflow Queue": st.column_config.TextColumn(
                        "CURRENT WORKFLOW QUEUE",
                        width="large",
                    ),
                },
            )

        else:

            st.success(
                f"No {stage} records are pending "
                "for the current filters."
            )


# ============================================================
# RAW STATUS SNAPSHOT
# ============================================================

st.divider()

with st.expander(
    "🔍 View current CRM status fields",
    expanded=False,
):

    status_snapshot = filtered_df.drop(
        columns=["Record Key"],
        errors="ignore",
    ).copy()

    status_cols = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",

        "Current Pending Stage",
        "Queue Bucket",

        "Quality Status",
        "Welcome Call Status",
        "Provisioning Status",
        "Dispatch Status",
        "Confirmation Status",
        "Live / Onboarding Status",

        "Pending Stage(s)",
        "Potential Opportunity",
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

        status_snapshot["Sale Date"] = (
            pd.to_datetime(
                status_snapshot["Sale Date"],
                errors="coerce",
            )
            .dt.strftime("%d/%m/%Y")
        )

    st.dataframe(
        status_snapshot,
        use_container_width=True,
        hide_index=True,
        height=min(
            560,
            max(
                180,
                100 + len(status_snapshot) * 34,
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
        "Sequential CRM workflow queue"
    )

with footer_right:
    st.caption(
        f"Last Google Sheet fetch: {fetched_at}"
    )
