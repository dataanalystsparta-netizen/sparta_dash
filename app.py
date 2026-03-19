import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import numpy as np
import plotly.express as px
import plotly.graph_objects as go 
import io

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# --- MASTER AGENT LIST ---
LIVE_AGENTS = [
    "Anshu", "Anjali", "Aman", "Frogh", "Gaurav", "Guru", 
    "Naveen", "Krrish", "Niki", "Manmeet", "Sangeeta", "Gungun",
    "Animesh", "Ajay", "Shaheen"
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

# --- MAIN UI ---
try:
    df1, df2, last_sync = fetch_data()

    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d5ac6c503.png", width=280)
        st.title("Sparta Performance & Live Status")
        
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

    sort_options = {
        "Total Applications (High to Low)": "Total Applications", 
        "Quality: Approved": "Qual_Approved", 
        "Live Status: Live": "Port_Live", 
        "Advisor Name (A-Z)": "index"
    }
    
    app_counts_base = f1.groupby('Advisor').size().to_frame('Total Applications')
    qual_counts_base = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
    port_counts_base = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
    master_base = pd.DataFrame(index=all_advisors).join([app_counts_base, qual_counts_base, port_counts_base]).fillna(0)

    available_sorts = [k for k, v in sort_options.items() if v == "index" or v in master_base.columns]
    selected_sort_label = col_c.selectbox("Master Sort Alignment:", available_sorts)

    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    with tab1:
        show_live_team = st.checkbox("Show current roster only", value=False, key="t_filter")
        
        if show_live_team:
            f1_team = f1[f1['Advisor'].isin(formatted_live)].copy()
            f2_team = f2[f2['Advisor'].isin(formatted_live)].copy()
            active_advisors_team = [n for n in all_advisors if n in formatted_live]
        else:
            f1_team, f2_team = f1.copy(), f2.copy()
            active_advisors_team = all_advisors

        t_apps = len(f1_team)
        t_appr = len(f1_team[f1_team['Q_Status'] == 'Approved'])
        t_comm = len(f2_team)
        t_live = len(f2_team[f2_team['P_Status'] == 'Live'])

        with st.container(border=True):
            m = st.columns(7)
            m[0].metric("📝 Tot. Apps", f"{t_apps:,}")
            m[1].metric("✅ Approved", f"{t_appr:,}")
            m[2].metric("📈 Appr. %", f"{(t_appr/t_apps*100):.1f}%" if t_apps > 0 else "0%")
            m[3].metric("📦 Committed", f"{t_comm:,}")
            m[4].metric("📋 Comm. %", f"{(t_comm/t_apps*100):.1f}%" if t_apps > 0 else "0%")
            m[5].metric("🌐 Total Live", f"{t_live:,}")
            m[6].metric("🚀 Live Rate", f"{(t_live/t_comm*100):.1f}%" if t_comm > 0 else "0%")

        app_counts = f1_team.groupby('Advisor').size().to_frame('Total Applications')
        qual_counts = f1_team.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
        port_counts = f2_team.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
        
        tab_master = pd.DataFrame(index=active_advisors_team).join([app_counts, qual_counts, port_counts]).fillna(0)
        sort_col = sort_options[selected_sort_label]
        master = tab_master.sort_index() if sort_col == "index" else tab_master.sort_values(sort_col, ascending=False)
        
        st.divider()
        c1, c2, c3 = st.columns([1, 1.8, 1.8])
        
        # Prepare Dataframes for Display and Export
        df_vol = master[['Total Applications']]
        q_cols = [c for c in master.columns if c.startswith('Qual_')]
        df_qual = format_with_pct(master[q_cols].rename(columns=lambda x: x.replace('Qual_', '')), master['Total Applications']) if q_cols else pd.DataFrame()
        p_cols = [c for c in master.columns if c.startswith('Port_')]
        df_live = format_with_pct(master[p_cols].rename(columns=lambda x: x.replace('Port_', '')), master['Total Applications']) if p_cols else pd.DataFrame()

        with c1:
            st.subheader("📊 Volume")
            st.dataframe(df_vol.style.background_gradient(cmap='Greens'), use_container_width=True)
        
        with c2:
            st.subheader("✅ Quality Audit")
            if not df_qual.empty:
                st.dataframe(df_qual, use_container_width=True)
            else: st.info("No quality data.")
            
        with c3:
            st.subheader("🌐 Live Status")
            if not df_live.empty:
                st.dataframe(df_live, use_container_width=True)
            else: st.info("No live status data.")

        # --- DOWNLOAD SECTION ---
        st.write("### 📥 Export Reports")
        d_col1, d_col2, d_col3 = st.columns(3)

        # 1. EXCEL EXPORT (Multiple Sheets)
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
            df_vol.to_excel(writer, sheet_name='Volume_Summary')
            if not df_qual.empty: df_qual.to_excel(writer, sheet_name='Quality_Audit')
            if not df_live.empty: df_live.to_excel(writer, sheet_name='Live_Status')
        
        d_col1.download_button(
            label="Download Excel (All Tabs)",
            data=output_excel.getvalue(),
            file_name=f"Sparta_Report_{start_date}_to_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # 2. CSV EXPORT (Concatenated)
        combined_csv = "--- VOLUME REPORT ---\n" + df_vol.to_csv() + \
                       "\n\n--- QUALITY AUDIT ---\n" + (df_qual.to_csv() if not df_qual.empty else "No Data") + \
                       "\n\n--- LIVE STATUS ---\n" + (df_live.to_csv() if not df_live.empty else "No Data")
        
        d_col2.download_button(
            label="Download CSV (Combined)",
            data=combined_csv,
            file_name=f"Sparta_Report_{start_date}_to_{end_date}.csv",
            mime="text/csv"
        )

        # 3. PDF EXPORT (Basic text/markdown conversion)
        # Note: True PDF generation usually requires heavy libraries, this creates a printable text file
        combined_text = f"Sparta Performance Report: {start_date} to {end_date}\n" + "="*50 + "\n\n" + combined_csv
        d_col3.download_button(
            label="Download PDF (Text Format)",
            data=combined_text,
            file_name=f"Sparta_Report_{start_date}_to_{end_date}.pdf",
            mime="application/pdf"
        )

    with tab2:
        st.subheader("👤 Individual Breakdown")
        col_check, col_select = st.columns([1, 3])
        show_ind_only = col_check.checkbox("Current Roster Only", value=True, key="i_filter")
        dropdown_list = [n for n in all_advisors if n in formatted_live] if show_ind_only else all_advisors
        selected_agent = col_select.selectbox("Select Agent:", dropdown_list)
        
        if selected_agent:
            ag1 = f1[f1['Advisor'] == selected_agent].copy()
            ag2 = f2[f2['Advisor'] == selected_agent].copy()
            st.divider()
            d_apps = ag1.groupby(ag1['Date_Parsed'].dt.date).size().reset_index(name='Apps')
            fig = px.line(d_apps, x='Date_Parsed', y='Apps', title=f"Daily Apps Trend: {selected_agent}")
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Configuration Error: {e}")
