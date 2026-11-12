---
name: quality-capex-rca-copilot
description: "Quantifies manufacturing scrap defects into 80/20 cost Paretos, detects anomalous supplier lots exceeding 2x plant average, and evaluates engineering CapEx payback years Use when investigating plant scrap spikes or justifying quality CapEx requests. Don't use for calculating MRO spare-part reorder points (use asset-reliability-spares-planner)."
created_by: gemini-agent-plugins
---

# Quality Defect 80/20 Pareto & CapEx RCA

## Domain Context & Objective

Builds 80/20 manufacturing scrap cost Paretos, isolates >=2x anomalous supplier lots, and computes CapEx payback hurdles. Computes manufacturing defect 80/20 Paretos, isolates shift/lot spikes, and checks CapEx payback. Execute calculations via `scripts/defect_pareto_correlator.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`.
- **Optional Customer BYO-MCP Servers:** `SAP PM / Shopfloor Historian & EHS Permit MCP server` (discover tools via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance:** Extract equipment work-order MTBF logs, spares inventory balances, QMS scrap batches, and EHS confined-space permit readings from BigQuery or customer SAP PM / Historian MCP servers via remote_cli mcp before Python safety and optimization runs.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** `events` requires [`defect_type`; `scrap_cost_usd` or `scrap_units`] | `capex_proposals` requires [`proposal_id`; `capex_cost_usd`] (matching top-level keys under `Expected Inputs` below).
- **Inspect Source Shape Directly in Python:** Call `read_xlsx_workbook(path)` (for `.xlsx`), `read_docx(path)` (for `.docx`), `read_csv_tsv(path)` (for `.csv`/`.tsv`), or `read_json_or_jsonl(path)` (for `.json`/`.jsonl`) in `pyrepl` — or inspect connector JSON keys directly — to see exact tab names, headers, and sample rows first.
- **Normalize Mismatched Fields in 5-10 Lines of Python:** Pass standard exports directly to `analyze(path_or_dict, config=cfg_path)`. When customer tab names, column headers, or nested objects differ, reshape rows into a canonical `payload` dict in a few lines of Python (calling `ask_question` only when two customer columns remain genuinely ambiguous).

## Step 3 — Run Deterministic Python Engine in `pyrepl` (or CLI) with Org Baseline Rules

1. Read `references/config.json` using `view_file` before scoring.
2. When `org_configured` is `false`, apply the bundled starter rubrics (`references/baselines/finance-materiality-baseline.md`, `references/baselines/itsm-sla-severity-baseline.md`) and stamp the top of every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

| Config Key | Type / Bounds | Default | Operational Role |
| :--- | :--- | :--- | :--- |
| `service_level_z` | number, 1.0..3.5 | `1.65` | Z-score for spare parts safety stock (1.65 = ~95% service level). |
| `max_capex_payback_years` | number, 0.25..10.0 | `2.0` | Maximum CapEx payback horizon in years. |
| `lot_spike_multiplier` | number, 1.2..5.0 | `2.0` | Ratio over plant lot scrap average triggering supplier containment alert. |
| `o2_min_pct` | number, 18.0..21.0 | `19.5` | Minimum safe confined-space O2 percentage. |
| `o2_max_pct` | number, 21.0..25.0 | `23.5` | Maximum safe confined-space O2 percentage. |
| `max_lel_pct` | number, 0.0..10.0 | `0.0` | Maximum permitted Lower Explosive Limit % for confined-space entry. |
| `max_gas_test_age_mins` | integer, 10..240 | `60` | Maximum elapsed minutes since atmospheric gas test. |

Execute `scripts/defect_pareto_correlator.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/quality-capex-rca-copilot"),
            Path("skills/user-skills/quality-capex-rca-copilot"),
            Path("skills/industrial-shopfloor-maintenance"),
            Path("skills/user-skills/industrial-shopfloor-maintenance"),
            Path("."),
        )
        if (p / "scripts/defect_pareto_correlator.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/defect_pareto_correlator.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.defect_pareto_correlator import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass standard .xlsx/.csv/.json exports directly when headers match canonical names:
# payload = source_path_or_dict
# 2. For unfamiliar customer exports, inspect tabs/headers in pyrepl and shape a clean dict:
# wb = read_xlsx_workbook(Path("customer_export.xlsx"))
# print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})
# payload = {"events": [{"defect_type": r.get("Customer defect_type"), "scrap_cost_usd": r.get("Customer scrap_cost_usd")} for r in wb["Custom_Tab"]], "capex_proposals": ...}
result = analyze(
    payload,
    config=cfg_path,
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/quality-capex-rca-copilot skills/user-skills/quality-capex-rca-copilot skills/industrial-shopfloor-maintenance skills/user-skills/industrial-shopfloor-maintenance skills/*; do
  [ -f "$d/scripts/defect_pareto_correlator.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/defect_pareto_correlator.py" --input payload.json --config "$SKILL_DIR/references/config.json" --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/defect_pareto_correlator.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `events`, `capex_proposals`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `summary`, `defect_pareto`, `anomalous_supplier_lots`, `capex_evaluations`, `truncation_warnings`; `summary` (`events_analyzed`, `total_scrap_cost_usd`, `vital_80_defect_count`, `anomalous_lot_count`, `approved_capex_count`) |
| **Eval & Safety Checks** | Computes cumulative % of scrap cost to tag vital 80% Pareto causes.; Isolates supplier lots >= 2.0x plant average scrap cost. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/bigquery-sap-erp-traps.md`, `references/traps/chain-denominator-seams.md`, `references/traps/servicenow-jira-itsm-traps.md`.

- Rank strictly by financial `scrap_cost_usd` (not just raw defect counts) so low-count high-cost assemblies stay visible.
- Quarantining supplier lots or approving CapEx expenditures requires Quality & Plant Finance sign-off (HITL).
- **`absent-is-not-zero.md`:** Preserve missing/null numerics as `None` (never coerce `'UNKNOWN'`/absent values to `0`) and surface `truncation_warnings` whenever `truncated=True`, `done=False`, or `total_available > count`.
- **`bigquery-sap-erp-traps.md`:** Normalize SAP `TCURX` zero/3-decimal factors (`JPY`/`KRW`), flip `SHKZG='H'` credit signs, invert `TCURR` quoted rates, and restrict BigQuery partitions.
- **`chain-denominator-seams.md`:** Keep numerator and denominator populations aligned across fiscal periods, currencies, and cohort windows; guard zero denominators deterministically.
- **`servicenow-jira-itsm-traps.md`:** Always read `sysparm_display_value=all`, inspect `business_stc` vs calendar elapsed time, and avoid truncated `top-N` ticket queries.

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`events_analyzed`, `total_scrap_cost_usd`, `vital_80_defect_count`, `anomalous_lot_count`, `approved_capex_count`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Creating spare-parts purchase requisitions in customer SAP PM / ERP MCP
  - Signing or authorizing live Permit-to-Work (LOTO / confined space) clearances in EHS MCP
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - Hard STOP_WORK_BLOCKED interlock whenever O2 < 19.5%/> 23.5%, LEL >= 10%, H2S/CO threshold breach, or missing LOTO verification
  - Zero-stock critical asset safety-stock floor and MTBF reorder-point calculation
  - Pareto 80/20 scrap concentration correlation and discounted CapEx payback bounds
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Daily Critical Spares ROP Watch", cron_expression="0 6 * * 1-5", time_zone="UTC", instruction="Run the daily critical spare parts ROP check via scripts/mtbf_spares_optimizer.py across plant rotating equipment and flag zero-stock critical assets.")`.
