# Handover RCA Playbook

## Symptoms
- HO preparation failure rate > 5%
- HO too-late or too-early counters elevated
- Mobility failures on Xn/F1 interfaces

## Diagnostic Steps
1. Verify Xn/F1 connectivity between source and target gNB.
2. Confirm neighbor relation exists for target PCI and band (n77/n78).
3. Compare source vs target RSRP at HO decision — target should be ≥ 3 dB stronger for A3.
4. Check `hoPrepTimer`, `hoGuardTimer`, and cell barring on target.

## Common Root Causes
- Missing or stale neighbor relation
- Target cell barred (transport/energy saving)
- Incorrect A3 offset for UE speed profile
- Xn setup failure due to IPsec/ SCTP timeout

## Recommended Actions
- Add or refresh NBR via OSS bulk template
- Clear cell barring after transport restoration
- Tune A3/A5 thresholds per cluster baseline
- Capture UE log with HO trace for failing events

## Validation
- HO success rate restored to ≥ 98% for 24h
- HO prep fail rate < 2% on affected neighbor pair
