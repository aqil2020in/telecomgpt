# Line Manager Demo — Speaker Script & Slides

**When:** Today · **Duration:** 15–20 min  
**URL:** https://telecomgpt.vercel.app  
**Before call:** Open UI 1 min early · Enable **Show agent trace** · Have `analytics/samples/ue_log.txt` ready

---

## Slide outline (6 slides — paste into PowerPoint)

### Slide 1 — Title
**TelecomGPT**  
Domain-specific AI for 5G RF & Test Engineering  
*[Your name] · Demo · [Date]*

### Slide 2 — The problem
- Band specs, attach logs, fault playbooks scattered across wikis, ShareTechnote, spreadsheets
- Generic ChatGPT lacks telecom tools, structured KB, and repeatable test checklists
- **Goal:** One assistant that routes work to the right specialist — like a virtual test team

### Slide 3 — Architecture (simple)
```
User  →  Next.js (Vercel)  →  FastAPI (Render)  →  LangGraph  →  22 agents  →  KB / RAG / tools
```
- **Path A — Chat:** natural-language questions (`POST /ask`)
- **Path B — Reports:** deterministic attach & UE capability checklists
- **Path C — Instant math** *(branch, merging soon):* link budget tables, HARQ/RRC fault reports

### Slide 4 — What's live today
| Capability | Status |
|------------|--------|
| NR band / device / protocol KB | ✅ Live |
| Multi-agent orchestration + trace | ✅ Live |
| Attach Report & UE Cap Report | ✅ Live |
| RF KPI / drive test (CSV upload) | ✅ Live (needs file) |
| Computed link budget & HARQ fault | 🔜 PR #1 |

### Slide 5 — Live demo flow
1. `What is n78?` — KB + sources + agent trace  
2. Protocol stack chip — multi-agent routing  
3. Attach Report on sample log — PASS/FAIL checklist  

### Slide 6 — Next steps
- Merge PR #1 (instant RF analytics)
- Pilot one team workflow (attach triage or KPI CSV)
- Chat persistence + production hardening

---

## Speaker script (word-for-word)

### OPENING (30 sec)

> "Thanks for the time. I'll show **TelecomGPT** — a domain-specific AI assistant we built for 5G RF and test engineering. It's not generic chat: it uses **22 specialist agents** backed by a structured knowledge base and telecom references. It's deployed as a real web app — UI on Vercel, API on Render — and I'll walk through three scenarios that mirror daily test work."

*[Share screen: telecomgpt.vercel.app]*

> "I've turned on **Show agent trace** at the bottom — that lets us see which agents ran behind each answer."

---

### DEMO 1 — Smart lookup (~2 min)

**Type:** `What is n78?` · **Press Enter**

**While it loads (if slow):**

> "First request can take up to a minute — Render wakes the API from sleep. Normal after that."

**When answer appears:**

> "Here's n78 — TD 3500, FR1, duplex, typical bandwidth. Two things to notice:"

**Point to Sources:**

> "First — **Sources**. Answers are grounded in our KB and indexed telecom docs, not free-form hallucination."

**Expand Agent trace:**

> "Second — the **trace**. The planner sent this to `telecom_kb`, `research`, and `spec`, then `synthesizer` merged the result. Think of it as routing to the right engineers on a virtual team."

---

### DEMO 2 — Protocol knowledge (~2 min)

**Click chip:** `Explain NR protocol stack C-plane vs U-plane` · **Send**

**While loading:**

> "The footer chips are preset prompts for common test tasks. This one asks for control plane vs user plane across the NR stack."

**When answer appears:**

> "We get RRC and NAS on the C-plane, SDAP through PHY on the U-plane — the kind of answer you'd expect from a protocol lead, but with traceability."

**Expand trace:**

> "Different question, different agents. The **planner** picks specialists from keywords — protocol questions don't go to the RF KPI agent. That's intentional routing, not one monolithic prompt."

---

### DEMO 3 — Attach report (~4 min) ⭐ highlight

**Say:**

> "This is the strongest part for our team — **deterministic log analysis**, not LLM guesswork."

**Click:** `📋 Attach Report`

**If prompted for file — upload** `ue_log.txt` (or any `.log` / `.txt`)

**While processing:**

> "This hits a fixed API — `POST /api/nr-sa/attach-report`. It runs a **checklist** against the log: cell search, SIB, RACH, RRC setup, registration, and so on. Each step is PASS or FAIL against defined rules."

**When report appears:**

> "Here's the overall result — X of Y steps passed. We can drill into each step. This is **Path B** — same checklist every time, suitable for regression on attach failures."

**Optional if export button visible:**

> "We can also export to Excel for test records."

---

### BRIDGE — Other capabilities (30 sec, no live demo)

> "Two more buttons worth knowing: **UE Cap Report** runs a similar checklist on UE Capability Enquiry logs — band combos like n77+n78. The chips for **RF KPI assessment** and **drive test** work after you upload a CSV. I didn't demo those live because they need a file — happy to run offline with our campaign data."

---

### GAPS — Be honest (1 min)

> "A few honest limits:"

> "One — **chat history** doesn't survive a page refresh yet; session memory exists on the backend but the UI doesn't restore it."

> "Two — log analysis is **pattern matching**, not full QXDM ASN.1 decode. Good for triage, not a replacement for QCAT."

> "Three — **link budget** and **deep RRC/HARQ fault** reports with computed tables are on our dev branch — PR #1 — merging soon. Production today gives solid RAG answers; the branch adds instant engineering math."

---

### CLOSE — Ask for pilot (1 min)

> "Summary: we have a **deployed, domain-specific multi-agent assistant** with visible routing, sourced answers, and **repeatable attach/UE-cap reports**."

> "I'd propose a **two-week pilot** on one workflow — attach log triage or n78 KPI CSV — and merge PR #1 for instant link-budget and fault analytics. Happy to take questions."

---

## Q&A cheat sheet

| Question | Your answer |
|----------|-------------|
| Is this just ChatGPT? | OpenAI powers reasoning; the **telecom layer** is our agents, KB, tools, and checklists. |
| Can we trust it? | Reports are rule-based. Chat cites sources; a verifier agent cross-checks KB. |
| Production ready? | Good for **assisted** engineering and pilots — not full OSS/log-decode replacement yet. |
| Cost? | Vercel + Render + OpenAI API usage; hybrid engine minimizes LLM calls where possible. |
| How do we extend it? | Add JSON reference data + agent handler — same pattern as link budget on PR #1. |
| Security? | Guardrails block harmful queries; PII redaction on input. Enterprise auth not yet. |

---

## Emergency fallbacks

| Problem | What to do |
|---------|------------|
| API timeout / "waking up" | Wait 30s, retry once; say "cold start on free Render tier" |
| Attach report fails | Use chip `Fault analysis RRC fail` as backup demo |
| Chart chip fails | Skip — say "needs Kaggle dataset on server, on backlog" |
| Manager wants link budget | Say "computed version on PR #1"; show RAG answer on prod if needed |

---

## 60-second version (if time is cut)

1. `What is n78?` → sources + trace (30s)  
2. Attach Report on sample log (30s)  
3. "22 agents, deployed, pilot proposal" (30s)
