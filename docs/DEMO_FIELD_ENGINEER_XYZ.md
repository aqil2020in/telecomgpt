# Field Engineer Demo — XYZ Telecom (Manager + Team Brief)

**Role:** Senior 5G Test Engineer (field)  
**Audience:** Line manager + RF/protocol test team  
**Duration:** 15–20 minutes  
**Product:** TelecomGPT — domain multi-agent AI for 5G RF & test engineering

---

## What is NEW to show (not generic ChatGPT)

| # | Demo | Why it matters for XYZ field team |
|---|------|----------------------------------|
| 1 | **Coverage Optimizer** — 3 mi radius around your site | “Where should UE test for best SINR/RSRP?” from drive-test CSV |
| 2 | **Instant link budget** — SINR vs RSRQ tables | Computed RF math, not hallucinated prose |
| 3 | **RRC/HARQ fault** — K1, RV, Msg1–4 | Faster attach/mobility triage from logs |
| 4 | **Attach Report** — PASS/FAIL checklist | Repeatable NR SA attach validation |
| 5 | **Agent trace** | Transparency — which specialist ran |

**Production today (main):** chat + attach/UE-cap + basic fault catalog.  
**Your branch (PR #1):** items 1–3 + docs. **Merge before demo** if you want live on Render, or **run locally** for guaranteed new features.

---

## Tomorrow: 18-minute run-of-show

### Before the meeting (10 min earlier)

- [ ] Open UI: https://telecomgpt.vercel.app (or local if demoing branch)
- [ ] Enable **Show agent trace**
- [ ] Files on desktop:
  - `analytics/samples/ho_demo_anonymized.log`
  - `backend/data/samples/coverage_dallas_3mi.csv` (or your scrubbed drive-test)
- [ ] Optional: wake API — send one harmless query first

---

### Minute 0–2 — Frame for XYZ

**Say:**

> “I’m demoing **TelecomGPT** — a telecom-specific assistant we can pilot for XYZ field and lab test. It’s not generic AI: **22 specialist agents** route questions to RF KPI, fault playbooks, drive-test maps, and deterministic checklists. I’ll show three things that save field time: **where to test for best coverage**, **instant link budget**, and **structured fault triage** — all with traceability.”

**One slide (verbal):**

```
Field engineer question → TelecomGPT → right agent → KB/tools/CSV → answer + sources/trace
```

---

### Minute 2–5 — NEW #1: Coverage Optimizer (hero demo)

**If branch/local:**

1. Upload `coverage_dallas_3mi.csv` (or your anonymized CSV)
2. Prompt:
```text
Coverage optimizer 32.93704401921274, -96.98407174060758 3 mile radius — best UE locations
```

**Show:**
- Table: **Top locations** (lat/lon, score, SINR, RSRP, SSB beam)
- **Weak zones** to avoid
- **Suggested verify** points (go drive here next)
- Map artifact if rendered

**XYZ value:**

> “Instead of scrolling a 2-hour drive-test in Excel, the team gets ranked coordinates for UE placement and retest within our 3-mile cluster.”

**If only production:** use RF KPI chip + uploaded CSV; explain optimizer ships on next deploy.

---

### Minute 5–8 — NEW #2: Instant link budget

**Prompt (chip or type):**
```text
Explain SINR vs RSRQ link budget
```

**Show:** computed table (Friis, RSRP, worked scenarios) — **not** vague LLM text.

**Say:** “Path C — deterministic telecom math, same every time. Good for training juniors and customer-facing RF explanations.”

---

### Minute 8–11 — NEW #3: Fault triage (field reality)

**Option A — log upload:** `ho_demo_anonymized.log` +  
```text
Fault analysis handover failure then RACH failure on target PCI 205
```

**Option B — chat only:**
```text
Handover failure mobilityfromnrcommand target cell not prepared n78
```

**Show:** causes → checks → 3GPP refs + agent trace (`fault_analysis`).

**Say:** “NOC/L1 gets a checklist in 30 seconds; with scrubbed UE logs we add pattern-based phase ID.”

---

### Minute 11–14 — Repeatable test: Attach Report

1. Click **📋 Attach Report** → upload sample log  
2. Show PASS/FAIL steps

**Say:** “This is **Path B** — rule-based, auditable. Same checklist for regression on XYZ NR SA campaigns.”

---

### Minute 14–18 — Close: pilot ask for XYZ

**Propose:**

| Phase | What | Who |
|-------|------|-----|
| **2 weeks** | 20 scrubbed HO/RACH + drive-test CSVs from XYZ trials | Field + you |
| **4 weeks** | Coverage optimizer tuned to XYZ column exports (TEMS/Nemo/scanner) | You + dev |
| **8 weeks** | Private deploy or VPC Render; no raw IMSI in cloud | IT + security |

**Ask:** “Approve a **pilot squad**: me (domain), one backend dev slot, one security review for anonymized log workflow.”

---

## What your MANAGER should know

### Business value (XYZ)

| Pain | TelecomGPT answer |
|------|-------------------|
| Tribal knowledge in senior engineers | Playbooks in JSON + agents |
| Slow log/CSV triage in field | Upload → instant report |
| Inconsistent RCA write-ups | Same structure every ticket |
| Generic ChatGPT wrong on 3GPP | Domain KB + RAG + tools |

### Honest limits (credibility)

- Not replacing OSS, QCAT, or full ASN.1 decode  
- Cloud demo uses **anonymized** logs/CSV — XYZ production needs scrub pipeline or private host  
- Chat history not persisted on refresh yet  
- Accuracy = rules + data quality — needs XYZ samples to tune  

### Cost / ownership

- **Run cost:** Vercel + Render + OpenAI API (hybrid engine limits LLM calls)  
- **Owner:** RF/test team owns **reference JSON + patterns**; engineering owns **agents/API**  
- **No model training required** — extend with data + Python modules  

---

## What your TEAM should know (developing resourceful agents)

### 1. Architecture in one picture

```
UI (Vercel) → API (Render) → Planner → LangGraph → Agents → Tools → KB / CSV / RAG
```

- **Agent** = job title (fault_analysis, coverage_optimizer)  
- **Tool** = instrument (evaluate_rf_kpis, optimize_coverage)  
- **Path A** = multi-agent chat  
- **Path B** = deterministic reports (attach, UE cap)  
- **Path C** = instant math (link budget, coverage rank) — **fast, no LLM**

### 2. How to add an agent (repeatable pattern)

| Step | File | Example |
|------|------|---------|
| 1 | `backend/data/*.json` | fault_catalog, thresholds |
| 2 | `backend/analytics/<feature>.py` | coverage_optimizer.py |
| 3 | `agents/test_engineer.py` or `extended.py` | wire handler |
| 4 | `planning.py` | keywords → agent |
| 5 | `tools.py` | register tool |
| 6 | `test_<feature>.py` | no OpenAI needed |

**Team contribution:** domain engineers write **JSON playbooks + log patterns**; devs wire **agents**.

### 3. Data rules for XYZ (mandatory)

| Rule | Why |
|------|-----|
| Scrub IMSI/IMEI/site names **on-prem** | Privacy / compliance |
| Upload `.txt` / `.csv` only (not PCAP) | Today’s parser scope |
| Use `scrub_log.sh` + manual review | Regex not enough alone |
| Keep PCI/ARFCN/RSRP — drop subscriber ID | Still debuggable |

### 4. Who does what on the squad

| Role | Responsibility |
|------|----------------|
| **You (Senior field test)** | Prompts, sample logs, acceptance criteria, pilot sites |
| **RF lead** | Thresholds (RSRP/SINR SLA), band priorities (n78/n41) |
| **Backend dev** | Agents, API, deploy, tests |
| **Security** | Anonymization policy, private deploy decision |
| **NOC/L2** | Alarm → prompt library for triage |

### 5. Files the team should bookmark

| Doc | Purpose |
|-----|---------|
| `docs/ARCHITECTURE.md` | System map |
| `docs/DEMO_MANAGER.md` | Short manager demo |
| `docs/DEMO_HANDOVER_OPERATOR.md` | HO/RACH + privacy |
| `docs/LEARNING_SYLLABUS.md` | 12-week upskill path |
| `backend/telecom_ai/agents/taxonomy.py` | All 23 agents |

---

## Suggested prompts for XYZ (copy-paste)

```
Coverage optimizer 32.93704401921274, -96.98407174060758 3 mile radius best UE locations
Explain SINR vs RSRQ link budget
Fault analysis RRC setup fail HARQ K1
Handover failure mobilityfromnrcommand n78
Validate NR SA registration test case
What is n78?
RF KPI assessment
```

---

## If something breaks live

| Issue | Fallback |
|-------|----------|
| Render cold start | “Waking up — 30s” — retry |
| Coverage optimizer not on prod | Show API/local or explain PR #1 merge |
| No CSV | Use bundled `coverage_dallas_3mi.csv` |
| Chart chip fails | Skip — needs Kaggle on server |

---

## One paragraph for your manager email (tonight)

> Tomorrow I’ll demo TelecomGPT for XYZ field test: a **coverage optimizer** that ranks best UE locations within a 3-mile radius from drive-test data, **instant link-budget** calculations, and **structured HO/RRC fault triage** with agent traceability. It’s deployed as a web app with deterministic checklists for attach validation. I’m proposing a 2-week pilot with anonymized logs from our trials to tune agents for the team — not replacing OSS, but cutting triage time and capturing senior engineer playbooks.

---

## Your positioning as Senior 5G Test Engineer

You are not “building ChatGPT.” You are:

1. **Domain owner** — XYZ procedures, KPIs, log patterns  
2. **Pilot lead** — real field data → agent quality  
3. **Bridge** — RAN reality ↔ AI architecture  

That’s the story that gets manager buy-in and makes agents **resourceful for the whole team**.
