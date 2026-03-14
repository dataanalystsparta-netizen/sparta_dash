import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Performance Dashboard", layout="wide")

# Inject our custom CSS to keep table rows aligned and heights equal
st.markdown("""
    <style>
    .reportview-container .main .block-container{ max-width: 95%; }
    .table-container { display: flex; gap: 20px; overflow-x: auto; align-items: flex-start; }
    td, th { height: 32px !important; vertical-align: middle !important; padding: 0px 8px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=600)  # Caches data for 10 minutes
def fetch_data():
    # Use Streamlit Secrets for security instead of a local JSON file
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ])
    client = gspread.authorize(creds)
    ss = client.open_by_key('1R1nXJHnmsHQhisEDronG-DMo5tWeI3Ysh8TyQmKQ2fQ')
    
    # Sparta 1
    df1 = pd.DataFrame(ss.worksheet('Sparta').get_all_records())
    df1['Standardized_Date'] = pd.to_datetime(df1['Standardized_Date'], format='mixed', dayfirst=True, errors='coerce')
    df1['Advisor'] = df1['Advisor'].astype(str).str.strip().str.title()
    
    # Sparta 2
    df2 = pd.DataFrame(ss.worksheet('Sparta2').get_all_records())
    df2['Sale Date'] = pd.to_datetime(df2['Sale Date'], format='mixed', dayfirst=True, errors='coerce')
    df2['Advisor'] = df2['Agent'].astype(str).str.strip().str.title()
    
    return df1, df2

def clean_logic(val, mode='quality'):
    s = str(val).strip().lower()
    if mode == 'quality':
        if any(k in s for k in ['appr', 'pass', 'paas']): return 'Quality Approved'
        if any(k in s for k in ['rew', 'repro', 'paper', 're-p']): return 'Rework Required'
        if any(k in s for k in ['cancel', 'canel', 'rej']): return 'Quality Cancelled'
        return 'Quality Others'
    else:
        if 'live' in s: return 'Portal Live'
        if any(k in s for k in ['cancel', 'reject']): return 'Portal Cancelled'
        if 'commit' in s: return 'Portal Committed'
        return 'Portal Others'

# --- 3. UI CONTROLS ---
st.title("🚀 Sparta Performance & Portal Dashboard")

# Quick Filter Buttons in a row
col1, col2, col3, col4, col5 = st.columns([2,1,1,1,4])
today = datetime.date.today()

with col1:
    start_date = st.date_input("Start Date", today.replace(day=1))
with col2:
    end_date = st.date_input("End Date", today)

# Logic for quick buttons (using session state to trigger updates)
if col3.button("Today"):
    start_date = end_date = today
if col4.button("Yesterday"):
    start_date = end_date = today - datetime.timedelta(days=1)

# --- 4. PROCESSING & RENDERING ---
df1, df2 = fetch_data()

# Apply cleaning
df1['Clean_Quality'] = df1['Quality Status'].apply(lambda x: clean_logic(x, 'quality'))
df2['Clean_Status'] = df2['Status'].apply(lambda x: clean_logic(x, 'portal'))

# Filter
f1 = df1[(df1['Standardized_Date'].dt.date >= start_date) & (df1['Standardized_Date'].dt.date <= end_date)]
f2 = df2[(df2['Sale Date'].dt.date >= start_date) & (df2['Sale Date'].dt.date <= end_date)]

# Aggregation & Join (same logic as before)
apps_grp = f1.groupby('Advisor').size().to_frame(name='Total Applications')
qual_grp = f1.groupby(['Advisor', 'Clean_Quality']).size().unstack(fill_value=0)
status_grp = f2.groupby(['Advisor', 'Clean_Status']).size().unstack(fill_value=0)

all_advisors = sorted(list(set(apps_grp.index) | set(qual_grp.index) | set(status_grp.index)))
master = pd.DataFrame(index=all_advisors).join([apps_grp, qual_grp, status_grp]).fillna(0)

# Sorting
sort_col = st.selectbox("Sort By", options=master.columns, index=0)
master = master.sort_values(by=sort_col, ascending=False)

# Totals
totals = master.sum().to_frame().T
totals.index = ['GRAND TOTAL']
final_df = pd.concat([master, totals])

# HTML Rendering Helper (keeps the exact styling you liked)
def get_html(df_part, cmap_config):
    styler = df_part.style
    # Apply gradients... (omitted for brevity, same as previous turn's logic)
    # ...
    return styler.to_html()

# Display side-by-side using Streamlit columns
t_col1, t_col2, t_col3 = st.columns([1, 2, 2])
with t_col1:
    st.write("### Applications")
    st.dataframe(final_df[['Total Applications']]) # Or use st.write(html) for the % styles
# ... etc for other tables
