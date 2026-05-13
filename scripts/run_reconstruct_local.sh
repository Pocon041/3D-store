#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

JOB_ID=${1:-debug_job}
INPUT=${2:-data/samples/product_images}
QUALITY=${3:-fast}
EXTRA=${4:-}

python -m backend.pipelines.reconstruct \
  --job-id "$JOB_ID" \
  --input "$INPUT" \
  --mode images \
  --quality "$QUALITY" \
  --export-glb $EXTRA
