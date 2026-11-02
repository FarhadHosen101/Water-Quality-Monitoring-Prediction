#!/usr/bin/env bash
# Startup script for AI-Based Water Quality Monitoring Platform

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "💧 Starting AI-Based Water Quality Monitoring System"
echo "=========================================================="

# Ensure venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Starting FastAPI server on http://0.0.0.0:8000..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
