# Throughput RCA Playbook

## Symptoms
- Mean DL throughput below cluster baseline
- Low CQI, high BLER, rank-1 dominance
- PRB utilization high but user throughput low

## Diagnostic Steps
1. Review CQI, BLER, RI, and MCS distribution.
2. Check for co-channel interference on same band/PCI mod-3.
3. Validate transport/backhaul utilization on N3.
4. Compare KPIs against golden cell (43212) in same cluster.

## Common Root Causes
- RF interference or poor SINR
- MIMO rank stuck at 1 (calibration issue)
- Scheduler limitation due to high PRB load
- Transport congestion on N3/F1

## Recommended Actions
- Adjust electrical/azimuth tilt to reduce overlap
- Recalibrate AAU and verify beam book
- Enable IRC or optimize ICIC parameters
- Upgrade or QoS-shape backhaul if utilization > 75%

## Validation
- Mean DL throughput meets target (≥ 100 Mbps NR SA)
- CQI avg ≥ 10 and BLER < 5% post-fix
