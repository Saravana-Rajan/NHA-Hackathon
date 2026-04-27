#!/usr/bin/env bash
# NHA PS-01 evaluator entrypoint.
#
# The hackathon harness mounts the participant inputs at /mnt/databanks/input
# and reads outputs from /mnt/databanks/output. This script wires both paths
# into the existing pipeline without changing the local developer workflow.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

INPUT_ROOT="${NHA_INPUT_ROOT:-/mnt/databanks/input}"
OUTPUT_DIR="${NHA_OUTPUT_DIR:-/mnt/databanks/output}"
WORK_DIR="${NHA_WORK_ROOT:-/mnt/databanks/work}"

# Locate the actual Claims tree under the mounted input.
if   [ -d "$INPUT_ROOT/filesofdata/Claims" ]; then CLAIMS="$INPUT_ROOT/filesofdata/Claims"
elif [ -d "$INPUT_ROOT/Claims" ];              then CLAIMS="$INPUT_ROOT/Claims"
else                                                CLAIMS="$INPUT_ROOT"
fi

export NHA_CLAIMS_ROOT="$CLAIMS"
export NHA_WORK_ROOT="$WORK_DIR"
export NHA_OUTPUT_DIR="$OUTPUT_DIR"

mkdir -p "$OUTPUT_DIR" "$WORK_DIR"

echo "[run.sh] repo        = $REPO_DIR"
echo "[run.sh] claims_root = $NHA_CLAIMS_ROOT"
echo "[run.sh] work_root   = $NHA_WORK_ROOT"
echo "[run.sh] output_dir  = $NHA_OUTPUT_DIR"

python -m pip install --quiet --no-input -r requirements.txt || true

python scripts/build_submission.py --out "$OUTPUT_DIR"
