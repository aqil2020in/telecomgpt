# TelecomGPT

A domain-specific AI assistant for cellular/RF engineering. It answers questions about
5G NR and LTE bands, device capabilities, CA/EN-DC/NR-DC, and performs 3GPP-grounded
calculations (NR-ARFCN, GSCN, peak throughput). Core routing is deterministic; an
optional LLM fallback (OpenAI) handles open-ended questions with knowledge-base context.

## Architecture

```
backend/                  FastAPI + knowledge base + calculators
  app.py                  REST API (POST /ask, /api/devices, /api/bands)
  telecom_ai/             Engine package
    core.py               TelecomAI — keyword router (device -> CA/EN-DC -> PHY math -> bands -> LLM)
    loaders.py            TelecomDB — knowledge layer with answer_* methods
    reasoning.py          llm_answer — optional LLM fallback with KB context
  data/
    telecom_master_db.json  NR/LTE band plans, CA/EN-DC/NR-DC combos, FCC lists, glossary
    devices/*.json          Per-device sheets incl. validated ca/endc/nrdc combo lists
  tools/
    arfcn_calculator.py     NR-ARFCN <-> frequency (TS 38.104 §5.4.2.1)
    gscn_calculator.py      GSCN <-> SSB frequency (TS 38.104 §5.4.3.1)
    throughput_calculator.py  NR peak data rate (TS 38.306 §4.1.2)
frontend/                 Next.js (pages router, TypeScript) minimal ask UI
```

## Quick start

### 1. Backend (Python 3.10+)

```bash
pip install -r requirements.txt
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000
```

Interactive API docs at http://127.0.0.1:8000/docs. Add `--reload` during development.

### 2. Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev                  # serves http://localhost:3000
```

The page calls the backend directly at `http://localhost:8000/ask` (CORS is
enabled on the FastAPI app).

## Example queries

| Query | What happens |
| --- | --- |
| `What is band n78?` | Band plan lookup from the master DB |
| `Does the S24 support n79?` | Device capability check |
| `Compare Pixel 9 vs iPhone 16` | Band/modem diff between two devices |
| `Does the iPhone 17 support carrier aggregation?` | Device CA/EN-DC/NR-DC combo summary |
| `Does the S23 support n77+n78 CA?` | Device-level combo validation |
| `Is carrier aggregation n41-n71 supported?` | Network-level CA combo validation |
| `Can I run EN-DC with b66+n77?` | EN-DC combo validation |
| `Is n77 FCC licensed?` | FCC category (licensed/unlicensed/mmWave) |
| `What FCC US bands exist for NR?` | US regulatory band overview |
| `ARFCN 632448` | NR-ARFCN → 3486.72 MHz (TS 38.104) |
| `Convert 3500 MHz to ARFCN` | Frequency → nearest raster point |
| `GSCN 7880` | SSB reference frequency lookup |
| `Max throughput 100 MHz 4 layers 256QAM` | TS 38.306 peak-rate formula |
| `What is DSS?` | Glossary definition |

## CLI usage of the calculators

The tools are standalone:

```bash
python backend/tools/arfcn_calculator.py 632448
python backend/tools/gscn_calculator.py 7880
python backend/tools/throughput_calculator.py
```

## API

| Method | Endpoint | Body | Returns |
| --- | --- | --- | --- |
| POST | `/ask` | `{"query": "..."}` | `{"answer": "..."}` |
| GET | `/api/devices` | — | Device summaries |
| GET | `/api/bands` | — | NR + LTE band plans |
| GET | `/api/health` | — | Liveness probe |

## Notes

- Device band lists are representative of US/international variants and are
  intended for demonstration; verify against FCC/operator certification data
  before engineering use.
- The routing layer is deterministic and traceable: every numeric answer cites
  the 3GPP clause used to compute it.
- To enable the LLM fallback for open-ended questions: `pip install openai`,
  set `OPENAI_API_KEY`, and optionally `TELECOMGPT_MODEL` (default `gpt-4o-mini`).
- `python backend/smoke_test.py` exercises all five routing branches.
