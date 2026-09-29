import io
import streamlit as st
import pandas as pd
import numpy as np

# Set page layout
st.set_page_config(
    page_title="Queue Management & Workflow Dashboard",
    page_icon="📊",
    layout="wide",
)

# -----------------------------------------------------------------------------
# WORKFLOW DEFINITIONS & MAPPINGS
# -----------------------------------------------------------------------------

STAGE_NEXT_DESTINATIONS = {
    "Quality Control": {
        "QA Pending": "Quality Control",
        "QA Rejected": "END",
        "Potential Opportunity": "Potential Opportunity",
        "QA Approved": "Welcome",
    },
    "Welcome": {
        "Pending": "Welcome",
        "Appointment Missed": "Welcome",
        "Followup": "Welcome",
        "Rejected": "END",
        "QA-Reassessment": "Quality Control",
        "Completed": "Provisioning",
    },
    "Provisioning": {
        "Pending": "Provisioning",
        "Provisioned": "Provisioning",
        "Delayed": "Provisioning",
        "Hold": "Provisioning",
        "To Be Extended": "Provisioning",
        "Send For Rework": "Welcome",  # Backward transition
        "To Be Cancelled": "Provisioning -> Cancellation",
        "Cancelled": "END",
        "Completed": "Dispatch",
    },
    "Dispatch": {
        "Pending": "Dispatch",
        "To Be Extended": "Provisioning",  # Backward transition
        "To Be Cancelled": "Dispatch -> Cancellation",
        "Completed": "Committed Call",
    },
    "Committed Call": {
        "Pending": "Committed Call",
        "Followup": "Committed Call",
        "To Be Extended": "Provisioning",  # Backward transition
        "To Be Cancelled": "Committed Call -> Cancellation",
        "Satisfied": "Onboarding",
    },
    "Onboarding": {
        "Installation Pending": "Onboarding",
        "Port-Pending": "Onboarding",
        "Delayed": "Onboarding",
        "Missed Appointment": "Welcome",  # Backward transition
        "To Be Extended": "Provisioning",  # Backward transition
        "To Be Cancelled": "Onboarding -> Cancellation",
        "Completed": "LIVE / COMPLETE",
    },
    "Potential Opportunity": {
        "Pending": "Potential Opportunity",
        "Followup": "Potential Opportunity",
        "Rejected": "END",
        "Qualified": "Quality Control",
    },
}

# Pending statuses for active stage queues
PENDING_STATUSES = {
    "Quality Control": ["QA Pending"],
    "Welcome": ["Pending", "Appointment Missed", "Followup"],
    "Provisioning": [
        "Pending",
        "Provisioned",
        "Delayed",
        "Hold",
        "To Be Extended",
    ],
    "Dispatch": ["Pending"],
    "Committed Call": ["Pending", "Followup"],
    "Onboarding": ["Installation Pending", "Port-Pending", "Delayed"],
    "Potential Opportunity": ["Pending", "Followup"],
}

# -----------------------------------------------------------------------------
# MOCK DATA GENERATOR
# -----------------------------------------------------------------------------


@st.cache_data
def generate_mock_data():
    np.random.seed(42)
    n = 120

    stages = list(STAGE_NEXT_DESTINATIONS.keys())
    advisors = [
        "Alex Mercer",
        "Sarah Jenkins",
        "David Chen",
        "Elena Rostova",
        "Marcus Vance",
    ]

    records = []
    for i in range(1, n + 1):
        stage = np.random.choice(stages)
        status_options = list(STAGE_NEXT_DESTINATIONS[stage].keys())
        status = np.random.choice(status_options)
        advisor = np.random.choice(advisors)

        created_date = pd.Timestamp("2026-09-01") + pd.Timedelta(
            days=int(np.random.randint(0, 28))
        )

        records.append(
            {
                "Ticket_ID": f"TICK-{1000 + i}",
                "Customer_Name": f"Customer {i}",
                "Current_Stage": stage,
                "Status": status,
                "Advisor": advisor,
                "Created_Date": created_date.strftime("%Y-%m-%d"),
                "Remarks": f"Standard workflow processing for Ticket {1000 + i}",
            }
        )

    df = pd.DataFrame(records)

    # Determine Next Destination based on rules
    def get_next_dest(row):
        return STAGE_NEXT_DESTINATIONS.get(row["Current_Stage"], {}).get(
            row["Status"], "Unknown"
        )

    df["Next_Destination"] = df.apply(get_next_dest, axis=1)
    return df


# -----------------------------------------------------------------------------
# MAIN APP LAYOUT
# -----------------------------------------------------------------------------


