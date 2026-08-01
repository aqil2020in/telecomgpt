# Cursor Reference — Rules, Commands, Tools, Skills & Models

**Audience:** Developers, leads, and managers using Cursor with this monorepo  
**Repo:** [telecomgpt](https://github.com/aqil2020in/telecomgpt)  
**Related:** [CURSOR_TRAINING.md](./CURSOR_TRAINING.md) · [AGENTS.md](../AGENTS.md) · [DEMO_TNIC_LOCAL_MANAGER.md](./DEMO_TNIC_LOCAL_MANAGER.md)

One-page operating guide. For tutorials and workshops, see [CURSOR_TRAINING.md](./CURSOR_TRAINING.md).

---

## 1. Mental model

| Layer | What it is | When it applies |
|-------|------------|-----------------|
| **Rules** | Persistent instructions injected into every AI session | Always on |
| **Commands** | Reusable prompts or shell shortcuts you trigger on demand | When you start a workflow |
| **Tools** | Things the agent can call (terminal, MCP, browser, git) | During Agent / Cloud Agent runs |
| **Skills** | Packaged playbooks (`SKILL.md`) that tell the agent how to use specific tools | When a task matches the skill trigger |
| **Models** | Reasoning depth vs speed tradeoff | Per task / per session |

**Golden rule:** Cursor amplifies judgment — treat AI output as a **first draft**. Plan → execute → **read the diff** → verify → commit.

---

## 2. Rules — best practices

### Where rules live

| Location | Scope | Use for |
|----------|-------|---------|
| **User Rules** (Cursor Settings) | All projects | Tone, review habits, security prefs |
| **Project Rules** (`.cursor/rules/*.mdc`) | This repo, scoped by `globs` | Stack, patterns, file-specific conventions |
| **`AGENTS.md`** (repo root) | Cloud Agents + monorepo | Ports, venv paths, demo commands, caveats |
| **Legacy `.cursorrules`** | Project | Still works; prefer `.cursor/rules/` |

### What good rules contain

- **Stack** — Python 3.12, FastAPI, Streamlit (not alternatives)
- **Layout** — `backend/`, `xyz_tnic/`, `datasets/`
- **Run commands** — exact shell one-liners
- **Constraints** — minimal diff, no drive-by refactors, no secrets in chat
- **Verification** — how to test (`pytest`, `./start.demo`)

### Rules for this repo (see `AGENTS.md`)

| Service | Port | Command |
|---------|------|---------|
| TelecomGPT API | 8000 | `cd backend && .venv/bin/uvicorn app:app --port 8000` |
| TNIC RCA API | 8010 | `cd xyz_tnic && .venv/bin/uvicorn tnic.main:app --port 8010` |
| TNIC dashboard | 8502 | `./start.demo` |
| Local demo (fast) | — | `./start.demo --no-install` |

### Rule anti-patterns

| Avoid | Do instead |
|-------|------------|
| Vague “write clean code” | “Match `kpi_service.py` patterns; minimal diff only” |
| 500-line rule files | Split into scoped `.mdc` files with `globs` |
| Duplicating docs | Rules = *how to work*; docs = *what the system is* |
| Secrets in rules | Point to `.env`; add `.env*` to `.cursorignore` |

### Example scoped rule

```markdown
---
description: TNIC local demo conventions
globs: xyz_tnic/**, start.demo, scripts/demo_tnic_local.sh, docs/DEMO*
---

- Demo: ./start.demo → http://localhost:8502
- Cloud Agent: use Cursor Browser, not PC localhost
- Cells: XYZ401–XYZ410 in datasets/
- No Render, no OpenAI for core RCA demo
- Upload CSV: datasets/telecom_issues.csv
```

---

## 3. Commands — best practices

“Commands” means two things in practice:

### A. Repo commands (shell)

| Command | Purpose |
|---------|---------|
| `./start.demo` | Start TNIC RCA + open browser |
| `./start.demo --no-install` | Fast repeat demo |
| `./scripts/demo_tnic_local.sh` | Same engine; pass `--open` to auto-open browser |
| `cd xyz_tnic && python -m pytest` | TNIC test suite |

**Best practice:** One memorable entry point (`./start.demo`) at repo root; keep implementation in `scripts/`.

### B. Cursor custom / slash commands

Use for **repeatable AI workflows**, not one-off questions.

| Good command | Bad command |
|--------------|-------------|
| “Plan-only RCA bug fix” | “Fix bugs” |
| “Update manager demo doc from diff” | “Make docs better” |
| “Run pytest + summarize failures” | “Test everything” |

**Template for a custom command:**

```
Goal: [single outcome]
Context: @file [paths]
Constraints: minimal diff, no unrelated files
Steps: plan → implement → run [test command] → report
Do NOT edit until plan is approved (if large change).
```

---

## 4. Tools — best practices

### Built-in agent tools

| Tool | Use when | Caution |
|------|----------|---------|
| **Terminal** | Run tests, start servers, git | Keep “ask before run” on prod repos |
| **Read / Grep / Search** | Understand code before editing | Prefer `@file` for known paths |
| **Browser** | Verify Streamlit UI on Cloud Agent | PC browser ≠ Cloud VM localhost |
| **Git / PR** | Cloud Agent branches and PRs | Review every diff before merge |

### MCP tools (Notion, Figma, Datadog, etc.)

| Practice | Why |
|----------|-----|
| Discover schema before calling | Avoid failed tool calls |
| Use MCP for external systems | Not for local file edits |
| Authenticate once in desktop IDE | Cloud Agent may need re-auth |
| Prefer MCP over browser scraping | More reliable, structured |

### `.cursorignore` (tool/index hygiene)

```
.env*
node_modules/
dist/
coverage/
xyz_tnic/data/uploads/
*.log
```

Exclude noise and secrets so search and Agent context stay high-signal.

---

## 5. Skills — best practices

**Skills** are plugin-provided `SKILL.md` playbooks (Notion search, Figma design, Datadog setup, etc.).

| Principle | Detail |
|-----------|--------|
| **Agent reads skill when triggered** | Description in frontmatter must match user intent |
| **Skills ≠ runtime code** | TNIC dashboard does not use Cursor Skills at runtime |
| **Follow skill workflow exactly** | e.g. load `figma-use` before `use_figma` |
| **Don't improvise when a skill exists** | Skills encode failure-prone sequences |

### Skill structure (typical)

```markdown
---
name: search
description: When to trigger this skill (be specific)
---

# Title
Step-by-step behavior, tool names, output format.
```

### When to create a team skill vs a rule

| Use a **rule** | Use a **skill** |
|----------------|-----------------|
| Repo conventions, ports, test commands | Multi-step external tool workflow |
| Always-on project context | Task triggered occasionally |
| Short, static constraints | Long procedural playbook |

---

## 6. Model selection — best practices

| Task | Model tier | Examples |
|------|------------|----------|
| Tab completion, typos, docstrings | **Fast** | Daily coding |
| Explain architecture, debug with Chat | **Fast** (usually enough) | `@file kpi_service.py` |
| Multi-file features, subtle bugs | **Higher reasoning** | KPI pipeline, upload ingest |
| Large refactors, system design | **Higher reasoning** | New agent specialist |
| Documentation, manager scripts | **Fast** | `DEMO_TNIC_LOCAL_MANAGER.md` |
| Cloud Agent autonomous PRs | **Higher reasoning** | Feature branches, tests |

### Practical rules

1. **Start fast** — escalate only if the agent loops or misses constraints.
2. **Match model to blast radius** — higher reasoning for 3+ files or production paths.
3. **Same task, same model** — avoids inconsistent style mid-PR.
4. **Managers** — Chat + fast model; avoid large Agent refactors on `main`.

---

## 7. Workflow cheat sheet

```
LEARN ORDER:     Tab → Inline Edit → Chat → Agent
CONTEXT:         @file  @folder  @codebase  @docs
BIG WORKFLOW:    Plan → Rules → Scope → Execute → Review → Test → Commit
THIS REPO:       AGENTS.md + ./start.demo
CLOUD AGENT:     Cursor Browser for localhost apps
SECURITY:        Privacy Mode · .cursorignore · no secrets in chat
TEAM RULE:       Never merge AI code you don't understand
```

### Prompt quality

| Weak | Strong |
|------|--------|
| “Fix handover bug” | “In `kpi_service.py`, HO rate for XYZ401 wrong — trace `load_handover_events_enriched()` → `_kpis_from_handover()`, minimal diff” |
| “Improve dashboard” | “On Handover page, sort findings by confidence descending only” |
| “Refactor everything” | “Extract upload helpers from `dashboard_utils.py`; add tests; no behavior change” |

### Mode selection

| Mode | When | Risk |
|------|------|------|
| **Tab** | Daily edits | Low |
| **Inline Edit** | One function/file | Low–medium |
| **Chat** | Understand, plan, debug | Low |
| **Agent** | Multi-file features | Medium–high |
| **Cloud Agent** | Background PRs, demos on VM | Medium (review PR) |

---

## 8. Official references

| Resource | URL |
|----------|-----|
| Cursor Docs | https://docs.cursor.com |
| Cursor Learn | https://cursor.com/learn |
| Rules | https://docs.cursor.com/context/rules |
| Agent | https://docs.cursor.com/agent/overview |
| MCP | https://docs.cursor.com/context/mcp |
| Changelog | https://cursor.com/changelog |

---

## 9. This repo — doc map

| Doc | Purpose |
|-----|---------|
| [CURSOR_REFERENCE.md](./CURSOR_REFERENCE.md) | This note — rules, commands, tools, skills, models |
| [CURSOR_TRAINING.md](./CURSOR_TRAINING.md) | Full 4-week tutorials + workshop |
| [AGENTS.md](../AGENTS.md) | Cloud Agent + ports + `./start.demo` |
| [DEMO_TNIC_LOCAL_MANAGER.md](./DEMO_TNIC_LOCAL_MANAGER.md) | 5-min manager demo |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Local vs Render |
| [RCA_MANAGER_EXPLAINER.md](./RCA_MANAGER_EXPLAINER.md) | KPI + RCA agent flow |

---

## 10. Quick start for your team

**Developers**

1. Read `AGENTS.md` once
2. Add `.cursor/rules/tnic-demo.mdc` (scoped globs)
3. Use Chat with `@file` before Agent on unfamiliar code
4. Verify with `pytest` or `./start.demo --no-install`

**Managers**

1. `./start.demo` (or Cursor Browser on Cloud Agent)
2. Chat only: `@file docs/DEMO_TNIC_LOCAL_MANAGER.md`
3. Do not merge code PRs without dev review

---

*Last updated: July 2026 · TelecomGPT monorepo*
