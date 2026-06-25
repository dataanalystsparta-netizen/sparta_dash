import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px
import plotly.graph_objects as go 
import calendar
import math

# ==========================================
# 1. GLOBAL PREMIUM THEMING & CONFIGURATION
# ==========================================
st.set_page_config(page_title="Sparta Analytics", layout="wide", initial_sidebar_state="expanded")

# Injecting an ultra-modern corporate design system
st.markdown("""
    <style>
    /* Global Canvas Styling */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #0F172A; /* Slate 900 Deep Dark */
        color: #F1F5F9;
    }
    
    .block-container { 
        max-width: 95%; 
        padding: 2rem 2rem; 
    }
    
    /* Sidebar Overhaul */
    [data-testid="stSidebar"] {
        background-color: #1E293B !important; /* Slate 800 */
        border-right: 1px solid #334155;
    }
    
    /* Glassmorphic Metric Containers */
    .kpi-container-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        height: 100%;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    }
    
    .kpi-section-title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Elegant Metric Cards */
    .metric-pill {
        background: #1E293B;
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        box-shadow: inset 0 1px 0 0 rgba(255,255,255,0.05);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .metric-pill:hover {
        border-color: #3B82F6;
        transform: translateY(-2px);
        box-shadow: 0 12px 20px -8px rgba(59, 130, 246, 0.4);
    }
    
    .metric-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    
    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1.1;
    }
    
    .metric-percentage {
        font-size: 0.75rem;
        font-weight: 700;
        margin-top: 6px;
        display: inline-block;
        padding: 2px 8px;
        border-radius: 20px;
    }
    
    /* Live Status Highlight Board */
    .insight-scroll-board {
        display: flex;
        gap: 16px;
        overflow-x: auto;
        padding: 8px 0px 16px 0px;
    }
    
    .insight-status-node {
        background: #1E293B;
        border-top: 4px solid #3B82F6;
        border-radius: 12px;
        padding: 16px;
        min-width: 280px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    /* Modernized Tips Callout */
    .compliance-tips-panel {
        background: linear-gradient(180deg, #1E1B4B 0%, #0F172A 100%); /* Deep Indigo Blend */
        border-left: 5px solid #6366F1;
        border-right: 1px solid #312E81;
        border-top: 1px solid #312E81;
        border-bottom: 1px solid #312E81;
        padding: 24px;
        border-radius: 12px;
        margin-top: 24px;
    }
    
    .compliance-title {
        font-size: 1rem;
        font-weight: 700;
        color: #E0E7FF;
        margin-bottom: 12px;
        letter-spacing: 0.5px;
    }
    
    /* Streamlit Object Modifiers */
    div[data-testid="stContainer"] {
        background-color: #1E293B;
        border: 1px solid #334155 !important;
        border-radius: 12px;
    }
    
    .stRadio[data-testid="stWidgetPropagate"] label {
        color: #94A3B8 !important;
    }
    </style>
""", unsafe_allow_html=True)

ACCESS_KEYS = st.secrets["agent_keys"]

# ==========================================
# 2. DATA INGESTION & PIPELINE LOGIC
# ==========================================
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

def robust_date_parser(date_str):
    date_str = str(date_str).strip()
    try:
        if '/' in date_str: return pd.to_datetime(date_str, dayfirst=True)
        return pd.to_datetime(date_str)
    except: return pd.NaT

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
    
    df2_raw = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2_raw['Date_Parsed'] = df2_raw['Sale Date'].apply(robust_date_parser)
    df2_raw['Advisor'] = df2_raw['Agent'].astype(str).str.strip().str.title()

    try:
        meta = ss.worksheet('Meta').get_all_values()
        last_sync = meta[0][1]
    except:
        last_sync = "Unknown"
        
    return df1, df2_raw, last_sync

# Data Normalization Transformers
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

