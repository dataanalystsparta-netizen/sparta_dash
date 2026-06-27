import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import calendar
import datetime
import math

# ==========================================
# 1. PAGE CONFIG & MODERN CSS STYLING
# ==========================================
st.set_page_config(
    page_title="Executive Performance & Quality Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Global UI Injection
st.markdown("""
    <style>
        /* Global Background and Fonts */
        .main {
            background-color: #f8fafc;
            color: #0f172a;
        }
        
        /* Typography overrides */
        h1, h2, h3 {
            font-weight: 700 !important;
            color: #1e3a8a !important;
            letter-spacing: -0.02em;
        }
        
        /* KPI & Insight Containers */
        .metric-card {
            background: white;
            padding: 1.25rem;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.1);
            border: 1px solid #e2e8f0;
            margin-bottom: 1rem;
        }
        .metric-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }
        .metric-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #0f172a;
        }
        
        /* Modern Insight Cards (Part 2 Flex Layout) */
        .insight-container {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .insight-card {
            flex: 1 1 calc(25% - 1rem);
            min-width: 240px;
            background: white;
            padding: 1rem 1.25rem;
            border-radius: 8px;
            border-left: 5px solid #cbd5e1;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .insight-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            font-weight: 700;
            color: #64748b;
            margin: 0 0 0.25rem 0;
        }
        .insight-phrase {
            font-size: 1.1rem;
            font-weight: 700;
            color: #0f172a;
            margin: 0 0 0.25rem 0;
        }
        .insight-comment {
            font-size: 0.85rem;
            color: #475569;
            margin: 0;
            line-height: 1.4;
        }

        /* Call Dispositions Tips Box Styling */
        .tips-box {
            background-color: white;
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-top: 1.5rem;
        }
        .tips-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #1e3a8a;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
        }
        .tips-list {
            font-size: 0.9rem;
            color: #334155;
            line-height: 1.6;
            padding-left: 1.25rem;
        }
        .tips-list li {
            margin-bottom: 0.5rem;
        }
        
        /* Streamlit Element Optimizations */
        div[data-testid="stDataFrame"] {
            border-radius: 8px !important;
            overflow: hidden !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        }
    </style>
""", unsafe_allow_html=True)

# Placeholder objects to preserve execution structure context
# In production, these variables point to loaded source DataFrames
today_date = datetime.date.today()
wc_col = True 

# Mock Initialization of data states if not already loaded upstream
if 'ag1' not in locals():
    # Structural mock arrays matching logic parameters
    dr = pd.date_range(start="2026-05-01", end="2026-06-25", freq="D")
    ag1 = pd.DataFrame({
        'Date_Parsed': dr, 'Standardized_Date': dr, 'Q_Status': np.random.choice(['Approved', 'Cancelled', 'Rejected', 'Rework'], size=len(dr)),
        'WC_Clean': np.random.choice(['Done', 'Cancelled', 'Pending', 'Paperwork'], size=len(dr)), 'CLI': [f"447123456{i}" for i in range(len(dr))],
        'Customer Name': [f"Customer Mock {i}" for i in range(len(dr))], 'Quality Status': np.random.choice(['Approved', 'Rework', 'Cancelled'], size=len(dr)),
        'Quality Remarks': ['Verified' for _ in range(len(dr))], 'Status': np.random.choice(['Done', 'Pending'], size=len(dr)),
        'Welcome call Remarks': ['Confirmed' for _ in range(len(dr))]
    })
    ag1_filtered = ag1.copy()

if 'ag2' not in locals():
    dr2 = pd.date_range(start="2026-05-01", end="2026-06-25", freq="D")
    ag2 = pd.DataFrame({
        'Date_Parsed': dr2, 'P_Status': np.random.choice(['Live', 'Committed', 'Cancelled'], size=len(dr2)),
        'Telephone No.': [f"447123456{i}" for i in range(len(dr2))], 'Status': np.random.choice(['Live', 'Committed'], size=len(dr2)),
        'Committed Date': dr2, 'LetterStatus': ['Sent' for _ in range(len(dr2))], 'CallStatus': ['Satisfied' for _ in range(len(dr2))],
        'Comments': ['System Ok' for _ in range(len(dr2))], 'Voice of Customer': ['Good' for _ in range(len(dr2))],
        'Cancellation Reason': ['N/A' for _ in range(len(dr2))]
    })
    ag2_filtered = ag2.copy()

# Try Block wrapping operational UI layout
try:
    # Header Area
    st.title("📊 Lead Conversion & Audit Ledger Dashboard")
    st.markdown("<p style='color: #64748b; font-size:1.1rem; margin-top:-0.5rem;'>Automated quality verification pipelines and operational conversion metrics</p>", unsafe_allow_html=True)
    st.write("---")

    # ==========================================
    # PART 1: INGESTION LOGIC & TOP KPI METRICS
    # ==========================================
    total_apps = len(ag1_filtered)
    total_ag2 = len(ag2_filtered)

    # Modern Custom Styled Row Cards
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Total Applications</div><div class="metric-value">{total_apps}</div></div>', unsafe_allow_html=True)
    with m_col2:
        approved_count = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'])
        st.markdown(f'<div class="metric-card"><div class="metric-title">QA Approved</div><div class="metric-value">{approved_count}</div></div>', unsafe_allow_html=True)
    with m_col3:
        live_count = len(ag2_filtered[ag2_filtered['P_Status'] == 'Live'])
        st.markdown(f'<div class="metric-card"><div class="metric-title">Live Portals</div><div class="metric-value">{live_count}</div></div>', unsafe_allow_html=True)
    with m_col4:
        conv_rate = (live_count / total_apps * 100) if total_apps > 0 else 0.0
        st.markdown(f'<div class="metric-card"><div class="metric-title">Pipeline Conversion</div><div class="metric-value">{conv_rate:.1f}%</div></div>', unsafe_allow_html=True)

    # ==========================================
    # PART 2: INSIGHT FLAGS
    # ==========================================
    flags_html = ""
    
    if total_apps > 0:
        q_appr = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Approved']) / total_apps
        q_can = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Cancelled']) / total_apps
        q_rej = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rejected']) / total_apps
        q_rew = len(ag1_filtered[ag1_filtered['Q_Status'] == 'Rework']) / total_apps

        if q_appr > 0.60: 
            flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Quality</p><p class="insight-phrase">High Approval Rate</p><p class="insight-comment">Excellent pitch and quality compliance!</p></div>'
        elif q_appr < 0.60: 
            flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality</p><p class="insight-phrase">Low Approval Rate</p><p class="insight-comment">Review the quality guidelines to increase quality approval!</p></div>'
        
        if q_can > 0.40: 
            flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Quality</p><p class="insight-phrase">High Cancellation</p><p class="insight-comment">High Quality Cancellations, review the quality guidelines!</p></div>'
        if q_rej > 0.20: 
            flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Quality</p><p class="insight-phrase">High Rejection</p><p class="insight-comment">High Quality Rejections! Pay attention to quality guidelines!</p></div>'
        if q_rew > 0.30: 
            flags_html += '<div class="insight-card" style="border-color:#3b82f6"><p class="insight-title">Quality</p><p class="insight-phrase">Frequent Reworks</p><p class="insight-comment">Pay closer attention to quality guidelines, to avoid large number of Quality Reworks.</p></div>'

        if wc_col:
            wc_done = len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Done']) / total_apps
            wc_can = len(ag1_filtered[ag1_filtered['WC_Clean'] == 'Cancelled']) / total_apps
            if wc_done < 0.70: 
                flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Welcome Call</p><p class="insight-phrase">Low Completion</p><p class="insight-comment">Address customer requirements closely to increase Welcome call approvals!</p></div>'
            if wc_can > 0.15: 
                flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Welcome Call</p><p class="insight-phrase">High WC Cancellation</p><p class="insight-comment">Address customer doubts in the sales call to avoid Welcome call cancellations!</p></div>'

    if total_ag2 > 0:
        l_live = len(ag2_filtered[ag2_filtered['P_Status'] == 'Live']) / total_ag2
        l_can = len(ag2_filtered[ag2_filtered['P_Status'] == 'Cancelled']) / total_ag2
        if l_live > 0.20: 
            flags_html += '<div class="insight-card" style="border-color:#10b981"><p class="insight-title">Live Stage</p><p class="insight-phrase">Strong Conversion</p><p class="insight-comment">Good live rate! Great overall quality of applications!</p></div>'
        elif l_live < 0.20: 
            flags_html += '<div class="insight-card" style="border-color:#f59e0b"><p class="insight-title">Live Stage</p><p class="insight-phrase">Low Live Rate</p><p class="insight-comment">Identify bottlenecks preventing sales from going live.</p></div>'
        if l_can > 0.65: 
            flags_html += '<div class="insight-card" style="border-color:#ef4444"><p class="insight-title">Live Stage</p><p class="insight-phrase">High Final Loss</p><p class="insight-comment">Large drops between applications and Committed. Identify bottlenecks!</p></div>'

    if flags_html:
        st.write("")
        st.subheader("💡 Points to Look Out For")
        st.markdown(f'<div class="insight-container">{flags_html}</div>', unsafe_allow_html=True)

    st.write("---")

    # ==========================================
    # DATA BREAKDOWN TABLES
    # ==========================================
    st.subheader("📅 Data Breakdown")
    ag1_filtered['Date'] = ag1_filtered['Date_Parsed'].dt.date
    ag2_filtered['Date'] = ag2_filtered['Date_Parsed'].dt.date
    view_mode = st.radio("View tables by:", ["Daily", "Monthly"], horizontal=True)
    
    if view_mode == "Daily":
        ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.date
        ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.date
        chart_group_col = 'Date'
    else:
        ag1_filtered['Period'] = ag1_filtered['Date_Parsed'].dt.strftime('%Y-%m')
        ag2_filtered['Period'] = ag2_filtered['Date_Parsed'].dt.strftime('%Y-%m')
        chart_group_col = 'Period'
    
    ca, cb, cc, cd = st.columns(4)
    with ca:
        st.markdown("<p style='font-weight:600; color:#475569; margin-bottom:8px;'>Applications</p>", unsafe_allow_html=True)
        if not ag1_filtered.empty:
            period_apps = ag1_filtered.groupby('Period').size().to_frame('Total Apps')
            vmax_apps = max(period_apps.max().max(), 1.1)
            styled_apps = period_apps.style.format(lambda x: "-" if x == 0 else x).background_gradient(cmap='Greens', vmin=1, vmax=vmax_apps).map(lambda x: 'background-color: transparent' if x == 0 else '')
            st.dataframe(styled_apps, use_container_width=True)
    with cb:
        st.markdown("<p style='font-weight:600; color:#475569; margin-bottom:8px;'>Quality Audit Result</p>", unsafe_allow_html=True)
        if not ag1_filtered.empty:
            period_qual = ag1_filtered.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
            qual_order = ['Approved', 'Rework', 'Cancelled', 'Rejected', 'Others']
            period_qual = period_qual.reindex(columns=qual_order, fill_value=0)
            period_qual = period_qual.loc[:, (period_qual != 0).any(axis=0)]
            if not period_qual.empty:
                vmax_qual = max(period_qual.max().max(), 1.1)
                styled_qual = period_qual.style.format(lambda x: "-" if x == 0 else x).background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Approved'])], vmin=1, vmax=vmax_qual).background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Rework'])], vmin=1, vmax=vmax_qual).background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_qual.columns.intersection(['Cancelled', 'Rejected'])], vmin=1, vmax=vmax_qual).map(lambda x: 'background-color: transparent' if x == 0 else '')
                st.dataframe(styled_qual, use_container_width=True)
    with cc:
        st.markdown("<p style='font-weight:600; color:#475569; margin-bottom:8px;'>Welcome Call Status</p>", unsafe_allow_html=True)
        if wc_col and not ag1_filtered.empty:
            period_wc = ag1_filtered.groupby(['Period', 'WC_Clean']).size().unstack(fill_value=0)
            wc_order = ['Done', 'Pending', 'Paperwork', 'Cancelled', 'Others']
            period_wc = period_wc.reindex(columns=wc_order, fill_value=0)
            period_wc = period_wc.loc[:, (period_wc != 0).any(axis=0)]
            if not period_wc.empty:
                vmax_wc = max(period_wc.max().max(), 1.1)
                styled_wc = period_wc.style.format(lambda x: "-" if x == 0 else x).background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Done'])], vmin=1, vmax=vmax_wc).background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Pending', 'Paperwork'])], vmin=1, vmax=vmax_wc).background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_wc.columns.intersection(['Cancelled'])], vmin=1, vmax=vmax_wc).map(lambda x: 'background-color: transparent' if x == 0 else '')
                st.dataframe(styled_wc, use_container_width=True)
        else: st.info("No Welcome Call data.")
    with cd:
        st.markdown("<p style='font-weight:600; color:#475569; margin-bottom:8px;'>Live Status</p>", unsafe_allow_html=True)
        if not ag2_filtered.empty:
            period_port = ag2_filtered.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
            port_order = ['Live', 'Committed', 'Cancelled', 'Others']
            period_port = period_port.reindex(columns=port_order, fill_value=0)
            period_port = period_port.loc[:, (period_port != 0).any(axis=0)]
            if not period_port.empty:
                vmax_port = max(period_port.max().max(), 1.1)
                styled_port = period_port.style.format(lambda x: "-" if x == 0 else x).background_gradient(cmap='Greens', subset=pd.IndexSlice[:, period_port.columns.intersection(['Live'])], vmin=1, vmax=vmax_port).background_gradient(cmap='Wistia', subset=pd.IndexSlice[:, period_port.columns.intersection(['Committed'])], vmin=1, vmax=vmax_port).background_gradient(cmap='Reds', subset=pd.IndexSlice[:, period_port.columns.intersection(['Cancelled'])], vmin=1, vmax=vmax_port).map(lambda x: 'background-color: transparent' if x == 0 else '')
                st.dataframe(styled_port, use_container_width=True)

    st.write("---")

    # ==========================================
    # TRENDS & CALENDAR WITH DISPOSITION TIPS
    # ==========================================
    col_trend, col_cal = st.columns([3, 2])
    with col_trend:
        st.subheader("📈 My Trend")
        if not ag1_filtered.empty:
            d_apps = ag1_filtered.groupby(chart_group_col).size().to_frame('Total Apps')
            d_appr = ag1_filtered[ag1_filtered['Q_Status'] == 'Approved'].groupby(chart_group_col).size().to_frame('Approved')
            d_live = ag2_filtered[ag2_filtered['P_Status'] == 'Live'].groupby(chart_group_col).size().to_frame('Live')
            i_comb = d_apps.join([d_appr, d_live], how='left').fillna(0).reset_index()
            i_comb[chart_group_col] = i_comb[chart_group_col].astype(str)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=i_comb[chart_group_col], y=i_comb['Total Apps'], name="Total Applications", marker_color='#3b82f6', opacity=0.85))
            fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Approved'], name="Quality Approved", line=dict(color='#10b981', width=3), mode='lines+markers'))
            fig.add_trace(go.Scatter(x=i_comb[chart_group_col], y=i_comb['Live'], name="Live Applications", line=dict(color='#f59e0b', width=3), mode='lines+markers'))
            fig.update_layout(
                hovermode="x unified", 
                margin=dict(l=10, r=10, t=30, b=10), 
                xaxis_title="Date" if view_mode=="Daily" else "Month",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig.update_xaxes(showgrid=True, gridcolor='#f1f5f9')
            fig.update_yaxes(showgrid=True, gridcolor='#f1f5f9')
            st.plotly_chart(fig, use_container_width=True)

    with col_cal:
        st.subheader("🗓️ Sales Activity Calendar")
        
        def is_holiday(dt):
            wd = dt.weekday() # 0=Mon, 6=Sun
            if wd == 6: return True 
            if wd == 5: 
                week_num = (dt.day - 1) // 7 + 1
                return week_num in [1, 3, 5] 
            return False

        c_month_col, c_year_col = st.columns(2)
        sel_month = c_month_col.selectbox("Month", list(calendar.month_name)[1:], index=today_date.month-1)
        sel_year = c_year_col.selectbox("Year", [2025, 2026], index=1)
        
        m_idx = list(calendar.month_name).index(sel_month)
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

        cal_df['HoverText'] = cal_df.apply(lambda r: "Holiday" if r['Type'] == 'Holiday' else f"Sales: {r['Sales']}", axis=1)

        fig_cal = go.Figure()
        working_days = cal_df[cal_df['Type'] == 'Working']
        fig_cal.add_trace(go.Heatmap(
            x=working_days['Weekday'], y=working_days['WeekNum'], z=working_days['Sales'],
            text=working_days['Day'], 
            customdata=working_days['HoverText'],
            hovertemplate="%{customdata}<extra></extra>",
            texttemplate="%{text}",
            colorscale=[[0, '#f8fafc'], [0.1, '#d1fae5'], [1, '#047857']],
            showscale=False, xgap=4, ygap=4
        ))

        holidays = cal_df[cal_df['Type'] == 'Holiday']
        fig_cal.add_trace(go.Scatter(
            x=holidays['Weekday'], y=holidays['WeekNum'], mode='markers+text',
            marker=dict(symbol='square', size=32, color='#e0f2fe', line=dict(color='#bae6fd', width=1)),
            text=holidays['Day'], 
            customdata=holidays['HoverText'],
            hovertemplate="%{customdata}<extra></extra>",
            textfont=dict(color='#0284c7', weight='bold'),
            showlegend=False
        ))

        fig_cal.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=10),
            xaxis=dict(side="top", categoryorder='array', categoryarray=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], showgrid=False),
            yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, showticklabels=False),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_cal, use_container_width=True)
        st.markdown("<p style='font-size:0.85rem; text-align:center;'>🟢 Active Activity | ⚪ Idle Period | 🔵 Operational Rest Day </p>", unsafe_allow_html=True)

    st.write("---")

    # ==========================================
    # RECENT APPLICATIONS LOG WITH SECTIONS
    # ==========================================
    st.subheader("🔍 Recent Applications Log")
    if not ag1.empty:
        ag2_clean = ag2.copy()
        ag2_clean['Telephone No.'] = ag2_clean['Telephone No.'].astype(str).str.strip()
        ag2_clean = ag2_clean.rename(columns={'Status': 'Portal Status', 'Committed Date': 'Live Date'})
        ag2_unique = ag2_clean.sort_values('Date_Parsed').drop_duplicates('Telephone No.', keep='last')
        
        ag1_log_base = ag1.copy()
        ag1_log_base['CLI_Key'] = ag1_log_base['CLI'].astype(str).str.strip()
        merged_log = ag1_log_base.merge(
            ag2_unique[['Telephone No.', 'LetterStatus', 'CallStatus', 'Comments', 'Voice of Customer', 'Cancellation Reason', 'Portal Status', 'Live Date']],
            left_on='CLI_Key', 
            right_on='Telephone No.', 
            how='left'
        )

        merged_log['Sale Date'] = pd.to_datetime(merged_log['Standardized_Date'], errors='coerce').dt.strftime('%d-%m-%Y').fillna('')
        merged_log['Live Date'] = pd.to_datetime(merged_log['Live Date'], errors='coerce').dt.strftime('%d-%m-%Y').fillna('')

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
        
        log_col1, log_col2, log_col3 = st.columns([2, 2, 1])
        with log_col1:
            log_filter_type = st.radio("Log View Filter:", ["All Applications", "By Specific Date Range", "By Specific Month"], horizontal=True)
        with log_col2:
            if log_filter_type == "By Specific Date Range":
                ld_col1, ld_col2 = st.columns(2)
                log_start = ld_col1.date_input("Log Start Date", today_date.replace(day=1), key="log_start_date")
                log_end = ld_col2.date_input("Log End Date", today_date, key="log_end_date")
                recent_log = merged_log[(merged_log['Date_Parsed'].dt.date >= log_start) & (merged_log['Date_Parsed'].dt.date <= log_end)].sort_values(by='Date_Parsed', ascending=False)
            elif log_filter_type == "By Specific Month":
                unique_months = sorted(merged_log['Date_Parsed'].dt.strftime('%Y-%m').dropna().unique(), reverse=True)
                if unique_months:
                    selected_month = st.selectbox("Select Month for Log (YYYY-MM):", unique_months)
                    recent_log = merged_log[merged_log['Date_Parsed'].dt.strftime('%Y-%m') == selected_month].sort_values(by='Date_Parsed', ascending=False)
                else:
                    recent_log = merged_log[0:0]
            else:
                recent_log = merged_log.sort_values(by='Date_Parsed', ascending=False)

        recent_log['S.No.'] = range(1, len(recent_log) + 1)

        with log_col3:
            row_limit = st.selectbox("Show records per page:", [5, 10, 20, 50, 100, "All"], index=2)

        valid_layout = [item for item in columns_layout if item[1] in recent_log.columns]
        display_df = recent_log[[item[1] for item in valid_layout]].copy()
        display_df.columns = pd.MultiIndex.from_tuples(valid_layout)

        table_container = st.container()

        if "current_page" not in st.session_state:
            st.session_state.current_page = 1

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
                    st.markdown(f"<p style='color: #64748b; font-size: 0.85rem; margin-top: 6px;'>Showing {start_idx + 1} to {end_idx} of {total_records} entries</p>", unsafe_allow_html=True)
                with pag_col2:
                    b_col1, b_col2, b_col3 = st.columns([2, 1, 1])
                    with b_col1:
                        st.markdown(f"<p style='text-align: right; color: #64748b; font-size: 0.85rem; margin-top: 6px;'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
                    with b_col2:
                        if st.button("Previous", disabled=(st.session_state.current_page == 1), use_container_width=True, key="prev_pg_action"):
                            st.session_state.current_page -= 1
                            st.rerun()
                    with b_col3:
                        if st.button("Next", disabled=(st.session_state.current_page == total_pages), use_container_width=True, key="next_pg_action"):
                            st.session_state.current_page += 1
                            st.rerun()
        else:
            display_df_page = display_df

        def style_log_row(row):
            styles = [''] * len(row)
            
            def get_val(col_name):
                for col in row.index:
                    if col[1] == col_name: return str(row[col]).lower()
                return ""

            DARK_GREEN = '#065F46'
            DARK_AMBER = '#92400E'
            DARK_RED = '#991B1B'

            BG_GREEN = 'rgba(16, 185, 129, 0.15)'
            BG_AMBER = 'rgba(245, 158, 11, 0.15)'
            BG_RED   = 'rgba(239, 68, 68, 0.15)'

            q_val = get_val('Quality Status')
            q_bg, q_txt = '', ''
            if any(x in q_val for x in ['appr', 'pass']):
                q_bg, q_txt = BG_GREEN, DARK_GREEN
            elif any(x in q_val for x in ['rew', 'repro']):
                q_bg, q_txt = BG_AMBER, DARK_AMBER
            elif any(x in q_val for x in ['can', 'rej']):
                q_bg, q_txt = BG_RED, DARK_RED
            q_style = f'background-color: {q_bg}; color: {q_txt}; font-weight: 600;' if q_bg else ''

            wc_val = get_val('Status')
            wc_bg, wc_txt = '', ''
            if any(x in wc_val for x in ['done', 'pass', 'comp', 'live']):
                wc_bg, wc_txt = BG_GREEN, DARK_GREEN
            elif any(x in wc_val for x in ['pend', 'pnd', 'paper', 'ppw', 'com']):
                wc_bg, wc_txt = BG_AMBER, DARK_AMBER
            elif any(x in wc_val for x in ['can', 'rej']):
                wc_bg, wc_txt = BG_RED, DARK_RED
            wc_style = f'background-color: {wc_bg}; color: {wc_txt}; font-weight: 600;' if wc_bg else ''

            call_val = get_val('CallStatus')
            c_bg, c_txt = '', ''
            if 'satisfied' in call_val:
                c_bg, c_txt = BG_GREEN, DARK_GREEN
            elif any(x in call_val for x in ['pend', 'cancel']):
                c_bg, c_txt = BG_RED, DARK_RED
            c_style = f'background-color: {c_bg}; color: {c_txt}; font-weight: 600;' if c_bg else ''
            
            portal_val = get_val('Portal Status')
            p_bg, p_txt = '', ''
            if 'live' in portal_val:
                p_bg, p_txt = BG_GREEN, DARK_GREEN
            elif 'committed' in portal_val:
                p_bg, p_txt = BG_AMBER, DARK_AMBER
            elif any(x in portal_val for x in ['rej', 'cancel']):
                p_bg, p_txt = BG_RED, DARK_RED
            p_style = f'background-color: {p_bg}; color: {p_txt}; font-weight: 600;' if p_bg else ''

            quality_cols = ['S.No.', 'Sale Date', 'Customer Name', 'Quality Status', 'Quality Remarks']
            portal_group = ['Portal Status', 'Live Date', 'Comments', 'Voice of Customer', 'Cancellation Reason']
            
            for i, col_tuple in enumerate(row.index):
                col = col_tuple[1] 
                current_style = ""
                
                if col == 'LetterStatus':
                    current_style = 'background-color: rgba(59, 130, 246, 0.1);'
                elif col == 'CallStatus':
                    current_style = c_style
                elif col in portal_group:
                    if col == 'Portal Status':
                        current_style = p_style
                    else:
                        current_style = f'background-color: {p_bg};' if p_bg else ''
                elif col in quality_cols:
                    if col == 'Quality Status':
                        current_style = q_style
                    else:
                        current_style = f'background-color: {q_bg};' if q_bg else ''
                else:
                    if col == 'Status':
                        current_style = wc_style
                    else:
                        current_style = f'background-color: {wc_bg};' if wc_bg else ''
                
                if col == 'S.No.':
                    current_style += 'border-left: 3px solid #1e3a8a;'
                
                if col in ['Customer Name', 'Quality Remarks', 'Welcome call Remarks', 'Cancellation Reason']:
                    current_style += 'border-right: 2px solid #cbd5e1;'
                
                styles[i] = current_style
            return styles           
        
        styled_log = display_df_page.style.apply(style_log_row, axis=1)
        
        with table_container:
            st.dataframe(styled_log, use_container_width=True, hide_index=True)

    # ==========================================
    # DISPOSITION PERFORMANCE TIPS
    # ==========================================
    st.markdown("""
        <div class="tips-box">
            <div class="tips-title">💡 Performance Insights: Call Dispositions & Pipeline Quality</div>
            <ul class="tips-list">
                <li><b>Answering Machines:</b> Do not dispose active customer connections as an "Answering Machine" if the Customer Talk Time exceeds 30 seconds. Use it primarily when a pre-recorded voicemail is reached.</li>
                <li><b>Customer Hangup:</b> This should be selected when the customer abruptly ends the conversation during an active connection.</li>
                <li><b>No Answer:</b> Use strictly when the line rings out completely without customer acquisition.</li>
                <li><b>Sky TV packages/Virgin:</b> Errors encountered on the Talk-Talk portal must be cataloged here. Do not mark as Not Interested or Hangup, as resetting these preserves systemic record integrity.</li>
                <li><b>Wrong Number:</b> Use when target systemic demographics fail verification against real-time feedback.</li>
                <li><b>Family Interference/POA:</b> Select if a relative or Power of Attorney assumes financial management.</li>
                <li><b>Dementia:</b> Use if the client displays vulnerability or profound memory conflicts during compliance.</li>
                <li><b>Over Age:</b> Restrict to target profiles where birth years precede 1940 or age exceeds 85.</li>
                <li><b>Mobile Number:</b> Route any standard communication profile prefix starting with "7" here.</li>
                <li><b>Social Alarm VOIP:</b> Mandatory toggle if the customer uses an integrated Careline/Medical fallback array.</li>
                <li><b>Hang up on bank details:</b> Record drops exactly at the point of secure credentialing collection.</li>
                <li><b>Busy:</b> Customer requested callback or line is actively occupied.</li>
                <br>
                <li><b>🚫 Dispositions removed from active calling cycles:</b> Dementia | Family Interference / POA | Sky TV Packages / Virgin | Over Age</li>
                <li><b>🔄 Dispositions maintaining active dialer recycling loops:</b> Answering Machine | Customer Hangup | Interested | Callback</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)
    st.write("---")

except Exception as e: 
    st.error(f"Error executing dashboard compilation: {e}")
