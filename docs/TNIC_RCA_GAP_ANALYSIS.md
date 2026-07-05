# TNIC RCA Gap Analysis Report

**Reference:** [Detailed RCA workflows for major 4G/5G network issues](https://pradeep-dhote9.medium.com/detailed-rca-workflows-for-major-4g-5g-network-issues-a86ea3a72561) (Pradeep Dhote, Dec 2025)

**TNIC version:** post-industry-workflow implementation  
**Date:** 2026-07-05

---

## Executive summary

| Metric | Before | After this implementation |
|--------|--------|---------------------------|
| Specialist agents | 13 | **18** (+ VoNR, ANR, Config Audit, gNB Syslog, Alarm) |
| Rule engines | 8 | **17** |
| Industry workflows covered | ~5 partial | **8 mapped** in `workflow_registry.py` |
| RCA catalog types | 0 | **28** in `rca_catalog.py` |
| Syslog signatures | 0 | **11** |
| Config validations | PM only | **10 golden parameters** |
| Master RCA enrichment | Coverage only | Catalog + workflow + coverage + syslog |

---

## 28-Type RCA Catalog (complete)

All types registered in `tnic/orchestrator/rca_catalog.py`:

| # | RCA Type | Primary Agent | Key Rules |
|---|----------|---------------|-----------|
| 1 | Coverage Hole | rf_coverage | cov_coverage_hole, rlf_coverage_hole |
| 2 | Overshooting Cell | rf_coverage | cov_overshooting, ho_too_early |
| 3 | Pilot Pollution | rf_coverage | cov_pilot_pollution, anr_pci_conflict |
| 4 | Interference | rf_coverage | cov_interference, rlf_interference |
| 5 | HO Prep Failure | handover | ho_prep_failure, ho_missing_neighbor |
| 6 | HO Execution Failure | handover | ho_execution_failure, rlf_after_ho |
| 7 | Ping Pong HO | handover | ho_ping_pong |
| 8 | Too Early HO | handover | ho_too_early, cov_overshooting |
| 9 | Too Late HO | handover | ho_too_late, rlf_coverage_hole |
| 10 | RLF | rlf | rlf_coverage_hole, rlf_interference, rlf_t310_n310 |
| 11 | RRC Setup Failure | rach | rach_rrc_setup_fail, core_ng_n2_failure |
| 12 | RACH Failure | rach | rach_msg1_fail, rach_low_success |
| 13 | VoNR Drop | vonr | vonr_drop, drop_ims |
| 14 | PDU Session Failure | core | core_pdu_session_fail |
| 15 | Beam Failure | beamforming | beam_failure, beam_instability |
| 16 | Low Throughput | throughput | tput_low_cqi_bler, tput_low_mcs |
| 17 | Latency | latency | lat_upf, lat_xn, lat_cudu |
| 18 | ANR Failure | anr | anr_stale_neighbor, anr_ho_nbr_mismatch |
| 19 | Neighbor Missing | anr | anr_missing_neighbor, ho_missing_neighbor |
| 20 | PCI Conflict | anr | anr_pci_conflict, ho_pci_collision |
| 21 | Configuration Drift | config_audit | cfg_audit_* golden baseline |
| 22 | Scheduler Congestion | throughput | tput_congestion, tput_prb_congestion_80 |
| 23 | Transport Congestion | transport | transport_congestion, tput_backhaul |
| 24 | Xn Failure | handover | ho_xn_failure, transport_xn_sctp |
| 25 | NG/N2 Failure | core | core_ng_n2_failure, ho_n2_failure |
| 26 | PM Counter Integrity | pm | pm_ho_rate_mismatch, pm_cqi_range |
| 27 | Alarm Correlation | alarm | alarm_kpi_correlation, alarm_du_cu |
| 28 | Syslog Correlation | gnb_syslog | 11 syslog signatures |

**API:** `GET /api/v1/rca/catalog` · `POST /api/v1/analyze/rca-type`

---

## Workflow-by-workflow analysis

### 1. Call Drop (4G/5G RAN)

| Item | Detail |
|------|--------|
| **Domains** | Retainability, Mobility, Coverage, Throughput, Transport |
| **TNIC agents** | call_drop, rlf, handover, rf_coverage, throughput, transport, gnb_syslog |
| **Was missing** | Workflow orchestration block, syslog RLF/PDCP signatures, VoNR drop correlation |
| **Now implemented** | `WORKFLOW_REGISTRY["call_drop"]`, `drop_ims` + vonr agent, `rlf_transport_flap` rule |
| **PM counters** | `call_drop_rate`, `rlf_rate`, `ho_success_rate`, `drop_mobility_pct`, `drop_radio_pct` |
| **Validation** | RLF ↓, DCR ↓, HO SR ↑ |

### 2. Low DL Throughput

| Item | Detail |
|------|--------|
| **Domains** | Throughput, Coverage, Beamforming, Transport |
| **TNIC agents** | throughput, beamforming, rf_coverage, transport, latency |
| **Was missing** | PRB >80% explicit rule, beam check in workflow map |
| **Now implemented** | `tput_prb_congestion_80`, workflow correlation to beamforming/transport |
| **PM counters** | `throughput_mbps`, `cqi`, `bler`, `prb_utilization`, `backhaul_utilization` |

### 3. Low UL Throughput

| Item | Detail |
|------|--------|
| **Domains** | Throughput, Coverage |
| **TNIC agents** | throughput, rf_coverage |
| **Was missing** | UL-specific rules |
| **Now implemented** | `tput_ul_degraded` (UL BLER, PHR, ul_throughput_mbps) |
| **Gap remaining** | TTI bundling, UL scheduler starvation (needs UL PM counters in dataset) |

### 4. VoLTE / VoNR voice

| Item | Detail |
|------|--------|
| **Domains** | VoNR, Core, Coverage, Mobility |
| **TNIC agents** | **vonr** (new), call_drop, core, latency, rf_coverage, gnb_syslog |
| **Was missing** | Entire VoNR agent, SIP/RTP rules |
| **Now implemented** | `vonr_rules.py` — 6 rules (setup, IMS reg, coverage, RTP, SRVCC, AMF/SMF) |
| **Gap remaining** | SIP trace parser, codec negotiation (needs IMS log ingestion) |

### 5. VoNR 5G SA

| Item | Detail |
|------|--------|
| **Domains** | VoNR, Core, Coverage |
| **TNIC agents** | vonr, core, rach, rf_coverage, config_audit |
| **Now implemented** | Workflow map + 5QI profile config audit + PDU session fail rule |

### 6. Handover Failure

| Item | Detail |
|------|--------|
| **Domains** | Mobility, Coverage, Transport |
| **TNIC agents** | handover, **anr**, rf_coverage, transport, config_audit, gnb_syslog |
| **Was missing** | ANR agent, PCI collision HO rule, NGAP/XnAP syslog |
| **Now implemented** | `anr_rules.py`, `ho_missing_neighbor`, `ho_pci_collision`, syslog NGAP/XnAP |

### 7. RRC / RACH Failure

| Item | Detail |
|------|--------|
| **Domains** | Accessibility, Coverage, Core |
| **TNIC agents** | rach, rf_coverage, core, config_audit, gnb_syslog |
| **Was missing** | RRC setup fail rule, PRACH config audit |
| **Now implemented** | `rach_rrc_setup_fail`, `rach_prach_config`, syslog PRACH/RRC reject |

### 8. Cell Outage / Degraded

| Item | Detail |
|------|--------|
| **Domains** | Coverage, Transport, Core |
| **TNIC agents** | gnb_syslog, pm, transport, config_audit |
| **Was missing** | Outage workflow, DU/CU crash signature |
| **Now implemented** | `syslog_du_crash`, workflow `cell_outage` orchestration map |
| **Gap remaining** | FM alarm CSV ingestion (needs alarm dataset) |

---

## Agent update matrix

| Agent | Status | Changes |
|-------|--------|---------|
| RF Coverage Agent | Extended | VoNR correlation in `COVERAGE_CORRELATION_MAP` |
| Handover Agent | Extended | +2 rules: missing neighbor, PCI collision |
| RLF Agent | Extended | +1 rule: transport flap |
| VoNR Agent | **NEW** | 6 rules, orchestrator wired |
| RACH Agent | Extended | +2 rules: RRC setup, PRACH config |
| Throughput Agent | Extended | +2 rules: UL degraded, PRB >80% |
| ANR Agent | **NEW** | 5 rules (NCR, PCI, stale NBR, HO+ANR, PRACH) |
| Config Audit Agent | **NEW** | 10 golden parameters |
| gNB Syslog Agent | **NEW** | 11 signatures |
| Master RCA Agent | Extended | workflow + coverage + syslog enrichment |

---

## Syslog signature catalog

| ID | Domain | Pattern |
|----|--------|---------|
| `syslog_ngap_ho_failure` | handover | NGAP HandoverPreparationFailure |
| `syslog_xnap_failure` | handover | XnAP / SCTP Xn |
| `syslog_rlf_out_of_sync` | rlf | RLF / T310 / N310 |
| `syslog_rach_preamble_collision` | rach | PRACH / MSG1 fail |
| `syslog_rrc_reject` | rach | RRCSetupReject |
| `syslog_pdcp_discard` | throughput | PDCP discard/timeout |
| `syslog_vonr_qfi_setup_fail` | vonr | 5QI-1 / VoNR bearer |
| `syslog_amf_release` | core | AMF UEContextRelease |
| `syslog_du_crash` | cell_outage | DU/CU crash / F1 down |
| `syslog_transport_loss` | transport | GTP/backhaul loss |
| `syslog_pci_conflict` | anr | PCI collision |

---

## Remaining gaps (roadmap)

| Priority | Gap | Effort |
|----------|-----|--------|
| P1 | FM alarm dataset + Cell Outage agent rules | Medium |
| P1 | IMS/SIP trace parser for VoNR mute calls | Medium |
| P2 | CM export ingestion (live MOI vs golden JSON) | High |
| P2 | UL PM counters in dataset (PHR, PUSCH BLER time series) | Low |
| P3 | SON closed-loop (auto-retune after RCA) | High |

---

## Files added/modified

```
tnic/rules/vonr_rules.py
tnic/rules/anr_rules.py
tnic/rules/config_audit_rules.py
tnic/rules/gnb_syslog_rules.py
tnic/services/gnb_syslog_parser.py
tnic/services/config_baseline.py
tnic/orchestrator/workflow_registry.py
tnic/orchestrator/master_rca.py          (extended)
tnic/orchestrator/rca_orchestrator.py    (extended)
tnic/agents/specialists.py               (4 new agents)
tnic/rules/ho_rules.py                   (+2 rules)
tnic/rules/rlf_rules.py                  (+1 rule)
tnic/rules/rach_rules.py                 (+2 rules)
tnic/rules/throughput_rules.py           (+2 rules)
tests/test_industry_rca_workflows.py
docs/TNIC_RCA_GAP_ANALYSIS.md
```
