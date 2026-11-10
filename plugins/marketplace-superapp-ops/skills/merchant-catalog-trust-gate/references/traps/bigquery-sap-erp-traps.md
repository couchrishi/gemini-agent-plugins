# Trap Guide: BigQuery & SAP S/4HANA ERP Traps (`bigquery-sap-erp-traps`)

> **Applies to:** Finance P&L variance, AP 3-way match, GR/IR clearing, Procure-to-Pay, BI SQL generation, retail/BOM rollups, and FSI/telco analytics sourced from BigQuery and SAP ERP (`ACDOCA`, `BSEG`, `EKPO`, `EKBE`, `RBKP`, `TCURX`).

## 1. Executive Summary Matrix

| Trap ID | System | Failure Pattern | Root Schema Cause | Deterministic Guard |
| :--- | :--- | :--- | :--- | :--- |
| `TRAP-BQ-01` | BigQuery | Missing partition filter | `REQUIRE_PARTITION_FILTER` rejection or multi-TB full scan | Enforce bounded partition predicate (`posting_date`, `_PARTITIONTIME`) & `max_query_scan_gb` |
| `TRAP-BQ-02` | BigQuery | Many-to-many join fanout | Joining `po_header` to `gr_lines` without unique grain / CTE rollup | Pre-aggregate child tables inside CTEs; verify cardinality before join |
| `TRAP-BQ-03` | BigQuery | `NULL` / `COUNT(*)` skew | `AVG()` skips `NULL` while `COUNT(*)` counts `NULL` rows | Inspect null rates (`max_null_rate_warn_pct`); use explicit `COUNT(col)` & `COALESCE` guards |
| `TRAP-SAP-01` | SAP S/4HANA | `TCURX` decimal shift error | `CURR` columns (`WRBTR`, `DMBTR`) stored as 2-decimal fixed ints/floats | Scale by `10 ** (2 - currency_decimals)` (`100x` for `JPY`/`KRW`; `0.1x` for `KWD`/`BHD`) |
| `TRAP-SAP-02` | SAP S/4HANA | `SHKZG` sign inversion | Unsigned `DMBTR`/`WRBTR`; `'H'` credits exported as positive numbers | Map `SHKZG == 'H' -> -abs(amount)`, `SHKZG == 'S' -> +abs(amount)` |
| `TRAP-SAP-03` | SAP S/4HANA | `EKBE.VGABE` GR/IR & `ZLSPR` | `VGABE='1'` (GR), `VGABE='2'` (IR), and `ZLSPR` payment blocks conflated | Separate GR vs IR ledgers; block payment on `ZLSPR` or `IR > GR` (`MISSING_GRN`) |

## 2. Part 1 — BigQuery SQL Cost & Cardinality Traps

### Case A — Many-to-Many Join Fanout (`3x–10x` Revenue Inflation)

- **Unsafe Query:**
  ```sql
  SELECT o.order_id, SUM(i.amount) AS order_total
  FROM analytics.orders o
  JOIN analytics.order_items i ON o.customer_id = i.customer_id
  GROUP BY 1;
  ```
- **Failure Mechanism:** Joining `orders` (`primary_keys: ["order_id"]`) to `order_items` (`primary_keys: ["order_id", "line_id"]`) on shared non-unique `customer_id` triggers a Cartesian product across every historical order a customer has placed. If Customer `C-42` placed `6` orders averaging `$5,000`, total revenue jumps **`6x` (`$30,000 -> $180,000`)**.
- **Correct Pre-Aggregated Pattern:**
  ```sql
  WITH items_by_order AS (
    SELECT order_id, SUM(amount) AS net_item_amount
    FROM analytics.order_items
    WHERE order_date BETWEEN @start_date AND @end_date
    GROUP BY order_id
  )
  SELECT o.order_id, COALESCE(i.net_item_amount, 0) AS order_total
  FROM analytics.orders o
  LEFT JOIN items_by_order i ON o.order_id = i.order_id
  WHERE o.order_date BETWEEN @start_date AND @end_date;
  ```
- Always validate join predicates and partition filters through `sql_safety_and_fanout_checker.py` before running warehouse SQL.

### Case B — `REQUIRE_PARTITION_FILTER` & Dry-Run Scan Cost Guards

- BigQuery fact tables (`acdoca_line_items`, `pos_transactions`, `telemetry_events`) enforce `require_partition_filter = true`. Unconstrained filters such as `DATE(posting_ts) = '2026-11-10'` disable partition pruning and either fail execution or scan petabytes.
- Always filter raw partition columns directly (`posting_date >= '2026-11-01' AND posting_date <= '2026-11-10'`) and compare dry-run `estimated_scan_gb` against `max_query_scan_gb` (`500 GB` baseline).

## 3. Part 2 — SAP S/4HANA OData & Table Export Traps

### Case C — `TCURX` Zero-Decimal & Three-Decimal Currency Shift (`100x` & `10x` Distortion)

- **Schema Root Cause:** SAP stores currency values in fixed 2-decimal `CURR` database columns (`BSEG.DMBTR`, `ACDOCA.WSL`, `EKPO.NETPR`, `RBKP.RMWWR`). SAP table `TCURX` defines exceptions wherever `CURRDEC != 2`:
  - **0-Decimal Currencies (`CURRDEC = 0`):** `JPY`, `KRW`, `VND`, `CLP`, `ISK`. Raw DB stores `100` units lower than face value (`150,000 JPY` stored as `1500.00`).
  - **3-Decimal Currencies (`CURRDEC = 3`):** `KWD`, `BHD`, `OMR`, `TND`, `JOD`. Raw DB stores `10x` higher (`1.250 KWD` stored as `12.50`).
