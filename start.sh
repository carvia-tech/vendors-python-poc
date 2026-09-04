#!/bin/bash
# Company Intelligence Engine - FastAPI Startup Script

echo "========================================"
echo "Company Intelligence Engine (FastAPI)"
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

# Run the FastAPI application
echo ""
echo "Starting FastAPI server..."
echo "Docs: http://localhost:8000/docs"
echo "API:  http://localhost:8000/api/health"
echo ""
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
