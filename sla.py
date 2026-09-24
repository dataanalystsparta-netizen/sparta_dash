"""
SPARTA PENDING SALES - MANUAL TRACKER
=====================================

Simple manual dashboard for recording pending sales.

Each sale is entered once and can be pending in MULTIPLE stages.

Fields:
    - Sale Date
    - Customer Name
    - Phone Number
    - Pending Stage(s)
    - Notes

Stages:
    - Quality
    - Welcome
    - Committed
    - Provisioning

There is NO automatic data loading.
There is NO SLA calculation.
There is NO Google Sheets dependency.

Data is stored in Streamlit session state.
"""

# ============================================================
# IMPORTS
# ============================================================

from datetime import date, datetime
from io import BytesIO

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

STAGE_CLASSES = {
    "Quality": "quality",
    "Welcome": "welcome",
    "Committed": "committed",
    "Provisioning": "provisioning",
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

    /* --------------------------------------------------------
       PAGE
       -------------------------------------------------------- */

    .block-container {
        max-width: 1500px;
        padding-top: 1.4rem;
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
        margin-bottom: 1.4rem;
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
       SECTION HEADINGS
       -------------------------------------------------------- */

    .section-heading {
        color: #0f172a;
        font-size: 1.15rem;
        font-weight: 800;
        margin-bottom: 0.55rem;
    }


    /* --------------------------------------------------------
       STAGE BADGES
       -------------------------------------------------------- */

    .stage-badge {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 0.67rem;
        font-weight: 800;
        margin-right: 4px;
        margin-bottom: 3px;
        white-space: nowrap;
    }

    .stage-quality {
        color: #c2410c;
        background: #fff7ed;
        border: 1px solid #fed7aa;
    }

    .stage-welcome {
        color: #a16207;
        background: #fefce8;
        border: 1px solid #fde68a;
    }

    .stage-committed {
        color: #1d4ed8;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
    }

    .stage-provisioning {
        color: #6d28d9;
        background: #f5f3ff;
        border: 1px solid #ddd6fe;
    }


    /* --------------------------------------------------------
       INFO BOX
       -------------------------------------------------------- */

    .info-panel {
        border: 1px solid #dbeafe;
        background: #f8fbff;
        border-radius: 13px;
        padding: 13px 15px;
        color: #475569;
        font-size: 0.82rem;
        margin-bottom: 1rem;
    }


    /* --------------------------------------------------------
       EMPTY STATE
       -------------------------------------------------------- */

    .empty-state {
        border: 1px dashed #cbd5e1;
        background: #f8fafc;
        border-radius: 14px;
        padding: 45px 25px;
        text-align: center;
    }

    .empty-icon {
        font-size: 2.4rem;
        margin-bottom: 8px;
    }

    .empty-title {
        color: #334155;
        font-weight: 800;
        font-size: 1rem;
    }

    .empty-text {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 5px;
    }


    /* --------------------------------------------------------
       SIDEBAR
       -------------------------------------------------------- */

    .sidebar-title {
        font-size: 1rem;
        font-weight: 800;
        color: #0f172a;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def count_stage(stage: str) -> int:
    """Count sales that have the given stage selected."""

    count = 0

    for sale in st.session_state.pending_sales:

        stages = sale.get("Pending Stage", [])

        if stage in stages:
            count += 1

    return count


def format_phone(phone: str) -> str:

    if not phone:
        return ""

    return str(phone).strip()


def format_date(value) -> str:

    if value is None:
        return ""

    try:
        return pd.Timestamp(value).strftime(
            "%d/%m/%Y"
        )
    except Exception:
        return str(value)


def stage_badges(stages) -> str:

    if not isinstance(stages, list):
        stages = [stages]

    html = ""

    for stage in stages:

        if stage not in STAGES:
            continue

        css_class = (
            "stage-"
            + STAGE_CLASSES[stage]
        )

        label = (
            STAGE_ICONS[stage]
            + " "
            + stage
        )

        html += (
            f'<span class="stage-badge '
            f'{css_class}">'
            f'{label}'
            f'</span>'
        )

    return html


def dataframe_from_sales() -> pd.DataFrame:

    rows = []

    for sale in st.session_state.pending_sales:

        rows.append(
            {
                "Sale Date": sale.get(
                    "Sale Date"
                ),

                "Customer Name": sale.get(
                    "Customer Name",
                    "",
                ),

                "Phone Number": sale.get(
                    "Phone Number",
                    "",
                ),

                "Pending Stage": " + ".join(
                    sale.get(
                        "Pending Stage",
                        [],
                    )
                ),

                "Notes": sale.get(
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
                "Pending Stage",
                "Notes",
            ]
        )

    return pd.DataFrame(rows)


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


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="main-title">
        ⏳ Sparta Pending Sales
    </div>

    <div class="main-subtitle">
        Manually track every pending sale and the stage(s)
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
        '<div class="sidebar-title">⚙️ Dashboard</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Manual pending-sales tracker"
    )

    st.divider()

    if st.session_state.pending_sales:

        st.markdown(
            f"**{len(st.session_state.pending_sales):,}** "
            "sales currently recorded."
        )

    else:

        st.caption(
            "No pending sales recorded."
        )

    st.divider()

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------

    if st.session_state.pending_sales:

        st.download_button(
            "📥 Export to Excel",
            data=excel_download(),
            file_name=(
                "Sparta_Pending_Sales.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

        st.divider()

    # --------------------------------------------------------
    # Clear all
    # --------------------------------------------------------

    if st.session_state.pending_sales:

        if st.button(
            "🗑️ Clear All Sales",
            use_container_width=True,
        ):

            st.session_state.pending_sales = []

            st.rerun()


# ============================================================
# KPI CARDS
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


# Use components.html so HTML is rendered instead of displayed literally.
import streamlit.components.v1 as components

components.html(
    kpi_html,
    height=150,
    scrolling=False,
)


# ============================================================
# INFORMATION
# ============================================================

st.markdown(
    """
    <div class="info-panel">
        <strong>How this works:</strong>
        enter a sale once and select every stage where it is currently
        pending. A sale can therefore appear in multiple stage counts
        while still being counted only once under <strong>Pending Sales</strong>.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ADD SALE
# ============================================================

st.markdown(
    '<div class="section-heading">➕ Add Pending Sale</div>',
    unsafe_allow_html=True,
)


with st.container(
    border=True
):

    with st.form(
        "add_pending_sale_form",
        clear_on_submit=True,
    ):

        row1_col1, row1_col2 = st.columns(
            [1, 2]
        )

        with row1_col1:

            sale_date = st.date_input(
                "Sale Date",
                value=date.today(),
                format="DD/MM/YYYY",
            )

        with row1_col2:

            customer_name = st.text_input(
                "Customer Name",
                placeholder="Enter customer name",
            )

        row2_col1, row2_col2 = st.columns(
            [1, 2]
        )

        with row2_col1:

            phone_number = st.text_input(
                "Phone Number",
                placeholder="Enter phone number",
            )

        with row2_col2:

            pending_stages = st.multiselect(
                "Pending Stage(s)",
                options=STAGES,
                format_func=lambda stage:
                    f"{STAGE_ICONS[stage]} {stage}",
                placeholder="Select one or more stages",
            )

        notes = st.text_input(
            "Notes (optional)",
            placeholder="Optional note about the pending sale",
        )

        submitted = st.form_submit_button(
            "➕ Add Pending Sale",
            type="primary",
            use_container_width=True,
        )


# ============================================================
# ADD VALIDATION
# ============================================================

if submitted:

    customer_name_clean = (
        customer_name
        .strip()
    )

    phone_clean = (
        format_phone(
            phone_number
        )
    )

    if not customer_name_clean:

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

        new_sale = {
            "Sale Date":
                sale_date,

            "Customer Name":
                customer_name_clean,

            "Phone Number":
                phone_clean,

            "Pending Stage":
                list(
                    pending_stages
                ),

            "Notes":
                notes.strip(),
        }

        st.session_state.pending_sales.append(
            new_sale
        )

        st.success(
            "Pending sale added successfully."
        )

        st.rerun()


# ============================================================
# CURRENT PENDING SALES
# ============================================================

st.divider()

st.markdown(
    '<div class="section-heading">📋 Current Pending Sales</div>',
    unsafe_allow_html=True,
)


if not st.session_state.pending_sales:

    st.markdown(
        """
        <div class="empty-state">

            <div class="empty-icon">
                📝
            </div>

            <div class="empty-title">
                No pending sales recorded yet
            </div>

            <div class="empty-text">
                Add your first pending sale using the form above.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

else:

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    search_col1, search_col2 = st.columns(
        [2, 1]
    )

    with search_col1:

        search = st.text_input(
            "🔎 Search",
            placeholder="Customer name or phone number...",
        )

    with search_col2:

        stage_filter = st.multiselect(
            "Filter by Stage",
            options=STAGES,
            format_func=lambda stage:
                f"{STAGE_ICONS[stage]} {stage}",
            placeholder="All stages",
        )

    # --------------------------------------------------------
    # Build filtered list
    # --------------------------------------------------------

    filtered_sales = []

    search_lower = (
        search
        .strip()
        .lower()
    )

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

        # Search
        if search_lower:

            searchable = (
                customer
                + " "
                + phone
            ).lower()

            if search_lower not in searchable:
                continue

        # Stage filter
        if stage_filter:

            if not any(
                stage in stages
                for stage in stage_filter
            ):
                continue

        filtered_sales.append(
            (
                index,
                sale,
            )
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    st.caption(
        f"Showing {len(filtered_sales):,} "
        f"of {len(st.session_state.pending_sales):,} "
        f"pending sales."
    )

    # --------------------------------------------------------
    # Display table
    # --------------------------------------------------------

    if not filtered_sales:

        st.info(
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

                    "_index":
                        original_index,
                }
            )

        display_df = pd.DataFrame(
            display_rows
        )

        # Don't expose internal index
        visible_df = display_df.drop(
            columns=["_index"]
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
# EDIT / DELETE
# ============================================================

if st.session_state.pending_sales:

    st.divider()

    st.markdown(
        '<div class="section-heading">✏️ Manage Existing Sale</div>',
        unsafe_allow_html=True,
    )

    sale_options = []

    sale_option_to_index = {}

    for index, sale in enumerate(
        st.session_state.pending_sales
    ):

        label = (
            f"{format_date(sale.get('Sale Date'))}"
            f" — "
            f"{sale.get('Customer Name', 'Unnamed')}"
            f" — "
            f"{sale.get('Phone Number', '')}"
        )

        sale_options.append(
            label
        )

        sale_option_to_index[
            label
        ] = index

    manage_col1, manage_col2 = st.columns(
        [3, 1]
    )

    with manage_col1:

        selected_sale_label = st.selectbox(
            "Select a sale to manage",
            options=sale_options,
        )

    selected_index = (
        sale_option_to_index[
            selected_sale_label
        ]
    )

    selected_sale = (
        st.session_state.pending_sales[
            selected_index
        ]
    )

    with manage_col2:

        st.write("")
        st.write("")

        delete_sale = st.button(
            "🗑️ Delete Sale",
            use_container_width=True,
        )

    if delete_sale:

        st.session_state.pending_sales.pop(
            selected_index
        )

        st.success(
            "Sale deleted."
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

            "Description": {
                "Quality":
                    "Awaiting Quality action",

                "Welcome":
                    "Awaiting Welcome action",

                "Committed":
                    "Awaiting Committed action",

                "Provisioning":
                    "Awaiting Provisioning action",
            }[stage],
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

footer_col1, footer_col2 = st.columns(
    [1, 1]
)

with footer_col1:

    st.caption(
        "Sparta Pending Sales — Manual Tracker"
    )

with footer_col2:

    st.caption(
        "Updated "
        + datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )
