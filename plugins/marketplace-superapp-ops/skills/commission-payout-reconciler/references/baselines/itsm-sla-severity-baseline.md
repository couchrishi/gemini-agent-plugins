# Starter Baseline: ITSM SLA Severity, Escalation & CAB Change-Risk Rubric (`itsm-sla-severity-baseline`)

> **Usage Stamp Rule:** Whenever `org_configured` in `references/config.json` is `false`, every deliverable MUST carry this exact top banner verbatim:
> `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## 1. Incident Severity & SLA Resolution Matrix (`itsm-command-center`)

| Priority | Business Impact Criteria | Initial Response | Resolution Target | Schedule | `config.json` Override Key |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P1 (Critical)** | Complete production outage, Tier-0 payment/auth failure, or active security breach | `15 min` | `4 hours` (`240 min`) | `24x7` | `p1_resolution_minutes` |
| **P2 (High)** | Severe service degradation or major enterprise workflow broken with workaround | `30 min` | `8 hours` (`480 min`) | `24x7` | `p2_resolution_minutes` |
| **P3 (Medium)** | Single-team or non-critical defect with localized operational workaround | `4 hours` | `3 bus days` (`1,440 min`) | `8x5` | `p3_resolution_minutes` |
| **P4 (Low)** | Minor defect, informational service inquiry, or cosmetic flaw | `1 bus day` | `5 bus days` (`2,400 min`) | `8x5` | `p4_resolution_minutes` |

- **At-Risk Warning & KCS Economics:** Warn when any active ticket consumes `>= 75.0%` of business-elapsed budget (`sla_at_risk_pct`); flag spike clusters of `>= 3` similar incidents (`spike_cluster_min`); value KCS deflection using `$28.00 / L1 ticket` (`cost_per_l1_ticket_usd`) and `35%` deflection target (`expected_kcs_deflection_rate`).

## 2. Change Advisory Board (CAB) 100-Point Risk Scoring Matrix (`change-risk-cab-review`)

| Risk Dimension | Max Points | Deterministic Trigger & Scoring Criteria | CAB Routing Tier | Score Range | Approval Requirement |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Blast Radius / Tier-0** | `30` | Touches Tier-0 (`payments`, `auth`, `erp`) or impacts `> 1,000` users | **Standard** | `0 – 29` | Pre-approved automated runbook |
| **Rollback Validation** | `25` | Missing tested rollback procedure or irreversible schema migration | **Normal** | `30 – 59` | Peer engineering + Manager review |
| **Freeze Window Collision** | `20` | Planned execution inside quarter-end close or holiday blackout | **High Risk** | `60 – 79` | Weekly CAB panel review required |
| **Historical Failure Rate** | `15` | Target CMDB CI 90-day change failure rate `> 10%` | **Emergency / Hold** | `80 – 100` | Executive VP + SRE Lead sign-off |
| **Test & Canary Coverage** | `10` | Missing staging validation or automated canary gate before rollout | — | — | Block production deploy until waived |

## 3. Cross-Plugin Operational, SRE, Industrial & Telco SLA Baselines

| Plugin ID | Covered Operational SLA / Safety Domain | Starter Baseline Defaults | `config.json` Override Keys |
| :--- | :--- | :--- | :--- |
| **`customer-operations-escalation`** | VIP account war-room & detractor triggers | `war_room_score_threshold = 70.0`, `vip_arr_threshold_usd = 250000.0`, `imminent_renewal_days = 90`, `detractor_csat_max = 2`, `detractor_nps_max = 6`, `max_resolution_hops = 6` | `war_room_score_threshold`, `vip_arr_threshold_usd`, `imminent_renewal_days`, `detractor_csat_max`, `detractor_nps_max`, `max_resolution_hops` |
| **`sdlc-modernization-sre`** | SRE error budget, PR complexity & traceability | `default_slo_availability_pct = 99.9`, `complexity_hotspot_threshold = 15`, `min_requirement_traceability_pct = 85.0`, `postmortem_action_sla_days = 14` | `default_slo_availability_pct`, `complexity_hotspot_threshold`, `min_requirement_traceability_pct`, `postmortem_action_sla_days` |
| **`industrial-shopfloor-maintenance`** | Confined-space gas & LOTO permit hard stops | `o2_min_pct = 19.5`, `o2_max_pct = 23.5`, `max_lel_pct = 0.0`, `max_gas_test_age_mins = 60` (`STOP_WORK_BLOCKED` on breach) | `o2_min_pct`, `o2_max_pct`, `max_lel_pct`, `max_gas_test_age_mins` |
| **`telco-noc-field-dispatch`** | NOC subscriber blast tiers, certs, spares & fallout | `p1_subscriber_threshold = 5000`, `p2_subscriber_threshold = 500`, `enforce_safety_cert_expiry = true`, `require_all_spares_reserved = true`, `provisioning_sla_days = 15` | `p1_subscriber_threshold`, `p2_subscriber_threshold`, `enforce_safety_cert_expiry`, `require_all_spares_reserved`, `provisioning_sla_days` |
| **`marketplace-superapp-ops`** | Last-mile delivery grace buffer | `sla_grace_minutes = 5` | `sla_grace_minutes` |
| **`retail-store-merchandising`** | DC receiving dock appointment grace window | `on_time_grace_minutes = 30`, `in_full_tolerance_pct = 98.0` | `on_time_grace_minutes`, `in_full_tolerance_pct` |

## 4. Operational Safety, Clock & HITL Guardrails

1. **Zero Tolerance on Safety/Permits:** Confined-space O2 outside `[19.5%, 23.5%]`, `LEL > 0%`, stale gas tests (`> 60 min`), missing LOTO locks, or expired technician tower-climb certs trigger immediate `STOP_WORK_BLOCKED` regardless of schedule pressure.
2. **State Separation (`TRAP-ITSM-01` & `TRAP-ITSM-03`):** Exclude `Canceled` (`state=8`) and open tickets (`resolved_at=null`) from closed MTTR; honor `8x5` schedules for `P3`/`P4`.
3. **Human-in-the-Loop Dispatch:** Automated ticket reassignment, PagerDuty executive paging, emergency CAB releases, or field crew dispatches stay strictly behind `explicit_per_call` confirmation.

## 5. Customizing via `config.json` & `--org-config`

```json
{
  "organization_name": "Cymbal Financial",
  "plugins": {
    "itsm-command-center": { "p1_resolution_minutes": 180, "sla_at_risk_pct": 70.0 },
    "telco-noc-field-dispatch": { "p1_subscriber_threshold": 2500, "enforce_safety_cert_expiry": true }
  }
}
```

Packaged org configs set `org_configured: true`, enforce corporate SLAs deterministically, and omit the starter baseline stamp.

## 6. Operational Incident & Safety Walkthrough Reference

| Domain / Scenario Input | Guarded Calculation & Decision Rule | Deterministic Output Classification |
| :--- | :--- | :--- |
| **3 P1 checkout DB tickets in `90 min`** | Meets `spike_cluster_min >= 3`; links matching runbook `RB-DB` | `SPIKE_CLUSTER_DETECTED` + unified Incident Bridge |
| **`CHG-1` on `payments-core`, no rollback, freeze** | Blast `30` + Rollback `25` + Freeze `20` (`= 75/100`) | **High Risk CAB** (`60–79` tier) -> Block until tested rollback |
| **`O2 = 18.8%` or gas test `90m` old (`PTW-APEX-101`)** | Breaches `o2_min_pct (19.5%)` / `max_gas_test_age_mins (60)` | Immediate `STOP_WORK_BLOCKED` (Safety hard halt) |
| **Core router `METRO-AGG-1` + `2` ring alarms** | Ring cycle skipped; downstream `7,700` subscribers `>= 5,000` | `1` Root **P1 Outage** + `2` Suppressed Symptom Alarms |
| **Tech `T-1` tower cert expired `2026-10-01`** | Breaches `enforce_safety_cert_expiry = true` (`WO-1`) | Excludes `T-1`, assigns valid cert `T-2`; holds unstocked spares |

## 7. Production Reliability & Dispatch Checklist

1. Separate open tickets (`resolved_at = None`), closed resolutions (`state 6/7`), and canceled duplicates (`state 8`) prior to reporting MTTR or SLA % metrics.
2. Use `8x5` business-elapsed budgets (net of `On Hold` pauses) on `P3`/`P4` SLAs while alerting early at `>= 75%` (`sla_at_risk_pct`).
3. Verify graph-traversal cycle guards remain active across CMDB and Telco NOC outage trees.
4. Keep PagerDuty executive escalations, emergency CAB approvals, field crew dispatches, and GitHub/Jira status mutations gated behind `explicit_per_call` confirmation.

## 8. ITSM / Safety CEL Policy Enforcements & Clock Rules

- `block_untested_freeze_cab`: `cab.freeze_collision == false && cab.rollback_validated == true`
- `enforce_stop_work_on_gas_or_loto`: `ehs.stop_work_blocked_count == 0`
- `block_expired_field_cert_dispatch`: `dispatch.expired_cert_assigned_count == 0`
- `require_human_on_p1_paging`: `request.severity in ["P1", "P2"]` requires `explicit_per_call` confirmation before external notification.

Scheduled monitors (`hourly-vip-escalation-radar.yaml`, `weekly-slo-burn-review.yaml`, `hourly-b2b-fallout-watch.yaml`) evaluate open backlogs deterministically against `24x7` vs `8x5` schedules, emit executive alerts via `emit_a2ui`, and hold outbound paging behind HITL approval.
