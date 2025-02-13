# personalized_recommendations.py
import logging
import pandas as pd
from google import genai
import os
from dotenv import load_dotenv

# Load environment variables (configure logging before loading)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# Accessing the API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
    exit(1)

# Initialize the client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
model_id = "gemini-2.0-flash-exp"  # or appropriate model

def get_personalized_recommendations(patient_name, parameter, trend_data):
    """
    Generates personalized recommendations using the Gemini API based on trend data.
    """

    # Determine reference interval. Assumes all entries have same intervals
    try:
        reference_interval = trend_data['reference_interval'].iloc[0]
        reference_interval_str = ", ".join([f"{k}: {v}" for k, v in reference_interval.items()])
    except AttributeError:
        reference_interval_str = "N/A"

    # Format trend data
    trend_data_str = ""
    for index, row in trend_data.iterrows():
        date = row['report_date'].strftime('%Y-%m-%d') if isinstance(row['report_date'], pd.Timestamp) else "Unknown Date"
        trend_data_str += f"Date: {date}, Result: {row['result']}, "

    # Build the prompt
    prompt = f"""
    You are a medical expert providing personalized health recommendations.

    Patient Name: {patient_name}
    Parameter: {parameter}
    Reference Interval: {reference_interval_str} (if available, otherwise N/A)
    Trend data is : {trend_data_str}

    Instructions:

    1.  Analyze the provided parameter and its trend data to understand the patient's health status.

    2.  Assess the patient's most recent parameter value in relation to the reference interval:
        -   If the value is within the reference interval, reassure the patient and encourage maintaining a healthy lifestyle.
        -   If the value is outside the reference interval, provide a concise warning about potential health risks and suggest appropriate actions.
        -   Also try to keep your knowledge on the correct reference interval for the parameter.

    3.  Based on the trend data, give specific, actionable diet and lifestyle suggestions to help the patient improve their parameter levels. Focus on practical changes.

    4.  Keep the tone friendly and encouraging.
    5.  Limit the response to under 200 words.

    Personalized Recommendations:
    """


    try:
        response = client.models.generate_content(model=model_id,contents=[prompt])
        recommendation = response.text.strip()
        logging.info(f"Generated recommendation for {patient_name} regarding {parameter}.")
        return recommendation
    except Exception as e:
        logging.error(f"Error generating recommendation: {e}")
        return "Could not generate personalized recommendations at this time."