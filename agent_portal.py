import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px
import plotly.graph_objects as go 

st.set_page_config(page_title="Sparta Agent Portal", layout="wide")

st.markdown("""
   <style>
   .block-container { max-width: 98%; padding-top: 1.5rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.1rem !important; color: #1E3A8A; }
   .last-updated { font-size: 0.75rem; color: gray; text-align: right; }
   
   /* Box Container Styling - Sharp Boundaries */
   .kpi-box {
       background-color: #F8FAFC;
       padding: 10px;
       border-radius: 0px; 
       border: 2px solid #475569; 
       height: 100%;
   }
   .box-label {
       font-size: 0.7rem;
       font-weight: 800;
       color: #1E3A8A;
       text-align: center;
       margin-bottom: 8px;
       text-transform: uppercase;
       letter-spacing: 0.5px;
   }

   /* Small KPI Card Styling */
   .kpi-card {
       padding: 6px 2px;
       border-radius: 2px;
       border-top: 3px solid #1E3A8A;
       text-align: center;
       box-shadow: 0 1px 2px rgba(0,0,0,0.05);
   }
   .kpi-label { font-size: 0.6rem; color: #475569; font-weight: 700; margin-bottom: 2px; text-transform: uppercase; white-space: nowrap; overflow: hidden; }
   .kpi-value { font-size: 1rem; color: #1E3A8A; font-weight: 700; margin: 0; line-height: 1; }
   .kpi-pc { font-size: 0.65rem; color: #0F172A; font-weight: 600; margin-top: 1px; }
   </style>
   """, unsafe_allow_html=True)

ACCESS_KEYS = st.secrets["agent_keys"]

def log_agent_login(agent_name):
    try:
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        client = gspread.authorize(creds)
        ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
        try:
            log_sheet = ss.worksheet('Logs')
        except gspread.WorksheetNotFound:
            log_sheet = ss.add_worksheet(title="Logs", rows="1000", cols="3")
            log_sheet.append_row(["Timestamp", "Agent Name", "Action"])
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([timestamp, agent_name, "Login"])
    except:
        pass

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
    def robust_date_parser(date_str):
        date_str = str(date_str).strip()
        try:
            if '/' in date_str: return pd.to_datetime(date_str, dayfirst=True)
            return pd.to_datetime(date_str)
        except: return pd.NaT
    df2['Date_Parsed'] = df2['Sale Date'].apply(robust_date_parser)
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
    if any(x in s for x in ['can']): return 'Cancelled'
    if any(x in s for x in ['rej']): return 'Rejected'
    return 'Others'

def map_portal(val):
    s = str(val).lower()
    if 'live' in s: return 'Live'
    if 'com' in s: return 'Committed'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    return 'Others'

def map_wc(val):
    s = str(val).lower().strip()
    if any(x in s for x in ['done', 'pass', 'comp']): return 'Done'
    if any(x in s for x in ['pend', 'pnd']): return 'Pending'
    if any(x in s for x in ['paper', 'ppw']): return 'Paperwork'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    return 'Others'

