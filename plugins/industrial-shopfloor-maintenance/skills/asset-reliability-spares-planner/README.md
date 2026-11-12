# Asset Reliability & Critical Spares ROP Planner (`asset-reliability-spares-planner`)

Computes asset MTBF (including conservative zero-failure censoring), lead-time spare demand, safety stock, Reorder Points, and stockout expedite recommendations. Deterministic computation executes via [`scripts/mtbf_spares_optimizer.py`](scripts/mtbf_spares_optimizer.py). Domain guards enforced: Applies right-censored MTBF handling cleanly when observed_failures == 0; Escalates CRITICAL stockouts at zero on-hand explicitly. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Plant Maintenance & Reliability Engineer**: Triggered when setting spare-parts reorder points (ROP) and safety stock across critical rotating assets; applies `1.65z` Weibull/demand math while honoring non-zero criticality floors (`TURBINE-SEAL-88`) even on zero historical failures.
- **MRO Storeroom Inventory Buyer**: Triggered when generating replenishment purchase requisitions under tight lead times; prevents catastrophic stockouts on critical turbines without inflating low-priority consumables.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`asset-reliability-spares-planner.zip`](../../../../dist/skills/asset-reliability-spares-planner.zip) (or the full department bundle [`industrial-shopfloor-maintenance.zip`](../../../../dist/bundles/industrial-shopfloor-maintenance.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP PM / Shopfloor Historian & EHS Permit MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/asset-reliability-spares-planner` or `@asset-reliability-spares-planner`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.mtbf_spares_optimizer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"spare_parts": [{"part_id": r.get("Custom part_id"), "on_hand_qty": r.get("Custom on_hand_qty"), "observed_failures": r.get("Custom observed_failures")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/industrial-shopfloor-maintenance/skills/asset-reliability-spares-planner/scripts/mtbf_spares_optimizer.py \
  --input examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx \
  --config plugins/industrial-shopfloor-maintenance/skills/asset-reliability-spares-planner/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `mtbf_spares_optimizer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP PM / Shopfloor Historian & EHS Permit MCP server`) via `remote_cli mcp`):** "Check Apex Manufacturing compressor mechanical seals with 0 on-hand and 21-day lead time."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate Drive Spares Sheet including an ultra-critical turbine bearing with 0 failures in 12,000h."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx) and ask: "Optimize critical spare-parts safety stock and Reorder Points (ROP) in `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`, ensuring zero-historical-failure critical turbine parts still maintain minimum criticality spares."

## Sample Response

### What You See in Gemini Enterprise Chat

Analyzing `3` maintenance spare SKUs in `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` triggered **`2` urgent reorders totaling `$10,080.00` estimated PO spend**, catching **`1` critical zero-inventory stockout (`TURBINE-SEAL-88`, `0` on hand vs. ROP `2`)** despite its `20,000h` censored MTBF.

- **Critical Stockout Protected (`TURBINE-SEAL-88`):** Non-zero criticality floor flagged order quantity `2` (`$8,400.00`) despite zero recent failure events, preventing catastrophic turbine downtime.
- **Secondary Reorder & Adequate Stock:** `PUMP-BEARING-40` (`1` vs `7` ROP) triggers `6` units (`$1,680.00`), while `VALVE-GASKET-12` (`12` vs `2` ROP) stays adequately stocked (`$0.00`).
- **Approval Confirmation Prompt:** Confirm if you would like to raise SAP PM replenishment purchase requisitions totaling `$10,080.00` via your connected SAP PM / ERP MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx) (`132.2 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Asset Reliability & Critical Spares ROP Optimization

- **Parts Analyzed:** 3 | **Critical Stockouts:** 1 | **Reorder Triggers:** 2 | **Recommended PO Spend:** $10,080.00

| Part ID | Criticality | MTBF (h) | ROP | Net Avail | Order Qty | Est Spend | Status |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `TURBINE-SEAL-88` | CRITICAL | 20,000.0 | 2 | 0 | **2** | $8,400.00 | `CRITICAL_STOCKOUT_EXPEDITE` |
| `PUMP-BEARING-40` | STANDARD | 876.0 | 7 | 1 | **6** | $1,680.00 | `REORDER_BELOW_ROP` |
| `VALVE-GASKET-12` | STANDARD | 4,380.0 | 2 | 12 | **0** | $0.00 | `ADEQUATE_COVERAGE` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Critical Spares ROP Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Critical Spares ROP Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the daily critical spare parts ROP check via scripts/mtbf_spares_optimizer.py across plant rotating equipment and flag zero-stock critical assets."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `spare_parts`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `spare_parts` requires [`part_id`; `on_hand_qty`; `observed_failures` or `lead_time_days`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `service_level_z` | `number` | `1.65` | Z-score for spare parts safety stock (1.65 = ~95% service level). |

See [`../../README.md`](../../README.md) for the `industrial-shopfloor-maintenance` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
