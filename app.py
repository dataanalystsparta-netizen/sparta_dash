import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import numpy as np
import plotly.express as px

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# --- MASTER AGENT LIST ---
LIVE_AGENTS = [
    "Anshu","Anjali", "Aman", "Frogh", "Gaurav", "Guru", 
    "Naveen", "Krrish", "Niki", "Manmeet","Sangeeta","Gungun",
    "Animesh","Ajay","Shaheen"
]

st.markdown("""
   <style>
   .block-container { max-width: 98%; padding-top: 5rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A; }
   .last-updated { font-size: 0.8rem; color: gray; text-align: right; }
   [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
   [data-testid="stMetricLabel"] { font-size: 0.85rem !important; white-space: nowrap; }
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
    df1['Date_Parsed'] = pd.to_datetime(df1['Standardized_Date'], errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Date_Parsed'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()

    try:
        meta = ss.worksheet('Meta').get_all_values()
        last_sync = meta[0][1]
    except:
        last_sync = "Unknown"
    
    return df1, df2, last_sync

def map_quality(val):
    s = str(val).lower()
    if any(x in s for x in ['appr', 'pass']): return 'Approved'
    if any(x in s for x in ['rew', 'repro']): return 'Rework'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    return 'Others'

def map_portal(val):
    s = str(val).lower()
    if 'live' in s: return 'Live'
    if 'com' in s: return 'Committed'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    return 'Others'

def format_with_pct(val_df, total_series):
    display_df = val_df.copy()
    for col in val_df.columns:
        pcts = (val_df[col] / total_series * 100).fillna(0)
        display_df[col] = val_df[col].apply(lambda x: f"{int(x):,}") + " (" + pcts.map("{:.1f}%".format) + ")"
    return display_df

# --- UI START ---
try:
    df1, df2, last_sync = fetch_data()

    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d5ac6c503.png", width=280)
        st.title("Sparta Dashboard")
        
    col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Date_Parsed'].dt.date >= start_date) & (df1['Date_Parsed'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Date_Parsed'].dt.date >= start_date) & (df2['Date_Parsed'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    formatted_live = [name.strip().title() for name in LIVE_AGENTS]

    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    with tab1:
        # --- TABLES (EXACTLY AS THEY WERE) ---
        show_live_team = st.checkbox("Show current roster only", value=False)
        active_list = formatted_live if show_live_team else all_advisors
        
        f1_t = f1[f1['Advisor'].isin(active_list)]
        f2_t = f2[f2['Advisor'].isin(active_list)]

        app_counts = f1_t.groupby('Advisor').size().to_frame('Total Applications')
        qual_counts = f1_t.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
        port_counts = f2_t.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
        
        master = pd.DataFrame(index=active_list).join([app_counts, qual_counts, port_counts]).fillna(0)
        final_df = pd.concat([master, master.sum().to_frame().T.rename(index={0: "GRAND TOTAL"})])

        c1, c2, c3 = st.columns([1, 1.8, 1.8])
        with c1:
            st.subheader("📊 Applications")
            st.dataframe(final_df[['Total Applications']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(master.index, 'Total Applications')), use_container_width=True)
        with c2:
            st.subheader("✅ Quality Audit")
            q_cols = [c for c in master.columns if c.startswith('Qual_')]
            disp_q_num = master[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
            st.dataframe(format_with_pct(disp_q_num, master['Total Applications']).style.background_gradient(cmap='YlGn', subset=(master.index, 'Approved') if 'Approved' in disp_q_num else []), use_container_width=True)
        with c3:
            st.subheader("🌐 Live Status")
            p_cols = [c for c in master.columns if c.startswith('Port_')]
            disp_p_num = master[p_cols].rename(columns=lambda x: x.replace('Port_', ''))
            st.dataframe(format_with_pct(disp_p_num, master['Total Applications']).style.background_gradient(cmap='Blues', subset=(master.index, 'Live') if 'Live' in disp_p_num else []), use_container_width=True)

        # --- GRAPHS (BELOW TABLES - FIXED FOR PYTHON 3.13) ---
        st.divider()
        st.subheader("📈 Team Trend Visualizations")
        f1_t['Period'] = f1_t['Date_Parsed'].dt.date.astype(str)
        trend_data = f1_t.groupby('Period').size().reset_index(name='Apps')
        
        fig = px.bar(trend_data, x='Period', y='Apps', title="Daily Application Volume")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        selected_agent = st.selectbox("Select Agent:", all_advisors)
        if selected_agent:
            ag1 = f1[f1['Advisor'] == selected_agent]
            # ... (Individual tables code preserved) ...
            st.write(f"Showing data for {selected_agent}")
            st.dataframe(ag1[['Standardized_Date', 'Quality Status', 'Q_Status']])
            
            # Graph below
            st.divider()
            ag_trend = ag1.groupby(ag1['Date_Parsed'].dt.date).size().reset_index(name='Count')
            ag_trend['Date_Parsed'] = ag_trend['Date_Parsed'].astype(str)
            fig_ag = px.line(ag_trend, x='Date_Parsed', y='Count', title=f"Trend for {selected_agent}")
            st.plotly_chart(fig_ag, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
