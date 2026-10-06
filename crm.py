"""
=======================================================================
SPARTA EXECUTIVE DASHBOARD — CRM ONLY
=======================================================================

Purpose
-------
A standalone Executive dashboard that reads ONLY the CRM mirror Google
Sheet. No legacy Excel / Sparta / Sparta2 reconciliation is performed.

Source
------
Google Spreadsheet / CRM mirror worksheet:
    SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
    CRM_MIRROR_WORKSHEET_GID = 1647226826

The dashboard intentionally keeps the CRM's own terminology and raw
values. The Executive KPI groupings below are based directly on the CRM
columns rather than translating the CRM into the legacy Sparta semantics.

CRM KPI groupings requested
---------------------------
Quality:
    QA-Approved      -> QA Approved
    Rework           -> QA Rework
    QA-Reject        -> QA Cancelled
    QA-Pending       -> QA Pending

Welcome:
    Welcome Approved  -> Welcome Done
    Welcome Rejected  -> Welcome Cancelled
    Welcome Followup  -> Welcome Pending
    Blank             -> NOT counted as Welcome Pending

Committed Rem. (CRM):
    Confirmation Approved
    Confirmation Followup
    Confirmation Pending

Live Cancelled (CRM):
    Confirmation Status = To Be Cancelled

Final Status:
    exact value from
    Committed (Live) Status (Onboarding Status)

All other record fields remain visible in the full CRM table exactly as
returned by the worksheet.
=======================================================================
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from html import escape
from typing import List

import gspread
import numpy as np
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sparta Executive Dashboard — CRM",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logger = logging.getLogger("sparta_executive_crm")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: #f6f8fc;
    }
    .block-container {
        max-width: 1550px;
        padding-top: 1.1rem;
        padding-bottom: 2rem;
    }
    .hero {
        padding: 22px 25px;
        border-radius: 18px;
        background: linear-gradient(135deg, #09142F 0%, #10275A 58%, #143A70 100%);
        color: #fff;
        box-shadow: 0 14px 32px rgba(15, 23, 42, .12);
        margin-bottom: 14px;
    }
    .hero-kicker {
        font-size: .68rem;
        text-transform: uppercase;
        letter-spacing: 1.6px;
        font-weight: 850;
        color: #9fc0ff;
    }
    .hero-title {
        font-size: 1.65rem;
        font-weight: 850;
        margin-top: 3px;
    }
    .hero-sub {
        color: #c6d5f4;
        font-size: .79rem;
        margin-top: 6px;
        line-height: 1.45;
    }
    .hero-status {
        margin-top: 10px;
        font-size: .70rem;
        color: #b3c6eb;
    }
    .kpi {
        min-height: 105px;
        padding: 13px 10px;
        border-radius: 14px;
        background: #fff;
        border: 1px solid #e2e8f0;
        box-shadow: 0 5px 16px rgba(15,23,42,.045);
        text-align: center;
    }
    .kpi-label {
        color: #64748b;
        font-size: .59rem;
        font-weight: 850;
        letter-spacing: .6px;
        text-transform: uppercase;
    }
    .kpi-value {
        color: #0f172a;
        font-size: 1.42rem;
        line-height: 1.0;
        font-weight: 900;
        margin-top: 8px;
    }
    .kpi-sub {
        color: #2563eb;
        font-size: .62rem;
        font-weight: 750;
        margin-top: 7px;
    }
    .section-note {
        color: #64748b;
        font-size: .73rem;
        margin-top: -5px;
        margin-bottom: 9px;
    }
    .status-pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 999px;
        background: #eef4ff;
        color: #1d4ed8;
        font-size: .63rem;
        font-weight: 800;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SPREADSHEET_ID = st.secrets.get(
    "SPREADSHEET_ID",
    "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ",
)
CRM_MIRROR_WORKSHEET_GID = int(
    st.secrets.get("CRM_MIRROR_WORKSHEET_GID", "1647226826")
)
DATA_CACHE_TTL = int(st.secrets.get("DATA_CACHE_TTL_SECONDS", "300"))

EXPECTED_COLUMNS: List[str] = [
    "Sale Date",
    "Advisor (Created Username)",
    "Customer Name",
    "Phone Number",
    "Quality Status",
    "Quality Remarks (Quality Comments)",
    "Welcome Call Status",
    "Welcome Call Remarks (Welcome Comments)",
    "Provisioning Status",
    "Provisioning Remarks (Provisioning Comments)",
    "Committed (Live) Status (Onboarding Status)",
    "LetterStatus (Dispatch Status)",
    "Confirmation Status",
    "Confirmation Comment",
    "Cancellation Reason - quality",
    "Cancellation Reason - welcome",
    "Cancellation/Rejection Reason - Provisioning",
    "Cancellation/Rejection Reason - Dispatch",
    "Cancellation/Rejection Reason - Confirmation",
    "Cancellation/Rejection Reason - Onboarding",
    "Cancellation/Rejection Reason - Potential Opportunity",
    "Standardized_Date",
    "Dashboard_Month",
]

# ---------------------------------------------------------------------------
# GOOGLE SHEETS
# ---------------------------------------------------------------------------
def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Missing gcp_service_account in Streamlit secrets.")

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(credentials)


def _worksheet_by_gid(spreadsheet, gid: int):
    for ws in spreadsheet.worksheets():
        if ws.id == gid:
            return ws
    raise RuntimeError(f"CRM worksheet GID {gid} was not found in the spreadsheet.")


@st.cache_data(ttl=DATA_CACHE_TTL, show_spinner=False)
def load_crm_sheet() -> tuple[pd.DataFrame, str]:
    """Read the CRM worksheet exactly as stored, then add analysis-only columns."""
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = _worksheet_by_gid(spreadsheet, CRM_MIRROR_WORKSHEET_GID)

    values = worksheet.get_all_values()
    fetched_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if not values:
        return pd.DataFrame(columns=EXPECTED_COLUMNS), fetched_at

    headers = [str(x).replace("\ufeff", "").strip() for x in values[0]]
    rows = []
    for row in values[1:]:
        padded = row + [""] * (len(headers) - len(row))
        rows.append(padded[: len(headers)])

    df = pd.DataFrame(rows, columns=headers)

    # Preserve every source column. If any expected column is absent, add it
    # as an empty string so the dashboard remains stable without rewriting
    # the CRM's terminology.
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Keep expected columns in source order, followed by any additional CRM
    # columns that may appear in the sheet.
    ordered = [c for c in EXPECTED_COLUMNS if c in df.columns]
    extras = [c for c in df.columns if c not in ordered]
    df = df[ordered + extras].copy()

    return df, fetched_at

# ---------------------------------------------------------------------------
# DATE HELPERS
# ---------------------------------------------------------------------------
def parse_date_value(value) -> pd.Timestamp:
    if value is None or pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if text.lower() in {"", "none", "nan", "nat", "(blank)"}:
        return pd.NaT

    # CRM examples are DD-MM-YYYY, but support ISO/date-like values too.
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(text[:10], fmt))
        except Exception:
            pass

    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def add_analysis_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_SaleDateParsed"] = out["Sale Date"].apply(parse_date_value)

    # Exact CRM values are retained in the source columns. These helper columns
    # are analysis-only and are not shown as replacements for the CRM fields.
    quality = out["Quality Status"].fillna("").astype(str).str.strip().str.lower()
    welcome = out["Welcome Call Status"].fillna("").astype(str).str.strip().str.lower()
    confirmation = out["Confirmation Status"].fillna("").astype(str).str.strip().str.lower()

    out["_QA_Group"] = np.select(
        [
            quality.eq("qa-approved"),
            quality.eq("rework"),
            quality.eq("qa-reject"),
            quality.eq("qa-pending"),
        ],
        [
            "QA Approved",
            "QA Rework",
            "QA Cancelled",
            "QA Pending",
        ],
        default="Other",
    )

    out["_Welcome_Group"] = np.select(
        [
            welcome.eq("welcome approved"),
            welcome.eq("welcome rejected"),
            welcome.eq("welcome followup"),
        ],
        [
            "Welcome Done",
            "Welcome Cancelled",
            "Welcome Pending",
        ],
        default="Not Counted",
    )

    out["_Committed_Group"] = confirmation.isin(
        {
            "confirmation approved",
            "confirmation followup",
            "confirmation pending",
        }
    )
    out["_Live_Cancelled_Group"] = confirmation.eq("to be cancelled")

    # This is explicitly the exact CRM field, surfaced as a named executive
    # column without changing the CRM value.
    out["Final Status"] = out[
        "Committed (Live) Status (Onboarding Status)"
    ].fillna("").astype(str).str.strip()

    out["Advisor"] = out[
        "Advisor (Created Username)"
    ].fillna("").astype(str).str.strip()

    # Exact Dashboard_Month is retained; this parsed period is only for sorting.
    out["_DashboardMonthParsed"] = pd.PeriodIndex(
        out["_SaleDateParsed"].dt.to_period("M"),
        freq="M",
    )
    return out


# ---------------------------------------------------------------------------
# SAFE FORMATTING
# ---------------------------------------------------------------------------
def pct(part: int, total: int) -> str:
    return "0.0%" if total == 0 else f"{part / total * 100:.1f}%"


def exact_count(df: pd.DataFrame, column: str, value: str) -> int:
    if column not in df.columns:
        return 0
    return int(
        df[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq(value.casefold())
        .sum()
    )


def unique_nonblank(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    values = (
        df[column]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    values = values[values != ""]
    return sorted(values.unique().tolist(), key=str.casefold)


# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------
if "crm_force_refresh" not in st.session_state:
    st.session_state.crm_force_refresh = 0

with st.sidebar:
    st.markdown("### ⚙️ CRM Controls")
    if st.button("🔄 Refresh CRM Data", use_container_width=True):
        load_crm_sheet.clear()
        st.session_state.crm_force_refresh += 1
        st.rerun()

try:
    crm_df_raw, fetched_at = load_crm_sheet()
    crm_df = add_analysis_columns(crm_df_raw)
except Exception as exc:
    logger.exception("Failed to load CRM data: %s", exc)
    st.error(f"Failed to load CRM data: {exc}")
    st.stop()

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="hero">
        <div class="hero-kicker">Sparta Telecom • Executive Dashboard</div>
        <div class="hero-title">CRM Executive Dashboard</div>
        <div class="hero-sub">
            This dashboard reads the CRM mirror directly. CRM terminology and raw values are preserved.
            No Excel / legacy Sparta reconciliation is used here.
        </div>
        <div class="hero-status">
            <span class="status-pill">CRM GID {CRM_MIRROR_WORKSHEET_GID}</span>
            &nbsp;&nbsp; Last refreshed: <strong>{escape(fetched_at)}</strong>
            &nbsp;&nbsp; Rows loaded: <strong>{len(crm_df):,}</strong>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# FILTERS
# ---------------------------------------------------------------------------
st.subheader("📅 Filters")

valid_dates = crm_df["_SaleDateParsed"].dropna()
if valid_dates.empty:
    min_date = date.today()
    max_date = date.today()
else:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()

with st.container(border=True):
    f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.25, 1.25])
    with f1:
        start_date = st.date_input(
            "Start Date",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
            key="crm_start_date",
        )
    with f2:
        end_date = st.date_input(
            "End Date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
            key="crm_end_date",
        )
    with f3:
        advisors = ["All Advisors"] + unique_nonblank(crm_df, "Advisor")
        selected_advisor = st.selectbox("Advisor", advisors, key="crm_advisor")
    with f4:
        months = ["All Months"] + sorted(
            unique_nonblank(crm_df, "Dashboard_Month"),
            key=lambda x: str(x),
            reverse=True,
        )
        selected_dashboard_month = st.selectbox(
            "CRM Dashboard Month",
            months,
            key="crm_dash_month",
        )

if start_date > end_date:
    st.error("Start Date must be earlier than or equal to End Date.")
    st.stop()

mask = crm_df["_SaleDateParsed"].notna()
mask &= crm_df["_SaleDateParsed"].dt.date.ge(start_date)
mask &= crm_df["_SaleDateParsed"].dt.date.le(end_date)

if selected_advisor != "All Advisors":
    mask &= crm_df["Advisor"].eq(selected_advisor)

if selected_dashboard_month != "All Months":
    mask &= crm_df["Dashboard_Month"].fillna("").astype(str).str.strip().eq(
        selected_dashboard_month
    )

filtered = crm_df.loc[mask].copy()

st.caption(
    f"Showing {len(filtered):,} CRM records from {start_date.strftime('%d/%m/%Y')} to "
    f"{end_date.strftime('%d/%m/%Y')}. Blank Welcome Call Status values are not counted as Welcome Pending."
)

# ---------------------------------------------------------------------------
# KPI SECTION
# ---------------------------------------------------------------------------
st.subheader("📌 Executive KPIs")

total = len(filtered)
qa_approved = exact_count(filtered, "Quality Status", "QA-Approved")
qa_rework = exact_count(filtered, "Quality Status", "Rework")
qa_reject = exact_count(filtered, "Quality Status", "QA-Reject")
qa_pending = exact_count(filtered, "Quality Status", "QA-Pending")

welcome_approved = exact_count(filtered, "Welcome Call Status", "Welcome Approved")
welcome_rejected = exact_count(filtered, "Welcome Call Status", "Welcome Rejected")
welcome_followup = exact_count(filtered, "Welcome Call Status", "Welcome Followup")
welcome_blank = int(
    filtered["Welcome Call Status"].fillna("").astype(str).str.strip().eq("").sum()
)

confirmation_approved = exact_count(filtered, "Confirmation Status", "Confirmation Approved")
confirmation_followup = exact_count(filtered, "Confirmation Status", "Confirmation Followup")
confirmation_pending = exact_count(filtered, "Confirmation Status", "Confirmation Pending")
committed_rem = confirmation_approved + confirmation_followup + confirmation_pending

live_cancelled = exact_count(filtered, "Confirmation Status", "To Be Cancelled")

onboarding_counts = (
    filtered["Final Status"]
    .replace("", "(blank)")
    .fillna("(blank)")
    .value_counts()
)

kpis = [
    ("Applications", total, "100% CRM base"),
    ("QA Approved", qa_approved, pct(qa_approved, total)),
    ("QA Rework", qa_rework, pct(qa_rework, total)),
    ("QA Cancelled", qa_reject, pct(qa_reject, total)),
    ("QA Pending", qa_pending, pct(qa_pending, total)),
    ("Welcome Done", welcome_approved, pct(welcome_approved, total)),
    ("Welcome Cancelled", welcome_rejected, pct(welcome_rejected, total)),
    ("Welcome Pending", welcome_followup, pct(welcome_followup, total)),
    ("Committed Rem.", committed_rem, pct(committed_rem, total)),
    ("Live Cancelled", live_cancelled, pct(live_cancelled, total)),
]

cols = st.columns(5)
for i, (label, value, sub) in enumerate(kpis):
    with cols[i % 5]:
        st.markdown(
            f"""
            <div class="kpi">
                <div class="kpi-label">{escape(label)}</div>
                <div class="kpi-value">{value:,}</div>
                <div class="kpi-sub">{escape(sub)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# FINAL STATUS OVERVIEW
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📡 CRM Final Status")
st.markdown(
    '<div class="section-note">Exact values from <b>Committed (Live) Status (Onboarding Status)</b>; blanks remain blanks.</div>',
    unsafe_allow_html=True,
)

if not onboarding_counts.empty:
    final_status_df = onboarding_counts.rename_axis("Final Status").reset_index(name="Records")
    final_status_df["% of Applications"] = (
        final_status_df["Records"] / max(total, 1) * 100
    ).round(1)
    st.dataframe(
        final_status_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Records": st.column_config.NumberColumn(format="%d"),
            "% of Applications": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
else:
    st.info("No Final Status values are available for the selected filters.")

# ---------------------------------------------------------------------------
# MONTHLY EXECUTIVE BREAKDOWN
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📅 Monthly CRM Breakdown")
st.markdown(
    '<div class="section-note">Built directly from CRM Sale Date and the CRM status fields.</div>',
    unsafe_allow_html=True,
)

monthly_base = filtered[filtered["_SaleDateParsed"].notna()].copy()
if not monthly_base.empty:
    monthly_base["Month"] = monthly_base["_SaleDateParsed"].dt.to_period("M")
    grouped = []
    for period, grp in monthly_base.groupby("Month", sort=False):
        apps = len(grp)
        qa_a = exact_count(grp, "Quality Status", "QA-Approved")
        qa_r = exact_count(grp, "Quality Status", "Rework")
        qa_c = exact_count(grp, "Quality Status", "QA-Reject")
        qa_p = exact_count(grp, "Quality Status", "QA-Pending")
        w_a = exact_count(grp, "Welcome Call Status", "Welcome Approved")
        w_r = exact_count(grp, "Welcome Call Status", "Welcome Rejected")
        w_f = exact_count(grp, "Welcome Call Status", "Welcome Followup")
        c_a = exact_count(grp, "Confirmation Status", "Confirmation Approved")
        c_f = exact_count(grp, "Confirmation Status", "Confirmation Followup")
        c_p = exact_count(grp, "Confirmation Status", "Confirmation Pending")
        lc = exact_count(grp, "Confirmation Status", "To Be Cancelled")
        grouped.append(
            {
                "MONTH": period.strftime("%B %Y"),
                "APPLICATIONS": apps,
                "QA APPROVED": qa_a,
                "QA REWORK": qa_r,
                "QA CANCELLED": qa_c,
                "QA PENDING": qa_p,
                "WELCOME DONE": w_a,
                "WELCOME CANCELLED": w_r,
                "WELCOME PENDING": w_f,
                "COMMITTED REM.": c_a + c_f + c_p,
                "LIVE CANCELLED": lc,
                "QA Pass %": round(qa_a / apps * 100, 1) if apps else 0,
                "Welcome Done %": round(w_a / apps * 100, 1) if apps else 0,
            }
        )

    monthly_df = pd.DataFrame(grouped)
    if not monthly_df.empty:
        # newest month first
        monthly_df["_sort"] = pd.PeriodIndex(monthly_df["MONTH"], freq="M")
        monthly_df = monthly_df.sort_values("_sort", ascending=False).drop(columns="_sort")
        st.dataframe(
            monthly_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "QA Pass %": st.column_config.NumberColumn(format="%.1f%%"),
                "Welcome Done %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
else:
    st.info("No monthly data is available for the selected filters.")

# ---------------------------------------------------------------------------
# SALES EXECUTIVE PERFORMANCE
# ---------------------------------------------------------------------------
st.divider()
st.subheader("👥 Sales Executive Performance")
st.markdown(
    '<div class="section-note">Advisor values are taken directly from <b>Advisor (Created Username)</b>.</div>',
    unsafe_allow_html=True,
)

if not filtered.empty:
    rows = []
    for advisor, grp in filtered.groupby("Advisor", dropna=False):
        name = str(advisor).strip() or "Unassigned"
        apps = len(grp)
        qa_a = exact_count(grp, "Quality Status", "QA-Approved")
        qa_r = exact_count(grp, "Quality Status", "Rework")
        qa_c = exact_count(grp, "Quality Status", "QA-Reject")
        qa_p = exact_count(grp, "Quality Status", "QA-Pending")
        w_a = exact_count(grp, "Welcome Call Status", "Welcome Approved")
        w_r = exact_count(grp, "Welcome Call Status", "Welcome Rejected")
        w_f = exact_count(grp, "Welcome Call Status", "Welcome Followup")
        c_a = exact_count(grp, "Confirmation Status", "Confirmation Approved")
        c_f = exact_count(grp, "Confirmation Status", "Confirmation Followup")
        c_p = exact_count(grp, "Confirmation Status", "Confirmation Pending")
        lc = exact_count(grp, "Confirmation Status", "To Be Cancelled")
        rows.append(
            {
                "SALES EXECUTIVE": name,
                "APPLICATIONS": apps,
                "QA APPROVED": qa_a,
                "QA REWORK": qa_r,
                "QA CANCELLED": qa_c,
                "QA PENDING": qa_p,
                "WELCOME DONE": w_a,
                "WELCOME CANCELLED": w_r,
                "WELCOME PENDING": w_f,
                "COMMITTED REM.": c_a + c_f + c_p,
                "LIVE CANCELLED": lc,
                "QA Pass %": round(qa_a / apps * 100, 1) if apps else 0,
                "Welcome Done %": round(w_a / apps * 100, 1) if apps else 0,
            }
        )

    advisor_df = pd.DataFrame(rows).sort_values("APPLICATIONS", ascending=False)
    st.dataframe(
        advisor_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "QA Pass %": st.column_config.NumberColumn(format="%.1f%%"),
            "Welcome Done %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
else:
    st.info("No advisor performance data is available for the selected filters.")

# ---------------------------------------------------------------------------
# RAW CRM STATUS BREAKDOWNS
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🔎 CRM Status Values")
st.markdown(
    '<div class="section-note">These tables show the CRM values exactly as they exist in the worksheet.</div>',
    unsafe_allow_html=True,
)

b1, b2, b3 = st.columns(3)
with b1:
    qa_raw = (
        filtered["Quality Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "(blank)")
        .value_counts()
        .rename_axis("Quality Status")
        .reset_index(name="Records")
    )
    st.markdown("**Quality Status**")
    st.dataframe(qa_raw, use_container_width=True, hide_index=True)
with b2:
    welcome_raw = (
        filtered["Welcome Call Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "(blank)")
        .value_counts()
        .rename_axis("Welcome Call Status")
        .reset_index(name="Records")
    )
    st.markdown("**Welcome Call Status**")
    st.dataframe(welcome_raw, use_container_width=True, hide_index=True)
with b3:
    confirmation_raw = (
        filtered["Confirmation Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "(blank)")
        .value_counts()
        .rename_axis("Confirmation Status")
        .reset_index(name="Records")
    )
    st.markdown("**Confirmation Status**")
    st.dataframe(confirmation_raw, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# FULL CRM RECORDS
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📋 Full CRM Records")
st.markdown(
    '<div class="section-note">Exact CRM columns are shown below. <b>Final Status</b> is a direct copy of the CRM onboarding-status field.</div>',
    unsafe_allow_html=True,
)

# Put key fields first, then every source column.
key_cols = [
    "Sale Date",
    "Advisor (Created Username)",
    "Customer Name",
    "Phone Number",
    "Quality Status",
    "Welcome Call Status",
    "Provisioning Status",
    "LetterStatus (Dispatch Status)",
    "Confirmation Status",
    "Final Status",
    "Standardized_Date",
    "Dashboard_Month",
]
full_cols = [c for c in key_cols if c in filtered.columns]
full_cols += [c for c in EXPECTED_COLUMNS if c in filtered.columns and c not in full_cols]
# Include any additional CRM columns after the expected structure.
full_cols += [c for c in filtered.columns if not c.startswith("_") and c not in full_cols]
full_cols = list(dict.fromkeys(full_cols))

search = st.text_input(
    "Search CRM records",
    value="",
    placeholder="Customer name, phone, advisor, status, remarks...",
    key="crm_search",
)

records_for_display = filtered.copy()
if search.strip():
    term = search.strip().casefold()
    visible_mask = pd.Series(False, index=records_for_display.index)
    text_cols = [c for c in records_for_display.columns if not c.startswith("_")]
    for col in text_cols:
        visible_mask |= records_for_display[col].fillna("").astype(str).str.casefold().str.contains(term, regex=False)
    records_for_display = records_for_display.loc[visible_mask].copy()

st.caption(f"Records displayed: {len(records_for_display):,}")
if not records_for_display.empty:
    display_df = records_for_display[full_cols].copy()
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=620,
    )
else:
    st.info("No CRM records match the current filters/search.")

# ---------------------------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------------------------
export_df = records_for_display[full_cols].copy() if not records_for_display.empty else pd.DataFrame(columns=full_cols)
export_csv = export_df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ Export Filtered CRM Records (CSV)",
    data=export_csv,
    file_name=f"sparta_crm_executive_{datetime.now():%Y%m%d_%H%M%S}.csv",
    mime="text/csv",
    use_container_width=False,
)

st.markdown(
    '<div style="text-align:center;color:#94a3b8;font-size:.66rem;margin-top:18px;">'
    'Sparta Executive Dashboard • CRM-only source • Raw CRM terminology preserved'
    '</div>',
    unsafe_allow_html=True,
)
