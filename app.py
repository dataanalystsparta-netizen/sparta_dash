import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import numpy as np
import plotly.express as px  # Added for stable charting

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
    h3 {
        margin-bottom: 0.5rem !important; 
        font-size: 1.2rem !important; 
        color: #1E3A8A;
    }
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
        
        # --- ORIGINAL TABLES ---
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

        # --- NEW TREND GRAPHS (TEAM) ---
        st.divider()
        st.subheader("📈 Team Performance Trends")
        tg_1, tg_2 = st.columns(2)
        
        # Trend Data Processing
        f1_trend = f1_team.groupby(f1_team['Date_Parsed'].dt.date).size().reset_index(name='Apps')
        f1_trend['Date_Parsed'] = f1_trend['Date_Parsed'].astype(str)
        
        with tg_1:
            fig_apps = px.bar(f1_trend, x='Date_Parsed', y='Apps', title="Daily Team Applications", color_discrete_sequence=['#2E7D32'])
            st.plotly_chart(fig_apps, use_container_width=True)
            
        with tg_2:
            q_trend = f1_team.groupby([f1_team['Date_Parsed'].dt.date, 'Q_Status']).size().unstack(fill_value=0).reset_index()
            q_trend['Date_Parsed'] = q_trend['Date_Parsed'].astype(str)
            fig_q = px.line(q_trend, x='Date_Parsed', y=[c for c in ['Approved', 'Cancelled', 'Rework'] if c in q_trend.columns], title="Quality Trends")
            st.plotly_chart(fig_q, use_container_width=True)

    with tab2:
        st.subheader("👤 Detailed Agent Analysis")
        col_check, col_select = st.columns([1, 3])
        show_live_only = col_check.checkbox("Show current roster only", value=False, key="individual_roster_filter")
        dropdown_list = [n for n in all_advisors if n in formatted_live] if show_live_only else all_advisors
        selected_agent = col_select.selectbox("Select Agent:", dropdown_list if dropdown_list else all_advisors)
        
        if selected_agent:
            ag1 = f1[f1['Advisor'] == selected_agent].copy()
            ag2 = f2[f2['Advisor'] == selected_agent].copy()
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
            if view_mode == "Monthly":
                ag1['Period'] = ag1['Date_Parsed'].dt.to_period('M')
                ag2['Period'] = ag2['Date_Parsed'].dt.to_period('M')
            else:
                ag1['Period'] = ag1['Date_Parsed'].dt.date
                ag2['Period'] = ag2['Date_Parsed'].dt.date
            
            st.write(f"**{view_mode}** breakdown for **{selected_agent}**")
            ca, cb, cc = st.columns([1, 1.8, 1.8])

            with ca:
                st.markdown(f"#### 📊 {view_mode} Applications")
                daily_apps = ag1.groupby('Period').size().to_frame('Applications')
                if view_mode == "Monthly": daily_apps.index = daily_apps.index.strftime('%b %Y')
                t_apps = daily_apps.sum().to_frame().T
                t_apps.index = ["TOTAL"]
                df_apps = pd.concat([daily_apps, t_apps])
                st.dataframe(df_apps.style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(daily_apps.index, 'Applications')), use_container_width=True)

            with cb:
                st.markdown("#### ✅ Quality Audit")
                daily_qual = ag1.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
                q_order = ['Approved', 'Rework', 'Cancelled', 'Others']
                actual_q = [c for c in q_order if c in daily_qual.columns]
                dq_num = daily_qual[actual_q]
                if view_mode == "Monthly": dq_num.index = dq_num.index.strftime('%b %Y')
                row_totals = daily_apps['Applications']
                dq_str = format_with_pct(dq_num, row_totals)
                t_qual_num = dq_num.sum().to_frame().T
                t_qual_num.index = ["TOTAL"]
                t_qual_str = format_with_pct(t_qual_num, pd.Series([total_apps], index=["TOTAL"]))
                final_q_str = pd.concat([dq_str, t_qual_str])
                styler_dq = final_q_str.style
                for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                    if col in dq_num.columns:
                        styler_dq = styler_dq.background_gradient(subset=(dq_num.index, col), cmap=cmap, gmap=dq_num[col])
                st.dataframe(styler_dq, use_container_width=True)

            with cc:
                st.markdown("#### 🌐 Live Status")
                daily_port = ag2.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
                p_order = ['Live', 'Committed', 'Cancelled', 'Others']
                actual_p = [c for c in p_order if c in daily_port.columns]
                dp_num = daily_port[actual_p]
                if view_mode == "Monthly": dp_num.index = dp_num.index.strftime('%b %Y')
                dp_str = format_with_pct(dp_num, row_totals)
                t_port_num = dp_num.sum().to_frame().T
                t_port_num.index = ["TOTAL"]
                t_port_str = format_with_pct(t_port_num, pd.Series([total_apps], index=["TOTAL"]))
                final_p_str = pd.concat([dp_str, t_port_str])
                styler_dp = final_p_str.style
                for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
                    if col in dp_num.columns:
                        styler_dp = styler_dp.background_gradient(subset=(dp_num.index, col), cmap=cmap, gmap=dp_num[col])
                st.dataframe(styler_dp, use_container_width=True)

            # --- NEW TREND GRAPHS (INDIVIDUAL) ---
            st.divider()
            st.subheader(f"📈 Trends for {selected_agent}")
            i_tg1, i_tg2 = st.columns(2)
            
            # Prepare Plotly data (casting Period to string to avoid Python 3.13 issues)
            ind_trend_data = daily_apps.reset_index()
            ind_trend_data['Period'] = ind_trend_data['Period'].astype(str)
            
            with i_tg1:
                fig_ind_apps = px.line(ind_trend_data, x='Period', y='Applications', title="Application Trend", markers=True)
                st.plotly_chart(fig_ind_apps, use_container_width=True)
            
            with i_tg2:
                # Merge Quality statuses for plotting
                ind_q_plot = dq_num.reset_index()
                ind_q_plot['Period'] = ind_q_plot['Period'].astype(str)
                fig_ind_q = px.bar(ind_q_plot, x='Period', y=[c for c in ['Approved', 'Cancelled'] if c in ind_q_plot.columns], barmode='group', title="Quality Volume")
                st.plotly_chart(fig_ind_q, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
