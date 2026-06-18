# 12-Week Learning Syllabus: 5G RAN Engineer → AI

Personal study guide using the **TelecomGPT** codebase. Each week: one file to read (30–60 min) and one hands-on exercise (1–2 hrs).

**Production:** UI [telecomgpt.vercel.app](https://telecomgpt.vercel.app) · API [telecomgpt.onrender.com](https://telecomgpt.onrender.com)

**Feature branch (link budget + RRC/HARQ instant answers):** `cursor/sinr-rsrq-link-budget-a733` — merge [PR #1](https://github.com/aqil2020in/telecomgpt/pull/1) before expecting those on production.

See also: [ARCHITECTURE.md](./ARCHITECTURE.md) · [ORCHESTRATION.md](./ORCHESTRATION.md)

---

## How to use this guide

| Day | Activity |
|-----|----------|
| 1 | Read the week's file; annotate with RAN parallels |
| 2 | Complete the exercise; save outputs in a personal notes doc |
| 3 | Run one `/ask` with `"trace": true` on production; compare to your prediction |
| 4 | Optional: 20 min on [LangGraph](https://langchain-ai.github.io/langgraph/) or [RAG](https://python.langchain.com/docs/concepts/rag/) docs for that week's topic |

---

## Phase 1 — Map the system (Weeks 1–3)

### Week 1 — The full stack

**RAN analogy:** OSS/NMS view of the whole RAN — you need the topology before debugging one cell.

| | |
|---|---|
| **Read** | [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) |
| **Exercise** | Open the UI, send: *"Explain 5G NR protocol stack"*. In DevTools → Network, find `POST /ask`. Write down: request body, `session_id`, `steps[]`, `plan.agents[]`, and which artifacts came back. |
| **Success** | You can draw User → Next.js → FastAPI → LangGraph → Agents → Tools → KB/RAG from memory. |

---

### Week 2 — API entry and request paths

**RAN analogy:** Distinguishing OAM, signaling, and user-plane — same network, different paths.

| | |
|---|---|
| **Read** | [`backend/app.py`](../backend/app.py) (first ~200 lines: routes, `/ask`, instant/fast paths) |
| **Exercise** | From terminal: |

```bash
curl https://telecomgpt.onrender.com/health

curl -X POST https://telecomgpt.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"what is PRACH?","trace":true}'
```

| **Success** | You can name **Path A** (multi-agent `/ask`), **Path B** (deterministic report APIs), and **Path C** (instant KB / computed analytics). |

---

### Week 3 — The 22 specialists

**RAN analogy:** Specialist teams (RF, protocol, drive test, fault) — each with a charter.

| | |
|---|---|
| **Read** | [`backend/telecom_ai/agents/taxonomy.py`](../backend/telecom_ai/agents/taxonomy.py) |
| **Exercise** | Build a table: **UI chip or prompt** → **agent name** → **category** (task / retrieval / autonomous / orchestration). Cover at least 10 chips/prompts from the UI. |
| **Success** | Given *"RF KPI assessment on my CSV"*, you predict `rf_metrics` (+ maybe `analytics`) before checking the trace. |

---

## Phase 2 — How questions get routed (Weeks 4–6)

### Week 4 — Intent → plan

**RAN analogy:** Alarm correlation rules — symptom keywords route to the right investigation procedure.

| | |
|---|---|
| **Read** | [`backend/telecom_ai/planning.py`](../backend/telecom_ai/planning.py) |
| **Exercise** | For these 5 queries, **predict** `create_plan()` agents *before* calling the API, then verify with `"trace": true`: |

1. *"SINR vs RSRQ link budget"*
2. *"Fault analysis RRC fail HARQ K1"*
3. *"Generate PowerPoint on n78"*
4. *"Compare S24 vs iPhone 16 5G bands"*
5. *"3GPP TS 38.331 RRC reconfiguration"*

| **Success** | You understand keyword routing vs LLM `refine_plan_with_llm` — when rules win vs when the LLM adjusts. |

---

### Week 5 — LangGraph orchestration

**RAN analogy:** A test campaign runbook — ordered steps, parallel tasks, rollback on failure.

| | |
|---|---|
| **Read** | [`backend/telecom_ai/orchestrator.py`](../backend/telecom_ai/orchestrator.py) |
| **Exercise** | Trace one `/ask` with `"trace": true`. Map each `steps[]` entry to a graph node (`load_memory`, `guardrails_pre`, `plan`, `execute_agents`, `synthesize`, `verify`, etc.). Note which agents ran in parallel. |
| **Success** | You can explain why `synthesizer` and `verifier` appear at the end of multi-agent runs. |

---

### Week 6 — Tools = your instrument panel

**RAN analogy:** Test instruments (spectrum analyzer, throughput tool, log parser) — agents call tools, not raw APIs.

| | |
|---|---|
| **Read** | [`backend/telecom_ai/tools.py`](../backend/telecom_ai/tools.py) — skim `build_tool_registry` and 5–6 tool definitions |
| **Exercise** | Pick 3 domain questions and find the tool: *"ARFCN for n78"*, *"UE capability for S24"*, *"NR power class HPUE"*. Grep the codebase for the tool name, then call `/ask` and confirm the tool appears in the trace or answer. |
| **Success** | You can answer: *"What's the difference between a tool, an agent, and the KB?"* |

---

## Phase 3 — Knowledge and memory (Weeks 7–9)

### Week 7 — RAG (retrieval-augmented generation)

**RAN analogy:** Internal wiki + 3GPP clause lookup — answers grounded in documents.

| | |
|---|---|
| **Read** | [`backend/rag/hybrid_retrieve.py`](../backend/rag/hybrid_retrieve.py) + skim [`backend/data/rag/chunks.json`](../backend/data/rag/chunks.json) structure |
| **Exercise** | Ask: *"What is ShareTechnote view on SSB?"* and *"Explain NR DC"*. Compare `sources[]` in the response. Locally (optional): `python backend/scripts/ingest_rag.py --help`. |
| **Success** | You can explain BM25 + vector hybrid search and when `research` / `spec` agents get selected. |

---

### Week 8 — Deterministic analytics (Path C)

**RAN analogy:** Link budget calculator / KPI script — same physics you trust, wrapped for the agent.

| | |
|---|---|
| **Read** | [`backend/analytics/link_budget.py`](../backend/analytics/link_budget.py) and [`backend/analytics/harq_rrc_fault.py`](../backend/analytics/harq_rrc_fault.py) |
| **Exercise** | |

```bash
cd backend
python3 test_link_budget.py
python3 test_harq_rrc_fault.py
```

Then change one scenario in `link_budget.py` (e.g. add a 3.5 GHz urban case) and re-run tests.

| **Success** | You can trace: user query → `looks_like_*_query()` → `_instant_answer()` → markdown table, **without** calling the LLM. |

---

### Week 9 — Session and long-term memory

**RAN analogy:** UE context (caps, last failure) + network history — short-term vs long-term store.

| | |
|---|---|
| **Read** | [`backend/memory/memory_manager.py`](../backend/memory/memory_manager.py) + [`backend/memory/session_memory.py`](../backend/memory/session_memory.py) |
| **Exercise** | Two `/ask` calls with the same `session_id`: first *"I'm testing n78 on Samsung S24"*, then *"What bands does my device support?"*. Inspect whether the second answer uses context. Check `GET /api/memory/{session_id}` if available. Note: UI does **not** persist chat on refresh ([`frontend/src/pages/index.tsx`](../frontend/src/pages/index.tsx) — `useState` only). |
| **Success** | You can list memory kinds (`semantic`, `episodic`, `procedural`, `conversation`) and one gap you'd fix (e.g. localStorage restore). |

---

## Phase 4 — Safety, UI, and capstone (Weeks 10–12)

### Week 10 — Guardrails and confidence

**RAN analogy:** Change-management rules — block unsafe configs, flag low-confidence KPI alarms.

| | |
|---|---|
| **Read** | [`backend/telecom_ai/guardrails.py`](../backend/telecom_ai/guardrails.py) + [`backend/telecom_ai/confidence.py`](../backend/telecom_ai/confidence.py) |
| **Exercise** | Send a blocked-pattern query (see `_BLOCKED_INPUT_PATTERNS` in guardrails) and a normal RF query. Compare `guardrail_issues` and `confidence` in trace. |
| **Success** | You understand input redaction, output filtering, and per-agent tool allowlists (`TOOL_POLICY`). |

---

### Week 11 — Frontend ↔ API contract

**RAN analogy:** Northbound interface — how the OSS presents alarms, maps, and reports.

| | |
|---|---|
| **Read** | [`frontend/src/pages/index.tsx`](../frontend/src/pages/index.tsx) (message state, `handleAsk`, artifact rendering) |
| **Exercise** | Trigger responses that return: (1) a Plotly chart artifact, (2) Attach Report button, (3) UE Capability Report. For each, find the `Artifact` type field and the React component that renders it. |
| **Success** | You can sketch how to add a one-line UI hint (e.g. "CSV upload required") without breaking the `/ask` flow. |

---

### Week 12 — Capstone: extend TelecomGPT

**RAN analogy:** You own one feature from spec → implementation → test → demo.

| | |
|---|---|
| **Read** | [`docs/ORCHESTRATION.md`](./ORCHESTRATION.md) + Week 8 files as a template |
| **Exercise** | Choose one capstone option below (PRACH scaffold in [Appendix A](#appendix-a-week-12-capstone--prach-occasion-calculator-scaffold)) |
| **Success** | Branch with: code change, test or manual verification, and a 5-minute demo script. |

**Capstone options:**

| Option | What you build | Best if you want to practice… |
|--------|----------------|------------------------------|
| **A — Instant path (recommended)** | New `backend/analytics/<topic>.py` | Deterministic telecom math + Path C wiring |
| **B — Agent + JSON** | Extend `fault_analysis` or `feature_validation` | Domain data modeling |
| **C — UI persistence** | `localStorage` for chat in `index.tsx` | Full-stack product polish |

---

## RAN → AI concept map

| 5G RAN concept | TelecomGPT equivalent |
|----------------|----------------------|
| gNB / cell config | `bts_config` agent + KB JSON |
| Drive test / KPI CSV | `rf_metrics`, `drive_test`, `analytics` |
| QXDM log | `log_debug` agent (pattern scan, not full ASN.1 decode) |
| Fault playbook | `fault_catalog.json` + `fault_analysis` |
| 3GPP spec lookup | `spec` + RAG chunks |
| Test campaign runbook | `planning.py` → `orchestrator.py` workflow |
| OSS northbound API | `app.py` FastAPI routes |
| NMS dashboard | Next.js UI + artifacts |

---

## Appendix A: Week 12 capstone — PRACH occasion calculator (scaffold)

Use this as a step-by-step template for **Option A**. It mirrors how link budget and RRC/HARQ fault were added on branch `cursor/sinr-rsrq-link-budget-a733`.

### Goal

Answer queries like *"PRACH occasion for n78 TDD 30 kHz, config index 159"* with a **computed table** (occasion index, slot, symbol, SCS) — not RAG-only prose.

### Files to create or edit

```
backend/
  data/
    prach_occasion_reference.json    # NEW — format tables, config index ranges
  analytics/
    prach_occasion.py                # NEW — lookup + markdown report
  test_prach_occasion.py             # NEW — unit tests
  telecom_ai/
    core.py                          # _instant_answer() branch
    planning.py                      # _CONFIG_KW or new _PRACH_KW
    tools.py                         # explain_prach_occasion tool
    agents/
      test_engineer.py               # bts_config or log_debug hook
      specialists.py                 # synthesizer pass-through
  app.py                             # GET /api/rf/prach-occasion (optional)
```

### 1. Reference data (`prach_occasion_reference.json`)

```json
{
  "scs_khz": [15, 30, 60, 120],
  "formats": {
    "0": { "duration_symbols": 839, "note": "long sequence FR1" },
    "A1": { "duration_symbols": 139, "note": "short sequence" }
  },
  "config_index_examples": [
    {
      "index": 159,
      "band": "n78",
      "duplex": "TDD",
      "scs_khz": 30,
      "occasions_per_frame": 1,
      "starting_symbol": 0,
      "slots": ["2", "12"],
      "note": "example — verify against TS 38.211 Table 6.3.3.2-3"
    }
  ],
  "rach_procedure_steps": [
    "Msg1 PRACH → Msg2 RAR → Msg3 PUSCH → Msg4 contention resolution"
  ]
}
```

Start with 3–5 verified config indices for bands you test daily (n41, n78, n257).

### 2. Analytics module (`prach_occasion.py`)

Implement these functions (same pattern as `link_budget.py`):

```python
def looks_like_prach_occasion_query(query: str) -> bool:
    """Match prach occasion, config index, rach config, preamble format."""

def prach_occasion_report(
    *,
    band: str | None = None,
    scs_khz: int | None = None,
    config_index: int | None = None,
) -> str:
    """Return markdown: inputs, occasion table, RACH msg flow reminder."""

def parse_prach_query(query: str) -> dict:
    """Extract n78, 30 kHz, index 159 from free text."""
```

**RAN skills you reuse:** TS 38.211 occasion tables, `prach-ConfigurationIndex` from SIB1, TDD pattern vs UL slots.

### 3. Wire Path C (`core.py`)

```python
# In _instant_answer() or fast path handler:
from analytics.prach_occasion import looks_like_prach_occasion_query, prach_occasion_report, parse_prach_query

if looks_like_prach_occasion_query(query):
    args = parse_prach_query(query)
    return prach_occasion_report(**args)
```

### 4. Agent + tool

**`tools.py`:**

```python
@tool_registry.register
def explain_prach_occasion(query: str) -> str:
    """PRACH occasion index, slot, and format for NR cell config."""
    ...
```

**`planning.py`:** add keywords: `prach occasion`, `prach config`, `rach config index`, `preamble format`.

**`test_engineer.py`:** in `bts_config` handler, call `prach_occasion_report` when query matches.

**`specialists.py`:** if answer already contains `## PRACH Occasion`, pass through without LLM rewrite.

### 5. Tests (`test_prach_occasion.py`)

```python
def test_detector():
    assert looks_like_prach_occasion_query("PRACH occasion n78 config index 159")

def test_report_contains_slots():
    md = prach_occasion_report(band="n78", scs_khz=30, config_index=159)
    assert "Msg1" in md
    assert "n78" in md.lower()

def test_instant_path(core):
    out = core.fast_ask("prach occasion for n78 30khz index 159")
    assert out.get("mode") == "fast-kb"
```

Run: `cd backend && python3 test_prach_occasion.py`

### 6. Optional API (`app.py`)

```python
@app.get("/api/rf/prach-occasion")
def api_prach_occasion(band: str, scs_khz: int = 30, config_index: int = 0):
    return {"markdown": prach_occasion_report(band=band, scs_khz=scs_khz, config_index=config_index)}
```

### 7. Demo script (5 min)

1. Show RAG-only answer on production for your query.
2. Show instant path on your branch — table with slot/symbol.
3. Open `test_prach_occasion.py` — explain one assertion.
4. Show trace: `plan.agents` includes `bts_config`, `mode: fast-kb`.

### Acceptance criteria

- [ ] Query detected without false positives on generic *"what is PRACH?"* (glossary/RAG is fine for that).
- [ ] Report cites config index and band explicitly.
- [ ] Tests pass without OpenAI key.
- [ ] Synthesizer does not truncate tables.

---

## Appendix B: Week 12 alternatives (outline)

### Option B — Fault catalog entry

1. Add one symptom to [`backend/data/fault_catalog.json`](../backend/data/fault_catalog.json) (e.g. `beam_failure_recovery`).
2. Extend [`backend/telecom_ai/agents/test_engineer.py`](../backend/telecom_ai/agents/test_engineer.py) `fault_analysis` to match log lines.
3. Test with sample text in [`analytics/samples/ue_log.txt`](../analytics/samples/ue_log.txt).

### Option C — Chat persistence

1. In [`frontend/src/pages/index.tsx`](../frontend/src/pages/index.tsx), on mount: `localStorage.getItem('telecomgpt_messages_' + sessionId)`.
2. After each `/ask` response: `localStorage.setItem(...)`.
3. Add "Clear history" button.
4. Verify refresh restores messages; new session gets new key.

---

## After Week 12

You will have walked every major layer:

**UI → API → planner → orchestrator → agents → tools → KB/RAG → memory → guardrails**

Plus hands-on experience adding a **Path C** deterministic module — the same engineering pattern used for link budget and RRC/HARQ fault analysis.

**Suggested next steps:**

- Merge [PR #1](https://github.com/aqil2020in/telecomgpt/pull/1) and redeploy Render + Vercel.
- Complete PRACH capstone and open a second PR.
- Read `docs/ORCHESTRATION.md` roadmap sections on MCP and procedural memory.
