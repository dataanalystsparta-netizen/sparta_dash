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
   .kpi-label { font-size: 0.6rem; color: #475569; font-weight: 700; margin-bottom: 2px; text-transform: uppercase; }
   .kpi-value { font-size: 1rem; color: #1E3A8A; font-weight: 700; margin: 0; line-height: 1; }
   .kpi-pc { font-size: 0.65rem; color: #0F172A; font-weight: 600; margin-top: 1px; }
   </style>
   """, unsafe_allow_html=True)

ACCESS_KEYS = st.secrets["agent_keys"]

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
    bg = "#F1F5F9" 
    if "total" in lbl: bg = "#E0F2FE" 
    elif any(x in lbl for x in ["appr", "done", "live"]): bg = "#DCFCE7" 
    elif any(x in lbl for x in ["rew", "pend", "paper", "comm"]): bg = "#FEF9C3" 
    elif "can" in lbl or "rej" in lbl: bg = "#FEE2E2" 
    percent = (value / total * 100) if total > 0 else 0
    pc_html = f'<p class="kpi-pc">{percent:.1f}%</p>' if "total apps" not in lbl else ""
    st.markdown(f'<div class="kpi-card" style="background-color: {bg};"><p class="kpi-label">{label}</p><p class="kpi-value">{value:,}</p>{pc_html}</div>', unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.agent_name = ""

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d503.png", width=250)
        st.title("Agent Portal")
        user_key = st.text_input("Access Key", type="password")
        if st.button("Login", use_container_width=True):
            if user_key.upper() in ACCESS_KEYS:
                st.session_state.authenticated = True
                st.session_state.agent_name = ACCESS_KEYS[user_key.upper()]
                st.rerun()
            else: st.error("Invalid Key")
else:
    agent = st.session_state.agent_name
    today = datetime.date.today()
    
    try:
        df1, df2, last_sync = fetch_data()
        ag1 = df1[df1['Advisor'] == agent].copy()
        ag2 = df2[df2['Advisor'] == agent].copy()
        
        col_title, col_time = st.columns([3, 1])
        with col_title: st.title(f"Performance: {agent}")
        col_time.markdown(f"<p class='last-updated'>Sync: <b>{last_sync}</b></p>", unsafe_allow_html=True)

        st.write("---")
        
        # ---------------- CALENDAR SECTION ----------------
        st.subheader("🗓️ Sales Activity Calendar")
        
        # Determine Work Pattern
        def is_holiday(dt):
            wd = dt.weekday() # 0=Mon, 6=Sun
            if wd == 6: return True # Sunday is holiday
            if wd == 5: # Saturday check
                week_num = (dt.day - 1) // 7 + 1
                return week_num in [2, 4] # 2nd and 4th Sat are holidays
            return False

        # Build Month Data
        month_col, year_col, _ = st.columns([2, 1, 4])
        selected_month = month_col.selectbox("Month", list(calendar.month_name)[1:], index=today.month-1)
        selected_year = year_col.selectbox("Year", [2025, 2026], index=1)
        
        m_idx = list(calendar.month_name).index(selected_month)
        num_days = calendar.monthrange(selected_year, m_idx)[1]
        dates = [datetime.date(selected_year, m_idx, day) for day in range(1, num_days+1)]
        
        # Count sales per day
        daily_sales = ag1.groupby(ag1['Date_Parsed'].dt.date).size()
        
        cal_df = pd.DataFrame({
            'Date': dates,
            'Day': [d.day for d in dates],
            'Weekday': [d.strftime('%a') for d in dates],
            'WeekNum': [int(d.strftime('%V')) for d in dates],
            'Sales': [daily_sales.get(d, 0) for d in dates],
            'Type': ['Holiday' if is_holiday(d) else 'Working' for d in dates]
        })

        # Plotly Heatmap Calendar
        fig_cal = go.Figure()

        # Add Working Days
        work_days = cal_df[cal_df['Type'] == 'Working']
        fig_cal.add_trace(go.Heatmap(
            x=cal_df['Weekday'],
            y=cal_df['WeekNum'],
            z=cal_df['Sales'],
            text=cal_df['Day'],
            texttemplate="%{text}",
            hoverinfo="text+z",
            colorscale=[[0, 'white'], [0.1, '#d1fae5'], [1, '#047857']],
            showscale=False,
            xgap=3, ygap=3
        ))

        # Highlight Holidays (Overlay)
        holidays = cal_df[cal_df['Type'] == 'Holiday']
        fig_cal.add_trace(go.Scatter(
            x=holidays['Weekday'],
            y=holidays['WeekNum'],
            mode='markers+text',
            marker=dict(symbol='square', size=40, color='#E2E8F0'),
            text=holidays['Day'],
            textfont=dict(color='#94A3B8'),
            hoverinfo='skip',
            showlegend=False
        ))

        fig_cal.update_layout(
            height=350,
            margin=dict(l=0, r=0, t=10, b=10),
            xaxis=dict(side="top", categoryorder='array', categoryarray=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
            yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig_cal, use_container_width=True)
        st.caption("🟢 Green: Sales | ⚪ White: Working (No Sales) | 🔘 Gray: Holiday")

        st.write("---")

        # ---------------- ORIGINAL KPI & DATA ----------------
        col_a, col_b, _ = st.columns([1, 1, 3])
        start_date = col_a.date_input("Filter Start", today.replace(day=1))
        end_date = col_b.date_input("Filter End", today)

        ag1_f = ag1[(ag1['Date_Parsed'].dt.date >= start_date) & (ag1['Date_Parsed'].dt.date <= end_date)].copy()
        ag2_f = ag2[(ag2['Date_Parsed'].dt.date >= start_date) & (ag2['Date_Parsed'].dt.date <= end_date)].copy()
        
        ag1_f['Q_Status'] = ag1_f['Quality Status'].apply(map_quality)
        ag2_f['P_Status'] = ag2_f['Status'].apply(map_portal)
        
        b1, b2, b3 = st.columns([1, 2, 2])
        with b1:
            st.markdown('<div class="kpi-box"><p class="box-label">Apps</p>', unsafe_allow_html=True)
            render_kpi("Total Apps", len(ag1_f), len(ag1_f))
            st.markdown('</div>', unsafe_allow_html=True)
        with b2:
            st.markdown('<div class="kpi-box"><p class="box-label">Quality</p>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1: render_kpi("Approved", len(ag1_f[ag1_f['Q_Status']=='Approved']), len(ag1_f))
            with c2: render_kpi("Rejected", len(ag1_f[ag1_f['Q_Status']=='Rejected']), len(ag1_f))
            st.markdown('</div>', unsafe_allow_html=True)
        with b3:
            st.markdown('<div class="kpi-box"><p class="box-label">Live</p>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1: render_kpi("Live", len(ag2_f[ag2_f['P_Status']=='Live']), len(ag2_f))
            with c2: render_kpi("Committed", len(ag2_f[ag2_f['P_Status']=='Committed']), len(ag2_f))
            st.markdown('</div>', unsafe_allow_html=True)

        st.write("---")
        st.subheader("🔍 Detailed Log")
        st.dataframe(ag1_f[['Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks']].sort_values('Standardized_Date', ascending=False), use_container_width=True, hide_index=True)

    except Exception as e: st.error(f"Error: {e}")
