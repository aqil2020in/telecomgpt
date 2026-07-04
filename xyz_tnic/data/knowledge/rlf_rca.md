# RLF RCA Playbook

## Symptoms
- RLF rate elevated post-handover or during idle
- Out-of-sync / N310 expiry in UE log
- Reestablishment failures

## Diagnostic Steps
1. Correlate RLF with preceding HO events (too-late HO).
2. Audit post-HO SINR for 5 seconds after execution.
3. Review radio link monitoring timers (N310/N311/T310).
4. Check for sudden RSRP drops due to blockage or beam failure.

## Common Root Causes
- Too-late handover — UE loses sync before HO complete
- Serving cell SINR collapse (interference/blockage)
- Beam failure without successful recovery
- Incorrect T310/N310 tuning for deployment

## Recommended Actions
- Tune A3/A5 for faster HO trigger
- Fix underlying RF/beam issue on serving cell
- Review RLM constants per 3GPP TS 38.331
- Capture QXDM log with RLF reason code

## Validation
- RLF rate normalized vs cluster median
- No RLF cluster within 5s after HO
