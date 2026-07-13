# TNIC RCA — Local Manager Demo (No Render)

**Audience:** Management, NPI leads  
**Duration:** 5–10 minutes  
**Cost:** $0 — no Render, no OpenAI (optional narrative off)  
**Requires:** Python 3.12+, git clone of this repo, internet only for `pip install` once

**Related:** [RCA_MANAGER_EXPLAINER.md](./RCA_MANAGER_EXPLAINER.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) §1.1

---

## What you are demoing

A **standalone TNIC RCA dashboard** that runs **entirely on your laptop or Cloud Agent**:

- Preloaded telecom CSVs (`datasets/`)
- KPI calculation (Python)
- Rule-based RCA agents (Handover, RLF, VoNR, …)
- Master RCA Report (multi-agent)

**No Render. No Vercel. No live OSS. No OpenAI tokens** (if narrative checkbox is off).

This is **Mode B** in [ARCHITECTURE.md §1.1](./ARCHITECTURE.md#11-deployment-vs-local-streamlit-demo-important).

---

## One-command start

From repo root:

```bash
chmod +x start.demo
./start.demo
```

Open: **http://localhost:8502** ( `./start.demo` opens your local browser automatically; on Cloud Agent it prints a Cursor Browser hint )

Options:

```bash
./start.demo --no-install              # fast repeat runs
./start.demo --port 8503               # alternate port
./scripts/demo_tnic_local.sh --no-install   # start without auto-open
```

### Cursor Cloud Agent (“cloud PC”)

On a **Cloud Agent VM**, `localhost` in your **personal PC browser** is not the agent machine. Use **Cursor Browser** (sidebar) after starting the demo:

1. In the agent terminal: `./start.demo --no-install`
2. Leave that terminal running (Streamlit binds to `0.0.0.0:8502`)
3. Open **Cursor Browser** → `http://localhost:8502` (script prints this hint on Cloud Agent)
4. Demo path: **Handover** → cell **XYZ401** → scroll to HO Agent findings

If port 8502 is busy: `PORT=8503 ./scripts/demo_tnic_local.sh --no-install` and open that port in Cursor Browser instead.

---

## Manual start (alternative)

```bash
cd telecomgpt
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r xyz_tnic/requirements-dashboard.txt

export TNIC_DATASETS_DIR="$(pwd)/datasets"
export OPENAI_API_KEY=""
export ENABLE_OPENAI_REPORTS=0
export TNIC_ENABLE_CHROMA=0

cd xyz_tnic
streamlit run dashboard/app.py --server.port 8502
```

---

## 5-minute manager demo script

| Min | Action | Say |
|-----|--------|-----|
| 0–1 | Home page — 10 cells XYZ401–410 | “Preloaded demo cluster; data ships with the product.” |
| 1–2 | **Handover** → XYZ401 | “Summary KPIs at top; charts are evidence from CSV files on disk.” |
| 2–3 | Scroll to **HO Agent findings** | “Rule-based telecom checklist — cause, confidence, fix steps. No cloud API.” |
| 3–4 | **RCA Report** → preset Handover failure → **Run Master RCA** | “Full team of experts on the same local data.” |
| 4–5 | Point at root cause, evidence, recommendations | “Final RCA deliverable — what NOC would attach to a ticket.” |

**Important:** On RCA Report, **uncheck** “Generate structured narrative report” to avoid any OpenAI call.

---

## What runs locally (nothing on Render)

| Component | Location |
|-----------|----------|
| Streamlit UI | Your machine |
| CSV data | `datasets/` on disk |
| KPI service | Python in-process |
| RCA agents & rules | Python in-process |
| Render API | **Not used** |

---

## FAQ for manager

| Question | Answer |
|----------|--------|
| Do we need Render? | **No** for this demo. |
| Do we need OpenAI? | **No** for findings; optional narrative only. |
| Is data live from the network? | **No** — synthetic OSS-shaped CSVs in the repo. |
| Same as production? | **Same RCA engine and rules**; production chat uses Render, this demo runs locally. |
| Can we use real OSS data later? | **Yes** — replace CSVs in `datasets/`; same dashboard and agents. |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `streamlit: command not found` | Run `./scripts/demo_tnic_local.sh` (uses venv) or `python -m streamlit run ...` |
| No cells in dropdown | Check `datasets/` exists and contains `pm_counters.csv` |
| Port in use | `./start.demo --port 8503 --no-install` |
| Can't open localhost on laptop (Cloud Agent) | Use **Cursor Browser** in the agent session, not your PC browser |
| Slow first start | First run installs deps; use `--no-install` after that |

---

## Stop the demo

Press **Ctrl+C** in the terminal running Streamlit.

---

## One sentence for management

> “This is TNIC RCA running **standalone on my machine** — same expert rules as production, preloaded demo data, **zero dependency on Render or OpenAI** for the core diagnosis.”
