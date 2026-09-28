"""
SPARTA PENDING OPERATIONS — GOOGLE SHEET QUEUE
================================================

Live operational queue driven by the CRM data mirrored into Google Sheets.

The dashboard reads the dedicated Google worksheet directly. The CRM API is
upstream of the separate sync process and is not called by this app.

Stages tracked:
    - Quality
    - Welcome
    - Provisioning
    - Dispatch
    - Confirmation
    - Live / Onboarding
    - Potential Opportunity

There is deliberately:
    - NO manual entry
    - NO manual resolution state
    - NO SLA calculation
    - NO ageing / breach / RAG logic

A sale can be pending in multiple stages when the source statuses indicate
open work at multiple workflow points.
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
        max-width: 880px;
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

    .stage-count {
        display: inline-block;
        margin-left: 7px;
        padding: 2px 7px;
        border-radius: 999px;
        font-size: .70rem;
        font-weight: 900;
        background: #eef2ff;
        color: #334155;
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
    return re.sub(r"\s+", " ", safe_text(value).replace("\ufeff", "")).strip()


def normalize_status(value) -> str:
    text = safe_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_display_text(value) -> str:
    text = safe_text(value)
    text = text.replace("<br>", " | ").replace("<br/>", " | ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"nan", "none", "null", "nat"}:
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

    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            parsed = pd.to_datetime(text, format=fmt, errors="coerce")
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


def is_blank_or_pending(value) -> bool:
    status = normalize_status(value)
    if not status:
        return True

    pending_terms = [
        "pending",
        "follow up",
        "followup",
        "other work",
        "delay",
        "in progress",
        "processing",
        "rework",
        "ringing",
        "chasing",
    ]
    return any(term in status for term in pending_terms)


def is_terminal(value) -> bool:
    status = normalize_status(value)
    if not status:
        return False

    terminal_terms = [
        "approved",
        "done",
        "complete",
        "completed",
        "processed",
        "provisioned",
        "confirmed",
        "confirmation complete",
        "dispatched",
        "dispatch complete",
        "live",
        "active",
        "cancelled",
        "canceled",
        "rejected",
    ]
    return any(term in status for term in terminal_terms)


def pending_quality(value) -> bool:
    return is_blank_or_pending(value) and not normalize_status(value).startswith("qa reject")


def pending_welcome(value) -> bool:
    return is_blank_or_pending(value)


def pending_provisioning(value) -> bool:
    status = normalize_status(value)
    if not status:
        return True
    if "potential opportunity" in status:
        return False
    return is_blank_or_pending(status)


def pending_dispatch(value) -> bool:
    return is_blank_or_pending(value)


def pending_confirmation(value) -> bool:
    return is_blank_or_pending(value)


def pending_live(value) -> bool:
    status = normalize_status(value)
    if not status:
        return True
    if any(term in status for term in ["live", "active", "completed", "complete"]):
        return False
    return any(
        term in status
        for term in [
            "committed",
            "pending",
            "follow up",
            "followup",
            "other work",
            "delay",
            "in progress",
            "processing",
        ]
    )


def pending_potential_opportunity(row) -> bool:
    # Potential Opportunity is represented by the provisioning status/reason in
    # the current CRM export rather than a separate status column.
    fields = [
        API_COLUMNS["provisioning"],
        API_COLUMNS["welcome"],
        API_COLUMNS["quality_cancel"],
        API_COLUMNS["welcome_cancel"],
        API_COLUMNS["provisioning_cancel"],
        API_COLUMNS["potential_cancel"],
    ]
    for field in fields:
        if field in row.index and "potential opportunity" in normalize_status(row[field]):
            return True
    return False


def classify_pending_stages(row) -> list[str]:
    stages = []

    if pending_quality(row.get(API_COLUMNS["quality"], "")):
        stages.append("Quality")

    if pending_welcome(row.get(API_COLUMNS["welcome"], "")):
        stages.append("Welcome")

    if pending_provisioning(row.get(API_COLUMNS["provisioning"], "")):
        stages.append("Provisioning")

    if pending_dispatch(row.get(API_COLUMNS["dispatch"], "")):
        stages.append("Dispatch")

    if pending_confirmation(row.get(API_COLUMNS["confirmation"], "")):
        stages.append("Confirmation")

    if pending_live(row.get(API_COLUMNS["live"], "")):
        stages.append("Live / Onboarding")

    if pending_potential_opportunity(row):
        stages.append("Potential Opportunity")

    return stages


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
    return clean_display_text(row.get(mapping.get(stage, ""), ""))


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
    return clean_display_text(row.get(mapping.get(stage, ""), ""))


def make_record_key(sale_date, phone) -> str:
    parsed = parse_date(sale_date)
    date_part = parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else ""
    phone_part = clean_phone(phone)
    return f"{date_part}|{phone_part}"


def build_queue_dataframe(source_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in source_df.iterrows():
        stages = classify_pending_stages(row)
        if not stages:
            continue

        row_data = {
            "Sale Date": parse_date(row.get(API_COLUMNS["sale_date"])),
            "Advisor": clean_display_text(row.get(API_COLUMNS["advisor"])),
            "Customer Name": clean_display_text(row.get(API_COLUMNS["customer"])),
            "Phone Number": clean_phone(row.get(API_COLUMNS["phone"])),
            "Pending Stage(s)": ", ".join(stages),
            "Pending Count": len(stages),
            "Quality Status": clean_display_text(row.get(API_COLUMNS["quality"])),
            "Welcome Call Status": clean_display_text(row.get(API_COLUMNS["welcome"])),
            "Provisioning Status": clean_display_text(row.get(API_COLUMNS["provisioning"])),
            "Dispatch Status": clean_display_text(row.get(API_COLUMNS["dispatch"])),
            "Confirmation Status": clean_display_text(row.get(API_COLUMNS["confirmation"])),
            "Live / Onboarding Status": clean_display_text(row.get(API_COLUMNS["live"])),
            "Record Key": make_record_key(
                row.get(API_COLUMNS["sale_date"]),
                row.get(API_COLUMNS["phone"]),
            ),
        }
        rows.append(row_data)

    columns = [
        "Sale Date",
        "Advisor",
        "Customer Name",
        "Phone Number",
        "Pending Stage(s)",
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
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(rows)
    result = result.sort_values(
        by=["Sale Date", "Customer Name"],
        ascending=[False, True],
        na_position="last",
    ).reset_index(drop=True)
    return result[columns]


def load_google_sheet_data():
    """Load the CRM mirror worksheet directly from Google Sheets."""
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.get_worksheet_by_id(CRM_MIRROR_WORKSHEET_GID)
    except Exception as exc:
        raise RuntimeError(
            f"Could not open Google Sheet worksheet GID {CRM_MIRROR_WORKSHEET_GID}: {exc}"
        ) from exc

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("The CRM mirror Google Sheet contains no records.")

    df.columns = [normalize_header(c) for c in df.columns]

    required = [
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

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            "Google Sheet is missing required CRM columns: " + ", ".join(missing)
        )

    fetched_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return df, fetched_at


@st.cache_data(ttl=DATA_CACHE_TTL, show_spinner=False)
def fetch_google_sheet_data():
    return load_google_sheet_data()


# ============================================================
# LOAD GOOGLE SHEET DATA
# ============================================================

try:
    sheet_df, fetched_at = fetch_google_sheet_data()
    queue_df = build_queue_dataframe(sheet_df)
except Exception as exc:
    st.error(f"Unable to load the Sparta CRM Google Sheet: {exc}")
    st.stop()


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
                    Live records from the CRM data mirrored into Google Sheets showing where each sale is still pending.
                    A single sale can appear in multiple queues when multiple workflow stages remain open.
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
    st.caption("Direct from the CRM mirror Google Sheet")
    st.divider()
    st.metric("Sheet Records", f"{len(sheet_df):,}")
    st.metric("Pending Sales", f"{len(queue_df):,}")

    st.divider()
    st.caption(f"Cache TTL: {DATA_CACHE_TTL:,} seconds")

    if st.button("↻ Refresh Google Sheet data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if not queue_df.empty:
        export_df_sidebar = queue_df.drop(columns=["Record Key"], errors="ignore").copy()
        export_df_sidebar["Sale Date"] = pd.to_datetime(
            export_df_sidebar["Sale Date"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")
        export_bytes = export_df_sidebar.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Export All Pending",
            data=export_bytes,
            file_name="Sparta_Pending_Operations.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# KPI COUNTS
# ============================================================

stage_counts = {
    stage: int(
        queue_df["Pending Stage(s)"].fillna("").astype(str).str.contains(
            rf"(?:^|, )(?P<stage>{re.escape(stage)})(?:$|, )",
            regex=True,
            na=False,
        ).sum()
    )
    for stage in STAGES
}

metric_cols = st.columns(5, gap="small")
metric_stage_order = [
    "Quality",
    "Welcome",
    "Provisioning",
    "Dispatch",
    "Confirmation",
]

for col, stage in zip(metric_cols, metric_stage_order):
    with col:
        st.metric(
            f"{STAGE_ICONS[stage]} Pending {stage}",
            stage_counts[stage],
        )

extra_cols = st.columns(2, gap="small")
for col, stage in zip(extra_cols, ["Live / Onboarding", "Potential Opportunity"]):
    with col:
        st.metric(
            f"{STAGE_ICONS[stage]} {stage}",
            stage_counts[stage],
        )

st.markdown(
    """
    <div class="queue-note">
        <b>Queue logic:</b> blank / follow-up / pending / delay / other-work / in-progress type statuses are treated as open work. Completed, approved, provisioned, processed, confirmed, dispatched, live, cancelled, and rejected outcomes are not shown as pending for that stage. The queue is status-based only; it reads the current workflow status from the CRM mirror sheet and does not calculate SLA targets or breaches.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FILTERS
