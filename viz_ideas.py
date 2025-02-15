import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, date
from pdf_utils import extract_report_data, get_report_date
import re
import shutil
from parameters_rename_agent import fix_parameters_across_json
from personalised_reco_agent import get_personalized_recommendations

# --- Constants ---
REPORTS_DIR = "reports"
ORIGINAL_EXTRACTS_DIR = "report_extracts"
RENAMED_EXTRACTS_DIR = "renamed_report_extracts"

# --- Core Functions ---
def fix_and_load_reports(directory):
    """Loads all JSON reports and returns a DataFrame."""
    fix_parameters_across_json()
    reports = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            with open(os.path.join(directory, filename), 'r') as f:
                data = json.load(f)
                try:
                    data['report_date'] = pd.to_datetime(data.get('report_date', pd.NaT))
                except ValueError:
                    data['report_date'] = pd.NaT
                for param in data['parameters']:
                    param['report_date'] = data['report_date']
                    param['patient_name'] = data.get('patient_name', 'Unknown')
                    reports.append(param)
    return pd.DataFrame(reports)

def process_pdf_reports(uploaded_files):
    """Handles PDF processing and data extraction."""
    for dir_path in [REPORTS_DIR, ORIGINAL_EXTRACTS_DIR]:
        os.makedirs(dir_path, exist_ok=True)

    for uploaded_file in uploaded_files:
        pdf_storage_path = os.path.join(REPORTS_DIR, uploaded_file.name)
        if os.path.exists(pdf_storage_path):
            st.warning(f"Skipping existing file: {uploaded_file.name}")
            continue

        with open(pdf_storage_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        temp_path = os.path.join(REPORTS_DIR, f"temp_{uploaded_file.name}")
        shutil.copyfile(pdf_storage_path, temp_path)

        try:
            report_data = extract_report_data(temp_path)
            report_date = get_report_date(report_data, uploaded_file.name)
            output_path = os.path.join(ORIGINAL_EXTRACTS_DIR, f"report_{report_date}.json")
            with open(output_path, 'w') as f:
                json.dump(json.loads(report_data), f, indent=4)
            st.success(f"Processed: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

# --- Visualization Components ---
def create_health_dashboard(df):
    """Main dashboard with health metrics."""
    st.header("Health Overview")
    
    # Score Cards
    current_score = calculate_health_score(df)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tracked Parameters", df['name'].nunique())
    with col2:
        abnormal = df[df['result_status'] != 'normal'].shape[0]
        st.metric("Abnormal Readings", abnormal)
    with col3:
        st.metric("Health Score", f"{current_score}/100")
    
    # Score Timeline
    plot_score_timeline(df)

def calculate_health_score(df):
    """Calculates overall health score with error handling"""
    try:
        # Convert results to numeric
        df['numeric_result'] = pd.to_numeric(df['result'], errors='coerce')
        
        # Classify results with fallback
        df['result_status'] = df.apply(classify_result, axis=1).fillna('unknown')
        
        # Define weights with default for unknown
        status_weights = {
            'normal': 1.0,
            'low': 0.7,
            'high': 0.7,
            'critical': 0.4,
            'unknown': 0.5  # Neutral weight for unclassified
        }
        
        # Calculate score with fallback for empty data
        if df.empty:
            return 0
            
        scores = df['result_status'].map(status_weights).dropna()
        if scores.empty:
            return 0
            
        return int(scores.mean() * 100)
        
    except Exception as e:
        st.error(f"Error calculating health score: {str(e)}")
        return 0

def classify_result(row):
    """Classifies results into normal/low/high categories."""
    try:
        ref = row.get('reference_interval.normal', '')
        if not ref or '-' not in ref: return 'unknown'
        low, high = map(float, ref.split('-'))
        value = float(row['result'])
        return 'low' if value < low else 'high' if value > high else 'normal'
    except:
        return 'unknown'

def plot_score_timeline(df):
    """Plots health score timeline."""
    timeline = df.groupby('report_date').apply(lambda x: calculate_health_score(x))
    fig = px.area(timeline.reset_index(), x='report_date', y=0, 
                 title="Health Score Trend", labels={'0': 'Score'})
    fig.update_layout(yaxis_range=[0, 100])
    st.plotly_chart(fig)

def enhanced_parameter_view(df, param):
    """Detailed parameter analysis view."""
    df_param = prepare_param_data(df, param)
    
    # Visualization
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_param.report_date, y=df_param.result, 
                           name="Values", line=dict(color='#3498db')))
    if df_param.ref_low.any() and df_param.ref_high.any():
        fig.add_hrect(y0=df_param.ref_low.iloc[0], y1=df_param.ref_high.iloc[0],
                     fillcolor='#2ecc71', opacity=0.2)
    
    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig)
    with col2:
        st.metric("Current Value", df_param.result.iloc[-1])
        st.metric("Normal Range", f"{df_param.ref_low.iloc[0]}-{df_param.ref_high.iloc[0]}")
        st.metric("Trend", f"{df_param.result.pct_change().iloc[-1]:.1%}")

