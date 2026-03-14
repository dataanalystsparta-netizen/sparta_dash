import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

st.markdown("""
    <style>
    .block-container { max-width: 98%; padding-top: 2rem; }
    .table-container { display: flex; flex-direction: row; gap: 20px; overflow-x: auto; align-items: flex-start; }
    .table-box { border: 1px solid #e6e6e6; border-radius: 5px; padding: 10px; background-color: white; min-width: 300px; }
    td, th { white-space: nowrap !important; font-size: 13px !important; padding: 6px 12px !important; border: 1px solid #f0f0f0 !important; }
    th { background-color: #1E3A8A !important; color: white !important; text-align: center !important; }
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
    
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Standardized_Date'] = pd.to_datetime(df1['Standardized_Date'], format='mixed', dayfirst=True, errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
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

    col_a, col_b = st.columns(2)
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    # 1. Apps
    app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')

    # 2. Quality
    qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0)
    qual_counts = qual_counts.add_prefix('Qual_')

    # 3. Portal
    port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0)
    port_counts = port_counts.add_prefix('Port_')

    # Merge
    master = pd.DataFrame(index=sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))).join([app_counts, qual_counts, port_counts]).fillna(0)
    master = master.sort_values('Total Apps', ascending=False)

    totals = master.sum().to_frame().T
    totals.index = ["GRAND TOTAL"]
    final_df = pd.concat([master, totals])

    # --- SAFE GRADIENT RENDERER ---
    rows_to_style = final_df.index[:-1] # Exclude Grand Total from gradients

    # Table 1: Apps
    html_apps = final_df[['Total Apps']].style.background_gradient(cmap='Greens', subset=(rows_to_style, 'Total Apps')).to_html()

    # Table 2: Quality (Only style columns if they exist)
    q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
    disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
    
    styler_q = disp_qual.style
    for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'YlOrBr')]:
        if col in disp_qual.columns:
            styler_q = styler_q.background_gradient(subset=(rows_to_style, col), cmap=cmap)
    html_qual = styler_q.to_html()

    # Table 3: Portal
    p_cols = [c for c in final_df.columns if c.startswith('Port_')]
    disp_port = final_df[p_cols].rename(columns=lambda x: x.replace('Port_', ''))
    
    styler_p = disp_port.style
    for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
        if col in disp_port.columns:
            styler_p = styler_p.background_gradient(subset=(rows_to_style, col), cmap=cmap)
    html_port = styler_p.to_html()

    st.divider()
    st.markdown(f"""
    <div class="table-container">
        <div class="table-box"><b>📊 Total Applications</b><br><br>{html_apps}</div>
        <div class="table-box"><b>✅ Quality Audit</b><br><br>{html_qual}</div>
        <div class="table-box"><b>🌐 Portal Status</b><br><br>{html_port}</div>
    </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.warning(f"No data found for the selected date range. Try widening your search.")
    if st.checkbox("Show Error Details"):
        st.error(e)
