---
name: bench-skill-demand-matcher
description: "Matches open project role requirements against available bench talent using deterministic skill overlap %, start-date delay limits, and hourly gross margin ranking Use when staffing sold engagements from bench/roll-off pools or flagging subcontract gaps. Don't use for scoring candidate interview debriefs (use structured-hiring-rubric)."
created_by: gemini-agent-plugins
---

# Bench Skill & Project Demand Matcher

## Domain Context & Objective

Matches open project seats against bench skills, roll-off dates, location overlap, and target role margin. Matches open consulting project demands against bench talent skills, availability, and target margin. Execute calculations via `scripts/talent_bench_matcher.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`.
- **Optional Customer BYO-MCP Servers:** `Workday HRIS & PSA Staffing MCP server` (discover tools via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance:** Pull rate cards, SOW milestone drafts, and RFP requirements from Google Drive/SharePoint plus consultant skill inventories and clearance eligibility from Workday/PSA MCP servers via remote_cli mcp before Python staffing and margin checks.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** `consultants` requires [`consultant_id`; `skills`] | `demands` requires [`role_id`; `required_skills`] (matching top-level keys under `Expected Inputs` below).
- **Inspect Source Shape Directly in Python:** Call `read_xlsx_workbook(path)` (for `.xlsx`), `read_docx(path)` (for `.docx`), `read_csv_tsv(path)` (for `.csv`/`.tsv`), or `read_json_or_jsonl(path)` (for `.json`/`.jsonl`) in `pyrepl` — or inspect connector JSON keys directly — to see exact tab names, headers, and sample rows first.
- **Normalize Mismatched Fields in 5-10 Lines of Python:** Pass standard exports directly to `analyze(path_or_dict, config=cfg_path)`. When customer tab names, column headers, or nested objects differ, reshape rows into a canonical `payload` dict in a few lines of Python (calling `ask_question` only when two customer columns remain genuinely ambiguous).

## Step 3 — Run Deterministic Python Engine in `pyrepl` (or CLI) with Org Baseline Rules

1. Read `references/config.json` using `view_file` before scoring.
2. When `org_configured` is `false`, apply the bundled starter rubrics (`references/baselines/commercial-contract-baseline.md`, `references/baselines/deal-desk-approval-baseline.md`) and stamp the top of every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

| Config Key | Type / Bounds | Default | Operational Role |
| :--- | :--- | :--- | :--- |
| `min_sow_gross_margin_pct` | number, 10.0..80.0 | `30.0` | Target consulting SOW gross margin percentage floor. |
| `critical_margin_floor_pct` | number, 5.0..50.0 | `20.0` | Walk-away Score-9 SOW gross margin floor. |
| `target_offshore_leverage_pct` | number, 0.0..95.0 | `55.0` | Target offshore/nearshore delivery hours share. |
| `max_acceptance_business_days` | integer, 3..30 | `10` | Maximum milestone acceptance SLA before deemed accepted. |
| `min_skill_overlap_pct` | number, 20.0..100.0 | `60.0` | Minimum skill match % for bench candidate shortlisting. |
| `max_start_delay_days` | integer, 0..60 | `14` | Maximum acceptable bench availability delay in days. |

Execute `scripts/talent_bench_matcher.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/bench-skill-demand-matcher"),
            Path("skills/user-skills/bench-skill-demand-matcher"),
            Path("skills/gsi-proposal-ip-factory"),
            Path("skills/user-skills/gsi-proposal-ip-factory"),
            Path("."),
        )
        if (p / "scripts/talent_bench_matcher.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/talent_bench_matcher.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.talent_bench_matcher import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass standard .xlsx/.csv/.json exports directly when headers match canonical names:
# payload = source_path_or_dict
# 2. For unfamiliar customer exports, inspect tabs/headers in pyrepl and shape a clean dict:
# wb = read_xlsx_workbook(Path("customer_export.xlsx"))
# print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})
# payload = {"consultants": [{"consultant_id": r.get("Customer consultant_id"), "skills": r.get("Customer skills")} for r in wb["Custom_Tab"]], "demands": ...}
result = analyze(
    payload,
    config=cfg_path,
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/bench-skill-demand-matcher skills/user-skills/bench-skill-demand-matcher skills/gsi-proposal-ip-factory skills/user-skills/gsi-proposal-ip-factory skills/*; do
  [ -f "$d/scripts/talent_bench_matcher.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/talent_bench_matcher.py" --input payload.json --config "$SKILL_DIR/references/config.json" --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/talent_bench_matcher.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `demands`, `consultants`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `summary`, `role_matches`, `truncation_warnings`; `summary` (`demands_evaluated`, `consultants_screened`, `filled_internally_count`, `external_subcontract_required_count`) |
| **Eval & Safety Checks** | Excludes late bench availability beyond max_start_delay_days.; Flags unfilled roles explicitly as EXTERNAL_SUBCONTRACT_REQUIRED. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/chain-denominator-seams.md`, `references/traps/google-workspace-traps.md`, `references/traps/sharepoint-onedrive-kql-traps.md`, `references/traps/workday-hris-traps.md`.

- Never force-match candidates below `min_skill_overlap_pct` or delayed past `max_start_delay_days`; label gaps `EXTERNAL_SUBCONTRACT_REQUIRED`.
- Confirming consultant project assignments requires Resource Manager and Consultant Lead confirmation (HITL).
- **`absent-is-not-zero.md`:** Preserve missing/null numerics as `None` (never coerce `'UNKNOWN'`/absent values to `0`) and surface `truncation_warnings` whenever `truncated=True`, `done=False`, or `total_available > count`.
- **`chain-denominator-seams.md`:** Keep numerator and denominator populations aligned across fiscal periods, currencies, and cohort windows; guard zero denominators deterministically.
- **`google-workspace-traps.md`:** Query Shared Drives with `supportsAllDrives=true`, read multi-tab Docs via `includeTabsContent=true`, and fetch Sheets with `UNFORMATTED_VALUE`.
- **`sharepoint-onedrive-kql-traps.md`:** Filter SharePoint/OneDrive drafts (`_ModerationStatus == 0`), avoid unquoted KQL paths, and follow `@odata.nextLink` cursors.
- **`workday-hris-traps.md`:** Filter effective-dated rows on `as_of`, separate `CWK` contractors from FTE headcount, and suppress demographic cuts with cell counts `n < 5`.

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`demands_evaluated`, `consultants_screened`, `filled_internally_count`, `external_subcontract_required_count`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Submitting below-margin or high-risk SOW bids for Practice VP / Finance sign-off in PSA MCP
  - Assigning bench consultants or initiating subcontractor requisitions in Workday/PSA MCP
  - Sending client proposal decks or redlined SOWs externally via Gmail or Outlook
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - Onshore/offshore leverage ratio, blended cost/bill rate, and hard minimum gross-margin floor guard
  - Mandatory security-clearance and availability window matching before bench allocation
  - Unlimited-revisions and deemed-acceptance SOW legal/margin risk clause flagging
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Weekly Bench Utilization Digest", cron_expression="0 8 * * 1", time_zone="UTC", instruction="Run the weekly bench-to-demand skill matching check via scripts/talent_bench_matcher.py and surface unfilled roles needing subcontractor sourcing.")`.