def prepare_param_data(df, param):
    """Prepares parameter-specific data."""
    df_param = df[df.name == param].copy()
    df_param['report_date'] = pd.to_datetime(df_param.report_date)
    df_param['result'] = pd.to_numeric(df_param.result, errors='coerce')
    
    # Extract reference ranges
    try:
        ref_range = df_param['reference_interval.normal'].iloc[0]
        df_param['ref_low'], df_param['ref_high'] = zip(*df_param['reference_interval.normal'].apply(
            lambda x: map(float, x.split('-')) if x else (None, None)))
    except:
        df_param['ref_low'] = df_param['ref_high'] = None
    
    return df_param.dropna(subset=['result'])

# --- Lifestyle Integration ---
def lifestyle_tracker():
    """Sidebar wellness tracking."""
    with st.sidebar.expander("Daily Wellness Log"):
        sleep = st.slider("Sleep Hours", 0.0, 12.0, 7.0)
        activity = st.selectbox("Activity Level", ["Sedentary", "Light", "Moderate", "Active"])
        if st.button("Save Log"):
            st.session_state.setdefault('logs', []).append({
                'date': date.today().isoformat(),
                'sleep': sleep,
                'activity': activity
            })
            st.success("Log saved!")

# --- Main App Structure ---
def main():
    st.set_page_config(page_title="Health Dashboard", layout="wide")
    st.title("Comprehensive Health Tracker")
    
    # File Processing
    uploaded_files = st.file_uploader("Upload medical reports", 
                                    type=["pdf"], 
                                    accept_multiple_files=True)
    if uploaded_files and st.button("Process Reports"):
        process_pdf_reports(uploaded_files)
        st.cache_data.clear()

    # Data Loading
    @st.cache_data
    def load_data():
        return fix_and_load_reports(RENAMED_EXTRACTS_DIR)
    
    if os.path.exists(RENAMED_EXTRACTS_DIR):
        df = load_data()
        if not df.empty:
            lifestyle_tracker()
            create_health_dashboard(df)
            
            # Parameter Analysis
            selected_param = st.selectbox("Select Parameter", df.name.unique())
            enhanced_parameter_view(df, selected_param)
            
            # Recommendations
            st.subheader("Personalized Advice")
            for patient in df.patient_name.unique():
                patient_data = df[df.patient_name == patient]
                if selected_param in patient_data.name.values:
                    rec = get_personalized_recommendations(
                        patient, selected_param,
                        patient_data[patient_data.name == selected_param]
                    )
                    with st.expander(f"Recommendations for {patient}"):
                        st.write(rec)
        else:
            st.info("No data found - upload reports first")
    else:
        st.info("Please upload medical reports to begin")

if __name__ == "__main__":
    main()