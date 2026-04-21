import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px
import plotly.graph_objects as go 
import calendar

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
       min-height: 75px;
       display: flex;
       flex-direction: column;
       justify-content: center;
   }
   .kpi-label { font-size: 0.6rem; color: #475569; font-weight: 700; margin-bottom: 2px; text-transform: uppercase; white-space: nowrap; overflow: hidden; }
   .kpi-value { font-size: 1rem; color: #1E3A8A; font-weight: 700; margin: 0; line-height: 1; }
   .kpi-pc { font-size: 0.65rem; color: #0F172A; font-weight: 600; margin-top: 1px; }

   /* NEW: Insight Flags Styling - Adjusted for vertical stacking */
   .insight-container {
       display: flex;
       flex-direction: column;
       gap: 8px;
       padding: 0px 5px;
   }
   .insight-card {
       background: #FFFFFF;
       border-left: 4px solid #1E3A8A;
       padding: 8px 12px;
       border-radius: 4px;
       box-shadow: 0 1px 3px rgba(0,0,0,0.1);
   }
   .insight-title { font-size: 0.7rem; font-weight: 800; color: #475569; margin: 0; text-transform: uppercase; }
   .insight-phrase { font-size: 0.85rem; font-weight: 700; color: #1E3A8A; margin: 2px 0; }
   .insight-comment { font-size: 0.7rem; color: #64748B; margin: 0; line-height: 1.2; }
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
    lbl = label.lower()
    bg = "#F1F5F9" # Default Gray
    if "total" in lbl: bg = "#E0F2FE" # Light Blue
    elif any(x in lbl for x in ["appr", "done", "live"]): bg = "#DCFCE7" # Light Green
    elif any(x in lbl for x in ["rew", "pend", "paper", "comm"]): bg = "#FEF9C3" # Light Yellow
    elif "can" in lbl or "rej" in lbl: bg = "#FEE2E2" # Light Red
    
    percent = (value / total * 100) if total > 0 else 0
    pc_html = f'<p class="kpi-pc">{percent:.1f}%</p>' if "total apps" not in lbl else ""
    
    st.markdown(f"""
        <div class="kpi-card" style="background-color: {bg};">
            <p class="kpi-label">{label}</p>
            <p class="kpi-value">{value:,}</p>
            {pc_html}
        </div>
    """, unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.agent_name = ""

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d503.png", width=250)
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
    today_date = datetime.date.today()
    
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
        start_date = col_a.date_input("Start Date", today_date.replace(day=1))
        end_date = col_b.date_input("End Date", today_date)

        ag1_filtered = ag1[(ag1['Date_Parsed'].dt.date >= start_date) & (ag1['Date_Parsed'].dt.date <= end_date)].copy()
        ag2_filtered = ag2[(ag2['Date_Parsed'].dt.date >= start_date) & (ag2['Date_Parsed'].dt.date <= end_date)].copy()
        
        ag1_filtered['Q_Status'] = ag1_filtered['Quality Status'].apply(map_quality)
        ag2_filtered['P_Status'] = ag2_filtered['Status'].apply(map_portal)
        wc_col = 'Status' if 'Status' in ag1_filtered.columns else 'Welcome call Status' if 'Welcome call Status' in ag1_filtered.columns else None
        if wc_col: ag1_filtered['WC_Clean'] = ag1_filtered[wc_col].apply(map_wc)

        # ---------------- PRE-CALCULATE FLAGS ----------------
        total_apps = len(ag1_filtered)
        total_ag2 = len(ag2_filtered)
        flags_html = ""
        
        if total_apps > 0:
            q_appr = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']) / total_apps
            q_can = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled']) / total_apps
            q_rej = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rejected']) / total_apps
            q_rew = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']) / total_apps

            if q_appr > 0.60: flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Quality</p><p class="insight-phrase">High Approval Rate</p><p class="insight-comment">Excellent pitch and quality compliance!</p></div>'
            elif q_appr < 0.60: flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality</p><p class="insight-phrase">Low Approval Rate</p><p class="insight-comment">Review quality guidelines!</p></div>'
            if q_can > 0.40: flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Quality</p><p class="insight-phrase">High Cancellation</p><p class="insight-comment">Review quality guidelines.</p></div>'
            if q_rej > 0.40: flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality</p><p class="insight-phrase">High Rejection</p><p class="insight-comment">Pay attention to quality guidelines!</p></div>'
            if q_rew > 0.40: flags_html += '<div class="insight-card" style="border-color:#3b82f6"><p class="insight-title">Quality</p><p class="insight-phrase">Frequent Reworks</p><p class="insight-comment">Avoid large number of quality reworks.</p></div>'

            if wc_col:
                wc_done = len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done']) / total_apps
                wc_can = len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Cancelled']) / total_apps
                if wc_done < 0.70: flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Welcome Call</p><p class="insight-phrase">Low Completion</p><p class="insight-comment">Address customer requirements closely.</p></div>'
                if wc_can > 0.15: flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Welcome Call</p><p class="insight-phrase">High WC Cancellation</p><p class="insight-comment">Address customer doubts in the sales call!</p></div>'

        if total_ag2 > 0:
            l_live = len(ag2_filtered[ag2_filtered['P_Status'] == 'Live']) / total_ag2
            l_can = len(ag2_filtered[ag2_filtered['P_Status'] == 'Cancelled']) / total_ag2
            if l_live > 0.20: flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Live Stage</p><p class="insight-phrase">Strong Conversion</p><p class="insight-comment">Great overall quality!</p></div>'
            elif l_live < 0.20: flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Live Stage</p><p class="insight-phrase">Low Live Rate</p><p class="insight-comment">Identify bottlenecks.</p></div>'
            if l_can > 0.65: flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Live Stage</p><p class="insight-phrase">High Final Loss</p><p class="insight-comment">Large drops from applications.</p></div>'

        # ---------------- LAYOUT: KPI BOXES (Left) & FLAGS (Right) ----------------
        col_main_kpi, col_insights = st.columns([0.8, 0.2])

        with col_main_kpi:
            group_1 = [("Total Apps", total_apps, total_apps)]
            group_2 = [
                ("Approved", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']), total_apps),
                ("Rework", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']), total_apps),
                ("Cancelled", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled']), total_apps),
                ("Rejected", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rejected']), total_apps),
                ("Others", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Others']), total_apps)
            ]
            group_3 = []
            if wc_col:
                group_3 = [
                    ("WC Done (Comm.)", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done']), total_apps),
                    ("WC Pending", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Pending']), total_apps),
                    ("WC Paperwork", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Paperwork']), total_apps),
                    ("WC Cancelled", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Cancelled']), total_apps),
                    ("WC Others", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Others']), total_apps)
                ]
            group_4 = [
                ("Live", len(ag2_filtered[ag2_filtered['P_Status'] == 'Live']), total_ag2 if total_ag2 > 0 else total_apps),
                ("Committed", len(ag2_filtered[ag2_filtered['P_Status'] == 'Committed']), total_ag2 if total_ag2 > 0 else total_apps),
                ("Cancelled", len(ag2_filtered[ag2_filtered['P_Status'] == 'Cancelled']), total_ag2 if total_ag2 > 0 else total_apps),
                ("Others", len(ag2_filtered[ag2_filtered['P_Status'] == 'Others']), total_ag2 if total_ag2 > 0 else total_apps)
            ]

            b1, b2, b3, b4 = st.columns([1.2, 2.5, 2.5, 2.2])
            with b1: 
                st.markdown('<div class="kpi-box"><p class="box-label">Total Apps</p>', unsafe_allow_html=True)
                render_kpi(group_1[0][0], group_1[0][1], group_1[0][2])
                st.markdown('</div>', unsafe_allow_html=True)
            with b2: 
                active_g2 = [k for k in group_2 if k[1] > 0]
                if active_g2:
                    st.markdown('<div class="kpi-box"><p class="box-label">Quality Status</p>', unsafe_allow_html=True)
                    cols = st.columns(len(active_g2))
                    for i, kpi in enumerate(active_g2):
                        with cols[i]: render_kpi(kpi[0], kpi[1], kpi[2])
                    st.markdown('</div>', unsafe_allow_html=True)
            with b3: 
                active_g3 = [k for k in group_3 if k[1] > 0]
                if active_g3:
                    st.markdown('<div class="kpi-box"><p class="box-label">Welcome Call Status</p>', unsafe_allow_html=True)
                    cols = st.columns(len(active_g3))
                    for i, kpi in enumerate(active_g3):
                        with cols[i]: render_kpi(kpi[0], kpi[1], kpi[2])
                    st.markdown('</div>', unsafe_allow_html=True)
            with b4: 
                active_g4 = [k for k in group_4 if k[1] > 0]
                if active_g4:
                    st.markdown('<div class="kpi-box"><p class="box-label">Live Status</p>', unsafe_allow_html=True)
                    cols = st.columns(len(active_g4))
                    for i, kpi in enumerate(active_g4):
                        with cols[i]: render_kpi(kpi[0], kpi[1], kpi[2])
                    st.markdown('</div>', unsafe_allow_html=True)

        with col_insights:
            if flags_html:
                st.markdown('<p style="font-size:1.1rem; font-weight:700; color:#1E3A8A; margin-bottom:10px;">💡 Points to Look Out</p>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight-container">{flags_html}</div>', unsafe_allow_html=True)

        st.write("---")

        st.subheader("🔍 Recent Applications Log")
        if not ag1_filtered.empty:
            display_cols = ['Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks', 'Quality Call Remarks', 'Status', 'Welcome call Remarks']
            recent_log = ag1_filtered.sort_values(by='Date_Parsed', ascending=False).head(20)
            actual_cols = [c for c in display_cols if c in ag1_filtered.columns]
            
            def style_log_row(row):
                styles = [''] * len(row)
                q_val = str(row.get('Quality Status', '')).lower()
                q_color = 'background-color: rgba(167, 243, 208, 0.3)' if any(x in q_val for x in ['appr', 'pass']) else 'background-color: rgba(253, 230, 138, 0.3)' if any(x in q_val for x in ['rew', 'repro']) else 'background-color: rgba(254, 202, 202, 0.3)' if any(x in q_val for x in ['can', 'rej']) else ''
                wc_val = str(row.get('Status', '')).lower()
                wc_color = 'background-color: rgba(167, 243, 208, 0.3)' if any(x in wc_val for x in ['done', 'pass', 'comp', 'live']) else 'background-color: rgba(253, 230, 138, 0.3)' if any(x in wc_val for x in ['pend', 'pnd', 'paper', 'ppw', 'com']) else 'background-color: rgba(254, 202, 202, 0.3)' if any(x in wc_val for x in ['can', 'rej']) else ''
                quality_cols = ['Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks', 'Quality Call Remarks']
                for i, col in enumerate(row.index): styles[i] = q_color if col in quality_cols else wc_color
                return styles
            
            styled_log = recent_log[actual_cols].style.apply(style_log_row, axis=1)
            st.dataframe(styled_log, use_container_width=True, hide_index=True)

    except Exception as e: st.error(f"Error: {e}")
