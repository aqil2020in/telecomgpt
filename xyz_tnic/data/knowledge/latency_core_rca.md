# Latency and Core RCA Playbook

## Symptoms
- RTT p95 above SLA (typically 30–50 ms for eMBB)
- UPF latency counters elevated
- PDU session setup delay

## Diagnostic Steps
1. Segment latency: RAN vs transport vs UPF vs AMF/SMF.
2. Check UPF CPU, session count, and DPDK queue drops.
3. Verify 5QI-to-DRB mapping and GBR/non-GBR profile.
4. Review AMF release and PDU session logs if drops accompany latency.

## Common Root Causes
- UPF cluster load imbalance
- Incorrect 5QI mapping for latency-sensitive apps
- N3/N6 transport congestion
- AMF-initiated release due to subscription mismatch

## Recommended Actions
- Rebalance UPF sessions across cluster nodes
- Scale UPF instances or enable horizontal pod autoscaling
- Apply QoS on N3 for GBR 5QI flows
- Update UDM subscription for affected DNN/S-NSSAI

## Validation
- RTT p95 within SLA for 24h monitoring window
- PDU session setup success rate ≥ 99%
