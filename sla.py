"""
SPARTA PENDING SALES - MANUAL TRACKER
=====================================

Manual operational dashboard for tracking pending sales.

Each sale is entered ONCE and may be pending in MULTIPLE stages.
Each stage can then be resolved independently.

Stages:
    - Quality
    - Welcome
    - Committed
    - Provisioning

Features:
    - Large KPI cards
    - Manual single-sale entry
    - Multi-stage pending selection
    - Excel / CSV quick upload
    - Search and filtering
    - Stage-specific resolution
    - Excel export
    - Automatic merging of duplicate sale rows

There is deliberately NO automatic Google Sheets integration and
NO SLA calculation.
"""

# ============================================================
# IMPORTS
# ============================================================

from datetime import date, datetime
from io import BytesIO
import re
import uuid

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Sparta Pending Sales",
    page_icon="⏳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

STAGES = [
    "Quality",
    "Welcome",
    "Committed",
    "Provisioning",
]

STAGE_ICONS = {
    "Quality": "🧪",
    "Welcome": "📞",
    "Committed": "📱",
    "Provisioning": "⚙️",
}

STAGE_DESCRIPTIONS = {
    "Quality": "Sales awaiting Quality action",
    "Welcome": "Sales awaiting Welcome action",
    "Committed": "Sales awaiting Committed action",
    "Provisioning": "Sales awaiting Provisioning action",
}


# ============================================================
# SESSION STATE
# ============================================================

if "pending_sales" not in st.session_state:
    st.session_state.pending_sales = []

if "resolution_history" not in st.session_state:
    st.session_state.resolution_history = []


# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1520px;
        padding-top: 1.25rem;
        padding-bottom: 2.4rem;
    }

    .main-title {
        font-size: 2.15rem;
        font-weight: 850;
        color: #0f172a;
        letter-spacing: -0.8px;
        margin-bottom: 2px;
    }

    .main-subtitle {
        color: #64748b;
        font-size: 0.94rem;
        margin-bottom: 1.2rem;
    }

    /* Native Streamlit metric cards */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 17px 13px 17px;
        min-height: 126px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.045);
    }

    [data-testid="stMetric"] > div:first-child {
        color: #64748b;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.70rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.55px !important;
        text-transform: uppercase !important;
    }

    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-size: 2rem !important;
        font-weight: 850 !important;
        line-height: 1.05 !important;
    }

    /* Give each metric card its own accent colour */
    [data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] {
        border-top: 4px solid #f97316;
    }

    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] {
        border-top: 4px solid #eab308;
    }

    [data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] {
        border-top: 4px solid #3b82f6;
    }

    [data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] {
        border-top: 4px solid #8b5cf6;
    }

    [data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"] {
        border-top: 4px solid #64748b;
    }

    .section-heading {
        color: #0f172a;
        font-size: 1.18rem;
        font-weight: 800;
        margin-bottom: 0.45rem;
    }

    .small-note {
        color: #64748b;
        font-size: 0.79rem;
    }

    .queue-note {
        border: 1px solid #dbeafe;
        background: #f8fbff;
        border-radius: 12px;
        padding: 11px 14px;
        color: #475569;
        font-size: 0.81rem;
        margin-bottom: 1rem;
    }

    .resolved-note {
        border: 1px solid #bbf7d0;
        background: #f0fdf4;
        border-radius: 12px;
        padding: 11px 14px;
        color: #166534;
        font-size: 0.81rem;
        margin-bottom: 1rem;
    }

    /* Colour stage selector boxes when supported by the theme */
    [data-testid="stExpander"] {
        border-radius: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def safe_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def clean_phone(value) -> str:
    """Keep phone numbers as text; do not convert to numeric."""
    return safe_text(value)


def format_date(value) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).strftime("%d/%m/%Y")
    except Exception:
        return safe_text(value)


def parse_date_value(value):
    if value is None or pd.isna(value):
        return pd.NaT

    text = safe_text(value)
    if not text:
        return pd.NaT

    # Prefer UK date interpretation because this dashboard is
    # used with DD/MM/YYYY data.
    return pd.to_datetime(
        text,
        errors="coerce",
        dayfirst=True,
    )


