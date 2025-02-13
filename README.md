# Health Tracker

Welcome to the Health Tracker project! This application helps you monitor and manage your health metrics effectively.

## Features

- Upload and process PDF medical reports
- Visualize health parameters through interactive charts
- Track multiple patients' health metrics over time
- Generate personalized health recommendations
- Store processed reports in JSON format
- Automatic parameter renaming support

## Project Structure

- `viz.py` - Main visualization dashboard using Streamlit
- `parser.py` - PDF report parsing logic
- `pdf_utils.py` - PDF processing utilities
- `models.py` - Data models and structures
- `parameters_rename_agent.py` - Parameter renaming functionality

## Data Storage

- Processed reports are stored in `reports/` directory
- Renamed parameter reports are stored in `renamed_report_extracts/`

## Requirements

Dependencies are listed in `requirements.txt`. Key dependencies include:
- Streamlit for the dashboard interface
- PDF processing libraries
- Data analysis tools

## Usage

1. Upload PDF medical reports through the web interface
2. Process the reports using the "Start Processing" button
3. View interactive visualizations of health parameters
4. Get personalized recommendations based on the data