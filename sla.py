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
    - Manual entry
    - Multi-stage pending selection
    - Excel / CSV quick upload
    - Search and stage filtering
    - Resolve/remove sales
    - Excel export
    - Stage KPI cards
    - Session-based storage

There is NO automatic source-sheet integration.
There is NO SLA calculation.
"""

# ============================================================
# IMPORTS
# ============================================================

from datetime import date, datetime
from io import BytesIO
import re

import pandas as pd
import streamlit as st


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

if "upload_message" not in st.session_state:
    st.session_state.upload_message = ""

if "remove_selection" not in st.session_state:
    st.session_state.remove_selection = []


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

    /* --------------------------------------------------------
       KPI CARDS
       -------------------------------------------------------- */

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
        box-shadow:
            0 2px 8px rgba(15, 23, 42, 0.045);
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

    /* --------------------------------------------------------
       INFO
       -------------------------------------------------------- */

    .info-panel {
        border: 1px solid #dbeafe;
        background: #f8fbff;
        border-radius: 13px;
        padding: 13px 15px;
        color: #475569;
        font-size: 0.82rem;
        margin: 0.75rem 0 1rem 0;
    }

    /* --------------------------------------------------------
       EMPTY STATE
       -------------------------------------------------------- */

    .empty-title {
        text-align: center;
        color: #334155;
        font-size: 1rem;
        font-weight: 800;
        margin-top: 0.35rem;
    }

    .empty-text {
        text-align: center;
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 0.25rem;
        margin-bottom: 0.5rem;
    }

    /* --------------------------------------------------------
       STAGE BADGE-LIKE TEXT
       -------------------------------------------------------- */

    .stage-quality {
        color: #c2410c;
        font-weight: 800;
    }

    .stage-welcome {
        color: #a16207;
        font-weight: 800;
    }

    .stage-committed {
        color: #1d4ed8;
        font-weight: 800;
    }

    .stage-provisioning {
        color: #6d28d9;
        font-weight: 800;
    }

    /* --------------------------------------------------------
       SECTION HEADINGS
       -------------------------------------------------------- */

    .section-heading {
        color: #0f172a;
        font-size: 1.16rem;
        font-weight: 800;
        margin-bottom: 0.55rem;
    }

    /* --------------------------------------------------------
       RESPONSIVE
       -------------------------------------------------------- */

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
# HELPER FUNCTIONS
# ============================================================

def normalise_phone(value) -> str:
    """
    Keep phone numbers readable while removing accidental
    whitespace around them.
    """
    if pd.isna(value):
        return ""

    return str(value).strip()


def format_date(value) -> str:

    if value is None or pd.isna(value):
        return ""

    try:
        return pd.Timestamp(value).strftime(
            "%d/%m/%Y"
        )
    except Exception:
        return str(value)


def parse_stage_cell(value) -> list:
    """
    Accept multiple common separators.

    Examples:
        Quality, Welcome
        Quality + Welcome
        Quality;Welcome
        Quality | Welcome
        Quality / Welcome
    """

    if pd.isna(value):
        return []

    text = str(value).strip()

    if not text:
        return []

    parts = re.split(
        r"\s*(?:\+|,|;|\||/)\s*",
        text,
    )

    cleaned = []

    stage_lookup = {
        stage.lower(): stage
        for stage in STAGES
    }

    for part in parts:

        key = part.strip().lower()

        if key in stage_lookup:

            canonical = stage_lookup[key]

            if canonical not in cleaned:
                cleaned.append(canonical)

    return cleaned


def count_stage(stage: str) -> int:

    return sum(
        1
        for sale in st.session_state.pending_sales
        if stage in sale.get(
            "Pending Stage",
            [],
        )
    )


def dataframe_from_sales() -> pd.DataFrame:

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


def excel_download() -> bytes:

    df = dataframe_from_sales()

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Pending Sales",
        )

    output.seek(0)

    return output.getvalue()


def create_sale(
    sale_date,
    customer_name,
    phone_number,
    pending_stages,
    notes,
):

    return {
        "Sale Date":
            sale_date,

        "Customer Name":
            str(customer_name).strip(),

        "Phone Number":
            normalise_phone(
                phone_number
            ),

        "Pending Stage":
            list(
                pending_stages
            ),

        "Notes":
            str(notes).strip(),
    }


def sale_identifier(
    index: int,
    sale: dict,
) -> str:

    sale_date = format_date(
        sale.get(
            "Sale Date"
        )
    )

    customer = sale.get(
        "Customer Name",
        "",
    )

    phone = sale.get(
        "Phone Number",
        "",
    )

    stages = " + ".join(
        sale.get(
            "Pending Stage",
            [],
        )
    )

    return (
        f"{index} | "
        f"{sale_date} | "
        f"{customer} | "
        f"{phone} | "
        f"{stages}"
    )


def quick_upload_dataframe(
    uploaded_file,
) -> pd.DataFrame:

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):

        # utf-8-sig handles Excel-generated CSVs with BOM
        return pd.read_csv(
            uploaded_file,
            dtype=str,
            keep_default_na=False,
        )

    if file_name.endswith(
        (".xlsx", ".xls")
    ):

        return pd.read_excel(
            uploaded_file,
            dtype=str,
        )

    raise ValueError(
        "Unsupported file type. "
        "Please upload CSV or Excel."
    )


def find_column(
    df: pd.DataFrame,
    possible_names: list,
):

    normalised_columns = {
        str(col).strip().lower(): col
        for col in df.columns
    }

    for name in possible_names:

        if name.lower() in normalised_columns:

            return normalised_columns[
                name.lower()
            ]

    return None


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

    st.divider()

    if st.session_state.pending_sales:

        st.download_button(
            "📥 Export Current Sales",
            data=excel_download(),
            file_name="Sparta_Pending_Sales.xlsx",
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

        st.divider()

    if st.session_state.pending_sales:

        if st.button(
            "🗑️ Clear All Sales",
            use_container_width=True,
        ):

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

kpi_cards = [
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
) in kpi_cards:

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
# ADD / QUICK UPLOAD ACCORDION
# CLOSED BY DEFAULT
# ============================================================

with st.expander(
    "➕ Add Pending Sales",
    expanded=False,
):

    st.markdown(
        "### Add a single sale"
    )

    with st.form(
        "add_pending_sale_form",
        clear_on_submit=True,
    ):

        col1, col2 = st.columns(
            [1, 2]
        )

        with col1:

            sale_date = st.date_input(
                "Sale Date",
                value=date.today(),
                format="DD/MM/YYYY",
            )

        with col2:

            customer_name = st.text_input(
                "Customer Name",
                placeholder="Enter customer name",
            )

        col3, col4 = st.columns(
            [1, 2]
        )

        with col3:

            phone_number = st.text_input(
                "Phone Number",
                placeholder="Enter phone number",
            )

        with col4:

            pending_stages = st.multiselect(
                "Pending Stage(s)",
                options=STAGES,
                format_func=lambda x:
                    f"{STAGE_ICONS[x]} {x}",
                placeholder="Select one or more stages",
            )

        notes = st.text_input(
            "Notes",
            placeholder="Optional note",
        )

        add_clicked = st.form_submit_button(
            "➕ Add Pending Sale",
            type="primary",
            use_container_width=True,
        )

    if add_clicked:

        customer_clean = (
            str(customer_name).strip()
        )

        phone_clean = (
            normalise_phone(
                phone_number
            )
        )

        if not customer_clean:

            st.error(
                "Please enter the Customer Name."
            )

        elif not phone_clean:

            st.error(
                "Please enter the Phone Number."
            )

        elif not pending_stages:

            st.error(
                "Please select at least one Pending Stage."
            )

        else:

            st.session_state.pending_sales.append(
                create_sale(
                    sale_date,
                    customer_clean,
                    phone_clean,
                    pending_stages,
                    notes,
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
        "Upload an Excel or CSV file to add multiple pending "
        "sales at once."
    )

    upload_template = pd.DataFrame(
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

    template_output = BytesIO()

    with pd.ExcelWriter(
        template_output,
        engine="openpyxl",
    ) as writer:

        upload_template.to_excel(
            writer,
            index=False,
            sheet_name="Pending Sales",
        )

    template_output.seek(0)

    template_col1, template_col2 = st.columns(
        [1, 2]
    )

    with template_col1:

        st.download_button(
            "📄 Download Upload Template",
            data=template_output.getvalue(),
            file_name="Sparta_Pending_Sales_Template.xlsx",
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

    with template_col2:

        uploaded_file = st.file_uploader(
            "Upload CSV / Excel",
            type=[
                "csv",
                "xlsx",
                "xls",
            ],
            label_visibility="collapsed",
        )

    if uploaded_file is not None:

        try:

            upload_df = quick_upload_dataframe(
                uploaded_file
            )

            if upload_df.empty:

                st.warning(
                    "The uploaded file is empty."
                )

            else:

                # --------------------------------------------
                # Find columns flexibly
                # --------------------------------------------

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

                if not date_col:
                    missing.append(
                        "Sale Date"
                    )

                if not customer_col:
                    missing.append(
                        "Customer Name"
                    )

                if not phone_col:
                    missing.append(
                        "Phone Number"
                    )

                if not stage_col:
                    missing.append(
                        "Pending Stage(s)"
                    )

                if missing:

                    st.error(
                        "Missing required column(s): "
                        + ", ".join(
                            missing
                        )
                    )

                else:

                    # ----------------------------------------
                    # Preview
                    # ----------------------------------------

                    preview_rows = []

                    for _, row in upload_df.iterrows():

                        stages = parse_stage_cell(
                            row[stage_col]
                        )

                        parsed_date = pd.to_datetime(
                            row[date_col],
                            errors="coerce",
                            dayfirst=True,
                        )

                        preview_rows.append(
                            {
                                "Sale Date":
                                    (
                                        parsed_date.strftime(
                                            "%d/%m/%Y"
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
                                    normalise_phone(
                                        row[
                                            phone_col
                                        ]
                                    ),

                                "Pending Stage(s)":
                                    " + ".join(
                                        stages
                                    ),

                                "Notes":
                                    (
                                        str(
                                            row[
                                                notes_col
                                            ]
                                        ).strip()
                                        if notes_col
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
                        f"{'' if len(upload_df) == 1 else 's'} "
                        "detected."
                    )

                    # ----------------------------------------
                    # Import button
                    # ----------------------------------------

                    if st.button(
                        "📥 Add Uploaded Sales",
                        type="primary",
                        use_container_width=True,
                    ):

                        imported = 0
                        skipped = 0
                        errors = []

                        for row_number, (_, row) in enumerate(
                            upload_df.iterrows(),
                            start=2,
                        ):

                            # Date
                            parsed_date = pd.to_datetime(
                                row[date_col],
                                errors="coerce",
                                dayfirst=True,
                            )

                            # Customer
                            customer = str(
                                row[
                                    customer_col
                                ]
                            ).strip()

                            # Phone
                            phone = normalise_phone(
                                row[
                                    phone_col
                                ]
                            )

                            # Stages
                            stages = parse_stage_cell(
                                row[
                                    stage_col
                                ]
                            )

                            # Notes
                            notes_value = ""

                            if notes_col:

                                notes_value = str(
                                    row[
                                        notes_col
                                    ]
                                ).strip()

                            # -----------------------------
                            # Validation
                            # -----------------------------

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

                            # -----------------------------
                            # Add
                            # -----------------------------

                            new_sale = create_sale(
                                parsed_date,
                                customer,
                                phone,
                                stages,
                                notes_value,
                            )

                            st.session_state.pending_sales.append(
                                new_sale
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


# ============================================================
# CURRENT SALES
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

        selected_stage_filters = st.multiselect(
            "Filter by Stage",
            options=STAGES,
            format_func=lambda x:
                f"{STAGE_ICONS[x]} {x}",
            placeholder="All stages",
        )

    search_lower = (
        search_text
        .strip()
        .lower()
    )

    filtered_sales = []

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

        # Search filter
        if search_lower:

            searchable = (
                customer
                + " "
                + phone
            ).lower()

            if search_lower not in searchable:
                continue

        # Stage filter
        if selected_stage_filters:

            if not any(
                stage in stages
                for stage in selected_stage_filters
            ):
                continue

        filtered_sales.append(
            (
                index,
                sale,
            )
        )


    # ========================================================
    # RESULT COUNT
    # ========================================================

    st.caption(
        f"Showing {len(filtered_sales):,} "
        f"of {len(st.session_state.pending_sales):,} "
        f"pending sale"
        f"{'' if len(st.session_state.pending_sales) == 1 else 's'}."
    )


    # ========================================================
    # TABLE
    # ========================================================

    if not filtered_sales:

        st.warning(
            "No pending sales match the selected filters."
        )

    else:

        display_rows = []

        for original_index, sale in filtered_sales:

            display_rows.append(
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

                    "_Index":
                        original_index,
                }
            )

        display_df = pd.DataFrame(
            display_rows
        )

        visible_df = display_df.drop(
            columns=["_Index"]
        )

        st.dataframe(
            visible_df,
            use_container_width=True,
            hide_index=True,
            height=min(
                650,
                max(
                    180,
                    100
                    + len(visible_df) * 38,
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
# RESOLVE / REMOVE SALES
# ============================================================

if st.session_state.pending_sales:

    st.divider()

    st.markdown(
        '<div class="section-heading">✅ Resolve Pending Sales</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "When a sale is no longer pending, select it below and "
        "remove it from the active pending list."
    )

    sale_options = []
    sale_option_to_index = {}

    for index, sale in enumerate(
        st.session_state.pending_sales
    ):

        option = sale_identifier(
            index,
            sale,
        )

        sale_options.append(
            option
        )

        sale_option_to_index[
            option
        ] = index

    selected_to_remove = st.multiselect(
        "Select sale(s) to remove",
        options=sale_options,
        placeholder="Select resolved sales...",
    )

    if selected_to_remove:

        st.warning(
            f"{len(selected_to_remove):,} sale"
            f"{'' if len(selected_to_remove) == 1 else 's'} "
            "will be removed from the pending dashboard."
        )

        if st.button(
            "✅ Mark Selected Sales as Resolved",
            type="primary",
            use_container_width=True,
        ):

            indexes_to_remove = sorted(
                [
                    sale_option_to_index[
                        option
                    ]
                    for option in selected_to_remove
                ],
                reverse=True,
            )

            for index in indexes_to_remove:

                st.session_state.pending_sales.pop(
                    index
                )

            st.success(
                f"{len(indexes_to_remove):,} sale"
                f"{'' if len(indexes_to_remove) == 1 else 's'} "
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


breakdown_rows = []

for stage in STAGES:

    breakdown_rows.append(
        {
            "Stage":
                f"{STAGE_ICONS[stage]} {stage}",

            "Pending Sales":
                count_stage(stage),

            "Description":
                STAGE_DESCRIPTIONS[stage],
        }
    )


breakdown_df = pd.DataFrame(
    breakdown_rows
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