# Unified Micro-Metric Rendering Engine
def render_modern_pill(label, value, total, is_total=False):
    percent = (value / total * 100) if total > 0 else 0
    
    if is_total:
        color_class = "background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3);"
        pct_html = ""
    elif label in ["Approved", "WC Done", "Live"]:
        color_class = "background: rgba(16, 185, 129, 0.12); color: #34D399;"
        pct_html = f'<span class="metric-percentage" style="{color_class}">{percent:.1f}%</span>'
    elif label in ["Rework", "WC Pending", "WC Paperwork", "Committed"]:
        color_class = "background: rgba(245, 158, 11, 0.12); color: #FBBF24;"
        pct_html = f'<span class="metric-percentage" style="{color_class}">{percent:.1f}%</span>'
    else:
        color_class = "background: rgba(239, 68, 68, 0.12); color: #F87171;"
        pct_html = f'<span class="metric-percentage" style="{color_class}">{percent:.1f}%</span>'

    st.markdown(f"""
        <div class="metric-pill">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value:,}</div>
            {pct_html}
        </div>
    """, unsafe_allow_html=True)

# Session States Initialize
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.agent_name = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = 1

# ==========================================
# 3. GATEKEEPER / AUTH SCREEN
# ==========================================
if not st.session_state.authenticated:
    _, col2, _ = st.columns([1, 1.4, 1])
    with col2:
        st.write("")
        st.write("")
        with st.container():
            st.markdown("<div style='padding: 30px;'>", unsafe_allow_html=True)
            st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-telecom-squarelogo-1663578233108%20(1).jpg", width=60)
            st.markdown("<h2 style='color:white; margin-top:15px; font-weight:800;'>Sparta Engine</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:#94A3B8; font-size:0.9rem;'>Enterprise Performance Ecosystem</p>", unsafe_allow_html=True)
            st.write("")
            
            user_key = st.text_input("Security Access Key", type="password")
            st.write("")
            if st.button("Unlock Dashboard Workspace", use_container_width=True, type="primary"):
                if user_key.upper() in ACCESS_KEYS:
                    st.session_state.authenticated = True
                    st.session_state.agent_name = ACCESS_KEYS[user_key.upper()]
                    log_agent_login(ACCESS_KEYS[user_key.upper()])
                    st.rerun()
                else:
                    st.error("Access Key validation failed.")
            st.markdown("</div>", unsafe_allow_html=True)
