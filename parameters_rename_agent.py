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
RENAMED_MAPPING_FILE = "renamed_parameters.json"

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

def load_existing_mappings(filename):
    """Loads existing parameter mappings from a JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.info(f"Mapping file '{filename}' not found. Starting with empty mappings.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in mapping file '{filename}'. Starting with empty mappings.")
        return {}
    return {}

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
    Uses existing mappings if available and only queries Gemini for new parameters.
    """
    existing_mappings = load_existing_mappings(RENAMED_MAPPING_FILE)
    normalized_names = existing_mappings.copy() # Start with existing mappings
    new_parameter_names = set()

    for filename, params in all_parameters.items():
        for p in params:
            original_name = p['name']
            if original_name not in normalized_names:
                new_parameter_names.add(original_name)

    if not new_parameter_names:
        logging.info("No new parameters to normalize. Using existing mappings.")
        return normalized_names

    logging.info(f"Normalizing new parameters using Gemini: {new_parameter_names}")

    # Build the prompt with only new parameter names
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
    for name in new_parameter_names:
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
                gemini_normalized_names = json.loads(json_string)
                logging.info("Successfully normalized new parameter names using Gemini.")
                # Merge new mappings with existing ones
                normalized_names.update(gemini_normalized_names)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from Gemini: {e}")
                logging.error(f"Problematic JSON string: {json_string}")  # Log the problematic string
        else:
            logging.error("Gemini returned an invalid JSON response.")
            logging.error(f"Response text: {response.text}")  # Log the result
    except Exception as e:
        logging.error(f"Error normalizing parameters with Gemini: {e}")

    return normalized_names

def rename_parameters(all_parameters, normalized_names):
    """
    Renames parameters in the copied JSON files based on the normalized names.
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
                    # Update renamed mapping (only if actually renamed)
                    if original_name not in renamed_mapping and normalized_name != original_name:
                        renamed_mapping[original_name] = normalized_name

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

def copy_files_to_renamed_directory(source_dir,dest_dir):
    """Copies all JSON files from source_dir to dest_sir."""
    # Ensure the destination directory exists
    for filename in os.listdir(source_dir):
        if filename.endswith('.json'):
            source_path = os.path.join(source_dir, filename)
            destination_path = os.path.join(dest_dir, filename)
            try:
                shutil.copy2(source_path, destination_path)  # copy2 preserves metadata
                logging.info(f"Copied '{filename}' to '{dest_dir}'")
            except Exception as e:
                logging.error(f"Error copying '{filename}': {e}")

def fix_parameters_across_json(source_dir,dest_dir):
    """
    Main function to orchestrate parameter matching and renaming using Gemini.
    """

    # Copy files to the renamed directory
    logging.info("Copying files to renamed directory...")
    copy_files_to_renamed_directory(source_dir,dest_dir)
    logging.info("Files copied.")

    # Load parameters from all JSON files (from the RENAMED directory now)
    all_parameters = {}
    for filename in os.listdir(dest_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(dest_dir, filename)
            all_parameters[file_path] = load_parameters_from_json(file_path)

    # Normalize parameters using Gemini
    logging.info("Starting parameter normalization...")
    normalized_names = normalize_parameters_with_gemini(all_parameters)

    # Rename parameters in the JSON files
    logging.info("Starting parameter renaming...")
    renamed_mapping, renamed_counts = rename_parameters(all_parameters, normalized_names)
    logging.info("Parameter renaming complete.")
    total_renamed = sum(renamed_counts.values())
    logging.info(f"Total parameters renamed: {total_renamed}")

    # Save the renamed parameter mapping to a JSON file
    save_renamed_mapping(normalized_names, RENAMED_MAPPING_FILE) # Save all normalized names, including existing

    logging.info("Parameter matching and renaming process finished.")
