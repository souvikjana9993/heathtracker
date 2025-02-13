import os
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from pdf_utils import extract_report_data, get_report_date  # Import your extraction functions
import re

# --- Constants ---
REPORTS_DIR = "reports"  # Temporary storage during upload
EXTRACTS_DIR = "report_extracts"

# --- Functions ---
def load_reports(directory):
    """Loads all JSON reports from the given directory and returns a DataFrame."""
    reports = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            with open(os.path.join(directory, filename), 'r') as f:
                data = json.load(f)
                # Convert report_date to datetime and handle potential errors
                try:
                    if 'report_date' in data:
                        data['report_date'] = pd.to_datetime(data['report_date'])
                    else:
                        data['report_date'] = pd.NaT
                except ValueError:
                    data['report_date'] = pd.NaT  # Assign NaT if parsing fails
                for param in data['parameters']:
                    param['report_date'] = data['report_date']
                    param['patient_name'] = data.get('patient_name', 'Unknown')
                    reports.append(param)
    return pd.DataFrame(reports)

def plot_trend(df, parameter_name):
    """Filters for a parameter and plots its trend over time."""
    df_param = df[df['name'] == parameter_name].copy()
    df_param['result'] = pd.to_numeric(
        df_param['result'].str.replace('<', '').str.strip(), errors='coerce'
    )
    fig = px.line(
        df_param,
        x='report_date',
        y='result',
        markers=True,
        title=f"Trend for {parameter_name}"
    )
    return fig

def get_personalized_recommendations(patient_name, parameter, trend_data):
    """Placeholder function for integrating agentic AI."""
    recommendation = (f"Patient {patient_name}: Your {parameter} levels are here. "
                      "Consider scheduling a consultation for further analysis. Add agentic AI functionality here.")
    return recommendation

def process_pdf_reports(uploaded_files):
    """Processes uploaded PDF reports and saves extracted data to JSON files."""
    # Ensure the REPORTS_DIR exists for temporary storage
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)

    # Ensure the EXTRACTS_DIR exists for storing the extracted data
    if not os.path.exists(EXTRACTS_DIR):
        os.makedirs(EXTRACTS_DIR)

    for uploaded_file in uploaded_files:
        # Save the uploaded PDF to the REPORTS_DIR temporarily
        pdf_path = os.path.join(REPORTS_DIR, uploaded_file.name)
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.write(f"Processing: {uploaded_file.name}")

        # Extract data from the PDF
        report_data = extract_report_data(pdf_path)

        # Get the report date
        filename = uploaded_file.name
        try:
            report_date = get_report_date(report_data, filename)
        except Exception as e:
            st.error(f"Error getting report date: {e}")
            report_date = "unknown_date"


        # Create the output filename
        output_filename = f"report_{report_date}.json"
        output_path = os.path.join(EXTRACTS_DIR, output_filename)

        # Avoid overwriting existing "unknown_date" reports
        if report_date == "unknown_date" and os.path.exists(output_path):
            st.warning(f"Skipping {output_filename} as it already exists.")
            continue

        # Write the extracted data to the JSON file
        try:
            with open(output_path, 'w') as f:
                json.dump(json.loads(report_data), f, indent=4)
            st.success(f"Successfully extracted data to: {output_path}")
        except json.JSONDecodeError as e:
            st.error(f"Error decoding JSON: {e}")
            st.error(f"Problematic JSON string: {report_data}")
        except Exception as e:
            st.error(f"Error writing to file: {e}")
        # Clean up the temporary PDF file
        os.remove(pdf_path)

# --- Streamlit App UI ---
st.title("Health Tracker Dashboard")

# File Upload Section
uploaded_files = st.file_uploader("Upload Medical Reports (PDF)", type=["pdf"], accept_multiple_files=True)

# Process Button
if uploaded_files:
    if st.button("Start Processing"):
        process_pdf_reports(uploaded_files)
        st.success("PDF Report Processing Complete!")
        # Clear cache to reload data
        st.cache_data.clear() # Clear the st.cache_data cache

# Load and Display Data
@st.cache_data
def load_data():
    return load_reports(EXTRACTS_DIR)

reports_df = load_data()

if not reports_df.empty:

    st.write("### Loaded Reports Data")
    st.dataframe(reports_df.head())

    # Parameter Selection
    parameter_options = reports_df['name'].unique().tolist()
    selected_parameter = st.selectbox("Select a parameter to visualize", parameter_options)

    if selected_parameter:
        fig = plot_trend(reports_df, selected_parameter)
        st.plotly_chart(fig)

        # Recommendations
        st.subheader("Personalized Recommendations")
        for patient in reports_df['patient_name'].unique():
            patient_params = reports_df[reports_df['patient_name'] == patient]
            if selected_parameter in patient_params['name'].values:
                rec = get_personalized_recommendations(patient, selected_parameter, patient_params)
                st.write(rec)
else:
    st.info("Upload and process PDF reports to see the data.")