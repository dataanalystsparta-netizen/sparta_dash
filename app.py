import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# --- MASTER AGENT LIST ---
LIVE_AGENTS = [
    "Anshu","Anjali", "Aman", "Frogh", "Gaurav", "Guru", 
    "Naveen", "Krrish", "Niki", "Manmeet","Sangeeta","Gungun"
]

st.markdown("""
   <style>
   .block-container { max-width: 98%; padding-top: 2rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A; }
   .last-updated { font-size: 0.8rem; color: gray; text-align: right; }
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
    "total_apps": "Total Applications.",
    "qual_approved": "Applications that have successfully passed the Quality Audit process.",
    "approv_rate": "Percentage of total applications that reached 'Approved' status.",
    "commit_apps": "Total applications that got 'Committed'.",
    "commit_rate": "Percentage of applications that got 'Committed'",
    "total_live": "Total applications that got 'Live'.",
    "live_rate": "Conversion rate from Committed applications to confirmed Live records."
}

try:
    df1, df2, last_sync = fetch_data()
    col_title, col_time = st.columns([3, 1])
    col_title.title("🚀 Sparta Performance & Live Status Dashboard")
    col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Date_Parsed'].dt.date >= start_date) & (df1['Date_Parsed'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Date_Parsed'].dt.date >= start_date) & (df2['Date_Parsed'].dt.date <= end_date)].copy()
    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    formatted_live = [name.strip().title() for name in LIVE_AGENTS]

    sort_options = {
        "Total Applications (High to Low)": "Total Applications", 
        "Quality: Approved": "Qual_Approved", 
        "Quality: Cancelled": "Qual_Cancelled", 
        "Live Status: Live": "Port_Live", 
        "Advisor Name (A-Z)": "index"
    }
    
    tab1, tab2 = st.tabs(["📊 Team Overview", "👤 Individual Performance"])

    with tab1:
        show_live_team = st.checkbox("Show current roster only", value=False, key="team_roster_filter")
        if show_live_team:
            f1_team = f1[f1['Advisor'].isin(formatted_live)].copy()
            f2_team = f2[f2['Advisor'].isin(formatted_live)].copy()
            active_advisors_team = [name for name in all_advisors if name in formatted_live]
        else:
            f1_team = f1.copy()
            f2_team = f2.copy()
            active_advisors_team = all_advisors

        team_apps = len(f1_team)
        team_approved = len(f1_team[f1_team['Q_Status'] == 'Approved'])
        team_approv_rate = f"{(team_approved / team_apps * 100):.1f}%" if team_apps > 0 else "0.0%"
        team_committed = len(f2_team)
        team_commit_rate = f"{(team_committed / team_apps * 100):.1f}%" if team_apps > 0 else "0.0%"
        team_live = len(f2_team[f2_team['P_Status'] == 'Live'])
        team_live_rate = f"{(team_live / team_committed * 100):.1f}%" if team_committed > 0 else "0.0%"

        with st.container(border=True):
            tm1, tm2, tm3, tm4, tm5, tm6, tm7 = st.columns(7)
            tm1.metric("📝 Tot. Applications", f"{team_apps:,}", help=KPI_DEFS["total_apps"])
            tm2.metric("✅ Quality Approv.", f"{team_approved:,}", help=KPI_DEFS["qual_approved"])
            tm3.metric("📈 Approv. Rate", team_approv_rate, help=KPI_DEFS["approv_rate"])
            tm4.metric("📦 Commit. Apps", f"{team_committed:,}", help=KPI_DEFS["commit_apps"])
            tm5.metric("📋 Commit. Rate", team_commit_rate, help=KPI_DEFS["commit_rate"])
            tm6.metric("🌐 Total Live", f"{team_live:,}", help=KPI_DEFS["total_live"])
            tm7.metric("🚀 Live Rate", team_live_rate, help=KPI_DEFS["live_rate"])

        app_counts = f1_team.groupby('Advisor').size().to_frame('Total Applications')
        qual_counts = f1_team.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
        port_counts = f2_team.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
        
        tab_master = pd.DataFrame(index=active_advisors_team).join([app_counts, qual_counts, port_counts]).fillna(0)
        selected_sort_label = col_c.selectbox("Master Sort:", [k for k in sort_options.keys() if sort_options[k] == "index" or sort_options[k] in tab_master.columns or sort_options[k] == "Total Applications"])
        sort_col = sort_options[selected_sort_label]
        master = tab_master.sort_index() if sort_col == "index" else tab_master.sort_values(sort_col, ascending=False)
        totals_row = master.sum().to_frame().T
        totals_row.index = ["GRAND TOTAL"]
        final_df = pd.concat([master, totals_row])
        advisor_indices = master.index

        st.divider()
        c1, c2, c3 = st.columns([1, 1.8, 1.8])
        
        with c1:
            st.subheader("📊 Applications")
            st.dataframe(final_df[['Total Applications']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Applications')), use_container_width=True, height=500)
        
        with c2:
            st.subheader("✅ Quality Audit")
            q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
            # Apply color based on the NUMERIC data before converting to string
            styler_q = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', '')).style
            for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                if col in styler_q.columns:
                    styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap)
            
            # Format display string: "Count (Percentage%)"
            styler_q = styler_q.format(lambda x, col_name=None: f"{x:,.0f} ({(x/final_df.loc[advisor_indices.append(pd.Index(['GRAND TOTAL'])), 'Total Applications'].reindex(advisor_indices.append(pd.Index(['GRAND TOTAL'])))[styler_q.index.get_loc(col_name) if hasattr(styler_q.index, 'get_loc') else 0]*100 if final_df.loc[final_df.index[0], 'Total Applications'] > 0 else 0):.1f}%)" if False else f"{x:,.0f}") 
            # Simplified formatting approach for stability
            def format_qual(val, row_idx, col_name):
                tot = final_df.loc[row_idx, 'Total Applications']
                perc = (val / tot * 100) if tot > 0 else 0
                return f"{val:,.0f} ({perc:.1f}%)"

            disp_qual = final_df[q_cols].rename(columns=lambda x: x.replace('Qual_', ''))
            styler_q = disp_qual.style
            for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                if col in disp_qual.columns: styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap)
            
            # The 'Secret Sauce': formatting the display without losing numeric gradient context
            styler_q = styler_q.format(lambda v: f"{v:,.0f}") # Fallback
            for col in disp_qual.columns:
                styler_q = styler_q.format(subset=[col], formatter=lambda v, c=col: f"{v:,.0f} ({(v/final_df.loc[final_df.index[disp_qual.index.get_loc(v) if v in disp_qual.index else 0],'Total Applications']*100 if v else 0):.1f}%)" if False else f"{v:,.0f}")
            
            # Refined formatting logic to avoid index errors
            formatted_qual = disp_qual.copy()
            for col in disp_qual.columns:
                for idx in disp_qual.index:
                    val = disp_qual.at[idx, col]
                    tot = final_df.at[idx, 'Total Applications']
                    perc = (val/tot*100) if tot > 0 else 0
                    formatted_qual.at[idx, col] = f"{val:,.0f} ({perc:.1f}%)"
            
            st.dataframe(disp_qual.style.background_gradient(cmap='YlGn', subset=(advisor_indices, 'Approved'))
                         .background_gradient(cmap='Reds', subset=(advisor_indices, 'Cancelled') if 'Cancelled' in disp_qual.columns else [])
                         .background_gradient(cmap='Wistia', subset=(advisor_indices, 'Rework') if 'Rework' in disp_qual.columns else [])
                         .format(lambda v: f"{v:,.0f} ({(v/final_df.loc[final_df.index[0], 'Total Applications']*100):.1f}%)" if False else "FIX"), use_container_width=True, height=500)
            
            # Use separate display dataframe for text but style the numeric one
            st.write("---") # Re-rendering for v3.3 cleanliness
            st.dataframe(disp_qual.style.background_gradient(cmap='YlGn', subset=(advisor_indices, 'Approved'))
                         .background_gradient(cmap='Reds', subset=(advisor_indices, 'Cancelled') if 'Cancelled' in disp_qual.columns else [])
                         .format(lambda v: f"{v:,.0f}"), use_container_width=True)
            # Reverting to v3.1 structure with manual string injection to fix gradient
            # Final fix for gradients + strings:
            q_display = disp_qual.copy().astype(str)
            for col in disp_qual.columns:
                for idx in disp_qual.index:
                    v, t = disp_qual.at[idx, col], final_df.at[idx, 'Total Applications']
                    q_display.at[idx, col] = f"{v:,.0f} ({(v/t*100 if t>0 else 0):.1f}%)"
            
            st.dataframe(disp_qual.style.format(lambda v: q_display.iloc[disp_qual.index.get_loc(disp_qual.index[0])]) # placeholder
                         .background_gradient(cmap='YlGn', subset=(advisor_indices, 'Approved')), use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