def main():
    st.title("⚡ Dynamic Queue & Workflow Management Dashboard")
    st.caption(
        "Real-time monitoring of customer transitions, backward loops, and stage destinations."
    )

    # Load Data
    df = generate_mock_data()

    # -------------------------------------------------------------------------
    # SIDEBAR CONTROLS & FILTERS
    # -------------------------------------------------------------------------
    st.sidebar.header("🔍 Filters & Controls")

    if st.sidebar.button("↻ Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")

    # Advisor Filter
    selected_advisors = st.sidebar.multiselect(
        "Filter by Advisor",
        options=sorted(df["Advisor"].unique()),
        default=sorted(df["Advisor"].unique()),
    )

    # Search Box
    search_query = st.sidebar.text_input(
        "Search Ticket ID / Customer", value=""
    )

    # Apply global filters
    filtered_df = df[df["Advisor"].isin(selected_advisors)]
    if search_query:
        filtered_df = filtered_df[
            filtered_df["Ticket_ID"].str.contains(search_query, case=False)
            | filtered_df["Customer_Name"].str.contains(
                search_query, case=False
            )
        ]

    # -------------------------------------------------------------------------
    # TOP LEVEL KPI METRICS
    # -------------------------------------------------------------------------
    st.subheader("📈 Queue Highlights")

    total_tickets = len(filtered_df)

    # Calculate Total Pending across all stages
    total_pending = 0
    for stage, statuses in PENDING_STATUSES.items():
        total_pending += len(
            filtered_df[
                (filtered_df["Current_Stage"] == stage)
                & (filtered_df["Status"].isin(statuses))
            ]
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tickets", total_tickets)
    col2.metric("Total Pending Action", total_pending)
    col3.metric(
        "Live / Completed",
        len(filtered_df[filtered_df["Next_Destination"] == "LIVE / COMPLETE"]),
    )
    col4.metric(
        "Terminated / END",
        len(filtered_df[filtered_df["Next_Destination"] == "END"]),
    )

    st.markdown("---")

    # -------------------------------------------------------------------------
    # STAGE TABS
    # -------------------------------------------------------------------------
    stages_list = list(STAGE_NEXT_DESTINATIONS.keys())
    tabs = st.tabs(["📋 All Tickets Summary"] + stages_list)

    # TAB 0: ALL TICKETS
    with tabs[0]:
        st.write("### All Active Tickets")
        st.dataframe(
            filtered_df,
            column_config={
                "Ticket_ID": "Ticket ID",
                "Customer_Name": "Customer Name",
                "Current_Stage": "Current Stage",
                "Status": "Current Status",
                "Next_Destination": "Next Destination ➔",
            },
            use_container_width=True,
            hide_index=True,
        )

    # TABS 1..7: STAGE SPECIFIC VIEWS
    for idx, stage in enumerate(stages_list, start=1):
        with tabs[idx]:
            st.write(f"### {stage} Stage Overview")

            stage_df = filtered_df[filtered_df["Current_Stage"] == stage]
            pending_list = PENDING_STATUSES.get(stage, [])

            # Stage Metrics
            stage_pending_count = len(
                stage_df[stage_df["Status"].isin(pending_list)]
            )
            col_a, col_b = st.columns(2)
            col_a.metric(f"Total in {stage}", len(stage_df))
            col_b.metric(f"Pending Action in {stage}", stage_pending_count)

            # Workflow Reference Table
            with st.expander(
                f"ℹ️ View {stage} Status-to-Destination Mapping Rules"
            ):
                rule_mapping = STAGE_NEXT_DESTINATIONS[stage]
                rule_df = pd.DataFrame(
                    list(rule_mapping.items()),
                    columns=["Status", "Next Destination"],
                )
                st.table(rule_df)

            st.write("#### Tickets in Stage")
            if stage_df.empty:
                st.info(f"No tickets currently in {stage}.")
            else:
                st.dataframe(
                    stage_df[
                        [
                            "Ticket_ID",
                            "Customer_Name",
                            "Status",
                            "Next_Destination",
                            "Advisor",
                            "Created_Date",
                            "Remarks",
                        ]
                    ],
                    column_config={
                        "Ticket_ID": "Ticket ID",
                        "Status": "Status",
                        "Next_Destination": "Next Destination ➔",
                    },
                    use_container_width=True,
                    hide_index=True,
                )

    # -------------------------------------------------------------------------
    # CSV EXPORT
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📥 Export Summary Data")

    csv_buffer = io.StringIO()
    filtered_df.to_csv(csv_buffer, index=False)

    st.download_button(
        label="Download Processed Queue as CSV",
        data=csv_buffer.getvalue(),
        file_name="queue_workflow_summary.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