# ============================================================

st.markdown("<div class='section-title'>🔎 Filters</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-subtitle'>Filter the pending queues without changing the underlying CRM data.</div>",
    unsafe_allow_html=True,
)

filter_cols = st.columns([2.0, 1.2, 1.2, 1.2])

with filter_cols[0]:
    search_text = st.text_input(
        "Search",
        placeholder="Customer, phone number or advisor…",
    )

sale_dates = pd.to_datetime(queue_df["Sale Date"], errors="coerce") if not queue_df.empty else pd.Series(dtype="datetime64[ns]")
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
    advisor_options = sorted(
        [x for x in queue_df["Advisor"].dropna().astype(str).unique().tolist() if x]
    ) if not queue_df.empty else []
    selected_advisor = st.selectbox(
        "Advisor",
        options=["All Advisors"] + advisor_options,
    )

stage_filter = st.multiselect(
    "Pending Stage",
    options=STAGES,
    format_func=lambda x: f"{STAGE_ICONS[x]} {x}",
    placeholder="All pending stages",
)

filtered_df = queue_df.copy()

if not filtered_df.empty:
    filtered_df["_SaleDate"] = pd.to_datetime(filtered_df["Sale Date"], errors="coerce")
    filtered_df = filtered_df[
        filtered_df["_SaleDate"].dt.date.between(date_from, date_to, inclusive="both")
    ]

    if selected_advisor != "All Advisors":
        filtered_df = filtered_df[filtered_df["Advisor"] == selected_advisor]

    if search_text.strip():
        needle = search_text.strip()
        blob = (
            filtered_df[["Customer Name", "Phone Number", "Advisor"]]
            .fillna("")
            .astype(str)
            .agg(" | ".join, axis=1)
        )
        filtered_df = filtered_df[
            blob.str.contains(needle, case=False, regex=False, na=False)
        ]

    if stage_filter:
        stage_regex = "|".join(re.escape(x) for x in stage_filter)
        filtered_df = filtered_df[
            filtered_df["Pending Stage(s)"].fillna("").str.contains(
                stage_regex,
                regex=True,
                na=False,
            )
        ]

    filtered_df = filtered_df.drop(columns=["_SaleDate"], errors="ignore")

