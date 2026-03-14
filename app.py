import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

st.markdown("""
    <style>
    .block-container { max-width: 98%; padding-top: 2rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A; }
    .last-updated { font-size: 0.8rem; color: gray; text-align: right; }
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
    
    # Sparta Sheet (Apps & Quality)
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Date_Parsed'] = pd.to_datetime(df1['Standardized_Date'], errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    # Sparta2 Sheet (Portal Status)
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Date_Parsed'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()

    # Meta Data (Heartbeat)
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

# --- UI START ---
try:
    df1, df2, last_sync = fetch_data()

    col_title, col_time = st.columns([3, 1])
    col_title.title("🚀 Sparta Performance & Portal Dashboard")
    col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Date_Parsed'].dt.date >= start_date) & (df1['Date_Parsed'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Date_Parsed'].dt.date >= start_date) & (df2['Date_Parsed'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    # 1. Grouping Main Dashboard
    app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')
    qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
    port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    master = pd.DataFrame(index=all_advisors).join([app_counts, qual_counts, port_counts]).fillna(0)

    # 2. MASTER SYNC SORTING
    sort_options = {
        "Total Apps (High to Low)": "Total Apps",
        "Quality: Approved": "Qual_Approved",
        "Quality: Cancelled": "Qual_Cancelled",
        "Portal: Live": "Port_Live",
        "Advisor Name (A-Z)": "index"
    }
    available_sorts = [k for k, v in sort_options.items() if v == "index" or v in master.columns]
    selected_sort_label = col_c.selectbox("Master Sort (Aligns all tables):", available_sorts)
    
    sort_col = sort_options[selected_sort_label]
    master = master.sort_index() if sort_col == "index" else master.sort_values(sort_col, ascending=False)

    totals_row = master.sum().to_frame().T
    totals_row.index = ["GRAND TOTAL"]
    final_df = pd.concat([master, totals_row])
    advisor_indices = master.index

    st.divider()

    # --- THREE-COLUMN DISPLAY ---
    c1, c2, c3 = st.columns([1, 1.8, 1.8])

    with c1:
        st.subheader("📊 Apps")
        st.dataframe(final_df[['Total Apps']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Apps')), use_container_width=True, height=450)

    with c2:
        st.subheader("✅ Quality Audit")
        q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
        disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
        styler_q = disp_qual.style.format("{:,.0f}")
        for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'YlOrBr')]:
            if col in disp_qual.columns: styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap)
        st.dataframe(styler_q, use_container_width=True, height=450)

    with c3:
        st.subheader("🌐 Portal Status")
        p_cols = [c for c in final_df.columns if c.startswith('Port_')]
        p_order = ['Port_Live', 'Port_Committed', 'Port_Cancelled', 'Port_Others']
        actual_p_order = [c for c in p_order if c in p_cols]
        disp_port = final_df[actual_p_order].rename(columns=lambda x: x.replace('Port_', ''))
        styler_p = disp_port.style.format("{:,.0f}")
        for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
            if col in disp_port.columns: styler_p = styler_p.background_gradient(subset=(advisor_indices, col), cmap=cmap)
        st.dataframe(styler_p, use_container_width=True, height=450)

    # --- AGENT WISE DAILY PERFORMANCE ---
    st.divider()
    st.subheader("👤 Agent-Wise Daily Performance")
    
    selected_agent = st.selectbox("Select Agent to View Detailed Daily Stats:", all_advisors)
    
    if selected_agent:
        # Filter data for specific agent
        ag1 = f1[f1['Advisor'] == selected_agent].copy()
        ag2 = f2[f2['Advisor'] == selected_agent].copy()
        
        # Group by Date
        daily_apps = ag1.groupby(ag1['Date_Parsed'].dt.date).size().to_frame('Apps')
        daily_qual = ag1.groupby([ag1['Date_Parsed'].dt.date, 'Q_Status']).size().unstack(fill_value=0)
        daily_port = ag2.groupby([ag2['Date_Parsed'].dt.date, 'P_Status']).size().unstack(fill_value=0)
        
        # Merge Daily Stats
        daily_master = pd.concat([daily_apps, daily_qual, daily_port], axis=1).fillna(0)
        daily_master.index.name = "Date"
        
        # Format the table
        st.dataframe(
            daily_master.style.format("{:,.0f}").background_gradient(cmap='Blues'),
            use_container_width=True
        )

except Exception as e:
    st.error(f"Error: {e}")
