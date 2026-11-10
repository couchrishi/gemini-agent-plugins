---
name: regulatory-change-mapper
description: "Maps regulatory articles against internal security and privacy controls, flags missing controls and stale or null audit evidence, and ranks remediation queues. Use when assessing regulatory changes (GDPR, DORA, EU AI Act) against internal controls. Don't use for individual contract redlines (use contract-playbook-redliner)."
created_by: gemini-agent-plugins
---

# Regulatory Change Mapper

Map statutory or regulatory articles deterministically against internal compliance controls and rank remediation actions before audit sign-off.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_grc_api`, `google_drive_api` | Query ServiceNow GRC control records and Drive regulatory briefing PDFs. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Docs`, `Google Drive` | Read Control Register Sheets (`UNFORMATTED_VALUE`) and Regulatory Change Docs in Compliance Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse uploaded regulation and control matrices directly in Python RAM via `view_file`. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Run [control_gap_mapper.py](scripts/control_gap_mapper.py) inside persistent `pyrepl` and optionally visualize gaps via `emit_a2ui`:

```python
from scripts.control_gap_mapper import analyze, render_markdown

res = analyze("regulatory_controls.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/control_gap_mapper.py --input regulatory_controls.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Null `last_tested_date` or empty `evidence_uri` MUST score `UNVERIFIED_MISSING_EVIDENCE` — never assume compliant.
- Modifying ServiceNow GRC control attestation states requires explicit user confirmation (HITL).
