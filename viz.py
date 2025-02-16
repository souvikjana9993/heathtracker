import os
import json
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit_authenticator as stauth
from pdf_utils import extract_report_data, get_report_date
import re
import shutil
from parameters_rename_agent import fix_parameters_across_json
from personalised_reco_agent import get_personalized_recommendations
from summary_agent import get_overall_summary
import yaml
from yaml.loader import SafeLoader
from streamlit_authenticator.utilities import LoginError

st.set_page_config(layout="wide")


with open("./config.yaml") as file:
    auth_config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    auth_config["credentials"],
    auth_config["cookie"]["name"],
    auth_config["cookie"]["key"],
    auth_config["cookie"]["expiry_days"],
)


def fix_and_load_reports(ORIGINAL_EXTRACTS_DIR, RENAMED_EXTRACTS_DIR):
    """Loads all JSON reports from the given directory and returns a DataFrame."""
    fix_parameters_across_json(ORIGINAL_EXTRACTS_DIR, RENAMED_EXTRACTS_DIR)
    reports = []
    for filename in os.listdir(RENAMED_EXTRACTS_DIR):
        if filename.endswith(".json"):
            file_path = os.path.join(RENAMED_EXTRACTS_DIR, filename)
            with open(file_path, "r") as f:
                try:
                    data = json.load(f)
                    # Date conversion with error handling
                    try:
                        data["report_date"] = pd.to_datetime(
                            data.get("report_date", ""), errors="coerce"
                        )
                    except Exception as e:
                        st.warning(f"Date conversion error in {filename}: {str(e)}")
                        data["report_date"] = pd.NaT

                    # Process parameters
                    for param in data.get("parameters", []):
                        # Add metadata to each parameter
                        param["report_date"] = data["report_date"]
                        param["patient_name"] = data.get("patient_name", "Unknown")
                        reports.append(param)
                except Exception as e:
                    st.error(f"Error loading {filename}: {str(e)}")
    return pd.DataFrame(reports)


def plot_trend(df, parameter_name):
    """Filters for a parameter and plots its trend over time."""
    df_param = df[df["name"] == parameter_name].copy()
    # Clean numerical values more robustly
    df_param["result"] = pd.to_numeric(
        df_param["result"].astype(str).str.replace("[<>]", "", regex=True).str.strip(),
        errors="coerce",
    )
    # Handle missing dates
    df_param = df_param.dropna(subset=["report_date"])

    fig = px.line(
        df_param,
        x="report_date",
        y="result",
        markers=True,
        title=f"Trend for {parameter_name}",
        color="patient_name",
    )
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
    )
    return fig


def process_pdf_reports(uploaded_files):
    """Processes uploaded PDF reports and saves extracted data to JSON files."""
    try:
        for uploaded_file in uploaded_files:
            pdf_storage_path = os.path.join(REPORTS_DIR, uploaded_file.name)
            if os.path.exists(pdf_storage_path):
                continue

            with open(pdf_storage_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            temp_pdf_path = os.path.join(REPORTS_DIR, f"temp_{uploaded_file.name}")
            shutil.copyfile(pdf_storage_path, temp_pdf_path)

            try:
                report_data = extract_report_data(temp_pdf_path)
                report_date = get_report_date(report_data, uploaded_file.name)
                output_filename = f"report_{report_date}.json"
                output_path = os.path.join(ORIGINAL_EXTRACTS_DIR, output_filename)

                with open(output_path, "w") as f:
                    json.dump(json.loads(report_data), f, indent=4)
            finally:
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
    except Exception as e:
        st.error(f"Critical error in PDF processing: {str(e)}")
        raise e


# --- Streamlit App UI ---
st.title("📊 Health and Reports Tracker Dashboard")

try:
    authenticator.login("main")
    if not st.session_state["authentication_status"]:
        if st.button("Register", key="reg"):
            authenticator.register_user("main")
except LoginError as e:
    st.error(e)

# Handle authentication response
if st.session_state["authentication_status"]:
    # Top-right logout button
    col1, col2 = st.columns([8, 1])
    with col2:
        authenticator.logout("Logout")
    with col1:
        st.success(f"Welcome *{st.session_state['name']}*!")

    # set anc create directories
    REPORTS_DIR = os.path.join("reports", st.session_state["username"])
    ORIGINAL_EXTRACTS_DIR = os.path.join(
        "report_extracts", st.session_state["username"]
    )
    RENAMED_EXTRACTS_DIR = os.path.join(
        "renamed_report_extracts", st.session_state["username"]
    )

    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)

    if not os.path.exists(ORIGINAL_EXTRACTS_DIR):
        os.makedirs(ORIGINAL_EXTRACTS_DIR)

    if not os.path.exists(RENAMED_EXTRACTS_DIR):
        os.makedirs(RENAMED_EXTRACTS_DIR)

    uploaded_files = st.file_uploader(
        "Upload Medical Reports (PDF format)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload lab reports in PDF format for analysis",
    )

    if uploaded_files and st.button(
        "🚀 Process Reports", type="primary", key="process"
    ):
        with st.spinner("Analyzing reports..."):
            process_pdf_reports(uploaded_files)
            st.success("Processing complete!")
            st.cache_data.clear()

    # Data Loading with error handling
    try:

        @st.cache_data
        def load_data(username):
            return fix_and_load_reports(ORIGINAL_EXTRACTS_DIR, RENAMED_EXTRACTS_DIR)

        reports_df = load_data(st.session_state["username"])
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.stop()

    if not reports_df.empty:
        st.write("## 📈 Parameter Analysis")
        parameter_options = reports_df["name"].unique().tolist()
        selected_parameter = st.selectbox(
            "Select Parameter to Analyze", parameter_options
        )

        if selected_parameter:
            col_plot, col_reco = st.columns([2, 1])

            with col_plot:
                fig = plot_trend(reports_df, selected_parameter)
                st.plotly_chart(fig, use_container_width=True)

            with col_reco:
                with st.container():
                    st.subheader(f"Recommendations for {st.session_state['username']}")
                    with st.spinner("Generating..."):
                        patient_data = reports_df[
                            (reports_df["name"] == selected_parameter)
                        ]
                        try:
                            patient = reports_df["patient_name"].unique()[0]
                            rec = get_personalized_recommendations(
                                patient, selected_parameter, patient_data
                            )
                            st.markdown(rec)
                        except Exception as e:
                            st.error(f"Error generating recommendations: {str(e)}")

        # Overall Summary Section
        st.divider()
        st.write("## 📋 Comprehensive Health Summary")

        if st.button("✨ Generate Overall Summary", key="generate_summary"):
            with st.expander(f"Full Summary for {patient}", expanded=False):
                with st.spinner(f"Analyzing {patient}'s history..."):
                    try:
                        summary = get_overall_summary(
                            patient, reports_df[reports_df["patient_name"] == patient]
                        )
                        st.markdown(
                            f"""
                        <div style="
                            max-height: 500px;
                            overflow-y: auto;
                            padding: 20px;
                            border: 1px solid #e0e0e0;
                            border-radius: 8px;
                            margin-bottom: 20px;
                        ">
                            {summary}
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    except Exception as e:
                        st.error(f"Summary generation failed: {str(e)}")

    else:
        st.info("👋 Upload PDF reports to begin analysis")


elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password")
