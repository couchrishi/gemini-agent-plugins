---
name: kpi-anomaly-driver-tree
description: "Computes zero-residual Volume-Mix-Rate KPI bridges and z-score segment anomalies across period-over-period tables in RAM. Use when explaining revenue, margin, or volume swings. Don't use for SQL join-fanout checks (use schema-grounded-sql-analyst)."
created_by: gemini-agent-plugins
---

# KPI Anomaly & Driver Tree

## Domain Context & Objective

Computes exact zero-residual Volume-Mix-Rate variance decomposition and segment z-score anomaly detection. Computes zero-residual Volume-Mix-Rate variance decomposition and z-score segment anomalies. Execute calculations via `scripts/mix_rate_volume_bridge.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides`.
- **Optional Customer BYO-MCP Servers:** `Semantic BI Layer / Looker MCP server` (discover tools via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance:** Fetch dataset metadata, INFORMATION_SCHEMA definitions, dry-run byte estimates, and KPI extract tables from BigQuery, Snowflake, Postgres, or Google Sheets via remote_cli mcp before running Python fanout and mix/rate/volume checks.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** `segments` requires [`segment`; `current_revenue` or `prior_revenue` or `current_volume`] (matching top-level keys under `Expected Inputs` below).
- **Inspect Source Shape Directly in Python:** Call `read_xlsx_workbook(path)` (for `.xlsx`), `read_docx(path)` (for `.docx`), `read_csv_tsv(path)` (for `.csv`/`.tsv`), or `read_json_or_jsonl(path)` (for `.json`/`.jsonl`) in `pyrepl` — or inspect connector JSON keys directly — to see exact tab names, headers, and sample rows first.
- **Normalize Mismatched Fields in 5-10 Lines of Python:** Pass standard exports directly to `analyze(path_or_dict, config=cfg_path)`. When customer tab names, column headers, or nested objects differ, reshape rows into a canonical `payload` dict in a few lines of Python (calling `ask_question` only when two customer columns remain genuinely ambiguous).

## Step 3 — Run Deterministic Python Engine in `pyrepl` (or CLI) with Org Baseline Rules

1. Read `references/config.json` using `view_file` before scoring.
2. When `org_configured` is `false`, apply the bundled starter rubrics (`references/baselines/finance-materiality-baseline.md`) and stamp the top of every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

| Config Key | Type / Bounds | Default | Operational Role |
| :--- | :--- | :--- | :--- |
| `default_currency` | string | `"USD"` | Default analytical reporting currency. |
| `zscore_anomaly_threshold` | number, 1.0..5.0 | `2.0` | Absolute z-score threshold flagging KPI segment anomalies. |
| `materiality_amount_threshold` | number, 100.0..10000000.0 | `25000.0` | Absolute variance materiality threshold in reporting currency. |
| `max_query_scan_gb` | number, 1.0..100000.0 | `500.0` | Maximum dry-run BigQuery scan GB allowed before explicit confirmation. |
| `min_sample_size_guard` | integer, 5..500 | `30` | Minimum denominator sample size before emitting LOW_SAMPLE_SIZE caution. |
| `max_null_rate_warn_pct` | number, 1.0..80.0 | `15.0` | Column null percentage triggering data-quality warning in dataset profiler. |

Execute `scripts/mix_rate_volume_bridge.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/kpi-anomaly-driver-tree"),
            Path("skills/user-skills/kpi-anomaly-driver-tree"),
            Path("skills/conversational-bi-analyst"),
            Path("skills/user-skills/conversational-bi-analyst"),
            Path("."),
        )
        if (p / "scripts/mix_rate_volume_bridge.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/mix_rate_volume_bridge.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.mix_rate_volume_bridge import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass standard .xlsx/.csv/.json exports directly when headers match canonical names:
# payload = source_path_or_dict
# 2. For unfamiliar customer exports, inspect tabs/headers in pyrepl and shape a clean dict:
# wb = read_xlsx_workbook(Path("customer_export.xlsx"))
# print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})
# payload = {"segments": [{"segment": r.get("Customer segment"), "current_revenue": r.get("Customer current_revenue")} for r in wb["Custom_Tab"]]}
result = analyze(
    payload,
    config=cfg_path,
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/kpi-anomaly-driver-tree skills/user-skills/kpi-anomaly-driver-tree skills/conversational-bi-analyst skills/user-skills/conversational-bi-analyst skills/*; do
  [ -f "$d/scripts/mix_rate_volume_bridge.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/mix_rate_volume_bridge.py" --input payload.json --config "$SKILL_DIR/references/config.json" --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/mix_rate_volume_bridge.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `segments`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `summary`, `segments`, `anomalies`, `truncation_warnings`; `summary` (`segment_count`, `prior_total_revenue`, `current_total_revenue`, `total_delta`, `volume_effect`, `mix_effect`) |
| **Eval & Safety Checks** | Volume + Mix + Rate effects sum strictly to total_delta with zero residual.; Flags segments below min_sample_size_guard with low_sample_caution. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/bigquery-sap-erp-traps.md`, `references/traps/chain-denominator-seams.md`, `references/traps/google-workspace-traps.md`.

- Verify `bridge_residual == 0.0` and surface `low_sample_caution` whenever segment volume `< min_sample_size_guard`.
- Distributing executive KPI alerts externally or to broad leadership mailing lists requires explicit user confirmation (HITL).
- **`absent-is-not-zero.md`:** Preserve missing/null numerics as `None` (never coerce `'UNKNOWN'`/absent values to `0`) and surface `truncation_warnings` whenever `truncated=True`, `done=False`, or `total_available > count`.
- **`bigquery-sap-erp-traps.md`:** Normalize SAP `TCURX` zero/3-decimal factors (`JPY`/`KRW`), flip `SHKZG='H'` credit signs, invert `TCURR` quoted rates, and restrict BigQuery partitions.
- **`chain-denominator-seams.md`:** Keep numerator and denominator populations aligned across fiscal periods, currencies, and cohort windows; guard zero denominators deterministically.
- **`google-workspace-traps.md`:** Query Shared Drives with `supportsAllDrives=true`, read multi-tab Docs via `includeTabsContent=true`, and fetch Sheets with `UNFORMATTED_VALUE`.

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`segment_count`, `prior_total_revenue`, `current_total_revenue`, `total_delta`, `volume_effect`, `mix_effect`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Executing DDL/DML statements or unpartitioned warehouse queries exceeding max_query_scan_gb
  - Sharing executive KPI briefings or Slides decks to external leadership distribution lists
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - SQL AST DDL/DML block, missing partition filter flag, and 1:N join fanout double-count guard
  - Volume + Mix + Rate additive bridge identity check with min_sample_size_guard warnings
  - Strict BigQuery/Sheets UNFORMATTED_VALUE coercion without string display rounding
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Daily KPI Anomaly Digest", cron_expression="0 7 * * 1-5", time_zone="UTC", instruction="Run the daily KPI variance and z-score anomaly check using scripts/mix_rate_volume_bridge.py. Decompose revenue/margin changes into exact Volume, Mix, and Rate effects, flag segments exceeding zscore_anomaly_threshold, and save an internal Canvas digest without emailing distribution lists.")`.
