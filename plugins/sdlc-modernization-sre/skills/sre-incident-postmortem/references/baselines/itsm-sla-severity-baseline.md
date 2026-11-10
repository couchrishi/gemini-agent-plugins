# Starter Baseline: ITSM SLA Severity & CAB Change-Risk Rubric (`itsm-sla-severity-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, stamp the deliverable header verbatim with:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Incident Severity & SLA Response / Resolution Targets

| Priority | Business Impact | Initial Response SLA | Resolution Target SLA | Clock Basis | Override Key in `config.json` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P1 (Critical)** | Complete production outage or active security breach affecting all users | `15 min` | `4 hours` (`240 min`) | `24x7` | `p1_resolution_minutes` |
| **P2 (High)** | Severe service degradation or critical workflow outage with workaround | `30 min` | `8 hours` (`480 min`) | `24x7` | `p2_resolution_minutes` |
| **P3 (Medium)** | Single-team or non-critical workflow degradation | `4 hours` | `3 business days` (`1440 bus min`) | `8x5` | `p3_resolution_minutes` |
| **P4 (Low)** | Minor defect, informational request, or cosmetic issue | `1 business day` | `5 business days` (`2400 bus min`) | `8x5` | `p4_resolution_minutes` |

- **Breach Warning Threshold:** Flag any active ticket at `>= 75%` of SLA business-elapsed budget (`sla_at_risk_pct = 75.0`).

## 2. Change Advisory Board (CAB) Risk Scoring (`0 – 100` Scale)

| Factor | Max Points | High-Risk Trigger |
| :--- | :--- | :--- |
| **Blast Radius / Tier-0 CI Impact** | `30` | Affects payment, auth, core ERP, or `> 1,000` users |
| **Rollback Plan & Validation** | `25` | Missing tested rollback script or non-reversible schema migration |
| **Freeze Window / Peak Collision** | `20` | Scheduled during quarter-end close, Black Friday/peak promo, or maintenance blackout |
| **Historical CI Failure Rate** | `15` | Target CI/service change failure rate `> 10%` in past 90 days |
| **Test & Canary Coverage** | `10` | Missing staging validation or automated canary gate |

- **CAB Routing Tiers:** `0–29` = `Standard / Auto-Approve`, `30–59` = `Normal / Peer + Manager Review`, `60–79` = `High / Weekly CAB Approval`, `80–100` = `Emergency / Executive VP + SRE Lead Sign-Off`.
