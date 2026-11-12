# Field Dispatch Cert & Spares Readiness (`field-dispatch-spares-prep`)

Matches telecom field work orders against technician skills, climbing/high-voltage certification expiration dates, and depot spare parts availability prior to dispatch. Deterministic computation executes via [`scripts/dispatch_readiness_matcher.py`](scripts/dispatch_readiness_matcher.py). Domain guards enforced: Blocks dispatch cleanly when safety cert expiry < dispatch_date; Blocks work orders with insufficient depot spare quantities. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Field Dispatch & Workforce Scheduler**: Triggered when assigning certified RF/fiber field technicians and reserved spares kits to morning work orders; hard-blocks expired tower-climb or high-voltage certifications (e.g., expired cert check) and incomplete depot spare kits.
- **Network Depot Materials Coordinator**: Triggered when staging optical SFP/line-card kits prior to dispatch truck roll; verifies `100%` parts reservation (`require_all_spares_reserved = true`) before switching orders to `READY_FOR_DISPATCH`.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`field-dispatch-spares-prep.zip`](../../../../dist/skills/field-dispatch-spares-prep.zip) (or the full department bundle [`telco-noc-field-dispatch.zip`](../../../../dist/bundles/telco-noc-field-dispatch.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`NMS Alarm Topology & Field Service Dispatch MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/field-dispatch-spares-prep` or `@field-dispatch-spares-prep`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.dispatch_readiness_matcher import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"work_orders": [{"work_order_id": r.get("Custom work_order_id"), "site_id": r.get("Custom site_id")} for r in wb["Source_Tab"]], "technicians": wb["technicians"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/telco-noc-field-dispatch/skills/field-dispatch-spares-prep/scripts/dispatch_readiness_matcher.py \
  --input examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx \
  --config plugins/telco-noc-field-dispatch/skills/field-dispatch-spares-prep/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `dispatch_readiness_matcher.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`NMS Alarm Topology & Field Service Dispatch MCP server`) via `remote_cli mcp`):** "Prepare dispatch for Stratos Telecom WO-88 with only one fiber tech whose climbing cert expired yesterday."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Field Ops Sheet where tech certs are valid but QSFP28 optical spare stock is 0."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx) and ask: "Verify technician tower-climbing/HV safety certifications and depot optical spares reservations for the `2026-11-10` field dispatch queue in `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` before authorizing truck rolls."

## Sample Response

### What You See in Gemini Enterprise Chat

Screening `2` field work orders for `2026-11-10` in `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` **cleared `WO-APX-1` (`TOWER-SGP-9`, tech `Elena Garcia`, spares verified) as `READY_FOR_DISPATCH`** while **blocking `WO-APX-2` (`TOWER-SGP-12`) due to missing `PSU-DC48` depot stock (`0` on hand vs. `1` required)**.

- **Cleared Truck Roll (`WO-APX-1`):** Assigned tech `T-APX-2` (`Elena Garcia`) holds valid safety certifications and `100%` reserved spares.
- **Hard-Blocked Dispatch (`WO-APX-2`):** Prevented wasted truck roll to `TOWER-SGP-12` by flagging zero depot stock on `PSU-DC48` (`MISSING_SPARES`).
- **Approval Confirmation Prompt:** Confirm if you would like to release depot spares and dispatch `WO-APX-1` via your connected Field Service / OSS MCP server (gated by `Auto-Guardian`) while routing `WO-APX-2` for `PSU-DC48` procurement.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx) (`143.0 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Field Dispatch Technician Cert & Spares Readiness (2026-11-10)

- **Work Orders:** 2 | **Ready:** 1 | **Blocked:** 1

| Work Order | Site | Assigned Tech | Spares Ready | Status | Blockers |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `WO-APX-1` | TOWER-SGP-9 | T-APX-2 (Elena Garcia) | YES | `READY_FOR_DISPATCH` | None |
| `WO-APX-2` | TOWER-SGP-12 | T-APX-2 (Elena Garcia) | NO | `BLOCKED` | MISSING_SPARES (PSU-DC48 (need 1, stock 0)) |

Truck rolls and depot pick-ticket releases require HITL dispatch coordinator confirmation.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly B2B Provisioning Fallout Watch` routine via `schedule_task`:

```text
Schedule recurring job "Hourly B2B Provisioning Fallout Watch" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly B2B provisioning fallout sweep via scripts/order_fallout_classifier.py and highlight P1 executive escalations where aged MRC breaches SLA."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `dispatch_date`, `depot_spares_qty`, `technicians`, `work_orders`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `work_orders` requires [`work_order_id`; `site_id` or `required_skills` or `required_spares`] | `technicians` requires [`tech_id`; `skills`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `enforce_safety_cert_expiry` | `boolean` | `True` | Block technician dispatch when climbing/high-voltage cert is expired as of dispatch date. |
| `require_all_spares_reserved` | `boolean` | `True` | Require 100% spare kit availability before marking work order READY_FOR_DISPATCH. |

See [`../../README.md`](../../README.md) for the `telco-noc-field-dispatch` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
