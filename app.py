import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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

KPI_DEFS = {
    "total_apps": "Total Applications.",
    "qual_approved": "Passed Quality Audit.",
    "approv_rate": "% of Apps Approved.",
    "commit_apps": "Total Committed.",
    "commit_rate": "% of Apps Committed",
    "total_live": "Total Live.",
    "live_rate": "Committed to Live conversion."
}

# --- UI START ---
try:
    df1, df2, last_sync = fetch_data()

    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d5ac6c503.png", width=280)
        st.title("Sparta Performance & Live Status Dashboard")
        
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
    selected_sort_label = col_c.selectbox("Master Sort:", available_sorts)

    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    # --- TAB 1: TEAM ---
    with tab1:
        show_live_team = st.checkbox("Show current roster only", value=False, key="t_roster")
        if show_live_team:
            f1_t = f1[f1['Advisor'].isin(formatted_live)].copy()
            f2_t = f2[f2['Advisor'].isin(formatted_live)].copy()
            active_adv = [n for n in all_advisors if n in formatted_live]
        else:
            f1_t, f2_t, active_adv = f1.copy(), f2.copy(), all_advisors

        # Metrics...
        t_apps = len(f1_t)
        t_appr = len(f1_t[f1_t['Q_Status'] == 'Approved'])
        t_comm = len(f2_t)
        t_live = len(f2_t[f2_t['P_Status'] == 'Live'])

        with st.container(border=True):
            m = st.columns(7)
            m[0].metric("📝 Apps", f"{t_apps:,}")
            m[1].metric("✅ Appr.", f"{t_appr:,}")
            m[2].metric("📈 Rate", f"{(t_appr/t_apps*100 if t_apps>0 else 0):.1f}%")
            m[3].metric("📦 Comm.", f"{t_comm:,}")
            m[4].metric("📋 Rate", f"{(t_comm/t_apps*100 if t_apps>0 else 0):.1f}%")
            m[5].metric("🌐 Live", f"{t_live:,}")
            m[6].metric("🚀 Rate", f"{(t_live/t_comm*100 if t_comm>0 else 0):.1f}%")

        # Table Assembly...
        ac = f1_t.groupby('Advisor').size().to_frame('Total Applications')
        qc = f1_t.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
        pc = f2_t.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
        
        mst = pd.DataFrame(index=active_adv).join([ac, qc, pc]).fillna(0)
        sc = sort_options[selected_sort_label]
        mst = mst.sort_index() if sc == "index" else mst.sort_values(sc, ascending=False)
        
        final_mst = pd.concat([mst, mst.sum().to_frame().T.rename(index={0: "GRAND TOTAL"})])
        idx = mst.index

        st.divider()
        c1, c2, c3 = st.columns([1, 1.8, 1.8])
        with c1:
            st.subheader("📊 Applications")
            st.dataframe(final_mst[['Total Applications']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(idx, 'Total Applications')), use_container_width=True)
        with c2:
            st.subheader("✅ Quality Audit")
            dq = final_mst[[c for c in final_mst.columns if c.startswith('Qual_')]].rename(columns=lambda x: x.replace('Qual_', ''))
            st.dataframe(format_with_pct(dq, final_mst['Total Applications']).style.background_gradient(subset=(idx, 'Approved'), cmap='YlGn', gmap=dq['Approved']), use_container_width=True)
        with c3:
            st.subheader("🌐 Live Status")
            dp = final_mst[[c for c in final_mst.columns if c.startswith('Port_')]].rename(columns=lambda x: x.replace('Port_', ''))
            st.dataframe(format_with_pct(dp, final_mst['Total Applications']).style.background_gradient(subset=(idx, 'Live'), cmap='Blues', gmap=dp['Live']), use_container_width=True)

        # TEAM GRAPHS
        st.divider()
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("📈 Trend: Apps vs Quality")
            f1_t['Day'] = f1_t['Date_Parsed'].dt.date.astype(str)
            v = f1_t.groupby('Day').size().reset_index(name='Apps')
            q = f1_t[f1_t['Q_Status'] == 'Approved'].groupby('Day').size().reset_index(name='Approved')
            cb = pd.merge(v, q, on='Day', how='left').fillna(0)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=cb['Day'], y=cb['Apps'], name="Apps", marker_color='#1E3A8A'), secondary_y=False)
            fig.add_trace(go.Scatter(x=cb['Day'], y=cb['Approved'], name="Approved", line=dict(color='#2E7D32', width=3)), secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.subheader("🚀 Status: Live vs. Cancelled")
            sp = mst[['Port_Live', 'Port_Cancelled']].rename(columns={'Port_Live':'Live', 'Port_Cancelled':'Cancelled'}).reset_index()
            fig2 = px.bar(sp, x='index', y=['Live', 'Cancelled'], barmode='group', color_discrete_map={'Live': '#2563EB', 'Cancelled': '#DC2626'})
            st.plotly_chart(fig2, use_container_width=True)

    # --- TAB 2: INDIVIDUAL (RESTORED FULLY) ---
    with tab2:
        st.subheader("👤 Detailed Agent Analysis")
        col_chk, col_sel = st.columns([1, 3])
        live_only = col_chk.checkbox("Show current roster only", value=False, key="i_roster")
        dd = [n for n in all_advisors if n in formatted_live] if live_only else all_advisors
        sel_agent = col_sel.selectbox("Select Agent:", dd)
        
        if sel_agent:
            ag1, ag2 = f1[f1['Advisor'] == sel_agent].copy(), f2[f2['Advisor'] == sel_agent].copy()
            
            # Metrics
            a_tot = len(ag1)
            a_app = len(ag1[ag1['Q_Status'] == 'Approved'])
            a_com = len(ag2)
            a_liv = len(ag2[ag2['P_Status'] == 'Live'])
            
            with st.container(border=True):
                im = st.columns(7)
                im[0].metric("📝 Apps", f"{a_tot:,}")
                im[1].metric("✅ Appr.", f"{a_app:,}")
                im[2].metric("📈 Rate", f"{(a_app/a_tot*100 if a_tot>0 else 0):.1f}%")
                im[3].metric("📦 Comm.", f"{a_com:,}")
                im[4].metric("📋 Rate", f"{(a_com/a_tot*100 if a_tot>0 else 0):.1f}%")
                im[5].metric("🌐 Live", f"{a_liv:,}")
                im[6].metric("🚀 Rate", f"{(a_liv/a_com*100 if a_com>0 else 0):.1f}%")

            st.divider()
            vm = st.radio("View Breakdown By:", ["Daily", "Monthly"], horizontal=True)
            ag1['Period'] = ag1['Date_Parsed'].dt.to_period('M').astype(str) if vm == "Monthly" else ag1['Date_Parsed'].dt.date.astype(str)
            ag2['Period'] = ag2['Date_Parsed'].dt.to_period('M').astype(str) if vm == "Monthly" else ag2['Date_Parsed'].dt.date.astype(str)
            
            # Individual Table Logic
            i_ac = ag1.groupby('Period').size().to_frame('Total Applications')
            i_qc = ag1.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
            i_pc = ag2.groupby(['Period', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
            
            i_mst = i_ac.join([i_qc, i_pc]).fillna(0).sort_index(ascending=False)
            
            ca, cb, cc = st.columns([1, 1.8, 1.8])
            with ca:
                st.write("**Applications**")
                st.dataframe(i_mst[['Total Applications']], use_container_width=True)
            with cb:
                st.write("**Quality**")
                idq = i_mst[[c for c in i_mst.columns if c.startswith('Qual_')]].rename(columns=lambda x: x.replace('Qual_', ''))
                st.dataframe(format_with_pct(idq, i_mst['Total Applications']), use_container_width=True)
            with cc:
                st.write("**Live Status**")
                idp = i_mst[[c for c in i_mst.columns if c.startswith('Port_')]].rename(columns=lambda x: x.replace('Port_', ''))
                st.dataframe(format_with_pct(idp, i_mst['Total Applications']), use_container_width=True)

            # INDIVIDUAL GRAPH
            st.divider()
            i_vol = ag1.groupby('Period').size().reset_index(name='Apps')
            i_q = ag1[ag1['Q_Status'] == 'Approved'].groupby('Period').size().reset_index(name='Approved')
            icb = pd.merge(i_vol, i_q, on='Period', how='left').fillna(0)
            if not icb.empty:
                fig_i = make_subplots(specs=[[{"secondary_y": True}]])
                fig_i.add_trace(go.Bar(x=icb['Period'], y=icb['Apps'], name="Apps", marker_color='#60A5FA'), secondary_y=False)
                fig_i.add_trace(go.Scatter(x=icb['Period'], y=icb['Approved'], name="Approved", line=dict(color='#059669', width=3)), secondary_y=True)
                st.plotly_chart(fig_i, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
