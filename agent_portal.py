import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px
import plotly.graph_objects as go 

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Agent Portal", layout="wide")

st.markdown("""
   <style>
   .block-container { max-width: 95%; padding-top: 3rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A; }
   .last-updated { font-size: 0.8rem; color: gray; text-align: right; }
   [data-testid="stMetricValue"] { font-size: 1.6rem !important; color: #1E3A8A; }
   [data-testid="stMetricLabel"] { font-size: 0.85rem !important; white-space: nowrap; }
   </style>
   """, unsafe_allow_html=True)

# --- AGENT ACCESS KEYS ---Dictionary mapping keys to exact Advisor names. 

ACCESS_KEYS = {
    "19167912": "Aman", #1
    "97631367": "Anjali",#2
    "19847913": "Anshu",#3
    "12695485": "Frogh",#4
    "17929264": "Gaurav",#5
    "19819343":"Animesh",#6
    "91981624":"Guru",#7
    "26819496":"Krrish",#8
    "76138936":"Kunal",#9
    "18638924":"Niki",#10
    "97491653":"Rani",#11
    "81986125":"Shaheen",#12
    "98168174":"Tokivi",#13
    "49836935":"Manmeet",#14
    "19843675":"Gungun",#15
    "86313569":"Prerna"
}

# --- DATA FETCHING (Same as Master, Cached for speed) ---
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

# --- SESSION STATE INITIALIZATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.agent_name = ""

# --- LOGIN SCREEN ---
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
                st.rerun()
            else:
                st.error("Invalid Key. Please contact your manager.")

# --- MAIN AGENT DASHBOARD ---
else:
    agent = st.session_state.agent_name
    
    # Sidebar Profile & Logout
    with st.sidebar:
        st.subheader(f"👤 {agent}")
        st.write("Logged in successfully.")
        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.agent_name = ""
            st.rerun()

    try:
        # 1. Fetch and IMMEDIATELY filter data for privacy
        df1, df2, last_sync = fetch_data()
        
        ag1 = df1[df1['Advisor'] == agent].copy()
        ag2 = df2[df2['Advisor'] == agent].copy()
        
        # 2. Header
        col_title, col_time = st.columns([3, 1])
        with col_title:
            st.title(f"My Performance Dashboard")
        col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

        # 3. Date Filters
        st.write("---")
        col_a, col_b, _ = st.columns([1, 1, 3])
        start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
        end_date = col_b.date_input("End Date", datetime.date.today())

        ag1 = ag1[(ag1['Date_Parsed'].dt.date >= start_date) & (ag1['Date_Parsed'].dt.date <= end_date)]
        ag2 = ag2[(ag2['Date_Parsed'].dt.date >= start_date) & (ag2['Date_Parsed'].dt.date <= end_date)]
        
        ag1['Q_Status'] = ag1['Quality Status'].apply(map_quality)
        ag2['P_Status'] = ag2['Status'].apply(map_portal)

        # 4. Top KPIs
        total_apps = len(ag1)
        approved = len(ag1[ag1['Q_Status'] == 'Approved'])
        approval_rate = f"{(approved / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
        total_committed_apps = len(ag2) 
        committed_rate = f"{(total_committed_apps / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
        live = len(ag2[ag2['P_Status'] == 'Live'])
        live_rate = f"{(live / total_committed_apps * 100):.1f}%" if total_committed_apps > 0 else "0.0%"
        
        with st.container(border=True):
            m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
            m1.metric("📝 Tot. Apps", f"{total_apps:,}")
            m2.metric("✅ Approved", f"{approved:,}")
            m3.metric("📈 Approv. Rate", approval_rate)
            m4.metric("📦 Committed", f"{total_committed_apps:,}")
            m5.metric("📋 Commit. Rate", committed_rate)
            m6.metric("🌐 Live", f"{live:,}")
            m7.metric("🚀 Live Rate", live_rate)

        # 5. Daily Breakdown Table
        st.subheader("📅 Daily Breakdown")
        ag1['Date'] = ag1['Date_Parsed'].dt.date
        ag2['Date'] = ag2['Date_Parsed'].dt.date
        
        ca, cb, cc = st.columns(3)
        with ca:
            if not ag1.empty:
                daily_apps = ag1.groupby('Date').size().to_frame('Total Apps')
                st.dataframe(daily_apps.style.background_gradient(cmap='Blues'), use_container_width=True)
            else:
                st.info("No applications.")

        with cb:
            if not ag1.empty:
                daily_qual = ag1.groupby(['Date', 'Q_Status']).size().unstack(fill_value=0)
                st.dataframe(daily_qual.style.background_gradient(cmap='Greens', subset=pd.IndexSlice[:, daily_qual.columns.intersection(['Approved'])]), use_container_width=True)
            else:
                st.info("No quality data.")
                
        with cc:
            if not ag2.empty:
                daily_port = ag2.groupby(['Date', 'P_Status']).size().unstack(fill_value=0)
                st.dataframe(daily_port.style.background_gradient(cmap='Purples', subset=pd.IndexSlice[:, daily_port.columns.intersection(['Live', 'Committed'])]), use_container_width=True)
            else:
                st.info("No portal data.")

        # 6. Performance Trends (Charts)
        st.subheader("📈 My Trend")
        if not ag1.empty:
            d_apps = ag1.groupby('Date').size().to_frame('Total Apps')
            d_appr = ag1[ag1['Q_Status'] == 'Approved'].groupby('Date').size().to_frame('Approved')
            d_live = ag2[ag2['P_Status'] == 'Live'].groupby('Date').size().to_frame('Live')
            i_comb = d_apps.join([d_appr, d_live], how='left').fillna(0).reset_index()
            i_comb['Date'] = i_comb['Date'].astype(str)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=i_comb['Date'], y=i_comb['Total Apps'], name="Total Apps", marker_color='#60A5FA'))
            fig.add_trace(go.Scatter(x=i_comb['Date'], y=i_comb['Approved'], name="Quality Approved", line=dict(color='#059669', width=3)))
            fig.add_trace(go.Scatter(x=i_comb['Date'], y=i_comb['Live'], name="Live Accounts", line=dict(color='#F59E0B', width=3)))
            fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)

        # 7. Quality Remarks Log (New for Agents)
        st.subheader("🔍 Recent Quality Audit Log")
        st.write("Review recent statuses to see if any accounts need rework.")
        if not ag1.empty:
            # Displaying standard columns - adjust names based on your actual sheet headers
            display_cols = ['Standardized_Date', 'Customer Name', 'Quality Status']
            # If you have a specific "Remarks" column, add it to this list:
            if 'Remarks' in ag1.columns: display_cols.append('Remarks')
            if 'Welcome Call Remarks' in ag1.columns: display_cols.append('Welcome Call Remarks')
            
            recent_log = ag1.sort_values(by='Date_Parsed', ascending=False).head(20)
            
            # Show only the columns that actually exist in the dataframe to prevent KeyError
            actual_cols = [c for c in display_cols if c in ag1.columns]
            st.dataframe(recent_log[actual_cols], use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