def render_kpi(label, value, total):
    # Color Mapping Logic
    lbl = label.lower()
    bg = "#F1F5F9" # Default Gray
    if "total" in lbl: bg = "#E0F2FE" # Light Blue
    elif any(x in lbl for x in ["appr", "done", "live"]): bg = "#DCFCE7" # Light Green
    elif any(x in lbl for x in ["rew", "pend", "paper", "comm"]): bg = "#FEF9C3" # Light Yellow
    elif "can" in lbl or "rej" in lbl: bg = "#FEE2E2" # Light Red
    
    percent = (value / total * 100) if total > 0 else 0
    st.markdown(f"""
        <div class="kpi-card" style="background-color: {bg};">
            <p class="kpi-label">{label}</p>
            <p class="kpi-value">{value:,}</p>
            <p class="kpi-pc">{percent:.1f}%</p>
        </div>
    """, unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.agent_name = ""

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d5ac6c503.png", width=250)
        st.title("Agent Portal")
        st.info("Please enter your access key to view your performance data.")
        user_key = st.text_input("Access Key", type="password")
        if st.button("Login", use_container_width=True):
            if user_key.upper() in ACCESS_KEYS:
                st.session_state.authenticated = True
                st.session_state.agent_name = ACCESS_KEYS[user_key.upper()]
                log_agent_login(ACCESS_KEYS[user_key.upper()])
                st.rerun()
            else:
                st.error("Invalid Access Key. Try again!")
else:
    agent = st.session_state.agent_name
    with st.sidebar:
        st.subheader(f"👤 {agent}")
        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.agent_name = ""
            st.rerun()

    try:
        df1, df2, last_sync = fetch_data()
        ag1 = df1[df1['Advisor'] == agent].copy()
        ag2 = df2[df2['Advisor'] == agent].copy()
        
        col_title, col_time = st.columns([3, 1])
        with col_title:
            st.title(f"My Performance Dashboard")
        col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

        st.write("---")
        col_a, col_b, _ = st.columns([1, 1, 3])
        start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
        end_date = col_b.date_input("End Date", datetime.date.today())

        ag1 = ag1[(ag1['Date_Parsed'].dt.date >= start_date) & (ag1['Date_Parsed'].dt.date <= end_date)]
        ag2 = ag2[(ag2['Date_Parsed'].dt.date >= start_date) & (ag2['Date_Parsed'].dt.date <= end_date)]
        
        ag1['Q_Status'] = ag1['Quality Status'].apply(map_quality)
        ag2['P_Status'] = ag2['Status'].apply(map_portal)
        wc_col = 'Status' if 'Status' in ag1.columns else 'Welcome call Status' if 'Welcome call Status' in ag1.columns else None
        if wc_col: ag1['WC_Clean'] = ag1[wc_col].apply(map_wc)

        # ---------------- CATEGORISED KPI BOXES ----------------
        total_apps = len(ag1)
        total_ag2 = len(ag2)
        
        # Define Groups
        group_1 = [("Total Apps", total_apps, total_apps)]
        group_2 = [
            ("Approved", len(ag1[ag1['Q_Status'] == 'Approved']), total_apps),
            ("Rework", len(ag1[ag1['Q_Status'] == 'Rework']), total_apps),
            ("Cancelled", len(ag1[ag1['Q_Status'] == 'Cancelled']), total_apps),
            ("Rejected", len(ag1[ag1['Q_Status'] == 'Rejected']), total_apps),
            ("Others", len(ag1[ag1['Q_Status'] == 'Others']), total_apps)
        ]
        group_3 = []
        if wc_col:
            group_3 = [
                ("WC Done", len(ag1[ag1['WC_Clean'] == 'Done']), total_apps),
                ("WC Pending", len(ag1[ag1['WC_Clean'] == 'Pending']), total_apps),
                ("WC Paperwork", len(ag1[ag1['WC_Clean'] == 'Paperwork']), total_apps),
                ("WC Cancelled", len(ag1[ag1['WC_Clean'] == 'Cancelled']), total_apps),
                ("WC Others", len(ag1[ag1['WC_Clean'] == 'Others']), total_apps)
            ]
        group_4 = [
            ("Live", len(ag2[ag2['P_Status'] == 'Live']), total_ag2 if total_ag2 > 0 else total_apps),
            ("Committed", len(ag2[ag2['P_Status'] == 'Committed']), total_ag2 if total_ag2 > 0 else total_apps),
            ("Portal Cancelled", len(ag2[ag2['P_Status'] == 'Cancelled']), total_ag2 if total_ag2 > 0 else total_apps),
            ("Portal Others", len(ag2[ag2['P_Status'] == 'Others']), total_ag2 if total_ag2 > 0 else total_apps)
        ]

        # Render Layout
        b1, b2, b3, b4 = st.columns([1.2, 2.5, 2.5, 2.2])
        
        with b1: # Box 1: Total Apps
            st.markdown('<div class="kpi-box"><p class="box-label">Total Apps</p>', unsafe_allow_html=True)
            render_kpi(group_1[0][0], group_1[0][1], group_1[0][2])
            st.markdown('</div>', unsafe_allow_html=True)

        with b2: # Box 2: Quality Cards
            active_g2 = [k for k in group_2 if k[1] > 0]
            if active_g2:
                st.markdown('<div class="kpi-box"><p class="box-label">Quality Status</p>', unsafe_allow_html=True)
                cols = st.columns(len(active_g2))
                for i, kpi in enumerate(active_g2):
                    with cols[i]: render_kpi(kpi[0], kpi[1], kpi[2])
                st.markdown('</div>', unsafe_allow_html=True)

        with b3: # Box 3: Welcome Call Cards
            active_g3 = [k for k in group_3 if k[1] > 0]
            if active_g3:
                st.markdown('<div class="kpi-box"><p class="box-label">Welcome Call Status</p>', unsafe_allow_html=True)
                cols = st.columns(len(active_g3))
                for i, kpi in enumerate(active_g3):
                    with cols[i]: render_kpi(kpi[0], kpi[1], kpi[2])
                st.markdown('</div>', unsafe_allow_html=True)

        with b4: # Box 4: Live Status Cards
            active_g4 = [k for k in group_4 if k[1] > 0]
            if active_g4:
                st.markdown('<div class="kpi-box"><p class="box-label">Live Status</p>', unsafe_allow_html=True)
                cols = st.columns(len(active_g4))
                for i, kpi in enumerate(active_g4):
                    with cols[i]: render_kpi(kpi[0], kpi[1], kpi[2])
                st.markdown('</div>', unsafe_allow_html=True)

        st.write("---")

        # ---------------- DASHBOARD CONTENT ----------------
        st.subheader("📅 Data Breakdown")
        ag1['Date'] = ag1['Date_Parsed'].dt.date
        ag2['Date'] = ag2['Date_Parsed'].dt.date
        view_mode = st.radio("View tables by:", ["Daily", "Monthly"], horizontal=True)
        
        if view_mode == "Daily":
            ag1['Period'] = ag1['Date_Parsed'].dt.date
            ag2['Period'] = ag2['Date_Parsed'].dt.date
            chart_group_col = 'Date'
        else:
            ag1['Period'] = ag1['Date_Parsed'].dt.strftime('%Y-%m')
            ag2['Period'] = ag2['Date_Parsed'].dt.strftime('%Y-%m')
            chart_group_col = 'Period'
        
        ca, cb, cc, cd = st.columns(4)
        with ca:
            st.markdown("##### Applications")
            if not ag1.empty:
                period_apps = ag1.groupby('Period').size().to_frame('Total Apps')
                vmax_apps = max(period_apps.max().max(), 1.1)
                styled_apps = period_apps.style.format(lambda x: "-" if x == 0 else x) \
                    .background_gradient(cmap='Greens', vmin=1, vmax=vmax_apps) \
                    .map(lambda x: 'background-color: transparent' if x == 0 else '')
                st.dataframe(styled_apps, use_container_width=True)

        with cb:
            st.markdown("##### Quality Audit Result")
            if not ag1.empty:
                period_qual = ag1.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
                qual_order = ['Approved', 'Rework', 'Cancelled', 'Rejected', 'Others']
                period_qual = period_qual.reindex(columns=qual_order, fill_value=0)
                period_qual = period_qual.loc[:, (period_qual != 0).any(axis=0)]
                if not period_qual.empty:
                    vmax_qual = max(period_qual.max().max(), 1.1)
                    styled_qual = period_qual.style.format(lambda x: "-" if x == 0 else x) \
                        .background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Approved'])], vmin=1, vmax=vmax_qual) \
                        .background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Rework'])], vmin=1, vmax=vmax_qual) \
                        .background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Cancelled', 'Rejected'])], vmin=1, vmax=vmax_qual) \
                        .map(lambda x: 'background-color: transparent' if x == 0 else '')
                    st.dataframe(styled_qual, use_container_width=True)

        with cc:
            st.markdown("##### Welcome Call Status")
            if wc_col and not ag1.empty:
                period_wc = ag1.groupby(['Period', 'WC_Clean']).size().unstack(fill_value=0)
                wc_order = ['Done', 'Pending', 'Paperwork', 'Cancelled', 'Others']
                period_wc = period_wc.reindex(columns=wc_order, fill_value=0)
                period_wc = period_wc.loc[:, (period_wc != 0).any(axis=0)]
                if not period_wc.empty:
                    vmax_wc = max(period_wc.max().max(), 1.1)
                    styled_wc = period_wc.style.format(lambda x: "-" if x == 0 else x) \
                        .background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Done'])], vmin=1, vmax=vmax_wc) \
                        .background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Pending', 'Paperwork'])], vmin=1, vmax=vmax_wc) \
                        .background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Cancelled'])], vmin=1, vmax=vmax_wc) \
                        .map(lambda x: 'background-color: transparent' if x == 0 else '')
                    st.dataframe(styled_wc, use_container_width=True)
            else:
                st.info("No Welcome Call data.")
                
        with cd:
            st.markdown("##### Live Status")
            if not ag2.empty:
                period_port = ag2.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
                port_order = ['Live', 'Committed', 'Cancelled', 'Others']
                period_port = period_port.reindex(columns=port_order, fill_value=0)
                period_port = period_port.loc[:, (period_port != 0).any(axis=0)]
                if not period_port.empty:
                    vmax_port = max(period_port.max().max(), 1.1)
                    styled_port = period_port.style.format(lambda x: "-" if x == 0 else x) \
                        .background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_port.columns.intersection(['Live'])], vmin=1, vmax=vmax_port) \
                        .background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_port.columns.intersection(['Committed'])], vmin=1, vmax=vmax_port) \
                        .background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_port.columns.intersection(['Cancelled'])], vmin=1, vmax=vmax_port) \
                        .map(lambda x: 'background-color: transparent' if x == 0 else '')
                    st.dataframe(styled_port, use_container_width=True)

        st.subheader("📈 My Trend")
        if not ag1.empty:
            d_apps = ag1.groupby(chart_group_col).size().to_frame('Total Apps')
            d_appr = ag1[ag1['Q_Status'] == 'Approved'].groupby(chart_group_col).size().to_frame('Approved')
            d_live = ag2[ag2['P_Status'] == 'Live'].groupby(chart_group_col).size().to_frame('Live')
            i_comb = d_apps.join([d_appr, d_live], how='left').fillna(0).reset_index()
            i_comb[chart_group_col] = i_comb[chart_group_col].astype(str)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=i_comb[chart_group_col], y=i_comb['Total Apps'], name="Total Applications", marker_color='#60A5FA'))
            fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Approved'], name="Quality Approved Applications", line=dict(color='#059669', width=3)))
            fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Live'], name="Live Applications", line=dict(color='#F59E0B', width=3)))
            fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0), xaxis_title="Date" if view_mode=="Daily" else "Month")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("🔍 Recent Applications Log")
        if not ag1.empty:
            display_cols = ['Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks', 'Quality Call Remarks', 'Status', 'Welcome call Remarks']
            recent_log = ag1.sort_values(by='Date_Parsed', ascending=False).head(20)
            actual_cols = [c for c in display_cols if c in ag1.columns]
            
            def style_log_row(row):
                styles = [''] * len(row)
                q_color = ''
                q_val = str(row.get('Quality Status', '')).lower()
                if any(x in q_val for x in ['appr', 'pass']): q_color = 'background-color: rgba(167, 243, 208, 0.3)'
                elif any(x in q_val for x in ['rew', 'repro']): q_color = 'background-color: rgba(253, 230, 138, 0.3)'
                elif any(x in q_val for x in ['can', 'rej']): q_color = 'background-color: rgba(254, 202, 202, 0.3)'

                wc_color = ''
                wc_val = str(row.get('Status', '')).lower()
                if any(x in wc_val for x in ['done', 'pass', 'comp', 'live']): wc_color = 'background-color: rgba(167, 243, 208, 0.3)'
                elif any(x in wc_val for x in ['pend', 'pnd', 'paper', 'ppw', 'com']): wc_color = 'background-color: rgba(253, 230, 138, 0.3)'
                elif any(x in wc_val for x in ['can', 'rej']): wc_color = 'background-color: rgba(254, 202, 202, 0.3)'

                quality_cols = ['Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks', 'Quality Call Remarks']
                for i, col in enumerate(row.index):
                    if col in quality_cols: styles[i] = q_color
                    else: styles[i] = wc_color
                return styles
            
            styled_log = recent_log[actual_cols].style.apply(style_log_row, axis=1)
            st.dataframe(styled_log, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error: {e}")