- **Before-vs-After Walkthrough (`Cymbal Tokyo Invoice INV-JP-01`):**
  - Contractual PO Line: `10` units @ `150,000 JPY` (`1,500,000 JPY` = `$10,000.00 USD` at `fx_rate = 0.006667`).
  - Raw SAP Table Export (`sap_raw_encoding = True`): `unit_price = 1500.00`.
  - **Without `TCURX` Shift:** Script treats `1500.00 JPY` as `$10.00/unit` (`$100.00` total) — fabricating a **`-99.0%` unit price variance** and blocking valid supplier payment!
  - **With `TCURX` Normalization:** `1500.00 * 10 ** (2 - 0) = 150,000 JPY` (`$10,000.00 USD`), yielding `0.00%` price variance and clean `MATCHED_READY_FOR_HITL` status.

### Case D — `SHKZG` Debit / Credit Indicator Inversion (`'S'` vs `'H'`)

- SAP exports frequently store `WRBTR` / `DMBTR` as **unsigned positive floats** while carrying debit/credit polarity in `SHKZG`:
  - `'S'` (*Soll* = Debit) -> `+abs(amount)`
  - `'H'` (*Haben* = Credit / Vendor Credit Memo / GR Reversal) -> `-abs(amount)`
- **Before-vs-After Walkthrough:** Supplier `V-US-01` submits a `$12,000` Debit Invoice (`SHKZG='S'`) and a matching `$12,000` Credit Memo (`SHKZG='H'`, `unit_price=12000`). Ignoring `SHKZG` sums AP outflow to **`+$24,000`** instead of **`$0.00` net liability**!

### Case E — GR/IR Clearing (`EKBE.VGABE`) & Payment Block (`ZLSPR`)

- In SAP PO History (`EKBE`), `VGABE = '1'` records Goods Receipts (`GR`), `VGABE = '2'` records Invoice Receipts (`IR`), and `VGABE = '3'` tracks Subsequent Debit/Credit adjustments.
- `GR > IR` represents an **accrued uninvoiced liability** tracked in `gr_ir_clearing_orchestrator` (`gr_ir_aging_threshold_days = 60`); `IR > GR` flags missing receipt verification (`MISSING_GRN`). Never auto-release invoices bearing SAP payment blocks (`ZLSPR = 'R'`, `'A'`, `'B'`).

## 4. Programmatic Assertion Rules

```python
DEFAULT_DECIMALS = {"JPY": 0, "KRW": 0, "VND": 0, "CLP": 0, "ISK": 0, "KWD": 3, "BHD": 3, "OMR": 3}

def normalize_sap_amount(
    raw_amount: float, currency: str, *, sap_raw_encoding: bool, shkzg: str | None, decimals_map: dict[str, int]
) -> float:
    curr = (currency or "USD").upper().strip()
    dec = int(decimals_map.get(curr, DEFAULT_DECIMALS.get(curr, 2)))
    scaled = raw_amount * (10 ** (2 - dec)) if sap_raw_encoding else raw_amount
    return -abs(scaled) if (shkzg or "").strip().upper() == "H" else scaled
```

1. **Always check `sap_raw_encoding` and `shkzg` together:** Reconcile credit memos into `CREDIT_MEMO_POSTED` without distorting unmatched-invoice exception counts.
2. **Require BigQuery dry-run + grain validation prior to execution:** Reject Cartesian joins lacking `GROUP BY` CTE pre-aggregation and unpartitioned full-table scans.

## 5. SAP Table, Field & Scale Reference Table

| SAP Object | Critical Fields | Common Failure Trap | Mandatory Python Guard |
| :--- | :--- | :--- | :--- |
| **`ACDOCA` / `BSEG`** | `DMBTR`, `WRBTR`, `WAERS`, `SHKZG` | Positive floats even for credits; local vs doc currency mixed | Flip sign on `SHKZG='H'`; normalize FX against `waers` |
| **`RBKP` / `RSEG`** | `RMWWR`, `WAERS`, `ZLSPR`, `BELNR` | Blocked invoices (`ZLSPR='R'/'A'`) or credit indicators skipped | Enforce `payment_hold=True` on blocked flags |
| **`EKPO` / `EKKO`** | `EBELN`, `EBELP`, `NETPR`, `MENGE` | Currency decimal shift (`TCURX`) differs from 2-decimal UI assumption | Scale `10 ** (2 - CURRDEC)` when `sap_raw_encoding=True` |
| **`EKBE`** | `VGABE`, `SHKZG`, `MENGE`, `DMBTR` | GR (`1`) and IR (`2`) summed without grouping reversals (`H`) | Net `S`/`H` per `(EBELN, EBELP, VGABE)` prior to 3-way compare |
| **`TCURX` / `TCURR`** | `CURRKEY`, `CURRDEC`, `UKURS` | `JPY`/`KRW` (`0` dec) vs `KWD`/`BHD` (`3` dec) off by `10x–100x` | Maintain explicit decimal override map in payload/config |

## 6. Warehouse & ERP Verification Checklist

1. Verify `posting_date` / `_PARTITIONTIME` literal bounds match BigQuery clustering and partitioning keys.
2. Confirm `SUM(line_items)` before and after joining PO/GR/IR tables reconciles within `$0.01`.
3. Separate negative SAP `'H'` credit rows (`CREDIT_MEMO_POSTED`) from `PRICE_VARIANCE` or `MISSING_GRN` holds.
4. Keep raw SAP table values logged alongside scaled USD amounts for audit traceability.
