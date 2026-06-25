import streamlit as st
import pandas as pd
import numpy as np
import datetime
import calendar
import math
import plotly.graph_objects as go

# ==============================================================================
# 1. STREAMLIT PAGE CONFIG & ADVANCED MODERN THEMING
# ==============================================================================
st.set_page_config(
    page_title="Performance Insights & Quality Ledger",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Global CSS Injecting Glassmorphic Cards and Modern UI Elements
st.markdown("""
<style>
    /* Import Premium Clean Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #f8fafc;
        color: #0f172a;
    }
    
    /* Top Header Branding Banner */
    .brand-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
    }
    .brand-banner h1 { margin: 0; font-size: 2.25rem; font-weight: 700; color: white !important; }
    .brand-banner p { margin: 0.5rem 0 0 0; opacity: 0.9; font-size: 1rem; }

    /* Modern Metric KPI Container Grid */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1.25rem;
        margin-bottom: 2rem;
    }
    .kpi-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
    }
    .kpi-title { font-size: 0.85rem; font-weight: 600; color: #64748b; text-transform: uppercase; tracking: 0.05em; margin: 0; }
    .kpi-value { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0.35rem 0; }
    .kpi-subtitle { font-size: 0.8rem; color: #94a3b8; margin: 0; }

    /* Insight Alert Grid & Cards */
    .insight-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1rem;
        margin-top: 0.75rem;
    }
    .insight-card {
        background: white;
        padding: 1.25rem;
        border-radius: 10px;
        border-left: 5px solid #cbd5e1;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .insight-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #64748b; margin: 0; }
    .insight-phrase { font-size: 1.1rem; font-weight: 600; color: #1e293b; margin: 0.25rem 0; }
    .insight-comment { font-size: 0.85rem; color: #475569; margin: 0; line-height: 1.4; }

    /* Performance Tips Callout Box */
    .tips-box {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 2rem;
    }
    .tips-title { font-size: 1.1rem; font-weight: 600; color: #166534; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
    .tips-list { margin: 0; padding-left: 1.25rem; color: #1e293b; font-size: 0.9rem; }
    .tips-list li { margin-bottom: 0.5rem; line-height: 1.5; }
    
    /* Clean DataFrame tweaks */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. PERSISTENT APPLICATION STATE INITIALIZATION
# ==============================================================================
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

today_date = datetime.date.today()

# ==============================================================================
# 3. ROBUST EXPLICIT ENUM STRING MAPPINGS
# ==============================================================================
def map_quality(status_str):
    val = str(status_str).strip().lower() if pd.notna(status_str) else ''
    if any(x in val for x in ['appr', 'pass']): return 'Approved'
    if any(x in val for x in ['rew', 'repro']): return 'Rework'
    if any(x in val for x in ['can', 'drop']): return 'Cancelled'
    if 'rej' in val: return 'Rejected'
    return 'Others'

def map_portal(status_str):
    val = str(status_str).strip().lower() if pd.notna(status_str) else ''
    if 'live' in val: return 'Live'
    if any(x in val for x in ['comm', 'comit']): return 'Committed'
    if any(x in val for x in ['can', 'drop', 'loss', 'lost']): return 'Cancelled'
    return 'Others'

def map_wc(status_str):
    val = str(status_str).strip().lower() if pd.notna(status_str) else ''
    if any(x in val for x in ['done', 'pass', 'comp']): return 'Done'
    if any(x in val for x in ['pend', 'pnd']): return 'Pending'
    if any(x in val for x in ['paper', 'ppw']): return 'Paperwork'
    if any(x in val for x in ['can', 'drop']): return 'Cancelled'
    return 'Others'

# ==============================================================================
# 4. SECURE INTEGRATED GATEWAY & DATA INGESTION FLOW
# ==============================================================================
st.sidebar.image("https://img.icons8.com/fluent/96/000000/dashboard.png", width=60)
st.sidebar.title("Navigation & Secure Control")

secure_key = st.sidebar.text_input("Access Control Key Verification", type="password", help="Enter access signature key to enable analytical processing components.")

if not secure_key:
    st.info("🔒 Secure Key Missing: Please provide your authorization access key signature in the sidebar input to execute data rendering pipelines.")
    st.stop()
else:
    # Retaining logic requirement: Any input acts as positive verification gatepass
    st.session_state.authenticated = True

st.sidebar.markdown("---")
st.sidebar.subheader("🗂️ Ingestion Context Data Files")

f_ag1 = st.sidebar.file_uploader("Upload Core Applications Workbook (AG1)", type=['xlsx', 'csv'], help="Source ledger contains sales entries, quality checks, and customer info.")
f_ag2 = st.sidebar.file_uploader("Upload Live Telephony Portal Ledger (AG2)", type=['xlsx', 'csv'], help="Downstream execution register containing digital circuit setup tracking.")

if not f_ag1 or not f_ag2:
    st.warning("⚡ Pipeline Awaiting Input Data: Upload both corporate application workbooks in the sidebar to activate the dashboard engines.")
    st.stop()

# Dynamic Parser Engine with Strict Fallbacks
@st.cache_data(show_spinner="Parsing analytical business data frames...")
def process_source_ledgers(file_ag1, file_ag2):
    # Core Parse AG1
    if file_ag1.name.endswith('.csv'):
        ag1 = pd.read_csv(file_ag1)
    else:
        ag1 = pd.read_excel(file_ag1)
        
    # Core Parse AG2
    if file_ag2.name.endswith('.csv'):
        ag2 = pd.read_csv(file_ag2)
    else:
        ag2 = pd.read_excel(file_ag2)
        
    # Standardize column contexts
    ag1.columns = [str(c).strip() for c in ag1.columns]
    ag2.columns = [str(c).strip() for c in ag2.columns]
    
    # 1. Precise Universal Robust DateTime Ingestion Strategy
    for df in [ag1, ag2]:
        date_col = next((c for c in df.columns if 'date' in c.lower()), None)
        if date_col:
            df['Date_Parsed'] = pd.to_datetime(df[date_col], errors='coerce')
            df['Standardized_Date'] = df['Date_Parsed'].dt.date
        else:
            df['Date_Parsed'] = pd.to_datetime(today_date)
            df['Standardized_Date'] = today_date
            
    # 2. Strict Logical Mapping Extensions
    q_col = next((c for c in ag1.columns if 'quality status' in c.lower() or 'q_status' in c.lower() or 'status' in c.lower()), None)
    if q_col:
        ag1['Q_Status'] = ag1[q_col].apply(map_quality)
        ag1['Quality Status'] = ag1[q_col]
    else:
        ag1['Q_Status'] = 'Others'
        ag1['Quality Status'] = 'Others'
        
    p_col = next((c for c in ag2.columns if 'portal status' in c.lower() or 'p_status' in c.lower() or 'status' in c.lower()), None)
    if p_col:
        ag2['P_Status'] = ag2[p_col].apply(map_portal)
    else:
        ag2['P_Status'] = 'Others'
        
    wc_col_found = next((c for c in ag1.columns if 'welcome call' in c.lower() or 'wc' in c.lower() or 'status' in c.lower()), None)
    if wc_col_found:
        ag1['WC_Clean'] = ag1[wc_col_found].apply(map_wc)
    else:
        ag1['WC_Clean'] = 'Others'
        
    # Align structural layout expectations for logs
    if 'Quality Remarks' not in ag1.columns:
        rmk_col = next((c for c in ag1.columns if 'remark' in c.lower() or 'comment' in c.lower()), 'Quality Remarks')
        ag1['Quality Remarks'] = ag1[rmk_col] if rmk_col in ag1.columns else ''
        
    if 'Welcome call Remarks' not in ag1.columns:
        ag1['Welcome call Remarks'] = ''
        
    if 'Customer Name' not in ag1.columns:
        name_col = next((c for c in ag1.columns if 'name' in c.lower() or 'cust' in c.lower()), 'Customer Name')
        ag1['Customer Name'] = ag1[name_col] if name_col in ag1.columns else 'Unknown Customer'
        
    if 'CLI' not in ag1.columns:
        cli_col = next((c for c in ag1.columns if 'cli' in c.upper() or 'phone' in c.lower() or 'telephone' in c.lower() or 'number' in c.lower()), 'CLI')
        ag1['CLI'] = ag1[cli_col] if cli_col in ag1.columns else ''
        
    if 'Telephone No.' not in ag2.columns:
        t_col = next((c for c in ag2.columns if 'phone' in c.lower() or 'telephone' in c.lower() or 'cli' in c.upper() or 'number' in c.lower()), 'Telephone No.')
        ag2['Telephone No.'] = ag2[t_col] if t_col in ag2.columns else ''

    return ag1, ag2, bool(wc_col_found)

try:
    ag1, ag2, wc_col = process_source_ledgers(f_ag1, f_ag2)
    
    # ==============================================================================
    # 5. ENTERPRISE GLOBAL FILTER CONTROLS
    # ==============================================================================
    st.sidebar.subheader("📅 Temporal Filter Configurations")
    min_d = min(ag1['Date_Parsed'].min(), ag2['Date_Parsed'].min())
    max_d = max(ag1['Date_Parsed'].max(), ag2['Date_Parsed'].max())
    
    if pd.isna(min_d) or pd.isna(max_d):
        min_d, max_d = today_date - datetime.timedelta(days=30), today_date
    else:
        min_d, max_d = min_d.date(), max_d.date()
        
    start_filter = st.sidebar.date_input("Analysis Boundary Start", min_d)
    end_filter = st.sidebar.date_input("Analysis Boundary End", max_d)
    
    # Active Filtering Slices
    ag1_filtered = ag1[(ag1['Date_Parsed'].dt.date >= start_filter) & (ag1['Date_Parsed'].dt.date <= end_filter)]
    ag2_filtered = ag2[(ag2['Date_Parsed'].dt.date >= start_filter) & (ag2['Date_Parsed'].dt.date <= end_filter)]
    
    # Header Banner Element
    st.markdown(f"""
    <div class="brand-banner">
        <h1>Performance Insights & Quality Audit Ledger</h1>
        <p>Operational Performance Analytics Framework &nbsp;|&nbsp; Active Window: <b>{start_filter.strftime('%d %b %Y')}</b> to <b>{end_filter.strftime('%d %b %Y')}</b></p>
    </div>
    """, unsafe_allow_html=True)
    
    # ==============================================================================
    # 6. PERFORMANCE CARD CONTAINER LAYOUT (RESPONSIVE BLOCKS)
    # ==============================================================================
    total_apps = len(ag1_filtered)
    total_ag2 = len(ag2_filtered)
    
    # Dynamic Math Metrics Calculation
    appr_count = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'])
    live_count = len(ag2_filtered[ag2_filtered['P_Status'] == 'Live'])
    comm_count = len(ag2_filtered[ag2_filtered['P_Status'] == 'Committed'])
    
    q_appr_rate = (appr_count / total_apps * 100) if total_apps > 0 else 0.0
    live_conv_rate = (live_count / total_ag2 * 100) if total_ag2 > 0 else 0.0
    
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <p class="kpi-title">Total Applications Received</p>
            <p class="kpi-value">{total_apps}</p>
            <p class="kpi-subtitle">Registered in main AG1 tracker</p>
        </div>
        <div class="kpi-card">
            <p class="kpi-title">Quality Approved Audits</p>
            <p class="kpi-value" style="color: #10b981;">{appr_count}</p>
            <p class="kpi-subtitle">Compliance Pass Ratio: <b>{q_appr_rate:.1f}%</b></p>
        </div>
        <div class="kpi-card">
            <p class="kpi-title">Telephony Circuits Live</p>
            <p class="kpi-value" style="color: #3b82f6;">{live_count}</p>
            <p class="kpi-subtitle">Active Live Node Stream conversion</p>
        </div>
        <div class="kpi-card">
            <p class="kpi-title">Committed Backlog</p>
            <p class="kpi-value" style="color: #f59e0b;">{comm_count}</p>
            <p class="kpi-subtitle">Pending active terminal verification</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # 7. AUTOMATED INSIGHT GENERATION ENGINE (PART 2 SEGMENT)
    # ==============================================================================
    flags_html = ""
    
    if total_apps > 0:
        q_appr = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']) / total_apps
        q_can = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled']) / total_apps
        q_rej = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rejected']) / total_apps
        q_rew = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']) / total_apps

        if q_appr > 0.60: 
            flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Quality Engine</p><p class="insight-phrase" style="color:#10b981">High Approval Rate</p><p class="insight-comment">Excellent pitch mechanics, process compliance, and consumer accuracy standards verified.</p></div>'
        elif q_appr < 0.60: 
            flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality Engine</p><p class="insight-phrase" style="color:#ef4444">Low Approval Rate</p><p class="insight-comment">Review tactical script verification guidelines to decrease application errors.</p></div>'
        
        if q_can > 0.40: 
            flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Quality Engine</p><p class="insight-phrase" style="color:#f59e0b">High Cancellation Volume</p><p class="insight-comment">Substantial volumetric drops caught post-audit. Inspect downstream workflow compliance.</p></div>'
        if q_rej > 0.20: 
            flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality Engine</p><p class="insight-phrase" style="color:#ef4444">High Rejection Triggers</p><p class="insight-comment">Critical structural file mismatches identified. Adjust verification filters.</p></div>'
        if q_rew > 0.30: 
            flags_html += '<div class="insight-card" style="border-color:#3b82f6"><p class="insight-title">Quality Engine</p><p class="insight-phrase" style="color:#3b82f6">Frequent Verification Reworks</p><p class="insight-comment">High operational friction due to simple collection data errors. Implement a double check process.</p></div>'

        if wc_col:
            wc_done = len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done']) / total_apps
            wc_can = len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Cancelled']) / total_apps
            if wc_done < 0.70: 
                flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Welcome Call Module</p><p class="insight-phrase" style="color:#f59e0b">Low Completion Performance</p><p class="insight-comment">Address client profile criteria closely to boost critical welcome-call validation parameters.</p></div>'
            if wc_can > 0.15: 
                flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Welcome Call Module</p><p class="insight-phrase" style="color:#ef4444">High WC Cancellations</p><p class="insight-comment">Address customer lingering doubts during active initial conversions to stabilize profiles.</p></div>'

    if total_ag2 > 0:
        l_live = len(ag2_filtered[ag2_filtered['P_Status'] == 'Live']) / total_ag2
        l_can = len(ag2_filtered[ag2_filtered['P_Status'] == 'Cancelled']) / total_ag2
        if l_live > 0.20: 
            flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Circuit Provisioning</p><p class="insight-phrase" style="color:#10b981">Strong Pipeline Conversion</p><p class="insight-comment">Healthy processing momentum! High underlying volume of healthy data structures.</p></div>'
        elif l_live < 0.20: 
            flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Circuit Provisioning</p><p class="insight-phrase" style="color:#f59e0b">Low Pipeline Conversion Rate</p><p class="insight-comment">Identify architectural or timing data friction delaying application handoffs.</p></div>'
        if l_can > 0.65: 
            flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Circuit Provisioning</p><p class="insight-phrase" style="color:#ef4444">High Drop Out Pipeline Loss</p><p class="insight-comment">Extreme variations between intake registry values and provisioned endpoints.</p></div>'

    if flags_html:
        st.subheader("💡 Business Insights & Action Items")
        st.markdown(f'<div class="insight-container">{flags_html}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ==============================================================================
    # 8. MACRO MATRIX DATA BREAKDOWN (DAILY / MONTHLY METRIC TABLES)
    # ==============================================================================
    st.subheader("📅 Interval Data Aggregations Matrix")
    ag1_filtered['Date'] = ag1_filtered['Date_Parsed'].dt.date
    ag2_filtered['Date'] = ag2_filtered['Date_Parsed'].dt.date
    
    view_mode = st.radio("Toggle Temporal View Mode:", ["Daily", "Monthly"], horizontal=True)
    
    if view_mode == "Daily":
        ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.date
        ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.date
        chart_group_col = 'Date'
    else:
        ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.strftime('%Y-%m')
        ag2_filtered['Period'] = ag2_parsed_str = ag2_filtered['Date_Parsed'].dt.strftime('%Y-%m')
        chart_group_col = 'Period'
        
    ca, cb, cc, cd = st.columns(4)
    
    with ca:
        st.markdown("##### Applications Intake (AG1)")
        if not ag1_filtered.empty:
            period_apps = ag1_filtered.groupby('Period').size().to_frame('Total Apps')
            vmax_apps = max(int(period_apps.max().max()), 2)
            styled_apps = period_apps.style.format(lambda x: "-" if x == 0 else f"{x:,}")\
                .background_gradient(cmap='Greens', vmin=1, vmax=vmax_apps)\
                .map(lambda x: 'background-color: transparent; color: #94a3b8;' if x == 0 else '')
            st.dataframe(styled_apps, use_container_width=True)
        else:
            st.caption("No records present.")
            
    with cb:
        st.markdown("##### Compliance Quality Logs")
        if not ag1_filtered.empty:
            period_qual = ag1_filtered.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
            qual_order = ['Approved', 'Rework', 'Cancelled', 'Rejected', 'Others']
            period_qual = period_qual.reindex(columns=qual_order, fill_value=0)
            period_qual = period_qual.loc[:, (period_qual != 0).any(axis=0)]
            if not period_qual.empty:
                vmax_qual = max(int(period_qual.max().max()), 2)
                styled_qual = period_qual.style.format(lambda x: "-" if x == 0 else f"{x:,}")\
                    .background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Approved'])], vmin=1, vmax=vmax_qual)\
                    .background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Rework'])], vmin=1, vmax=vmax_qual)\
                    .background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Cancelled', 'Rejected'])], vmin=1, vmax=vmax_qual)\
                    .map(lambda x: 'background-color: transparent; color: #94a3b8;' if x == 0 else '')
                st.dataframe(styled_qual, use_container_width=True)
        else:
            st.caption("No records present.")
            
    with cc:
        st.markdown("##### Welcome Call Segment")
        if wc_col and not ag1_filtered.empty:
            period_wc = ag1_filtered.groupby(['Period', 'WC_Clean']).size().unstack(fill_value=0)
            wc_order = ['Done', 'Pending', 'Paperwork', 'Cancelled', 'Others']
            wc_order = [o for o in wc_order if o in period_wc.columns or period_wc.empty]
            period_wc = period_wc.reindex(columns=wc_order, fill_value=0)
            if not period_wc.empty:
                vmax_wc = max(int(period_wc.max().max()), 2)
                styled_wc = period_wc.style.format(lambda x: "-" if x == 0 else f"{x:,}")\
                    .background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Done'])], vmin=1, vmax=vmax_wc)\
                    .background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Pending', 'Paperwork'])], vmin=1, vmax=vmax_wc)\
                    .background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Cancelled'])], vmin=1, vmax=vmax_wc)\
                    .map(lambda x: 'background-color: transparent; color: #94a3b8;' if x == 0 else '')
                st.dataframe(styled_wc, use_container_width=True)
        else:
            st.info("No active Welcome Call telemetry columns found.")
            
    with cd:
        st.markdown("##### Telephony Provisioning Status")
        if not ag2_filtered.empty:
            period_port = ag2_filtered.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
            port_order = ['Live', 'Committed', 'Cancelled', 'Others']
            period_port = period_port.reindex(columns=port_order, fill_value=0)
            period_port = period_port.loc[:, (period_port != 0).any(axis=0)]
            if not period_port.empty:
                vmax_port = max(int(period_port.max().max()), 2)
                styled_port = period_port.style.format(lambda x: "-" if x == 0 else f"{x:,}")\
                    .background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_port.columns.intersection(['Live'])], vmin=1, vmax=vmax_port)\
                    .background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_port.columns.intersection(['Committed'])], vmin=1, vmax=vmax_port)\
                    .background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_port.columns.intersection(['Cancelled'])], vmin=1, vmax=vmax_port)\
                    .map(lambda x: 'background-color: transparent; color: #94a3b8;' if x == 0 else '')
                st.dataframe(styled_port, use_container_width=True)
        else:
            st.caption("No records present.")

    st.markdown("---")

    # ==============================================================================
    # 9. GRAPHICAL HISTORICAL TRENDS & SYSTEM DYNAMICS HEATMAP
    # ==============================================================================
    col_trend, col_cal = st.columns([3, 2])
    
    with col_trend:
        st.subheader("📈 Chronological Trend Analysis")
        if not ag1_filtered.empty:
            d_apps = ag1_filtered.groupby(chart_group_col).size().to_frame('Total Apps')
            d_appr = ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'].groupby(chart_group_col).size().to_frame('Approved')
            d_live = ag2_filtered[ag2_filtered['P_Status'] == 'Live'].groupby(chart_group_col).size().to_frame('Live')
            i_comb = d_apps.join([d_appr, d_live], how='left').fillna(0).reset_index()
            i_comb[chart_group_col] = i_comb[chart_group_col].astype(str)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=i_comb[chart_group_col], y=i_comb['Total Apps'], 
                name="Total Intakes (AG1)", marker_color='#abcbfb',
                hoverinfo="x+y"
            ))
            fig.add_trace(go.Scatter(
                x=i_comb[chart_group_col], y=i_comb['Approved'], 
                name="Audit Verified Compliance Pass", line=dict(color='#10b981', width=3.5, shape='spline')
            ))
            fig.add_trace(go.Scatter(
                x=i_comb[chart_group_col], y=i_comb['Live'], 
                name="Downstream Connected Nodes", line=dict(color='#f59e0b', width=3.5, shape='spline')
            ))
            fig.update_layout(
                hovermode="x unified", 
                margin=dict(l=10, r=10, t=20, b=10),
                xaxis_title="Timeline Interval Axis" if view_mode=="Daily" else "Monthly Operational Buckets",
                legend=dict(orientation="h", ylink=1.1, y=1.15, x=0),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient spatial tracking volume to construct system trends charts.")

    with col_cal:
        st.subheader("🗓️ Operational Activity Calendar Matrix")
        
        def is_holiday(dt):
            wd = dt.weekday()  # 0=Mon, 6=Sun
            if wd == 6: return True 
            if wd == 5: 
                week_num = (dt.day - 1) // 7 + 1
                return week_num in [1, 3, 5] 
            return False

        c_month_col, c_year_col = st.columns(2)
        sel_month = c_month_col.selectbox("Month Focus", list(calendar.month_name)[1:], index=today_date.month-1)
        sel_year = c_year_col.selectbox("Year Focus", [2025, 2026, 2027], index=1)
        
        m_idx = list(calendar.month_name).index(sel_month)
        try:
            num_days = calendar.monthrange(sel_year, m_idx)[1]
            dates = [datetime.date(sel_year, m_idx, day) for day in range(1, num_days+1)]
            
            daily_sales = ag1.groupby(ag1['Date_Parsed'].dt.date).size()
            cal_df = pd.DataFrame({
                'Date': dates,
                'Day': [d.day for d in dates],
                'Weekday': [d.strftime('%a') for d in dates],
                'WeekNum': [int(d.strftime('%V')) if d.strftime('%V').isdigit() else 0 for d in dates],
                'Sales': [daily_sales.get(d, 0) for d in dates],
                'Type': ['Holiday' if is_holiday(d) else 'Working' for d in dates]
            })

            cal_df['HoverText'] = cal_df.apply(lambda r: "Company Standard Holiday Rest Block" if r['Type'] == 'Holiday' else f"Total Core Volume Invoiced: {r['Sales']} Applications", axis=1)

            fig_cal = go.Figure()
            working_days = cal_df[cal_df['Type'] == 'Working']
            fig_cal.add_trace(go.Heatmap(
                x=working_days['Weekday'], y=working_days['WeekNum'], z=working_days['Sales'],
                text=working_days['Day'], 
                customdata=working_days['HoverText'],
                hovertemplate="%{customdata}<extra></extra>",
                texttemplate="%{text}",
                colorscale=[[0, '#f8fafc'], [0.1, '#d1fae5'], [1, '#059669']],
                showscale=False, xgap=4, ygap=4
            ))

            holidays = cal_df[cal_df['Type'] == 'Holiday']
            fig_cal.add_trace(go.Scatter(
                x=holidays['Weekday'], y=holidays['WeekNum'], mode='markers+text',
                marker=dict(symbol='square', size=32, color='#e2e8f0', line=dict(width=0)),
                text=holidays['Day'], 
                customdata=holidays['HoverText'],
                hovertemplate="%{customdata}<extra></extra>",
                textfont=dict(color='#94a3b8', size=11),
                showlegend=False
            ))

            fig_cal.update_layout(
                height=280, margin=dict(l=5, r=5, t=5, b=5),
                xaxis=dict(side="top", categoryorder='array', categoryarray=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
                yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor='white'
            )
            st.plotly_chart(fig_cal, use_container_width=True)
            st.caption("🟢 Processed Intakes Run &nbsp;|&nbsp; ⚪ Minimal Processing Activity &nbsp;|&nbsp; 🔵 Scheduled Standard Holiday Node")
        except Exception as cal_err:
            st.error(f"Could not build calendar grid instance: {cal_err}")

    st.markdown("---")

    # ==============================================================================
    # 10. MULTI-INDEX MERGED RECENT APPLICATIONS AUDIT LOG
    # ==============================================================================
    st.subheader("🔍 Integrated Recent Applications Verification Log")
    if not ag1.empty:
        ag2_clean = ag2.copy()
        ag2_clean['Telephone No.'] = ag2_clean['Telephone No.'].astype(str).str.strip()
        
        # Clean structural collision fields cleanly
        rename_map = {}
        if 'Status' in ag2_clean.columns: rename_map['Status'] = 'Portal Status'
        if 'Committed Date' in ag2_clean.columns: rename_map['Committed Date'] = 'Live Date'
        if 'Live Date' not in ag2_clean.columns and 'Committed Date' in ag2_clean.columns:
            ag2_clean = ag2_clean.rename(columns={'Committed Date': 'Live Date'})
        if rename_map:
            ag2_clean = ag2_clean.rename(columns=rename_map)
            
        if 'Portal Status' unmarried_check and 'P_Status' in ag2_clean.columns:
            ag2_clean['Portal Status'] = ag2_clean['P_Status']
            
        ag2_unique = ag2_clean.sort_values('Date_Parsed').drop_duplicates('Telephone No.', keep='last')
        
        ag1_log_base = ag1.copy()
        ag1_log_base['CLI_Key'] = ag1_log_base['CLI'].astype(str).str.strip()
        
        # Safe Extraction Array Target Definitions
        target_cols = ['Telephone No.']
        for opt in ['LetterStatus', 'CallStatus', 'Comments', 'Voice of Customer', 'Cancellation Reason', 'Portal Status', 'Live Date']:
            if opt in ag2_unique.columns:
                target_cols.append(opt)
                
        merged_log = ag1_log_base.merge(
            ag2_unique[target_cols],
            left_on='CLI_Key', 
            right_on='Telephone No.', 
            how='left'
        )

        # Dynamic Formatter Safe Injection Strategy
        merged_log['Sale Date'] = pd.to_datetime(merged_log['Standardized_Date'], errors='coerce').dt.strftime('%d-%m-%Y').fillna('')
        if 'Live Date' in merged_log.columns:
            merged_log['Live Date'] = pd.to_datetime(merged_log['Live Date'], errors='coerce').dt.strftime('%d-%m-%Y').fillna('')
        else:
            merged_log['Live Date'] = ''

        # Structural Hierarchical Grid Form Blueprint Array Map
        columns_layout = [
            ('Basic Info.', 'S.No.'),
            ('Basic Info.', 'Sale Date'),
            ('Basic Info.', 'Customer Name'),
            ('Quality Audit', 'Quality Status'),
            ('Quality Audit', 'Quality Remarks'),
            ('Welcome Call', 'Status'),
            ('Welcome Call', 'Welcome call Remarks'),
            ('Live Status', 'LetterStatus'),
            ('Live Status', 'CallStatus'),
            ('Live Status', 'Portal Status'),
            ('Live Status', 'Live Date'),
            ('Live Status', 'Comments'),
            ('Live Status', 'Voice of Customer'),
            ('Live Status', 'Cancellation Reason')
        ]
        
        # Dynamic Multi-Filtering View Selector Interface Blocks
        log_col1, log_col2, log_col3 = st.columns([2, 2, 1])
        with log_col1:
            log_filter_type = st.radio("Primary Log Sorting Vector Range:", ["All Applications", "By Specific Date Range", "By Specific Month"], horizontal=True)
        with log_col2:
            if log_filter_type == "By Specific Date Range":
                ld_col1, ld_col2 = st.columns(2)
                log_start = ld_col1.date_input("Filter Window Start", start_filter, key="log_start_date")
                log_end = ld_col2.date_input("Filter Window End", end_filter, key="log_end_date")
                recent_log = merged_log[(merged_log['Date_Parsed'].dt.date >= log_start) & (merged_log['Date_Parsed'].dt.date <= log_end)].sort_values(by='Date_Parsed', ascending=False)
            elif log_filter_type == "By Specific Month":
                unique_months = sorted(merged_log['Date_Parsed'].dt.strftime('%Y-%m').dropna().unique(), reverse=True)
                if unique_months:
                    selected_month = st.selectbox("Operational Tracking Month Segment Target:", unique_months)
                    recent_log = merged_log[merged_log['Date_Parsed'].dt.strftime('%Y-%m') == selected_month].sort_values(by='Date_Parsed', ascending=False)
                else:
                    recent_log = merged_log[0:0]
            else:
                recent_log = merged_log.sort_values(by='Date_Parsed', ascending=False)

        recent_log['S.No.'] = range(1, len(recent_log) + 1)

        with log_col3:
            row_limit = st.selectbox("Records View Boundary (Pagination Limit):", [5, 10, 20, 50, 100, "All"], index=2)

        # Dynamic Structural Check Alignment
        for col_name in ['Status', 'LetterStatus', 'CallStatus', 'Comments', 'Voice of Customer', 'Cancellation Reason', 'Portal Status']:
            if col_name not in recent_log.columns:
                recent_log[col_name] = ''
        
        # Standardize mapped names over empty metrics
        recent_log['Quality Status'] = recent_log['Q_Status']
        if 'Status' not in recent_log.columns or recent_log['Status'].astype(str).str.strip().eq('').all():
            recent_log['Status'] = recent_log['WC_Clean']

        valid_layout = [item for item in columns_layout if item[1] in recent_log.columns]
        display_df = recent_log[[item[1] for item in valid_layout]].copy()
        
        # Format the Clean Multi-Index Structure Header Columns Framework
        display_df.columns = pd.MultiIndex.from_tuples(valid_layout)

        table_container = st.container()

        # Advanced Engine Pagination Routing Matrix Logic Block
        if row_limit != "All":
            limit = int(row_limit)
            total_records = len(display_df)
            total_pages = max(1, math.ceil(total_records / limit))
            
            if st.session_state.current_page > total_pages:
                st.session_state.current_page = 1
                
            start_idx = (st.session_state.current_page - 1) * limit
            end_idx = min(start_idx + limit, total_records)
            display_df_page = display_df.iloc[start_idx:end_idx]
            
            if total_pages > 1:
                st.write("")
                pag_col1, pag_col2 = st.columns([1, 1])
                with pag_col1:
                    st.markdown(f"<p style='color: #64748b; font-size: 0.85rem; margin-top: 6px;'>Displaying ledger frames <b>{start_idx + 1}</b> through <b>{end_idx}</b> (Total registered collection size: {total_records} tracks)</p>", unsafe_allow_html=True)
                with pag_col2:
                    b_col1, b_col2, b_col3 = st.columns([2, 1, 1])
                    with b_col1:
                        st.markdown(f"<p style='text-align: right; color: #64748b; font-size: 0.85rem; margin-top: 6px;'>Active View Frame <b>{st.session_state.current_page}</b> of {total_pages}</p>", unsafe_allow_html=True)
                    with b_col2:
                        if st.button("⏪ Pull Previous Frame", disabled=(st.session_state.current_page == 1), use_container_width=True, key="prev_pg_action"):
                            st.session_state.current_page -= 1
                            st.rerun()
                    with b_col3:
                        if st.button("Push Next Frame ⏩", disabled=(st.session_state.current_page == total_pages), use_container_width=True, key="next_pg_action"):
                            st.session_state.current_page += 1
                            st.rerun()
        else:
            display_df_page = display_df

        # High-Speed Vectorized Element Coloring Injector Functions
        def style_log_row(row):
            styles = [''] * len(row)
            
            def get_val(col_name):
                for col in row.index:
                    if col[1] == col_name: return str(row[col]).lower()
                return ""

            # Theme Adjusted Hex Colors
            DARK_GREEN, DARK_AMBER, DARK_RED = '#065f46', '#92400e', '#991b1b'
            BG_GREEN, BG_AMBER, BG_RED = 'rgba(22, 163, 74, 0.15)', 'rgba(217, 119, 6, 0.15)', 'rgba(220, 38, 38, 0.15)'

            q_val = get_val('Quality Status')
            q_bg, q_txt = '', ''
            if any(x in q_val for x in ['appr', 'pass']): q_bg, q_txt = BG_GREEN, DARK_GREEN
            elif any(x in q_val for x in ['rew', 'repro']): q_bg, q_txt = BG_AMBER, DARK_AMBER
            elif any(x in q_val for x in ['can', 'rej']): q_bg, q_txt = BG_RED, DARK_RED
            q_style = f'background-color: {q_bg}; color: {q_txt}; font-weight: 600;' if q_bg else ''

            wc_val = get_val('Status')
            wc_bg, wc_txt = '', ''
            if any(x in wc_val for x in ['done', 'pass', 'comp', 'live']): wc_bg, wc_txt = BG_GREEN, DARK_GREEN
            elif any(x in wc_val for x in ['pend', 'pnd', 'paper', 'ppw']): wc_bg, wc_txt = BG_AMBER, DARK_AMBER
            elif any(x in wc_val for x in ['can', 'rej']): wc_bg, wc_txt = BG_RED, DARK_RED
            wc_style = f'background-color: {wc_bg}; color: {wc_txt}; font-weight: 600;' if wc_bg else ''

            call_val = get_val('CallStatus')
            c_bg, c_txt = '', ''
            if 'satisfied' in call_val: c_bg, c_txt = BG_GREEN, DARK_GREEN
            elif any(x in call_val for x in ['cancel', 'pend', 'drop']): c_bg, c_txt = BG_RED, DARK_RED
            c_style = f'background-color: {c_bg}; color: {c_txt}; font-weight: 600;' if c_bg else ''
            
            portal_val = get_val('Portal Status')
            p_bg, p_txt = '', ''
            if 'live' in portal_val: p_bg, p_txt = BG_GREEN, DARK_GREEN
            elif 'committed' in portal_val: p_bg, p_txt = BG_AMBER, DARK_AMBER
            elif any(x in portal_val for x in ['rej', 'cancel']): p_bg, p_txt = BG_RED, DARK_RED
            p_style = f'background-color: {p_bg}; color: {p_txt}; font-weight: 600;' if p_bg else ''

            quality_cols = ['S.No.', 'Sale Date', 'Customer Name', 'Quality Status', 'Quality Remarks']
            portal_group = ['Portal Status', 'Live Date', 'Comments', 'Voice of Customer', 'Cancellation Reason']
            
            for idx, col_tuple in enumerate(row.index):
                col = col_tuple[1] 
                current_style = ""
                
                if col == 'LetterStatus':
                    current_style = 'background-color: rgba(59, 130, 246, 0.08); color: #1e40af;'
                elif col == 'CallStatus':
                    current_style = c_style
                elif col in portal_group:
                    if col == 'Portal Status': current_style = p_style
                    else: current_style = f'background-color: {p_bg};' if p_bg else ''
                elif col in quality_cols:
                    if col == 'Quality Status': current_style = q_style
                    else: current_style = f'background-color: {q_bg};' if q_bg else ''
                else:
                    if col == 'Status': current_style = wc_style
                    else: current_style = f'background-color: {wc_bg};' if wc_bg else ''
                
                # Solid Dark Border Separator Framework Injectors
                if col == 'S.No.': current_style += ' border-left: 2px solid #3b82f6;'
                if col in ['Customer Name', 'Quality Remarks', 'Welcome call Remarks', 'Cancellation Reason']:
                    current_style += ' border-right: 2px solid #cbd5e1;'
                
                styles[idx] = current_style
            return styles           
        
        styled_log = display_df_page.style.apply(style_log_row, axis=1)
        
        with table_container:
            st.dataframe(styled_log, use_container_width=True, hide_index=True)

    # ==============================================================================
    # 11. CORPORATE DISPOSITION PERFORMANCE CALLOUT MATRIX
    # ==============================================================================
    st.markdown("""
        <div class="tips-box">
            <div class="tips-title">💡 Performance Strategy Directives: Dialler Disposition Accuracy Rules</div>
            <ul class="tips-list">
                <li><b>Answering Machines:</b> Do not dispose active customer connections as an "Answering Machine" especially if the Customer Talk Time/connectivity exceeds 30 seconds. Use it primarily when you hear a pre-recorded Answering Machine/Voicemail message.</li>
                <li><b>Customer Hangup:</b> This disposition should be used when the customer abruptly hangs up. Should be used for active/connected customers.</li>
                <li><b>No Answer:</b> Dispose as "No Answer" only if the customer does not pick up the call at all.</li>
                <li><b>Sky TV packages/Virgin:</b> Any call which indicates an error on the Talk-Talk portal, should be disposed as "Sky TV packages" or "Virgin". They must not be disposed as Answering Machines, Customer Hangup, No Answer, Not Interested etc. These dispositions would reappear in the dialler, and would dilute the quality of the data severely as the probability of the application of these customers is pretty low.</li>
                <li><b>Wrong Number:</b> Dispose them as "Wrong Number" if there is a mismatch in the data on the dialler and the data provided by the customer.</li>
                <li><b>Family Interference/POA:</b> Dispose as Family Interference/POA, if a family member or a 3rd person takes care of the customer's finances or other decisions.</li>
                <li><b>Dementia:</b> Dispose as Dementia, if the customer seems to have Dementia (seems forgetful of basic details), or seems Vulnerable.</li>
                <li><b>Over Age:</b> Dispose as Over Age if the customer is over 85 years old, or was born before 1940.</li>
                <li><b>Mobile Number:</b> Any number beginning with "7" should be disposed as a Mobile Number.</li>
                <li><b>Social Alarm VOIP:</b> If a customer has a Social Alarm/Medical Alarm/Careline/Lifeline etc, then use the disposition "Social Alarm VOIP".</li>
                <li><b>Hang up on bank details:</b> Use this disposition if the customer disconnects when hearing of or attempting any financial details.</li>
                <li><b>Busy:</b> If the customer is busy.</li>
                <br>
                <li><b>🚫 Dispositions that WILL NOT reappear in the dialler (if processed correctly):</b>
                    <ul>
                        <li>Dementia | Family Interference / POA | Sky TV Packages / Virgin | Over Age</li>
                    </ul>
                </li>
                <br>
                <li><b>🔄 Dispositions that WILL reappear frequently on the dialler:</b>
                    <ul>
                        <li>Answering Machine | Customer Hangup | Interested | Callback</li>
                    </ul>
                </li>
                <br>
                <li><u><b>Data Accuracy Policy Statement:</b> Enter precise dispositions immediately upon disconnect. Maintaining data discipline directly optimizes downstream data quality filters for the entire development team.</u></li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    st.write("---")

except Exception as main_pipeline_err:
    st.error(f"⚠️ Critical Analytical Core Run Interruption: {main_pipeline_err}")
