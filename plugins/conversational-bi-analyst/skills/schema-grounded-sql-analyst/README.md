# Schema-Grounded SQL Analyst (`schema-grounded-sql-analyst`)

Validates analytical SQL against table metadata for missing partition filters, M:N join fanouts, destructive DDL/DML, and metric denominator mismatches before execution. Deterministic computation executes via [`scripts/sql_safety_and_fanout_checker.py`](scripts/sql_safety_and_fanout_checker.py). Domain guards enforced: Blocks queries missing WHERE filters on required partition_column; Catches M:N join fanout risk when primary keys are omitted from JOIN ON. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Analytics Engineer / BI Developer**: Triggered when validating ad-hoc warehouse queries before running expensive cloud scans; blocks `1:N` fanout joins, enforces partition predicates (`order_date`), and guards against DML writes.
- **Finance & Ops Data Analyst**: Triggered when reconciling BigQuery/Snowflake metric queries against certified semantic definitions; prevents `2x–5x` order-line inflation and estimates scan GB cost prior to dry-run execution.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`schema-grounded-sql-analyst.zip`](../../../../dist/skills/schema-grounded-sql-analyst.zip) (or the full department bundle [`conversational-bi-analyst.zip`](../../../../dist/bundles/conversational-bi-analyst.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` + Customer BYO-MCP (`Semantic BI Layer / Looker MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/schema-grounded-sql-analyst` or `@schema-grounded-sql-analyst`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_json_or_jsonl
from scripts.sql_safety_and_fanout_checker import analyze, render_markdown

raw = Path("customer_input.txt").read_text(encoding="utf-8")
meta_rows = read_json_or_jsonl(Path("customer_metadata.json"))
payload = {"sql": raw, "tables": [{"table_name": r["Source table_name"]} for r in meta_rows]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/conversational-bi-analyst/skills/schema-grounded-sql-analyst/scripts/sql_safety_and_fanout_checker.py \
  --input examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx \
  --config plugins/conversational-bi-analyst/skills/schema-grounded-sql-analyst/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `sql_safety_and_fanout_checker.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` + Customer BYO-MCP (`Semantic BI Layer / Looker MCP server`) via `remote_cli mcp`):** "Check this BigQuery SQL joining `purchase_orders` to `goods_receipts` on `po_id` alone without filtering `posting_date`."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Review Northstar Retail's Connected Sheets BigQuery query estimated at 950 GB scan."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx) and ask: "Validate the SQL warehouse query and table schemas in `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` for partition predicates, 1:N join fanout safety, `SELECT *` anti-patterns, and scan-GB budget before submitting a warehouse run."

## Sample Response

### What You See in Gemini Enterprise Chat

Inspecting the SQL query against the schema metadata in `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` **blocked execution (`sql_gate_passed: False`)** despite being read-only (`is_read_only_safe: True`, `420.0 GB` scan under budget) because `2` partition filters are missing and joining `orders` to `order_items` risks `M:N` row fanout.

- **Missing Partition Filters (`2`):** Both `orders` and `order_items` lack mandatory `WHERE` predicates on `order_date`, triggering full-table scan cost risk.
- **Join Fanout Risk (`1`):** `order_items` omits its composite primary key `['order_id', 'line_id']`; pre-aggregate `order_items` inside a CTE before joining to `orders`.
- **Approval Confirmation Prompt:** Once `WHERE order_date >= ...` and the CTE aggregation are applied, confirm if you would like to run the updated query via your connected `BigQuery` connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx) (`149.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# SQL Safety & Join Fanout Gate

- **Gate Passed:** `False` | **Read-Only Safe:** `True`
- **Missing Partition Filters:** 2 | **M:N Fanout Risks:** 1
- **Estimated Scan:** 420.0 GB (Over Budget: `False`)

- **Partition Guard:** Table `order_items` requires a `WHERE` predicate on `order_date`.
- **Partition Guard:** Table `orders` requires a `WHERE` predicate on `order_date`.
- **Join Fanout Risk:** `order_items` missing primary key(s) `['order_id', 'line_id']` — Pre-aggregate order_items in a CTE or include ['order_id', 'line_id'] in JOIN ON.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily KPI Anomaly Digest` routine via `schedule_task`:

```text
Schedule recurring job "Daily KPI Anomaly Digest" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Run the daily KPI variance and z-score anomaly check using scripts/mix_rate_volume_bridge.py. Decompose revenue/margin changes into exact Volume, Mix, and Rate effects, flag segments exceeding zscore_anomaly_threshold, and save an internal Canvas digest without emailing distribution lists."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `sql`, `estimated_scan_gb`, `tables`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** top-level `sql` text | `tables` requires [`table_name` or `name`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_query_scan_gb` | `number` | `500.0` | Maximum dry-run BigQuery scan GB allowed before explicit confirmation. |

See [`../../README.md`](../../README.md) for the `conversational-bi-analyst` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
