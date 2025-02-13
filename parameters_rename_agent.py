# parameter_matcher.py
import os
import json
import logging
import shutil  # Import shutil for file operations
from google import genai
from dotenv import load_dotenv
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
EXTRACTS_DIR = "report_extracts"
RENAMED_MAPPING_FILE = "renamed_parameters.json"  # Added constant for mapping file
RENAMED_EXTRACTS_DIR = "renamed_report_extracts"  # New directory for renamed files

# Load Gemini API key from .env file
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
    exit(1)

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
model_id = "gemini-2.0-flash-exp"  # or appropriate model


def load_parameters_from_json(json_file):
    """Loads parameters from a JSON file."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            return data.get('parameters', [])
    except FileNotFoundError:
        logging.error(f"File not found: {json_file}")
        return []
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in file: {json_file}")
        return []


def extract_range_values(reference_interval_str):
    """Extracts lower and upper range values from a reference interval string."""
    if not reference_interval_str:
        return None, None

    try:
        # First try to find the lower and upper
        match = re.match(r"([+-]?\d*\.?\d+)\s*-\s*([+-]?\d*\.?\d+)", reference_interval_str)
        if match:
            lower = float(match.group(1))
            upper = float(match.group(2))
        else:
             # Otherwise it needs to be greather than or less than
            match_lower = re.match(r">([+-]?\d*\.?\d+)", reference_interval_str)
            match_upper = re.match(r"<([+-]?\d*\.?\d+)", reference_interval_str)

            lower = None
            upper = None
            if match_lower:
                lower = float(match_lower.group(1))
            if match_upper:
                upper = float(match_upper.group(1))

        return lower, upper
    except Exception as e:
        logging.error(f"Error extracting range values: {e}")
        return None, None


def normalize_parameters_with_gemini(all_parameters):
    """
    Normalizes all parameter names using a single Gemini API call.
    """
    # Build the prompt with all parameter names
    prompt_header = """
    You are a medical data normalizer. Your task is to standardize a list of given parameter names into common, well-defined medical terms.
    Consider common abbreviations, synonyms, and variations in terminology.
    Return a JSON object where the keys are the original parameter names and the values are the standardized parameter names.

    Here are some examples of the desired standardization:
    {
        "Cholesterol - Total": "Total Cholesterol",
        "Cholesterol, LDL": "LDL Cholesterol",
        "Hb": "Hemoglobin",
        "AST (SGOT)": "AST",
        "T Bilirubin": "Total Bilirubin",
        "triglyceride": "Triglycerides",
        "glucose - fasting": "Fasting Glucose",
        "vitamin d (25-oh)": "Vitamin D",
        "aspartate transaminase (sgot)": "AST",
        "Cholesterol - HDL": "HDL Cholesterol",
        "Cholesterol - LDL": "LDL Cholesterol",
        "Cholesterol- VLDL": "VLDL Cholesterol",
        "Non HDL Cholesterol": "Non-HDL Cholesterol",
        "Testosterone, total": "Total Testosterone",
        "LDL Cholesterol": "LDL Cholesterol",
        "HDL Cholesterol": "HDL Cholesterol",
        "VLDL Cholesterol": "VLDL Cholesterol",
        "ALT (SGPT)": "ALT",
        "SGPT (Alanine transaminase)": "ALT",
        "SGOT (Aspartate transaminase)": "AST",
        "Glycosylated Hemoglobin (HbA1c)": "Hemoglobin A1c"
    }

    Provide the results *only* as a valid JSON object.  Ensure that all keys and values are enclosed in double quotes.
    Do not include any other text or explanations, code blocks, or markdown formatting. Output a parsable JSON string.

    Here is the JSON:

    {
    """

    prompt_body = ""
    all_parameter_names = set()
    for filename, params in all_parameters.items():
        for p in params:
            all_parameter_names.add(p['name'])

    for name in all_parameter_names:
        escaped_name = name.replace('"', '\\"')  # Escape double quotes
        prompt_body += f'"{escaped_name}": "",\n'

    # Remove the trailing comma and newline
    if prompt_body:
        prompt_body = prompt_body[:-2]

    prompt_footer = "\n}"

    full_prompt = prompt_header + prompt_body + prompt_footer

    try:
        response = client.models.generate_content(model=model_id, contents=[full_prompt])
        json_string = response.text.strip()

        # remove code blocks
        json_string = re.sub(r'```json\n', '', json_string)
        json_string = re.sub(r'```', '', json_string)

        # Remove any leading or trailing characters that are not part of the JSON structure
        json_string = json_string.strip()

        if json_string.startswith('{') and json_string.endswith('}'):

            # Parse the JSON response
            try:
                normalized_names = json.loads(json_string)
                logging.info("Successfully normalized parameter names using Gemini.")
                return normalized_names
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from Gemini: {e}")
                logging.error(f"Problematic JSON string: {json_string}")  # Log the problematic string
                return {}  # Return an empty dictionary on error
        else:
            logging.error("Gemini returned an invalid JSON response.")
            logging.error(f"Response text: {response.text}")  # Log the result
            return {}
    except Exception as e:
        logging.error(f"Error normalizing parameters with Gemini: {e}")
        return {}  # Return an empty dictionary on error


def rename_parameters(all_parameters, normalized_names):
    """
    Renames parameters in the copied JSON files based on the normalized names from Gemini.
    """
    renamed_mapping = {}  # Store the mapping of renamed parameters
    renamed_counts = {}

    for filename, params in all_parameters.items():
        renamed_counts[filename] = 0  # Initialize counts
        # Load the JSON file
        with open(filename, 'r') as f:
            data = json.load(f)

        # Iterate through parameters and rename them using Gemini
        for p in data.get('parameters', []):
            original_name = p['name']
            if original_name in normalized_names and normalized_names[original_name]:
                normalized_name = normalized_names[original_name]  # use the data
                if normalized_name != original_name:
                    logging.info(
                        f"Renaming parameter '{original_name}' in '{filename}' to '{normalized_name}'"
                    )
                    p['name'] = normalized_name
                    renamed_counts[filename] += 1  # Increase renames
                    # Update renamed mapping
                    if original_name not in renamed_mapping:
                        renamed_mapping[original_name] = normalized_name

            # Extract range values and modify the reference_interval structure
            if 'reference_interval' in p:
                reference_interval = p['reference_interval']

                # Check if other keys are null
                if (reference_interval.get('normal') is None and
                    reference_interval.get('medium') is None and
                    reference_interval.get('high') is None and
                    reference_interval.get('veryhigh') is None and
                    reference_interval.get('other') is not None): # Other is present

                    other_value = reference_interval.get('other')  # Get the value from the "other" field
                    lower, upper = extract_range_values(other_value)

                    # Create a new dictionary with 'upper' and 'lower'
                    new_reference_interval = {}
                    if lower is not None:
                        new_reference_interval['lower'] = lower
                    if upper is not None:
                        new_reference_interval['upper'] = upper

                    # Replace the entire reference_interval with the new one
                    p['reference_interval'] = new_reference_interval

        # Save the modified JSON file
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)

    return renamed_mapping, renamed_counts


def save_renamed_mapping(renamed_mapping, filename):
    """Saves the renamed parameter mapping to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(renamed_mapping, f, indent=4)
        logging.info(f"Renamed parameter mapping saved to: {filename}")
    except Exception as e:
        logging.error(f"Error saving renamed mapping: {e}")


def copy_files_to_renamed_directory():
    """Copies all JSON files from EXTRACTS_DIR to RENAMED_EXTRACTS_DIR."""
    # Ensure the destination directory exists
    if not os.path.exists(RENAMED_EXTRACTS_DIR):
        os.makedirs(RENAMED_EXTRACTS_DIR)

    for filename in os.listdir(EXTRACTS_DIR):
        if filename.endswith('.json'):
            source_path = os.path.join(EXTRACTS_DIR, filename)
            destination_path = os.path.join(RENAMED_EXTRACTS_DIR, filename)
            try:
                shutil.copy2(source_path, destination_path)  # copy2 preserves metadata
                logging.info(f"Copied '{filename}' to '{RENAMED_EXTRACTS_DIR}'")
            except Exception as e:
                logging.error(f"Error copying '{filename}': {e}")


def fix_parameters_across_json():
    """
    Main function to orchestrate parameter matching and renaming using Gemini.
    """

    # Create the renamed extracts directory if it doesn't exist
    if not os.path.exists(RENAMED_EXTRACTS_DIR):
        os.makedirs(RENAMED_EXTRACTS_DIR)

    # Copy files to the renamed directory
    logging.info("Copying files to renamed directory...")
    copy_files_to_renamed_directory()
    logging.info("Files copied.")

    # Load parameters from all JSON files (from the RENAMED directory now)
    all_parameters = {}
    for filename in os.listdir(RENAMED_EXTRACTS_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(RENAMED_EXTRACTS_DIR, filename)
            all_parameters[file_path] = load_parameters_from_json(file_path)

    # Normalize parameters using Gemini
    logging.info("Starting parameter normalization using Gemini...")
    normalized_names = normalize_parameters_with_gemini(all_parameters)

    # Rename parameters in the JSON files
    logging.info("Starting parameter renaming...")
    renamed_mapping, renamed_counts = rename_parameters(all_parameters, normalized_names)
    logging.info("Parameter renaming complete.")
    total_renamed = sum(renamed_counts.values())
    logging.info(f"Total parameters renamed: {total_renamed}")

    # Save the renamed parameter mapping to a JSON file
    save_renamed_mapping(renamed_mapping, RENAMED_MAPPING_FILE)

    logging.info("Parameter matching and renaming process finished.")


if __name__ == "__main__":
    fix_parameters_across_json()