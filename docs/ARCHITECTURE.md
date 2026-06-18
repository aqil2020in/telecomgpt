# TelecomGPT Architecture

Domain-specific multi-agent AI for **5G/LTE RF & Test Engineering**: Adaptive RAG + LangGraph + FastAPI + Next.js.

See also: **[ORCHESTRATION.md](./ORCHESTRATION.md)** (guardrails, integrations, env vars) · **[LEARNING_SYLLABUS.md](./LEARNING_SYLLABUS.md)** (12-week RAN → AI study guide) · **Agent deck:** `python backend/scripts/generate_agent_architecture_ppt.py`

---

## 1. System overview (deployment)

```mermaid
flowchart TB
    subgraph Users["Users"]
        TE[Senior Test Engineer]
    end

    subgraph Client["Client layer"]
        Next["Next.js Chat UI\n(Vercel)"]
        ST["Streamlit Analytics\n(optional, local)"]
    end

    subgraph Render["Render — 2GB API"]
        API["FastAPI\nbackend/app.py"]
        LG["LangGraph Orchestrator"]
        Tools["Tool Registry\nKB · RAG · CSV · PPT"]
        Agents["22 Specialist Agents"]
    end

    subgraph Knowledge["Knowledge & data"]
        KB[("Structured KB\nbands · devices · calculators")]
        Chunks[("BM25 RAG\nchunks.json ~2.2k")]
        Chroma[("Chroma Vector\nsession + RAG refs")]
        Refs[("Reference JSON\nattach · UE cap · stack")]
        Session[("Session files\nCSV · logs")]
    end

    subgraph External["Live references"]
        STweb["ShareTechnote"]
        SQ["sqimway.com"]
        GPP["3GPP.org"]
        OAI["OpenAI GPT-4o-mini"]
    end

    TE --> Next
    TE -.-> ST
    Next -->|POST /ask · upload · reports| API
    ST -.->|analytics APIs| API
    API --> LG
    LG --> Agents
    Agents --> Tools
    Tools --> KB
    Tools --> Chunks
    Tools --> Chroma
    Tools --> Refs
    Tools --> Session
    Tools --> STweb
    Tools --> SQ
    Tools --> GPP
    LG --> OAI
    API --> Next
```

| Layer | Where | Role |
| --- | --- | --- |
| **UI (primary)** | Vercel | Chat, suggestion chips, agent trace, attach/UE-cap reports |
| **UI (analytics)** | `streamlit run analytics/app.py` | CSV/log charts — not the main chat path |
| **API + brain** | Render 2GB | FastAPI wraps LangGraph |
| **LLM** | OpenAI (prod) / Ollama (local) | Synthesis in `synthesizer` agent |

**Production URLs:** API `https://telecomgpt.onrender.com` · UI `https://telecomgpt.vercel.app`

---

## 2. Request flow — two paths

```mermaid
flowchart LR
    subgraph UI["Next.js UI"]
        Chips["Suggestion chips"]
        Chat["Chat + upload"]
        Attach["Attach Report"]
        UECap["UE Cap Report"]
        Trace["Agent trace"]
    end

    subgraph PathA["Path A — Multi-agent"]
        Ask["POST /ask"]
        Orch["LangGraph"]
    end

    subgraph PathB["Path B — Deterministic"]
        AttachAPI["POST /api/nr-sa/attach-report"]
        UECapAPI["POST /api/nr/ue-capability/report"]
        Scan["Rule-based log scanners"]
    end

    Chips --> Ask
    Chat --> Ask
    Trace --> Ask
    Chat --> Upload["POST /api/upload"]
    Upload --> SessionStore[("Session store")]
    SessionStore --> Orch
    Ask --> Orch

    Attach --> AttachAPI
    UECap --> UECapAPI
    AttachAPI --> Scan
    UECapAPI --> Scan

    Orch --> Response["Answer + artifacts + sources"]
    Scan --> Report["Checklist + PDF/Excel"]
```

| Path | Use when | Trust model |
| --- | --- | --- |
| **A — `/ask`** | Explain, troubleshoot, KPI analysis, open questions | RAG + LLM + sources |
| **B — report APIs** | Attach / UE capability checklist scoring | Rule-based, auditable, PDF/Excel |

---

## 3. LangGraph orchestrator pipeline

```mermaid
flowchart TB
    START([User query]) --> LM[load_memory]
    LM --> GP[guardrails_pre]
    GP -->|blocked| SM[save_memory]
    GP --> PL[plan agents]
    PL --> CG[confidence_gate]
    CG -->|clarify| SM
    CG --> PB[parallel_batch\nup to 8 agents]
    PB --> ST[sequential_tail]
    ST --> SYN[synthesizer]
    SYN --> VER[verifier]
    VER --> GO[guardrails_post]
    GO --> SM
    SM --> END([Response to UI])

    LM -.-> Mem[("Memory\nsession · semantic\nepisodic · procedural")]
    SM -.-> Mem
```

