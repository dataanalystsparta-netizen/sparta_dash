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

# Custom CSS for high-contrast headers, dark fonts, and general layout
st.markdown("""
   <style>
   .block-container { max-width: 98%; padding-top: 5rem; }
    h3 { margin-bottom: 0.5rem !important; font-size: 1.2rem !important; color: #1E3A8A; }
   .last-updated { font-size: 0.8rem; color: gray; text-align: right; }
   [data-testid="stMetricValue"] { font-size: 1.6rem !important; color: #059669; }
   [data-testid="stMetricLabel"] { font-size: 0.85rem !important; white-space: nowrap; }
   /* Apply high-contrast yellow headers */
   th { background-color: #FFEA00 !important; color: #111827 !important; font-weight: bold !important; }
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
    if any(x in s for x in ['appr', 'pass']): return 'Approve'
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
    match = re.search(r'£\s*(\d+(?:\.\d+)?)', s)
    if match:
        amount = float(match.group(1))
        if 'inc' not in s: 
            amount = amount * 1.20
        return amount
    return 0.0

# --- PDF FORMATTING ENGINE ---
def generate_formatted_pdf(period_label, df_vol, df_qual, df_live):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, f"Sparta Team Report: {period_label}", ln=True, align='C')
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
   "qual_approve": "Applications that have successfully passed the Quality Audit process.",
   "approv_rate": "Percentage of total applications that reached 'Approve' status.",
   "commit_apps": "Total applications that got 'Committed'.",
   "commit_rate": "Percentage of applications that got 'Committed'",
   "total_live": "Total applications that got 'Live'.",
   "live_rate": "Conversion rate from Committed applications to confirmed Live records."
}

TABLE_TOOLTIPS = {
    "Total Applications": "Grand total of all applications logged by the advisor.",
    "Applications": "Number of applications logged for this specific period.",
    "Approve": "Applications that have cleared the Quality Audit process.",
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
        st.title("Sparta Agent Performance Dashboard")
        
    col_time.markdown(f"<p class='last-updated'>Data Last Synced:<br><b>{last_sync}</b></p>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([1, 1, 1.5])
    
    # Implementing the interactive Month Dropdown instead of pure dates
    df1['Month_Year'] = df1['Date_Parsed'].dt.strftime('%b %Y').fillna('Unknown Date')
    df2['Month_Year'] = df2['Date_Parsed'].dt.strftime('%b %Y').fillna('Unknown Date')
    
    available_months = sorted([m for m in df1['Month_Year'].unique() if m != 'Unknown Date'], reverse=True)
    selected_month = col_a.selectbox("Filter by Month:", ["All Time"] + available_months)

    if selected_month != "All Time":
        f1 = df1[df1['Month_Year'] == selected_month].copy()
        f2 = df2[df2['Month_Year'] == selected_month].copy()
    else:
        f1 = df1.copy()
        f2 = df2.copy()

    f1['Q_Status'] = f1['Quality Status'].apply(map_quality)
    f2['P_Status'] = f2['Status'].apply(map_portal)
    
    # Process Financials cleanly if column exists
    if 'Packageoffered' in f1.columns:
        f1['Standardized_Rev'] = f1['Packageoffered'].apply(calculate_standardized_revenue)
    else:
        f1['Standardized_Rev'] = 0.0

    all_advisors = sorted(list(set(f1['Advisor'].unique()) | set(f2['Advisor'].unique())))
    formatted_live = [name.strip().title() for name in LIVE_AGENTS]

    sort_options = {
        "Total Applications (High to Low)": "Total Applications", 
        "Quality: Approve": "Qual_Approve", 
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
        team_approve = len(f1_team[f1_team['Q_Status'] == 'Approve'])
        team_approv_rate = f"{(team_approve / team_apps * 100):.1f}%" if team_apps > 0 else "0.0%"
        team_committed = len(f2_team)
        team_commit_rate = f"{(team_committed / team_apps * 100):.1f}%" if team_apps > 0 else "0.0%"
        team_live = len(f2_team[f2_team['P_Status'] == 'Live'])
        team_live_rate = f"{(team_live / team_committed * 100):.1f}%" if team_committed > 0 else "0.0%"

        with st.container(border=True):
            tm1, tm2, tm3, tm4, tm5, tm6, tm7 = st.columns(7)
            tm1.metric("📝 Tot. Applications", f"{team_apps:,}", help=KPI_DEFS["total_apps"])
            tm2.metric("✅ Quality Approve", f"{team_approve:,}", help=KPI_DEFS["qual_approve"])
            tm3.metric("📈 Approve Rate", team_approv_rate, help=KPI_DEFS["approv_rate"])
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
                q_order = ['Qual_Approve', 'Qual_Rework', 'Qual_Cancelled', 'Qual_Others']
                actual_q_order = [c for c in q_order if c in q_cols]
                disp_qual_num = final_df[actual_q_order].rename(columns=lambda x: x.replace('Qual_', ''))
                disp_qual_str = format_with_pct(disp_qual_num, final_df['Total Applications'])
                styler_q = disp_qual_str.style
                for col, cmap in [('Approve', 'YlGn'), ('Cancelled', 'Reds'), ('Rework', 'Wistia')]:
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

        # --- EXPORT SECTION ---
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
        e_col1.download_button(label="Excel (All Tables)", data=output.getvalue(), file_name=f"Sparta_Team_Report_{selected_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        combined_csv = "APPLICATIONS VOLUME\n" + export_vol.to_csv() + "\nQUALITY AUDIT\n" + export_qual.to_csv() + "\nLIVE STATUS\n" + export_live.to_csv()
        e_col2.download_button(label="CSV (Combined Tables)", data=combined_csv, file_name=f"Sparta_Team_Report_{selected_month}.csv", mime="text/csv")
        pdf_bytes = generate_formatted_pdf(selected_month, export_vol, export_qual, export_live)
        e_col3.download_button(label="PDF (Formatted Tables)", data=pdf_bytes, file_name=f"Sparta_Team_Report_{selected_month}.pdf", mime="application/pdf")

        st.divider()
        st.subheader("📈 Team Performance Trends (Agent-Wise)")
        tg_1, tg_2 = st.columns(2)
        with tg_1:
            if not f1_team.empty:
                # Strictly grouped by Advisor, stripping out time dimensions
                agent_v = f1_team.groupby('Advisor').size().reset_index(name='Apps')
                agent_q = f1_team[f1_team['Q_Status'] == 'Approve'].groupby('Advisor').size().reset_index(name='Approve')
                combined = pd.merge(agent_v, agent_q, on='Advisor', how='left').fillna(0)
                
                fig_single = go.Figure()
                fig_single.add_trace(go.Bar(x=combined['Advisor'], y=combined['Apps'], name="Total Apps", marker_color='#1E3A8A'))
                fig_single.add_trace(go.Scatter(x=combined['Advisor'], y=combined['Approve'], name="Approve (Audit)", line=dict(color='#2E7D32', width=3)))
                fig_single.update_layout(title_text="Agent-Wise Apps vs. Quality Approve", hovermode="x unified")
                st.plotly_chart(fig_single, use_container_width=True)
            else:
                st.info("No application trend data for this period.")
        with tg_2:
            available_cols = [c for c in ['Port_Live', 'Port_Cancelled'] if c in master.columns]
            if available_cols:
                status_plot = master[available_cols].rename(columns={'Port_Live':'Live', 'Port_Cancelled':'Cancelled'}).reset_index()
                fig_status = px.bar(status_plot, x='index', y=[c.replace('Port_', '') for c in available_cols], barmode='group', color_discrete_map={'Live': '#2563EB', 'Cancelled': '#DC2626'}, title="Agent-Wise Live vs. Cancelled Volume")
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
            approve = len(ag1[ag1['Q_Status'] == 'Approve'])
            approval_rate = f"{(approve / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            total_committed_apps = len(ag2) 
            committed_rate = f"{(total_committed_apps / total_apps * 100):.1f}%" if total_apps > 0 else "0.0%"
            live = len(ag2[ag2['P_Status'] == 'Live'])
            live_rate = f"{(live / total_committed_apps * 100):.1f}%" if total_committed_apps > 0 else "0.0%"
            
            with st.container(border=True):
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                m1.metric("📝 Tot. Applications", f"{total_apps:,}", help=KPI_DEFS["total_apps"])
                m2.metric("✅ Quality Approve", f"{approve:,}", help=KPI_DEFS["qual_approve"])
                m3.metric("📈 Approve Rate", approval_rate, help=KPI_DEFS["approv_rate"])
                m4.metric("📦 Commit. Apps", f"{total_committed_apps:,}", help=KPI_DEFS["commit_apps"])
                m5.metric("📋 Commit. Rate", committed_rate, help=KPI_DEFS["commit_rate"])
                m6.metric("🌐 Total Live", f"{live:,}", help=KPI_DEFS["total_live"])
                m7.metric("🚀 Live Rate", live_rate, help=KPI_DEFS["live_rate"])

    with tab3:
        st.subheader("💰 Revenue & Financial Insights (Standardized 20% VAT Inclusive)")
        
        fin_df = f1_team if show_live_team else f1
        
        total_mrr = fin_df['Standardized_Rev'].sum()
        avg_revenue = fin_df['Standardized_Rev'].mean() if len(fin_df) > 0 else 0
        total_sales_count = len(fin_df)
        
        with st.container(border=True):
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("Gross MRR (Total Package Value)", f"£{total_mrr:,.2f}")
            fc2.metric("Average Revenue Per Sale (ARPU)", f"£{avg_revenue:,.2f}")
            fc3.metric("Total Packages Sold", f"{total_sales_count:,}")
            
        st.divider()
        
        # Completely Agent-Wise logic enforcing the removal of date dimensions
        fin_group = fin_df.groupby('Advisor')['Standardized_Rev'].sum().to_frame("Revenue (£)").sort_values(by="Revenue (£)", ascending=False)
        
        # Calculating percentage formatting for financials
        if total_mrr > 0:
            fin_group['% of Total Revenue'] = (fin_group['Revenue (£)'] / total_mrr * 100).apply(lambda x: f"{x:.1f}%")
        else:
            fin_group['% of Total Revenue'] = "0.0%"
        
        col_fin1, col_fin2 = st.columns([1, 1.5])
        
        with col_fin1:
            st.markdown("#### 📊 Agent-Wise Revenue Table")
            st.dataframe(
                fin_group.style.format({"Revenue (£)": "£{:,.2f}"}).background_gradient(cmap='Greens', subset=['Revenue (£)']),
                use_container_width=True,
                height=450
            )
            
        with col_fin2:
            st.markdown("#### 📈 Agent-Wise Revenue Trend")
            if not fin_group.empty:
                chart_df = fin_group.reset_index()
                fig_fin = px.bar(chart_df, x='Advisor', y='Revenue (£)', color='Revenue (£)', color_continuous_scale='Greens')
                fig_fin.update_layout(xaxis_title="", hovermode="x unified")
                st.plotly_chart(fig_fin, use_container_width=True)
            else:
                st.info("No financial data found to plot.")

except Exception as e:
    st.error(f"Error: {e}")
