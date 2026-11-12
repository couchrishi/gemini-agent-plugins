# B2B Telecom Order Fallout & MRC Classifier (`b2b-order-fallout-resolver`)

Classifies B2B telecom provisioning fallout orders into credit, address, LNP port, OSP fiber capacity, or CPE queues while prioritizing by SLA breach and MRC at risk. Deterministic computation executes via [`scripts/order_fallout_classifier.py`](scripts/order_fallout_classifier.py). Domain guards enforced: Routes LNP, OSP capacity, credit, address, and CPE errors accurately; Computes both monthly MRC and annualized ARR blocked. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Enterprise Carrier Provisioning Manager**: Triggered when triaging stalled B2B fiber, DIA, and SD-WAN orders past the `15`-day provisioning SLA; ranks fallout queues by aged revenue impact (`MRC x days_in_fallout`), flags `$2,500+` MRC VIP orders, and routes by fallout root cause.
- **Telco B2B Service Delivery Lead**: Triggered when recovering blocked enterprise Monthly Recurring Revenue (`$163.2k+` annualized ARR blocked); assigns technical engineering vs customer-site readiness owners cleanly.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`b2b-order-fallout-resolver.zip`](../../../../dist/skills/b2b-order-fallout-resolver.zip) (or the full department bundle [`telco-noc-field-dispatch.zip`](../../../../dist/bundles/telco-noc-field-dispatch.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`NMS Alarm Topology & Field Service Dispatch MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/b2b-order-fallout-resolver` or `@b2b-order-fallout-resolver`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.order_fallout_classifier import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"fallout_orders": [{"order_id": r.get("Custom order_id"), "fallout_code": r.get("Custom fallout_code"), "mrc_usd": r.get("Custom mrc_usd")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/telco-noc-field-dispatch/skills/b2b-order-fallout-resolver/scripts/order_fallout_classifier.py \
  --input examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx \
  --config plugins/telco-noc-field-dispatch/skills/b2b-order-fallout-resolver/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `order_fallout_classifier.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`NMS Alarm Topology & Field Service Dispatch MCP server`) via `remote_cli mcp`):** "Triage Stratos Telecom B2B fallout queue with aged $4,200/mo DIA circuit hitting OLT port capacity and $1,100/mo SIP LNP freeze."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Classify B2B Fallout Sheet in Drive across credit holds, demarc address failures, and CPE backorders."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx) and ask: "Rank the aged B2B carrier provisioning fallout backlog in `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` by blocked Monthly Recurring Revenue (`MRC`), flag orders breaching the 15-day SLA, and route each order to the right operations queue."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing `2` stalled B2B provisioning orders in `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` found **both (`2 / 2`) in `P1_EXEC_ESCALATE` past the 15-day provisioning SLA**, blocking **`$13,600.00/mo` MRC (`$163,200.00` annualized ARR)**: `B2B-APX-901` (`$8,400/mo`, `26d`) and `B2B-APX-902` (`$5,200/mo`, `21d`).

- **Priority #1 (`B2B-APX-901` — `Stratos Sovereign Bank`):** `DIA_FIBER` at `$8,400.00/mo` aged `26` days -> routed to `Order Fallout Triage Desk` (`UNCLASSIFIED_PROV_EXCEPTION`).
- **Priority #2 (`B2B-APX-902` — `Kestrel Maritime Group`):** `MPLS_WAN` at `$5,200.00/mo` aged `21` days -> routed to `LNP Porting Operations` (`NUMBER_PORT_LNP_FREEZE`).
- **Approval Confirmation Prompt:** Confirm field dispatch or child-ticket routing updates for site readiness resolution via your connected Field Service / OSS MCP server (gated by `Auto-Guardian`) if physical demarc work is scheduled.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx`](../../../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx) (`141.2 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# B2B Telco Provisioning Fallout & MRC-at-Risk Triage

- **Orders in Fallout:** 2 | **SLA Breached:** 2 | **MRC at Risk:** $13,600.00/mo ($163,200.00 ARR)

| Order | Customer | Product | MRC | Age (d) | Bucket | Assigned Queue | Priority |
| :--- | :--- | :--- | ---: | ---: | :--- | :--- | :--- |
| `B2B-APX-901` | Stratos Sovereign Bank | DIA_FIBER | $8,400.00 | 26 | `UNCLASSIFIED_PROV_EXCEPTION` | Order Fallout Triage Desk | `P1_EXEC_ESCALATE` |
| `B2B-APX-902` | Kestrel Maritime Group | MPLS_WAN | $5,200.00 | 21 | `NUMBER_PORT_LNP_FREEZE` | LNP Porting Operations | `P1_EXEC_ESCALATE` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly B2B Provisioning Fallout Watch` routine via `schedule_task`:

```text
Schedule recurring job "Hourly B2B Provisioning Fallout Watch" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly B2B provisioning fallout sweep via scripts/order_fallout_classifier.py and highlight P1 executive escalations where aged MRC breaches SLA."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `fallout_orders`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `fallout_orders` requires [`order_id`; `fallout_code` or `error_message`; `mrc_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `provisioning_sla_days` | `integer` | `15` | B2B circuit provisioning SLA target in days. |
| `high_value_mrc_usd` | `number` | `2500.0` | B2B MRC threshold escalating aged fallout to executive triage. |

See [`../../README.md`](../../README.md) for the `telco-noc-field-dispatch` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
