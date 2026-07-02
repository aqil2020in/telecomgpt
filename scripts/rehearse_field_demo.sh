#!/usr/bin/env bash
# Rehearse TelecomGPT field demo locally in ~2 minutes.
# Usage: ./scripts/rehearse_field_demo.sh
# Requires: Python 3.10+, pip packages from backend/requirements.txt

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
PORT="${PORT:-8000}"
API="http://127.0.0.1:${PORT}"

echo "==> TelecomGPT field demo rehearsal"
echo "    Root: $ROOT"
echo ""

# --- deps (quick) ---
if ! python3 -c "import pandas, fastapi, uvicorn" 2>/dev/null; then
  echo "==> Installing minimal Python deps..."
  pip install -q -r "$BACKEND/requirements.txt" 2>/dev/null || \
    pip install -q pandas plotly fastapi uvicorn pydantic langgraph langchain-core
fi

# --- unit tests (no OpenAI) ---
echo "==> Running analytics tests..."
cd "$BACKEND"
python3 test_coverage_optimizer.py
python3 test_link_budget.py
python3 test_harq_rrc_fault.py
echo ""

# --- start API in background ---
if curl -sf "${API}/api/health" >/dev/null 2>&1; then
  echo "==> API already running at ${API}"
else
  echo "==> Starting API on port ${PORT}..."
  cd "$BACKEND"
  uvicorn app:app --host 127.0.0.1 --port "$PORT" >/tmp/telecomgpt_demo.log 2>&1 &
  API_PID=$!
  echo "$API_PID" >/tmp/telecomgpt_demo.pid
  for i in $(seq 1 30); do
    if curl -sf "${API}/api/health" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! curl -sf "${API}/api/health" >/dev/null 2>&1; then
    echo "ERROR: API failed to start. Log: /tmp/telecomgpt_demo.log"
    exit 1
  fi
  echo "==> API ready (pid $(cat /tmp/telecomgpt_demo.pid))"
fi
echo ""

# --- sample API calls ---
echo "==> 1/4 Coverage optimizer (3 mi radius)..."
curl -sf "${API}/api/rf/coverage-optimizer?lat=32.93704401921274&lon=-96.98407174060758&radius_miles=3" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  ok:', d.get('ok'), '| points:', d.get('points_in_radius'), '| top score:', (d.get('best_measured') or [{}])[0].get('rf_score'))"
echo ""

echo "==> 2/4 Link budget..."
curl -sf "${API}/api/rf/link-budget?q=Explain%20SINR%20vs%20RSRQ%20link%20budget" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('markdown','')[:120]; print('  ', m.replace(chr(10),' ')[:120], '...')"
echo ""

echo "==> 3/4 RRC/HARQ fault..."
curl -sf "${API}/api/fault/rrc-harq?q=Fault%20analysis%20RRC%20fail%20HARQ%20K1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('markdown','')[:120]; print('  ', m.replace(chr(10),' ')[:120], '...')"
echo ""

echo "==> 4/4 POST /ask with trace (coverage prompt)..."
curl -sf -X POST "${API}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Coverage optimizer 32.93704401921274, -96.98407174060758 3 mile radius best UE locations","trace":true}' \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('  mode:', d.get('mode'))
print('  agents:', d.get('plan',{}).get('agents'))
print('  answer preview:', (d.get('answer') or '')[:150].replace(chr(10),' '), '...')
"
echo ""

echo "=========================================="
echo "  Rehearsal OK"
echo ""
echo "  UI (point frontend to local API):"
echo "    export NEXT_PUBLIC_API_URL=${API}"
echo "    cd frontend && npm run dev"
echo ""
echo "  Or open API docs: ${API}/docs"
echo ""
echo "  Stop background API:"
echo "    kill \$(cat /tmp/telecomgpt_demo.pid 2>/dev/null) 2>/dev/null || true"
echo "=========================================="
