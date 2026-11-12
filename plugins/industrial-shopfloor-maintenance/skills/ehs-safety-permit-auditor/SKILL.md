---
name: ehs-safety-permit-auditor
description: "Audits high-hazard Permit-to-Work packages against Lockout/Tagout isolation, atmospheric O2/LEL safety tolerances, gas-test recency, fire watch, and worker certifications Use when verifying confined-space, hot-work, or high-voltage electrical permits before shopfloor entry. Don't use for calculating MRO spare-part inventories (use asset-reliability-spares-planner)."
created_by: gemini-agent-plugins
---

# EHS Permit-to-Work & LOTO Safety Auditor

## Domain Context & Objective

Enforces zero-compromise LOTO isolation, confined-space O2 (19.5-23.5%), 0% LEL gas freshness, fire watch, and worker certification checks. Audits EHS Permit-to-Work (PTW) packages for LOTO isolation, gas test limits, and worker certification. Execute calculations via `scripts/hse_permit_checker.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`.
- **Optional Customer BYO-MCP Servers:** `SAP PM / Shopfloor Historian & EHS Permit MCP server` (discover tools via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance:** Extract equipment work-order MTBF logs, spares inventory balances, QMS scrap batches, and EHS confined-space permit readings from BigQuery or customer SAP PM / Historian MCP servers via remote_cli mcp before Python safety and optimization runs.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** `permits` requires [`permit_id`; `gas_test_lel_pct` or `gas_test_o2_pct` or `loto_isolated`] (matching top-level keys under `Expected Inputs` below).
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

Execute `scripts/hse_permit_checker.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/ehs-safety-permit-auditor"),
            Path("skills/user-skills/ehs-safety-permit-auditor"),
            Path("skills/industrial-shopfloor-maintenance"),
            Path("skills/user-skills/industrial-shopfloor-maintenance"),
            Path("."),
        )
        if (p / "scripts/hse_permit_checker.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/hse_permit_checker.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.hse_permit_checker import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass standard .xlsx/.csv/.json exports directly when headers match canonical names:
# payload = source_path_or_dict
# 2. For unfamiliar customer exports, inspect tabs/headers in pyrepl and shape a clean dict:
# wb = read_xlsx_workbook(Path("customer_export.xlsx"))
# print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})
# payload = {"permits": [{"permit_id": r.get("Customer permit_id"), "gas_test_lel_pct": r.get("Customer gas_test_lel_pct")} for r in wb["Custom_Tab"]]}
result = analyze(
    payload,
    config=cfg_path,
    as_of_date="2026-11-10",
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/ehs-safety-permit-auditor skills/user-skills/ehs-safety-permit-auditor skills/industrial-shopfloor-maintenance skills/user-skills/industrial-shopfloor-maintenance skills/*; do
  [ -f "$d/scripts/hse_permit_checker.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/hse_permit_checker.py" --input payload.json --config "$SKILL_DIR/references/config.json" --as-of 2026-11-10 --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/hse_permit_checker.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `as_of_date`, `permits`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `as_of_date`, `summary`, `permit_audits`, `truncation_warnings`; `summary` (`permits_audited`, `stop_work_blocked_count`, `eligible_count`) |
| **Eval & Safety Checks** | Blocks missing gas test or expired worker certs unconditionally.; Enforces 19.5%-23.5% O2, 0.0% LEL, and <=60 min test freshness. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/bigquery-sap-erp-traps.md`, `references/traps/chain-denominator-seams.md`, `references/traps/servicenow-jira-itsm-traps.md`.

- Life-safety rule: missing O2/LEL readings or `loto_isolated != true` on confined-space/high-voltage work MUST return `STOP_WORK_BLOCKED` (never treat absent as safe!).
- Final Permit-to-Work authorization always requires live physical sign-off by a qualified Area Safety Authority (HITL).
- **`bigquery-sap-erp-traps.md`:** Normalize SAP `TCURX` zero/3-decimal factors (`JPY`/`KRW`), flip `SHKZG='H'` credit signs, invert `TCURR` quoted rates, and restrict BigQuery partitions.
- **`chain-denominator-seams.md`:** Keep numerator and denominator populations aligned across fiscal periods, currencies, and cohort windows; guard zero denominators deterministically.
- **`servicenow-jira-itsm-traps.md`:** Always read `sysparm_display_value=all`, inspect `business_stc` vs calendar elapsed time, and avoid truncated `top-N` ticket queries.

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`permits_audited`, `stop_work_blocked_count`, `eligible_count`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Creating spare-parts purchase requisitions in customer SAP PM / ERP MCP
  - Signing or authorizing live Permit-to-Work (LOTO / confined space) clearances in EHS MCP
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - Hard STOP_WORK_BLOCKED interlock whenever O2 < 19.5%/> 23.5%, LEL >= 10%, H2S/CO threshold breach, or missing LOTO verification
  - Zero-stock critical asset safety-stock floor and MTBF reorder-point calculation
  - Pareto 80/20 scrap concentration correlation and discounted CapEx payback bounds
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Daily Critical Spares ROP Watch", cron_expression="0 6 * * 1-5", time_zone="UTC", instruction="Run the daily critical spare parts ROP check via scripts/mtbf_spares_optimizer.py across plant rotating equipment and flag zero-stock critical assets.")`.
