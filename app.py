import streamlit as st
import pandas as pd
import numpy as np

import gspread
from google.oauth2.service_account import Credentials
# ----------------------------------------------------------
# GOOGLE SHEETS CONFIG
# ----------------------------------------------------------

SPREADSHEET_ID = "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ"

SHEET1_NAME = "Sparta"        # <-- CHANGE TO ACTUAL NAME
SHEET2_NAME = "Sparta2"        # <-- CHANGE TO ACTUAL NAME


# ----------------------------------------------------------
# CONNECT TO GOOGLE
# ----------------------------------------------------------

@st.cache_resource
def get_gsheet_client():

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def load_sheet1():

    gc = get_gsheet_client()

    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET1_NAME)

    data = sheet.get_all_records()

    df = pd.DataFrame(data)

    df = df.rename(columns={

        "Advisor":"Advisor",
        "Sale Date":"Sale Date",
        "Customer Name":"Customer Name",
        "CLI":"Telephone No.",
        "Quality Date":"Quality Date",
        "Quality Status":"Quality Status",
        "Quality Remarks":"Quality Remarks",
        "Welcome call Remarks":"Welcome Remarks",
        "Status":"Welcome Status",
        "Cancellation Sub-text":"Cancellation Reason",
        "WCD date":"Welcome Date",
        "Provisioning":"Provisioning Status",
        "Prov Date":"Provisioning Date",
        "Current Provider":"Current Provider",
        "Packageoffered":"Package"

    })

    keep = [

        "Advisor",
        "Sale Date",
        "Customer Name",
        "Telephone No.",
        "Quality Date",
        "Quality Status",
        "Quality Remarks",
        "Welcome Remarks",
        "Welcome Status",
        "Cancellation Reason",
        "Welcome Date",
        "Provisioning Status",
        "Provisioning Date",
        "Current Provider",
        "Package"

    ]

    df = df[keep].copy()

    df["Telephone No."] = df["Telephone No."].astype(str).str.replace(r"\D","",regex=True)

    return df

@st.cache_data(ttl=300)
def load_sheet2():

    gc = get_gsheet_client()

    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET2_NAME)

    data = sheet.get_all_records()

    df = pd.DataFrame(data)

    df = df.rename(columns={

        "Telephone No.":"Telephone No.",
        "Committed Date":"Live Date",
        "Status":"Portal Status",
        "LetterStatus":"Letter Status",
        "CallStatus":"Call Status",
        "Comments":"Comments",
        "Voice of Customer":"Voice of Customer",
        "Cancellation Reason":"Portal Cancellation Reason"

    })

    keep = [

        "Telephone No.",
        "Live Date",
        "Portal Status",
        "Letter Status",
        "Call Status",
        "Comments",
        "Voice of Customer",
        "Portal Cancellation Reason"

    ]

    df = df[keep].copy()

    df["Telephone No."] = df["Telephone No."].astype(str).str.replace(r"\D","",regex=True)

    return df

@st.cache_data(ttl=300)
def load_master_data():

    app_df = load_sheet1()

    live_df = load_sheet2()

    master_df = app_df.merge(
        live_df,
        on="Telephone No.",
        how="left"
    )

    date_cols = [

        "Sale Date",
        "Quality Date",
        "Welcome Date",
        "Provisioning Date",
        "Live Date"

    ]

    for col in date_cols:

        if col in master_df.columns:

            master_df[col] = pd.to_datetime(
                master_df[col],
                errors="coerce"
            )

    return master_df
