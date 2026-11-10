# ITSM & Service Desk Command Center (`itsm-command-center`)

Unifies incident SLA breach triage and spike clustering, deterministic CAB change-risk scoring, and Problem/KCS ticket deflection analytics across ServiceNow and Jira Service Management.

## Included Workflow Skills

1. **`incident-triage-routing`** ([SKILL.md](skills/incident-triage-routing/SKILL.md)) — Normalizes ServiceNow `state` codes and `display_value` fields, computes business-elapsed SLA burn (`sla_cluster_triage.py`), clusters correlated CI/error spikes, and ranks matching runbooks.
2. **`change-risk-cab-review`** ([SKILL.md](skills/change-risk-cab-review/SKILL.md)) — Scores Change Requests (`cab_risk_scorer.py`) across blast radius, rollback readiness, blackout freeze windows, CI failure history, and staging/canary coverage.
3. **`problem-rca-kb-generator`** ([SKILL.md](skills/problem-rca-kb-generator/SKILL.md)) — Mines resolved tickets (`kcs_deflection_analyzer.py`) for repeat Problem candidates, calculates MTTR (excluding open/canceled noise) and annualized L1 deflection savings, and validates KCS articles.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/itsm-command-center.zip`
- **Granular 1-Hop Upload:** `dist/skills/incident-triage-routing.zip`, `dist/skills/change-risk-cab-review.zip`, `dist/skills/problem-rca-kb-generator.zip`
