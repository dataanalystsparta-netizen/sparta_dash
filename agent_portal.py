import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import calendar
import datetime
import math

# -----------------------------------------------------------------------------
# 1. GLOBAL CUSTOM MODERN CSS (Inject at the top of the app)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* App Canvas styling */
    .stApp {
        background-color: #f8fafc;
    }
    
    /* Modern Insight Card Containers */
    .insight-container {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .insight-card {
        flex: 1 1 calc(25% - 16px);
        min-width: 240px;
        background-color: #ffffff;
        border-left: 5px solid #cbd5e1;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
        transition: transform 0.2s ease;
    }
    .insight-card:hover {
        transform: translateY(-2px);
    }
    .insight-title {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .insight-phrase {
        font-size: 1.15rem;
        color: #0f172a;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .insight-comment {
        font-size: 0.87rem;
        color: #475569;
        line-height: 1.4;
        margin: 0;
    }

    /* Beautiful Custom Call Disposition Box */
    .tips-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        margin-top: 25px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.03);
    }
    .tips-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .tips-list {
        list-style-type: none;
        padding-left: 0;
        margin: 0;
    }
    .tips-list > li {
        position: relative;
        padding-left: 20px;
        margin-bottom: 12px;
        font-size: 0.93rem;
        color: #334155;
        line-height: 1.6;
    }
    .tips-list > li::before {
        content: "•";
        position: absolute;
        left: 0;
        color: #3b82f6;
        font-weight: bold;
        font-size: 1.2rem;
        top: -2px;
    }
    .tips-list ul {
        list-style-type: none;
        padding-left: 20px;
        margin-top: 6px;
    }
    .tips-list ul li {
        position: relative;
        padding-left: 15px;
        margin-bottom: 4px;
        font-size: 0.88rem;
        color: #475569;
    }
    .tips-list ul li::before {
        content: "◦";
        position: absolute;
        left: 0;
        color: #64748b;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


try:
    # -----------------------------------------------------------------------------
    # [KEEP DATA INGESTION EXACTLY AS IT IS]
    # (Assuming data handling, ag1, ag2, variables like total_apps, wc_col, etc., 
    # run right here completely unmodified)
    # -----------------------------------------------------------------------------

    # ---------------- INSIGHT FLAGS (MODERNIZED OVERHAUL) ----------------
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

    # ----------------📅 DATA BREAKDOWN (ROBUST STREAMLIT NATIVE FORMATTING) ----------------
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
    
    # Clean formatter configuration using native elements to guarantee sorting handles flawlessly
    def modern_table_render(df, colorscale_map=None):
        return st.dataframe(
            df,
            use_container_width=True,
            column_config={col: st.column_config.NumberColumn(format="%d") for col in df.columns}
        )

    with ca:
        st.markdown("##### Applications")
        if not ag1_filtered.empty:
            period_apps = ag1_filtered.groupby('Period').size().to_frame('Total Apps')
            modern_table_render(period_apps)
            
    with cb:
        st.markdown("##### Quality Audit Result")
        if not ag1_filtered.empty:
            period_qual = ag1_filtered.groupby(['Period', 'Q_Status']).size().unstack(fill_value=0)
            qual_order = ['Approved', 'Rework', 'Cancelled', 'Rejected', 'Others']
            period_qual = period_qual.reindex(columns=qual_order, fill_value=0)
            period_qual = period_qual.loc[:, (period_qual != 0).any(axis=0)]
            if not period_qual.empty:
                modern_table_render(period_qual)
                
    with cc:
        st.markdown("##### Welcome Call Status")
        if wc_col and not ag1_filtered.empty:
            period_wc = ag1_filtered.groupby(['Period', 'WC_Clean']).size().unstack(fill_value=0)
            wc_order = ['Done', 'Pending', 'Paperwork', 'Cancelled', 'Others']
            period_wc = period_wc.reindex(columns=wc_order, fill_value=0)
            period_wc = period_wc.loc[:, (period_wc != 0).any(axis=0)]
            if not period_wc.empty:
                modern_table_render(period_wc)
        else: 
            st.info("No Welcome Call data.")
            
    with cd:
        st.markdown("##### Live Status")
        if not ag2_filtered.empty:
            period_port = ag2_filtered.groupby(['Period', 'P_Status']).size().unstack(fill_value=0)
            port_order = ['Live', 'Committed', 'Cancelled', 'Others']
            period_port = period_port.reindex(columns=port_order, fill_value=0)
            period_port = period_port.loc[:, (period_port != 0).any(axis=0)]
            if not period_port.empty:
                modern_table_render(period_port)

    st.write("---")

    # ---------------- 📈 TRENDS & CALENDAR OVERHAUL ----------------
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
            fig.add_trace(go.Bar(
                x=i_comb[chart_group_col], y=i_comb['Total Apps'], 
                name="Total Applications", marker_color='#60A5FA', opacity=0.85
            ))
            fig.add_trace(go.Scatter(
                x=i_comb[chart_group_col], y=i_comb['Approved'], 
                name="Quality Approved", line=dict(color='#10B981', width=3, shape='spline')
            ))
            fig.add_trace(go.Scatter(
                x=i_comb[chart_group_col], y=i_comb['Live'], 
                name="Live Applications", line=dict(color='#F59E0B', width=3, shape='spline')
            ))
            fig.update_layout(
                hovermode="x unified", 
                margin=dict(l=10, r=10, t=20, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_title="Date" if view_mode=="Daily" else "Month",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter, sans-serif")
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor='#e2e8f0')
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
            colorscale=[[0, '#f8fafc'], [0.1, '#e6f4ea'], [1, '#137333']],
            showscale=False, xgap=4, ygap=4
        ))

        holidays = cal_df[cal_df['Type'] == 'Holiday']
        fig_cal.add_trace(go.Scatter(
            x=holidays['Weekday'], y=holidays['WeekNum'], mode='markers+text',
            marker=dict(symbol='square', size=30, color='#e0f2fe', line=dict(color='#bae6fd', width=1)),
            text=holidays['Day'], 
            customdata=holidays['HoverText'],
            hovertemplate="%{customdata}<extra></extra>",
            textfont=dict(color='#0284c7', weight='bold'),
            showlegend=False
        ))

        fig_cal.update_layout(
            height=280, margin=dict(l=5, r=5, t=5, b=5),
            xaxis=dict(side="top", categoryorder='array', categoryarray=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
            yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_cal, use_container_width=True)
        st.caption("🟢 High Volume | ⚪ Zero Sales | 🔵 Standard Scheduled Off Day ")

    st.write("---")

    # ---------------- 🔍 RECENT APPLICATIONS LOG (MODERN INTERACTIVE TABLE) ----------------
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
        
        log_col1, log_col2, log_col3 = st.columns([1.8, 2.2, 1])
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
        else:
            display_df_page = display_df

        # Clean, ultra-fast table streaming using native column config for dynamic alignment/sorting
        with table_container:
            st.dataframe(
                display_df_page, 
                use_container_width=True, 
                hide_index=True
            )

        # ------------ DISPOSITION PERFORMANCE TIPS (CLEANED UP CSS MARKUP) ---
        st.markdown("""
            <div class="tips-box">
                <div class="tips-title">💡 Performance Details: Correct Call Dispositions and Data Quality</div>
                <ul class="tips-list">
                    <li><b>Answering Machines:</b> Do not dispose active customer connections as an "Answering Machine" especially if the Customer Talk Time/connectivity exceeds 30 seconds. Use it primarily when you hear a pre-recorded Answering Machine/Voicemail message.</li>
                    <li><b>Customer Hangup:</b> This disposition should be used when the customer abruptly hangs up. Should be used for active/connected customers.</li>
                    <li><b>No Answer:</b> Dispose as "No Answer" only if the customer does not pick up the call.</li>
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
                            <li>Dementia</li>
                            <li>Family Interference / POA</li>
                            <li>Sky TV Packages / Virgin</li>
                            <li>Over Age</li>
                        </ul>
                    </li>
                    <br>
                    <li><b>🔄 Dispositions that WILL reappear frequently on the dialler:</b>
                        <ul>
                            <li>Answering Machine</li>
                            <li>Customer Hangup</li>
                            <li>Interested</li>
                            <li>Callback</li>
                        </ul>
                    </li>
                    <br>
                    <li><u><b>Data Accuracy and Quality: The more accurate the disposition you enter, the better quality of the data would appear on the dialler for the entire team.</b></u></li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
        st.write("---")

except Exception as e: 
    st.error(f"Error encountered during script runtime execution: {e}")
