# NOC Outage Topology Alarm Correlator (`noc-outage-topology-correlator`)

Correlates telco SNMP/gNMI alarm storms across parent-child core, metro, OLT, and cell-site topology graphs to isolate root-cause nodes and roll up impacted subscribers. Deterministic computation executes via [`scripts/alarm_topology_correlator.py`](scripts/alarm_topology_correlator.py). Domain guards enforced: Suppresses downstream OLT/cell alarms when upstream metro aggregation node is alarming; Computes full downstream subscriber and VIP circuit cone accurately. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Network Operations Center (NOC) Duty Lead**: Triggered when isolating root optical fiber or core router faults during multi-thousand alarm storms; runs cycle-safe ring topology BFS to suppress sympathetic downstream alarms (`75%` noise reduction) and flags P1 (`>=5000` subs).
- **Transport & Core Network Architect**: Triggered when correlating simultaneous tower and aggregation alarms without circular graph hangs; identifies the exact root failed node/link to accelerate dispatch mean-time-to-repair.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`noc-outage-topology-correlator.zip`](../../../../dist/skills/noc-outage-topology-correlator.zip) (or the full department bundle [`telco-noc-field-dispatch.zip`](../../../../dist/bundles/telco-noc-field-dispatch.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`NMS Alarm Topology & Field Service Dispatch MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/noc-outage-topology-correlator` or `@noc-outage-topology-correlator`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.alarm_topology_correlator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"alarms": [{"node_id": r.get("Custom node_id"), "alarm_code": r.get("Custom alarm_code")} for r in wb["Source_Tab"]], "nodes": wb["nodes"], "edges": wb["edges"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/telco-noc-field-dispatch/skills/noc-outage-topology-correlator/scripts/alarm_topology_correlator.py \
  --input examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx \
  --config plugins/telco-noc-field-dispatch/skills/noc-outage-topology-correlator/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `alarm_topology_correlator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`NMS Alarm Topology & Field Service Dispatch MCP server`) via `remote_cli mcp`):** "Correlate Stratos Telecom alarm flood with 1 metro agg router alarm feeding 18 alarming 5G gNodeBs serving 12,400 subscribers."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Analyze Drive Topology & Alarm Export Sheet containing redundant ring links."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx) and ask: "Correlate the live alarm storm and fiber/router ring topology in `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` using cycle-safe graph traversal to isolate the true P1 root node, suppress downstream symptom alerts, and quantify impacted subscribers and VIP circuits."

## Sample Response

### What You See in Gemini Enterprise Chat

Running cycle-safe topology BFS across `4` ingested network alarms in `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` **isolated `1` P1 critical root outage (`METRO-AGG-SGP-01`, `OPTICAL_LOS`) serving `20,150` subscribers and `24` VIP circuits** while **suppressing `3` downstream symptom alarms (`75.0%` alarm noise reduction)**.

- **Root Cause Pinpointed:** `METRO-AGG-SGP-01` (`METRO_ROUTER` optical LOS) explains `100%` of downstream child tower/node alerts (`3` child alarms compressed into `1` incident).
- **Blast-Radius Severity (`P1_CRITICAL`):** `20,150` impacted subscribers (`>=5,000` P1 threshold) plus `24` enterprise VIP circuits trigger immediate NOC dispatch.
- **Approval Confirmation Prompt:** Confirm if you would like to bulk-suppress the `3` child symptom alarms via your connected `ServiceNow` connector (gated by `Auto-Guardian`) and dispatch emergency optical field repair via your connected Field Service / OSS MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx) (`150.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# NOC Alarm Storm Topology Correlation & Root Cause Clusters

- **Raw Alarms:** 4 -> **Root Incidents:** 1 | **Suppressed Symptoms:** 3 (75.0% reduction) | **P1 Critical:** 1

| Severity | Root Node | Type | Root Alarms | Suppressed Children | Subscribers | VIP Circuits |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: |
| `P1_CRITICAL` | `METRO-AGG-SGP-01` | METRO_ROUTER | OPTICAL_LOS | 3 | 20,150 | 24 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly B2B Provisioning Fallout Watch` routine via `schedule_task`:

```text
Schedule recurring job "Hourly B2B Provisioning Fallout Watch" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly B2B provisioning fallout sweep via scripts/order_fallout_classifier.py and highlight P1 executive escalations where aged MRC breaches SLA."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `nodes`, `edges`, `alarms`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `alarms` requires [`node_id`; `alarm_code`] | `nodes` requires [`node_id`; `node_type`] | `edges` requires [`upstream_node_id`; `downstream_node_id`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `p1_subscriber_threshold` | `integer` | `5000` | Subscriber impact count escalating correlated root incident to P1 Critical. |
| `p2_subscriber_threshold` | `integer` | `500` | Subscriber impact count escalating correlated root incident to P2 Major. |

See [`../../README.md`](../../README.md) for the `telco-noc-field-dispatch` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
