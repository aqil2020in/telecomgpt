# Cursor Training Guide — Concepts, Tutorials & Best Practices

**Audience:** Developers and technical leads using this monorepo  
**Repo:** [telecomgpt](https://github.com/aqil2020in/telecomgpt)  
**Related:** [AGENTS.md](../AGENTS.md) · [LEARNING_SYLLABUS.md](./LEARNING_SYLLABUS.md) · [DEMO_TNIC_LOCAL_MANAGER.md](./DEMO_TNIC_LOCAL_MANAGER.md)

---

## Who this guide is for

| Section | Best for |
|---------|----------|
| **Part 1–3** | Developers learning Cursor day-to-day |
| **Part 4** | Team leads running a half-day workshop |
| **Part 5** | Managers who demo TNIC without coding |
| **Part 6–7** | Everyone — prompt templates and cheat sheet |

**Mental model:** Cursor amplifies your engineering judgment. Treat AI output as a **first draft**, not finished production code.

---

## Part 1 — Core concepts

### What Cursor is

Cursor is a **VS Code–based IDE with AI built in at the core** — not a plugin on top of a normal editor.

| Concept | What it means |
|---------|----------------|
| **Tab completion** | Inline autocomplete that predicts multi-line edits |
| **Inline Edit** (`Cmd/Ctrl+K`) | Change the selected code block from a short prompt |
| **Chat** (`Cmd/Ctrl+L`) | Ask questions; explain or debug with optional light edits |
| **Agent / Composer** | Multi-file changes from a natural-language goal |
| **Codebase index** | Cursor indexes your repo for semantic search (`@codebase`) |
| **Rules** | Persistent project instructions injected into every AI session |
| **MCP** | Connect AI to external tools (Notion, Figma, databases, APIs) |
| **Cloud Agents** | Background tasks (lint fixes, PRs) while you work on something else |

### Learn modes in this order

```
Tab  →  Inline Edit  →  Chat  →  Agent
(fast)    (one file)     (understand)   (multi-file)
```

| Mode | When to use | Risk |
|------|-------------|------|
| Tab | Daily coding, small completions | Low |
| Inline Edit | Refactor one function or file | Low–medium |
| Chat | Explain architecture, debug, plan | Low |
| Agent | Features spanning multiple files | Medium–high |

**Training rule:** Start with Tab for your first week. Add Agent only after you are comfortable reviewing diffs line-by-line.

### Context symbols (`@` mentions)

| Symbol | Purpose |
|--------|---------|
| `@file` | One specific file |
| `@folder` | Directory scope |
| `@codebase` | Semantic search across the repo |
| `@docs` | Official framework/library documentation |
| `@web` | Live web search |
| `@git` | Recent commits, branches, diffs |

**Bad prompt:** “Fix the handover bug.”

**Good prompt (this repo):**
```
In xyz_tnic/tnic/datasets/kpi_service.py, HO success rate for XYZ401 looks wrong.
Trace from load_handover_events_enriched() through _kpis_from_handover()
and fix the rate calculation. Minimal diff only.
```

### Rules — training the AI for your project

Rules are **persistent instructions** the agent follows every session.

| Location | Scope |
|----------|--------|
| **User Rules** (Cursor Settings) | Personal preferences across all projects |
| **Project Rules** (`.cursor/rules/` or `AGENTS.md`) | This repo’s architecture, ports, conventions |
| **Legacy `.cursorrules`** | Still works; `.cursor/rules/` is preferred |

This repo already ships **`AGENTS.md`** with:
- Product ports (TelecomGPT 8000/3000, TNIC 8010/8502)
- Virtualenv paths (`/workspace/.venv/bin/python`)
- Local demo command (`./scripts/demo_tnic_local.sh`)
- Non-obvious caveats (Render vs local, Chroma, OpenAI optional)

**Strong rules specify:**
- Stack (Python 3.12, Streamlit, FastAPI — not alternatives)
- Folder layout (`backend/`, `xyz_tnic/`, `datasets/`)
- Patterns to use **and** avoid
- How to run tests and demos
- Security (no secrets in prompts; use `.env`)

### Agent workflow: Plan → Execute → Verify

1. **Plan** — Ask for approach before code (*“Do not edit yet — outline steps.”*)
2. **Scope** — One feature or bug per session
3. **Execute** — Agent implements with rules + `@file` context
4. **Review** — Read every diff line
5. **Verify** — Run tests, lint, smoke demo
6. **Commit** — Small, descriptive commits

---

## Part 2 — Hands-on tutorials (4-week path)

### Week 1 — Foundations

**Day 1–2: Setup**
1. Install from [cursor.com](https://cursor.com)
2. Enable **Codebase Indexing** (Cursor Settings → Features)
3. Import VS Code extensions/keybindings if migrating
4. Enable **Privacy Mode** for proprietary or client code

**Day 3: Tab & Inline Edit**
- Open `xyz_tnic/tnic/datasets/kpi_service.py`
- Type a function signature; accept Tab suggestions
- Select a block → Inline Edit → *“Add a one-line docstring”*

**Day 4: Chat with context**
```
@file xyz_tnic/tnic/datasets/kpi_service.py
Explain how compute_cell_kpis merges handover and RLF data.
List the CSV sources in order.
```

**Day 5: First Agent task (small)**
```
Add a log line to scripts/demo_tnic_local.sh when the smoke test passes.
Do not change anything else.
```

---

### Week 2 — Project-aware work (TelecomGPT repo)

**Tutorial A — Debug with Chat**
```
@codebase Where is TNIC_DATASETS_DIR resolved?
Which dashboard pages depend on it?
```

**Tutorial B — Scoped doc update**
```
@file xyz_tnic/dashboard/pages/8_RCA_Report.py
@file docs/DEMO_TNIC_LOCAL_MANAGER.md

Add one sentence about the "Upload telecom_issues.csv" data source.
Match existing doc tone. Minimal diff only.
```

**Tutorial C — Write a project rule**

Create `.cursor/rules/tnic-demo.mdc`:
```markdown
---
description: TNIC local demo conventions
globs: xyz_tnic/**, scripts/demo_tnic_local.sh, docs/DEMO*
---

- Local demo: ./scripts/demo_tnic_local.sh → http://localhost:8502
- Demo cells: XYZ401–XYZ410 (preloaded in datasets/)
- Core RCA needs no Render and no OpenAI
- KPI source: datasets/ via TNIC_DATASETS_DIR
- Unified upload format: datasets/telecom_issues.csv (issue_domain column)
```

---

### Week 3 — Agent + verification

**Tutorial D — Feature with tests**
```
Goal: Validate telecom_issues.csv has required columns before ingest.

1. Plan the change (files, tests) — do not edit yet
2. Implement in xyz_tnic/tnic/datasets/telecom_issues.py
3. Add or extend xyz_tnic/tests/test_telecom_issues.py
4. Run: cd xyz_tnic && python -m pytest tests/test_telecom_issues.py -q
```

**Tutorial E — Cloud Agent (optional)**
- Open **Cloud Agents** in Cursor
- Task: *“Fix failing test in xyz_tnic/tests/”*
- Review PR/diff before merge

---

### Week 4 — Team workflows & MCP

**Tutorial F — MCP (if configured)**
- Connect Notion / Figma / internal APIs via MCP in Cursor Settings
- Example: *“Search Notion for TNIC roadmap tasks.”*

**Tutorial G — Manager demo script**
```
@file docs/DEMO_TNIC_LOCAL_MANAGER.md
@file docs/ARCHITECTURE.md

Write a 5-minute spoken script for a non-technical manager.
Cover: what runs locally vs Render, Handover → RCA Report flow,
and the telecom_issues.csv upload option.
Plain language, no jargon.
```

---

## Part 3 — Best practices (production-grade)

### 1. Rules before large Agent runs
Ensure `AGENTS.md` or `.cursor/rules/` covers stack, layout, and constraints. Highest-leverage training step for any team.

### 2. Narrow prompts beat vague ones

| Avoid | Prefer |
|-------|--------|
| “Make the dashboard better” | “On Handover page, sort HO findings by confidence descending” |
| “Fix all bugs” | “Fix TypeError in kpi_service when rsrp is string dtype” |
| “Refactor everything” | “Extract upload helpers from dashboard_utils into upload_service.py” |

### 3. Plan before multi-file Agent work
For 3+ files:
> *“Plan only — list files, risks, and test plan. Wait for my approval.”*

### 4. Review diffs, not summaries
Never merge because the agent *said* it worked. Read the diff; run tests yourself.

### 5. Use `.cursorignore`
Exclude noise and secrets from the index:
```
.env*
*.log
dist/
coverage/
node_modules/
xyz_tnic/data/uploads/
*.lock
datasets/telecom_issues.csv
```
(Omit the last line if you want the agent to reference the full unified CSV.)

### 6. Commit often during Agent sessions
Each logical step → one commit. Git history is your rollback path.

### 7. Chat to diagnose, Agent to fix
- **Chat:** *“Why would HO success rate be None for XYZ401?”*
- **Agent:** *“Implement the fix in _kpis_from_handover only.”*

### 8. One concern per session
Do not mix “add auth + refactor KPI service + update docs” in one Agent run.

### 9. Tests as guardrails
```
@test_telecom_issues.py must pass after this change.
Do not weaken assertions.
```

### 10. Know when to code manually
- Security-sensitive auth/crypto
- Subtle business logic not yet validated
- Two-line fixes (often faster by hand)

### 11. Privacy & security
- **Privacy Mode** for company code
- Never paste API keys, passwords, or customer PII into chat
- Keep “ask before run” enabled for destructive shell commands on production repos

### 12. Model selection (practical defaults)

| Task | Model tier |
|------|------------|
| Daily Tab / small edits | Fast model |
| Architecture, large refactors | Higher-reasoning model |
| Documentation, explanations | Fast model is usually enough |

---

## Part 4 — Half-day team workshop

| Block | Duration | Activity |
|-------|----------|----------|
| **Concepts** | 30 min | Modes, context, rules, index |
| **Live demo** | 45 min | Tab → Chat → Agent on this repo |
| **Hands-on** | 60 min | Each person: one Chat query + one scoped Agent task |
| **Rules lab** | 45 min | Draft or extend `.cursor/rules/` for the monorepo |
| **Safety** | 30 min | Diff review, `.cursorignore`, Privacy Mode |
| **Wrap-up** | 30 min | Team agreement: when to use Agent vs manual |

**Workshop exercise (this repo):**
1. Run `./scripts/demo_tnic_local.sh`
2. Chat: explain KPI service flow (`@file kpi_service.py`)
3. Agent: add one FAQ bullet to `docs/DEMO_TNIC_LOCAL_MANAGER.md`
4. Review diff as a group before accepting

---

## Part 5 — Manager track (no coding required)

Managers can use Cursor to **prepare demos and documentation**, not to ship code.

### What managers should use

| Tool | Use for |
|------|---------|
| **Chat** | Explain architecture, draft talking points |
| **Agent (read-only / docs only)** | Update handouts, demo scripts, FAQs |
| **Cloud Agents** | Optional — ask an agent to draft docs in a PR for review |

### What managers should avoid
- Accepting code diffs without a developer review
- Pasting production credentials into chat
- Large Agent refactors on `main` without a feature branch

### 15-minute manager exercise

1. Open **Chat**
2. Paste:
   ```
   @file docs/DEMO_TNIC_LOCAL_MANAGER.md
   @file docs/RCA_MANAGER_EXPLAINER.md

   I have a 10-minute meeting with my director.
   Give me: (1) opening one-liner, (2) three demo steps,
   (3) two FAQ answers about Render vs local.
   ```
3. Practice the demo locally:
   ```bash
   ./scripts/demo_tnic_local.sh
   ```
4. Open http://localhost:8502 → Handover → XYZ401 → RCA Report

### Manager cheat sheet

> “TNIC RCA runs on my laptop — preloaded CSVs, Python KPI calculation, rule-based agents. No Render, no OpenAI required for core diagnosis. Same logic as production; different deployment mode.”

Full demo script: [DEMO_TNIC_LOCAL_MANAGER.md](./DEMO_TNIC_LOCAL_MANAGER.md)

---

## Part 6 — Prompt templates (copy-paste)

### Understand code
```
@codebase [topic]
Explain architecture in 5 bullets.
List the 3 most important files and why.
```

### Safe refactor
```
@file [path]
Refactor [function] only.
Preserve behavior. Add/update tests.
Minimal diff — no drive-by changes.
```

### Debug
```
Error: [paste error]
@file [suspect file]
Root cause + smallest fix. Explain before editing.
```

### Demo / docs (manager-friendly)
```
@file docs/[doc].md
Write a manager-friendly 5-min demo script.
Plain language, no jargon. Include exact shell commands.
```

### Plan mode (before big changes)
```
Do NOT edit files yet.
Goal: [describe feature]
Return: files to change, steps, risks, test plan.
```

### Repo-specific examples

**KPI flow:**
```
@file xyz_tnic/tnic/datasets/kpi_service.py
@file xyz_tnic/tnic/datasets/loaders.py
Draw the data flow from datasets/*.csv to compute_cell_kpis("XYZ401").
```

**Upload RCA:**
```
@file xyz_tnic/tnic/datasets/telecom_issues.py
@file xyz_tnic/dashboard/pages/8_RCA_Report.py
Explain how uploading telecom_issues.csv leads to key issue detection and Master RCA.
```

---

## Part 7 — Common mistakes

| Mistake | Fix |
|---------|-----|
| Vague prompts | Add file paths, expected behavior, constraints |
| No project rules | Maintain `AGENTS.md` or `.cursor/rules/` |
| Accepting large diffs unread | Review line-by-line; reject unrelated changes |
| Huge Agent tasks | Split: plan → implement → test |
| Stale index | Command palette → **Cursor: Rebuild Index** after major restructures |
| No verification | Run `pytest`, smoke demo after Agent work |
| Secrets in chat | Use env vars; `.env*` in `.cursorignore` |

---

## Part 8 — Official resources

| Resource | URL |
|----------|-----|
| Cursor Docs | https://docs.cursor.com |
| Cursor Learn | https://cursor.com/learn |
| Rules | https://docs.cursor.com/context/rules |
| Agent overview | https://docs.cursor.com/agent/overview |
| MCP | https://docs.cursor.com/context/mcp |
| Changelog | https://cursor.com/changelog |

---

## One-page cheat sheet

```
LEARN ORDER:     Tab → Inline Edit → Chat → Agent
CONTEXT:         @file  @folder  @codebase  @docs
BIG WORKFLOW:    Plan → Rules → Scope → Execute → Review → Test → Commit
THIS REPO:       AGENTS.md (ports, venv, demo commands)
LOCAL TNIC DEMO: ./scripts/demo_tnic_local.sh  →  http://localhost:8502
UNIFIED CSV:     datasets/telecom_issues.csv  →  RCA Report upload
SECURITY:        Privacy Mode · .cursorignore · no secrets in chat
TEAM RULE:       Never merge AI code you don't understand
```

---

## How this fits the rest of the repo

| Doc | Focus |
|-----|--------|
| [LEARNING_SYLLABUS.md](./LEARNING_SYLLABUS.md) | 12-week 5G RAN → AI curriculum on this codebase |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, local vs Render |
| [DEMO_TNIC_LOCAL_MANAGER.md](./DEMO_TNIC_LOCAL_MANAGER.md) | 5-min manager demo (no Render) |
| [RCA_MANAGER_EXPLAINER.md](./RCA_MANAGER_EXPLAINER.md) | How RCA agents and KPI service work |
| [AGENTS.md](../AGENTS.md) | Cursor Cloud / agent instructions for this monorepo |

---

*Last updated: July 2026 · TelecomGPT monorepo*
