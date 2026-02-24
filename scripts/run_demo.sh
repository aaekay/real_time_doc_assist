#!/bin/bash
# Run the OPD Question Copilot demo (backend + frontend)
#
# Prerequisites:
#   1. External OpenAI-compatible LLM server running (see ./api_usage.md)
#   2. Python dependencies installed (pip install -r requirements.txt)
#   3. Frontend dependencies installed (cd frontend && npm install)
#
# Usage:
#   ./scripts/run_demo.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python"
fi

echo "=== OPD Question Copilot ==="
echo ""

if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "[OK] Loaded env from $ENV_FILE"
fi

MODEL_CACHE_DIR="${OPD_MODEL_CACHE_DIR:-models/hf_cache}"
if [[ ! "$MODEL_CACHE_DIR" = /* ]]; then
    MODEL_CACHE_DIR="$PROJECT_DIR/$MODEL_CACHE_DIR"
fi
mkdir -p "$MODEL_CACHE_DIR"
export HF_HOME="${HF_HOME:-$MODEL_CACHE_DIR/hf_home}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$MODEL_CACHE_DIR/hub}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$MODEL_CACHE_DIR/transformers}"
echo "[OK] Using model cache dir: $MODEL_CACHE_DIR"

# Check whether current Python env supports MedASR LASR classes.
HAS_LASR_CLASSES="$("$PYTHON_BIN" - <<'PY'
import importlib
import sys

try:
    t = importlib.import_module("transformers")
except Exception:
    print("0")
    sys.exit(0)

has_tokenizer = hasattr(t, "LasrTokenizer")
has_feature = hasattr(t, "LasrFeatureExtractor") or hasattr(t, "LASRFeatureExtractor")
print("1" if (has_tokenizer and has_feature) else "0")
PY
)"
if [[ "$HAS_LASR_CLASSES" == "1" ]]; then
    echo "[OK] Current Python env has LASR classes for MedASR."
else
    echo "[WARN] Current Python env lacks LASR classes for MedASR."
    echo "       Backend will run via: uv run --with transformers>=5.2.0"
fi

# Check if external MedGemma/LLM server is running and looks OpenAI-compatible.
MEDGEMMA_URL="${OPD_MEDGEMMA_BASE_URL:-http://127.0.0.1:11424/v1}"
MEDGEMMA_MODELS_URL="${MEDGEMMA_URL%/}/models"
if curl -fsS "${MEDGEMMA_MODELS_URL}" | "$PYTHON_BIN" -c "import json,sys; obj=json.load(sys.stdin); assert isinstance(obj, dict) and isinstance(obj.get('data', []), list)" > /dev/null 2>&1; then
    echo "[OK] External LLM server is running at ${MEDGEMMA_URL}"
else
    probe_code="$(curl -sS -o /tmp/opd_medgemma_probe.txt -w '%{http_code}' "${MEDGEMMA_MODELS_URL}" 2>/dev/null || true)"
    probe_body="$(head -c 160 /tmp/opd_medgemma_probe.txt 2>/dev/null | tr '\n' ' ')"
    echo "[WARN] External LLM endpoint not valid at ${MEDGEMMA_URL} (code: ${probe_code:-n/a})"
    if [[ -n "$probe_body" ]]; then
        echo "       Response preview: ${probe_body}"
    fi
    echo "       Start your LLM API service (for example: llm-serve)."
    echo "       API contract reference: ./api_usage.md"
    echo "       If needed, set OPD_MEDGEMMA_BASE_URL to the correct host/port."
    echo "       Continuing anyway (pipeline calls will fail)..."
    echo ""
fi

# Start backend
echo "Starting backend on port ${OPD_PORT:-8080}..."
cd "$PROJECT_DIR"
if [[ "$HAS_LASR_CLASSES" == "1" ]]; then
    "$PYTHON_BIN" -m uvicorn backend.main:app \
        --host "${OPD_HOST:-0.0.0.0}" \
        --port "${OPD_PORT:-8080}" \
        --reload &
else
    uv run --with "transformers>=5.2.0" python -m uvicorn backend.main:app \
        --host "${OPD_HOST:-0.0.0.0}" \
        --port "${OPD_PORT:-8080}" \
        --reload &
fi
BACKEND_PID=$!

# Start frontend
echo "Starting frontend dev server..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=== Running ==="
echo "  Backend:  http://localhost:${OPD_PORT:-8080}"
echo "  Frontend: http://localhost:5173"
echo "  Health:   http://localhost:${OPD_PORT:-8080}/health"
echo ""
echo "Press Ctrl+C to stop both servers."

# Trap Ctrl+C to kill both
cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait
    echo "Done."
}
trap cleanup SIGINT SIGTERM

# Wait for either to exit
wait
