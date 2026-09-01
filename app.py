"""
Updated app.py - adds a totals row to the Sales Executive Performance Breakdown table.

Notes:
- Totals row sums numeric columns and computes overall percentage pills.
- Totals raw-status tooltips are generated using the filtered master_df (same source as the advisor rows).
- The Data Preview section remains commented out per earlier request.
"""
import logging
import re
import time
from datetime import datetime
from html import escape
from typing import List, Optional

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ----------------------------------------------------------
# Basic logging
# ----------------------------------------------------------
logger = logging.getLogger("sparta_dash")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="Sparta Sales Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS (kept inline for single-file convenience)
st.markdown(
    """
<style>
/* condensed CSS kept from the original - tweak or externalize as needed */
[data-testid="stMetric"] { border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 4px !important; box-shadow: 0 1px 3px rgba(0,0,0,0.04); text-align: center !important; }
[data-testid="stMetricLabel"] { font-size: 0.58rem !important; font-weight:700 !important; color:#475569; text-transform:uppercase; }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# CONFIG / CONSTANTS
# ==========================================================
SPREADSHEET_ID: str = st.secrets.get("SPREADSHEET_ID", "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ")
APPLICATION_SHEET: str = st.secrets.get("APPLICATION_SHEET", "Sparta")
LIVE_SHEET: str = st.secrets.get("LIVE_SHEET", "Sparta2")
SCOPES: List[str] = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

NEW_ADVISORS = ["Subhodeep", "Ravikant", "Priyanshu", "Kajal", "Vishal", "Aryan", "Shivam"]
CUSTOMER_SERVICE_ADVISORS = ["Aman", "Ravi Inbound", "Santosh Joshi", "Vijender", "Laxmi Narayan"]
LEFT_ADVISORS = [
    "Gaurav", "Guru", "Niki", "Shaheen", "Manmeet", "Gungun", "Rani", "Archana", "Deepali", "Sushanshu",
    "Supreme", "Tokivi", "Sangeeta", "Vijay", "Khushbu", "Kushal", "Nishant", "Pawan", "Mehak", "Khushboo", "Ashima",
    "Aarti", "Abhay", "Diwakar", "Manshay", "Khusboo", "Manmet", "Lakshay", "Sneha", "Swarali", "Monica", "Paras",
    "Veer", "Yash", "Sudhanshu", "Rishabh", "Krrish", "Anshu", "Edwin", "Sravan"
]

NEW_ADVISORS_SET = {a.strip().lower() for a in NEW_ADVISORS}
CS_ADVISORS_SET = {a.strip().lower() for a in CUSTOMER_SERVICE_ADVISORS}
LEFT_ADVISORS_SET = {a.strip().lower() for a in LEFT_ADVISORS}

# ==========================================================
# Google Sheets client (cached resource)
# ==========================================================
@st.cache_resource
def get_google_service():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Missing gcp_service_account in Streamlit secrets.")
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    logger.info("Google Sheets client created")
    return service

def load_sheet(sheet_name: str, max_retries: int = 3, backoff: float = 1.0) -> pd.DataFrame:
    service = get_google_service()
    for attempt in range(1, max_retries + 1):
        try:
            result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=sheet_name).execute()
            values = result.get("values", [])
            if not values:
                return pd.DataFrame()
            headers, rows = values[0], values[1:]
            max_cols = len(headers)
            cleaned_rows = [
                r + [""] * (max_cols - len(r)) if len(r) < max_cols else r[:max_cols]
                for r in rows
            ]
            df = pd.DataFrame(cleaned_rows, columns=headers)
            logger.info("Loaded sheet '%s' with %d rows", sheet_name, len(df))
            return df
        except HttpError as e:
            logger.warning("HttpError reading sheet %s (attempt %d/%d): %s", sheet_name, attempt, max_retries, e)
        except Exception as e:
            logger.exception("Unexpected error reading sheet %s (attempt %d/%d): %s", sheet_name, attempt, max_retries, e)
        if attempt < max_retries:
            time.sleep(backoff * (2 ** (attempt - 1)))
    raise RuntimeError(f"Failed to load sheet {sheet_name} after {max_retries} attempts")

@st.cache_data(ttl=300, show_spinner=False)
def load_sheet_cached(sheet_name: str) -> pd.DataFrame:
    return load_sheet(sheet_name)

# ==========================================================
# DATA CLEANING & VECTORIZED CATEGORIZATION
# ==========================================================
PHONE_RE = re.compile(r"\D")

def clean_phone(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace(PHONE_RE, "", regex=True).str.lstrip("0").str.strip()

def parse_mixed_dates_value(val) -> pd.Timestamp:
    if pd.isna(val) or str(val).strip().lower() in {"", "(blank)", "nan", "none"}:
        return pd.NaT
    val_str = str(val).strip()
    iso_match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", val_str)
    if iso_match:
        year, month, day = iso_match.groups()
        try:
            return pd.Timestamp(year=int(year), month=int(month), day=int(day))
        except ValueError:
            pass
    uk_match = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", val_str)
    if uk_match:
        day, month, year = uk_match.groups()
        try:
            return pd.Timestamp(year=int(year), month=int(month), day=int(day))
        except ValueError:
            pass
    return pd.to_datetime(val_str, errors="coerce", dayfirst=True)

def parse_date_series(series: pd.Series) -> pd.Series:
    return series.apply(parse_mixed_dates_value)

def format_date_ddmmyyyy(series: pd.Series) -> pd.Series:
    parsed = parse_date_series(series)
    return parsed.dt.strftime("%d/%m/%Y").fillna("")

def categorize_quality_status_series(s: pd.Series) -> pd.Series:
    s_norm = s.fillna("").astype(str).str.strip().str.lower()
    pending_mask = s_norm.isin(["", "(blank)", "nan", "none"])
    approved_mask = s_norm.str.contains("appr", na=False)
    rework_mask = s_norm.str.contains("rework", na=False)
    cancelled_mask = s_norm.str.contains(r"cancel|reject|hold|duplicat|inbound|n/a|rec in accessible", na=False)
    return pd.Series(
        np.select(
            [pending_mask, approved_mask, rework_mask, cancelled_mask],
            ["Pending", "Approved", "Rework", "Cancelled"],
            default="Cancelled"
        ),
        index=s.index,
    )

def categorize_welcome_status_series(s: pd.Series) -> pd.Series:
    s_norm = s.fillna("").astype(str).str.strip().str.lower()
    pending_mask = s_norm.isin(["", "(blank)", "nan", "none"]) | s_norm.str.contains(r"pending|follow|paperwork|wrong|ring", na=False)
    done_mask = s_norm.str.contains("done", na=False)
    cancelled_mask = s_norm.str.contains(r"cancel|reject|hold", na=False)
    return pd.Series(
        np.select([pending_mask, done_mask, cancelled_mask], ["Pending", "Done", "Cancelled"], default="Pending"),
        index=s.index,
    )

def categorize_portal_status_series(s: pd.Series) -> pd.Series:
    s_norm = s.fillna("").astype(str).str.strip().str.lower()
    committed_mask = s_norm.isin(["", "(blank)", "nan", "none"]) | s_norm.str.contains(r"commit|in progress|processing", na=False)
    cancelled_mask = s_norm.str.contains(r"cancel|reject", na=False)
    live_mask = s_norm.str.contains(r"live|pending|active|completed", na=False)
    return pd.Series(
        np.select([cancelled_mask, live_mask, committed_mask], ["Cancelled", "Live", "Committed"], default="Committed"),
        index=s.index,
    )

def get_raw_breakdown(df: pd.DataFrame, raw_col: str, clean_col: str, target_val: str):
    if raw_col not in df.columns or clean_col not in df.columns:
        return []
    mask = df[clean_col] == target_val
    raw_values = df.loc[mask, raw_col].fillna("(blank)").astype(str).str.strip().replace("", "(blank)")
    if raw_values.empty:
        return []
    counts = raw_values.value_counts()
    return [(str(rv), int(cnt)) for rv, cnt in counts.items()]

def format_raw_breakdown(df: pd.DataFrame, raw_col: str, clean_col: str, target_val: str) -> str:
    breakdown = get_raw_breakdown(df, raw_col, clean_col, target_val)
    if not breakdown:
        return ""
    lines = [f"{raw}: {count}" for raw, count in breakdown]
    total = sum(count for _, count in breakdown)
    return "Raw Status Breakdown\n" + "\n".join(lines) + f"\nTotal: {total}"

# ==========================================================
# DATA LOADING
# ==========================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_sparta() -> pd.DataFrame:
    df = load_sheet_cached(APPLICATION_SHEET)
    if df.empty:
        return df
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
        "Standardized_Date": "Standardized Date",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    keep_columns = [c for c in rename_map.values() if c in df.columns]
    df = df[keep_columns].copy()
    if "Telephone No." in df.columns:
        df["Telephone No."] = clean_phone(df["Telephone No."])
    if "Sale Date" in df.columns:
        df["Sale Date Clean"] = parse_date_series(df["Sale Date"])
        df["Sale Date"] = format_date_ddmmyyyy(df["Sale Date"])
    for col in ["Quality Date", "Welcome Date", "Provisioning Date", "Standardized Date"]:
        if col in df.columns:
            df[col] = format_date_ddmmyyyy(df[col])
    if "Quality Status" in df.columns:
        df["Quality Status Clean"] = categorize_quality_status_series(df["Quality Status"])
    if "Welcome Status" in df.columns:
        df["Welcome Status Clean"] = categorize_welcome_status_series(df["Welcome Status"])
    return df

@st.cache_data(ttl=300, show_spinner=False)
def load_sparta2() -> pd.DataFrame:
    df = load_sheet_cached(LIVE_SHEET)
    if df.empty:
        return df
    rename_map = {
        "Sale Date": "Sale Date",
        "Telephone No.": "Telephone No.",
        "Committed Date": "Live Date",
        "Status": "Portal Status",
        "LetterStatus": "Letter Status",
        "CallStatus": "Call Status",
        "Comments": "Comments",
        "Voice of Customer": "Voice of Customer",
        "Cancellation Reason": "Portal Cancellation",
        "Dashboard_Month": "Dashboard Month",
        "Standardized_Date": "Standardized Date",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    keep_columns = [c for c in rename_map.values() if c in df.columns]
    df = df[keep_columns].copy()
    if "Telephone No." in df.columns:
        df["Telephone No."] = clean_phone(df["Telephone No."])
    if "Sale Date" in df.columns:
        df["Sale Date Clean"] = parse_date_series(df["Sale Date"])
        df["Sale Date"] = format_date_ddmmyyyy(df["Sale Date"])
    for date_col in ["Live Date", "Standardized Date"]:
        if date_col in df.columns:
            df[date_col] = format_date_ddmmyyyy(df[date_col])
    if "Portal Status" in df.columns:
        df["Portal Status Clean"] = categorize_portal_status_series(df["Portal Status"])
    return df

with st.spinner("Loading Google Sheets..."):
    try:
        sparta_df = load_sparta()
        sparta2_df = load_sparta2()
    except Exception as e:
        st.error("Failed to load Google Sheets data. See logs for details.")
        logger.exception("Failed to load sheets: %s", e)
        st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def build_master_dataframe(app_df: pd.DataFrame, portal_df: pd.DataFrame) -> pd.DataFrame:
    apps = app_df.copy()
    portal = portal_df.copy()
    if "Telephone No." in portal.columns:
        portal = portal[portal["Telephone No."] != ""].copy()
        portal = portal.drop_duplicates(subset="Telephone No.", keep="last")
    if "Telephone No." in apps.columns and "Telephone No." in portal.columns:
        merged = apps.merge(portal, on="Telephone No.", how="left", suffixes=("", "_portal"))
    else:
        merged = apps.copy()
    return merged

master_raw_df = build_master_dataframe(sparta_df, sparta2_df)

def assign_periods(df: pd.DataFrame, date_col: str = "Sale Date Clean", default_period: str = "2026-01"):
    if date_col in df.columns and not df[date_col].dropna().empty:
        df["Month_Year"] = df[date_col].dt.strftime("%B %Y")
        df["Period_Sort"] = df[date_col].dt.to_period("M")
    else:
        df["Month_Year"] = "Unknown"
        df["Period_Sort"] = pd.Period(default_period, freq="M")
    return df

master_raw_df = assign_periods(master_raw_df)
sparta2_df = assign_periods(sparta2_df)

# ==========================================================
# FILTERS SECTION
# ==========================================================
st.subheader("📅 Filters")

if "Sale Date Clean" in master_raw_df.columns and not master_raw_df["Sale Date Clean"].dropna().empty:
    available_months = ["All Months"] + list(
        master_raw_df["Sale Date Clean"].dt.to_period("M").drop_duplicates().sort_values(ascending=False).dt.strftime("%B %Y")
    )
else:
    available_months = ["All Months"]

valid_dates = master_raw_df["Sale Date Clean"].dropna() if "Sale Date Clean" in master_raw_df.columns else pd.Series(dtype="datetime64[ns]")
min_date = valid_dates.min().date() if not valid_dates.empty else datetime.today().date()
max_date = valid_dates.max().date() if not valid_dates.empty else datetime.today().date()

filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])
with filter_col1:
    selected_month = st.selectbox("Select Month", options=available_months, index=0)
with filter_col2:
    start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
with filter_col3:
    end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

st.markdown("##### Tag Visibility Filters")
tag_col1, tag_col2, tag_col3, tag_col4 = st.columns([1, 1, 1, 1])
with tag_col1:
    include_new = st.checkbox("Include 'New' Agents", value=True)
with tag_col2:
    include_cs = st.checkbox("Include 'Customer Service' Agents", value=True)
with tag_col3:
    include_left = st.checkbox("Include 'Left' Agents", value=False)
with tag_col4:
    include_untagged = st.checkbox("Include Untagged Names", value=True)

if start_date > end_date:
    st.error("Error: Start Date must be earlier than or equal to End Date.")
    master_df = master_raw_df.copy()
    filtered_portal_df = sparta2_df.copy()
else:
    if "Sale Date Clean" in master_raw_df.columns:
        date_mask = (master_raw_df["Sale Date Clean"].dt.date >= start_date) & (master_raw_df["Sale Date Clean"].dt.date <= end_date)
        if selected_month != "All Months":
            date_mask &= master_raw_df["Month_Year"] == selected_month
        master_df = master_raw_df[date_mask].copy()
    else:
        master_df = master_raw_df.copy()

    if "Sale Date Clean" in sparta2_df.columns:
        portal_date_mask = (sparta2_df["Sale Date Clean"].dt.date >= start_date) & (sparta2_df["Sale Date Clean"].dt.date <= end_date)
        if selected_month != "All Months":
            portal_date_mask &= sparta2_df["Month_Year"] == selected_month
        filtered_portal_df = sparta2_df[portal_date_mask].copy()
    else:
        filtered_portal_df = sparta2_df.copy()

# ==========================================================
# TOP KPI SECTION
# ==========================================================
st.subheader("📌 Key Performance Indicators")

def count_status(df: pd.DataFrame, column: str, target_val: str) -> int:
    return int((df[column] == target_val).sum()) if column in df.columns else 0

def get_pct(part: int, total: int) -> str:
    return "0.0%" if total == 0 else f"{(part / total * 100):.1f}%"

total_applications = len(master_df)
portal_total = len(filtered_portal_df)

q_approved = count_status(master_df, "Quality Status Clean", "Approved")
q_rework = count_status(master_df, "Quality Status Clean", "Rework")
q_cancelled = count_status(master_df, "Quality Status Clean", "Cancelled")
q_pending = count_status(master_df, "Quality Status Clean", "Pending")

wc_done = count_status(master_df, "Welcome Status Clean", "Done")
wc_cancelled = count_status(master_df, "Welcome Status Clean", "Cancelled")
wc_pending = count_status(master_df, "Welcome Status Clean", "Pending")

portal_live = count_status(filtered_portal_df, "Portal Status Clean", "Live")
portal_committed = count_status(filtered_portal_df, "Portal Status Clean", "Committed")
portal_cancelled = count_status(filtered_portal_df, "Portal Status Clean", "Cancelled")

all_kpis = [
    ("Applications", total_applications, "100% Base", "#3b82f6", "#eff6ff", "#1d4ed8"),
    ("Quality Approved", q_approved, f"{get_pct(q_approved, total_applications)} Qualified", "#10b981", "#f0fdf4", "#15803d"),
    ("Quality Rework", q_rework, f"{get_pct(q_rework, total_applications)} In Rework", "#f59e0b", "#fefce8", "#b45309"),
    ("Quality Cancelled", q_cancelled, f"{get_pct(q_cancelled, total_applications)} Rejected", "#ef4444", "#fef2f2", "#b91c1c"),
    ("Quality Pending", q_pending, f"{get_pct(q_pending, total_applications)} Pending", "#f97316", "#fff7ed", "#c2410c"),
    ("Welcome Done", wc_done, f"{get_pct(wc_done, total_applications)} Completed", "#10b981", "#f0fdf4", "#15803d"),
    ("Welcome Cancelled", wc_cancelled, f"{get_pct(wc_cancelled, total_applications)} Cancelled", "#ef4444", "#fef2f2", "#b91c1c"),
    ("Welcome Pending", wc_pending, f"{get_pct(wc_pending, total_applications)} Pending", "#f59e0b", "#fefce8", "#b45309"),
    ("Live Status: Live", portal_live, f"{get_pct(portal_live, portal_total)} Live/Pend.", "#14b8a6", "#f0fdfa", "#0f766e"),
    ("Live Status: Comm.", portal_committed, f"{get_pct(portal_committed, portal_total)} Pipeline", "#f59e0b", "#fefce8", "#b45309"),
    ("Live Status: Canc.", portal_cancelled, f"{get_pct(portal_cancelled, portal_total)} Churned", "#ef4444", "#fef2f2", "#b91c1c"),
]

visible_kpis = [k for k in all_kpis if k[1] > 0]

if visible_kpis:
    cols = st.columns(len(visible_kpis))
    for col, (label, val, delta_sub, border_col, bg_col, delta_col) in zip(cols, visible_kpis):
        with col:
            st.markdown(
                f"""
                <div style="border:1px solid #e2e8f0;border-top:4px solid {border_col};background-color:{bg_col};border-radius:8px;padding:8px 4px; text-align:center;">
                    <div style="font-size:0.58rem;font-weight:700;color:#475569;text-transform:uppercase;">{label}</div>
                    <div style="font-size:1.3rem;font-weight:800;color:#0f172a;margin-top:6px;">{val:,}</div>
                    <div style="font-size:0.62rem;font-weight:700;color:{delta_col};margin-top:4px;">{delta_sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("No active KPIs for the selected filters.")

# ==========================================================
# MONTHLY KPI BREAKDOWN (SELECTABLE YEAR)
# ==========================================================
st.divider()
st.subheader("📅 Monthly KPI Breakdown")

current_year = datetime.now().year
years = list(range(2022, current_year + 1))
selected_year = st.selectbox("Select year for monthly breakdown", options=years, index=len(years) - 1)

monthly_app_df = master_raw_df.dropna(subset=["Period_Sort"]).copy()
monthly_app_df = monthly_app_df[monthly_app_df["Period_Sort"].dt.year == int(selected_year)]

monthly_portal_df = sparta2_df.dropna(subset=["Period_Sort"]).copy()
monthly_portal_df = monthly_portal_df[monthly_portal_df["Period_Sort"].dt.year == int(selected_year)]

all_periods = sorted(list(set(monthly_app_df["Period_Sort"]).union(set(monthly_portal_df["Period_Sort"]))), reverse=True)

if not all_periods:
    st.info(f"No {selected_year} monthly data available for the KPI summary table.")
else:
    def build_monthly_summary(month_periods):
        rows = []
        for period in month_periods:
            m_str = period.strftime("%B %Y")
            m_app = monthly_app_df[monthly_app_df["Period_Sort"] == period]
            m_portal = monthly_portal_df[monthly_portal_df["Period_Sort"] == period]
            m_total_apps = len(m_app)
            m_qa_approved = count_status(m_app, "Quality Status Clean", "Approved")
            m_qa_rework = count_status(m_app, "Quality Status Clean", "Rework")
            m_qa_cancelled = count_status(m_app, "Quality Status Clean", "Cancelled")
            m_qa_pending = count_status(m_app, "Quality Status Clean", "Pending")
            m_wc_done = count_status(m_app, "Welcome Status Clean", "Done")
            m_wc_cancelled = count_status(m_app, "Welcome Status Clean", "Cancelled")
            m_wc_pending = count_status(m_app, "Welcome Status Clean", "Pending")
            m_p_live = count_status(m_portal, "Portal Status Clean", "Live")
            m_p_committed = count_status(m_portal, "Portal Status Clean", "Committed")
            m_p_cancelled = count_status(m_portal, "Portal Status Clean", "Cancelled")

            qa_approved_raw = format_raw_breakdown(m_app, "Quality Status", "Quality Status Clean", "Approved")
            qa_rework_raw = format_raw_breakdown(m_app, "Quality Status", "Quality Status Clean", "Rework")
            qa_cancelled_raw = format_raw_breakdown(m_app, "Quality Status", "Quality Status Clean", "Cancelled")
            qa_pending_raw = format_raw_breakdown(m_app, "Quality Status", "Quality Status Clean", "Pending")

            welcome_done_raw = format_raw_breakdown(m_app, "Welcome Status", "Welcome Status Clean", "Done")
            welcome_cancelled_raw = format_raw_breakdown(m_app, "Welcome Status", "Welcome Status Clean", "Cancelled")
            welcome_pending_raw = format_raw_breakdown(m_app, "Welcome Status", "Welcome Status Clean", "Pending")

            committed_raw = format_raw_breakdown(m_portal, "Portal Status", "Portal Status Clean", "Committed")
            live_raw = format_raw_breakdown(m_portal, "Portal Status", "Portal Status Clean", "Live")
            live_cancelled_raw = format_raw_breakdown(m_portal, "Portal Status", "Portal Status Clean", "Cancelled")

            rows.append({
                "MONTH": m_str,
                "APPLICATIONS": m_total_apps,
                "QA APPROVED": m_qa_approved,
                "QA APPROVED RAW": qa_approved_raw,
                "QA Pass Rate % Val": (m_qa_approved / m_total_apps * 100) if m_total_apps > 0 else 0.0,
                "QA REWORK": m_qa_rework,
                "QA REWORK RAW": qa_rework_raw,
                "QA CANCELLED": m_qa_cancelled,
                "QA CANCELLED RAW": qa_cancelled_raw,
                "QA PENDING": m_qa_pending,
                "QA PENDING RAW": qa_pending_raw,
                "WELCOME DONE": m_wc_done,
                "WELCOME DONE RAW": welcome_done_raw,
                "Welcome Done % Val": (m_wc_done / m_total_apps * 100) if m_total_apps > 0 else 0.0,
                "WELCOME CANCELLED": m_wc_cancelled,
                "WELCOME CANCELLED RAW": welcome_cancelled_raw,
                "WELCOME PENDING": m_wc_pending,
                "WELCOME PENDING RAW": welcome_pending_raw,
                "COMMITTED REM.": m_p_committed,
                "COMMITTED RAW": committed_raw,
                "LIVE": m_p_live,
                "LIVE RAW": live_raw,
                "Live Conversion % Val": (m_p_live / m_total_apps * 100) if m_total_apps > 0 else 0.0,
                "LIVE CANCELLED": m_p_cancelled,
                "LIVE CANCELLED RAW": live_cancelled_raw,
            })
        return pd.DataFrame(rows)

    monthly_summary_df = build_monthly_summary(all_periods)

    if not monthly_summary_df.empty:
        tot_apps = monthly_summary_df["APPLICATIONS"].sum()
        totals_row = {
            "MONTH": "Total",
            "APPLICATIONS": tot_apps,
            "QA APPROVED": monthly_summary_df["QA APPROVED"].sum(),
            "QA APPROVED RAW": format_raw_breakdown(monthly_app_df, "Quality Status", "Quality Status Clean", "Approved"),
            "QA Pass Rate % Val": (monthly_summary_df["QA APPROVED"].sum() / tot_apps * 100) if tot_apps > 0 else 0.0,
            "QA REWORK": monthly_summary_df["QA REWORK"].sum(),
            "QA REWORK RAW": format_raw_breakdown(monthly_app_df, "Quality Status", "Quality Status Clean", "Rework"),
            "QA CANCELLED": monthly_summary_df["QA CANCELLED"].sum(),
            "QA CANCELLED RAW": format_raw_breakdown(monthly_app_df, "Quality Status", "Quality Status Clean", "Cancelled"),
            "QA PENDING": monthly_summary_df["QA PENDING"].sum(),
            "QA PENDING RAW": format_raw_breakdown(monthly_app_df, "Quality Status", "Quality Status Clean", "Pending"),
            "WELCOME DONE": monthly_summary_df["WELCOME DONE"].sum(),
            "WELCOME DONE RAW": format_raw_breakdown(monthly_app_df, "Welcome Status", "Welcome Status Clean", "Done"),
            "Welcome Done % Val": (monthly_summary_df["WELCOME DONE"].sum() / tot_apps * 100) if tot_apps > 0 else 0.0,
            "WELCOME CANCELLED": monthly_summary_df["WELCOME CANCELLED"].sum(),
            "WELCOME CANCELLED RAW": format_raw_breakdown(monthly_app_df, "Welcome Status", "Welcome Status Clean", "Cancelled"),
            "WELCOME PENDING": monthly_summary_df["WELCOME PENDING"].sum(),
            "WELCOME PENDING RAW": format_raw_breakdown(monthly_app_df, "Welcome Status", "Welcome Status Clean", "Pending"),
            "COMMITTED REM.": monthly_summary_df["COMMITTED REM."].sum(),
            "COMMITTED RAW": format_raw_breakdown(monthly_portal_df, "Portal Status", "Portal Status Clean", "Committed"),
            "LIVE": monthly_summary_df["LIVE"].sum(),
            "LIVE RAW": format_raw_breakdown(monthly_portal_df, "Portal Status", "Portal Status Clean", "Live"),
            "Live Conversion % Val": (monthly_summary_df["LIVE"].sum() / tot_apps * 100) if tot_apps > 0 else 0.0,
            "LIVE CANCELLED": monthly_summary_df["LIVE CANCELLED"].sum(),
            "LIVE CANCELLED RAW": format_raw_breakdown(monthly_portal_df, "Portal Status", "Portal Status Clean", "Cancelled"),
        }
        monthly_summary_df = pd.concat([monthly_summary_df, pd.DataFrame([totals_row])], ignore_index=True)

    def render_pill(val_float: float, thresholds: List[float], good_bg: str = "#d1fae5"):
        val_str = f"{val_float:.1f}%"
        high, med = thresholds
        if val_float >= high:
            bg, color, border = "#d1fae5", "#047857", "#a7f3d0"
        elif val_float >= med:
            bg, color, border = "#fef3c7", "#b45309", "#fde68a"
        else:
            bg, color, border = "#ffe4e6", "#be123c", "#fecdd3"
        return f'<span style="background-color: {bg}; color: {color}; border: 1px solid {border}; border-radius: 8px; padding: 2px 8px; font-weight:700;">{val_str}</span>'

    display_columns = [
        "MONTH", "APPLICATIONS", "QA APPROVED", "QA Pass Rate %",
        "QA REWORK", "QA CANCELLED", "QA PENDING", "WELCOME DONE",
        "Welcome Done %", "WELCOME CANCELLED", "WELCOME PENDING",
        "COMMITTED REM.", "LIVE", "Live Conversion %", "LIVE CANCELLED",
    ]

    m_header_styles = {
        "MONTH": "background-color: #f1f5f9; color: #334155;",
        "APPLICATIONS": "background-color: #eff6ff; color: #1e40af;",
        "QA APPROVED": "background-color: #f0fdf4; color: #15803d;",
        "QA Pass Rate %": "background-color: #f0fdf4; color: #15803d;",
        "QA REWORK": "background-color: #fefce8; color: #a16207;",
        "QA CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
        "QA PENDING": "background-color: #fff7ed; color: #c2410c;",
        "WELCOME DONE": "background-color: #f0fdf4; color: #15803d;",
        "Welcome Done %": "background-color: #f0fdf4; color: #15803d;",
        "WELCOME CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
        "WELCOME PENDING": "background-color: #fefce8; color: #a16207;",
        "COMMITTED REM.": "background-color: #fff7ed; color: #c2410c;",
        "LIVE": "background-color: #f0fdfa; color: #0f766e;",
        "Live Conversion %": "background-color: #f0fdfa; color: #0f766e;",
        "LIVE CANCELLED": "background-color: #fef2f2; color: #b91c1c;",
    }

    m_html = """
    <style>
    .monthly-kpi-table { width:100%; border-collapse:collapse; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial; font-size:0.88rem; }
    .monthly-kpi-table th { padding:10px 12px; font-weight:800; font-size:0.78rem; text-transform:uppercase; text-align:center; border-bottom:2px solid #e2e8f0; }
    .monthly-kpi-table td { padding:10px 12px; text-align:center; border-bottom:1px solid #f1f5f9; }
    .monthly-kpi-table td:first-child, .monthly-kpi-table th:first-child { text-align:left; }
    .monthly-kpi-table tr:last-child { font-weight:800; background-color:#f8fafc; }
    </style>
    <div style="width:100%; overflow-x:auto;">
    <table class="monthly-kpi-table"><thead><tr>
    """
    for col_name in display_columns:
        th_style = m_header_styles.get(col_name, "background-color:#f8fafc;color:#475569;")
        m_html += f'<th style="{th_style}">{col_name}</th>'
    m_html += "</tr></thead><tbody>"

    for _, row in monthly_summary_df.iterrows():
        m_html += "<tr>"
        for col_name in display_columns:
            if col_name == "MONTH":
                m_html += f"<td>{escape(str(row['MONTH']))}</td>"
            elif col_name == "QA Pass Rate %":
                pill = render_pill(row["QA Pass Rate % Val"], thresholds=[75.0, 51.0])
                m_html += f"<td>{pill}</td>"
            elif col_name == "Welcome Done %":
                pill = render_pill(row["Welcome Done % Val"], thresholds=[61.0, 51.0])
                m_html += f"<td>{pill}</td>"
            elif col_name == "Live Conversion %":
                pill = render_pill(row["Live Conversion % Val"], thresholds=[41.0, 21.0])
                m_html += f"<td>{pill}</td>"
            else:
                val = row.get(col_name, 0)
                formatted_val = "-" if (val == 0 or pd.isna(val)) else f"{int(val):,}" if isinstance(val, (int, np.integer)) else escape(str(val))
                tooltip_map = {
                    "QA APPROVED": "QA APPROVED RAW",
                    "QA REWORK": "QA REWORK RAW",
                    "QA CANCELLED": "QA CANCELLED RAW",
                    "QA PENDING": "QA PENDING RAW",
                    "WELCOME DONE": "WELCOME DONE RAW",
                    "WELCOME CANCELLED": "WELCOME CANCELLED RAW",
                    "WELCOME PENDING": "WELCOME PENDING RAW",
                    "COMMITTED REM.": "COMMITTED RAW",
                    "LIVE": "LIVE RAW",
                    "LIVE CANCELLED": "LIVE CANCELLED RAW",
                }
                raw_column = tooltip_map.get(col_name)
                if raw_column and row.get(raw_column) and val != 0:
                    tooltip_text = escape(str(row[raw_column])).replace("\n", "&#10;")
                    m_html += f'<td title="{tooltip_text}" style="cursor:help;">{formatted_val}</td>'
                else:
                    m_html += f"<td>{formatted_val}</td>"
        m_html += "</tr>"
    m_html += "</tbody></table></div>"

    table_height = max(150, 90 + (len(monthly_summary_df) * 45))
    components.html(m_html, height=table_height, scrolling=False)

# ==========================================================
# ADVISOR PERFORMANCE MATRIX (with totals row)
# ==========================================================
st.divider()
st.subheader("👥 Sales Executive Performance Breakdown")

if "Advisor" in master_df.columns and not master_df.empty:
    advisor_summary = (
        master_df.groupby("Advisor", dropna=False)
            .agg(
                Applications=("Advisor", "count"),
                QA_Approved=("Quality Status Clean", lambda x: (x == "Approved").sum()),
                QA_Rework=("Quality Status Clean", lambda x: (x == "Rework").sum()),
                QA_Cancelled=("Quality Status Clean", lambda x: (x == "Cancelled").sum()),
                QA_Pending=("Quality Status Clean", lambda x: (x == "Pending").sum()),
                Welcome_Done=("Welcome Status Clean", lambda x: (x == "Done").sum()),
                Welcome_Cancelled=("Welcome Status Clean", lambda x: (x == "Cancelled").sum()),
                Welcome_Pending=("Welcome Status Clean", lambda x: (x == "Pending").sum()),
                Committed=("Portal Status Clean", lambda x: (x == "Committed").sum()),
                Live=("Portal Status Clean", lambda x: (x == "Live").sum()),
                Live_Cancelled=("Portal Status Clean", lambda x: (x == "Cancelled").sum()),
            )
            .reset_index()
    )

    def filter_tagged_rows(row):
        name = (str(row["Advisor"]) or "").strip().lower()
        is_new = name in NEW_ADVISORS_SET
        is_cs = name in CS_ADVISORS_SET
        is_left = name in LEFT_ADVISORS_SET
        is_tagged = is_new or is_cs or is_left
        if is_new and not include_new:
            return False
        if is_cs and not include_cs:
            return False
        if is_left and not include_left:
            return False
        if not is_tagged and not include_untagged:
            return False
        return True

    advisor_summary = advisor_summary[advisor_summary.apply(filter_tagged_rows, axis=1)].copy()

    if advisor_summary.empty:
        st.info("No sales records match the selected tag filters.")
    else:
        advisor_summary["QA Pass Rate % Val"] = ((advisor_summary["QA_Approved"] / advisor_summary["Applications"].replace(0, np.nan)) * 100).fillna(0.0)
        advisor_summary["Welcome Done % Val"] = ((advisor_summary["Welcome_Done"] / advisor_summary["Applications"].replace(0, np.nan)) * 100).fillna(0.0)
        advisor_summary["Live Conversion % Val"] = ((advisor_summary["Live"] / advisor_summary["Applications"].replace(0, np.nan)) * 100).fillna(0.0)

        advisor_summary = advisor_summary.rename(columns={
            "Advisor": "SALES EXECUTIVE",
            "Applications": "APPLICATIONS",
            "QA_Approved": "QA APPROVED",
            "QA_Rework": "QA REWORK",
            "QA_Cancelled": "QA CANCELLED",
            "QA_Pending": "QA PENDING",
            "Welcome_Done": "WELCOME DONE",
            "Welcome_Cancelled": "WELCOME CANCELLED",
            "Welcome_Pending": "WELCOME PENDING",
            "Committed": "COMMITTED REM.",
            "Live": "LIVE",
            "Live_Cancelled": "LIVE CANCELLED",
        })

        advisor_summary["SALES EXECUTIVE"] = advisor_summary["SALES EXECUTIVE"].replace("", "Unassigned").fillna("Unassigned")
        advisor_summary = advisor_summary.sort_values(by="APPLICATIONS", ascending=False)

        # Build per-advisor raw breakdown tooltips once (use master_df as source)
        advisor_tooltip_mapping = {
            "QA APPROVED": ("Quality Status", "Quality Status Clean", "Approved"),
            "QA REWORK": ("Quality Status", "Quality Status Clean", "Rework"),
            "QA CANCELLED": ("Quality Status", "Quality Status Clean", "Cancelled"),
            "QA PENDING": ("Quality Status", "Quality Status Clean", "Pending"),
            "WELCOME DONE": ("Welcome Status", "Welcome Status Clean", "Done"),
            "WELCOME CANCELLED": ("Welcome Status", "Welcome Status Clean", "Cancelled"),
            "WELCOME PENDING": ("Welcome Status", "Welcome Status Clean", "Pending"),
            "COMMITTED REM.": ("Portal Status", "Portal Status Clean", "Committed"),
            "LIVE": ("Portal Status", "Portal Status Clean", "Live"),
            "LIVE CANCELLED": ("Portal Status", "Portal Status Clean", "Cancelled"),
        }

        raw_tooltips = {}
        # Pre-normalize advisor column in master_df for matching
        master_df["_advisor_norm"] = master_df["Advisor"].fillna("").astype(str).str.strip().str.lower()
        for _, r in advisor_summary.iterrows():
            adv_display = str(r["SALES EXECUTIVE"])
            adv_norm = adv_display.strip().lower()
            subset = master_df[master_df["_advisor_norm"] == adv_norm]
            adv_tooltips = {}
            for k, (raw_col, clean_col, target_val) in advisor_tooltip_mapping.items():
                adv_tooltips[k] = format_raw_breakdown(subset, raw_col, clean_col, target_val)
            raw_tooltips[adv_display] = adv_tooltips
        # drop the helper column
        master_df.drop(columns=["_advisor_norm"], inplace=True, errors=True)

        numeric_cols = {
            "APPLICATIONS", "QA APPROVED", "QA REWORK", "QA CANCELLED", "QA PENDING",
            "WELCOME DONE", "WELCOME CANCELLED", "WELCOME PENDING", "COMMITTED REM.", "LIVE", "LIVE CANCELLED"
        }

        base_col_order = [
            "SALES EXECUTIVE", "APPLICATIONS", "QA APPROVED", "QA Pass Rate %",
            "QA REWORK", "QA CANCELLED", "QA PENDING", "WELCOME DONE", "Welcome Done %",
            "WELCOME CANCELLED", "WELCOME PENDING", "COMMITTED REM.",
            "LIVE", "LIVE CANCELLED", "Live Conversion %"
        ]

        visible_cols = ["SALES EXECUTIVE"]
        for col in base_col_order[1:]:
            if col in numeric_cols:
                if (advisor_summary[col] > 0).any():
                    visible_cols.append(col)
            elif col == "QA Pass Rate %":
                if "QA APPROVED" in visible_cols:
                    visible_cols.append(col)
            elif col == "Welcome Done %":
                if "WELCOME DONE" in visible_cols:
                    visible_cols.append(col)
            elif col == "Live Conversion %":
                if "LIVE" in visible_cols:
                    visible_cols.append(col)

        def render_qa_pill(v): return render_pill(v, [75.0, 51.0])
        def render_welcome_pill(v): return render_pill(v, [61.0, 51.0])
        def render_live_pill(v): return render_pill(v, [41.0, 21.0])

        header_styles = {
            "SALES EXECUTIVE": "background-color:#f1f5f9;color:#334155;",
            "APPLICATIONS": "background-color:#eff6ff;color:#1e40af;",
            "QA APPROVED": "background-color:#f0fdf4;color:#15803d;",
            "QA Pass Rate %": "background-color:#f0fdf4;color:#15803d;",
            "QA REWORK": "background-color:#fefce8;color:#a16207;",
            "QA CANCELLED": "background-color:#fef2f2;color:#b91c1c;",
            "QA PENDING": "background-color:#fff7ed;color:#c2410c;",
            "WELCOME DONE": "background-color:#f0fdf4;color:#15803d;",
            "Welcome Done %": "background-color:#f0fdf4;color:#15803d;",
            "WELCOME CANCELLED": "background-color:#fef2f2;color:#b91c1c;",
            "WELCOME PENDING": "background-color:#fefce8;color:#a16207;",
            "COMMITTED REM.": "background-color:#fff7ed;color:#c2410c;",
            "LIVE": "background-color:#f0fdfa;color:#0f766e;",
            "LIVE CANCELLED": "background-color:#fef2f2;color:#b91c1c;",
            "Live Conversion %": "background-color:#f0fdfa;color:#0f766e;",
        }

        # Compute totals across visible advisors for numeric columns
        totals_series = advisor_summary[list(numeric_cols)].sum(numeric_only=True)
        total_apps = int(totals_series.get("APPLICATIONS", 0))
        total_qa_approved = int(totals_series.get("QA APPROVED", 0))
        total_welcome_done = int(totals_series.get("WELCOME DONE", 0))
        total_live = int(totals_series.get("LIVE", 0))

        # totals percentages (overall)
        total_qa_pass_pct = (total_qa_approved / total_apps * 100) if total_apps > 0 else 0.0
        total_welcome_pct = (total_welcome_done / total_apps * 100) if total_apps > 0 else 0.0
        total_live_pct = (total_live / total_apps * 100) if total_apps > 0 else 0.0

        # totals tooltips using filtered master_df
        totals_tooltips = {}
        for k, (raw_col, clean_col, target_val) in advisor_tooltip_mapping.items():
            totals_tooltips[k] = format_raw_breakdown(master_df, raw_col, clean_col, target_val)

        # Build HTML table for advisors including tooltips for numeric KPI cells + totals row
        html_parts = ['<style>.perf-table{width:100%;border-collapse:collapse;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial;font-size:0.88rem;} .perf-table th{padding:10px 12px;font-weight:800;font-size:0.78rem;text-transform:uppercase;border-bottom:2px solid #e2e8f0;} .perf-table td{padding:8px 12px;border-bottom:1px solid #f1f5f9;} .tag{padding:2px 6px;border-radius:6px;font-weight:700;margin-left:6px;font-size:0.68rem;display:inline-block;vertical-align:middle;} .new{background:#ede9fe;color:#6d28d9;} .cs{background:#e0f2fe;color:#0369a1;} .left{background:#fee2e2;color:#991b1b;} .totals-row{font-weight:800;background-color:#f8fafc;}</style>']
        html_parts.append('<div style="overflow-x:auto;"><table class="perf-table"><thead><tr>')
        for c in visible_cols:
            style = header_styles.get(c, "background-color:#f8fafc;color:#475569;")
            html_parts.append(f'<th style="{style}">{c}</th>')
        html_parts.append('</tr></thead><tbody>')

        for _, r in advisor_summary.iterrows():
            html_parts.append("<tr>")
            for c in visible_cols:
                if c == "SALES EXECUTIVE":
                    name = escape(str(r[c]))
                    lname = name.strip().lower()
                    tags_html = ""
                    if lname in NEW_ADVISORS_SET:
                        tags_html += '<span class="tag new">New</span>'
                    if lname in CS_ADVISORS_SET:
                        tags_html += '<span class="tag cs">Customer Service</span>'
                    if lname in LEFT_ADVISORS_SET:
                        tags_html += '<span class="tag left">Left</span>'
                    html_parts.append(f"<td>{name}{tags_html}</td>")
                elif c == "QA Pass Rate %":
                    html_parts.append(f"<td>{render_qa_pill(r['QA Pass Rate % Val'])}</td>")
                elif c == "Welcome Done %":
                    html_parts.append(f"<td>{render_welcome_pill(r['Welcome Done % Val'])}</td>")
                elif c == "Live Conversion %":
                    html_parts.append(f"<td>{render_live_pill(r['Live Conversion % Val'])}</td>")
                else:
                    val = r[c]
                    formatted_val = "-" if val == 0 or pd.isna(val) else f"{int(val):,}" if isinstance(val, (int, np.integer)) else escape(str(val))
                    # attach tooltip if available
                    adv_display = str(r["SALES EXECUTIVE"])
                    tooltip_text = ""
                    if adv_display in raw_tooltips:
                        tooltip_text = raw_tooltips[adv_display].get(c, "")
                    if tooltip_text and val != 0:
                        tooltip_html = escape(str(tooltip_text)).replace("\n", "&#10;")
                        html_parts.append(f'<td title="{tooltip_html}" style="cursor:help;">{formatted_val}</td>')
                    else:
                        html_parts.append(f"<td>{formatted_val}</td>")
            html_parts.append("</tr>")

        # Add totals row
        html_parts.append('<tr class="totals-row">')
        for c in visible_cols:
            if c == "SALES EXECUTIVE":
                html_parts.append("<td>Total</td>")
            elif c == "QA Pass Rate %":
                html_parts.append(f"<td>{render_qa_pill(total_qa_pass_pct)}</td>")
            elif c == "Welcome Done %":
                html_parts.append(f"<td>{render_welcome_pill(total_welcome_pct)}</td>")
            elif c == "Live Conversion %":
                html_parts.append(f"<td>{render_live_pill(total_live_pct)}</td>")
            else:
                # numeric totals
                if c in numeric_cols:
                    tot_val = int(totals_series.get(c, 0))
                    formatted = "-" if tot_val == 0 else f"{tot_val:,}"
                    # show totals tooltip if available
                    tooltip_text = totals_tooltips.get(c, "")
                    if tooltip_text and tot_val != 0:
                        tooltip_html = escape(str(tooltip_text)).replace("\n", "&#10;")
                        html_parts.append(f'<td title="{tooltip_html}" style="cursor:help;">{formatted}</td>')
                    else:
                        html_parts.append(f"<td>{formatted}</td>")
                else:
                    html_parts.append("<td>-</td>")
        html_parts.append("</tr>")

        html_parts.append("</tbody></table></div>")
        st.markdown("".join(html_parts), unsafe_allow_html=True)
else:
    st.info("No sales records available for the selected date or month filter.")

# ==========================================================
# FOOTER & DATA PREVIEW (COMMENTED OUT)
# ==========================================================


# The data preview section is intentionally commented out per request.
# Uncomment if you want to re-enable the tabs and CSV download.

# preview_sparta = sparta_df.drop(columns=["Sale Date Clean"], errors="ignore")
# preview_sparta2 = sparta2_df.drop(columns=["Sale Date Clean"], errors="ignore")
# preview_master = master_df.drop(columns=["Sale Date Clean"], errors="ignore")

# st.divider()
# st.header("📂 Data Preview")

# tab1, tab2, tab3 = st.tabs(["Applications", "Portal", "Master Dataset"])
# with tab1:
#     st.dataframe(preview_sparta, use_container_width=True, height=450, hide_index=True)
# with tab2:
#     st.dataframe(preview_sparta2, use_container_width=True, height=450, hide_index=True)
# with tab3:
#     st.dataframe(preview_master, use_container_width=True, height=500, hide_index=True)
#     csv = preview_master.to_csv(index=False).encode("utf-8")
#     st.download_button("Download master dataset (CSV)", data=csv, file_name=f"master_dataset_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

# st.divider()
# st.success("✅ Data loaded successfully")
# st.caption(f"Dashboard refreshed at {datetime.now().strftime('%d %b %Y %H:%M:%S')}")


# Keep a minimal footer to confirm load
st.divider()
st.success("✅ Data loaded successfully")
st.caption(f"Dashboard refreshed at {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
