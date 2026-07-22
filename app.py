import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ----------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------

st.set_page_config(
    page_title="Sparta Sales Operations",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------------------------------------------------
# CONFIG
# ----------------------------------------------------------

SHEET1_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ/"
    "export?format=csv&gid=1598890500"
)

SHEET2_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ/"
    "export?format=csv&gid=1601740359"
)

# ----------------------------------------------------------
# CSS
# ----------------------------------------------------------

st.markdown("""
<style>

.main{
    background:#F5F7FA;
}

.block-container{
    padding-top:2rem;
    padding-bottom:2rem;
    max-width:95%;
}

.metric-box{
    background:white;
    padding:18px;
    border-radius:14px;
    border:1px solid #E5E7EB;
}

</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------
# HELPERS
# ----------------------------------------------------------

def clean_phone(value):
    """
    Standardise phone numbers across both sheets.
    """

    if pd.isna(value):
        return ""

    value = str(value)

    value = value.replace(".0","")

    value = "".join(ch for ch in value if ch.isdigit())

    return value.strip()


# ----------------------------------------------------------
# LOAD SHEET 1
# ----------------------------------------------------------

@st.cache_data(ttl=300)

def load_sheet1():

    df = pd.read_csv(SHEET1_URL)

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

    df["Telephone No."] = df["Telephone No."].apply(clean_phone)

    return df


# ----------------------------------------------------------
# LOAD SHEET 2
# ----------------------------------------------------------

@st.cache_data(ttl=300)

def load_sheet2():

    df = pd.read_csv(SHEET2_URL)

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

    df["Telephone No."] = df["Telephone No."].apply(clean_phone)

    return df


# ----------------------------------------------------------
# MASTER DATA
# ----------------------------------------------------------

@st.cache_data(ttl=300)

def load_master_data():

    apps = load_sheet1()

    live = load_sheet2()

    master = apps.merge(

        live,

        on="Telephone No.",

        how="left"

    )

    # convert dates

    date_cols = [

        "Sale Date",

        "Quality Date",

        "Welcome Date",

        "Provisioning Date",

        "Live Date"

    ]

    for c in date_cols:

        if c in master.columns:

            master[c] = pd.to_datetime(

                master[c],

                errors="coerce"

            )

    return master


# ----------------------------------------------------------
# LOAD DATA
# ----------------------------------------------------------

master_df = load_master_data()

# ----------------------------------------------------------
# HEADER
# ----------------------------------------------------------

left,right = st.columns([5,1])

with left:

    st.title("📊 Sparta Sales Operations Command Center")

    st.caption("Version 2.0")

with right:

    st.metric(

        "Last Refresh",

        datetime.now().strftime("%H:%M:%S")

    )

st.divider()

# ----------------------------------------------------------
# BASIC METRICS
# ----------------------------------------------------------

c1,c2,c3 = st.columns(3)

with c1:

    st.metric(

        "Applications",

        len(master_df)

    )

with c2:

    st.metric(

        "Unique Customers",

        master_df["Telephone No."].nunique()

    )

with c3:

    st.metric(

        "Live Records",

        master_df["Portal Status"].notna().sum()

    )

st.divider()

# ----------------------------------------------------------
# PREVIEW
# ----------------------------------------------------------

st.subheader("Master Dataset Preview")

st.dataframe(

    master_df.head(20),

    use_container_width=True

)

st.success(
    f"Loaded {len(master_df):,} records successfully."
)
