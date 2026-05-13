#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

PERSON=${1:-data/samples/tryon/person.jpg}
GARMENT=${2:-data/samples/tryon/garment.jpg}
CATEGORY=${3:-upper}
EXTRA=${4:-}

python -m backend.pipelines.tryon \
  --person "$PERSON" \
  --garment "$GARMENT" \
  --category "$CATEGORY" $EXTRA
