# Customer Operations, VIP Escalation & Knowledge Quality (`customer-operations-escalation`)

Scores VIP account escalations by ARR exposure and Sev1 outages, mines CSAT/NPS verbatims into ARR-weighted driver paretos with null-rating hygiene, and validates support troubleshooting decision trees for graph defects.

## Included Workflow Skills

1. **`critical-escalation-warroom`** ([SKILL.md](skills/critical-escalation-warroom/SKILL.md)) — Scores VIP account escalations (0-100) from Sev1/Sev2 cases, SLA breaches, ARR, imminent renewals, outages, and competitor risk.
2. **`csat-churn-signal-miner`** ([SKILL.md](skills/csat-churn-signal-miner/SKILL.md)) — Classifies survey verbatims into ARR-weighted friction drivers, excludes null scores from averages, and catches explicit churn intent.
3. **`troubleshooting-tree-author`** ([SKILL.md](skills/troubleshooting-tree-author/SKILL.md)) — Validates customer support diagnostic trees via BFS/DFS for cycles, dead-end questions, orphan nodes, broken refs, and depth.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/customer-operations-escalation.zip`
- **Granular 1-Hop Upload:** `dist/skills/critical-escalation-warroom.zip`, `dist/skills/csat-churn-signal-miner.zip`, `dist/skills/troubleshooting-tree-author.zip`
