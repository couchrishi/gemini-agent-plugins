# Troubleshooting Decision Tree Author & Validator (`troubleshooting-tree-author`)

Audits interactive troubleshooting flowcharts using graph traversal to detect cycles, unreachable orphan nodes, broken branch targets, dead-end questions, and excessive hop depth. Deterministic computation executes via [`scripts/decision_tree_validator.py`](scripts/decision_tree_validator.py). Domain guards enforced: Detects cycles, orphan nodes, broken targets, and dead-end questions via BFS/DFS; Measures max_resolution_depth against max_resolution_hops. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Support Operations Architect**: Triggered when validating guided diagnostic flows before publishing to Tier-1 agents or self-service bots; audits DAG reachability from `N-START`, flags broken node pointers, orphan branches, dead ends, and >`6`-hop paths.
- **Service Design Lead**: Triggered when reviewing AI-drafted or edited troubleshooting playbooks prior to rollout; guarantees graph integrity so support agents never hit broken diagnostic dead ends on live calls.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`troubleshooting-tree-author.zip`](../../../../dist/skills/troubleshooting-tree-author.zip) (or the full department bundle [`customer-operations-escalation.zip`](../../../../dist/bundles/customer-operations-escalation.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/troubleshooting-tree-author` or `@troubleshooting-tree-author`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.decision_tree_validator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"nodes": [{"node_id": r.get("Custom node_id"), "node_type": r.get("Custom node_type")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/customer-operations-escalation/skills/troubleshooting-tree-author/scripts/decision_tree_validator.py \
  --input examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx \
  --config plugins/customer-operations-escalation/skills/troubleshooting-tree-author/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `decision_tree_validator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack` via `remote_cli mcp`):** "Validate our payment-timeout diagnostic tree JSON containing an infinite retry loop and a dangling branch target."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Support Playbook tree from Drive with 8 nested diagnostic hops."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx) and ask: "Validate the guided diagnostic troubleshooting tree in `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` from root node `N-START` to catch infinite cycles, broken branch pointers, unreachable orphan nodes, and excessive resolution depth before KB publish."

## Sample Response

### What You See in Gemini Enterprise Chat

Graph validation on the `4`-node diagnostic workflow starting at `N-START` in `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` **blocked publication (`graph_valid: False`)** after detecting **`1` infinite routing cycle (`N-START -> N-AUTH -> N-START`)** and **`1` unreachable orphan node**.

- **Blocking Topology Defects:** Transition `N-START -> N-AUTH -> N-START` creates an endless support loop while leaving `1` downstream node unreachable (`0` broken refs, `0` dead ends, max depth `1` hop).
- **Publish Safety Guarantee:** Support bots and Tier-1 agents are prevented from receiving non-terminating flowcharts.
- **Approval Confirmation Prompt:** Support portal publication requires graph validity (`graph_valid == true`) and `Auto-Guardian` approval; resolve the `N-AUTH -> N-START` cycle and reconnect the orphan node first, then confirm publish.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx) (`140.8 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Troubleshooting Decision Tree Integrity Audit (Root: `N-START`)

- **Nodes:** 4 | **Graph Valid:** `False` | **Max Depth:** 1 hops
- **Broken Refs:** 0 | **Dead Ends:** 0 | **Unreachable:** 1 | **Cycles:** 1

## Cycles Detected
- `N-START -> N-AUTH -> N-START`
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly VIP Escalation Radar` routine via `schedule_task`:

```text
Schedule recurring job "Hourly VIP Escalation Radar" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly VIP escalation exposure check via scripts/escalation_exposure_scorer.py across open Sev1/Sev2 accounts and renewal windows."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `root_node_id`, `nodes`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `nodes` requires [`node_id`; `node_type` or `branches`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_resolution_hops` | `integer` | `6` | Maximum decision tree hops before usability warning. |

See [`../../README.md`](../../README.md) for the `customer-operations-escalation` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
