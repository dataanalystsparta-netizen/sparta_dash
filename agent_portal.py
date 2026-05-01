import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Sparta Agent Portal", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
.insight-card {
    background-color: #f8f9fa;
    border-radius: 5px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    text-align: center;
    margin-bottom: 20px;
}
.insight-value {
    font-size: 24px;
    font-weight: bold;
    color: #007bff;
}
.insight-label {
    font-size: 14px;
    color: #6c757d;
}
</style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login():
    st.session_state['logged_in'] = True

def logout():
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Sparta Agent Portal - Login")
    st.text_input("Username", key="user_input")
    st.text_input("Password", type="password", key="pass_input")
    st.button("Login", on_click=login)
    st.stop()

# --- MAIN APP ---
st.sidebar.button("Logout", on_click=logout)
st.title("📊 Sparta Agent Portal - Performance Dashboard")

# --- DATA GENERATION (Mock Data with MultiIndex) ---
@st.cache_data
def load_data():
    np.random.seed(42)
    months = ['January', 'February', 'March', 'April']
    
    # Note: Using 'approve' terminology standard
    statuses = ['approve', 'cancel', 'pending'] 
    quality = ['pass', 'fail', 'pending']
    
    data = {
        'Agent Name': ['Aditya'] * 50,
        'Month': np.random.choice(months, 50),
        'Application ID': np.random.randint(1000, 9999, 50),
        ('Basic Info', 'Customer'): [f"Cust_{i}" for i in range(50)],
        ('Quality Audit', 'Quality Status'): np.random.choice(quality, 50),
        ('Portal Data', 'Status'): np.random.choice(statuses, 50),
        ('Welcome Call', 'CallStatus'): np.random.choice(['approve', 'cancel'], 50),
        ('Portal Data', 'Portal Status'): np.random.choice(['live', 'error', 'pending'], 50),
        ('Metrics', 'Conversion Rate'): np.random.uniform(0.1, 0.9, 50)
    }
    
    # Structuring MultiIndex exactly as required
    tuples = [
        ('Basic Info', 'Agent Name'), 
        ('Basic Info', 'Month'), 
        ('Basic Info', 'Application ID'), 
        ('Basic Info', 'Customer'), 
        ('Quality Audit', 'Quality Status'), 
        ('Portal Data', 'Status'), 
        ('Welcome Call', 'CallStatus'), 
        ('Portal Data', 'Portal Status'), 
        ('Metrics', 'Conversion Rate')
    ]
    
    df = pd.DataFrame({
        'Agent Name': data['Agent Name'],
        'Month': data['Month'],
        'Application ID': data['Application ID'],
        'Customer': data['Basic Info', 'Customer'],
        'Quality Status': data['Quality Audit', 'Quality Status'],
        'Status': data['Portal Data', 'Status'],
        'CallStatus': data['Welcome Call', 'CallStatus'],
        'Portal Status': data['Portal Data', 'Portal Status'],
        'Conversion Rate': data['Metrics', 'Conversion Rate']
    })
    
    df.columns = pd.MultiIndex.from_tuples(tuples)
    return df

df = load_data()

# --- FILTERS ---
st.subheader("Data Filters")
selected_month = st.selectbox("Select Month", options=['All'] + list(df[('Basic Info', 'Month')].unique()))

if selected_month != 'All':
    filtered_df = df[df[('Basic Info', 'Month')] == selected_month]
else:
    filtered_df = df

# --- INSIGHT CARDS ---
st.subheader("Performance Insights")
col1, col2, col3 = st.columns(3)

total_apps = len(filtered_df)
approved_mask = filtered_df[('Portal Data', 'Status')].str.lower() == 'approve'
cancelled_mask = filtered_df[('Portal Data', 'Status')].str.lower() == 'cancel'

approval_rate = (filtered_df[approved_mask].shape[0] / total_apps * 100) if total_apps > 0 else 0
cancel_rate = (filtered_df[cancelled_mask].shape[0] / total_apps * 100) if total_apps > 0 else 0

with col1:
    st.markdown(f"""
    <div class="insight-card">
        <div class="insight-label">Total Applications</div>
        <div class="insight-value">{total_apps}</div>
    </div>
    """, unsafe_allow_html=True)
    
with col2:
    st.markdown(f"""
    <div class="insight-card">
        <div class="insight-label">Approval Rate</div>
        <div class="insight-value">{approval_rate:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="insight-card">
        <div class="insight-label">Cancellation Rate</div>
        <div class="insight-value">{cancel_rate:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

# --- DATA TABLE STYLING & RENDERING ---
st.subheader("Recent Applications Log")

def style_status(val):
    """Applies matching background, text color, and bolding based on status."""
    if pd.isna(val):
        return ''
    
    val_str = str(val).lower()
    
    # Green mapping
    if any(x in val_str for x in ['approve', 'pass', 'live', 'success']):
        bg_color = '#e6ffe6'
        text_color = '#008000'
    # Red mapping
    elif any(x in val_str for x in ['cancel', 'fail', 'reject', 'error']):
        bg_color = '#ffe6e6'
        text_color = '#cc0000'
    # Amber/Orange mapping
    elif any(x in val_str for x in ['pending', 'awaiting', 'hold']):
        bg_color = '#fff4e6'
        text_color = '#e67300'
    else:
        return ''
        
    return f'background-color: {bg_color}; color: {text_color}; font-weight: bold;'

# 1. Format percentages
format_dict = {('Metrics', 'Conversion Rate'): '{:.1%}'}
styled_df = filtered_df.style.format(format_dict)

# 2. Target specific columns for color and bolding
target_columns = [
    ('Quality Audit', 'Quality Status'),
    ('Portal Data', 'Status'),
    ('Welcome Call', 'CallStatus'),
    ('Portal Data', 'Portal Status')
]

# Ensure we only apply to columns that actually exist in the dataframe structure
existing_targets = [col for col in target_columns if col in filtered_df.columns]

if existing_targets:
    styled_df = styled_df.map(style_status, subset=existing_targets)

# 3. Render the interactive table (Allows header sorting out-of-the-box)
st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True,
    height=600
)
