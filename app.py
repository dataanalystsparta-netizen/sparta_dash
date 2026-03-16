import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# --- MASTER AGENT LIST ---
LIVE_AGENTS = [
    "Anjali", "Aman", "Frogh", "Anshu", "Shailendra", 
    "Saurabh", "Priyanka", "Deepak", "Rohan"
]

st.markdown("""
   <style>
   .block-container { max-width: 98%; padding-top: 2rem; }
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

# (map_quality, map_portal, and KPI_DEFS remain unchanged)
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

KPI_DEFS = {
    "total_apps": "Total records extracted from the primary Sparta tracking sheet.",
    "qual_approved": "Applications that have successfully passed through the Quality Audit process.",
    "approv_rate": "Percentage of total applications that reached 'Approved' status.",
    "commit_apps": "Total records logged in the Portal/Sparta2 tracking system.",
    "commit_rate": "Efficiency of moving leads from Application to Portal stage.",
    "total_live": "Records confirmed with a 'Live' status in the portal.",
    "live_rate": "Conversion efficiency from Committed records to confirmed Live records."
}

try:
    df1, df2, last_sync = fetch_data()
    # ... (Date inputs and Team Overview tab remain the same)
    col_title, col_time = st.columns([3, 1])
    col_title.title("🚀 Sparta Performance & Live Status Dashboard")
    col_time.markdown(f"Data Last Synced: **{last_sync}**")

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Date_Parsed'].dt.date >= start_date) & (df1['Date_Parsed'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Date_Parsed'].dt.date >= start_date) & (df2['Date_Parsed'].dt.date <= end_date)].copy()
    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))

    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    with tab1:
        st.write("Team Overview Content...") # Keep your existing tab 1 code here

    with tab2:
        st.subheader("👤 Detailed Agent Analysis")
        
        # --- FIXED FILTERING LOGIC ---
        formatted_live = [name.strip().title() for name in LIVE_AGENTS]
        
        # 1. Determine which list to use based on the checkbox state
        # We put the checkbox ABOVE the dropdown in the code so the choice is made first
        show_live_only = st.checkbox("Show current roster only", value=False)
        
        if show_live_only:
            dropdown_list = [name for name in all_advisors if name in formatted_live]
            # If for some reason the filtered list is empty, fall back to all
            if not dropdown_list:
                dropdown_list = all_advisors
        else:
            dropdown_list = all_advisors

        # 2. Pass the dynamic 'dropdown_list' to the selectbox
        selected_agent = st.selectbox("Select Agent:", dropdown_list)
        
        if selected_agent:
            # (Rest of the agent calculation and display logic remains the same)
            ag1 = f1[f1['Advisor'] == selected_agent].copy()
            ag2 = f2[f2['Advisor'] == selected_agent].copy()
            
            total_apps = len(ag1)
            approved = len(ag1[ag1['Q_Status'] == 'Approved'])
            approval_rate = f"{(approved / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            
            with st.container(border=True):
                m1, m2, m3 = st.columns(3)
                m1.metric("📝 Tot. Applications", f"{total_apps:,}", help=KPI_DEFS["total_apps"])
                m2.metric("✅ Quality Approv.", f"{approved:,}", help=KPI_DEFS["qual_approved"])
                m3.metric("📈 Approv. Rate", approval_rate, help=KPI_DEFS["approv_rate"])
            # ... continue with the rest of your agent display code
            
except Exception as e:
    st.error(f"Error: {e}")
