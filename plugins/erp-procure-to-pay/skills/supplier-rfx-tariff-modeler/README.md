# Supplier RFx & Tariff Landed Cost Modeler (`supplier-rfx-tariff-modeler`)

Computes total landed unit and annual cost across competing supplier RFx quotes under incremental tariff shock scenarios, working capital payment terms, and defect PPM risk. Deterministic computation executes via [`scripts/landed_cost_simulator.py`](scripts/landed_cost_simulator.py). Domain guards enforced: Applies shock tariffs selectively to shocked origin countries when configured; Evaluates MOQ feasibility before ranking lowest unit FOB. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Strategic Sourcing / Commodity Manager**: Triggered when re-evaluating global vendor awards under sudden tariff hikes (`+25%`) and terms differences; calculates all-in landed cost including duty shock, net-days working capital adjustment, freight, and defect cost.
- **Supply Chain Finance Lead**: Triggered when auditing dual-sourcing concentration caps (`<=70%`) across critical assemblies; prevents naive lowest-ex-works-price selections that lose money after duty and scrap penalties.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`supplier-rfx-tariff-modeler.zip`](../../../../dist/skills/supplier-rfx-tariff-modeler.zip) (or the full department bundle [`erp-procure-to-pay.zip`](../../../../dist/bundles/erp-procure-to-pay.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP & PLM BOM MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/supplier-rfx-tariff-modeler` or `@supplier-rfx-tariff-modeler`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.landed_cost_simulator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"bids": [{"supplier_id": r.get("Custom supplier_id"), "unit_fob_usd": r.get("Custom unit_fob_usd"), "origin_country": r.get("Custom origin_country")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/erp-procure-to-pay/skills/supplier-rfx-tariff-modeler/scripts/landed_cost_simulator.py \
  --input examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx \
  --config plugins/erp-procure-to-pay/skills/supplier-rfx-tariff-modeler/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `landed_cost_simulator.py`: `--tariff-shock-pct`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP & PLM BOM MCP server`) via `remote_cli mcp`):** "Model a +25% tariff shock on CN origin quotes vs VN and MX bids for Apex Manufacturing."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Compare supplier quotes in our Drive RFx Sheet including Net 90 vs Net 30 financing value."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx) and ask: "Using the supplier quotes in `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`, model all-in annual landed cost across `50,000` units under a `+25%` tariff shock including duty, freight, payment-term financing, and defect cost before recommending a PO award."

## Sample Response

### What You See in Gemini Enterprise Chat

Under a **`+25.0%` tariff shock** across `50,000` annual units in `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`, **#1 ranked `Monterrey Industrial Machining` (`SUP-MONTERREY-MX`, `$11.85/unit`, `14d` lead) delivers the lowest landed cost at `$592,443.18/yr`**, saving **`$105,806.82/yr` vs. lowest-FOB China bid (`$698,250.00/yr`)**.

- **Tariff Shock Flip:** `SUP-SHENZHEN-CN` offered the lowest FOB price (`$9.80`), yet `27.0%` post-shock duty plus freight/lead pushed its landed unit cost to `$13.96` (`#3` worst).
- **Secondary Alternate:** `Gdansk Precision Components` (`SUP-GDANSK-PL`, `2.5%` duty, `21d` lead) ranked `#2` at `$13.70/unit` (`$684,760.96/yr`), providing clean dual-sourcing headroom.
- **Approval Confirmation Prompt:** Confirm if you would like to issue the `$592,443.18/yr` purchase award to `SUP-MONTERREY-MX` via your connected ERP MCP server (`Auto-Guardian` confirmation required).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx) (`135.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Supplier RFx Total Landed Cost & Tariff Sensitivity Model

- **Annual Demand:** 50,000 units | **Tariff Shock:** +25.0%
- **Lowest Landed Supplier:** Monterrey Industrial Machining ($592,443.18/yr; Saves $105,806.82 vs highest)

| Rank | Supplier | Origin | FOB | Tariff % | Landed/Unit | Annual Landed Cost | Lead (d) |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| 1 | `SUP-MONTERREY-MX` Monterrey Industrial Machining | MX | $11.10 | 0.0% | $11.85 | $592,443.18 | 14 |
| 2 | `SUP-GDANSK-PL` Gdansk Precision Components | PL | $12.10 | 2.5% | $13.70 | $684,760.96 | 21 |
| 3 | `SUP-SHENZHEN-CN` Shenzhen Precision Foundry | CN | $9.80 | 27.0% | $13.96 | $698,250.00 | 45 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily GR/IR Aging Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily GR/IR Aging Watch" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Execute weekday SAP GR/IR clearing aging check via scripts/gr_ir_reconciler.py to isolate IR_WITHOUT_GR blocks and >60 day accruals."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `annual_demand_units`, `tariff_shock_pct`, `tariff_shock_countries`, `bids`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `bids` requires [`supplier_id` or `supplier_name`; `unit_fob_usd`; `origin_country` or `base_tariff_pct`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `annual_cost_of_capital_pct` | `number` | `8.0` | Annual working-capital discount rate for payment terms modeling. |
| `defect_cost_per_unit_usd` | `number` | `45.0` | Estimated cost of poor quality per defective unit. |
| `max_single_source_share_pct` | `number` | `70.0` | Concentration cap before dual-source warning. |

See [`../../README.md`](../../README.md) for the `erp-procure-to-pay` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
