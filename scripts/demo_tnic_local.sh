#!/usr/bin/env bash
# Start TNIC RCA Streamlit dashboard — 100% LOCAL demo (no Render, no OpenAI required)
#
# Usage:
#   ./scripts/demo_tnic_local.sh              # install deps + start dashboard
#   ./scripts/demo_tnic_local.sh --no-install # skip pip install
#   ./scripts/demo_tnic_local.sh --port 8502
#   ./scripts/demo_tnic_local.sh --open       # start + open browser (local) or Cursor Browser hint (cloud)
#
# Manager demo: Handover → XYZ401 → RCA Report (uncheck OpenAI narrative)
# Docs: docs/DEMO_TNIC_LOCAL_MANAGER.md

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TNIC="$ROOT/xyz_tnic"
PORT="${PORT:-8502}"
SKIP_INSTALL=0
OPEN_BROWSER=0

open_demo_url() {
  local url="$1"
  if [[ -n "${CURSOR_AGENT:-}" || -n "${CURSOR_CLOUD_AGENT:-}" ]]; then
    echo ""
    echo "  Cloud Agent: open Cursor Browser → ${url}"
    echo "  (Your laptop browser cannot reach this VM's localhost.)"
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  elif command -v open >/dev/null 2>&1; then
    open "$url"
  elif command -v start >/dev/null 2>&1; then
    start "$url"
  else
    "$PY" -m webbrowser "$url" >/dev/null 2>&1 || true
  fi
}

wait_for_dashboard() {
  local url="$1"
  local i
  for i in $(seq 1 60); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "WARNING: Dashboard did not respond at ${url} within 60s; open it manually."
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-install) SKIP_INSTALL=1; shift ;;
    --open) OPEN_BROWSER=1; shift ;;
    --port) PORT="${2:-8502}"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    -h|--help)
      echo "Usage: $0 [--no-install] [--open] [--port 8502]"
      exit 0
      ;;
    *) shift ;;
  esac
done

echo "=============================================="
echo "  TNIC RCA — Local Manager Demo (no Render)"
echo "=============================================="
echo "  Repo:     $ROOT"
echo "  Datasets: $ROOT/datasets"
echo "  Port:     $PORT"
echo ""

# --- datasets ---
if [[ ! -d "$ROOT/datasets" ]] || [[ -z "$(ls -A "$ROOT/datasets"/*.csv 2>/dev/null)" ]]; then
  echo "ERROR: Missing datasets/ CSV files. Clone repo: git clone https://github.com/aqil2020in/telecomgpt.git"
  exit 1
fi
export TNIC_DATASETS_DIR="$ROOT/datasets"

# --- zero-cost demo: no OpenAI, no Chroma ---
export OPENAI_API_KEY=""
export ENABLE_OPENAI_REPORTS=0
export TNIC_ENABLE_CHROMA=0

# --- venv (prefer repo .venv) ---
VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "==> Creating virtualenv at $VENV"
  python3 -m venv "$VENV"
fi
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  echo "==> Installing dashboard dependencies (lightweight, no Chroma)..."
  "$PIP" install -q --upgrade pip
  "$PIP" install -q -r "$TNIC/requirements-dashboard.txt"
fi

if ! "$PY" -c "import streamlit" 2>/dev/null; then
  echo "ERROR: streamlit not installed. Run without --no-install or: pip install -r xyz_tnic/requirements-dashboard.txt"
  exit 1
fi

# --- quick smoke test ---
echo "==> Smoke test: KPI + Handover agent for XYZ401..."
cd "$TNIC"
"$PY" -c "
from tnic.datasets.kpi_service import compute_cell_kpis
from tnic.agents.specialists import HOAgent
k = compute_cell_kpis('XYZ401').kpis
r = HOAgent().analyze(k, query='handover failure cell XYZ401')
print('  HO success rate:', k.get('ho_success_rate'), '| findings:', len(r.findings))
"

echo ""
echo "==> Starting Streamlit dashboard..."
echo "    Open: http://localhost:${PORT}"
echo ""
echo "  Manager demo path:"
echo "    1. Handover → cell XYZ401 → HO Agent findings"
echo "    2. RCA Report → Handover failure → Run Master RCA"
echo "       (uncheck 'Generate structured narrative report' for zero OpenAI)"
echo ""
echo "  Press Ctrl+C to stop."
echo "=============================================="

DEMO_URL="http://localhost:${PORT}"
STREAMLIT_ARGS=(
  -m streamlit run dashboard/app.py
  --server.port "$PORT"
  --server.address 0.0.0.0
  --server.headless true
  --browser.gatherUsageStats false
)

if [[ "$OPEN_BROWSER" -eq 0 ]]; then
  exec "$PY" "${STREAMLIT_ARGS[@]}"
fi

"$PY" "${STREAMLIT_ARGS[@]}" &
STREAMLIT_PID=$!
trap 'kill "$STREAMLIT_PID" 2>/dev/null || true' EXIT INT TERM

if wait_for_dashboard "$DEMO_URL"; then
  echo "==> Opening demo dashboard..."
  open_demo_url "$DEMO_URL"
fi

wait "$STREAMLIT_PID"
