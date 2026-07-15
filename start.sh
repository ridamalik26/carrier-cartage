#!/usr/bin/env bash
# Portable start script for macOS/Linux (Windows users: run start.bat instead).
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f backend/templates/violation_report_template.docx ]; then
    echo "Building Word report template..."
    python -m backend.reporting.build_template
fi

if [ ! -f .env ]; then
    echo "Creating .env with default login admin/admin123 - CHANGE THIS:"
    echo "  python -m backend.set_password <username> <new-password>"
    cp .env.example .env
    python -m backend.set_password admin admin123
fi

echo
echo "Starting server on http://127.0.0.1:8000"
echo "Open that URL in a browser to use the app. Press Ctrl+C to stop."
echo
uvicorn backend.main:app --host 0.0.0.0 --port 8000
