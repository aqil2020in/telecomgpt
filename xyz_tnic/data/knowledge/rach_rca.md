# RACH RCA Playbook

## Symptoms
- RACH success rate < 92%
- MSG1/MSG3 failure counters elevated
- Registration failures at cell edge

## Diagnostic Steps
1. Verify `prach-ConfigurationIndex` matches band and SCS.
2. Check root sequence index collision with neighbors.
3. Review timing advance distribution for edge UEs.
4. Inspect co-channel DAS/small cell PRACH overlap.

## Common Root Causes
- PRACH occasion collision
- TA misalignment at cell border
- High interference on PRACH REs
- Incorrect zeroCorrelationZoneConfig

## Recommended Actions
- Re-plan root sequence index per cluster
- Adjust PRACH power ramping and preamble format
- Optimize cell range and TA parameters
- Disable conflicting DAS PRACH if overlapping

## Validation
- RACH success rate ≥ 98% for 24h
- MSG3 retx rate within baseline