**Module:** `backend/telecom_ai/orchestrator.py`

---

## 4. Adaptive hybrid RAG

```mermaid
flowchart TB
    Q[Query] --> Route{Query type?}

    Route -->|band · device · glossary| Fast["Fast path\nStructured KB"]
    Route -->|explain · troubleshoot · spec| Hybrid["hybrid_retrieve"]

    Hybrid --> BM25["BM25\nstatic chunks"]
    Hybrid --> VEC["Chroma vector\nmemory"]
    Hybrid --> Live["Live fetch"]
    Hybrid --> Web["Tavily web\n(optional)"]

    Live --> ST["ShareTechnote pages"]
    Live --> SQ["sqimway band tables\nTS 38.104"]
    Live --> GPP["3GPP dynareport\nTS series rows"]

    BM25 --> Merge["Merged context"]
    VEC --> Merge
    Live --> Merge
    Web --> Merge
    Fast --> Answer
    Merge --> LLM["LLM synthesizer\n+ Sources URLs"]
    LLM --> Answer[Final answer]
```

**Module:** `backend/rag/hybrid_retrieve.py` · **Live fetch:** `backend/rag/live_fetch.py`

| Retrieval layer | Source |
| --- | --- |
| BM25 | `backend/data/rag/chunks.json` (~2,230 chunks) |
| Vector | ChromaDB `backend/data/memory/vector/` |
| Live ShareTechnote | Topic URL guess + top RAG cite refresh |
| Live sqimway | `nr_band.php` band rows (TS 38.104) |
| Live 3GPP | dynareport series pages + TS row extraction |
| Web | Tavily with domain bias (optional) |

---

## 5. Agent taxonomy

```mermaid
flowchart TB
    subgraph Orch["Orchestration"]
        SYN[synthesizer]
        VER[verifier]
    end

    subgraph Task["Task agents"]
        LD[log_debug]
        FA[fault_analysis]
        RF[rf_metrics]
        BC[bts_config]
        FV[feature_validation]
        AN[analytics]
        DT[drive_test]
        PR[presentation]
    end

    subgraph Retrieval["Retrieval agents"]
        RS[research]
        SP[spec]
    end

    subgraph Auto["Autonomous agents"]
        KB[telecom_kb]
        RX[react]
        CR[crew]
        AG[autogen]
    end

    LG[LangGraph\nparallel_batch] --> Task
    LG --> Retrieval
    LG --> Auto
    Task --> SYN
    Retrieval --> SYN
    Auto --> SYN
    SYN --> VER
```

**Full map:** `GET /api/agents/taxonomy` · **Module:** `backend/telecom_ai/agents/taxonomy.py`

### Roles & responsibilities

#### Infrastructure nodes (LangGraph)

| Node | Responsibility |
| --- | --- |
| `load_memory` | Assemble session + semantic/episodic/procedural context |
| `guardrails_pre/post` | Input/output filtering, PII redaction |
| `plan` | Keyword (+ optional LLM) agent routing |
| `confidence_gate` | Clarification on vague low-confidence queries |
| `parallel_batch` | Run up to 8 agents concurrently |
| `save_memory` | Persist Q&A and successful plans |

#### Task agents (Test Engineer)

| Agent | Responsibility |
| --- | --- |
| `log_debug` | Parse UE logs, RRC/NAS scan, attach/UE-cap hints, protocol stack scan |
| `fault_analysis` | Symptom → cause → checks from fault catalog |
| `rf_metrics` | Drive-test CSV KPI grading, RF handbook hints |
| `bts_config` | gNB parameter scan vs 3GPP limits |
| `feature_validation` | 3GPP feature test templates + pass criteria |
| `drive_test` | SLA rules, GPS RF maps |
| `analytics` | Kaggle CSV, Plotly chart artifacts |
| `presentation` | PowerPoint report generation |
| `comparison` | Device/technology comparison |
| `compliance` | FCC regulatory checks |
| `deploy` / `eval` | Health status, KB smoke tests |

#### Retrieval & autonomous agents

| Agent | Responsibility |
| --- | --- |
| `research` | Hybrid RAG + live fetch + memory recall |
| `spec` | 3GPP TS-focused retrieval with citations |
| `telecom_kb` | Multi-tool KB lookups (bands, devices, CA, calculators) |
| `react` | ReAct loop — LLM picks tools |
| `crew` / `autogen` | CrewAI / AutoGen under hybrid engine mode |

#### Orchestration agents

