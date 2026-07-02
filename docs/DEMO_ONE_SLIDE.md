# TelecomGPT — XYZ Field Test Pilot (1 slide)

**Presenter:** Senior 5G Test Engineer · **Audience:** Manager + RF/test team · **Time:** 15–20 min

---

## Slide title
**TelecomGPT — AI assistants for XYZ 5G field & lab test**

---

## Six bullets (paste into PowerPoint)

1. **Problem** — Field engineers lose hours on drive-test CSVs, attach/HO/RACH logs, and scattered 3GPP references; generic ChatGPT lacks XYZ workflows and auditable checklists.

2. **Solution** — TelecomGPT: **23 specialist agents** (coverage, RF KPI, fault, attach) + structured KB/RAG + **deterministic tools** — deployed web app with **agent trace** on every answer.

3. **Live demo** — (a) **Coverage optimizer** — best UE locations in **3 mi** around site `32.937, -96.984` from CSV; (b) **instant link budget**; (c) **HO/RACH fault** + **Attach PASS/FAIL** report.

4. **XYZ value** — Faster triage, consistent RCA write-ups, ranked retest coordinates, junior engineer training — **senior playbooks encoded**, not lost when people rotate.

5. **Data & trust** — Anonymize logs/CSV on-prem (no IMSI in cloud); rule-based reports + sourced chat; **not** OSS/QCAT replacement — **assisted engineering**.

6. **Ask** — **2-week pilot**: 20 scrubbed trial logs/CSVs · squad = field (me) + 1 dev + security review · success = measured reduction in triage time.

---

## Speaker notes (footer, optional)

- Open: https://telecomgpt.vercel.app · enable **Show agent trace**
- Files: `coverage_dallas_3mi.csv`, `ho_demo_anonymized.log`
- Branch PR #1 for optimizer + link budget (or run local script tonight)