else:
    # ==========================================
    # 4. EXECUTIVE DASHBOARD WORKSPACE
    # ==========================================
    agent = st.session_state.agent_name
    today_date = datetime.date.today()
    
    with st.sidebar:
        st.markdown(f"<div style='padding: 10px 0px;'><h3 style='color:white; font-weight:700; margin:0;'>{agent}</h3>"
                    f"<p style='color:#64748B; font-size:0.8rem; margin:0;'>Account Executive</p></div>", unsafe_allow_html=True)
        st.divider()
        if st.button("Terminate Session", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            st.session_state.agent_name = ""
            st.session_state.current_page = 1
            st.rerun()

    try:
        df1, df2_raw, last_sync = fetch_data()
        ag1 = df1[df1['Advisor'] == agent].copy()
        ag2 = df2_raw[df2_raw['Advisor'] == agent].copy()
        
        # Header Status Bar Layout
        col_title, col_time = st.columns([3, 1])
        with col_title:
            st.markdown(f"<h1 style='font-weight: 800; letter-spacing: -1px; color: white; margin:0;'>Performance Analytics</h1>"
                        f"<p style='color: #64748B; margin: 0;'>Operational tracking matrix for {agent}</p>", unsafe_allow_html=True)
        with col_time:
            st.markdown(f"<div style='text-align: right; background: #1E293B; border: 1px solid #334155; padding: 8px 16px; border-radius: 8px;'>"
                        f"<span style='color: #64748B; font-size: 0.75rem; block-display: true;'>LIVE HUB ENGINE SYNC</span><br>"
                        f"<b style='color: #34D399; font-size: 0.85rem;'>{last_sync}</b></div>", unsafe_allow_html=True)
        
        st.write("")
        
        # Dynamic Time Windows Filter Card
        with st.container():
            c_a, c_b, _ = st.columns([1.2, 1.2, 2.6])
            start_date = c_a.date_input("Performance window start", today_date.replace(day=1))
            end_date = c_b.date_input("Performance window end", today_date)

        ag1_filtered = ag1[(ag1['Date_Parsed'].dt.date >= start_date) & (ag1['Date_Parsed'].dt.date <= end_date)].copy()
        ag2_filtered = ag2[(ag2['Date_Parsed'].dt.date >= start_date) & (ag2['Date_Parsed'].dt.date <= end_date)].copy()
        
        ag1_filtered['Q_Status'] = ag1_filtered['Quality Status'].apply(map_quality)
        ag2_filtered['P_Status'] = ag2_filtered['Status'].apply(map_portal)
        wc_col = 'Status' if 'Status' in ag1_filtered.columns else 'Welcome call Status' if 'Welcome call Status' in ag1_filtered.columns else None
        if wc_col: 
            ag1_filtered['WC_Clean'] = ag1_filtered[wc_col].apply(map_wc)

        # ---------------- COMPACT CONSOLIDATED KPI DASHBOARD ----------------
        total_apps = len(ag1_filtered)
        total_ag2 = len(ag2_filtered)
        
        st.write("")
        
        # Four Tier Executive Metrics Wall
        m_col1, m_col2, m_col3, m_col4 = st.columns([1.1, 2.3, 2.3, 2.3])
        
        with m_col1:
            st.markdown('<div class="kpi-container-card"><div class="kpi-section-title">📊 Overview</div>', unsafe_allow_html=True)
            render_modern_pill("Total Apps", total_apps, total_apps, is_total=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with m_col2:
            st.markdown('<div class="kpi-container-card"><div class="kpi-section-title">🛡️ QA Audit</div>', unsafe_allow_html=True)
            q_metrics = [("Approved", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'])),
                         ("Rework", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework'])),
                         ("Cancelled", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled'] or ag1_filtered[ag1_filtered['Q_Status'] == 'Rejected']))]
            q_cols = st.columns(3)
            for i, (lbl, val) in enumerate(q_metrics):
                with q_cols[i]: render_modern_pill(lbl, val, total_apps)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with m_col3:
            st.markdown('<div class="kpi-container-card"><div class="kpi-section-title">📞 Welcome Call</div>', unsafe_allow_html=True)
            if wc_col:
                wc_metrics = [("WC Done", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done'])),
                              ("WC Pending", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Pending'])),
                              ("WC Cancel", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Cancelled']))]
                wc_cols = st.columns(3)
                for i, (lbl, val) in enumerate(wc_metrics):
                    with wc_cols[i]: render_modern_pill(lbl, val, total_apps)
            else:
                st.caption("No fields present")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with m_col4:
            st.markdown('<div class="kpi-container-card"><div class="kpi-section-title">⚡ Gateway Status</div>', unsafe_allow_html=True)
            l_denom = total_ag2 if total_ag2 > 0 else total_apps
            l_metrics = [("Live", len(ag2_filtered[ag2_filtered['P_Status'] == 'Live'])),
                         ("Committed", len(ag2_filtered[ag2_filtered['P_Status'] == 'Committed'])),
                         ("Cancelled", len(ag2_filtered[ag2_filtered['P_Status'] == 'Cancelled']))]
            l_cols = st.columns(3)
            for i, (lbl, val) in enumerate(l_metrics):
                with l_cols[i]: render_modern_pill(lbl, val, l_denom)
            st.markdown('</div>', unsafe_allow_html=True)

        # ---------------- STRATEGIC SYSTEM HIGHLIGHT NODES ----------------
        flags_html = ""
        if total_apps > 0:
            q_appr = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']) / total_apps
            q_can = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled']) / total_apps
            q_rew = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']) / total_apps

            if q_appr > 0.60: flags_html += '<div class="insight-status-node" style="border-color:#10B981;"><p class="metric-label">Quality Core</p><p style="color:#10B981; font-weight:700; margin:4px 0;">Premium Approval Margin</p><p style="color:#94A3B8; font-size:0.75rem; margin:0;">Compliance velocity tracking well above targets.</p></div>'
            elif q_appr < 0.60: flags_html += '<div class="insight-status-node" style="border-color:#EF4444;"><p class="metric-label">Quality Core</p><p style="color:#EF4444; font-weight:700; margin:4px 0;">Velocity Deficit</p><p style="color:#94A3B8; font-size:0.75rem; margin:0;">Review quality checkpoints to reduce script drops.</p></div>'
            if q_can > 0.35: flags_html += '<div class="insight-status-node" style="border-color:#F59E0B;"><p class="metric-label">Auditing</p><p style="color:#F59E0B; font-weight:700; margin:4px 0;">High Cancellation Outliers</p><p style="color:#94A3B8; font-size:0.75rem; margin:0;">Monitor post-call stabilization parameters closely.</p></div>'
            if q_rew > 0.30: flags_html += '<div class="insight-status-node" style="border-color:#3B82F6;"><p class="metric-label">Process Tracking</p><p style="color:#3B82F6; font-weight:700; margin:4px 0;">Rework Pipeline Spikes</p><p style="color:#94A3B8; font-size:0.75rem; margin:0;">Ensure secondary validation keys are populated cleanly.</p></div>'

        if flags_html:
            st.write("")
            st.markdown("<h3 style='color:white; font-size:1rem !important; font-weight:700;'>🎯 Real-Time Insight Targets</h3>", unsafe_allow_html=True)
            st.markdown(f'<div class="insight-scroll-board">{flags_html}</div>', unsafe_allow_html=True)

        # ---------------- MATRIC HISTORICAL MATRIX MATRICES ----------------
        st.write("")
        st.markdown("<h3 style='color:white; font-size:1.1rem !important; font-weight:700; margin-bottom:15px;'>📅 Data Distribution Grids</h3>", unsafe_allow_html=True)
        
        ag1_filtered['Date'] = ag1_filtered['Date_Parsed'].dt.date
        ag2_filtered['Date'] = ag2_filtered['Date_Parsed'].dt.date
        view_mode = st.radio("Group Aggregations By:", ["Daily Lineup", "Monthly Rollup"], horizontal=True, key="view_mode_layout")
        
        if view_mode == "Daily Lineup":
            ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.date
            ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.date
            chart_group_col = 'Date'
        else:
            ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.strftime('%Y-%m')
            ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.strftime('%Y-%m')
            chart_group_col = 'Period'
        
        grid_css = "color-scheme: dark; border: 1px solid #334155; border-radius: 8px;"
        
        ca, cb, cc, cd = st.columns(4)
        with ca:
            st.markdown("<p style='color:#94A3B8; font-size:0.8rem; font-weight:600;'>VOLUME MATRIX</p>", unsafe_allow_html=True)
            if not ag1_filtered.empty:
                period_apps = ag1_filtered.groupby('Period').size().to_frame('Total Apps')
                st.dataframe(period_apps.style.background_gradient(cmap='Blues'), use_container_width=True)
        with cb:
            st.markdown("<p style='color:#94A3B8; font-size:0.8rem; font-weight:600;'>QUALITY AUDIT EVALS</p>", unsafe_allow_html=True)
            if not ag1_filtered.empty:
                period_qual = ag1_filtered.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
                period_qual = period_qual.reindex(columns=['Approved', 'Rework', 'Cancelled', 'Rejected'], fill_value=0)
                st.dataframe(period_qual.style.background_gradient(cmap='Purples'), use_container_width=True)
        with cc:
            st.markdown("<p style='color:#94A3B8; font-size:0.8rem; font-weight:600;'>WELCOME CALL ENGINE</p>", unsafe_allow_html=True)
            if wc_col and not ag1_filtered.empty:
                period_wc = ag1_filtered.groupby(['Period', 'WC_Clean']).size().unstack(fill_value=0)
                period_wc = period_wc.reindex(columns=['Done', 'Pending', 'Paperwork', 'Cancelled'], fill_value=0)
                st.dataframe(period_wc.style.background_gradient(cmap='Teal'), use_container_width=True)
        with cd:
            st.markdown("<p style='color:#94A3B8; font-size:0.8rem; font-weight:600;'>GATEWAY CONVERSIONS</p>", unsafe_allow_html=True)
            if not ag2_filtered.empty:
                period_port = ag2_filtered.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
                period_port = period_port.reindex(columns=['Live', 'Committed', 'Cancelled'], fill_value=0)
                st.dataframe(period_port.style.background_gradient(cmap='YlOrBr'), use_container_width=True)

        # ---------------- DARK HIGH-CONTRAST CHART PLOTS ----------------
        st.write("")
        col_trend, col_cal = st.columns([3, 2])
        
        with col_trend:
            st.markdown("<h3 style='color:white; font-size:1.1rem !important; font-weight:700;'>📈 Conversion Vector Trend</h3>", unsafe_allow_html=True)
            if not ag1_filtered.empty:
                d_apps = ag1_filtered.groupby(chart_group_col).size().to_frame('Total Apps')
                d_appr = ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'].groupby(chart_group_col).size().to_frame('Approved')
                d_live = ag2_filtered[ag2_filtered['P_Status'] == 'Live'].groupby(chart_group_col).size().to_frame('Live')
                i_comb = d_apps.join([d_appr, d_live], how='left').fillna(0).reset_index()
                i_comb[chart_group_col] = i_comb[chart_group_col].astype(str)
                
                fig = go.Figure()
                fig.add_trace(go.Bar(x=i_comb[chart_group_col], y=i_comb['Total Apps'], name="Submissions", marker_color='#1E3A8A', marker_line=dict(color='#3B82F6', width=1.5)))
                fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Approved'], name="QA Passed", line=dict(color='#10B981', width=3, shape='spline')))
                fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Live'], name="Live In Portal", line=dict(color='#F59E0B', width=3, shape='spline')))
                
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    hovermode="x unified", margin=dict(l=0, r=0, t=20, b=0),
                    font=dict(color='#94A3B8'),
                    xaxis=dict(showgrid=True, gridcolor='#1E293B'),
                    yaxis=dict(showgrid=True, gridcolor='#1E293B'),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_cal:
            st.markdown("<h3 style='color:white; font-size:1.1rem !important; font-weight:700;'>🗓️ Production Velocity Radar</h3>", unsafe_allow_html=True)
            
            def is_holiday(dt):
                wd = dt.weekday()
                if wd == 6: return True 
                if wd == 5: 
                    week_num = (dt.day - 1) // 7 + 1
                    return week_num in [1, 3, 5] 
                return False

            c_month_col, c_year_col = st.columns(2)
            sel_month = c_month_col.selectbox("Month Selection", list(calendar.month_name)[1:], index=today_date.month-1)
            sel_year = c_year_col.selectbox("Year Selection", [2025, 2026], index=1)
            
            m_idx = list(calendar.month_name).index(sel_month)
            num_days = calendar.monthrange(sel_year, m_idx)[1]
            dates = [datetime.date(sel_year, m_idx, day) for day in range(1, num_days+1)]
            
            daily_sales = ag1.groupby(ag1['Date_Parsed'].dt.date).size()
            cal_df = pd.DataFrame({
                'Date': dates,
                'Day': [d.day for d in dates],
                'Weekday': [d.strftime('%a') for d in dates],
                'WeekNum': [int(d.strftime('%V')) if d.strftime('%V').isdigit() else 0 for d in dates],
                'Sales': [daily_sales.get(d, 0) for d in dates],
                'Type': ['Holiday' if is_holiday(d) else 'Working' for d in dates]
            })

            cal_df['HoverText'] = cal_df.apply(lambda r: "System Down / Holiday" if r['Type'] == 'Holiday' else f"Sales Logged: {r['Sales']}", axis=1)

            fig_cal = go.Figure()
            working_days = cal_df[cal_df['Type'] == 'Working']
            fig_cal.add_trace(go.Heatmap(
                x=working_days['Weekday'], y=working_days['WeekNum'], z=working_days['Sales'],
                text=working_days['Day'], 
                customdata=working_days['HoverText'],
                hovertemplate="%{customdata}<extra></extra>",
                texttemplate="%{text}",
                colorscale=[[0, '#1E293B'], [0.2, '#064E3B'], [1, '#10B981']],
                showscale=False, xgap=4, ygap=4
            ))

            holidays = cal_df[cal_df['Type'] == 'Holiday']
            fig_cal.add_trace(go.Scatter(
                x=holidays['Weekday'], y=holidays['WeekNum'], mode='markers+text',
                marker=dict(symbol='square', size=32, color='#334155'),
                text=holidays['Day'], 
                customdata=holidays['HoverText'],
                hovertemplate="%{customdata}<extra></extra>",
                textfont=dict(color='#64748B', size=10),
                showlegend=False
            ))

            fig_cal.update_layout(
                height=260, margin=dict(l=0, r=0, t=10, b=10),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(side="top", categoryorder='array', categoryarray=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], showgrid=False),
                yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, showticklabels=False),
            )
            st.plotly_chart(fig_cal, use_container_width=True)

        # ---------------- HIGH LEVEL AUDIT RECORD LOG LEDGER ----------------
        st.write("")
        st.markdown("<h3 style='color:white; font-size:1.1rem !important; font-weight:700;'>🔍 Records Query Inspection Ledger</h3>", unsafe_allow_html=True)
        
        if not ag1.empty:
            ag2_clean = ag2.copy()
            ag2_clean['Telephone No.'] = ag2_clean['Telephone No.'].astype(str).str.strip()
            ag2_clean = ag2_clean.rename(columns={'Status': 'Portal Status', 'Committed Date': 'Live Date'})
            ag2_unique = ag2_clean.sort_values('Date_Parsed').drop_duplicates('Telephone No.', keep='last')
            
            ag1_log_base = ag1.copy()
            ag1_log_base['CLI_Key'] = ag1_log_base['CLI'].astype(str).str.strip()
            
            merged_log = ag1_log_base.merge(
                ag2_unique[['Telephone No.', 'LetterStatus', 'CallStatus', 'Comments', 'Voice of Customer', 'Cancellation Reason', 'Portal Status', 'Live Date']],
                left_on='CLI_Key', right_on='Telephone No.', how='left'
            )

            merged_log['Sale Date'] = pd.to_datetime(merged_log['Standardized_Date'], errors='coerce').dt.strftime('%d-%m-%Y').fillna('')
            merged_log['Live Date'] = pd.to_datetime(merged_log['Live Date'], errors='coerce').dt.strftime('%d-%m-%Y').fillna('')

            columns_layout = [
                ('Basic Info.', 'S.No.'), ('Basic Info.', 'Sale Date'), ('Basic Info.', 'Customer Name'),
                ('Quality Audit', 'Quality Status'), ('Quality Audit', 'Quality Remarks'),
                ('Welcome Call', 'Status'), ('Welcome Call', 'Welcome call Remarks'),
                ('Live Status', 'LetterStatus'), ('Live Status', 'CallStatus'), ('Live Status', 'Portal Status'),
                ('Live Status', 'Live Date'), ('Live Status', 'Comments'), ('Live Status', 'Voice of Customer'),
                ('Live Status', 'Cancellation Reason')
            ]
            
            with st.container():
                log_col1, log_col2, log_col3 = st.columns([2.2, 1.8, 1])
                with log_col1:
                    log_filter_type = st.radio("Active Target Window Filter:", ["Full Ledger View", "Date Window Bracket", "Calendar Month Slice"], horizontal=True, key="log_f_type")
                with log_col2:
                    if log_filter_type == "Date Window Bracket":
                        ld_col1, ld_col2 = st.columns(2)
                        log_start = ld_col1.date_input("Log Start", today_date.replace(day=1), key="ls_d")
                        log_end = ld_col2.date_input("Log End", today_date, key="le_d")
                        recent_log = merged_log[(merged_log['Date_Parsed'].dt.date >= log_start) & (merged_log['Date_Parsed'].dt.date <= log_end)].sort_values(by='Date_Parsed', ascending=False)
                    elif log_filter_type == "Calendar Month Slice":
                        unique_months = sorted(merged_log['Date_Parsed'].dt.strftime('%Y-%m').dropna().unique(), reverse=True)
                        if unique_months:
                            selected_month = st.selectbox("Select Target Month:", unique_months, key="lm_dropdown")
                            recent_log = merged_log[merged_log['Date_Parsed'].dt.strftime('%Y-%m') == selected_month].sort_values(by='Date_Parsed', ascending=False)
                        else:
                            recent_log = merged_log[0:0]
                    else:
                        recent_log = merged_log.sort_values(by='Date_Parsed', ascending=False)

                recent_log['S.No.'] = range(1, len(recent_log) + 1)

                with log_col3:
                    row_limit = st.selectbox("Records Matrix Depth:", [5, 10, 20, 50, 100, "All"], index=2, key="r_depth_sel")

            valid_layout = [item for item in columns_layout if item[1] in recent_log.columns]
            display_df = recent_log[[item[1] for item in valid_layout]].copy()
            display_df.columns = pd.MultiIndex.from_tuples(valid_layout)

            table_container = st.container()

            # Dynamic Interactive Pagination Core
            if row_limit != "All":
                limit = int(row_limit)
                total_records = len(display_df)
                total_pages = max(1, math.ceil(total_records / limit))
                if st.session_state.current_page > total_pages:
                    st.session_state.current_page = 1
                
                start_idx = (st.session_state.current_page - 1) * limit
                end_idx = min(start_idx + limit, total_records)
                display_df_page = display_df.iloc[start_idx:end_idx]
                
                if total_pages > 1:
                    st.write("")
                    p_c1, p_c2 = st.columns([1, 1])
                    p_c1.markdown(f"<p style='color:#94A3B8; font-size:0.8rem;'>Showing {start_idx + 1} to {end_idx} of {total_records} indices</p>", unsafe_allow_html=True)
                    with p_c2:
                        b_col1, b_col2, b_col3 = st.columns([2, 1, 1])
                        b_col1.markdown(f"<p style='text-align: right; color:#94A3B8; font-size:0.8rem; margin-top:6px;'>Page {st.session_state.current_page} / {total_pages}</p>", unsafe_allow_html=True)
                        if b_col2.button("Prev", disabled=(st.session_state.current_page == 1), use_container_width=True, key="p_prev_btn"):
                            st.session_state.current_page -= 1
                            st.rerun()
                        if b_col3.button("Next", disabled=(st.session_state.current_page == total_pages), use_container_width=True, key="p_nxt_btn"):
                            st.session_state.current_page += 1
                            st.rerun()
                else:
                    display_df_page = display_df
            else:
                display_df_page = display_df

            # Advanced Stylized Multi-Tier Row Coloring Matrix Engine
            def style_premium_row(row):
                styles = [''] * len(row)
                
                def get_val(col_name):
                    for col in row.index:
                        if col[1] == col_name: return str(row[col]).lower()
                    return ""

                # Sleek dark color schemes for rows
                BG_GREEN  = 'background-color: #064E3B; color: #34D399;' # Deep Emerald
                BG_AMBER  = 'background-color: #78350F; color: #FBBF24;' # Deep Amber
                BG_RED    = 'background-color: #7F1D1D; color: #F87171;' # Deep Crimson
                BG_BLUE   = 'background-color: #1E3A8A; color: #60A5FA;' # Deep Cobalt

                q_val = get_val('Quality Status')
                q_style = ''
                if any(x in q_val for x in ['appr', 'pass']): q_style = BG_GREEN
                elif any(x in q_val for x in ['rew', 'repro']): q_style = BG_AMBER
                elif any(x in q_val for x in ['can', 'rej']): q_style = BG_RED

                wc_val = get_val('Status')
                wc_style = ''
                if any(x in wc_val for x in ['done', 'pass', 'comp', 'live']): wc_style = BG_GREEN
                elif any(x in wc_val for x in ['pend', 'pnd', 'paper', 'ppw', 'com']): wc_style = BG_AMBER
                elif any(x in wc_val for x in ['can', 'rej']): wc_style = BG_RED

                c_val = get_val('CallStatus')
                c_style = ''
                if 'satisfied' in c_val: c_style = BG_GREEN
                elif any(x in c_val for x in ['pend', 'cancel']): c_style = BG_RED
                
                p_val = get_val('Portal Status')
                p_style = ''
                if 'live' in p_val: p_style = BG_GREEN
                elif 'committed' in p_val: p_style = BG_AMBER
                elif any(x in p_val for x in ['rej', 'cancel']): p_style = BG_RED

                quality_cols = ['S.No.', 'Sale Date', 'Customer Name', 'Quality Status', 'Quality Remarks']
                portal_group = ['Portal Status', 'Live Date', 'Comments', 'Voice of Customer', 'Cancellation Reason']
                
                for i, col_tuple in enumerate(row.index):
                    col = col_tuple[1] 
                    cell_css = "border-bottom: 1px solid #1E293B;"
                    
                    if col == 'LetterStatus': cell_css += BG_BLUE
                    elif col == 'CallStatus': cell_css += c_style
                    elif col in portal_group:
                        cell_css += p_style if col == 'Portal Status' else (p_style.split(';')[0] + ';') if p_style else ''
                    elif col in quality_cols:
                        cell_css += q_style if col == 'Quality Status' else (q_style.split(';')[0] + ';') if q_style else ''
                    else:
                        cell_css += wc_style if col == 'Status' else (wc_style.split(';')[0] + ';') if wc_style else ''
                    
                    # Section dividers structural borders
                    if col == 'S.No.': cell_css += 'border-left: 4px solid #3B82F6;'
                    if col in ['Customer Name', 'Quality Remarks', 'Welcome call Remarks', 'Cancellation Reason']:
                        cell_css += 'border-right: 4px solid #3B82F6;'
                    
                    styles[i] = cell_css
                return styles           
            
            styled_log = display_df_page.style.apply(style_premium_row, axis=1)
            
            with table_container:
                st.dataframe(styled_log, use_container_width=True, hide_index=True)

        # ------------ PERFORMANCE TIPS PANEL ---
        st.markdown("""
            <div class="compliance-tips-panel">
                <div class="compliance-title">💡 Operational Compliance Dispositions Protocol</div>
                <ul style="margin:0; padding-left:20px; color:#C7D2FE; font-size:0.85rem; line-height:1.6;">
                    <li><b>Answering Machines:</b> Use strictly for automated voice recordings. Do not deploy this tag if Talk Time exceeds 30 seconds.</li>
                    <li><b>Customer Hangup:</b> Primary tag for abrupt line disconnections with an active, talking user.</li>
                    <li><b>Sky TV packages/Virgin:</b> Compulsory assignment if an activation block surfaces on the Talk-Talk master portal. Do not mask as "Not Interested". Masking these preserves bad records and breaks dialer data velocity.</li>
                    <li><b>Social Alarm VOIP:</b> Critical flag to deployment if client maintains a working Careline/Lifeline/Medical tracking module.</li>
                    <li><b>Over Age:</b> Restrict configuration criteria exclusively to prospects born prior to 1940 or older than 85 years old.</li>
                    <br>
                    <li><b>⛔ Permanent Drop Pools (Will not cycle back to dialer):</b> Dementia, Family Interference/POA, Sky TV/Virgin, Over Age.</li>
                    <li><b>🔄 Volatile In-Flight Cycles (Will cycle back frequently):</b> Answering Machine, Customer Hangup, Callbacks, General Interested.</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
        st.write("---")

    except Exception as e: 
        st.error(f"Operational Pipeline Fault: {e}")
