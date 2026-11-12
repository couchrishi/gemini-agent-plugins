# Multi-Level BOM Cost Rollup & PPV Engine (`bom-cost-rollup-variance`)

Explodes multi-level Bills of Materials with scrap yield multipliers, detects cyclic references, and decomposes finished-good Purchase Price Variance down to leaf components. Deterministic computation executes via [`scripts/bom_ppv_rollup.py`](scripts/bom_ppv_rollup.py). Domain guards enforced: Detects circular parent-child BOM edges in bom_cycles_detected; Multiplies scrap factor cleanly across nested sub-assemblies. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Cost Accounting / Manufacturing Finance Lead**: Triggered when auditing multi-level bills of materials for standard cost rollups and purchase price variance (PPV); traverses DAG edges safely (`0` cycles) and compounds stage yields via `cost / (1 - scrap_rate)` (`+$10.56/unit` PPV on `FG-ACTUATOR-900`).
- **Product Costing Engineer**: Triggered when flagging upstream raw-material yield losses propagating into finished goods margin; isolates top component PPV drivers (`>5%` alert threshold) for supplier renegotiation.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`bom-cost-rollup-variance.zip`](../../../../dist/skills/bom-cost-rollup-variance.zip) (or the full department bundle [`erp-procure-to-pay.zip`](../../../../dist/bundles/erp-procure-to-pay.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP & PLM BOM MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/bom-cost-rollup-variance` or `@bom-cost-rollup-variance`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.bom_ppv_rollup import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"bom_edges": [{"parent_sku": r.get("Custom parent_sku"), "child_sku": r.get("Custom child_sku"), "qty_per_parent": r.get("Custom qty_per_parent")} for r in wb["Source_Tab"]], "items": wb["items"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/erp-procure-to-pay/skills/bom-cost-rollup-variance/scripts/bom_ppv_rollup.py \
  --input examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx \
  --config plugins/erp-procure-to-pay/skills/bom-cost-rollup-variance/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `bom_ppv_rollup.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP & PLM BOM MCP server`) via `remote_cli mcp`):** "Roll up 3-level pump assembly BOM standard vs actual PPV with 4% scrap on sub-assemblies."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Validate our Drive BOM Workbook containing an accidental sub-assembly circular edge."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx) and ask: "Roll up the multi-level manufacturing Bill of Materials and component Purchase Price Variance (PPV) in `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`, compounding sub-assembly scrap yield losses cleanly while checking for circular BOM references."

## Sample Response

### What You See in Gemini Enterprise Chat

Traversing the indented BOM for **`FG-ACTUATOR-900`** in `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` completed with **`0` circular reference errors** and calculated **`$+10.56/unit` (`+16.45%`) total Purchase Price Variance**, lifting actual unit cost from `$64.20` standard to **`$74.76` actual** (`1` alert component exceeding `5%`).

- **Compound Yield Rollup:** Stage scrap losses compounded via `cost / (1 - scrap_rate)` across child assemblies rather than adding linear flat percentages.
- **PPV Breach Flagged:** `1` upstream component exceeded the `5%` alert threshold, driving the `+$10.56/unit` finish-good cost overrun.
- **Approval Confirmation Prompt:** Confirm if you would like to review supplier contract awards via your connected ERP MCP server (`Auto-Guardian` confirmation required) or trigger MR11 standard-cost variance review via your connected ERP MCP server (`Auto-Guardian` confirmation required).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx) (`140.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Multi-Level BOM Cost Rollup & Purchase Price Variance (PPV)

- **Assemblies Rolled Up:** 1 | **Cycles Detected:** 0 | **Total Extended PPV:** $+10.56

| Assembly SKU | Volume | Std Cost | Actual Cost | Unit PPV | PPV % | Extended Variance |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `FG-ACTUATOR-900` | 1 | $64.20 | $74.76 | $+10.56 | +16.45% | **$+10.56** |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily GR/IR Aging Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily GR/IR Aging Watch" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Execute weekday SAP GR/IR clearing aging check via scripts/gr_ir_reconciler.py to isolate IR_WITHOUT_GR blocks and >60 day accruals."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `target_assemblies`, `items`, `bom_edges`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `bom_edges` requires [`parent_sku`; `child_sku`; `qty_per_parent`] | `items` requires [`sku`; `standard_unit_cost_usd` or `actual_unit_cost_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `ppv_alert_threshold_pct` | `number` | `5.0` | BOM component purchase price variance alert threshold %. |

See [`../../README.md`](../../README.md) for the `erp-procure-to-pay` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
