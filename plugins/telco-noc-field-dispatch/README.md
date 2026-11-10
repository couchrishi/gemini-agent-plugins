# Telecom NOC & Field Network Dispatch (`telco-noc-field-dispatch`)

Suppresses downstream network alarm storms via parent-child topology graph correlation, validates technician climbing/safety certifications and van/depot spares prior to field dispatch, and classifies B2B enterprise provisioning order fallout by queue and MRC-at-risk.

## Included Workflow Skills

1. **`noc-outage-topology-correlator`** ([SKILL.md](skills/noc-outage-topology-correlator/SKILL.md)) — Traces upstream parent-child network graphs to suppress downstream alarm storms and roll up impacted subscribers and VIP circuits.
2. **`field-dispatch-spares-prep`** ([SKILL.md](skills/field-dispatch-spares-prep/SKILL.md)) — Validates technician skills and non-expired safety certs as of dispatch date alongside depot/van spare kit stock before truck rolls.
3. **`b2b-order-fallout-resolver`** ([SKILL.md](skills/b2b-order-fallout-resolver/SKILL.md)) — Classifies stuck B2B DIA/MPLS/SIP orders into deterministic remediation queues and quantifies Monthly Recurring Charge (MRC) at risk.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/telco-noc-field-dispatch.zip`
- **Granular 1-Hop Upload:** `dist/skills/noc-outage-topology-correlator.zip`, `dist/skills/field-dispatch-spares-prep.zip`, `dist/skills/b2b-order-fallout-resolver.zip`
