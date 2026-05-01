import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import plotly.express as px
import plotly.graph_objects as go 
import calendar

st.set_page_config(page_title="Sparta Agent Portal", layout="wide")

# --- UI STYLE ---
st.markdown("""
    <style>
    .block-container { max-width: 98%; padding-top: 1.5rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.1rem !important; color: #1E3A8A; }
    .last-updated { font-size: 0.75rem; color: gray; text-align: right; }
    .kpi-box { background-color: #F1F5F9; padding: 15px; border-radius: 12px; border: 1px solid #E2E8F0; height: 100%; box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05); }
    .box-label { font-size: 0.75rem; font-weight: 800; color: #475569; text-align: left; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; }
    .box-label::before { content: ""; display: inline-block; width: 4px; height: 12px; background: #1E3A8A; margin-right: 8px; border-radius: 2px; }
    .kpi-card { padding: 12px 5px; border-radius: 10px; text-align: center; background: white; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); min-height: 85px; display: flex; flex-direction: column; justify-content: center; }
    .kpi-label { font-size: 0.65rem; color: #64748B; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; }
    .kpi-value { font-size: 1.2rem; color: #0F172A; font-weight: 800; margin: 0; line-height: 1; }
    .kpi-pc { font-size: 0.7rem; color: #1E3A8A; font-weight: 700; margin-top: 4px; background: rgba(30, 58, 138, 0.1); display: inline-block; padding: 2px 6px; border-radius: 4px; }
    .insight-container { display: flex; gap: 12px; overflow-x: auto; padding: 10px 5px 20px 5px; }
    .insight-card { background: #FFFFFF; border-left: 5px solid #1E3A8A; padding: 12px 16px; min-width: 220px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .insight-title { font-size: 0.7rem; font-weight: 800; color: #64748B; margin: 0; text-transform: uppercase; }
    .insight-phrase { font-size: 0.9rem; font-weight: 700; color: #1E3A8A; margin: 4px 0; }
    .insight-comment { font-size: 0.75rem; color: #475569; margin: 0; line-height: 1.3; }
    </style>
    """, unsafe_allow_html=True)

ACCESS_KEYS = st.secrets["agent_keys"]

def log_agent_login(agent_name):
    try:
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        client = gspread.authorize(creds)
        ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
        log_sheet = ss.worksheet('Logs')
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([timestamp, agent_name, "Login"])
    except: pass

@st.cache_data(ttl=300)
def fetch_data():
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    client = gspread.authorize(creds)
    ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
    
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Date_Parsed'] = pd.to_datetime(df1['Standardized_Date'], errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    
    # Handle the specific "Month" and "Telephone No." headers from your snippet
    df2['Date_Parsed'] = pd.to_datetime(df2['Month'], errors='coerce')
    
    # If "Agent" column is missing in Sparta2, we won't filter it by Advisor to ensure data flows
    if 'Agent' in df2.columns:
        df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()
    else:
        df2['Advisor'] = "All" # Fallback if agent column is missing

    try:
        meta = ss.worksheet('Meta').get_all_values()
        last_sync = meta[0][1]
    except: last_sync = "Unknown"
    
    return df1, df2, last_sync

# Mapping Functions
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
    st.markdown(f'<div class="kpi-card" style="border-top: 4px solid {accent};"><p class="kpi-label">{label}</p><p class="kpi-value">{value:,}</p>{pc_html}</div>', unsafe_allow_html=True)

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
                log_agent_login(ACCESS_KEYS[user_key.upper()])
                st.rerun()
            else: st.error("Invalid Access Key.")
