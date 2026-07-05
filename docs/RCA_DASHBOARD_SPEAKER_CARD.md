# TNIC RCA Dashboard — One-Page Speaker Card

**URL:** `http://localhost:8501` (or forwarded port) · **Duration:** 18 min · **Focus cell:** XYZ401

---

## OPEN (30 sec)

> *"XYZ Telecom Network Intelligence — 13 rule-based specialist agents on real telecom CSV datasets. Not generic chat: auditable RCA across mobility, RF, and access. Sidebar = domain agents; RCA Report = Master Orchestrator."*

Set sidebar **Focus cell → XYZ401**

---

## ACT 1 · Executive Summary — 3 min

| Show | Say |
|------|-----|
| 10 cells, avg health **~53/100** | "Stressed Dallas SITE01 cluster — all Grade C/D" |
| Worst cell **XYZ407** | "NOC prioritization in one glance" |
| Health table + bar chart | "HO ~89%, RLF high, drops high — mobility crisis" |
| Focus cell XYZ401 metrics | "We'll deep-dive this cell — worst mobility story" |

---

## ACT 2 · Domain Pages — 6 min (XYZ401)

| Page | 1-line script |
|------|---------------|
| **Handover** | "89% HO success — prep fail, Xn, ping-pong rules fire" |
| **RLF** | "RLF driven by coverage at cell edge, not random" |
| **Call Drops** | "Mobility drops follow same RF weakness" |
| **RACH** | "Access failures at edge — correlated symptom" |
| **Beamforming** | "Secondary: beam congestion on hot SSB beams" |

> *"Each page = one specialist agent. Threshold rules, confidence scores, field actions."*

---

## ACT 3 · RF Coverage — 3 min ⭐

| Show | Numbers |
|------|---------|
| RSRP + SINR heatmaps | Geospatial proof |
| Coverage Hole Map | Red clusters at edge |
| Score / issues | **52** · Coverage Deficiency · Beam Congestion · **94%** conf |

> *"Drive-test data confirms PM suspicion — coverage holes in 3-mile cluster."*

---

## ACT 4 · RCA Report — 4 min ⭐⭐ CLIMAX

1. Cell: **XYZ401**
2. Preset: **Unified coverage RCA**
3. ✅ Generate narrative report → **Run Master RCA**

| Result | Say |
|--------|-----|
| 8 agents run | rf_coverage → rlf → ho → call_drop → rach → tp → beam → complaint |
| Root cause | Coverage deficiency → HO / RLF / drops / RACH cascade |
| Recommendations | Retilt, fill holes, rebalance beams, re-drive cluster |

> *"One click = multi-agent RCA with evidence, confidence, and actions — API-ready JSON."*

---

## CLOSE (30 sec)

> *"Cluster overview → domain agents → geospatial proof → unified RCA in 18 minutes. Same engine via REST API for OSS integration. Pilot next: one live cluster PM export."*

---

## Cell Quick Reference

| Cell | Use |
|------|-----|
| **XYZ401** | Primary demo — coverage RCA (score 52, 94%) |
| **XYZ407** | Worst in cluster (50.9) — exec summary |
| **XYZ409** | Contrast — healthier (~55) |

---

## If Asked…

| Question | Answer |
|----------|--------|
| Is this AI? | Rule-based diagnosis; optional AI narrative. Datasets + rules = source of truth. |
| Data real? | Demo CSVs — pm_counters, HO, RLF, RACH, drops, throughput, geospatial RF. |
| API? | `POST /api/v1/analyze-cell` · `POST /api/v1/analyze/rca` · port 8000/docs |

---

## 5-Min Executive Cut

**Summary (1 min) → RF Coverage XYZ401 (2 min) → RCA Report unified preset (2 min)**
