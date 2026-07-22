#!/bin/bash
# Company Information Intelligence Engine - Startup Script

echo "========================================"
echo "Company Intelligence Engine"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run the application
echo ""
echo "Starting application..."
echo ""
streamlit run app.py