| Agent | Responsibility |
| --- | --- |
| `synthesizer` | Merge agent outputs + RAG + LLM; append Sources |
| `verifier` | Cross-check answer vs KB agent outputs |

---

## 6. Memory architecture

```mermaid
flowchart LR
    subgraph Short["Short-term"]
        ChatHist["Chat turns\n~100 max"]
        Uploads["Uploaded CSV/log paths"]
        Profile["User profile\nbands · devices"]
    end

    subgraph Long["Long-term vector"]
        Sem["Semantic facts"]
        Epi["Episodic Q&A"]
        Pro["Procedural plans"]
        Ref["RAG references\nkind=reference"]
    end

    subgraph Static["Static knowledge"]
        MasterDB["telecom_master_db.json"]
        Catalog["nr_bands · attach · UE cap refs"]
        ChunksFile["chunks.json BM25"]
    end

    Ask["/ask"] --> Short
    Ask --> Long
    Ask --> Static
    Boot["Startup / ingest-rag"] --> Ref
```

| Operation | Endpoint |
| --- | --- |
| Snapshot | `GET /api/memory/{session_id}` |
| Compact session → long-term | `POST /api/memory/{session_id}/refresh` |
| Rebuild BM25 chunks | `POST /api/rag/reindex` |
| Vector index (background) | `POST /api/memory/ingest-rag` |
| Poll vector ingest | `GET /api/memory/ingest-rag/status` |

---

## 7. Layer stack

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION    Next.js (chat)  │  Streamlit (analytics)    │
├─────────────────────────────────────────────────────────────┤
│  API GATEWAY     FastAPI — /ask, uploads, reports, RAG ops  │
├─────────────────────────────────────────────────────────────┤
│  ORCHESTRATION   LangGraph — plan, guardrails, parallel run │
├─────────────────────────────────────────────────────────────┤
│  AGENTS          Task │ Retrieval │ Autonomous │ Synth/Verify│
├─────────────────────────────────────────────────────────────┤
│  TOOLS           KB lookup · hybrid_search · CSV · log · PPT│
├─────────────────────────────────────────────────────────────┤
│  KNOWLEDGE       JSON KB │ BM25 │ Chroma │ Live ST/sqim/3GPP│
├─────────────────────────────────────────────────────────────┤
│  LLM             OpenAI (prod) │ Ollama (local dev)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Test Engineer tools (Path B)

| Feature | API |
| --- | --- |
| NR SA attach report | `POST /api/nr-sa/attach-report` (+ PDF/Excel export) |
| UE Capability report | `POST /api/nr/ue-capability/report` (+ PDF/Excel) |
| NR band catalog (91 bands) | `GET /api/bands/nr` |
| Protocol stack reference | `GET /api/nr/protocol-stack/reference` |
| Power class reference | `GET /api/nr/power-class/reference` |
| RF handbook | `GET /api/rf/handbook/reference` |

---

## 9. Key endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /ask` | Multi-agent chat (async job for slow queries) |
| `POST /api/upload` | Session CSV/log upload |
| `GET /api/agents/taxonomy` | Full agent map |
| `GET /api/rag/status` | Chunk count, live fetch flags |
| `POST /api/rag/reindex` | Re-crawl ShareTechnote seed URLs |
| `POST /api/memory/ingest-rag` | Background vector index |
| `GET /api/memory/ingest-rag/status` | Poll vector ingest |
| `GET /api/health` | Liveness + `low_memory`, `vector_enabled` |
| `GET /api/monitoring/runs` | Recent orchestrator metrics |

---

## 10. Production configuration (2GB Render)

| Variable | Value | Effect |
| --- | --- | --- |
| `TELECOMGPT_LOW_MEMORY` | `0` | Full parallelism (8 agents) |
| `TELECOMGPT_VECTOR` | `1` | Chroma hybrid retrieval |
| `TELECOMGPT_LIVE_FETCH` | `1` | Live ShareTechnote/sqimway/3GPP |
| `TELECOMGPT_AUTO_REINDEX` | `1` | Vector ingest on boot (background) |
| `TELECOMGPT_ENGINE` | `hybrid` | LangGraph + CrewAI/AutoGen spokes |

See `render.yaml` for the full blueprint.

---

## 11. Local setup

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --port 8000

cd ../frontend
npm install && npm run dev   # NEXT_PUBLIC_API_URL=http://localhost:8000

streamlit run analytics/app.py   # optional analytics UI
```

Generate architecture PowerPoint:

```bash
cd backend
pip install python-pptx
python scripts/generate_agent_architecture_ppt.py
# → backend/data/reports/TelecomGPT_AI_Agent_Architecture_YYYYMMDD.pptx
```

Optional Mem0: `pip install mem0ai` and `TELECOMGPT_MEMORY=mem0`.
