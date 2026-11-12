# Supplier OTIF, Chargebacks & Detention Auditor (`supplier-otif-chargeback-auditor`)

Calculates vendor PO On-Time In-Full scores with buyer/weather exclusions, computes contractual late and short-ship chargebacks, and reconciles live-unload detention eligibility. Deterministic computation executes via [`scripts/otif_detention_calculator.py`](scripts/otif_detention_calculator.py). Domain guards enforced: Applies late carrier detention forfeiture and weather exclusion accurately; Separates On-Time %, In-Full %, and combined OTIF %. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Retail Supply Chain Vendor Compliance Lead**: Triggered when calculating quarterly vendor On-Time In-Full (OTIF) scorecards and deduction claims; evaluates `>=98%` in-full and `<=30m` grace windows (`95%` OTIF target) plus yard detention exposure before EDI/AP chargebacks.
- **DC Inbound Receiving Manager**: Triggered when reconciling dock arrival timestamps against purchase-order delivery windows; generates itemized PO evidence packs requiring commercial sign-off prior to vendor debit memos.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`supplier-otif-chargeback-auditor.zip`](../../../../dist/skills/supplier-otif-chargeback-auditor.zip) (or the full department bundle [`retail-store-merchandising.zip`](../../../../dist/bundles/retail-store-merchandising.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP Retail ERP & POS Store Telemetry MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/supplier-otif-chargeback-auditor` or `@supplier-otif-chargeback-auditor`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.otif_detention_calculator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"po_deliveries": [{"po_number": r.get("Custom po_number"), "ordered_units": r.get("Custom ordered_units"), "received_units": r.get("Custom received_units")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/retail-store-merchandising/skills/supplier-otif-chargeback-auditor/scripts/otif_detention_calculator.py \
  --input examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx \
  --config plugins/retail-store-merchandising/skills/supplier-otif-chargeback-auditor/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `otif_detention_calculator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP Retail ERP & POS Store Telemetry MCP server`) via `remote_cli mcp`):** "Audit Northstar Retail PO arriving 95 minutes late with 180 minutes dock dwell and 90% fill rate."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate DC Receiving Sheet with WEATHER_FORCE_MAJEURE exclusion and on-time carrier detained 4 hours."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx) and ask: "Calculate vendor On-Time In-Full (OTIF) scorecards, dock-delay chargebacks, and carrier detention offsets from `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` against our `95%` OTIF target and `30`-minute dock grace window."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing `3` PO dock deliveries in `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` recorded **`66.7%` overall OTIF (below the `95.0%` target)**, generating **`$3,017.50` gross vendor chargebacks offset by `$150.00` detention exposure (`$2,867.50` net recovery from `V-CPG-NORTH`)** while `Horizon Packaging` (`V-STD-01`) passed at `100.0%` OTIF.

- **Vendor SLA Breach (`V-CPG-NORTH` — Pacifica Beverage Corp):** `50.0%` OTIF across `2` POs triggers `$3,017.50` gross chargeback minus `$150.00` payable carrier detention = **`$2,867.50` net vendor recovery**.
- **Compliant Supplier (`V-STD-01` — Horizon Packaging):** `100.0%` OTIF with `$0.00` deductions.
- **Approval Confirmation Prompt:** Confirm commercial vendor-ops sign-off before issuing the `$3,017.50` (`$2,867.50` net) AP chargeback debit memo via your connected AP / ERP MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx) (`138.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Supplier OTIF, Chargeback & Detention Settlement Audit

- **Deliveries Audited:** 3 | **Overall OTIF:** 66.7% (Target 95.0%) | **Total Chargebacks:** $3,017.50 | **Detention Exposure:** $150.00

| Vendor | POs | OTIF % | Chargebacks | Detention Payable | Net Recovery | SLA |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `V-CPG-NORTH` Pacifica Beverage Corp | 2 | 50.0% | $3,017.50 | $150.00 | $2,867.50 | BREACH |
| `V-STD-01` Horizon Packaging | 1 | 100.0% | $0.00 | $0.00 | $0.00 | PASS |

Draft debit memos require HITL vendor-ops sign-off before posting to ERP AP.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Store Shrink & Zero-Scan Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Store Shrink & Zero-Scan Watch" on cron `30 6 * * *` (`UTC`) with instruction: "Run the morning store shrink and zero-scan phantom inventory sweep via scripts/store_shrink_task_ranker.py and produce prioritized cycle-count lists per store manager."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `po_deliveries`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `po_deliveries` requires [`po_number`; `ordered_units`; `received_units`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `target_otif_pct` | `number` | `95.0` | Contractual vendor On-Time In-Full SLA threshold percentage. |
| `in_full_tolerance_pct` | `number` | `98.0` | Minimum received-vs-ordered fill rate required for In-Full pass. |
| `on_time_grace_minutes` | `integer` | `30` | Dock arrival grace window past appointment time. |

See [`../../README.md`](../../README.md) for the `retail-store-merchandising` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
