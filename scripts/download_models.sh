#!/bin/bash
# Download MedASR model files into local project folders.
#
# Usage:
#   ./scripts/download_models.sh
#   ./scripts/download_models.sh medasr

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

load_env_file() {
    local env_file="$1"
    [[ -f "$env_file" ]] || return 0

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"

            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"

            if [[ "$value" =~ ^\"(.*)\"$ ]]; then
                value="${BASH_REMATCH[1]}"
            elif [[ "$value" =~ ^\'(.*)\'$ ]]; then
                value="${BASH_REMATCH[1]}"
            else
                value="${value%%[[:space:]]#*}"
                value="${value%"${value##*[![:space:]]}"}"
            fi

            if [[ -z "${!key+x}" ]]; then
                export "$key=$value"
            fi
        fi
    done < "$env_file"
}

select_hf_token() {
    if [[ -n "${HF_TOKEN:-}" ]]; then
        export HF_TOKEN
        export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"
        return 0
    fi
    if [[ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
        export HF_TOKEN="$HUGGING_FACE_HUB_TOKEN"
        export HUGGING_FACE_HUB_TOKEN
        return 0
    fi
    if [[ -n "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
        export HF_TOKEN="$HUGGINGFACEHUB_API_TOKEN"
        export HUGGING_FACE_HUB_TOKEN="$HUGGINGFACEHUB_API_TOKEN"
        return 0
    fi
    if [[ -n "${OPD_HF_TOKEN:-}" ]]; then
        export HF_TOKEN="$OPD_HF_TOKEN"
        export HUGGING_FACE_HUB_TOKEN="$OPD_HF_TOKEN"
        return 0
    fi
    return 1
}

load_env_file "$ENV_FILE"

TARGET="${1:-all}"
if [[ "$TARGET" != "all" && "$TARGET" != "medasr" ]]; then
    echo "Invalid target: $TARGET"
    echo "Use one of: all | medasr"
    exit 1
fi

if ! select_hf_token; then
    echo "[ERROR] No Hugging Face token found."
    echo "        Set HF_TOKEN in .env (or HUGGING_FACE_HUB_TOKEN / HUGGINGFACEHUB_API_TOKEN / OPD_HF_TOKEN)."
    exit 1
fi

MODEL_CACHE_DIR="${OPD_MODEL_CACHE_DIR:-models/hf_cache}"
MEDASR_LOCAL_DIR="${OPD_MEDASR_LOCAL_DIR:-models/medasr}"

if [[ ! "$MODEL_CACHE_DIR" = /* ]]; then
    MODEL_CACHE_DIR="$PROJECT_DIR/$MODEL_CACHE_DIR"
fi
if [[ ! "$MEDASR_LOCAL_DIR" = /* ]]; then
    MEDASR_LOCAL_DIR="$PROJECT_DIR/$MEDASR_LOCAL_DIR"
fi

mkdir -p "$MODEL_CACHE_DIR"
export HF_HOME="${HF_HOME:-$MODEL_CACHE_DIR/hf_home}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$MODEL_CACHE_DIR/hub}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$MODEL_CACHE_DIR/transformers}"

echo "Downloading models into local project folders..."
echo "  cache dir: $MODEL_CACHE_DIR"
echo "  medasr dir: $MEDASR_LOCAL_DIR"
echo ""

DOWNLOAD_MEDASR=0
if [[ "$TARGET" == "all" || "$TARGET" == "medasr" ]]; then
    DOWNLOAD_MEDASR=1
    mkdir -p "$MEDASR_LOCAL_DIR"
fi

PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python"
fi

"$PYTHON_BIN" - <<'PY' "$DOWNLOAD_MEDASR" "$MEDASR_LOCAL_DIR" "$HF_TOKEN"
import sys
from huggingface_hub import snapshot_download

download_medasr = sys.argv[1] == "1"
medasr_dir = sys.argv[2]
token = sys.argv[3]

jobs = []
if download_medasr:
    jobs.append(("google/medasr", medasr_dir))

for repo, out_dir in jobs:
    print(f"== Downloading {repo} -> {out_dir}")
    snapshot_download(
        repo_id=repo,
        local_dir=out_dir,
        token=token,
    )
    print(f"== Done: {repo}\n")
PY

echo "Model download complete."
