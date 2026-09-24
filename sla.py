"""
SPARTA PENDING SALES - MANUAL TRACKER
=====================================

Manual dashboard for tracking pending sales.

Each sale is entered ONCE and can be pending in MULTIPLE stages.

Stages:
    - Quality
    - Welcome
    - Committed
    - Provisioning

Features:
    - Manual single-sale entry
    - Multi-stage pending selection
    - Excel / CSV quick upload
    - Search
    - Stage filter
    - Resolve/remove sales
    - Excel export
    - Stage KPI cards

Data is stored in Streamlit session state only.
No Google Sheets integration.
No automatic SLA calculation.
"""

# ============================================================
# IMPORTS
# ============================================================

from datetime import date, datetime
from io import BytesIO
import re

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


# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1500px;
        padding-top: 1.35rem;
        padding-bottom: 2rem;
    }

    .main-title {
        font-size: 2.15rem;
        font-weight: 850;
        color: #0f172a;
        letter-spacing: -0.8px;
        margin-bottom: 3px;
    }

    .main-subtitle {
        color: #64748b;
        font-size: 0.94rem;
        margin-bottom: 1.35rem;
    }

    .kpi-row {
        display: flex;
        gap: 14px;
        width: 100%;
        margin-bottom: 1rem;
    }

    .kpi-card {
        flex: 1;
        min-width: 0;
        height: 132px;
        border-radius: 15px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.045);
        padding: 16px 17px;
        position: relative;
        overflow: hidden;
    }

    .kpi-card::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        height: 4px;
    }

    .kpi-card.quality::before {
        background: #f97316;
    }

    .kpi-card.welcome::before {
        background: #eab308;
    }

    .kpi-card.committed::before {
        background: #3b82f6;
    }

    .kpi-card.provisioning::before {
        background: #8b5cf6;
    }

    .kpi-card.total::before {
        background: #64748b;
    }

    .kpi-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .kpi-label {
        color: #64748b;
        font-size: 0.69rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.65px;
    }

    .kpi-icon {
        font-size: 1.3rem;
        line-height: 1;
    }

    .kpi-number {
        color: #0f172a;
        font-size: 2rem;
        font-weight: 850;
        line-height: 1;
        margin-top: 16px;
        letter-spacing: -0.7px;
    }

    .kpi-description {
        color: #94a3b8;
        font-size: 0.68rem;
        margin-top: 8px;
    }

    .section-heading {
        color: #0f172a;
        font-size: 1.16rem;
        font-weight: 800;
        margin-bottom: 0.55rem;
    }

    @media (max-width: 1100px) {
        .kpi-row {
            flex-wrap: wrap;
        }

        .kpi-card {
            flex: 1 1 calc(50% - 8px);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def format_date(value) -> str:
    """Format a date for display."""
    if value is None or pd.isna(value):
        return ""

    try:
        return pd.Timestamp(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def clean_phone(value) -> str:
    """Keep phone number as text and remove surrounding whitespace."""
    if value is None or pd.isna(value):
        return ""

    return str(value).strip()


def parse_stage_cell(value) -> list[str]:
    """
    Parse a multi-stage cell.

    Accepted:
        Quality + Welcome
        Quality, Welcome
        Quality; Welcome
        Quality | Welcome
        Quality / Welcome
    """
    if value is None or pd.isna(value):
        return []

    text = str(value).strip()

    if not text:
        return []

    pieces = re.split(r"\s*(?:\+|,|;|\||/)\s*", text)

    lookup = {stage.lower(): stage for stage in STAGES}
    result = []

    for piece in pieces:
        key = piece.strip().lower()

        if key in lookup:
            stage = lookup[key]

            if stage not in result:
                result.append(stage)

    return result


def count_stage(stage: str) -> int:
    """Count unique sales with a given pending stage."""
    return sum(
        1
        for sale in st.session_state.pending_sales
        if stage in sale.get("Pending Stage", [])
    )


def create_sale(
    sale_date,
    customer_name,
    phone_number,
    pending_stages,
    notes,
) -> dict:

    return {
        "Sale Date": sale_date,
        "Customer Name": str(customer_name).strip(),
        "Phone Number": clean_phone(phone_number),
        "Pending Stage": list(pending_stages),
        "Notes": str(notes).strip(),
    }


def sales_to_dataframe() -> pd.DataFrame:

    rows = []

    for sale in st.session_state.pending_sales:

        rows.append(
            {
                "Sale Date":
                    sale.get(
                        "Sale Date"
                    ),

                "Customer Name":
                    sale.get(
                        "Customer Name",
                        "",
                    ),

                "Phone Number":
                    sale.get(
                        "Phone Number",
                        "",
                    ),

                "Pending Stage(s)":
                    " + ".join(
                        sale.get(
                            "Pending Stage",
                            [],
                        )
                    ),

                "Notes":
                    sale.get(
                        "Notes",
                        "",
                    ),
            }
        )

    if not rows:

        return pd.DataFrame(
            columns=[
                "Sale Date",
                "Customer Name",
                "Phone Number",
                "Pending Stage(s)",
                "Notes",
            ]
        )

    df = pd.DataFrame(rows)

    df["Sale Date"] = pd.to_datetime(
        df["Sale Date"],
        errors="coerce",
    ).dt.strftime(
        "%d/%m/%Y"
    )

    return df


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
    """Find a column using case-insensitive aliases."""

    lookup = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for alias in aliases:

        if alias.lower() in lookup:
            return lookup[alias.lower()]

    return None


def read_uploaded_file(
    uploaded_file,
) -> pd.DataFrame:
    """Read CSV or Excel upload."""

    name = uploaded_file.name.lower()

    if name.endswith(".csv"):

        return pd.read_csv(
            uploaded_file,
            dtype=str,
            keep_default_na=False,
        )

    if name.endswith(
        (".xlsx", ".xls")
    ):

        return pd.read_excel(
            uploaded_file,
            dtype=str,
        )

    raise ValueError(
        "Only CSV, XLSX and XLS files are supported."
    )


def sale_label(
    index: int,
    sale: dict,
) -> str:
    """Create a readable label for the remove/resolve selector."""

    return (
        f"{index + 1}. "
        f"{format_date(sale.get('Sale Date'))} | "
        f"{sale.get('Customer Name', 'Unnamed')} | "
        f"{sale.get('Phone Number', '')} | "
        f"{' + '.join(sale.get('Pending Stage', []))}"
    )


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="main-title">
        ⏳ Sparta Pending Sales
    </div>

    <div class="main-subtitle">
        Manually track every pending sale and the stage or stages
        where it is currently waiting.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "**⚙️ Dashboard Controls**"
    )

    st.caption(
        "Manual pending-sales tracker"
    )

    st.divider()

    st.write(
        f"**{len(st.session_state.pending_sales):,}** "
        "sales currently recorded."
    )

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

        clear_all = st.button(
            "🗑️ Clear All Sales",
            use_container_width=True,
        )

        if clear_all:

            st.session_state.pending_sales = []

            st.rerun()


# ============================================================
# KPI COUNTS
# ============================================================

quality_count = count_stage(
    "Quality"
)

welcome_count = count_stage(
    "Welcome"
)

committed_count = count_stage(
    "Committed"
)

provisioning_count = count_stage(
    "Provisioning"
)

total_sales = len(
    st.session_state.pending_sales
)


# ============================================================
# KPI CARDS
# ============================================================

cards = [
    (
        "Pending Quality",
        quality_count,
        "🧪",
        "quality",
        "Sales awaiting Quality action",
    ),
    (
        "Pending Welcome",
        welcome_count,
        "📞",
        "welcome",
        "Sales awaiting Welcome action",
    ),
    (
        "Pending Committed",
        committed_count,
        "📱",
        "committed",
        "Sales awaiting Committed action",
    ),
    (
        "Pending Provisioning",
        provisioning_count,
        "⚙️",
        "provisioning",
        "Sales awaiting Provisioning action",
    ),
    (
        "Pending Sales",
        total_sales,
        "⏳",
        "total",
        "Unique sales currently recorded",
    ),
]


kpi_html = """
<div class="kpi-row">
"""

for (
    title,
    value,
    icon,
    css_class,
    description,
) in cards:

    kpi_html += f"""
    <div class="kpi-card {css_class}">

        <div class="kpi-top">

            <div class="kpi-label">
                {title}
            </div>

            <div class="kpi-icon">
                {icon}
            </div>

        </div>

        <div class="kpi-number">
            {value:,}
        </div>

        <div class="kpi-description">
            {description}
        </div>

    </div>
    """

kpi_html += """
</div>
"""


components.html(
    kpi_html,
    height=150,
    scrolling=False,
)


# ============================================================
# INFORMATION
# ============================================================

st.info(
    "Enter a sale once and select every stage where it is "
    "currently pending. The sale is counted once under "
    "'Pending Sales' but contributes to every selected stage."
)


# ============================================================
# ADD PENDING SALES - CLOSED BY DEFAULT
# ============================================================

with st.expander(
    "➕ Add Pending Sales",
    expanded=False,
):

    st.markdown(
        "### Add a single sale"
    )

    with st.form(
        "manual_add_form",
        clear_on_submit=True,
    ):

        col1, col2 = st.columns(
            [1, 2]
        )

        with col1:

            manual_sale_date = st.date_input(
                "Sale Date",
                value=date.today(),
                format="DD/MM/YYYY",
            )

        with col2:

            manual_customer = st.text_input(
                "Customer Name",
                placeholder="Enter customer name",
            )

        col3, col4 = st.columns(
            [1, 2]
        )

        with col3:

            manual_phone = st.text_input(
                "Phone Number",
                placeholder="Enter phone number",
            )

        with col4:

            manual_stages = st.multiselect(
                "Pending Stage(s)",
                options=STAGES,
                format_func=lambda stage:
                    f"{STAGE_ICONS[stage]} {stage}",
                placeholder="Select one or more stages",
            )

        manual_notes = st.text_input(
            "Notes (optional)",
            placeholder="Optional note",
        )

        manual_submitted = st.form_submit_button(
            "➕ Add Pending Sale",
            type="primary",
            use_container_width=True,
        )

    if manual_submitted:

        customer = manual_customer.strip()
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

            st.session_state.pending_sales.append(
                create_sale(
                    manual_sale_date,
                    customer,
                    phone,
                    manual_stages,
                    manual_notes,
                )
            )

            st.success(
                "Pending sale added."
            )

            st.rerun()

    # ========================================================
    # QUICK UPLOAD
    # ========================================================

    st.divider()

    st.markdown(
        "### 📤 Quick Upload"
    )

    st.caption(
        "Upload an Excel or CSV file to add multiple "
        "sales at once."
    )

    st.markdown(
        """
        **Required columns**

        `Sale Date` | `Customer Name` | `Phone Number` | `Pending Stage(s)`

        **Optional**

        `Notes`

        For multiple stages, use for example:

        `Quality + Welcome + Provisioning`
        """
    )

    template_df = pd.DataFrame(
        [
            {
                "Sale Date":
                    date.today(),

                "Customer Name":
                    "Example Customer",

                "Phone Number":
                    "07123456789",

                "Pending Stage(s)":
                    "Quality + Welcome",

                "Notes":
                    "Example note",
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
        "Upload CSV / Excel",
        type=[
            "csv",
            "xlsx",
            "xls",
        ],
    )

    if uploaded_file is not None:

        try:

            uploaded_df = read_uploaded_file(
                uploaded_file
            )

            if uploaded_df.empty:

                st.warning(
                    "The uploaded file is empty."
                )

            else:

                date_col = find_column(
                    uploaded_df,
                    [
                        "Sale Date",
                        "Date",
                    ],
                )

                customer_col = find_column(
                    uploaded_df,
                    [
                        "Customer Name",
                        "Customer",
                        "Name",
                    ],
                )

                phone_col = find_column(
                    uploaded_df,
                    [
                        "Phone Number",
                        "Phone",
                        "Telephone No.",
                        "Telephone",
                        "CLI",
                    ],
                )

                stage_col = find_column(
                    uploaded_df,
                    [
                        "Pending Stage(s)",
                        "Pending Stages",
                        "Pending Stage",
                        "Stage",
                        "Stages",
                    ],
                )

                notes_col = find_column(
                    uploaded_df,
                    [
                        "Notes",
                        "Note",
                        "Comments",
                    ],
                )

                missing_columns = []

                if date_col is None:

                    missing_columns.append(
                        "Sale Date"
                    )

                if customer_col is None:

                    missing_columns.append(
                        "Customer Name"
                    )

                if phone_col is None:

                    missing_columns.append(
                        "Phone Number"
                    )

                if stage_col is None:

                    missing_columns.append(
                        "Pending Stage(s)"
                    )

                if missing_columns:

                    st.error(
                        "Missing required column(s): "
                        + ", ".join(
                            missing_columns
                        )
                    )

                else:

                    preview = []

                    for _, row in uploaded_df.iterrows():

                        parsed_date = pd.to_datetime(
                            row[date_col],
                            errors="coerce",
                            dayfirst=True,
                        )

                        preview.append(
                            {
                                "Sale Date":
                                    (
                                        format_date(
                                            parsed_date
                                        )
                                        if not pd.isna(
                                            parsed_date
                                        )
                                        else ""
                                    ),

                                "Customer Name":
                                    str(
                                        row[
                                            customer_col
                                        ]
                                    ).strip(),

                                "Phone Number":
                                    clean_phone(
                                        row[
                                            phone_col
                                        ]
                                    ),

                                "Pending Stage(s)":
                                    " + ".join(
                                        parse_stage_cell(
                                            row[
                                                stage_col
                                            ]
                                        )
                                    ),

                                "Notes":
                                    (
                                        str(
                                            row[
                                                notes_col
                                            ]
                                        ).strip()
                                        if notes_col is not None
                                        else ""
                                    ),
                            }
                        )

                    preview_df = pd.DataFrame(
                        preview
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
                        f"{len(uploaded_df):,} row"
                        f"{'' if len(uploaded_df) == 1 else 's'} "
                        "detected."
                    )

                    if st.button(
                        "📥 Add Uploaded Sales",
                        type="primary",
                        use_container_width=True,
                    ):

                        imported = 0
                        skipped = 0
                        errors = []

                        for (
                            row_number,
                            (_, row),
                        ) in enumerate(
                            uploaded_df.iterrows(),
                            start=2,
                        ):

                            parsed_date = pd.to_datetime(
                                row[
                                    date_col
                                ],
                                errors="coerce",
                                dayfirst=True,
                            )

                            customer = str(
                                row[
                                    customer_col
                                ]
                            ).strip()

                            phone = clean_phone(
                                row[
                                    phone_col
                                ]
                            )

                            stages = parse_stage_cell(
                                row[
                                    stage_col
                                ]
                            )

                            notes = ""

                            if notes_col is not None:

                                notes = str(
                                    row[
                                        notes_col
                                    ]
                                ).strip()

                            row_errors = []

                            if pd.isna(
                                parsed_date
                            ):

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
                                    + ", ".join(
                                        row_errors
                                    )
                                )

                                continue

                            st.session_state.pending_sales.append(
                                create_sale(
                                    parsed_date,
                                    customer,
                                    phone,
                                    stages,
                                    notes,
                                )
                            )

                            imported += 1

                        if imported:

                            st.success(
                                f"{imported:,} sale"
                                f"{'' if imported == 1 else 's'} "
                                "added successfully."
                            )

                        if skipped:

                            st.warning(
                                f"{skipped:,} row"
                                f"{'' if skipped == 1 else 's'} "
                                "skipped."
                            )

                            with st.expander(
                                "View skipped rows"
                            ):

                                for error in errors:

                                    st.write(
                                        f"• {error}"
                                    )

                        if imported:

                            st.rerun()

        except Exception as exc:

            st.error(
                f"Unable to read the uploaded file: {exc}"
            )


# ============================================================
# CURRENT PENDING SALES
# ============================================================

st.divider()

st.markdown(
    '<div class="section-heading">📋 Current Pending Sales</div>',
    unsafe_allow_html=True,
)


# ============================================================
# EMPTY STATE
# ============================================================

if not st.session_state.pending_sales:

    st.info(
        "📝 No pending sales recorded yet. "
        "Open 'Add Pending Sales' above to add a sale "
        "manually or upload an Excel/CSV file."
    )

else:

    # ========================================================
    # SEARCH / FILTERS
    # ========================================================

    filter_col1, filter_col2 = st.columns(
        [2, 1]
    )

    with filter_col1:

        search_text = st.text_input(
            "🔎 Search",
            placeholder=(
                "Search customer name or phone number..."
            ),
        )

    with filter_col2:

        stage_filter = st.multiselect(
            "Filter by Stage",
            options=STAGES,
            format_func=lambda stage:
                f"{STAGE_ICONS[stage]} {stage}",
            placeholder="All stages",
        )

    query = search_text.strip().lower()

    filtered = []

    for index, sale in enumerate(
        st.session_state.pending_sales
    ):

        customer = str(
            sale.get(
                "Customer Name",
                "",
            )
        )

        phone = str(
            sale.get(
                "Phone Number",
                "",
            )
        )

        stages = sale.get(
            "Pending Stage",
            [],
        )

        if query:

            search_target = (
                customer
                + " "
                + phone
            ).lower()

            if query not in search_target:
                continue

        if stage_filter:

            if not any(
                stage in stages
                for stage in stage_filter
            ):
                continue

        filtered.append(
            (
                index,
                sale,
            )
        )

    st.caption(
        f"Showing {len(filtered):,} of "
        f"{len(st.session_state.pending_sales):,} "
        "pending sales."
    )

    # ========================================================
    # CURRENT TABLE
    # ========================================================

    if not filtered:

        st.warning(
            "No pending sales match the selected filters."
        )

    else:

        rows = []

        for _, sale in filtered:

            rows.append(
                {
                    "Sale Date":
                        format_date(
                            sale.get(
                                "Sale Date"
                            )
                        ),

                    "Customer Name":
                        sale.get(
                            "Customer Name",
                            "",
                        ),

                    "Phone Number":
                        sale.get(
                            "Phone Number",
                            "",
                        ),

                    "Pending Stage(s)":
                        " + ".join(
                            sale.get(
                                "Pending Stage",
                                [],
                            )
                        ),

                    "Notes":
                        sale.get(
                            "Notes",
                            "",
                        ),
                }
            )

        current_df = pd.DataFrame(
            rows
        )

        st.dataframe(
            current_df,
            use_container_width=True,
            hide_index=True,
            height=min(
                650,
                max(
                    180,
                    100
                    + len(current_df) * 38,
                ),
            ),
            column_config={
                "Sale Date":
                    st.column_config.TextColumn(
                        "SALE DATE",
                        width="small",
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

                "Notes":
                    st.column_config.TextColumn(
                        "NOTES",
                        width="large",
                    ),
            },
        )


# ============================================================
# RESOLVE / REMOVE
# ============================================================

if st.session_state.pending_sales:

    st.divider()

    st.markdown(
        '<div class="section-heading">✅ Resolve Pending Sales</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "When a sale is no longer pending, select it and remove "
        "it from the active pending list."
    )

    option_map = {}

    for index, sale in enumerate(
        st.session_state.pending_sales
    ):

        label = sale_label(
            index,
            sale,
        )

        option_map[label] = index

    selected_sales = st.multiselect(
        "Select sale(s) to resolve",
        options=list(
            option_map.keys()
        ),
        placeholder="Select resolved sales...",
    )

    if selected_sales:

        st.warning(
            f"{len(selected_sales):,} sale"
            f"{'' if len(selected_sales) == 1 else 's'} "
            "will be removed from the active pending list."
        )

        if st.button(
            "✅ Mark Selected Sales as Resolved",
            type="primary",
            use_container_width=True,
        ):

            indexes = sorted(
                [
                    option_map[label]
                    for label in selected_sales
                ],
                reverse=True,
            )

            for index in indexes:

                st.session_state.pending_sales.pop(
                    index
                )

            st.success(
                f"{len(indexes):,} sale"
                f"{'' if len(indexes) == 1 else 's'} "
                "removed from pending."
            )

            st.rerun()


# ============================================================
# STAGE BREAKDOWN
# ============================================================

st.divider()

st.markdown(
    '<div class="section-heading">📊 Stage Breakdown</div>',
    unsafe_allow_html=True,
)


breakdown_df = pd.DataFrame(
    [
        {
            "Stage":
                f"{STAGE_ICONS['Quality']} Quality",

            "Pending Sales":
                quality_count,

            "Description":
                STAGE_DESCRIPTIONS["Quality"],
        },

        {
            "Stage":
                f"{STAGE_ICONS['Welcome']} Welcome",

            "Pending Sales":
                welcome_count,

            "Description":
                STAGE_DESCRIPTIONS["Welcome"],
        },

        {
            "Stage":
                f"{STAGE_ICONS['Committed']} Committed",

            "Pending Sales":
                committed_count,

            "Description":
                STAGE_DESCRIPTIONS["Committed"],
        },

        {
            "Stage":
                f"{STAGE_ICONS['Provisioning']} Provisioning",

            "Pending Sales":
                provisioning_count,

            "Description":
                STAGE_DESCRIPTIONS["Provisioning"],
        },
    ]
)


st.dataframe(
    breakdown_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Stage":
            st.column_config.TextColumn(
                "STAGE",
                width="medium",
            ),

        "Pending Sales":
            st.column_config.NumberColumn(
                "PENDING SALES",
                format="%d",
            ),

        "Description":
            st.column_config.TextColumn(
                "DESCRIPTION",
                width="large",
            ),
    },
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

left, right = st.columns(
    [1, 1]
)

with left:

    st.caption(
        "Sparta Pending Sales — Manual Tracker"
    )

with right:

    st.caption(
        "Updated "
        + datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )
