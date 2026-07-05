# TNIC RCA — 1-Slide Tech Stack & Q&A Cheat Sheets

**Platform:** XYZ Telecom Network Intelligence Copilot (TNIC) + TelecomGPT  
**Date:** 2026-07-05

---

## 1-Slide Tech Stack (copy to PPT / Confluence)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TNIC ROOT CAUSE ANALYSIS PLATFORM — TECH STACK (1 SLIDE)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  PURPOSE     Automated 5G RCA: 28 failure types · 18 agents · 17 rule engines│
│  LANGUAGE    Python 3.12                                                     │
│  API         FastAPI + Uvicorn (:8000)                                       │
│  UI          Streamlit dashboard (:8501)                                     │
│  RCA CORE    Rule engines + KPI thresholds + regex patterns (deterministic)  │
│  ORCHESTRATOR MasterRCAOrchestrator → multi-agent chain → ranked findings   │
│  DATA        CSV datasets · dynamic upload (CSV/LOG/XLSX/ZIP) · SQLite PM DB │
│  EVENT MODEL NormalizedEvent → KPI bridge → existing agents (no new agent)   │
│  OPTIONAL AI OpenAI (narrative reports) · ChromaDB RAG (playbooks)           │
│  CHAT LAYER  TelecomGPT: LangGraph · session memory · guardrails · PII filter │
│  CONFIDENCE  Evidence tiers: UE 60% → +gNB 80% → +PM 90% → +RF 95% → 98%  │
│  TESTS       163 pytest · demo cells XYZ401–410                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Elevator line:** *Expert-system RCA with multi-agent orchestration; LLM optional for narration only.*

---

## Architecture (1 diagram for slides)

```
User → Streamlit / API → MasterRCAOrchestrator → 18 Agents + 17 Rules
                              ↓
                    KPI Service + Upload Event Bridge
                              ↓
              CSV · JSONL uploads · SQLite · ChromaDB (RAG)
```

---

# Q&A Cheat Sheet — MANAGEMENT

| Question | Answer |
|----------|--------|
| **What is RCA here?** | Automated Root Cause Analysis: finds *why* a network problem happened, not just that KPIs are bad. |
| **Is this real AI or rules?** | Primary RCA is **rules + telecom logic** (reproducible). LLM only writes optional executive summaries. |
| **What problems does it cover?** | 28 types: coverage hole, HO fail, RLF, RACH, VoNR, PDU session, beam, config drift, alarms, UE trace, etc. |
| **What data do we need?** | PM counters, HO/RLF/RACH events, gNB syslog, config, neighbors, VoNR, alarms, UE traces — or **upload any supported file**. |
| **Can ops use it without developers?** | Yes — Upload page: drag CSV/LOG/XLSX → auto classify → RCA findings. |
| **How confident are results?** | Each finding has a 0–100% score; cross-source evidence (UE + gNB + PM + RF) raises confidence up to 98%. |
| **Does it replace engineers?** | No — accelerates triage. Engineers validate and fix; platform gives evidence + recommended actions. |
| **Time to value?** | Demo ready on XYZ401–410; single-cell RCA in seconds via API or dashboard. |
| **Production path?** | FastAPI on Render/main branch; datasets dir or upload API; optional OpenAI key for narratives. |
| **ROI story?** | Cuts multi-domain correlation (PM + syslog + RF + UE) from hours to minutes per incident. |

**Management one-liner:** *TNIC turns scattered telecom data into ranked root causes with evidence — rules-first, LLM optional.*

---

# Q&A Cheat Sheet — RF / RAN ENGINEERING

| Question | Answer |
|----------|--------|
| **Which RF issues are covered?** | Coverage hole, weak coverage, overshooting, pilot pollution, interference, beam gaps, too early/late HO, RLF at cell edge. |
| **What RF KPIs drive rules?** | `ss_rsrp`, `ss_rsrq`, `ss_sinr`, CQI, BLER, beam failure ratio, drive-test uploads (RSRP/SINR columns). |
| **How does coverage correlate to HO/RLF?** | `master_rca.py` emits cross-domain findings: coverage hole → HO fail, RLF, RACH fail, throughput, VoNR. |
| **Can I upload drive-test CSV?** | Yes — classified as `RF_MEASUREMENT`; normalized to events; feeds RF Coverage + Master RCA. |
| **UE trace vs gNB syslog?** | UE trace = UE-side (MSG1, RRC, NAS). gNB syslog = network-side (HO_PREP_FAIL, T310). Correlation boosts confidence. |
| **Demo cells?** | XYZ401–404 degraded; XYZ405–410 healthier — use for HO/RLF/coverage demos. |
| **RF agent entry points?** | Dashboard: RF Coverage Map · API: `POST /api/v1/analyze/rf-coverage` · Upload RF CSV on page 17. |
| **Ping-pong / too early HO?** | Handover agent rules: `ho_ping_pong_rate`, `ho_too_early_rate`, `ho_too_late_rate` vs thresholds. |
| **What’s NOT ML?** | No trained RF propagation model — thresholds and catalog rules from telecom playbooks. |