st.caption(
    f"Showing {len(filtered_df):,} pending sale(s) from {len(queue_df):,} total pending sale(s)."
)


# ============================================================
# ALL PENDING TABLE
# ============================================================

st.markdown("<div class='section-title'>📋 All Pending</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-subtitle'>One row per sale. Use Pending Stage(s) to see every open workflow stage for that sale.</div>",
    unsafe_allow_html=True,
)

all_display = filtered_df.drop(columns=["Record Key"], errors="ignore").copy()
if not all_display.empty:
    all_display["Sale Date"] = pd.to_datetime(
        all_display["Sale Date"], errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    st.dataframe(
        all_display,
        use_container_width=True,
        hide_index=True,
        height=min(610, max(200, 120 + len(all_display) * 35)),
        column_config={
            "Sale Date": st.column_config.TextColumn("SALE DATE", width="small"),
            "Advisor": st.column_config.TextColumn("ADVISOR", width="medium"),
            "Customer Name": st.column_config.TextColumn("CUSTOMER NAME", width="medium"),
            "Phone Number": st.column_config.TextColumn("PHONE NUMBER", width="medium"),
            "Pending Stage(s)": st.column_config.TextColumn("PENDING STAGE(S)", width="large"),
            "Pending Count": st.column_config.NumberColumn("OPEN STAGES", format="%d", width="small"),
        },
    )
else:
    st.info("No pending records match the current filters.")


# ============================================================
# STAGE QUEUES
# ============================================================

st.divider()
st.markdown("<div class='section-title'>🗂️ Stage Queues</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-subtitle'>The same sale may appear in more than one queue when more than one workflow stage remains open.</div>",
    unsafe_allow_html=True,
)

queue_tabs = st.tabs([
    f"{STAGE_ICONS[stage]} {stage} ({stage_counts[stage]:,})"
    for stage in STAGES
])

for tab, stage in zip(queue_tabs, STAGES):
    with tab:
        stage_rows = []

        for _, row in filtered_df.iterrows():
            row_stage_text = safe_text(row.get("Pending Stage(s)"))
            stage_list = [x.strip() for x in row_stage_text.split(",") if x.strip()]
            if stage not in stage_list:
                continue

            source_row = None
            # Recover the source record using Sale Date + Phone where possible.
            sale_date_key = make_record_key(row.get("Sale Date"), row.get("Phone Number"))
            matches = sheet_df[
                sheet_df.apply(
                    lambda x: make_record_key(
                        x.get(API_COLUMNS["sale_date"]),
                        x.get(API_COLUMNS["phone"]),
                    ) == sale_date_key,
                    axis=1,
                )
            ]
            if not matches.empty:
                source_row = matches.iloc[-1]

            stage_rows.append(
                {
                    "Sale Date": row.get("Sale Date"),
                    "Advisor": row.get("Advisor", ""),
                    "Customer Name": row.get("Customer Name", ""),
                    "Phone Number": row.get("Phone Number", ""),
                    "Pending Stage": stage,
                    "Current Status": status_display(source_row, stage) if source_row is not None else "",
                    "Remarks / Latest Note": remarks_display(source_row, stage) if source_row is not None else "",
                    "All Pending Stages": row.get("Pending Stage(s)", ""),
                }
            )

        stage_df = pd.DataFrame(stage_rows)

        if not stage_df.empty:
            stage_df["Sale Date"] = pd.to_datetime(
                stage_df["Sale Date"], errors="coerce"
            ).dt.strftime("%d/%m/%Y")

            st.dataframe(
                stage_df,
                use_container_width=True,
                hide_index=True,
                height=min(620, max(220, 120 + len(stage_df) * 36)),
                column_config={
                    "Sale Date": st.column_config.TextColumn("SALE DATE", width="small"),
                    "Advisor": st.column_config.TextColumn("ADVISOR", width="medium"),
                    "Customer Name": st.column_config.TextColumn("CUSTOMER NAME", width="medium"),
                    "Phone Number": st.column_config.TextColumn("PHONE NUMBER", width="medium"),
                    "Pending Stage": st.column_config.TextColumn("STAGE", width="medium"),
                    "Current Status": st.column_config.TextColumn("CURRENT STATUS", width="large"),
                    "Remarks / Latest Note": st.column_config.TextColumn("REMARKS / LATEST NOTE", width="large"),
                    "All Pending Stages": st.column_config.TextColumn("OTHER OPEN STAGES", width="large"),
                },
            )
        else:
            st.success(f"No {stage} records are pending for the current filters.")


# ============================================================
# RAW STATUS SNAPSHOT
# ============================================================

st.divider()
with st.expander("🔍 View current CRM status fields", expanded=False):
    status_snapshot = filtered_df.drop(columns=["Record Key"], errors="ignore").copy()
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
    ]
    status_cols = [c for c in status_cols if c in status_snapshot.columns]
    status_snapshot = status_snapshot[status_cols]
    if not status_snapshot.empty:
        status_snapshot["Sale Date"] = pd.to_datetime(
            status_snapshot["Sale Date"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")
    st.dataframe(
        status_snapshot,
        use_container_width=True,
        hide_index=True,
        height=min(560, max(180, 100 + len(status_snapshot) * 34)),
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()
footer_left, footer_right = st.columns(2)
with footer_left:
    st.caption("Sparta Pending Operations · Live Google Sheet queue")
with footer_right:
    st.caption(f"Last Google Sheet fetch: {fetched_at}")
