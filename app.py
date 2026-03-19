import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import numpy as np
import plotly.express as px
import plotly.graph_objects as go 
import io
from fpdf import FPDF
import re

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sparta Master Dashboard", layout="wide")

# --- MASTER AGENT LIST ---
LIVE_AGENTS = [
   "Anshu","Anjali", "Aman", "Frogh", "Gaurav", "Guru", 
   "Naveen", "Krrish", "Niki", "Manmeet","Sangeeta","Gungun",
   "Animesh","Ajay","Shaheen"
]

st.markdown("""
   <style>
   .block-container { max-width: 98%; padding-top: 5rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A; }
   .last-updated { font-size: 0.8rem; color: gray; text-align: right; }
   [data-testid="stMetricValue"] { font-size: 1.6rem !important; color: #059669; }
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

def format_with_pct(val_df, total_series):
    display_df = val_df.copy()
    for col in val_df.columns:
        pcts = (val_df[col] / total_series * 100).fillna(0)
        display_df[col] = [
            f"{int(v):,} ({p:.1f}%)" if v > 0 else "-" 
            for v, p in zip(val_df[col], pcts)
        ]
    return display_df

# --- FINANCIAL EXTRACTION ENGINE ---
def calculate_standardized_revenue(val):
    s = str(val).lower()
    # Find the pound sign and extract the numbers/decimals immediately following it
    match = re.search(r'£\s*(\d+(?:\.\d+)?)', s)
    if match:
        amount = float(match.group(1))
        # Check if inclusive of VAT. If not, add 20%
        if 'inc' not in s: 
            amount = amount * 1.20
        return amount
    # Fallback: if no £ sign, try to just extract the first number found
    match_num = re.search(r'(\d+(?:\.\d+)?)', s)
    if match_num:
        return float(match_num.group(1))
    return 0.0

# --- PDF FORMATTING ENGINE ---
def generate_formatted_pdf(start_date, end_date, df_vol, df_qual, df_live):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, f"Sparta Team Report: {start_date} to {end_date}", ln=True, align='C')
    pdf.ln(5)
    
    def draw_pdf_table(df, title):
        if df.empty: return
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(0, 10, title, ln=True)
        df_reset = df.reset_index()
        if 'index' in df_reset.columns:
            df_reset.rename(columns={'index': 'Advisor'}, inplace=True)
        cols = df_reset.columns.tolist()
        page_width = pdf.w - 2 * pdf.l_margin
        col_width_advisor = 40
        rem_width = page_width - col_width_advisor
        col_width_other = rem_width / (len(cols) - 1) if len(cols) > 1 else 0
        row_height = 7
        pdf.set_font("Arial", 'B', 9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(220, 230, 245)
        for col in cols:
            w = col_width_advisor if col == cols[0] else col_width_other
            pdf.cell(w, row_height, str(col).replace('_', ' '), border=1, fill=True, align='C')
        pdf.ln(row_height)
        pdf.set_font("Arial", '', 9)
        fill = False
        for _, row in df_reset.iterrows():
            pdf.set_fill_color(248, 248, 248)
            for col in cols:
                w = col_width_advisor if col == cols[0] else col_width_other
                val = str(row[col])
                align = 'L' if col == cols[0] else 'R'
                if str(row[cols[0]]) == "GRAND TOTAL":
                    pdf.set_font("Arial", 'B', 9)
                else:
                    pdf.set_font("Arial", '', 9)
                pdf.cell(w, row_height, val, border=1, fill=fill, align=align)
            pdf.ln(row_height)
            fill = not fill
        pdf.ln(10)

    draw_pdf_table(df_vol, "1. Applications Volume")
    draw_pdf_table(df_qual, "2. Quality Audit Status")
    draw_pdf_table(df_live, "3. Live Status Pipeline")
    return pdf.output(dest='S').encode('latin-1')

KPI_DEFS = {
   "total_apps": "Total Applications.",
   "qual_approved": "Applications that have successfully passed the Quality Audit process.",
   "approv_rate": "Percentage of total applications that reached 'Approved' status.",
   "commit_apps": "Total applications that got 'Committed'.",
   "commit_rate": "Percentage of applications that got 'Committed'",
   "total_live": "Total applications that got 'Live'.",
   "live_rate": "Conversion rate from Committed applications to confirmed Live records."
}

TABLE_TOOLTIPS = {
    "Total Applications": "Grand total of all applications logged by the advisor.",
    "Applications": "Number of applications logged for this specific period.",
    "Approved": "Applications that have cleared the Quality Audit process.",
    "Rework": "Applications requiring corrections/rework or missing information.",
    "Cancelled": "Applications that were rejected or did not proceed.",
    "Others": "These applications are pending, hold or other miscellaneous statuses.",
    "Live": "Applications successfully activated and confirmed.",
    "Committed": "Applications that are currently in a 'committed' state, and awaiting final activation or cancellation."
}

# --- UI START ---
try:
    df1, df2, last_sync = fetch_data()

    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.image("https://raw.githubusercontent.com/dataanalystsparta-netizen/logos/refs/heads/main/sparta-lite.30f2063887def24833df3d0d5ac6c503.png", width=280)
        st.title("Sparta Performance & Live Status Dashboard")
        
    col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    start_date = col_a.date_input("Start Date", datetime.date.today().replace(day=1))
    end_date = col_b.date_input("End Date", datetime.date.today())

    f1 = df1[(df1['Date_Parsed'].dt.date >= start_date) & (df1['Date_Parsed'].dt.date <= end_date)].copy()
    f2 = df2[(df2['Date_Parsed'].dt.date >= start_date) & (df2['Date_Parsed'].dt.date <= end_date)].copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)
    
    # Financial Extraction for Potential Contract Value (Sheet 1)
    if 'Packageoffered' in f1.columns:
        f1['Potential_Val'] = f1['Packageoffered'].apply(calculate_standardized_revenue)
    else:
        f1['Potential_Val'] = 0.0

    # Financial Extraction for Actual Revenue (Sheet 2)
    # Checking for common revenue column names in Sparta2
    rev_col_candidates = ['Revenue', 'Package', 'Amount', 'Sale Value']
    actual_rev_col = next((c for c in rev_col_candidates if c in f2.columns), None)
    
    if actual_rev_col:
        f2['Actual_Rev'] = f2[actual_rev_col].apply(calculate_standardized_revenue)
    else:
        f2['Actual_Rev'] = 0.0

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    formatted_live = [name.strip().title() for name in LIVE_AGENTS]

    sort_options = {
        "Total Applications (High to Low)": "Total Applications", 
        "Quality: Approved": "Qual_Approved", 
        "Quality: Cancelled": "Qual_Cancelled", 
        "Live Status: Live": "Port_Live", 
        "Advisor Name (A-Z)": "index"
    }
    
    app_counts_base = f1.groupby('Advisor').size().to_frame('Total Applications')
    qual_counts_base = f1.groupby(['Advisor', 'Q_Status']).size().unstack(fill_value=0).add_prefix('Qual_')
    port_counts_base = f2.groupby(['Advisor', 'P_Status']).size().unstack(fill_value=0).add_prefix('Port_')
    master_base = pd.DataFrame(index=all_advisors).join([app_counts_base, qual_counts_base, port_counts_base]).fillna(0)

    available_sorts = [k for k, v in sort_options.items() if v == "index" or v in master_base.columns]
    selected_sort_label = col_c.selectbox("Master Sort (Aligns all tables):", available_sorts)

    # --- TAB NAVIGATION ---
    tab1, tab2, tab3 = st.tabs(["📊 Team Overview", "👤 Individual Performance", "💰 Financials"])

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
            st.dataframe(
                final_df[['Total Applications']].style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(advisor_indices, 'Total Applications')), 
                use_container_width=True, height=500,
                column_config={"Total Applications": st.column_config.Column(help=TABLE_TOOLTIPS["Total Applications"])}
            )
        
        with c2:
            st.subheader("✅ Quality Audit")
            q_cols = [c for c in final_df.columns if c.startswith('Qual_')]
            if q_cols:
                q_order = ['Qual_Approved', 'Qual_Rework', 'Qual_Cancelled', 'Qual_Others']
                actual_q_order = [c for c in q_order if c in q_cols]
                disp_qual_num = final_df[actual_q_order].rename(columns=lambda x: x.replace('Qual_', ''))
                disp_qual_str = format_with_pct(disp_qual_num, final_df['Total Applications'])
                styler_q = disp_qual_str.style
                for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                    if col in disp_qual_num.columns:
                        styler_q = styler_q.background_gradient(subset=(advisor_indices, col), cmap=cmap, gmap=disp_qual_num[col])
                
                st.dataframe(
                    styler_q, use_container_width=True, height=500,
                    column_config={col: st.column_config.Column(help=TABLE_TOOLTIPS.get(col, "")) for col in disp_qual_num.columns}
                )
            else:
                st.info("No quality data available.")
            
        with c3:
            st.subheader("🌐 Live Status")
            p_cols = [c for c in final_df.columns if c.startswith('Port_')]
            if p_cols:
                p_order = ['Port_Live', 'Port_Committed', 'Port_Cancelled', 'Port_Others']
                actual_p_order = [c for c in p_order if c in p_cols]
                disp_port_num = final_df[actual_p_order].rename(columns=lambda x: x.replace('Port_', ''))
                disp_port_str = format_with_pct(disp_port_num, final_df['Total Applications'])
                styler_p = disp_port_str.style
                for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
                    if col in disp_port_num.columns:
                        styler_p = styler_p.background_gradient(subset=(advisor_indices, col), cmap=cmap, gmap=disp_port_num[col])
                
                st.dataframe(
                    styler_p, use_container_width=True, height=500,
                    column_config={col: st.column_config.Column(help=TABLE_TOOLTIPS.get(col, "")) for col in disp_port_num.columns}
                )
            else:
                st.info("No live status data available.")

    with tab2:
        st.subheader("👤 Detailed Agent Analysis")
        col_check, col_select = st.columns([1, 3])
        show_live_only = col_check.checkbox("Show current roster only", value=False, key="individual_roster_filter")
        dropdown_list = [n for n in all_advisors if n in formatted_live] if show_live_only else all_advisors
        selected_agent = col_select.selectbox("Select Agent:", dropdown_list if dropdown_list else all_advisors)
        
        if selected_agent:
            ag1 = f1[f1['Advisor'] == selected_agent].copy()
            ag2 = f2[f2['Advisor'] == selected_agent].copy()
            total_apps = len(ag1)
            approved = len(ag1[ag1['Q_Status'] == 'Approved'])
            approval_rate = f"{(approved / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            total_committed_apps = len(ag2) 
            committed_rate = f"{(total_committed_apps / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            live = len(ag2[ag2['P_Status'] == 'Live'])
            live_rate = f"{(live / total_committed_apps * 100):.1f}%" if total_committed_apps > 0 else "0.0%"
            
            with st.container(border=True):
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                m1.metric("📝 Tot. Applications", f"{total_apps:,}")
                m2.metric("✅ Quality Approv.", f"{approved:,}")
                m3.metric("📈 Approv. Rate", approval_rate)
                m4.metric("📦 Commit. Apps", f"{total_committed_apps:,}")
                m5.metric("📋 Commit. Rate", committed_rate)
                m6.metric("🌐 Total Live", f"{live:,}")
                m7.metric("🚀 Live Rate", live_rate)

    # --- UPDATED: FINANCIALS TAB (TAB 3) ---
    with tab3:
        st.subheader("💰 Financial Performance & Contract Value")
        
        # Determine whether to use the filtered team or all data
        fin_f1 = f1_team if show_live_team else f1
        fin_f2 = f2_team if show_live_team else f2
        
        # Summary Metrics
        total_potential = fin_f1['Potential_Val'].sum()
        total_actual_rev = fin_f2['Actual_Rev'].sum()
        avg_potential = fin_f1['Potential_Val'].mean() if len(fin_f1) > 0 else 0
        
        with st.container(border=True):
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("Potential Contract Value", f"£{total_potential:,.2f}", help="Total value of packages offered (Sheet 1)")
            fc2.metric("Confirmed Revenue", f"£{total_actual_rev:,.2f}", help="Total revenue from Committed/Live records (Sheet 2)")
            fc3.metric("Avg. Potential Value", f"£{avg_potential:,.2f}")
            
        st.divider()
        
        view_mode_fin = st.radio("Breakdown By:", ["Daily", "Monthly", "Advisor"], horizontal=True, key="fin_view")
        col_fin1, col_fin2 = st.columns([1, 1.5])
        
        # Process data for table
        if view_mode_fin == "Daily":
            p_grp = fin_f1.groupby(fin_f1['Date_Parsed'].dt.date)['Potential_Val'].sum()
            r_grp = fin_f2.groupby(fin_f2['Date_Parsed'].dt.date)['Actual_Rev'].sum()
        elif view_mode_fin == "Monthly":
            p_grp = fin_f1.groupby(fin_f1['Date_Parsed'].dt.to_period('M'))['Potential_Val'].sum()
            r_grp = fin_f2.groupby(fin_f2['Date_Parsed'].dt.to_period('M'))['Actual_Rev'].sum()
            p_grp.index = p_grp.index.strftime('%b %Y')
            r_grp.index = r_grp.index.strftime('%b %Y')
        else: # Advisor
            p_grp = fin_f1.groupby('Advisor')['Potential_Val'].sum()
            r_grp = fin_f2.groupby('Advisor')['Actual_Rev'].sum()

        fin_table = pd.DataFrame({
            "Potential Value (£)": p_grp,
            "Revenue (£)": r_grp
        }).fillna(0)
        
        if view_mode_fin == "Advisor":
            fin_table = fin_table.sort_values(by="Revenue (£)", ascending=False)

        with col_fin1:
            st.markdown(f"#### 📊 {view_mode_fin} Data")
            st.dataframe(
                fin_table.style.format("£{:,.2f}").background_gradient(cmap='Greens', subset=['Revenue (£)']),
                use_container_width=True, height=450
            )
            
        with col_fin2:
            st.markdown(f"#### 📈 {view_mode_fin} Comparison")
            if not fin_table.empty:
                chart_df = fin_table.reset_index()
                x_col = chart_df.columns[0]
                
                fig_fin = go.Figure()
                if view_mode_fin == "Advisor":
                    fig_fin.add_trace(go.Bar(x=chart_df[x_col], y=chart_df['Potential Value (£)'], name="Potential Value", marker_color='rgba(156, 163, 175, 0.5)'))
                    fig_fin.add_trace(go.Bar(x=chart_df[x_col], y=chart_df['Revenue (£)'], name="Revenue", marker_color='#059669'))
                else:
                    fig_fin.add_trace(go.Scatter(x=chart_df[x_col], y=chart_df['Potential Value (£)'], name="Potential Value", line=dict(color='gray', dash='dash')))
                    fig_fin.add_trace(go.Scatter(x=chart_df[x_col], y=chart_df['Revenue (£)'], name="Revenue", fill='tozeroy', line=dict(color='#059669', width=3)))
                    
                fig_fin.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_fin, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
