import re
from datetime import date, datetime
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# ============================================================
# GOOGLE SHEET
# ============================================================


def load_google_sheet_data():
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

    missing = [c for c in REQUIRED_HEADERS if c not in df.columns]

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
# LOAD
# ============================================================

try:
    sheet_df, fetched_at = fetch_google_sheet_data()
    queue_df = build_queue_dataframe(sheet_df)
except Exception as exc:
    st.error(f"Unable to load the Sparta CRM Google Sheet: {exc}")
    st.stop()


# ============================================================
# HEADER
# ============================================================

header_left, header_right = st.columns([5, 1], vertical_alignment="center")

with header_left:
    st.caption("SPARTA CRM · OPERATIONS QUEUE")
    st.title("⏳ Sparta Pending Operations")
    st.write(
        "Live records from the CRM mirror showing only workflow stages where "
        "work is genuinely pending. Downstream stages open only after "
        "the previous stage is completed."
    )

with header_right:
    st.caption("Last Google Sheet refresh")
    st.write(f"**{fetched_at}**")


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("⚙️ Queue Controls")
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
        export_df = queue_df.drop(
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
        ).copy()

        export_df["Sale Date"] = pd.to_datetime(
            export_df["Sale Date"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        export_bytes = export_df.to_csv(index=False).encode("utf-8-sig")

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


def count_reason(column, value):
    if queue_df.empty:
        return 0

    return int(
        queue_df[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq(value)
        .sum()
    )


# Quality
quality_pending_count = count_reason("_QualityReason", "QA-Pending")

# Welcome
welcome_followup_count = count_reason("_WelcomeReason", "Followup")
welcome_pending_count = count_reason("_WelcomeReason", "Pending")

# Provisioning
provisioning_pending_count = count_reason("_ProvisioningReason", "Pending")

# Dispatch
dispatch_pending_count = count_reason("_DispatchReason", "Pending")

# Confirmation
confirmation_pending_count = count_reason("_ConfirmationReason", "Pending")

# Live / Onboarding
live_pending_count = (
    int(
        queue_df["_LiveReason"]
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
        queue_df["_PotentialReason"]
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
    "Quality": quality_pending_count,
    "Welcome": welcome_followup_count + welcome_pending_count,
    "Provisioning": provisioning_pending_count,
    "Dispatch": dispatch_pending_count,
    "Confirmation": confirmation_pending_count,
    "Live / Onboarding": live_pending_count,
    "Potential Opportunity": potential_count,
}


# ============================================================
# KPI SECTION
# ============================================================

st.subheader("📊 Pending Breakdown")
st.caption(
    "A blank downstream status becomes Pending only after "
    "the sale has reached that stage. Blank is not shown "
    "as a separate category."
)

row1 = st.columns(5, gap="small")

with row1[0]:
    st.metric("🧪 QA-Pending", quality_pending_count)

with row1[1]:
    st.metric("📞 Welcome Followup", welcome_followup_count)

with row1[2]:
    st.metric("📞 Welcome Pending", welcome_pending_count)

with row1[3]:
    st.metric("⚙️ Provisioning Pending", provisioning_pending_count)

with row1[4]:
    st.metric("✉️ Dispatch Pending", dispatch_pending_count)


row2 = st.columns(4, gap="small")

with row2[0]:
    st.metric("✅ Confirmation Pending", confirmation_pending_count)

with row2[1]:
    st.metric("📡 Live / Onboarding", live_pending_count)

with row2[2]:
    st.metric("🎯 Potential Opportunity", potential_count)

with row2[3]:
    st.metric("📋 Total Pending Sales", len(queue_df))


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

st.subheader("🔎 Filters")
st.caption("Filter the pending queues without changing the underlying CRM data.")

filter_cols = st.columns([2.0, 1.2, 1.2, 1.2])

with filter_cols[0]:
    search_text = st.text_input(
        "Search", placeholder="Customer, phone number or advisor…"
    )

sale_dates = (
    pd.to_datetime(queue_df["Sale Date"], errors="coerce")
    if not queue_df.empty
    else pd.Series(dtype="datetime64[ns]")
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
                for x in queue_df["Advisor"]
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
        "Advisor", options=["All Advisors"] + advisor_options
    )

stage_filter = st.multiselect(
    "Pending Stage",
    options=STAGES,
    format_func=lambda x: f"{STAGE_ICONS[x]} {x}",
    placeholder="All pending stages",
)


# ============================================================
# FILTER DATA
# ============================================================

filtered_df = queue_df.copy()

if not filtered_df.empty:
    filtered_df["_SaleDate"] = pd.to_datetime(
        filtered_df["Sale Date"], errors="coerce"
    )

    filtered_df = filtered_df[
        filtered_df["_SaleDate"].dt.date.between(
            date_from, date_to, inclusive="both"
        )
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
        stage_regex = "|".join(re.escape(stage) for stage in stage_filter)
        filtered_df = filtered_df[
            filtered_df["Pending Stage(s)"]
            .fillna("")
            .str.contains(stage_regex, regex=True, na=False)
        ]

    filtered_df = filtered_df.drop(
        columns=["_SaleDate"], errors="ignore"
    )


st.caption(
    f"Showing {len(filtered_df):,} pending sale(s) from {len(queue_df):,} total pending sale(s)."
)


# ============================================================
# ALL PENDING
# ============================================================

st.subheader("📋 All Pending")
st.caption(
    "One row per sale. Pending Stage(s) shows only stages where the sale is genuinely pending."
)

all_display = filtered_df.drop(
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
).copy()

if not all_display.empty:
    # Header Sort Options Controls
    sort_cols = st.columns([2, 1])
    with sort_cols[0]:
        sort_by = st.selectbox(
            "Sort Table By",
            options=list(all_display.columns),
            index=0,
            key="sort_all_pending_col",
        )
    with sort_cols[1]:
        sort_order = st.radio(
            "Order",
            options=["Ascending", "Descending"],
            horizontal=True,
            key="sort_all_pending_order",
        )

    # Sort logic handling dates properly
    if sort_by == "Sale Date":
        all_display["_temp_sort"] = pd.to_datetime(
            all_display["Sale Date"], errors="coerce"
        )
        all_display = all_display.sort_values(
            by="_temp_sort", ascending=(sort_order == "Ascending")
        ).drop(columns=["_temp_sort"])
    else:
        all_display = all_display.sort_values(
            by=sort_by, ascending=(sort_order == "Ascending")
        )

    all_display["Sale Date"] = pd.to_datetime(
        all_display["Sale Date"], errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    st.dataframe(
        all_display,
        use_container_width=True,
        hide_index=True,
        height=min(
            610,
            max(200, 120 + len(all_display) * 35),
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
            "Pending Stage(s)": st.column_config.TextColumn(
                "PENDING STAGE(S)", width="large"
            ),
            "Pending Detail": st.column_config.TextColumn(
                "PENDING DETAIL", width="large"
            ),
            "Pending Count": st.column_config.NumberColumn(
                "OPEN STAGES", format="%d", width="small"
            ),
        },
    )

else:
    st.info("No pending records match the current filters.")


# ============================================================
# STAGE QUEUES
# ============================================================

st.divider()

st.subheader("🗂️️ Stage Queues")
st.caption(
    "Each tab contains only sales that have actually reached "
    "that workflow stage and are still pending there."
)


queue_tabs = st.tabs(
    [
        f"{STAGE_ICONS[stage]} {stage} ({stage_counts[stage]:,})"
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


for tab, stage in zip(queue_tabs, STAGES):
    with tab:
        reason_column = stage_reason_columns[stage]

        if filtered_df.empty:
            stage_df = pd.DataFrame()
        else:
            stage_df = filtered_df[
                filtered_df[reason_column]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
            ].copy()

        if stage_df.empty:
            st.success(
                f"No {stage} records are pending for the current filters."
            )
            continue

        display_rows = []

        for _, row in stage_df.iterrows():
            reason = safe_text(row.get(reason_column, ""))

            source_rows = sheet_df[
                sheet_df.apply(
                    lambda source_row: make_record_key(
                        source_row.get(API_COLUMNS["sale_date"]),
                        source_row.get(API_COLUMNS["phone"]),
                    )
                    == safe_text(row.get("Record Key", "")),
                    axis=1,
                )
            ]

            source_row = (
                source_rows.iloc[-1] if not source_rows.empty else None
            )

            display_rows.append(
                {
                    "Sale Date": row.get("Sale Date"),
                    "Advisor": row.get("Advisor", ""),
                    "Customer Name": row.get("Customer Name", ""),
                    "Phone Number": row.get("Phone Number", ""),
                    "Pending Stage": stage,
                    "Pending Type": reason,
                    "Current Status": (
                        status_display(source_row, stage)
                        if source_row is not None
                        else ""
                    ),
                    "Remarks / Latest Note": (
                        remarks_display(source_row, stage)
                        if source_row is not None
                        else ""
                    ),
                    "Other Open Stages": row.get("Pending Stage(s)", ""),
                }
            )

        stage_display = pd.DataFrame(display_rows)

        # Header Sort Options for Stage Tab
        tab_sort_cols = st.columns([2, 1])
        with tab_sort_cols[0]:
            stage_sort_by = st.selectbox(
                "Sort Table By",
                options=list(stage_display.columns),
                index=0,
                key=f"sort_stage_col_{stage}",
            )
        with tab_sort_cols[1]:
            stage_sort_order = st.radio(
                "Order",
                options=["Ascending", "Descending"],
                horizontal=True,
                key=f"sort_stage_order_{stage}",
            )

        if stage_sort_by == "Sale Date":
            stage_display["_temp_sort"] = pd.to_datetime(
                stage_display["Sale Date"], errors="coerce"
            )
            stage_display = stage_display.sort_values(
                by="_temp_sort", ascending=(stage_sort_order == "Ascending")
            ).drop(columns=["_temp_sort"])
        else:
            stage_display = stage_display.sort_values(
                by=stage_sort_by, ascending=(stage_sort_order == "Ascending")
            )

        stage_display["Sale Date"] = pd.to_datetime(
            stage_display["Sale Date"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        st.dataframe(
            stage_display,
            use_container_width=True,
            hide_index=True,
            height=min(
                620,
                max(220, 120 + len(stage_display) * 36),
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
                "Pending Stage": st.column_config.TextColumn(
                    "STAGE", width="medium"
                ),
                "Pending Type": st.column_config.TextColumn(
                    "PENDING TYPE", width="medium"
                ),
                "Current Status": st.column_config.TextColumn(
                    "CURRENT STATUS", width="large"
                ),
                "Remarks / Latest Note": st.column_config.TextColumn(
                    "REMARKS / LATEST NOTE", width="large"
                ),
                "Other Open Stages": st.column_config.TextColumn(
                    "OTHER OPEN STAGES", width="large"
                ),
            },
        )
