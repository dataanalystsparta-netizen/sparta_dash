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
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=300)
def fetch_data():
    # Use the specific keys provided in the context for GCP integration
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(info, scopes=[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ])
    client = gspread.authorize(creds)
    # Open the specific spreadsheet provided in the user's links
    ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
    
    # 1. Sparta Sheet (Apps & Quality Audit)
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Standardized_Date'] = pd.to_datetime(df1['Standardized_Date'], format='mixed', dayfirst=True, errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    # 2. Sparta2 Sheet (Portal Status)
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Sale Date'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()
    
    return df1, df2

def map_quality(val):
    s = str(val).lower()
    if any(x in s for x in ['appr', 'pass']): return 'Approved'
    if any(x in s for x in ['rew', 'repro']): return 'Rework'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    return 'Others'

def map_portal(val):
    s = str(val).lower()
    if 'live' in s: return 'Live'
    if any(x in s for x in ['can', 'rej']): return 'Cancelled'
    if 'com' in s: return 'Committed'
    return 'Others'

# --- UI START ---
st.title("🚀 Sparta Performance & Portal Dashboard")

try:
    df1, df2 = fetch_data()

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    # 1. Grouping
    app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')
    qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
    port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')

    # Master Merge for Syncing logic
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
    if sort_col == "index":
        master = master.sort_index()
    else:
        master = master.sort_values(sort_col, ascending=False)

    # 3. Final Prepare with Totals Row
    totals = master.sum().to_frame().T
    totals.index = ["GRAND TOTAL"]
    final_df = pd.concat([master, totals])
    
    # Track indices for color styling
    advisor_indices = master.index

    st.divider()

    # --- THREE-COLUMN DISPLAY ---
    c1, c2, c3 = st.columns([1, 1.8, 1.8])

    # Table 1: Apps
    with c1:
        st.subheader("📊 Apps")
        st.dataframe(
            final_df[['Total Apps']].style.format("{:,.0f}")
            .background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Apps')),
            use_container_width=True, height=650
        )

    # Table 2: Quality Audit (Colors Updated)
    with c2:
        st.subheader("✅ Quality Audit")
        q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
        disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
        
        styler_q = disp_qual.style.format("{:,.0f}")
        for col, cmap in [
            ('Approved', 'YlGn'), 
            ('Cancelled', 'Reds'), # Updated from maroon to bright red
            ('Rework', 'YlOrYl') # Updated from brown to pure yellow
        ]:
            if col in disp_qual.columns:
                styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap)
        st.dataframe(styler_q, use_container_width=True, height=650)

    # Table 3: Portal Status (Colors Updated)
    with c3:
        st.subheader("🌐 Portal Status")
        p_cols = [c for c in final_df.columns if c.startswith('Port_')]
        disp_port = final_df[p_cols].rename(columns=lambda x: x.replace('Port_', ''))
        
        styler_p = disp_port.style.format("{:,.0f}")
        for col, cmap in [
            ('Live', 'Blues'), 
            ('Cancelled', 'Reds'), # Updated from maroon to bright red
            ('Committed', 'Purples')
        ]:
            if col in disp_port.columns:
                styler_p = styler_p.background_gradient(subset=(advisor_indices, col), cmap=cmap)
        st.dataframe(styler_p, use_container_width=True, height=650)

except Exception as e:
    st.warning("Please adjust filters or check data connection.")
    # In a production app, consider logging the error details securely.
    # st.error(e)