else:
    agent = st.session_state.agent_name
    today_date = datetime.date.today()
    
    with st.sidebar:
        st.subheader(f"👤 {agent}")
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    try:
        df1, df2, last_sync = fetch_data()
        ag1 = df1[df1['Advisor'] == agent].copy()
        
        # If Sparta2 has an Advisor column, filter it. If not, use the whole sheet.
        if 'Advisor' in df2.columns and not (df2['Advisor'] == "All").all():
            ag2 = df2[df2['Advisor'] == agent].copy()
        else:
            ag2 = df2.copy()
            
        st.title(f"My Performance Dashboard")
        st.markdown(f"<p class='last-updated'>Data Last Synced: <b>{last_sync}</b></p>", unsafe_allow_html=True)

        col_a, col_b, _ = st.columns([1, 1, 3])
        start_date = col_a.date_input("Start Date", today_date.replace(day=1))
        end_date = col_b.date_input("End Date", today_date)

        ag1_filtered = ag1[(ag1['Date_Parsed'].dt.date >= start_date) & (ag1['Date_Parsed'].dt.date <= end_date)].copy()
        ag2_filtered = ag2[(ag2['Date_Parsed'].dt.date >= start_date) & (ag2['Date_Parsed'].dt.date <= end_date)].copy()
        
        ag1_filtered['Q_Status'] = ag1_filtered['Quality Status'].apply(map_quality)
        ag2_filtered['P_Status'] = ag2_filtered['Status'].apply(map_portal)
        wc_col = 'Status' if 'Status' in ag1_filtered.columns else None
        if wc_col: ag1_filtered['WC_Clean'] = ag1_filtered[wc_col].apply(map_wc)

        # KPI Groups
        total_apps = len(ag1_filtered)
        total_ag2 = len(ag2_filtered)
        
        b1, b2, b3, b4 = st.columns([1.2, 2.5, 2.5, 2.2])
        with b1: 
            st.markdown('<div class="kpi-box"><p class="box-label">Overview</p>', unsafe_allow_html=True)
            render_kpi("Total Apps", total_apps, total_apps)
            st.markdown('</div>', unsafe_allow_html=True)
        with b2:
            st.markdown('<div class="kpi-box"><p class="box-label">Quality Audit</p>', unsafe_allow_html=True)
            c = st.columns(2)
            with c[0]: render_kpi("Approved", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']), total_apps)
            with c[1]: render_kpi("Rework", len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']), total_apps)
            st.markdown('</div>', unsafe_allow_html=True)
        with b3:
            st.markdown('<div class="kpi-box"><p class="box-label">Welcome Call</p>', unsafe_allow_html=True)
            c = st.columns(2)
            with c[0]: render_kpi("WC Done", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done']), total_apps)
            with c[1]: render_kpi("WC Pending", len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Pending']), total_apps)
            st.markdown('</div>', unsafe_allow_html=True)
        with b4:
            st.markdown('<div class="kpi-box"><p class="box-label">Live Status</p>', unsafe_allow_html=True)
            c = st.columns(2)
            with c[0]: render_kpi("Live", len(ag2_filtered[ag2_filtered['P_Status'] == 'Live']), total_ag2 if total_ag2 > 0 else 1)
            with c[1]: render_kpi("Committed", len(ag2_filtered[ag2_filtered['P_Status'] == 'Committed']), total_ag2 if total_ag2 > 0 else 1)
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        # --- RECENT APPLICATIONS LOG (MERGE LOGIC) ---
        st.subheader("🔍 Recent Applications Log")
        if not ag1_filtered.empty:
            # Standardize CLI Keys (remove .0, spaces, and leading zeros)
            ag1_filtered['CLI_Key'] = ag1_filtered['CLI'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lstrip('0')
            
            ag2_clean = ag2.copy()
            # Match "Telephone No." header from your snippet
            phone_col = 'Telephone No.' if 'Telephone No.' in ag2_clean.columns else 'CLI'
            
            if phone_col in ag2_clean.columns:
                ag2_clean['Telephone_Key'] = ag2_clean[phone_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.lstrip('0')
                ag2_clean = ag2_clean.rename(columns={'Status': 'Portal Status'})
                
                # De-duplicate to prevent row explosion
                ag2_unique = ag2_clean.sort_values('Date_Parsed').drop_duplicates('Telephone_Key', keep='last')
                
                # Merge columns from Sparta2
                merged_log = ag1_filtered.merge(
                    ag2_unique[['Telephone_Key', 'LetterStatus', 'CallStatus', 'Comments', 'Voice of Customer', 'Cancellation Reason', 'Portal Status']],
                    left_on='CLI_Key', 
                    right_on='Telephone_Key', 
                    how='left'
                )

                # Column display selection
                display_cols = [
                    'Standardized_Date', 'Customer Name', 'Quality Status', 'Quality Remarks', 
                    'Status', 'LetterStatus', 'CallStatus', 'Comments', 'Voice of Customer', 
                    'Cancellation Reason', 'Portal Status'
                ]
                
                final_display_cols = [c for c in display_cols if c in merged_log.columns]
                recent_log = merged_log.sort_values(by='Date_Parsed', ascending=False).head(20)
                
                # Styling logic
                def style_row(row):
                    q_val = str(row.get('Quality Status', '')).lower()
                    if any(x in q_val for x in ['appr', 'pass']): color = 'background-color: rgba(167, 243, 208, 0.2)'
                    elif any(x in q_val for x in ['rew', 'repro']): color = 'background-color: rgba(253, 230, 138, 0.2)'
                    elif any(x in q_val for x in ['can', 'rej']): color = 'background-color: rgba(254, 202, 202, 0.2)'
                    else: color = ''
                    return [color] * len(row)

                st.dataframe(recent_log[final_display_cols].style.apply(style_row, axis=1), use_container_width=True, hide_index=True)
            else:
                st.warning("Could not find 'Telephone No.' in Sparta2 for matching.")
                st.dataframe(ag1_filtered.head(20), use_container_width=True)

    except Exception as e:
        st.error(f"Error loading dashboard: {e}")
