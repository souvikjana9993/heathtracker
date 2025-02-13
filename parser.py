# main.py
import os
import json
from pdf_utils import extract_report_data, extract_date_from_filename, get_report_date

REPORTS_DIR = "reports"
EXTRACTS_DIR = "report_extracts"

# Ensure the extracts directory exists
if not os.path.exists(EXTRACTS_DIR):
    os.makedirs(EXTRACTS_DIR)

# Process each PDF file in the reports directory
for filename in os.listdir(REPORTS_DIR):
    if filename.endswith(".pdf"):
        pdf_path = os.path.join(REPORTS_DIR, filename)
        print(f"Processing: {pdf_path}")

        report_data = extract_report_data(pdf_path)

        # Get the report date, prioritizing content then filename
        report_date = get_report_date(report_data, filename)

        # Create the output filename with report date
        output_filename = f"report_{report_date}.json"
        output_path = os.path.join(EXTRACTS_DIR, output_filename)

        # Avoid overwriting existing "unknown_date" reports
        if report_date == "unknown_date" and os.path.exists(output_path):
            print(f"Skipping {output_path} as it already exists.")
            continue  # Skip to the next file

        # Write the extracted data to the JSON file
        try:
            with open(output_path, 'w') as f:
                json.dump(json.loads(report_data), f, indent=4)
            print(f"Successfully extracted data to: {output_path}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(f"Problematic JSON string: {report_data}")
        except Exception as e:
            print(f"Error writing to file: {e}")