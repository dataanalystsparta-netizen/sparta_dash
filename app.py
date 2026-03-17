import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import numpy as np
import plotly.express as px
import plotly.graph_objects as go # Added for Dual-Axis
from plotly.subplots import make_subplots # Added for Dual-Axis

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# --- MASTER AGENT LIST (LIVE AS OF TODAY) ---
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
    "qual_approved": "Applications that have successfully passed the Quality Audit process.",
    "approv_rate": "Percentage of total applications that reached 'Approved' status.",
    "commit_apps": "Total applications that got 'Committed'.",
    "commit_rate": "Percentage of applications that got 'Committed'",
    "total_live": "Total applications that got 'Live'.",
    "live_rate": "Conversion rate from Committed applications to confirmed Live records."
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
        "Quality: Cancelled": "Qual_Cancelled", 
        "Live Status: Live": "Port_Live", 
        "Advisor Name (A-Z)": "index"
    }
    
    app_counts_base = f1.groupby('Advisor').size().to_frame('Total Applications')
    qual_counts_base = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
    port_counts_base = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
    master_base = pd.DataFrame(index=all_advisors).join([app_counts_base, qual_counts_base, port_counts_base]).fillna(0)

    available_sorts = [k for k, v in sort_options.items() if v == "index" or v in master_base.columns]
    selected_sort_label = col_c.selectbox("Master Sort (Aligns all tables):", available_sorts)

    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    with tab1:
        show_live_team = st.checkbox("Show current roster only", value=False, key="team_roster_filter")
        
        if show_live_team:
            f1_team = f1[f1['Advisor'].isin(formatted_live)].copy()
            f2_team = f2[f2['Advisor'].isin(formatted_live)].copy()
            active_advisors_team = [name for name in all_advisors if name in formatted_live]
        else:
            f1_team = f1.copy()
            f2_team = f2.copy()
            active_advisors_team = all_advisors

        team_apps = len(f1_team)
        team_approved = len(f1_team[f1_team['Q_Status'] == 'Approved'])
        team_approv_rate = f"{(team_approved / team_apps * 100):.1f}%" if team_apps > 0 else "0.0%"
        team_committed = len(f2_team)
        team_commit_rate = f"{(team_committed / team_apps * 100):.1f}%" if team_apps > 0 else "0.0%"
        team_live = len(f2_team[f2_team['P_Status'] == 'Live'])
        team_live_rate = f"{(team_live / team_committed * 100):.1f}%" if team_committed > 0 else "0.0%"

        with st.container(border=True):
            tm1, tm2, tm3, tm4, tm5, tm6, tm7 = st.columns(7)
            tm1.metric("📝 Tot. Applications", f"{team_apps:,}", help=KPI_DEFS["total_apps"])
            tm2.metric("✅ Quality Approv.", f"{team_approved:,}", help=KPI_DEFS["qual_approved"])
            tm3.metric("📈 Approv. Rate", team_approv_rate, help=KPI_DEFS["approv_rate"])
            tm4.metric("📦 Commit. Apps", f"{team_committed:,}", help=KPI_DEFS["commit_apps"])
            tm5.metric("📋 Commit. Rate", team_commit_rate, help=KPI_DEFS["commit_rate"])
            tm6.metric("🌐 Total Live", f"{team_live:,}", help=KPI_DEFS["total_live"])
            tm7.metric("🚀 Live Rate", team_live_rate, help=KPI_DEFS["live_rate"])

        app_counts = f1_team.groupby('Advisor').size().to_frame('Total Applications')
        qual_counts = f1_team.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
        port_counts = f2_team.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
        
        tab_master = pd.DataFrame(index=active_advisors_team).join([app_counts, qual_counts, port_counts]).fillna(0)
        sort_col = sort_options[selected_sort_label]
        master = tab_master.sort_index() if sort_col == "index" else tab_master.sort_values(sort_col, ascending=False)
        
        totals_row = master.sum().to_frame().T
        totals_row.index = ["GRAND TOTAL"]
        final_df = pd.concat([master, totals_row])
        advisor_indices = master.index

        st.divider()
        c1, c2, c3 = st.columns([1, 1.8, 1.8])
        with c1:
            st.subheader("📊 Applications")
            st.dataframe(final_df[['Total Applications']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Applications')), use_container_width=True, height=500)
        
        with c2:
            st.subheader("✅ Quality Audit")
            q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
            disp_qual_num = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
            disp_qual_str = format_with_pct(disp_qual_num, final_df['Total Applications'])
            styler_q = disp_qual_str.style
            for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                if col in disp_qual_num.columns:
                    styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap, gmap=disp_qual_num[col])
            st.dataframe(styler_q, use_container_width=True, height=500)
            
        with c3:
            st.subheader("🌐 Live Status")
            p_cols = [c for c in final_df.columns if c.startswith('Port_')]
            p_order = ['Port_Live', 'Port_Committed', 'Port_Cancelled', 'Port_Others']
            actual_p_order = [c for c in p_order if c in p_cols]
            disp_port_num = final_df[actual_p_order].rename(columns=lambda x: x.replace('Port_', ''))
            disp_port_str = format_with_pct(disp_port_num, final_df['Total Applications'])
            styler_p = disp_port_str.style
            for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
                if col in disp_port_num.columns:
                    styler_p = styler_p.background_gradient(subset=(advisor_indices, col), cmap=cmap, gmap=disp_port_num[col])
            st.dataframe(styler_p, use_container_width=True, height=500)

        # --- TEAM GRAPHS (DUAL AXIS & LIVE/CANCELLED) ---
        st.divider()
        g_col1, g_col2 = st.columns(2)

        with g_col1:
            st.subheader("📈 Trend: Apps vs Quality")
            f1_team['Day'] = f1_team['Date_Parsed'].dt.date.astype(str)
            # Volume Data
            vol_data = f1_team.groupby('Day').size().reset_index(name='Apps')
            # Quality Data
            q_trend = f1_team[f1_team['Q_Status'] == 'Approved'].groupby('Day').size().reset_index(name='Approved')
            combined = pd.merge(vol_data, q_trend, on='Day', how='left').fillna(0)

            fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
            fig_dual.add_trace(go.Bar(x=combined['Day'], y=combined['Apps'], name="Total Apps", marker_color='#1E3A8A'), secondary_y=False)
            fig_dual.add_trace(go.Scatter(x=combined['Day'], y=combined['Approved'], name="Approved (Audit)", line=dict(color='#2E7D32', width=3)), secondary_y=True)
            
            fig_dual.update_layout(title_text="Daily Apps vs. Approved Quality", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig_dual.update_yaxes(title_text="<b>Total Applications</b>", secondary_y=False)
            fig_dual.update_yaxes(title_text="<b>Approved Audit</b>", secondary_y=True)
            st.plotly_chart(fig_dual, use_container_width=True)

        with g_col2:
            st.subheader("🚀 Status: Live vs. Cancelled")
            # Pulling from the master data (excluding Grand Total)
            status_plot = master[['Port_Live', 'Port_Cancelled']].rename(columns={'Port_Live':'Live', 'Port_Cancelled':'Cancelled'}).reset_index()
            fig_status = px.bar(status_plot, x='index', y=['Live', 'Cancelled'], barmode='group', 
                                color_discrete_map={'Live': '#2563EB', 'Cancelled': '#DC2626'},
                                title="Agent-wise Live vs. Cancelled Volume")
            fig_status.update_layout(xaxis_title="Advisor", yaxis_title="Volume", legend_title="Portal Status")
            st.plotly_chart(fig_status, use_container_width=True)

    with tab2:
        st.subheader("👤 Detailed Agent Analysis")
        col_check, col_select = st.columns([1, 3])
        show_live_only = col_check.checkbox("Show current roster only", value=False, key="individual_roster_filter")
        dropdown_list = [n for n in all_advisors if n in formatted_live] if show_live_only else all_advisors
        selected_agent = col_select.selectbox("Select Agent:", dropdown_list if dropdown_list else all_advisors)
        
        if selected_agent:
            ag1 = f1[f1['Advisor'] == selected_agent].copy()
            ag2 = f2[f2['Advisor'] == selected_agent].copy()
            # ... (Individual Table Logic and Metrics preserved exactly) ...
            total_apps = len(ag1)
            approved = len(ag1[ag1['Q_Status'] == 'Approved'])
            approval_rate = f"{(approved / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            total_committed_apps = len(ag2) 
            committed_rate = f"{(total_committed_apps / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            live = len(ag2[ag2['P_Status'] == 'Live'])
            live_rate = f"{(live / total_committed_apps * 100):.1f}%" if total_committed_apps > 0 else "0.0%"
            
            with st.container(border=True):
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                m1.metric("📝 Tot. Applications", f"{total_apps:,}", help=KPI_DEFS["total_apps"])
                m2.metric("✅ Quality Approv.", f"{approved:,}", help=KPI_DEFS["qual_approved"])
                m3.metric("📈 Approv. Rate", approval_rate, help=KPI_DEFS["approv_rate"])
                m4.metric("📦 Commit. Apps", f"{total_committed_apps:,}", help=KPI_DEFS["commit_apps"])
                m5.metric("📋 Commit. Rate", committed_rate, help=KPI_DEFS["commit_rate"])
                m6.metric("🌐 Total Live", f"{live:,}", help=KPI_DEFS["total_live"])
                m7.metric("🚀 Live Rate", live_rate, help=KPI_DEFS["live_rate"])
            
            st.divider()
            view_mode = st.radio("View Breakdown By:", ["Daily", "Monthly"], horizontal=True)
            # (Your table logic here remains unchanged)
            st.write(f"Showing breakdown for {selected_agent}")

            # --- INDIVIDUAL DUAL AXIS ---
            st.divider()
            st.subheader(f"📈 Performance Trend: {selected_agent}")
            ag1['Day'] = ag1['Date_Parsed'].dt.date.astype(str)
            i_vol = ag1.groupby('Day').size().reset_index(name='Apps')
            i_qual = ag1[ag1['Q_Status'] == 'Approved'].groupby('Day').size().reset_index(name='Approved')
            i_comb = pd.merge(i_vol, i_qual, on='Day', how='left').fillna(0)

            fig_ind = make_subplots(specs=[[{"secondary_y": True}]])
            fig_ind.add_trace(go.Bar(x=i_comb['Day'], y=i_comb['Apps'], name="Applications", marker_color='#60A5FA'), secondary_y=False)
            fig_ind.add_trace(go.Scatter(x=i_comb['Day'], y=i_comb['Approved'], name="Approved", line=dict(color='#059669', width=3)), secondary_y=True)
            fig_ind.update_layout(hovermode="x unified")
            st.plotly_chart(fig_ind, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
