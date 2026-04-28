#!/usr/bin/env bash
# NHA PS-01 entrypoint.
#
# Path resolution (first that works wins):
#   inputs : NHA_CLAIMS_ROOT env, then /mnt/databanks/input/{filesofdata/Claims,Claims},
#            then ~/Claims, then ./Datasets/filesofdata/Claims (repo).
#   output : NHA_OUTPUT_DIR env, then /mnt/databanks/output (if writable),
#            then ~/outputs.
#   work   : NHA_WORK_ROOT env, then /mnt/databanks/work (if writable),
#            then ~/pipeline_work.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# --- Resolve Claims input ---
pick_claims() {
    if [ -n "${NHA_CLAIMS_ROOT:-}" ] && [ -d "$NHA_CLAIMS_ROOT" ]; then echo "$NHA_CLAIMS_ROOT"; return; fi
    for c in /mnt/databanks/input/filesofdata/Claims \
             /mnt/databanks/input/Claims \
             /mnt/databanks/input \
             "$HOME/Claims" \
             "$REPO_DIR/Datasets/filesofdata/Claims"; do
        if [ -d "$c" ]; then echo "$c"; return; fi
    done
    echo ""
}

# --- Resolve a writable directory: try preferred path; if it fails, return fallback ---
pick_writable_dir() {
    local preferred="$1"
    local fallback="$2"
    if [ -n "$preferred" ]; then
        mkdir -p "$preferred" 2>/dev/null && [ -w "$preferred" ] && { echo "$preferred"; return; }
    fi
    mkdir -p "$fallback"
    echo "$fallback"
}

CLAIMS="$(pick_claims)"
OUTPUT_DIR="$(pick_writable_dir "${NHA_OUTPUT_DIR:-/mnt/databanks/output}" "$HOME/outputs")"
WORK_DIR="$(pick_writable_dir   "${NHA_WORK_ROOT:-/mnt/databanks/work}"     "$HOME/pipeline_work")"

export NHA_CLAIMS_ROOT="$CLAIMS"
export NHA_WORK_ROOT="$WORK_DIR"
export NHA_OUTPUT_DIR="$OUTPUT_DIR"

echo "[run.sh] repo        = $REPO_DIR"
echo "[run.sh] claims_root = ${NHA_CLAIMS_ROOT:-<missing>}"
echo "[run.sh] work_root   = $NHA_WORK_ROOT"
echo "[run.sh] output_dir  = $NHA_OUTPUT_DIR"

if [ -z "$CLAIMS" ]; then
    echo "[run.sh] WARNING: no Claims dataset found — pipeline will produce empty outputs."
    echo "[run.sh]          Run the databank_download_widget notebook cell first, or set NHA_CLAIMS_ROOT."
fi

python -m pip install --quiet --no-input -r requirements.txt || true

python scripts/build_submission.py --out "$OUTPUT_DIR"
