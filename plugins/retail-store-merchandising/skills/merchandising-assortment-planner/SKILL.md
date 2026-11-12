---
name: merchandising-assortment-planner
description: "Computes promotional unit and revenue lift normalized by campaign duration, adjusts for sibling SKU cannibalization, basket halo, and vendor coop funding, and calculates net margin ROI Use when evaluating retail promotion effectiveness, vendor co-op ROI, or seasonal markdown performance. Don't use for auditing store floor shrink variance (use store-ops-shrink-copilot)."
created_by: gemini-agent-plugins
---

# Merchandising Promo Lift & Margin ROI

## Domain Context & Objective

Normalizes baseline vs promo durations, deducts sibling cannibalization, adds basket halo, and computes net promo margin ROI. Evaluates promotional unit lift, cannibalization/halo adjustments, and net incremental promo margin ROI. Execute calculations via `scripts/promo_lift_analyzer.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs`.
- **Optional Customer BYO-MCP Servers:** `SAP Retail ERP & POS Store Telemetry MCP server` (discover tools via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance:** Pull store perpetual inventory, POS terminal polling health, promo elasticity tables, and ASN/POD Dock timestamps from BigQuery/Snowflake or customer SAP Retail / POS MCP servers via remote_cli mcp before Python shrink and OTIF math.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** `campaigns` requires [`campaign_id` or `campaign_name`; `baseline_units` or `baseline_revenue_usd`; `promo_units` or `promo_revenue_usd`] (matching top-level keys under `Expected Inputs` below).
- **Inspect Source Shape Directly in Python:** Call `read_xlsx_workbook(path)` (for `.xlsx`), `read_docx(path)` (for `.docx`), `read_csv_tsv(path)` (for `.csv`/`.tsv`), or `read_json_or_jsonl(path)` (for `.json`/`.jsonl`) in `pyrepl` — or inspect connector JSON keys directly — to see exact tab names, headers, and sample rows first.
- **Normalize Mismatched Fields in 5-10 Lines of Python:** Pass standard exports directly to `analyze(path_or_dict, config=cfg_path)`. When customer tab names, column headers, or nested objects differ, reshape rows into a canonical `payload` dict in a few lines of Python (calling `ask_question` only when two customer columns remain genuinely ambiguous).

## Step 3 — Run Deterministic Python Engine in `pyrepl` (or CLI) with Org Baseline Rules

1. Read `references/config.json` using `view_file` before scoring.
2. When `org_configured` is `false`, apply the bundled starter rubrics (`references/baselines/finance-materiality-baseline.md`, `references/baselines/itsm-sla-severity-baseline.md`) and stamp the top of every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

| Config Key | Type / Bounds | Default | Operational Role |
| :--- | :--- | :--- | :--- |
| `zero_scan_days_threshold` | integer, 1..30 | `5` | Days without POS scans for positive book on-hand before flagging phantom inventory. |
| `min_book_qty_for_phantom` | integer, 1..100 | `4` | Minimum perpetual book qty required to trigger zero-scan investigation. |
| `high_shrink_usd_threshold` | number, >=10.0 | `250.0` | Physical count variance threshold in USD triggering EAS/receiving audit. |
| `min_acceptable_promo_roi` | number, 0.0..5.0 | `0.15` | Minimum incremental net gross margin ROI ratio to classify campaign as scalable. |
| `target_otif_pct` | number, 50.0..100.0 | `95.0` | Contractual vendor On-Time In-Full SLA threshold percentage. |
| `in_full_tolerance_pct` | number, 80.0..100.0 | `98.0` | Minimum received-vs-ordered fill rate required for In-Full pass. |
| `on_time_grace_minutes` | integer, 0..240 | `30` | Dock arrival grace window past appointment time. |

Execute `scripts/promo_lift_analyzer.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/merchandising-assortment-planner"),
            Path("skills/user-skills/merchandising-assortment-planner"),
            Path("skills/retail-store-merchandising"),
            Path("skills/user-skills/retail-store-merchandising"),
            Path("."),
        )
        if (p / "scripts/promo_lift_analyzer.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/promo_lift_analyzer.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.promo_lift_analyzer import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass standard .xlsx/.csv/.json exports directly when headers match canonical names:
# payload = source_path_or_dict
# 2. For unfamiliar customer exports, inspect tabs/headers in pyrepl and shape a clean dict:
# wb = read_xlsx_workbook(Path("customer_export.xlsx"))
# print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})
# payload = {"campaigns": [{"campaign_id": r.get("Customer campaign_id"), "baseline_units": r.get("Customer baseline_units"), "promo_units": r.get("Customer promo_units")} for r in wb["Custom_Tab"]]}
result = analyze(
    payload,
    config=cfg_path,
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/merchandising-assortment-planner skills/user-skills/merchandising-assortment-planner skills/retail-store-merchandising skills/user-skills/retail-store-merchandising skills/*; do
  [ -f "$d/scripts/promo_lift_analyzer.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/promo_lift_analyzer.py" --input payload.json --config "$SKILL_DIR/references/config.json" --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/promo_lift_analyzer.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `campaigns`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `summary`, `campaign_evaluations`, `truncation_warnings`; `summary` (`campaigns_evaluated`, `profitable_count`, `margin_destructive_count`, `total_net_incremental_gm_usd`) |
| **Eval & Safety Checks** | Normalizes multi-week baseline to exact promo_days before lift calculation.; Deducts sibling cannibalization and promo execution cost cleanly. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/chain-denominator-seams.md`, `references/traps/bigquery-sap-erp-traps.md`, `references/traps/sharepoint-onedrive-kql-traps.md`.

- Normalize 28-day baseline totals to promo-day daily run rates BEFORE computing lift percentages (`chain-denominator-seams.md`).
- Locking promotional funding extensions or chain-wide markdown campaigns requires Category Merchant Director approval (HITL).
- **`absent-is-not-zero.md`:** Preserve missing/null numerics as `None` (never coerce `'UNKNOWN'`/absent values to `0`) and surface `truncation_warnings` whenever `truncated=True`, `done=False`, or `total_available > count`.
- **`bigquery-sap-erp-traps.md`:** Normalize SAP `TCURX` zero/3-decimal factors (`JPY`/`KRW`), flip `SHKZG='H'` credit signs, invert `TCURR` quoted rates, and restrict BigQuery partitions.
- **`sharepoint-onedrive-kql-traps.md`:** Filter SharePoint/OneDrive drafts (`_ModerationStatus == 0`), avoid unquoted KQL paths, and follow `@odata.nextLink` cursors.

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`campaigns_evaluated`, `profitable_count`, `margin_destructive_count`, `total_net_incremental_gm_usd`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Posting perpetual inventory shrink write-offs impacting store COGS via SAP Retail MCP
  - Issuing supplier OTIF chargeback or detention debit memos via ERP AP MCP
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - Mandatory exclusion of unpolled POS stores (pos_poll_status == MISSING) before shrink/write-off attribution
  - Baseline-adjusted promo net margin ROI guard preventing margin-destructive promotions from passing on gross unit lift
  - Strict contractual OTIF window and dock-wait grace-minute detention math
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Daily Store Shrink & Zero-Scan Watch", cron_expression="30 6 * * *", time_zone="UTC", instruction="Run the morning store shrink and zero-scan phantom inventory sweep via scripts/store_shrink_task_ranker.py and produce prioritized cycle-count lists per store manager.")`.