**RF one-liner:** *Upload drive test or pick a cell — platform correlates RSRP/SINR with HO, RLF, RACH, and VoNR failures.*

---

# Q&A Cheat Sheet — ARCHITECTURE REVIEW

| Question | Answer |
|----------|--------|
| **Two orchestrators?** | **TNIC** `MasterRCAOrchestrator` (RCA, deterministic) + **TelecomGPT** LangGraph (chat, LLM plan). Bridge: `backend/tnic/bridge.py`. |
| **Agent contract?** | `BaseAgent.analyze(kpis: dict, query: str) → AgentResult` with `RuleFinding` list. |
| **Rule engine pattern?** | `RuleEngine.evaluate(kpis)` — `RuleDefinition(condition, confidence, actions)`. |
| **Extensibility?** | Add rule in `tnic/rules/` → register in `RULE_ENGINES` → optional agent in `AGENT_REGISTRY`. Upload path: no code — classifier + normalizer. |
| **State / memory?** | RCA: stateless per request. Chat: `MemoryManager` session. Uploads: JSONL event repo + manifest index. RAG: ChromaDB persistent. |
| **Guardrails?** | TNIC: dataset validation, upload extension filter, confidence clamp. TelecomGPT: input/output policy, PII redaction (IMSI/IMEI). |
| **API surface?** | `/api/v1/analyze/*`, `/api/v1/upload/*`, `/api/v1/datasets/*` — OpenAPI at `/docs`. |
| **Data normalization?** | Upload → `FileClassification` → `SchemaInference` → `NormalizedEvent[]` → `events_kpi_bridge` → same KPI dict agents use. |
| **Failure isolation?** | Rule conditions wrapped in try/except; enrichment blocks fail open; OpenAI narrator falls back to template. |
| **Test coverage?** | 163 tests: agents, orchestrator, datasets, upload ingestion, UE protocol, assurance. |
| **Repo layout?** | `xyz_tnic/tnic/` = engine; `backend/tnic/` = mirror; `backend/telecom_ai/` = chat layer. |
| **Dependencies (core)?** | fastapi, pydantic, pandas, sqlalchemy, streamlit, pytest. Optional: openai, chromadb, langgraph. |
| **No ML training?** | Correct — no sklearn/torch in RCA path; `drop_classifier` is weighted heuristic, not trained model. |

**Architecture one-liner:** *Pluggable rule agents over a unified KPI/event bus; optional LLM/RAG at the edges, not the core.*

---

## Demo Script (5 minutes)

1. **Dashboard** → Executive Summary → show XYZ401 worst health.  
2. **Handover page** → cell XYZ401 → agent findings.  
3. **Upload page** → drop `ue_protocol_trace.csv` → show detected type, cells, failures → RCA.  
4. **API** (optional): `POST /api/v1/analyze/rca` with query `"handover failure cell XYZ401"`.  
5. **Close:** Top finding + confidence + recommended action + “163 automated tests.”

---

## Key File Map (for technical deep-dives)

| Topic | Path |
|-------|------|
| Master orchestrator | `tnic/orchestrator/rca_orchestrator.py` |
| Master enrichment | `tnic/orchestrator/master_rca.py` |
| 28 RCA types | `tnic/orchestrator/rca_catalog.py` |
| Agents registry | `tnic/agents/specialists.py` |
| Rule engine base | `tnic/rules/engine.py` |
| KPI merge | `tnic/datasets/kpi_service.py` |
| Upload pipeline | `tnic/services/ingest_pipeline.py` |
| File classifier | `tnic/services/file_classifier.py` |
| Event repository | `tnic/services/event_repository.py` |
| LLM narrator | `tnic/services/report_generator.py` |
| RAG | `tnic/rag/retriever.py` |
| Chat guardrails | `backend/telecom_ai/guardrails.py` |
| Chat orchestrator | `backend/telecom_ai/orchestrator.py` |

---

## Slide Titles (ready to paste)

1. **Problem:** Multi-domain 5G failures need correlated RCA, not siloed KPIs.  
2. **Solution:** TNIC — 18 agents, 28 RCA types, upload-any-file ingestion.  
3. **How it works:** KPI/event bus → rules → ranked findings → optional LLM report.  
4. **Evidence model:** Confidence scales with UE + gNB + PM + RF + transport.  
5. **Demo:** XYZ401 handover + UE trace upload.  
6. **Ask:** Pilot on N production cells with PM + syslog feed.
