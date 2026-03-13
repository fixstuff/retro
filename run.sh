#!/bin/bash
# Retro Code Builder — start script
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

echo "╔══════════════════════════════════════╗"
echo "║      RETRO CODE BUILDER v1.0        ║"
echo "║   http://localhost:8580             ║"
echo "╚══════════════════════════════════════╝"

exec uvicorn app:app --host 0.0.0.0 --port 8580
