@echo off
setlocal
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if not exist backend\templates\violation_report_template.docx (
    echo Building Word report template...
    python -m backend.reporting.build_template
)

if not exist .env (
    echo Creating .env with default login admin/admin123 - CHANGE THIS:
    echo   python -m backend.set_password ^<username^> ^<new-password^>
    copy .env.example .env >nul
    python -m backend.set_password admin admin123
)

echo.
echo Starting server on http://127.0.0.1:8000
echo Open that URL in a browser to use the app. Press Ctrl+C to stop.
echo.
uvicorn backend.main:app --host 0.0.0.0 --port 8000
