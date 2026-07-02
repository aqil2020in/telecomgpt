#!/bin/bash
# Scrub subscriber/site identifiers from a log before uploading to TelecomGPT.
# Usage: ./scrub_log.sh input.log
# Output: input_anonymized.log (review manually before upload)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 input.log" >&2
  exit 1
fi

IN="$1"
BASE="${IN%.log}"
OUT="${BASE}_anonymized.log"

sed -E \
  -e 's/IMSI[[:space:]]*[0-9]{10,15}/IMSI_REDACTED/gi' \
  -e 's/IMEI[SV]*[[:space:]]*[0-9]{14,16}/IMEI_REDACTED/gi' \
  -e 's/gNB-[A-Za-z0-9_-]+/GNB_XXX/g' \
  -e 's/Site_[A-Za-z0-9_-]+/SITE_XXX/g' \
  "$IN" > "$OUT"

echo "Wrote $OUT — review manually before upload"
