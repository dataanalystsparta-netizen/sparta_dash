import streamlit as st
import pd as pd
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px
import plotly.graph_objects as go 
import calendar

st.set_page_config(page_title="Sparta Agent Portal", layout="wide")

# --- IMPROVED UI SECTION ---
st.markdown("""
    <style>
    .block-container { max-width: 98%; padding-top: 1.5rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.1rem !important; color: #1E3A8A; }
    h5 { font-size: 0.9rem !important; font-weight: 700; color: #475569; margin-bottom: 10px !important; }
    .last-updated { font-size: 0.75rem; color: gray; text-align: right; }
    
    /* Modern Scrollbar */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #f1f1f1; }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }

    /* Improved Box Container */
    .kpi-box {
        background-color: #F1F5F9; 
        padding: 15px;
        border-radius: 12px; 
        border: 1px solid #E2E8F0; 
        height: 100%;
        box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05);
    }
    
    /* Table Container Styling */
    .table-container {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }

    .box-label {
        font-size: 0.75rem;
        font-weight: 800;
        color: #475569;
        text-align: left;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: flex;
        align-items: center;
    }
    .box-label::before {
        content: "";
        display: inline-block;
        width: 4px;
        height: 12px;
        background: #1E3A8A;
        margin-right: 8px;
        border-radius: 2px;
    }

    /* KPI Card */
    .kpi-card {
        padding: 12px 5px;
        border-radius: 10px;
        text-align: center;
        background: white;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        min-height: 85px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    .kpi-label { font-size: 0.65rem; color: #64748B; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; }
    .kpi-value { font-size: 1.2rem; color: #0F172A; font-weight: 800; margin: 0; line-height: 1; }
    .kpi-pc { 
        font-size: 0.7rem; color: #1E3A8A; font-weight: 700; margin-top: 4px;
        background: rgba(30, 58, 138, 0.1); display: inline-block; padding: 2px 6px; border-radius: 4px;
    }

    /* Insight Flags */
    .insight-container { display: flex; gap: 12px; overflow-x: auto; padding: 10px 5px 20px 5px; }
    .insight-card {
        background: #FFFFFF;
        border-left: 5px solid #1E3A8A;
        padding: 12px 16px;
        min-width: 220px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .insight-title { font-size: 0.7rem; font-weight: 800; color: #64748B; margin: 0; text-transform: uppercase; }
    .insight-phrase { font-size: 0.9rem; font-weight: 700; color: #1E3A8A; margin: 4px 0; }
    .insight-comment { font-size: 0.75rem; color: #475569; margin: 0; line-height: 1.3; }
    
    /* Target Streamlit Dataframe to add rounded corners */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #E2E8F0;
    }
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
    accent = "#94A3B8" 
    if "total" in lbl: accent = "#3B82F6"
    elif any(x in lbl for x in ["appr", "done", "live"]): accent = "#10B981"
    elif any(x in lbl for x in ["rew", "pend", "paper", "comm"]): accent = "#F59E0B"
    elif "can" in lbl or "rej" in lbl: accent = "#EF4444"
    
    percent = (value / total * 100) if total > 0 else 0
    pc_html = f'<div style="display:flex; justify-content:center;"><p class="kpi-pc">{percent:.1f}%</p></div>' if "total apps" not in lbl else ""
    
    st.markdown(f"""
        <div class="kpi-card" style="border-top: 4px solid {accent};">
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

        # ---------------- KPI BOXES ----------------
        total_apps = len(ag1_filtered)
        total_ag2 = len(ag2_filtered)
        
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
                ("WC Done", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done']), total_apps),
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
            st.markdown('<div class="kpi-box"><p class="box-label">Overview</p>', unsafe_allow_html=True)
            render_kpi(group_1[0][0], group_1[0][1], group_1[0][2])
            st.markdown('</div>', unsafe_allow_html=True)
        with b2: 
            active_g2 = [k for k in group_2 if k[1] > 0]
            if active_g2:
                st.markdown('<div class="kpi-box"><p class="box-label">Quality Audit Status</p>', unsafe_allow_html=True)
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

        # ---------------- INSIGHT FLAGS ----------------
        flags_html = ""
        if total_apps > 0:
            q_appr = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']) / total_apps
            q_can = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled']) / total_apps
            q_rej = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rejected']) / total_apps
            q_rew = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']) / total_apps

            if q_appr > 0.60: flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Quality</p><p class="insight-phrase">High Approval Rate</p><p class="insight-comment">Excellent pitch and quality compliance!</p></div>'
            elif q_appr < 0.60: flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality</p><p class="insight-phrase">Low Approval Rate</p><p class="insight-comment">Review quality guidelines to increase approval!</p></div>'
            if q_can > 0.40: flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Quality</p><p class="insight-phrase">High Cancellation</p><p class="insight-comment">High cancellations detected!</p></div>'
            if q_rej > 0.20: flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality</p><p class="insight-phrase">High Rejection</p><p class="insight-comment">Pay attention to rejection flags!</p></div>'

        if flags_html:
            st.write("")
            st.subheader("💡 Points to Look Out For")
            st.markdown(f'<div class="insight-container">{flags_html}</div>', unsafe_allow_html=True)

        st.write("---")

        # ---------------- DATA BREAKDOWN TABLES ----------------
        st.subheader("📅 Data Breakdown")
        ag1_filtered['Date'] = ag1_filtered['Date_Parsed'].dt.date
        ag2_filtered['Date'] = ag2_filtered['Date_Parsed'].dt.date
        view_mode = st.radio("View tables by:", ["Daily", "Monthly"], horizontal=True)
        
        if view_mode == "Daily":
            ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.date
            ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.date
            chart_group_col = 'Date'
        else:
            ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.strftime('%Y-%m')
            ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.strftime('%Y-%m')
            chart_group_col = 'Period'
        
        ca, cb, cc, cd = st.columns(4)
        
        # Styles for the mini-tables
        def get_styled_table(df, col_name, color):
            vmax = max(df.max().max(), 1.1)
            return df.style.format(lambda x: "-" if x == 0 else x)\
                .background_gradient(cmap=color, vmin=1, vmax=vmax)\
                .map(lambda x: 'background-color: transparent; color: #94A3B8;' if x == 0 else 'font-weight: bold;')

        with ca:
            st.markdown("##### Applications")
            if not ag1_filtered.empty:
                period_apps = ag1_filtered.groupby('Period').size().to_frame('Total Apps')
                st.markdown('<div class="table-container">', unsafe_allow_html=True)
                st.dataframe(get_styled_table(period_apps, 'Total Apps', 'Greens'), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        with cb:
            st.markdown("##### Quality Audit")
            if not ag1_filtered.empty:
                period_qual = ag1_filtered.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
                period_qual = period_qual.reindex(columns=['Approved', 'Rework', 'Cancelled', 'Rejected', 'Others'], fill_value=0)
                period_qual = period_qual.loc[:, (period_qual != 0).any(axis=0)]
                st.markdown('<div class="table-container">', unsafe_allow_html=True)
                st.dataframe(get_styled_table(period_qual, '', 'Blues'), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        with cc:
            st.markdown("##### Welcome Call")
            if wc_col and not ag1_filtered.empty:
                period_wc = ag1_filtered.groupby(['Period', 'WC_Clean']).size().unstack(fill_value=0)
                period_wc = period_wc.reindex(columns=['Done', 'Pending', 'Paperwork', 'Cancelled', 'Others'], fill_value=0)
                period_wc = period_wc.loc[:, (period_wc != 0).any(axis=0)]
                st.markdown('<div class="table-container">', unsafe_allow_html=True)
                st.dataframe(get_styled_table(period_wc, '', 'Purples'), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        with cd:
            st.markdown("##### Live Status")
            if not ag2_filtered.empty:
                period_port = ag2_filtered.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
                period_port = period_port.reindex(columns=['Live', 'Committed', 'Cancelled', 'Others'], fill_value=0)
                period_port = period_port.loc[:, (period_port != 0).any(axis=0)]
                st.markdown('<div class="table-container">', unsafe_allow_html=True)
                st.dataframe(get_styled_table(period_port, '', 'YlOrBr'), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

        st.write("---")
        
        # ---------------- TRENDS & CALENDAR ----------------
        col_trend, col_cal = st.columns([3, 2])
        with col_trend:
            st.subheader("📈 My Trend")
            if not ag1_filtered.empty:
                d_apps = ag1_filtered.groupby(chart_group_col).size().to_frame('Total Apps')
                d_appr = ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'].groupby(chart_group_col).size().to_frame('Approved')
                d_live = ag2_filtered[ag2_filtered['P_Status'] == 'Live'].groupby(chart_group_col).size().to_frame('Live')
                i_comb = d_apps.join([d_appr, d_live], how='left').fillna(0).reset_index()
                i_comb[chart_group_col] = i_comb[chart_group_col].astype(str)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=i_comb[chart_group_col], y=i_comb['Total Apps'], name="Total Applications", marker_color='#60A5FA', opacity=0.7))
                fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Approved'], name="Quality Approved", line=dict(color='#059669', width=3), mode='lines+markers'))
                fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Live'], name="Live", line=dict(color='#F59E0B', width=3), mode='lines+markers'))
                fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

        with col_cal:
            st.subheader("🗓️ Sales Activity Calendar")
            def is_holiday(dt):
                wd = dt.weekday()
                if wd == 6: return True 
                if wd == 5: 
                    week_num = (dt.day - 1) // 7 + 1
                    return week_num in [1, 3, 5] 
                return False

            c_month_col, c_year_col = st.columns(2)
            sel_month = c_month_col.selectbox("Month", list(calendar.month_name)[1:], index=today_date.month-1)
            sel_year = c_year_col.selectbox("Year", [2025, 2026], index=1)
            
            m_idx = list(calendar.month_name).index(sel_month)
            num_days = calendar.monthrange(sel_year, m_idx)[1]
            dates = [datetime.date(sel_year, m_idx, day) for day in range(1, num_days+1)]
            daily_sales = ag1.groupby(ag1['Date_Parsed'].dt.date).size()
            cal_df = pd.DataFrame({
                'Date': dates, 'Day': [d.day for d in dates],
                'Weekday': [d.strftime('%a') for d in dates],
                'WeekNum': [int(d.strftime('%V')) if d.strftime('%V').isdigit() else 0 for d in dates],
                'Sales': [daily_sales.get(d, 0) for d in dates],
                'Type': ['Holiday' if is_holiday(d) else 'Working' for d in dates]
            })

            fig_cal = go.Figure()
            working_days = cal_df[cal_df['Type'] == 'Working']
            fig_cal.add_trace(go.Heatmap(
                x=working_days['Weekday'], y=working_days['WeekNum'], z=working_days['Sales'],
                text=working_days['Day'], customdata=working_days['Sales'],
                hovertemplate="Day %{text}: %{customdata} Sales<extra></extra>",
                texttemplate="%{text}", colorscale=[[0, 'white'], [0.1, '#d1fae5'], [1, '#047857']],
                showscale=False, xgap=3, ygap=3
            ))
            holidays = cal_df[cal_df['Type'] == 'Holiday']
            fig_cal.add_trace(go.Scatter(
                x=holidays['Weekday'], y=holidays['WeekNum'], mode='markers+text',
                marker=dict(symbol='square', size=30, color='#F1F5F9'),
                text=holidays['Day'], textfont=dict(color='#94A3B8'), showlegend=False
            ))
            fig_cal.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=10),
                xaxis=dict(side="top", categoryorder='array', categoryarray=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
                yaxis=dict(autorange="reversed", showgrid=False, showticklabels=False), plot_bgcolor='white')
            st.plotly_chart(fig_cal, use_container_width=True)

        st.write("---")

        # ---------------- RECENT LOG ----------------
        st.subheader("🔍 Recent Applications Log")
        if not ag1_filtered.empty:
            display_cols = ['Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks', 'Status', 'Welcome call Remarks']
            recent_log = ag1_filtered.sort_values(by='Date_Parsed', ascending=False).head(20)
            actual_cols = [c for c in display_cols if c in ag1_filtered.columns]
            
            def style_log_row(row):
                q_val = str(row.get('Quality Status', '')).lower()
                wc_val = str(row.get('Status', '')).lower()
                
                # Dynamic Colors for Status
                q_bg = 'background-color: #ecfdf5;' if any(x in q_val for x in ['appr', 'pass']) else \
                       'background-color: #fffbeb;' if any(x in q_val for x in ['rew', 'repro']) else \
                       'background-color: #fef2f2;' if any(x in q_val for x in ['can', 'rej']) else ''
                
                wc_bg = 'background-color: #f0f9ff;' if any(x in wc_val for x in ['done', 'pass', 'live']) else ''
                
                styles = []
                for col in row.index:
                    if col in ['Quality Status', 'Quality Remarks']: styles.append(q_bg)
                    elif col in ['Status', 'Welcome call Remarks']: styles.append(wc_bg)
                    else: styles.append('')
                return styles
            
            st.markdown('<div class="table-container">', unsafe_allow_html=True)
            styled_log = recent_log[actual_cols].style.apply(style_log_row, axis=1)
            st.dataframe(styled_log, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e: st.error(f"Error: {e}")
