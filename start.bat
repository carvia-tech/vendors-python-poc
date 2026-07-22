@echo off
REM Company Intelligence Engine - FastAPI Startup Script

echo ========================================
echo Company Intelligence Engine (FastAPI)
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

REM Run the FastAPI application
echo.
echo Starting FastAPI server...
echo Docs: http://localhost:8000/docs
echo API:  http://localhost:8000/api/health
echo.
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

pause
