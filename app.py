SPREADSHEET_ID = "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ"
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ"


@st.cache_data(ttl=300)
def load_data():

    # -------------------------
    # Authenticate
    # -------------------------
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    client = gspread.authorize(creds)

    ss = client.open_by_key(SPREADSHEET_ID)

    # -------------------------
    # Load Sheets
    # -------------------------
    app_sheet = pd.DataFrame(
        ss.worksheet("Sparta").get_all_records()
    )

    live_sheet = pd.DataFrame(
        ss.worksheet("Sparta2").get_all_records()
    )

    # -------------------------
    # Last Sync
    # -------------------------
    try:
        meta = ss.worksheet("Meta").get_all_values()
        last_sync = meta[0][1]
    except:
        last_sync = "Unknown"

    # =====================================================
    # APPLICATION SHEET
    # =====================================================

    app_df = app_sheet[
        [
            "Advisor",
            "Sale Date",
            "Customer Name",
            "CLI",
            "Quality Date",
            "Quality Status",
            "Quality Remarks",
            "Welcome call Remarks",
            "Status",
            "Cancellation Sub-text",
            "WCD date",
            "Provisioning",
            "Prov Date",
            "Current Provider",
            "Packageoffered",
            "Standardized_Date",
            "Dashboard_Month",
        ]
    ].copy()

    app_df.rename(
        columns={
            "CLI": "Telephone No.",
            "Status": "Welcome Call Status",
            "Cancellation Sub-text": "Welcome Cancellation Reason",
            "WCD date": "Welcome Call Date",
            "Provisioning": "Provisioning Status",
            "Prov Date": "Provisioning Date",
            "Packageoffered": "Package",
        },
        inplace=True,
    )

    # =====================================================
    # LIVE SHEET
    # =====================================================

    live_df = live_sheet[
        [
            "Telephone No.",
            "Committed Date",
            "Status",
            "LetterStatus",
            "CallStatus",
            "Comments",
            "Voice of Customer",
            "Cancellation Reason",
        ]
    ].copy()

    live_df.rename(
        columns={
            "Committed Date": "Live Date",
            "Status": "Portal Status",
        },
        inplace=True,
    )

    # =====================================================
    # DATE PARSING
    # =====================================================

    date_columns = [
        "Sale Date",
        "Quality Date",
        "Welcome Call Date",
        "Provisioning Date",
        "Live Date",
        "Standardized_Date",
    ]

    for col in date_columns:

        if col in app_df.columns:
            app_df[col] = pd.to_datetime(
                app_df[col],
                errors="coerce",
                dayfirst=True,
            )

        if col in live_df.columns:
            live_df[col] = pd.to_datetime(
                live_df[col],
                errors="coerce",
                dayfirst=True,
            )

    # =====================================================
    # CLEAN TELEPHONE
    # =====================================================

    app_df["Telephone No."] = (
        app_df["Telephone No."]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    live_df["Telephone No."] = (
        live_df["Telephone No."]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # =====================================================
    # CLEAN ADVISOR
    # =====================================================

    app_df["Advisor"] = (
        app_df["Advisor"]
        .astype(str)
        .str.strip()
        .str.title()
    )

    # =====================================================
    # BUILD MASTER DATASET
    # =====================================================

    master_df = app_df.merge(
        live_df,
        on="Telephone No.",
        how="left",
    )

    return master_df, last_sync
