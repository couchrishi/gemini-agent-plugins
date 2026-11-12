# Quality Defect 80/20 Pareto & CapEx RCA (`quality-capex-rca-copilot`)

Quantifies manufacturing scrap defects into 80/20 cost Paretos, detects anomalous supplier lots exceeding 2x plant average, and evaluates engineering CapEx payback years. Deterministic computation executes via [`scripts/defect_pareto_correlator.py`](scripts/defect_pareto_correlator.py). Domain guards enforced: Computes cumulative % of scrap cost to tag vital 80% Pareto causes; Isolates supplier lots >= 2.0x plant average scrap cost. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Plant Quality Director / Six Sigma Black Belt**: Triggered when prioritizing shopfloor scrap categories and CapEx automation proposals; builds `80/20` cost Pareto (`Porosity Void #1`), detects `>2x` lot-level supplier spikes, and validates `<2.0`-year CapEx payback.
- **Manufacturing Ops VP**: Triggered when ranking factory capital investments across competing scrap-reduction business cases; links defect telemetry directly to NPV/payback gating before CapEx submission.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`quality-capex-rca-copilot.zip`](../../../../dist/skills/quality-capex-rca-copilot.zip) (or the full department bundle [`industrial-shopfloor-maintenance.zip`](../../../../dist/bundles/industrial-shopfloor-maintenance.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP PM / Shopfloor Historian & EHS Permit MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/quality-capex-rca-copilot` or `@quality-capex-rca-copilot`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.defect_pareto_correlator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"events": [{"defect_type": r.get("Custom defect_type"), "scrap_cost_usd": r.get("Custom scrap_cost_usd")} for r in wb["Source_Tab"]], "capex_proposals": wb["capex_proposals"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/industrial-shopfloor-maintenance/skills/quality-capex-rca-copilot/scripts/defect_pareto_correlator.py \
  --input examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx \
  --config plugins/industrial-shopfloor-maintenance/skills/quality-capex-rca-copilot/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `defect_pareto_correlator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP PM / Shopfloor Historian & EHS Permit MCP server`) via `remote_cli mcp`):** "Analyze Apex Manufacturing CNC plant scrap events across supplier lots and shifts."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate Drive Quality Sheet proposing a $180k vision inspection cell saving $120k/yr vs $300k saving $60k/yr."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx) and ask: "Build an 80/20 scrap-cost Pareto across plant quality defects in `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`, screen supplier lots for anomalous failure spikes, and evaluate proposed CapEx automation payback hurdles."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `3` plant defect logs totaling **`$222,000.00` in scrap cost** in `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` (`0` anomalous single-lot spikes), **`2` vital-80% defect types drive `94.6%` of total losses** (`Porosity Void` `$142,000.00` at `64.0%`, `Micro-Fracture` `$68,000.00` at `30.6%`), validating **`1` CapEx automation payback**.

- **Pareto Concentration:** Addressing `Porosity Void` (`1,800` units, `$142k`) and `Micro-Fracture` (`650` units, `$68k`) captures `94.6%` of total plant scrap ahead of `Surface Burr` (`$12k`, `5.4%`).
- **CapEx Hurdle Gate:** `1` automation investment cleared the `<2.0`-year payback criterion linked directly to `Porosity Void` / inspection telemetry.
- **Approval Confirmation Prompt:** Confirm if you would like to create spares/tooling procurement requisitions for the approved quality CapEx cell via your connected SAP PM / ERP MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx`](../../../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx) (`134.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Quality Defect 80/20 Pareto & CapEx Payback Report

- **Scrap Events:** 3 | **Total Scrap Cost:** $222,000.00 | **Vital 80% Drivers:** 2 | **Anomalous Supplier Lots:** 0

| Defect Type | Events | Units | Scrap Cost | Share % | Cum % | Vital 80% |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `Porosity Void` | 1 | 1800 | $142,000.00 | 64.0% | 64.0% | YES |
| `Micro-Fracture` | 1 | 650 | $68,000.00 | 30.6% | 94.6% | YES |
| `Surface Burr` | 1 | 190 | $12,000.00 | 5.4% | 100.0% | No |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Critical Spares ROP Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Critical Spares ROP Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the daily critical spare parts ROP check via scripts/mtbf_spares_optimizer.py across plant rotating equipment and flag zero-stock critical assets."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `events`, `capex_proposals`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `events` requires [`defect_type`; `scrap_cost_usd` or `scrap_units`] | `capex_proposals` requires [`proposal_id`; `capex_cost_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_capex_payback_years` | `number` | `2.0` | Maximum CapEx payback horizon in years. |
| `lot_spike_multiplier` | `number` | `2.0` | Ratio over plant lot scrap average triggering supplier containment alert. |

See [`../../README.md`](../../README.md) for the `industrial-shopfloor-maintenance` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
