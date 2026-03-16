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
    h3 {
margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A;
}
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

# --- UI START ---
try:
    df1, df2, last_sync = fetch_data()

    col_title, col_time = st.columns([3, 1])
    col_title.title("🚀 Sparta Performance & Live Status Dashboard")
    col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Date_Parsed'].dt.date >= start_date) & (df1['Date_Parsed'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Date_Parsed'].dt.date >= start_date) & (df2['Date_Parsed'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    with tab1:
        col_sort = st.columns([1, 1, 1.5])[2]
        app_counts = f1.groupby('Advisor').size().to_frame('Total Apps')
        qual_counts = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
        port_counts = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')

        all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
        master = pd.DataFrame(index=all_advisors).join([app_counts, qual_counts, port_counts]).fillna(0)

        sort_options = {
            "Total Apps (High to Low)": "Total Apps", 
            "Quality: Approved": "Qual_Approved", 
            "Quality: Cancelled": "Qual_Cancelled", 
            "Live Status: Live": "Port_Live", 
            "Advisor Name (A-Z)": "index"
        }
        available_sorts = [k for k, v in sort_options.items() if v == "index" or v in master.columns]
        selected_sort_label = col_sort.selectbox("Master Sort (Aligns all tables):", available_sorts)
        
        sort_col = sort_options[selected_sort_label]
        master = master.sort_index() if sort_col == "index" else master.sort_values(sort_col, ascending=False)

        totals_row = master.sum().to_frame().T
        totals_row.index = ["GRAND TOTAL"]
        final_df = pd.concat([master, totals_row])
        advisor_indices = master.index

        st.divider()
        c1, c2, c3 = st.columns([1, 1.8, 1.8])
        with c1:
            st.subheader("📊 Apps")
            st.dataframe(final_df[['Total Apps']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Apps')), use_container_width=True, height=500)
        with c2:
            st.subheader("✅ Quality Audit")
            q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
            disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
            styler_q = disp_qual.style.format("{:,.0f}")
            for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                if col in disp_qual.columns: styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap)
            st.dataframe(styler_q, use_container_width=True, height=500)
        with c3:
            st.subheader("🌐 Live Status")
            p_cols = [c for c in final_df.columns if c.startswith('Port_')]
            p_order = ['Port_Live', 'Port_Committed', 'Port_Cancelled', 'Port_Others']
            actual_p_order = [c for c in p_order if c in p_cols]
            disp_port = final_df[actual_p_order].rename(columns=lambda x: x.replace('Port_', ''))
            styler_p = disp_port.style.format("{:,.0f}")
            for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
                if col in disp_port.columns: styler_p = styler_p.background_gradient(subset=(advisor_indices, col), cmap=cmap)
            st.dataframe(styler_p, use_container_width=True, height=500)

    with tab2:
        st.subheader("👤 Detailed Agent Analysis")
        selected_agent = st.selectbox("Select Agent:", all_advisors)
        
        if selected_agent:
            ag1 = f1[f1['Advisor'] == selected_agent].copy()
            ag2 = f2[f2['Advisor'] == selected_agent].copy()
            
            # --- METRIC CARDS ---
            total_apps = len(ag1)
            approved = len(ag1[ag1['Q_Status'] == 'Approved'])
            total_port = len(ag2)
            live = len(ag2[ag2['P_Status'] == 'Live'])
            
            approval_rate = f"{(approved / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            live_rate = f"{(live / total_port * 100):.1f}%" if total_port > 0 else "0.0%"
            
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("📝 Total Apps", f"{total_apps:,}")
            mc2.metric("✅ Approval Rate", approval_rate)
            mc3.metric("🌐 Total Live", f"{live:,}")
            mc4.metric("🚀 Live Rate", live_rate)
            
            st.divider()
            
            # --- VIEW TOGGLE ---
            view_mode = st.radio("View Breakdown By:", ["Daily", "Monthly"], horizontal=True)
            
            if view_mode == "Monthly":
                ag1['Period'] = ag1['Date_Parsed'].dt.to_period('M')
                ag2['Period'] = ag2['Date_Parsed'].dt.to_period('M')
            else:
                ag1['Period'] = ag1['Date_Parsed'].dt.date
                ag2['Period'] = ag2['Date_Parsed'].dt.date
            
            st.write(f"**{view_mode}** breakdown for **{selected_agent}**")
            
            ca, cb, cc = st.columns([1, 1.8, 1.8])

            # 1. Apps
            with ca:
                st.markdown(f"#### 📊 {view_mode} Apps")
                daily_apps = ag1.groupby('Period').size().to_frame('Apps')
                if view_mode == "Monthly":
                    daily_apps.index = daily_apps.index.strftime('%b %Y')
                    
                t_apps = daily_apps.sum().to_frame().T
                t_apps.index = ["TOTAL"]
                df_apps = pd.concat([daily_apps, t_apps])
                st.dataframe(df_apps.style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(daily_apps.index, 'Apps')), use_container_width=True)

            # 2. Quality
            with cb:
                st.markdown(f"#### ✅ Quality Audit")
                daily_qual = ag1.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
                q_order = ['Approved', 'Rework', 'Cancelled', 'Others']
                actual_q = [c for c in q_order if c in daily_qual.columns]
                dq_filtered = daily_qual[actual_q]
                
                if view_mode == "Monthly":
                    dq_filtered.index = dq_filtered.index.strftime('%b %Y')
                    
                t_qual = dq_filtered.sum().to_frame().T
                t_qual.index = ["TOTAL"]
                df_qual = pd.concat([dq_filtered, t_qual])
                
                styler_dq = df_qual.style.format("{:,.0f}")
                # --- COLOR SYNC: Wistia and Reds to match Main Page ---
                for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                    if col in df_qual.columns:
                        styler_dq = styler_dq.background_gradient(subset=(dq_filtered.index, col), cmap=cmap)
                st.dataframe(styler_dq, use_container_width=True)

            # 3. Live Status
            with cc:
                st.markdown(f"#### 🌐 Live Status")
                daily_port = ag2.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
                p_order = ['Live', 'Committed', 'Cancelled', 'Others']
                actual_p = [c for c in p_order if c in daily_port.columns]
                dp_filtered = daily_port[actual_p]
                
                if view_mode == "Monthly":
                    dp_filtered.index = dp_filtered.index.strftime('%b %Y')
                    
                t_port = dp_filtered.sum().to_frame().T
                t_port.index = ["TOTAL"]
                df_port = pd.concat([dp_filtered, t_port])
                
                styler_dp = df_port.style.format("{:,.0f}")
                # --- COLOR SYNC: Reds to match Main Page ---
                for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
                    if col in df_port.columns:
                        styler_dp = styler_dp.background_gradient(subset=(dp_filtered.index, col), cmap=cmap)
                st.dataframe(styler_dp, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
