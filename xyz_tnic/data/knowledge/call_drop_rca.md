# Call Drop RCA Playbook

## Symptoms
- `call_drop_rate` or QDROP counters elevated
- Context release with abnormal cause
- Drops correlate with mobility or RLF events

## Diagnostic Steps
1. Correlate drop timestamps with HO and RLF counters.
2. Review AMF release cause if RAN KPIs are healthy.
3. Check beam failure ratio and SINR at drop location.
4. Inspect timer settings: T310, T311, N310, N311.

## Common Root Caauses
- RLF after failed reestablishment
- Too-late handover leaving UE on degraded serving cell
- Core-initiated release (5GMM cause 36/39)
- Beam failure on massive MIMO sector

## Recommended Actions
- Run RLF RCA workflow on affected cell cluster
- Tune mobility parameters for fast-moving UEs
- Verify core subscription and PDU session stability
- Recalibrate beam weights if BFR > 25%

## Validation
- Drop rate below operator threshold (< 1%) for 48h
- Re-establishment success rate within SLA
