from google import genai
from dotenv import load_dotenv
import os
import json
from models import MedicalReport
import re  # Import the regular expression module

load_dotenv()

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
model_id = "gemini-2.0-flash-exp"  # or appropriate model

def extract_report_data(pdf_path):
    """
    Extracts data from a medical report PDF using Gemini and returns a JSON object.
    Includes extraction of report date from the report content.
    """

    report_pdf = client.files.upload(
        file=pdf_path,
        config={'display_name': 'Report'}
    )

    # pdf_utils.py

# Modified prompt (snippet only)
    prompt = """
    You are processing a medical report in PDF format. Your task is to extract data *only* from pages that contain a tabular structure similar to a lab test report, and to avoid including repeated measures of the same parameter. A lab test report typically has columns for Parameter Name, Result, Unit, and Reference Range.

    **Instructions:**

    1. **Analyze each page** of the uploaded PDF.
    2. **Identify pages that contain a clear table-like structure** with columns like Parameter Name, Result, Unit, and Reference Range. Look for clear visual separation of data into rows and columns. The presence of a "normal" range or reference range is crucial.
    3. **Ignore pages that do NOT contain such a table.** This includes cover pages, consent forms, disclaimers, or pages with mostly text and no organized table structure.
    4. **If and only if at least one page has a table has table structure**, proceed to extract the following data from *all* pages that have the table, applying these additional rules:

        *   **Prioritize Most Recent Measurement:**  If the same parameter (e.g., "Cholesterol") is measured multiple times in the report, extract only the *most recent* measurement.  Do not include older or less recent measurements.
        *   **If multiple values are present for one parameter, prioritize the value on the top.**
        *   **Extract the report_date in (YYYY-MM-DD) format.** If the report date does not exist return 'unknown_date'.

        *   **Reference Interval Handling:**
            *   **If the reference interval is given with defined levels (e.g., "Desirable: < 150", "Borderline: 150 - 199", "High: 200-499", "Very High: >= 500"), extract the corresponding values into the appropriate fields ("normal", "medium", "high", "veryhigh").**
            *   **If the reference interval is given *only* as a single range (e.g., "211 - 911" with *no* levels defined), extract it into the "other" field. In this case, set the "normal", "medium", "high", and "veryhigh" and "other" fields to null.**
            *   **Do NOT attempt to split a range into separate high/low values if defined levels are provided.**

    5. **If NO pages contain this table-like structure, return an empty JSON object: `{}`** or a message saying no table found. Do not throw an error if no tables are found, simply return the empty object.
    6. **Return valid JSON.**
    """

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=[report_pdf, prompt],
            config={
                'response_mime_type': 'application/json',
                'response_schema': MedicalReport
            }
        )
        report_data = response.text
        # Normalize parameter names
        report_json = json.loads(report_data)

        report_data = json.dumps(report_json, indent=4)
        return report_data

    except Exception as e:
        print(f"Error processing report: {e}")
        return "{}"  # Return empty JSON object on error

def extract_date_from_filename(filename):
    """
    Extracts the report date from the filename using a regular expression.
    Assumes the filename contains a date in YYYY-MM-DD format.
    """
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)
    else:
        return "unknown_date"  # Or a default value if no date is found

def get_report_date(report_data, filename):
    """
    Gets the report date, prioritizing the date from the report content,
    falling back to the filename if the report content doesn't have a date.
    """
    try:
        report_json = json.loads(report_data)
        report_date = report_json.get("report_date", "unknown_date")
        if report_date == "unknown_date" or not re.match(r'\d{4}-\d{2}-\d{2}', report_date):
            report_date = extract_date_from_filename(filename)
        return report_date
    except (json.JSONDecodeError, AttributeError):
        # If JSON decoding fails, fallback to filename
        return extract_date_from_filename(filename)