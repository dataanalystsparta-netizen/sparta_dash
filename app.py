import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# ----------------------------------------------------------
# DATA INGESTION
# ----------------------------------------------------------

@st.cache_data(ttl=300)
def fetch_data():

    info = st.secrets["gcp_service_account"]

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open_by_key(
        "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ"
    )

    # --------------------------------------------------
    # SHEET 1
    # --------------------------------------------------

    sheet1 = pd.DataFrame(
        spreadsheet.worksheet("Sparta").get_all_records()
    )

    # Keep only required columns

    sheet1 = sheet1[
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

    sheet1.rename(
        columns={
            "CLI": "Telephone No.",
            "Status": "Welcome Status",
            "Cancellation Sub-text": "Welcome Cancellation Reason",
            "WCD date": "Welcome Date",
            "Provisioning": "Provisioning Status",
            "Prov Date": "Provisioning Date",
            "Packageoffered": "Package Offered",
        },
        inplace=True,
    )

    # --------------------------------------------------
    # SHEET 2
    # --------------------------------------------------

    sheet2 = pd.DataFrame(
        spreadsheet.worksheet("Sparta2").get_all_records()
    )

    sheet2 = sheet2[
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

    sheet2.rename(
        columns={
            "Committed Date": "Live Date",
            "Status": "Portal Status",
            "Comments": "Portal Comments",
        },
        inplace=True,
    )

    # --------------------------------------------------
    # DATE CONVERSIONS
    # --------------------------------------------------

    date_columns = [
        "Sale Date",
        "Quality Date",
        "Welcome Date",
        "Provisioning Date",
        "Standardized_Date",
    ]

    for col in date_columns:
        if col in sheet1.columns:
            sheet1[col] = pd.to_datetime(
                sheet1[col],
                errors="coerce",
                dayfirst=True,
            )

    sheet2["Live Date"] = pd.to_datetime(
        sheet2["Live Date"],
        errors="coerce",
        dayfirst=True,
    )

    # --------------------------------------------------
    # CLEAN STRINGS
    # --------------------------------------------------

    sheet1["Advisor"] = (
        sheet1["Advisor"]
        .astype(str)
        .str.strip()
        .str.title()
    )

    sheet2["Telephone No."] = (
        sheet2["Telephone No."]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    sheet1["Telephone No."] = (
        sheet1["Telephone No."]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # --------------------------------------------------
    # MASTER DATASET
    # --------------------------------------------------

    master_df = sheet1.merge(
        sheet2,
        on="Telephone No.",
        how="left",
    )

    # --------------------------------------------------
    # LAST SYNC
    # --------------------------------------------------

    try:
        meta = spreadsheet.worksheet("Meta").get_all_values()
        last_sync = meta[0][1]
    except Exception:
        last_sync = "Unknown"

    return master_df, last_sync
