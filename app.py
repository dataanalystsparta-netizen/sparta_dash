import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# Custom CSS to force the tables into a horizontal row and fix cell heights
st.markdown("""
    <style>
    .block-container { max-width: 98%; padding-top: 2rem; }
    .table-container { display: flex; flex-direction: row; gap: 20px; overflow-x: auto; align-items: flex-start; }
    td, th { white-space: nowrap !important; font-size: 13px !important; padding: 4px 10px !important; }
    th { background-color: #1E3A8A !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=300)
def fetch_data():
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(info, scopes=[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ])
    client = gspread.authorize(creds)
    # Using your specific Sheet ID
    ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
    
    # Load Sparta (Applications & Quality)
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Standardized_Date'] = pd.to_datetime(df1['Standardized_Date'], format='mixed', dayfirst=True, errors='coerce')
    
    # Load Sparta2 (Portal Live Data)
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Sale Date'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()
    
    return df1, df2

# Mapping functions for Quality and Portal status
def map_quality(val):
    s = str(val).lower()
    if any(x in s for x in ['appr', 'pass']): return 'Approved'
    if any(x in s for x in ['rew', 'repro']): return 'Rework'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    return 'Others'

def map_portal(val):
    s = str(val).lower()
    if 'live' in s: return 'Live'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    if 'com' in s: return 'Committed'
    return 'Others'

# --- UI ---
st.title("🚀 Sparta Performance & Portal Dashboard")

df1, df2 = fetch_data()

# Date Filter
col1, col2 = st.columns(2)
start_date = col1.date_input("Start Date", datetime.date.today().replace(day=1))
end_date = col2.date_input("End Date", datetime.date.today())

# Filtering logic
f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)].copy()
f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)].copy()

f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
f2['P_Status'] = f2['Status'].apply(map_portal)

# Create the 3 DataFrames
app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')
qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0)
port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0)

# Merge everything for a consistent Advisor list
master = pd.DataFrame(index=sorted(f1['Advisor'].unique())).join([app_counts, qual_counts, port_counts]).fillna(0)
master = master.sort_values('Total Apps', ascending=False)

# Add Grand Total Row
totals = master.sum().to_frame().T
totals.index = ["GRAND TOTAL"]
final_display = pd.concat([master, totals])

# --- DISPLAY TABLES WITH GRADIENTS ---
st.write(f"Showing results for {len(f1)} applications and {len(f2)} portal entries.")

# 1. Applications Table (Green Gradient)
html_apps = final_display[['Total Apps']].style.background_gradient(cmap='Greens').to_html()

# 2. Quality Table (Multi-Gradient)
qual_cols = [c for c in ['Approved', 'Rework', 'Cancelled', 'Others'] if c in final_display.columns]
html_qual = final_display[qual_cols].style.background_gradient(subset=['Approved'], cmap='Greens')\
    .background_gradient(subset=['Rework'], cmap='YlOrBr')\
    .background_gradient(subset=['Cancelled'], cmap='Reds').to_html()

# 3. Portal Table (Blue/Red Gradient)
port_cols = [c for c in ['Live', 'Committed', 'Cancelled'] if c in final_display.columns]
html_port = final_display[port_cols].style.background_gradient(subset=['Live'], cmap='Blues')\
    .background_gradient(subset=['Cancelled'], cmap='Reds').to_html()

# Render horizontally
st.markdown(f"""
<div class="table-container">
    <div><b>Applications</b><br>{html_apps}</div>
    <div><b>Quality Status</b><br>{html_qual}</div>
    <div><b>Portal Status</b><br>{html_port}</div>
</div>
""", unsafe_allow_html=True)