def parse_stage_cell(value) -> list[str]:
    """
    Accept common multi-stage separators:
        Quality + Welcome
        Quality, Welcome
        Quality; Welcome
        Quality | Welcome
        Quality / Welcome
    """
    if value is None or pd.isna(value):
        return []

    text = safe_text(value)
    if not text:
        return []

    parts = re.split(
        r"\s*(?:\+|,|;|\||/)\s*",
        text,
    )

    lookup = {stage.lower(): stage for stage in STAGES}
    result = []

    for part in parts:
        key = safe_text(part).lower()
        if key in lookup and lookup[key] not in result:
            result.append(lookup[key])

    return result


def count_stage(stage: str) -> int:
    return sum(
        1
        for sale in st.session_state.pending_sales
        if stage in sale.get("Pending Stage", [])
    )


def make_sale_key(
    sale_date,
    phone_number,
) -> str:
    """Use date + phone as the practical sale identity."""
    parsed = parse_date_value(sale_date)
    date_part = (
        parsed.strftime("%Y-%m-%d")
        if not pd.isna(parsed)
        else ""
    )

    phone = clean_phone(phone_number)

    return f"{date_part}|{phone}"


def create_sale(
    sale_date,
    customer_name,
    phone_number,
    pending_stages,
    notes,
) -> dict:

    return {
        "ID": uuid.uuid4().hex,
        "Sale Date": parse_date_value(sale_date),
        "Customer Name": safe_text(customer_name),
        "Phone Number": clean_phone(phone_number),
        "Pending Stage": list(pending_stages),
        "Notes": safe_text(notes),
    }


def upsert_sale(
    sale_date,
    customer_name,
    phone_number,
    pending_stages,
    notes,
) -> tuple[str, bool]:
    """
    Add a sale or merge into an existing same-date/same-phone sale.

    Returns:
        (message, was_new_sale)
    """
    parsed_date = parse_date_value(sale_date)
    customer = safe_text(customer_name)
    phone = clean_phone(phone_number)
    stages = list(pending_stages)
    note_text = safe_text(notes)

    key = make_sale_key(
        parsed_date,
        phone,
    )

    for existing in st.session_state.pending_sales:

        existing_key = make_sale_key(
            existing.get("Sale Date"),
            existing.get("Phone Number"),
        )

        if existing_key == key:

            existing_stages = existing.get(
                "Pending Stage",
                [],
            )

            merged_stages = list(existing_stages)

            for stage in stages:
                if stage not in merged_stages:
                    merged_stages.append(stage)

            existing["Pending Stage"] = merged_stages

            if customer:
                existing["Customer Name"] = customer

            if note_text:
                old_notes = safe_text(
                    existing.get("Notes", "")
                )

                if old_notes and note_text not in old_notes:
                    existing["Notes"] = (
                        old_notes + " | " + note_text
                    )
                elif not old_notes:
                    existing["Notes"] = note_text

            return (
                "Existing sale updated; selected stages merged into it.",
                False,
            )

    st.session_state.pending_sales.append(
        create_sale(
            parsed_date,
            customer,
            phone,
            stages,
            note_text,
        )
    )

    return (
        "Pending sale added successfully.",
        True,
    )


def sales_to_dataframe() -> pd.DataFrame:

    rows = []

    for sale in st.session_state.pending_sales:

        rows.append(
            {
                "Sale Date": sale.get("Sale Date"),
                "Customer Name": sale.get("Customer Name", ""),
                "Phone Number": sale.get("Phone Number", ""),
                "Pending Stage(s)": ", ".join(
                    sale.get("Pending Stage", [])
                ),
                "Notes": sale.get("Notes", ""),
            }
        )

    columns = [
        "Sale Date",
        "Customer Name",
        "Phone Number",
        "Pending Stage(s)",
        "Notes",
    ]

    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)

    df["Sale Date"] = pd.to_datetime(
        df["Sale Date"],
        errors="coerce",
    ).dt.strftime("%d/%m/%Y")

    return df[columns]


def export_excel() -> bytes:

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        sales_to_dataframe().to_excel(
            writer,
            index=False,
            sheet_name="Pending Sales",
        )

    output.seek(0)
    return output.getvalue()


