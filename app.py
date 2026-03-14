import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# Custom CSS for the 3-table horizontal layout and professional headers
st.markdown("""
    <style>
    .block-container { max-width: 98%; padding-top: 2rem; }
    .table-container { display: flex; flex-direction: row; gap: 25px; overflow-x: auto; align-items: flex-start; }
    .table-box { border: 1px solid #e6e6e6; border-radius: 5px; padding: 10px; background-color: white; }
    td, th { white-space: nowrap !important; font-size: 13px !important; padding: 6px 12px !important; border: 1px solid #f0f0f0 !important; }
    th { background-color: #1E3A8A !important; color: white !important; text-align: center !important; }
    .grand-total { font-weight: bold; background-color: #f8f9fa !important; }
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
    ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
    
    # Sparta Sheet (Apps & Quality)
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Standardized_Date'] = pd.to_datetime(df1['Standardized_Date'], format='mixed', dayfirst=True, errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    # Sparta2 Sheet (Portal Status)
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Sale Date'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()
    
    return df1, df2

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

# --- UI START ---
st.title("🚀 Sparta Performance & Portal Dashboard")

try:
    df1, df2 = fetch_data()

    # Date Range Selectors
    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("Start Date", datetime.date.today().replace(day=1))
    with col_b:
        end_date = st.date_input("End Date", datetime.date.today())

    # Data Filtering
    f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)].copy()

    # Apply Logic Mappings
    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    # 1. Total Apps Grouping
    app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')

    # 2. Quality Status Grouping (Unique Names)
    qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0)
    qual_counts = qual_counts.add_prefix('Qual_')

    # 3. Portal Status Grouping (Unique Names)
    port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0)
    port_counts = port_counts.add_prefix('Port_')

    # Master Merge
    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    master = pd.DataFrame(index=all_advisors).join([app_counts, qual_counts, port_counts]).fillna(0)
    master = master.sort_values('Total Apps', ascending=False)

    # Add Totals Row
    totals = master.sum().to_frame().T
    totals.index = ["GRAND TOTAL"]
    final_df = pd.concat([master, totals])

    # --- RENDER TABLES ---
    
    # Setup columns for the 3 tables (renaming them for clean display)
    q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
    p_cols = [c for c in final_df.columns if c.startswith('Port_')]

    # Table 1: Apps (Green)
    html_apps = final_df[['Total Apps']].style.background_gradient(cmap='Greens', subset=final_df.index[:-1]).to_html()

    # Table 2: Quality (Multi-colored)
    # We rename columns here by removing 'Qual_' just for the UI
    disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
    html_qual = disp_qual.style\
        .background_gradient(subset=['Approved'], cmap='YlGn')\
        .background_gradient(subset=['Cancelled'], cmap='Reds')\
        .background_gradient(subset=['Rework'], cmap='YlOrBr').to_html()

    # Table 3: Portal (Blue/Red)
    disp_port = final_df[p_cols].rename(columns=lambda x: x.replace('Port_', ''))
    html_port = disp_port.style\
        .background_gradient(subset=['Live'], cmap='Blues')\
        .background_gradient(subset=['Cancelled'], cmap='Reds')\
        .background_gradient(subset=['Committed'], cmap='Purples').to_html()

    st.divider()
    
    # Side-by-Side Display
    st.markdown(f"""
    <div class="table-container">
        <div class="table-box"><b>📊 Total Applications</b><br><br>{html_apps}</div>
        <div class="table-box"><b>✅ Quality Audit</b><br><br>{html_qual}</div>
        <div class="table-box"><b>🌐 Portal Status</b><br><br>{html_port}</div>
    </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Waiting for valid data or connection... Error: {e}")
