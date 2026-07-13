#!/usr/bin/env bash
# Start TNIC RCA Streamlit dashboard — 100% LOCAL demo (no Render, no OpenAI required)
#
# Usage:
#   ./scripts/demo_tnic_local.sh              # install deps + start dashboard
#   ./scripts/demo_tnic_local.sh --no-install # skip pip install
#   ./scripts/demo_tnic_local.sh --port 8502
#
# Manager demo: Handover → XYZ401 → RCA Report (uncheck OpenAI narrative)
# Docs: docs/DEMO_TNIC_LOCAL_MANAGER.md

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TNIC="$ROOT/xyz_tnic"
PORT="${PORT:-8502}"
SKIP_INSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-install) SKIP_INSTALL=1; shift ;;
    --port) PORT="${2:-8502}"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    -h|--help)
      echo "Usage: $0 [--no-install] [--port 8502]"
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

exec "$PY" -m streamlit run dashboard/app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false