def find_column(
    df: pd.DataFrame,
    aliases: list[str],
):
    lookup = {
        safe_text(column).lower(): column
        for column in df.columns
    }

    for alias in aliases:
        if alias.lower() in lookup:
            return lookup[alias.lower()]

    return None


def read_uploaded_file(uploaded_file) -> pd.DataFrame:

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        return pd.read_csv(
            uploaded_file,
            dtype=str,
            keep_default_na=False,
        )

    if file_name.endswith(".xlsx"):
        return pd.read_excel(
            uploaded_file,
            dtype=str,
        )

    raise ValueError(
        "Please upload a CSV or XLSX file."
    )


def sale_label(
    sale: dict,
) -> str:
    return (
        f"{format_date(sale.get('Sale Date'))}"
        f"  |  "
        f"{safe_text(sale.get('Customer Name')) or 'Unnamed'}"
        f"  |  "
        f"{safe_text(sale.get('Phone Number'))}"
        f"  |  "
        f"{', '.join(sale.get('Pending Stage', []))}"
    )


# ============================================================
# PAGE HEADER
# ============================================================

st.title("⏳ Sparta Pending Sales")
st.caption(
    "Manual operational tracker — one sale can be pending across multiple stages, with each stage resolved independently."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("### ⚙️ Dashboard Controls")

    st.caption(
        "Manual pending-sales tracker"
    )

    st.divider()

    st.metric(
        "Active Sales",
        len(st.session_state.pending_sales),
    )

    st.divider()

    if st.session_state.pending_sales:

        st.download_button(
            "📥 Export Current Sales",
            data=export_excel(),
            file_name="Sparta_Pending_Sales.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

        st.divider()

        if st.button(
            "🗑️ Clear All Active Sales",
            use_container_width=True,
        ):
            st.session_state.pending_sales = []
            st.rerun()


# ============================================================
# KPI CARDS
# ============================================================

quality_count = count_stage("Quality")
welcome_count = count_stage("Welcome")
committed_count = count_stage("Committed")
provisioning_count = count_stage("Provisioning")
total_sales = len(st.session_state.pending_sales)

metric_cols = st.columns(5, gap="small")

with metric_cols[0]:
    st.metric(
        "🧪 Pending Quality",
        quality_count,
        help="Active sales currently marked as pending Quality.",
    )

with metric_cols[1]:
    st.metric(
        "📞 Pending Welcome",
        welcome_count,
        help="Active sales currently marked as pending Welcome.",
    )

with metric_cols[2]:
    st.metric(
        "📱 Pending Committed",
        committed_count,
        help="Active sales currently marked as pending Committed.",
    )

with metric_cols[3]:
    st.metric(
        "⚙️ Pending Provisioning",
        provisioning_count,
        help="Active sales currently marked as pending Provisioning.",
    )

with metric_cols[4]:
    st.metric(
        "⏳ Pending Sales",
        total_sales,
        help="Unique active sales. A sale pending in several stages is counted only once here.",
    )


# ============================================================
# INFORMATION PANEL
# ============================================================
'''
st.info(
    "A single sale may have multiple pending stages. "
    "The stage cards count each selected stage, while the "
    "Pending Sales card counts the sale only once. "
    "Resolving one stage does not resolve the other stages."
)

'''
# ============================================================
# ADD PENDING SALES ACCORDION
# CLOSED BY DEFAULT
# ============================================================

with st.expander(
    "➕ Add Pending Sales",
    expanded=False,
):

    add_tab, upload_tab = st.tabs(
        [
            "✍️ Add Single Sale",
            "📤 Quick Upload",
        ]
    )

    # --------------------------------------------------------
    # SINGLE SALE
    # --------------------------------------------------------

    with add_tab:

        with st.form(
            "manual_add_form",
            clear_on_submit=True,
        ):

            row1 = st.columns([1, 2])

            with row1[0]:
                manual_date = st.date_input(
                    "Sale Date",
                    value=date.today(),
                    format="DD/MM/YYYY",
                )

            with row1[1]:
                manual_customer = st.text_input(
                    "Customer Name",
                    placeholder="Enter customer name",
                )

            row2 = st.columns([1, 2])

            with row2[0]:
                manual_phone = st.text_input(
                    "Phone Number",
                    placeholder="Enter phone number",
                )

            with row2[1]:
                manual_stages = st.multiselect(
                    "Pending Stage(s)",
                    options=STAGES,
                    format_func=lambda x: (
                        f"{STAGE_ICONS[x]} {x}"
                    ),
                    placeholder="Select one or more stages",
                )

            manual_notes = st.text_area(
                "Notes",
                placeholder="Optional note about this pending sale",
                height=80,
            )

            submitted = st.form_submit_button(
                "➕ Add Pending Sale",
                type="primary",
                use_container_width=True,
            )

        if submitted:

            customer = safe_text(
                manual_customer
            )

            phone = clean_phone(
                manual_phone
            )

            if not customer:
                st.error(
                    "Please enter the Customer Name."
                )

            elif not phone:
                st.error(
                    "Please enter the Phone Number."
                )

            elif not manual_stages:
                st.error(
                    "Please select at least one Pending Stage."
                )

            else:

                message, is_new = upsert_sale(
                    manual_date,
                    customer,
                    phone,
                    manual_stages,
                    manual_notes,
                )

                if is_new:
                    st.success(message)
                else:
                    st.info(message)

                st.rerun()

    # --------------------------------------------------------
    # QUICK UPLOAD
    # --------------------------------------------------------

    with upload_tab:

        st.caption(
            "Upload multiple pending sales at once. Existing sales with the same Sale Date + Phone Number will be merged instead of duplicated."
        )

        st.markdown(
            "**Required columns:** `Sale Date`, `Customer Name`, `Phone Number`, `Pending Stage(s)`  \n"
            "**Optional:** `Notes`"
        )

        st.markdown(
            "For multiple stages in one cell, use for example: "
            "`Quality + Welcome + Provisioning`."
        )

        template_df = pd.DataFrame(
            [
                {
                    "Sale Date": date.today(),
                    "Customer Name": "Example Customer",
                    "Phone Number": "07123456789",
                    "Pending Stage(s)": "Quality + Welcome",
                    "Notes": "Example note",
                }
            ]
        )

        template_bytes = BytesIO()

        with pd.ExcelWriter(
            template_bytes,
            engine="openpyxl",
        ) as writer:
            template_df.to_excel(
                writer,
                index=False,
                sheet_name="Pending Sales",
            )

        template_bytes.seek(0)

        st.download_button(
            "📄 Download Excel Template",
            data=template_bytes.getvalue(),
            file_name="Sparta_Pending_Sales_Template.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        uploaded_file = st.file_uploader(
            "Upload CSV / XLSX",
            type=[
                "csv",
                "xlsx",
            ],
            help="The file must contain Sale Date, Customer Name, Phone Number and Pending Stage(s).",
        )

        if uploaded_file is not None:

            try:
                upload_df = read_uploaded_file(
                    uploaded_file
                )

                if upload_df.empty:
                    st.warning(
                        "The uploaded file is empty."
                    )
                else:

                    date_col = find_column(
                        upload_df,
                        [
                            "Sale Date",
                            "Date",
                        ],
                    )

                    customer_col = find_column(
                        upload_df,
                        [
                            "Customer Name",
                            "Customer",
                            "Name",
                        ],
                    )

                    phone_col = find_column(
                        upload_df,
                        [
                            "Phone Number",
                            "Phone",
                            "Telephone No.",
                            "Telephone",
                            "CLI",
                        ],
                    )

                    stage_col = find_column(
                        upload_df,
                        [
                            "Pending Stage(s)",
                            "Pending Stages",
                            "Pending Stage",
                            "Stage",
                            "Stages",
                        ],
                    )

                    notes_col = find_column(
                        upload_df,
                        [
                            "Notes",
                            "Note",
                            "Comments",
                        ],
                    )

                    missing = []

                    if date_col is None:
                        missing.append("Sale Date")

                    if customer_col is None:
                        missing.append("Customer Name")

                    if phone_col is None:
                        missing.append("Phone Number")

                    if stage_col is None:
                        missing.append("Pending Stage(s)")

                    if missing:
                        st.error(
                            "Missing required column(s): "
                            + ", ".join(missing)
                        )
                    else:

                        preview_rows = []

                        for _, row in upload_df.iterrows():

                            parsed = parse_date_value(
                                row[date_col]
                            )

                            stages = parse_stage_cell(
                                row[stage_col]
                            )

                            preview_rows.append(
                                {
                                    "Sale Date": format_date(parsed),
                                    "Customer Name": safe_text(row[customer_col]),
                                    "Phone Number": clean_phone(row[phone_col]),
                                    "Pending Stage(s)": ", ".join(stages),
                                    "Notes": (
                                        safe_text(row[notes_col])
                                        if notes_col is not None
                                        else ""
                                    ),
                                }
                            )

                        preview_df = pd.DataFrame(
                            preview_rows
                        )

                        st.markdown(
                            "**Upload Preview**"
                        )

                        st.dataframe(
                            preview_df.head(10),
                            use_container_width=True,
                            hide_index=True,
                        )

                        st.caption(
                            f"{len(upload_df):,} row"
                            f"{'' if len(upload_df) == 1 else 's'} detected."
                        )

                        if st.button(
                            "📥 Add Uploaded Sales",
                            type="primary",
                            use_container_width=True,
                            key="import_uploaded_sales",
                        ):

                            imported_new = 0
                            merged_existing = 0
                            skipped = 0
                            errors = []

                            for row_number, (_, row) in enumerate(
                                upload_df.iterrows(),
                                start=2,
                            ):

                                parsed_date = parse_date_value(
                                    row[date_col]
                                )

                                customer = safe_text(
                                    row[customer_col]
                                )

                                phone = clean_phone(
                                    row[phone_col]
                                )

                                stages = parse_stage_cell(
                                    row[stage_col]
                                )

                                notes = (
                                    safe_text(row[notes_col])
                                    if notes_col is not None
                                    else ""
                                )

                                row_errors = []

                                if pd.isna(parsed_date):
                                    row_errors.append(
                                        "invalid Sale Date"
                                    )

                                if not customer:
                                    row_errors.append(
                                        "missing Customer Name"
                                    )

                                if not phone:
                                    row_errors.append(
                                        "missing Phone Number"
                                    )

                                if not stages:
                                    row_errors.append(
                                        "no valid Pending Stage"
                                    )

                                if row_errors:
                                    skipped += 1
                                    errors.append(
                                        f"Row {row_number}: "
                                        + ", ".join(row_errors)
                                    )
                                    continue

                                _, was_new = upsert_sale(
                                    parsed_date,
                                    customer,
                                    phone,
                                    stages,
                                    notes,
                                )

                                if was_new:
                                    imported_new += 1
                                else:
                                    merged_existing += 1

                            if imported_new:
                                st.success(
                                    f"{imported_new:,} new sale"
                                    f"{'' if imported_new == 1 else 's'} added."
                                )

                            if merged_existing:
                                st.info(
                                    f"{merged_existing:,} existing sale"
                                    f"{'' if merged_existing == 1 else 's'} updated/merged."
                                )

                            if skipped:
                                st.warning(
                                    f"{skipped:,} row"
                                    f"{'' if skipped == 1 else 's'} skipped."
                                )

                                with st.expander(
                                    "View skipped rows"
                                ):
                                    for error in errors:
                                        st.write(
                                            f"• {error}"
                                        )

                            if imported_new or merged_existing:
                                st.rerun()

            except Exception as exc:
                st.error(
                    f"Unable to read the uploaded file: {exc}"
                )


# ============================================================
# CURRENT PENDING SALES
# ============================================================

st.divider()

st.subheader("📋 Current Pending Sales")

if not st.session_state.pending_sales:

    st.info(
        "📝 No pending sales recorded yet. "
        "Open 'Add Pending Sales' above to add a sale manually "
        "or upload an Excel/CSV file."
    )

else:

    # --------------------------------------------------------
    # Filters
    # --------------------------------------------------------

    filter_row1 = st.columns(
        [2, 1.2, 1.2]
    )

    with filter_row1[0]:
        search_text = st.text_input(
            "🔎 Search",
            placeholder="Customer name or phone number...",
        )

    # Determine date bounds
    sale_dates = [
        parse_date_value(sale.get("Sale Date"))
        for sale in st.session_state.pending_sales
    ]

    valid_dates = [
        d for d in sale_dates
        if not pd.isna(d)
    ]

    if valid_dates:
        min_date = min(valid_dates).date()
        max_date = max(valid_dates).date()
    else:
        min_date = date.today()
        max_date = date.today()

    with filter_row1[1]:
        date_from = st.date_input(
            "Sale Date From",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
        )

    with filter_row1[2]:
        date_to = st.date_input(
            "Sale Date To",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
        )

    stage_filter = st.multiselect(
        "Filter by Pending Stage",
        options=STAGES,
        format_func=lambda stage: (
            f"{STAGE_ICONS[stage]} {stage}"
        ),
        placeholder="All stages",
    )

    # --------------------------------------------------------
    # Apply filters
    # --------------------------------------------------------

    query = safe_text(search_text).lower()
    filtered_sales = []

    for sale in st.session_state.pending_sales:

        customer = safe_text(
            sale.get("Customer Name")
        )

        phone = safe_text(
            sale.get("Phone Number")
        )

        stages = sale.get(
            "Pending Stage",
            [],
        )

        sale_date_value = parse_date_value(
            sale.get("Sale Date")
        )

        if not pd.isna(sale_date_value):

            sale_date_only = sale_date_value.date()

            if not (
                date_from
                <= sale_date_only
                <= date_to
            ):
                continue

        if query:

            searchable = (
                customer
                + " "
                + phone
            ).lower()

            if query not in searchable:
                continue

        if stage_filter:

            if not any(
                stage in stages
                for stage in stage_filter
            ):
                continue

        filtered_sales.append(
            sale
        )

    st.caption(
        f"Showing {len(filtered_sales):,} of "
        f"{len(st.session_state.pending_sales):,} active sales."
    )

    # --------------------------------------------------------
    # Table
    # --------------------------------------------------------

    if not filtered_sales:

        st.warning(
            "No pending sales match the selected filters."
        )

    else:

        table_rows = []

        for sale in filtered_sales:

            table_rows.append(
                {
                    "Sale Date": format_date(
                        sale.get("Sale Date")
                    ),
                    "Customer Name": safe_text(
                        sale.get("Customer Name")
                    ),
                    "Phone Number": safe_text(
                        sale.get("Phone Number")
                    ),
                    "Pending Stage(s)": ", ".join(
                        sale.get(
                            "Pending Stage",
                            [],
                        )
                    ),
                    "Notes": safe_text(
                        sale.get("Notes")
                    ),
                }
            )

        current_df = pd.DataFrame(
            table_rows
        )

        st.dataframe(
            current_df,
            use_container_width=True,
            hide_index=True,
            height=min(
                620,
                max(
                    190,
                    100 + len(current_df) * 38,
                ),
            ),
            column_config={
                "Sale Date": st.column_config.TextColumn(
                    "SALE DATE",
                    width="small",
                ),
                "Customer Name": st.column_config.TextColumn(
                    "CUSTOMER NAME",
                    width="medium",
                ),
                "Phone Number": st.column_config.TextColumn(
                    "PHONE NUMBER",
                    width="medium",
                ),
                "Pending Stage(s)": st.column_config.TextColumn(
                    "PENDING STAGE(S)",
                    width="large",
                ),
                "Notes": st.column_config.TextColumn(
                    "NOTES",
                    width="large",
                ),
            },
        )


# ============================================================
# STAGE-SPECIFIC RESOLUTION
# ============================================================

st.divider()

st.subheader("✅ Resolve Pending Stage(s)")
st.success(
    "Resolving a stage removes only that stage. If a sale is pending in Quality + Welcome and Quality is resolved, the sale remains active under Welcome."
)

if not st.session_state.pending_sales:

    st.info(
        "There are no active pending sales to resolve."
    )

else:

    resolution_sale_labels = [
        sale_label(sale)
        for sale in st.session_state.pending_sales
    ]

    selected_resolution_label = st.selectbox(
        "Select Sale",
        options=resolution_sale_labels,
        index=None,
        placeholder="Select a sale...",
    )

    if selected_resolution_label is not None:

        selected_index = resolution_sale_labels.index(
            selected_resolution_label
        )

        selected_sale = (
            st.session_state.pending_sales[
                selected_index
            ]
        )

        active_stages = selected_sale.get(
            "Pending Stage",
            [],
        )

        st.caption(
            "Currently pending: "
            + ", ".join(active_stages)
        )

        stages_to_resolve = st.multiselect(
            "Stage(s) resolved",
            options=active_stages,
            format_func=lambda stage: (
                f"{STAGE_ICONS[stage]} {stage}"
            ),
            placeholder="Select the stage(s) that are now resolved...",
        )

        resolution_note = st.text_input(
            "Resolution note (optional)",
            placeholder="Optional note about the resolution",
        )

        if st.button(
            "✅ Mark Selected Stage(s) as Resolved",
            type="primary",
            use_container_width=True,
            disabled=not stages_to_resolve,
        ):

            resolved_at = datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            )

            remaining_stages = [
                stage
                for stage in active_stages
                if stage not in stages_to_resolve
            ]

            customer_name = safe_text(
                selected_sale.get(
                    "Customer Name"
                )
            )

            phone_number = safe_text(
                selected_sale.get(
                    "Phone Number"
                )
            )

            for stage in stages_to_resolve:

                st.session_state.resolution_history.append(
                    {
                        "Resolved At": resolved_at,
                        "Sale Date": selected_sale.get(
                            "Sale Date"
                        ),
                        "Customer Name": customer_name,
                        "Phone Number": phone_number,
                        "Stage": stage,
                        "Note": safe_text(
                            resolution_note
                        ),
                    }
                )

            if remaining_stages:

                selected_sale[
                    "Pending Stage"
                ] = remaining_stages

                st.success(
                    f"Resolved: {', '.join(stages_to_resolve)}. "
                    f"The sale remains pending in: "
                    f"{', '.join(remaining_stages)}."
                )

            else:

                st.session_state.pending_sales.pop(
                    selected_index
                )

                st.success(
                    "All pending stages for this sale have been resolved. "
                    "The sale has been removed from active pending sales."
                )

            st.rerun()


# ============================================================
# RESOLUTION HISTORY
# ============================================================

if st.session_state.resolution_history:

    with st.expander(
        "🕘 Resolution History",
        expanded=False,
    ):

        history_df = pd.DataFrame(
            st.session_state.resolution_history
        )

        if not history_df.empty:

            history_df["Sale Date"] = pd.to_datetime(
                history_df["Sale Date"],
                errors="coerce",
            ).dt.strftime(
                "%d/%m/%Y"
            )

            history_df = history_df[
                [
                    "Resolved At",
                    "Sale Date",
                    "Customer Name",
                    "Phone Number",
                    "Stage",
                    "Note",
                ]
            ]

            st.dataframe(
                history_df.iloc[::-1],
                use_container_width=True,
                hide_index=True,
                height=min(
                    450,
                    max(
                        160,
                        90 + len(history_df) * 36,
                    ),
                ),
            )


# ============================================================
# STAGE BREAKDOWN
# ============================================================

st.divider()

st.subheader("📊 Pending Stage Breakdown")

breakdown_df = pd.DataFrame(
    [
        {
            "Stage": f"🧪 Quality",
            "Pending Sales": quality_count,
            "Description": STAGE_DESCRIPTIONS["Quality"],
        },
        {
            "Stage": f"📞 Welcome",
            "Pending Sales": welcome_count,
            "Description": STAGE_DESCRIPTIONS["Welcome"],
        },
        {
            "Stage": f"📱 Committed",
            "Pending Sales": committed_count,
            "Description": STAGE_DESCRIPTIONS["Committed"],
        },
        {
            "Stage": f"⚙️ Provisioning",
            "Pending Sales": provisioning_count,
            "Description": STAGE_DESCRIPTIONS["Provisioning"],
        },
    ]
)

st.dataframe(
    breakdown_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Stage": st.column_config.TextColumn(
            "STAGE",
            width="medium",
        ),
        "Pending Sales": st.column_config.NumberColumn(
            "PENDING SALES",
            format="%d",
        ),
        "Description": st.column_config.TextColumn(
            "DESCRIPTION",
            width="large",
        ),
    },
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
        "Sparta Pending Sales — Manual Tracker"
    )

with footer_right:
    st.caption(
        "Updated "
        + datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )
