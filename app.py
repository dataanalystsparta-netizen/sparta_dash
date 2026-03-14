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

    col_a, col_b = st.columns(2)
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    # 1. Grouping
    app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')
    qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0)
    port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0)

    # Master Merge
    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    master = pd.DataFrame(index=all_advisors).join([app_counts, qual_counts, port_counts]).fillna(0)
    
    # Insert visual separators (empty columns) to mimic the 3-table look
    master.insert(1, " | ", "")
    # Find where Quality ends to put the second separator
    qual_end_idx = len(app_counts.columns) + len(qual_counts.columns) + 1
    master.insert(qual_end_idx + 1, " || ", "")

    master = master.sort_values('Total Apps', ascending=False)

    # Add Totals Row
    totals = master.select_dtypes(include=['number']).sum().to_frame().T
    totals.index = ["GRAND TOTAL"]
    final_df = pd.concat([master, totals]).fillna("")

    # --- RENDERING ---
    st.divider()
    st.info("💡 Hint: Click any column header to sort. The entire row will stay synced.")
    
    rows_to_style = final_df.index[:-1]

    # Setup styling logic
    styler = final_df.style.format(precision=0, na_rep="")
    
    # 1. Apps Color
    styler = styler.background_gradient(cmap='Greens', subset=(rows_to_style, 'Total Apps'))
    
    # 2. Quality Colors
    for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'YlOrBr')]:
        if col in final_df.columns:
            styler = styler.background_gradient(subset=(rows_to_style, col), cmap=cmap)
            
    # 3. Portal Colors
    for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
        if col in final_df.columns:
            styler = styler.background_gradient(subset=(rows_to_style, col), cmap=cmap)

    st.dataframe(styler, use_container_width=True, height=800)

except Exception as e:
    st.warning("Adjust filters or check data source.")
    if st.checkbox("Show technical error"):
        st.error(e)
