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
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import requests

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

@st.cache_data
def get_lat_lon(postcode):
    """Fetches coordinates for UK postcodes using postcodes.io API"""
    if not postcode or postcode == "Unknown":
        return None, None
    try:
        url = f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data['result']['latitude'], data['result']['longitude']
    except:
        pass
    return None, None

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
    match = re.search(r'£?\s*(\d+(?:\.\d+)?)', s)
    if match:
        amount = float(match.group(1))
        if 'inc' not in s: 
            amount = amount * 1.20
        return amount
    return 0.0

# --- ADDRESS PARSING ENGINE ---
def parse_address(val):
    s = str(val)
    s = re.sub(r'^Address', '', s, flags=re.IGNORECASE).strip()
    pc_match = re.search(r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})', s, re.IGNORECASE)
    postcode = pc_match.group(1).upper() if pc_match else "Unknown"
    if postcode != "Unknown" and " " not in postcode:
        postcode = postcode[:-3] + " " + postcode[-3:]
    country = "England"
    pc_area = ""
    if postcode != "Unknown":
        pc_area_match = re.match(r'^([A-Z]{1,2})', postcode)
        if pc_area_match:
            pc_area = pc_area_match.group(1)
            scotland = ['AB','DD','DG','EH','FK','G','HS','IV','KA','KW','KY','ML','PA','PH','TD','ZE']
            wales = ['CF','LL','NP','SA']
            if pc_area in scotland: country = "Scotland"
            elif pc_area in wales: country = "Wales"
            elif pc_area == 'BT': country = "Northern Ireland"
    city = "Unknown"
    county = "Unknown"
    clean_s = s
    if pc_match:
        clean_s = s[:pc_match.start()].strip()
    clean_s = re.sub(r'[0-9,\s]+$', '', clean_s)
    if ',' in clean_s:
        parts = [p.strip() for p in clean_s.split(',') if p.strip()]
        if len(parts) >= 2:
            county = parts[-1].title()
            city = parts[-2].title()
        elif len(parts) == 1:
            city = parts[0].title()
    else:
        words = clean_s.split()
        if len(words) >= 1:
            city = words[-1].title()
        if len(words) >= 2:
            county = words[-2].title()
    return pd.Series([country, county, city, postcode])

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
    
    if 'Packageoffered' in f1.columns:
        f1['Standardized_Rev'] = f1['Packageoffered'].apply(calculate_standardized_revenue)
    else:
        f1['Standardized_Rev'] = 0.0
    if 'PlanTariff' in f2.columns:
        f2['Standardized_Rev'] = f2['PlanTariff'].apply(calculate_standardized_revenue)
    else:
        f2['Standardized_Rev'] = 0.0

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

    # --- TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Team Overview", "👤 Individual Performance", "💰 Financials", "📍 Locations"])

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
                st.dataframe(styler_q, use_container_width=True, height=500, column_config={col: st.column_config.Column(help=TABLE_TOOLTIPS.get(col, "")) for col in disp_qual_num.columns})
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
                st.dataframe(styler_p, use_container_width=True, height=500, column_config={col: st.column_config.Column(help=TABLE_TOOLTIPS.get(col, "")) for col in disp_port_num.columns})
            else:
                st.info("No live status data available.")
        st.write("### 📥 Download Team Report")
        e_col1, e_col2, e_col3 = st.columns(3)
        export_vol = final_df[['Total Applications']]
        export_qual = disp_qual_str if q_cols else pd.DataFrame()
        export_live = disp_port_str if p_cols else pd.DataFrame()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_vol.to_excel(writer, sheet_name='Applications_Volume')
            if not export_qual.empty: export_qual.to_excel(writer, sheet_name='Quality_Audit')
            if not export_live.empty: export_live.to_excel(writer, sheet_name='Live_Status')
        e_col1.download_button(label="Excel (All Tables)", data=output.getvalue(), file_name=f"Sparta_Team_Report_{start_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        combined_csv = "APPLICATIONS VOLUME\n" + export_vol.to_csv() + "\nQUALITY AUDIT\n" + export_qual.to_csv() + "\nLIVE STATUS\n" + export_live.to_csv()
        e_col2.download_button(label="CSV (Combined Tables)", data=combined_csv, file_name=f"Sparta_Team_Report_{start_date}.csv", mime="text/csv")
        pdf_bytes = generate_formatted_pdf(start_date, end_date, export_vol, export_qual, export_live)
        e_col3.download_button(label="PDF (Formatted Tables)", data=pdf_bytes, file_name=f"Sparta_Team_Report_{start_date}.pdf", mime="application/pdf")
        st.divider()
        st.subheader("📈 Team Performance Trends")
        tg_1, tg_2 = st.columns(2)
        with tg_1:
            if not f1_team.empty:
                daily_v = f1_team.groupby(f1_team['Date_Parsed'].dt.date).size().reset_index(name='Apps')
                daily_q = f1_team[f1_team['Q_Status'] == 'Approved'].groupby(f1_team['Date_Parsed'].dt.date).size().reset_index(name='Approved')
                combined = pd.merge(daily_v, daily_q, on='Date_Parsed', how='left').fillna(0)
                combined['Date_Parsed'] = combined['Date_Parsed'].astype(str)
                fig_single = go.Figure()
                fig_single.add_trace(go.Bar(x=combined['Date_Parsed'], y=combined['Apps'], name="Total Apps", marker_color='#1E3A8A'))
                fig_single.add_trace(go.Scatter(x=combined['Date_Parsed'], y=combined['Approved'], name="Approved (Audit)", line=dict(color='#2E7D32', width=3)))
                fig_single.update_layout(title_text="Daily Apps vs. Quality Approval", hovermode="x unified")
                st.plotly_chart(fig_single, use_container_width=True)
            else:
                st.info("No application trend data for this period.")
        with tg_2:
            available_cols = [c for c in ['Port_Live', 'Port_Cancelled'] if c in master.columns]
            if available_cols:
                status_plot = master[available_cols].rename(columns={'Port_Live':'Live', 'Port_Cancelled':'Cancelled'}).reset_index()
                fig_status = px.bar(status_plot, x='index', y=[c.replace('Port_', '') for c in available_cols], barmode='group', color_discrete_map={'Live': '#2563EB', 'Cancelled': '#DC2626'}, title="Agent-wise Live vs. Cancelled Volume")
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("No Live/Cancelled records found for this selection.")

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
                m1.metric("📝 Tot. Applications", f"{total_apps:,}", help=KPI_DEFS["total_apps"])
                m2.metric("✅ Quality Approv.", f"{approved:,}", help=KPI_DEFS["qual_approved"])
                m3.metric("📈 Approv. Rate", approval_rate, help=KPI_DEFS["approv_rate"])
                m4.metric("📦 Commit. Apps", f"{total_committed_apps:,}", help=KPI_DEFS["commit_apps"])
                m5.metric("📋 Commit. Rate", committed_rate, help=KPI_DEFS["commit_rate"])
                m6.metric("🌐 Total Live", f"{live:,}", help=KPI_DEFS["total_live"])
                m7.metric("🚀 Live Rate", live_rate, help=KPI_DEFS["live_rate"])
            st.divider()
            view_mode = st.radio("View Breakdown By:", ["Daily", "Monthly"], horizontal=True)
            if view_mode == "Monthly":
                ag1['Period'] = ag1['Date_Parsed'].dt.to_period('M')
                ag2['Period'] = ag2['Date_Parsed'].dt.to_period('M')
            else:
                ag1['Period'] = ag1['Date_Parsed'].dt.date
                ag2['Period'] = ag2['Date_Parsed'].dt.date
            st.write(f"**{view_mode}** breakdown for **{selected_agent}**")
            ca, cb, cc = st.columns([1, 1.8, 1.8])
            with ca:
                st.markdown(f"#### 📊 {view_mode} Applications")
                if not ag1.empty:
                    daily_apps = ag1.groupby('Period').size().to_frame('Applications')
                    if view_mode == "Monthly": daily_apps.index = daily_apps.index.strftime('%b %Y')
                    t_apps = daily_apps.sum().to_frame().T
                    t_apps.index = ["TOTAL"]
                    df_apps = pd.concat([daily_apps, t_apps])
                    st.dataframe(df_apps.style.format("{:,.0f}").background_gradient(cmap='Greens', subset=(daily_apps.index, 'Applications')), use_container_width=True, column_config={"Applications": st.column_config.Column(help=TABLE_TOOLTIPS["Applications"])})
                else:
                    st.info("No applications found.")
            with cb:
                st.markdown("#### ✅ Quality Audit")
                if not ag1.empty:
                    daily_qual = ag1.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
                    q_order = ['Approved', 'Rework', 'Cancelled', 'Others']
                    actual_q = [c for c in q_order if c in daily_qual.columns]
                    dq_num = daily_qual[actual_q]
                    if view_mode == "Monthly": dq_num.index = dq_num.index.strftime('%b %Y')
                    row_totals = daily_apps['Applications']
                    dq_str = format_with_pct(dq_num, row_totals)
                    t_qual_num = dq_num.sum().to_frame().T
                    t_qual_num.index = ["TOTAL"]
                    t_qual_str = format_with_pct(t_qual_num, pd.Series([total_apps], index=["TOTAL"]))
                    final_q_str = pd.concat([dq_str, t_qual_str])
                    styler_dq = final_q_str.style
                    for col, cmap in [('Approved', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
                        if col in dq_num.columns: styler_dq = styler_dq.background_gradient(subset=(dq_num.index, col), cmap=cmap, gmap=dq_num[col])
                    st.dataframe(styler_dq, use_container_width=True, column_config={col: st.column_config.Column(help=TABLE_TOOLTIPS.get(col, "")) for col in dq_num.columns})
                else:
                    st.info("No quality records.")
            with cc:
                st.markdown("#### 🌐 Live Status")
                if not ag2.empty:
                    daily_port = ag2.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
                    p_order = ['Live', 'Committed', 'Cancelled', 'Others']
                    actual_p = [c for c in p_order if c in daily_port.columns]
                    dp_num = daily_port[actual_p]
                    if view_mode == "Monthly": dp_num.index = dp_num.index.strftime('%b %Y')
                    dp_str = format_with_pct(dp_num, row_totals)
                    t_port_num = dp_num.sum().to_frame().T
                    t_port_num.index = ["TOTAL"]
                    t_port_str = format_with_pct(t_port_num, pd.Series([total_apps], index=["TOTAL"]))
                    final_p_str = pd.concat([dp_str, t_port_str])
                    styler_dp = final_p_str.style
                    for col, cmap in [('Live', 'Blues'), ('Cancelled', 'Reds'), ('Committed', 'Purples')]:
                        if col in dp_num.columns: styler_dp = styler_dp.background_gradient(subset=(dp_num.index, col), cmap=cmap, gmap=dp_num[col])
                    st.dataframe(styler_dp, use_container_width=True, column_config={col: st.column_config.Column(help=TABLE_TOOLTIPS.get(col, "")) for col in dp_num.columns})
                else:
                    st.info("No live status records found for this agent.")
            st.divider()
            st.subheader(f"📈 Performance Trends: {selected_agent}")
            if not ag1.empty:
                d_apps = ag1.groupby('Period').size().to_frame('Total Apps')
                d_comm = ag2.groupby('Period').size().to_frame('Committed')
                d_appr = ag1[ag1['Q_Status'] == 'Approved'].groupby('Period').size().to_frame('Approved')
                d_live = ag2[ag2['P_Status'] == 'Live'].groupby('Period').size().to_frame('Live')
                i_comb = d_apps.join([d_comm, d_appr, d_live], how='left').fillna(0).reset_index()
                i_comb['Period'] = i_comb['Period'].astype(str)
                ig1, ig2 = st.columns(2)
                with ig1:
                    fig1 = go.Figure()
                    fig1.add_trace(go.Bar(x=i_comb['Period'], y=i_comb['Total Apps'], name="Total Apps", marker_color='#60A5FA'))
                    fig1.add_trace(go.Scatter(x=i_comb['Period'], y=i_comb['Approved'], name="Quality Approved", line=dict(color='#059669', width=3)))
                    fig1.update_layout(title="Apps vs Quality Approved", hovermode="x unified")
                    st.plotly_chart(fig1, use_container_width=True)
                with ig2:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(x=i_comb['Period'], y=i_comb['Committed'], name="Commit. Apps", marker_color='#8B5CF6'))
                    fig2.add_trace(go.Scatter(x=i_comb['Period'], y=i_comb['Live'], name="Live", line=dict(color='#F59E0B', width=3)))
                    fig2.update_layout(title="Committed vs Live", hovermode="x unified")
                    st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.subheader("💰 Revenue & Financial Insights (Standardized 20% VAT Inclusive)")
        show_live_fin = st.checkbox("Show current roster only", value=False, key="fin_roster_filter")
        fin_df = f2[f2['Advisor'].isin(formatted_live)].copy() if show_live_fin else f2.copy()
        live_df = fin_df[fin_df['P_Status'] == 'Live']
        total_committed_mrr = fin_df['Standardized_Rev'].sum()
        total_live_mrr = live_df['Standardized_Rev'].sum()
        total_committed_sales = len(fin_df)
        with st.container(border=True):
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("Gross Committed MRR (Total Value)", f"£{total_committed_mrr:,.2f}")
            fc2.metric("Actual Live MRR (Confirmed Live)", f"£{total_live_mrr:,.2f}")
            fc3.metric("Total Committed Packages", f"{total_committed_sales:,}")
        st.divider()
        view_mode_fin = st.radio("Financial Breakdown By:", ["Daily", "Monthly", "Advisor"], horizontal=True, key="fin_view")
        col_fin1, col_fin2 = st.columns([1, 1.5])
        with col_fin1:
            st.markdown(f"#### 📊 {view_mode_fin} Revenue Table")
            if view_mode_fin == "Daily":
                group_col = fin_df['Date_Parsed'].dt.date
                group_col_live = live_df['Date_Parsed'].dt.date
            elif view_mode_fin == "Monthly":
                group_col = fin_df['Date_Parsed'].dt.to_period('M')
                group_col_live = live_df['Date_Parsed'].dt.to_period('M')
            else:
                group_col = fin_df['Advisor']
                group_col_live = live_df['Advisor']
            comm_group = fin_df.groupby(group_col)['Standardized_Rev'].sum().to_frame("Committed Revenue (£)")
            live_group = live_df.groupby(group_col_live)['Standardized_Rev'].sum().to_frame("Live Revenue (£)")
            fin_group = comm_group.join(live_group, how='outer').fillna(0)
            if view_mode_fin == "Monthly": fin_group.index = fin_group.index.strftime('%b %Y')
            elif view_mode_fin == "Advisor": fin_group = fin_group.sort_values(by="Committed Revenue (£)", ascending=False)
            st.dataframe(fin_group.style.format("£{:,.2f}").background_gradient(cmap='Greens', subset=['Committed Revenue (£)']).background_gradient(cmap='YlOrBr', subset=['Live Revenue (£)']), use_container_width=True, height=450)
        with col_fin2:
            st.markdown(f"#### 📈 {view_mode_fin} Revenue Trend")
            if not fin_group.empty:
                chart_df = fin_group.reset_index()
                x_col = chart_df.columns[0]
                fig_fin = go.Figure()
                if view_mode_fin == "Advisor": fig_fin.add_trace(go.Bar(x=chart_df[x_col], y=chart_df['Committed Revenue (£)'], name="Committed Revenue", marker_color='#059669'))
                else: fig_fin.add_trace(go.Scatter(x=chart_df[x_col], y=chart_df['Committed Revenue (£)'], name="Committed Revenue", fill='tozeroy', line=dict(color='#059669'), fillcolor='rgba(5, 150, 105, 0.2)'))
                fig_fin.add_trace(go.Scatter(x=chart_df[x_col], y=chart_df['Live Revenue (£)'], name="Live Revenue", line=dict(color='#D97706', width=3), mode='lines+markers'))
                fig_fin.update_layout(xaxis_title="", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_fin, use_container_width=True)
            else:
                st.info("No financial data found to plot.")

    # --- NEW: LOCATIONS TAB (TAB 4) ---
    with tab4:
        st.subheader("📍 Geographical Locations & Demographics")
        if 'Address' in f2.columns:
            if 'Postcode' not in f2.columns:
                f2[['Country', 'County', 'City', 'Postcode']] = f2['Address'].apply(parse_address)
            geo_df = f2.copy()
            st.write("### Filter Demographics")
            fc1, fc2, fc3, fc4 = st.columns(4)
            countries = sorted(geo_df['Country'].unique().tolist())
            selected_country = fc1.multiselect("Country", countries, default=countries)
            if selected_country: geo_df = geo_df[geo_df['Country'].isin(selected_country)]
            counties = sorted(geo_df['County'].unique().tolist())
            selected_county = fc2.multiselect("County", counties)
            if selected_county: geo_df = geo_df[geo_df['County'].isin(selected_county)]
            cities = sorted(geo_df['City'].unique().tolist())
            selected_city = fc3.multiselect("City", cities)
            if selected_city: geo_df = geo_df[geo_df['City'].isin(selected_city)]
            postcodes = sorted(geo_df['Postcode'].unique().tolist())
            selected_pc = fc4.multiselect("Postcode", postcodes)
            if selected_pc: geo_df = geo_df[geo_df['Postcode'].isin(selected_pc)]
            
            st.divider()
            
            # --- MAP INTEGRATION ---
            st.write("#### 🗺️ Campaign Map (Live vs Cancelled)")
            map_data = geo_df[geo_df['Postcode'] != "Unknown"].copy()
            if not map_data.empty:
                # Add Lat/Lon to unique postcodes to speed up loading
                unique_pcs = map_data['Postcode'].unique()
                coords_map = {pc: get_lat_lon(pc) for pc in unique_pcs}
                map_data['lat'] = map_data['Postcode'].map(lambda x: coords_map[x][0])
                map_data['lon'] = map_data['Postcode'].map(lambda x: coords_map[x][1])
                map_data = map_data.dropna(subset=['lat', 'lon'])

                if not map_data.empty:
                    m = folium.Map(location=[54.0, -2.0], zoom_start=6, tiles="CartoDB positron")
                    marker_cluster = MarkerCluster().add_to(m)

                    for _, row in map_data.iterrows():
                        color = 'green' if row['P_Status'] == 'Live' else 'red' if row['P_Status'] == 'Cancelled' else 'orange' if row['P_Status'] == 'Committed' else 'gray'
                        popup_text = f"<b>Advisor:</b> {row['Advisor']}<br><b>Status:</b> {row['P_Status']}<br><b>City:</b> {row['City']}<br><b>Rev:</b> £{row['Standardized_Rev']:.2f}"
                        folium.Marker(
                            location=[row['lat'], row['lon']],
                            popup=folium.Popup(popup_text, max_width=200),
                            icon=folium.Icon(color=color, icon='info-sign')
                        ).add_to(marker_cluster)
                    
                    st_folium(m, width="100%", height=500)
                else:
                    st.info("No coordinates found for the selected postcodes.")
            else:
                st.info("No valid addresses available for mapping.")

            st.divider()
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Total Applications in Region", f"{len(geo_df):,}")
            mc2.metric("Regional Live Revenue", f"£{geo_df[geo_df['P_Status']=='Live']['Standardized_Rev'].sum():,.2f}")
            top_city = geo_df['City'].mode()[0] if not geo_df.empty else "N/A"
            mc3.metric("Top City by Volume", top_city)
            vc1, vc2 = st.columns(2)
            with vc1:
                st.write("#### 🏙️ Top Cities Pipeline")
                if not geo_df.empty:
                    city_group = geo_df.groupby('City').agg(
                        Total_Apps=('Advisor', 'count'),
                        Live_Apps=('P_Status', lambda x: (x == 'Live').sum()),
                        Live_Revenue=('Standardized_Rev', lambda x: x[geo_df['P_Status'] == 'Live'].sum())
                    ).sort_values('Total_Apps', ascending=False).reset_index()
                    st.dataframe(city_group.style.format({'Live_Revenue': '£{:,.2f}'}).background_gradient(cmap='Blues'), use_container_width=True)
                else: st.info("No data for current selection.")
            with vc2:
                st.write("#### 📮 Postcode Breakdown")
                if not geo_df.empty:
                    pc_group = geo_df.groupby('Postcode').agg(
                        Total_Apps=('Advisor', 'count'),
                        Live_Apps=('P_Status', lambda x: (x == 'Live').sum()),
                        Live_Revenue=('Standardized_Rev', lambda x: x[geo_df['P_Status'] == 'Live'].sum())
                    ).sort_values('Total_Apps', ascending=False).reset_index()
                    st.dataframe(pc_group.style.format({'Live_Revenue': '£{:,.2f}'}).background_gradient(cmap='Greens'), use_container_width=True)
                else: st.info("No data for current selection.")
        else:
            st.warning("No 'Address' column found in the Sparta2 dataset. Please ensure the column is named 'Address'.")

except Exception as e:
    st.error(f"Error: {e}")
