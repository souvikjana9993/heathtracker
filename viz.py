# viz.py
import os
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from pdf_utils import extract_report_data, get_report_date
import re
import shutil
from parameters_rename_agent import fix_parameters_across_json
from personalised_reco_agent import get_personalized_recommendations
from summary_agent import get_overall_summary  # New import

# --- Constants ---
REPORTS_DIR = "reports"  # Temporary storage during upload
ORIGINAL_EXTRACTS_DIR = "report_extracts"
RENAMED_EXTRACTS_DIR = "renamed_report_extracts"

# Set wide layout
st.set_page_config(layout="wide")

# --- Functions ---
def fix_and_load_reports(directory):
    """Loads all JSON reports from the given directory and returns a DataFrame."""
    fix_parameters_across_json()
    reports = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r') as f:
                try:
                    data = json.load(f)
                    # Handle report date conversion
                    if 'report_date' in data:
                        try:
                            data['report_date'] = pd.to_datetime(data['report_date'])
                        except (ValueError, pd.errors.ParserError):
                            data['report_date'] = pd.NaT
                    else:
                        data['report_date'] = pd.NaT

                    # Process parameters
                    for param in data['parameters']:
                        # Convert stringified reference_interval to dict
                        if 'reference_interval' in param:
                            if isinstance(param['reference_interval'], str):
                                try:
                                    param['reference_interval'] = json.loads(param['reference_interval'])
                                except json.JSONDecodeError:
                                    param['reference_interval'] = {}

                        # Add metadata to each parameter
                        param['report_date'] = data['report_date']
                        param['patient_name'] = data.get('patient_name', 'Unknown')
                        reports.append(param)
                except json.JSONDecodeError as e:
                    st.error(f"Error loading {filename}: {str(e)}")
    return pd.DataFrame(reports)

def plot_trend(df, parameter_name):
    """Filters for a parameter and plots its trend over time."""
    df_param = df[df['name'] == parameter_name].copy()
    # Clean numerical values
    df_param['result'] = pd.to_numeric(
        df_param['result'].str.replace('<', '').str.replace('>', '').str.strip(), 
        errors='coerce'
    )
    fig = px.line(
        df_param,
        x='report_date',
        y='result',
        markers=True,
        title=f"Trend for {parameter_name}",
        color='patient_name'
    )
    # Remove time and legend formatting
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False)
    )
    return fig

def process_pdf_reports(uploaded_files):
    """Processes uploaded PDF reports and saves extracted data to JSON files."""
    # Ensure directories exist
    for dir_path in [REPORTS_DIR, ORIGINAL_EXTRACTS_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    for uploaded_file in uploaded_files:
        # Create permanent storage path
        pdf_storage_path = os.path.join(REPORTS_DIR, uploaded_file.name)
        
        # Skip existing files
        if os.path.exists(pdf_storage_path):
            st.warning(f"PDF {uploaded_file.name} already exists. Skipping.")
            continue

        # Save uploaded file
        with open(pdf_storage_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Create temporary processing path
        temp_pdf_path = os.path.join(REPORTS_DIR, f"temp_{uploaded_file.name}")
        shutil.copyfile(pdf_storage_path, temp_pdf_path)

        # Process PDF
        try:
            report_data = extract_report_data(temp_pdf_path)
            filename = uploaded_file.name
            report_date = get_report_date(report_data, filename)

            # Create output path
            output_filename = f"report_{report_date}.json"
            output_path = os.path.join(ORIGINAL_EXTRACTS_DIR, output_filename)

            # Save extracted data
            with open(output_path, 'w') as f:
                json.dump(json.loads(report_data), f, indent=4)
            st.success(f"Extracted: {output_filename}")

        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        finally:
            # Clean temp file
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

# --- Streamlit App UI ---
st.title("📊 Health Analytics Dashboard")

# File Upload Section
uploaded_files = st.file_uploader(
    "Upload Medical Reports (PDF format)", 
    type=["pdf"], 
    accept_multiple_files=True,
    help="Upload lab reports in PDF format for analysis"
)

# Process Button
if uploaded_files:
    if st.button("🚀 Process Reports", type="primary"):
        with st.spinner("Analyzing reports..."):
            process_pdf_reports(uploaded_files)
            st.success("Processing complete!")
            st.cache_data.clear()

# Load and Display Data
@st.cache_data
def load_data():
    return fix_and_load_reports(RENAMED_EXTRACTS_DIR)

reports_df = load_data()

if not reports_df.empty:
    st.write("## 📈 Parameter Analysis")
    
    # Single line parameter selection
    parameter_options = reports_df['name'].unique().tolist()
    selected_parameter = st.selectbox("Select Parameter to Analyze", parameter_options)
    
    if selected_parameter:
        # Create columns for plot and recommendations
        col_plot, col_reco = st.columns([1, 1])  # 2:1 width ratio
        
        with col_plot:
            # Display trend plot
            fig = plot_trend(reports_df, selected_parameter)
            st.plotly_chart(fig, use_container_width=True,config={'x-axis': 'Date', 'y-axis': 'Value'})
        
        with col_reco:
            
            # Get unique patients with selected parameter
            patients_with_param = reports_df[
                reports_df['name'] == selected_parameter
            ]['patient_name'].unique()
            
            # Display recommendations for each patient
            for patient in patients_with_param:
                with st.text(f"Recommendations for {patient} ....Generating..."):
                    patient_data = reports_df[
                        (reports_df['patient_name'] == patient) & 
                        (reports_df['name'] == selected_parameter)
                    ]
                    rec = get_personalized_recommendations(
                        patient, selected_parameter, patient_data
                    )
                    st.markdown(rec)

    # Overall Summary Section
    st.divider()
    st.write("## 📋 Comprehensive Health Summary")
    
    if st.button("✨ Generate Overall Summary", type="primary"):
        for patient in reports_df['patient_name'].unique():
            patient_data = reports_df[reports_df['patient_name'] == patient]
            
            with st.expander(f"Full Summary for {patient}", expanded=True):
                with st.spinner(f"Generating summary for {patient}..."):
                    summary = get_overall_summary(patient, patient_data)
                    
                    # Scrollable summary container
                    st.markdown(
                        f'<div style="height: 500px; overflow-y: auto; '
                        f'padding: 20px; border: 1px solid #e0e0e0; '
                        f'border-radius: 8px; margin-bottom: 20px;">{summary}</div>',
                        unsafe_allow_html=True
                    )

else:
    st.info("👋 Upload PDF reports to begin analysis")