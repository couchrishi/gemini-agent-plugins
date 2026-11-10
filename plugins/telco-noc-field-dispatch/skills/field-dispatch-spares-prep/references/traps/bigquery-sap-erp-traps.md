# Trap Guide: BigQuery & SAP S/4HANA ERP Traps (`bigquery-sap-erp-traps`)

## Part 1: BigQuery Analytical & Cost Guards

1. **Missing Partition Filter (`REQUIRE_PARTITION_FILTER`) & Full-Table Scan Cost Explosion**
   - Querying fact tables (`events_*`, `gl_line_items`, `order_settlements`) without constraining the partition column (`_PARTITIONTIME`, `posting_date`, `event_timestamp`) either fails with `Cannot query over table without a filter over column` or scans petabytes.
   - **Mitigation:** Always verify `partition_column` and `clustering_columns` in table metadata and require a bounded date predicate (`WHERE posting_date BETWEEN ...`) before executing.

2. **Many-to-Many Join Fanout Explosion**
   - Joining `purchase_orders` (`po_id`, `po_item`) to `goods_receipts` (`po_id`) without the `po_item` key—or joining order headers directly to multi-line payment settlements—duplicates header totals `N` times (`SUM(po_amount)` inflates by `3x–10x`).
   - **Mitigation:** Pre-aggregate child tables to the join grain (`GROUP BY po_id, po_item`) inside CTEs BEFORE joining, and assert `SUM(after_join) == SUM(before_join)` via `sql_safety_and_fanout_checker.py`.

## Part 2: SAP S/4HANA OData & Financial Table Traps

1. **`TCURR` / `TCURX` Currency Decimal-Shift Trap (`JPY`, `KRW`, `VND`, `KWD`, `BHD`)**
   - Internally, SAP stores currency amounts in fixed 2-decimal `CURR` fields (`WRBTR`, `DMBTR`, `NETWR`). For **0-decimal currencies** (`JPY`, `KRW`, `TWD` = `CURRDEC=0`), SAP stores `10,000 JPY` as `100.00` in raw database exports (requiring a `100x` multiplier from `TCURX`), and for **3-decimal currencies** (`KWD`, `BHD`, `OMR` = `CURRDEC=3`), `1.250 KWD` is stored as `12.50` (`0.1x` multiplier)!
   - **Mitigation:** Always normalize SAP monetary columns using `TCURX` decimal shift (`factor = 10 ** (2 - currency_decimals)`) whenever reading raw SAP table extracts (`BSEG`, `ACDOCA`, `EKPO`, `RBKP`), and surface normalized vs raw amounts explicitly.

2. **`SHKZG` Debit / Credit Sign Inversion (`'S'` vs `'H'`)**
   - In SAP `ACDOCA` / `BSEG` / `EKBE`, `WRBTR` and `DMBTR` are often exported as **unsigned positive numbers**, while `SHKZG` indicates sign: `'S'` (*Soll* = Debit = `+`) vs `'H'` (*Haben* = Credit = `-`).
   - Summing `DMBTR` without applying `SHKZG == 'H' -> -amount` treats vendor credit memos, reversals, and GR/IR clearing credits as positive spend!
   - **Mitigation:** Apply deterministic sign normalization (`-abs(val)` for `SHKZG == 'H'`, `+abs(val)` for `SHKZG == 'S'`) before reconciliation or GL summation.

3. **GR/IR Clearing Account (`EKBE` `VGABE` `1` vs `2`) & Payment Block (`ZLSPR`)**
   - In Goods Receipt / Invoice Receipt (`GR/IR`) clearing (`WRX`), `EKBE.VGABE = '1'` is Goods Receipt and `VGABE = '2'` (or `RBKP`) is Invoice Receipt. An uninvoiced GR (`GR > IR`) is an **accrued liability**, whereas a blocked invoice (`IR > GR` with `ZLSPR = 'R'` price/qty block) requires procurement/receiving resolution before payment release.
