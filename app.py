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
    .section-header { background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-top: 30px; margin-bottom: 20px; }
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
    df1['Standardized_Date'] = pd.to_datetime(df1['Standardized_Date'], format='mixed', dayfirst=True, errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Sale Date'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()
    
    # Try to fetch Last Updated time from Meta tab
    last_update = "Unknown"
    try:
        meta = ss.worksheet('Meta').get_all_values()
        last_update = meta[0][1]
    except:
        pass
        
    return df1, df2, last_update

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
st.title("🚀 Sparta Performance & Portal Dashboard")

try:
    df1, df2, last_update = fetch_data()
    st.caption(f"Last Synced from Local Network: **{last_update}**")

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    # 1. Main Dashboard Grouping
    app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')
    qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
    port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    master = pd.DataFrame(index=all_advisors).join([app_counts, qual_counts, port_counts]).fillna(0)

    # Master Sort
    sort_options = {"Total Apps": "Total Apps", "Quality: Approved": "Qual_Approved", "Portal: Live": "Port_Live", "Advisor Name": "index"}
    selected_sort_label = col_c.selectbox("Master Sort (Aligns all tables):", list(sort_options.keys()))
    sort_col = sort_options[selected_sort_label]
    master = master.sort_index() if sort_col == "index" else master.sort_values(sort_col, ascending=False)

    totals_row = master.sum().to_frame().T
    totals_row.index = ["GRAND TOTAL"]
    final_df = pd.concat([master, totals_row])
    advisor_indices = master.index

    # --- RENDER TOP TABLES ---
    st.divider()
    c1, c2, c3 = st.columns([1, 1.8, 1.8])

    with c1:
        st.subheader("📊 Apps")
        st.dataframe(final_df[['Total Apps']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Apps')), use_container_width=True)

    with c2:
        st.subheader("✅ Quality Audit")
        q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
        disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
        st.dataframe(disp_qual.style.format("{:,.0f}").background_gradient(cmap='YlGn', subset=(advisor_indices, 'Approved')), use_container_width=True)

    with c3:
        st.subheader("🌐 Portal Status")
        p_order = ['Port_Live', 'Port_Committed', 'Port_Cancelled', 'Port_Others']
        actual_p = [c for c in p_order if c in final_df.columns]
        disp_port = final_df[actual_p].rename(columns=lambda x: x.replace('Port_', ''))
        st.dataframe(disp_port.style.format("{:,.0f}").background_gradient(cmap='Blues', subset=(advisor_indices, 'Live')), use_container_width=True)

    # --- AGENT PERFORMANCE SECTION ---
    st.markdown("<div class='section-header'><h3>👤 Detailed Agent Performance Drill-down</h3></div>", unsafe_allow_html=True)
    
    selected_agent = st.selectbox("Select Advisor to see daily/monthly trend:", ["All Advisors"] + all_advisors)
    view_type = st.radio("Group By:", ["Date", "Month"], horizontal=True)

    # Logic to aggregate based on selection
    trend_data = f1.copy()
    if selected_agent != "All Advisors":
        trend_data = trend_data[trend_data['Advisor'] == selected_agent]

    if view_type == "Date":
        trend_data['Period'] = trend_data['Standardized_Date'].dt.date
    else:
        trend_data['Period'] = trend_data['Standardized_Date'].dt.strftime('%b-%y')

    # Create Trend Table
    daily_apps = trend_data.groupby('Period').size().to_frame('Apps')
    daily_qual = trend_data.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
    
    trend_final = daily_apps.join(daily_qual).fillna(0)
    
    st.write(f"Showing performance for: **{selected_agent}** by **{view_type}**")
    st.dataframe(trend_final.style.format("{:,.0f}").background_gradient(cmap='Purples', subset=['Apps']), use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
