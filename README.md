# Health Tracker

Welcome to the Health Tracker project! This application helps you monitor and manage your health metrics effectively.

## Features

- Upload and process PDF medical reports
- Visualize health parameters through interactive charts
- Generate personalized health recommendations

## Project Structure

- `viz.py` - Main visualization dashboard using Streamlit
- `personalised_reco_agent.py` - Generates a AI report of the health parameter history
- `pdf_utils.py` - PDF processing utilities 
- `models.py` - Data models and structures
- `parameters_rename_agent.py` - Renames parameters correctly across multiple reports using embeddings

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
