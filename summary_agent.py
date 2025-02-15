import logging
import pandas as pd
from google import genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
model_id = "gemini-2.0-flash-exp"

def get_overall_summary(patient_name, all_reports_df):
    """
    Generates an overall health summary using the Gemini API based on complete patient data.
    """
    # Prepare trend data string
    trend_data_str = ""
    for param_name, group in all_reports_df.groupby('name'):
        param_data = []
        for _, row in group.iterrows():
            date_str = row['report_date'].strftime('%Y-%m-%d') if pd.notnull(row['report_date']) else "Unknown Date"
            result = row['result']
            ref_interval = row.get('reference_interval', {})
            ref_str = ", ".join([f"{k}: {v}" for k, v in ref_interval.items() if v]) if isinstance(ref_interval, dict) else "N/A"

            param_data.append(f"{date_str}: {result} (Ref: {ref_str})")

        trend_data_str += f"\n\n**{param_name}**\n" + "\n".join(param_data)

    # Build the prompt
    prompt = f"""
    You are a senior medical analyst preparing a comprehensive health summary.

    Patient: {patient_name}

    Health Data:
    {trend_data_str}

    Analysis Requirements:
    1. Identify parameters consistently outside reference intervals and focus on trends whether increassing or decreasing with date
    2. Highlight most concerning values and their potential health risks
    3. Note any improving/worsening trends across parameters
    4. Prioritize cardiovascular/metabolic risks
    5. Provide actionable lifestyle modifications addressing multiple issues
    6. Mention parameters needing urgent medical attention (if any)
    7. Keep summary structured but conversational (max 500 words)
    8. Use markdown formatting for headings and bullet points
    9. Analyse the combination of parameters deeply for holistic health insights

    Format:
    # Overall Health Summary for {patient_name}

    ## Key Concerns
    - List of critical parameters with values/dates

    ## Risk Analysis
    - Potential health risks based on abnormal values

    ## Recommended Actions
    - Priority lifestyle changes
    - Suggested medical follow-ups
    - Monitoring recommendations

    ## Positive Notes
    - Parameters within range worth maintaining
    """

    try:
        response = client.models.generate_content(model=model_id, contents=[prompt])
        summary = response.text.strip()
        logging.info(f"Generated overall summary for {patient_name}")
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Could not generate summary at this time."