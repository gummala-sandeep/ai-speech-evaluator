#!/usr/bin/env bash
# run.sh — Start both the FastAPI backend and Streamlit frontend
# Usage: bash run.sh
#
# IMPORTANT: Activate venv311 (Python 3.11) before running:
#   source venv311/bin/activate && bash run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Resolve the correct Python / venv ────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/venv311"

if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    echo "✓ Using Python: $(python --version) from $VENV_DIR"
else
    echo "ERROR: venv311 not found at $VENV_DIR"
    echo "Create it with: python3.11 -m venv venv311 && source venv311/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Load environment variables from .env if present
if [ -f .env ]; then
    echo "✓ Loading environment variables from .env"
    while IFS= read -r line || [ -n "$line" ]; do
        # Strip comments and check if it's a valid key=value pair
        clean_line=$(echo "$line" | sed 's/#.*//' | xargs)
        if [ -n "$clean_line" ]; then
            export "$clean_line"
        fi
    done < .env
fi

export PYTHONPATH="${PYTHONPATH}:$(pwd)"


echo ""
echo "======================================================"
echo "  SkillEcho — Voice-Based Concept Understanding Analyser"
echo "======================================================"
echo ""

# ── 1. Quick dependency check (no reinstall on every launch) ─────────────
echo "[1/3] Checking Python dependencies…"
python -c "import fastapi, whisper, librosa, streamlit, sentence_transformers" 2>/dev/null \
    && echo "      ✓ All core packages present." \
    || { echo "      ✗ Missing packages — running pip install…"; pip install -r requirements.txt --quiet; }

# ── 2. Start FastAPI backend in background ───────────────────────────────
echo "[2/3] Starting FastAPI backend on http://localhost:8000 …"
uvicorn src.backend.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "      Backend PID: $BACKEND_PID"
sleep 3   # Give the server time to initialise models & DB

# ── 3. Start Streamlit frontend ──────────────────────────────────────────
echo "[3/3] Starting Streamlit frontend on http://localhost:8501 …"
echo ""
echo "  → Backend API docs : http://localhost:8000/docs"
echo "  → Streamlit UI     : http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop both services."
echo "======================================================"

# Forward SIGINT/SIGTERM to the backend process as well
trap "kill $BACKEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

streamlit run src/frontend/app.py --server.port 8501 --server.address 0.0.0.0

# Clean up backend when Streamlit exits
kill $BACKEND_PID 2>/dev/null || true
