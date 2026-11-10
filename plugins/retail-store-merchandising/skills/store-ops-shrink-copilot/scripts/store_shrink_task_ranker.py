#!/usr/bin/env python3
"""Ranks retail store shrink $ loss, phantom inventory (zero-scan), and prioritized associate execution tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "zero_scan_days_threshold": 5,
    "min_book_qty_for_phantom": 4,
    "high_shrink_usd_threshold": 250.0,
    "max_stores_per_batch": 200,
}


def _to_float(val: Any, default: Any = 0.0) -> float:
    num = _to_opt_float(val)
    if num is not None:
        return num
    d = _to_opt_float(default)
    return d if d is not None else 0.0


def _to_opt_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        num = float(val)
        return None if (num != num or abs(num) == float("inf")) else num
    s = str(val).strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    for ch in (",", "$", "€", "£", "¥", "%"):
        s = s.replace(ch, "")
    s = s.strip()
    if not s:
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    if num != num or abs(num) == float("inf"):
        return None
    return -num if neg else num


def _to_int(val: Any, default: Any = 0) -> int:
    num = _to_opt_float(val)
    if num is None:
        num = _to_opt_float(default)
    if num is None:
        return 0
    try:
        return int(round(num))
    except (ValueError, TypeError, OverflowError):
        return 0


def _to_opt_int(val: Any) -> int | None:
    num = _to_opt_float(val)
    if num is None:
        return None
    try:
        return int(round(num))
    except (ValueError, TypeError, OverflowError):
        return None


def _safe_date(val: Any) -> Any:
    import datetime as _dt
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val.date()
    if isinstance(val, _dt.date):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _safe_datetime(val: Any) -> Any:
    import datetime as _dt
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val if val.tzinfo else val.replace(tzinfo=_dt.timezone.utc)
    if isinstance(val, _dt.date):
        return _dt.datetime(val.year, val.month, val.day, tzinfo=_dt.timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _strip_null_items(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_strip_null_items(x) for x in obj if x is not None]
    if isinstance(obj, dict):
        return {k: _strip_null_items(v) for k, v in obj.items()}
    return obj


def _as_list(val: Any, default: list[Any] | None = None) -> list[Any]:
    if isinstance(val, list):
        return [x for x in val if x is not None]
    if val is None:
        return list(default) if default is not None else []
    if isinstance(val, (tuple, set)):
        return [x for x in val if x is not None]
    return list(default) if default is not None else []


def _as_dict_list(val: Any) -> list[dict[str, Any]]:
    return [item for item in _as_list(val) if isinstance(item, dict)]


def _as_dict(val: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    return dict(default) if default is not None else {}


def _collect_truncation_warnings(
    data: dict[str, Any],
    *,
    count: int | None = None,
    existing: list[str] | None = None,
) -> list[str]:
    warnings = [str(w) for w in (existing or []) if w]
    meta = _as_dict(data.get("metadata"))
    trunc = bool(data.get("truncated")) or bool(meta.get("truncated"))
    if (
        data.get("done") is False
        or meta.get("done") is False
        or bool(data.get("next_page_token") or data.get("nextPageToken"))
        or bool(meta.get("next_page_token") or meta.get("nextPageToken"))
    ):
        trunc = True
    total_avail = data.get("total_available")
    if total_avail is None:
        total_avail = data.get("totalSize")
    if total_avail is None:
        total_avail = meta.get("total_available")
    if total_avail is None:
        total_avail = meta.get("totalSize")
    avail_int = _to_opt_int(total_avail)
    if avail_int is not None and count is not None and avail_int > count:
        trunc = True
    if trunc and not warnings:
        if avail_int is not None and count is not None:
            warnings.append(
                f"TRUNCATION_WARNING: Returned {count} of {avail_int} available records; totals and counts represent a partial dataset only."
            )
        else:
            warnings.append(
                "TRUNCATION_WARNING: Upstream feed reported truncated or paginated output; totals and counts represent a partial dataset only."
            )
    return warnings


def _load_enterprise_io() -> Any | None:
    try:
        from scripts import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    try:
        import enterprise_io as _eio  # type: ignore

        return _eio
    except ImportError:
        pass
    eio_path = Path(__file__).resolve().parent / "enterprise_io.py"
    if eio_path.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("enterprise_io", eio_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


_ENTERPRISE_IO = _load_enterprise_io()


def _to_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"true", "yes", "y", "1", "on"}:
        return True
    if s in {"false", "no", "n", "0", "off", ""}:
        return False if s else default
    return bool(s)


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            _loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(_loaded, dict):
                cfg.update(_loaded)
    org_cfg = _to_bool(cfg.get("org_configured"), False)
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(
    input_arg: str | Path | dict[str, Any] | list[dict[str, Any]],
    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"sku_store_records": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="store-ops-shrink-copilot", sheet=sheet)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"sku_store_records": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"sku_store_records": loaded}
    return loaded if isinstance(loaded, dict) else {}


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,

    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    data = _strip_null_items(load_payload(payload, sheet=sheet))
    cfg, org_configured, banner = load_config(config)

    rows = data.get("sku_store_records") or data.get("records") or []
    trunc_warnings: list[str] = []
    if data.get("truncated"):
        trunc_warnings.append("POS/WMS query returned truncated results; shrink ranking covers partial store subset only.")

    zero_days_thresh = _to_int(cfg.get("zero_scan_days_threshold"), 5)
    min_phantom_qty = _to_int(cfg.get("min_book_qty_for_phantom"), 4)
    high_shrink_usd = _to_float(cfg.get("high_shrink_usd_threshold"), 250.0)

    store_shrink: dict[str, dict[str, Any]] = {}
    sku_anomalies: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    unpolled_skips = 0

    for row in rows:
        store_id = str(row.get("store_id") or "STR-UNK")
        sku = str(row.get("sku") or row.get("item_id") or "SKU-UNK")
        desc = str(row.get("description") or sku)
        book_qty = _to_int(row.get("book_on_hand_qty"), 0)
        counted_qty = _to_opt_int(row.get("physical_count_qty"))
        unit_cost = _to_float(row.get("unit_cost_usd"), 0.0)
        days_since_scan = _to_int(row.get("days_since_last_pos_scan"), 0)
        expected_daily_units = _to_float(row.get("expected_daily_sales_units"), 0.0)
        pos_status = str(row.get("pos_poll_status") or "POLLED").upper()
        eas_protected = _to_bool(row.get("eas_tag_required"), False)

        st = store_shrink.setdefault(
            store_id,
            {
                "store_id": store_id,
                "store_name": str(row.get("store_name") or store_id),
                "shrink_units": 0,
                "shrink_usd": 0.0,
                "phantom_skus": 0,
                "negative_on_hand_skus": 0,
                "unpolled_skipped": 0,
            },
        )

        # Absent-is-not-zero guard: never classify unpolled POS stores as phantom inventory
        if pos_status != "POLLED":
            unpolled_skips += 1
            st["unpolled_skipped"] += 1
            continue

        shrink_usd = 0.0
        shrink_units = 0
        if counted_qty is not None:
            variance = book_qty - int(counted_qty)
            if variance > 0:
                shrink_units = variance
                shrink_usd = round(variance * unit_cost, 2)
                st["shrink_units"] += shrink_units
                st["shrink_usd"] = round(st["shrink_usd"] + shrink_usd, 2)

        anomaly_type: str | None = None
        action: str | None = None
        priority_score = shrink_usd

        if book_qty < 0:
            anomaly_type = "NEGATIVE_LEDGER_CORRUPTION"
            st["negative_on_hand_skus"] += 1
            action = "Correct negative perpetual inventory receipt/scan mismatch"
            priority_score = max(priority_score, abs(book_qty) * unit_cost + 50.0)
        elif (
            book_qty >= min_phantom_qty
            and days_since_scan >= zero_days_thresh
            and expected_daily_units >= 0.5
        ):
            anomaly_type = "PHANTOM_INVENTORY_ZERO_SCAN"
            st["phantom_skus"] += 1
            est_lost_sales_usd = round(expected_daily_units * days_since_scan * unit_cost, 2)
            action = "Execute shelf physical walk + backroom pull or zero-out PI"
            priority_score = max(priority_score, est_lost_sales_usd + book_qty * unit_cost)
        elif shrink_usd >= high_shrink_usd:
            anomaly_type = "HIGH_DOLLAR_SHRINK"
            action = "Verify EAS tagging compliance & lockup planogram" if eas_protected else "Audit receiving log & cycle count SKU"

        if anomaly_type:
            sku_anomalies.append(
                {
                    "store_id": store_id,
                    "sku": sku,
                    "description": desc,
                    "anomaly_type": anomaly_type,
                    "book_on_hand_qty": book_qty,
                    "physical_count_qty": counted_qty,
                    "days_since_last_pos_scan": days_since_scan,
                    "shrink_usd": shrink_usd,
                    "priority_score": round(priority_score, 2),
                    "recommended_action": action,
                }
            )
            tasks.append(
                {
                    "store_id": store_id,
                    "sku": sku,
                    "task_type": anomaly_type,
                    "action": action,
                    "impact_score_usd": round(priority_score, 2),
                }
            )

    sku_anomalies.sort(key=lambda x: -x["priority_score"])
    tasks.sort(key=lambda x: -x["impact_score_usd"])
    ranked_stores = sorted(store_shrink.values(), key=lambda x: -x["shrink_usd"])

    total_shrink_usd = round(sum(s["shrink_usd"] for s in ranked_stores), 2)
    return {
        "skill": "store-ops-shrink-copilot",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "summary": {
            "records_scanned": len(rows),
            "stores_covered": len(ranked_stores),
            "total_shrink_usd": total_shrink_usd,
            "phantom_inventory_count": sum(1 for a in sku_anomalies if a["anomaly_type"] == "PHANTOM_INVENTORY_ZERO_SCAN"),
            "negative_ledger_count": sum(1 for a in sku_anomalies if a["anomaly_type"] == "NEGATIVE_LEDGER_CORRUPTION"),
            "high_shrink_sku_count": sum(1 for a in sku_anomalies if a["anomaly_type"] == "HIGH_DOLLAR_SHRINK"),
            "unpolled_pos_skipped": unpolled_skips,
        },
        "store_rankings": ranked_stores,
        "sku_anomalies": sku_anomalies,
        "prioritized_store_tasks": tasks,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(rows), existing=trunc_warnings),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            "# Store Shrink, Phantom Inventory & Associate Task Plan",
            "",
            f"- **Stores:** {s['stores_covered']} | **Total Physical Shrink:** ${s['total_shrink_usd']:,.2f} | "
            f"**Phantom Inventory (Zero-Scan):** {s['phantom_inventory_count']} | **Negative Ledger:** {s['negative_ledger_count']}",
            "",
        ]
    )
    if s["unpolled_pos_skipped"]:
        lines.append(
            f"> Skipped {s['unpolled_pos_skipped']} record(s) with non-POLLED POS status to prevent false phantom-inventory flags."
        )
        lines.append("")
    lines.extend(
        [
            "| Priority | Store | SKU | Anomaly Type | Book Qty | Zero-Scan Days | Shrink $ | Action |",
            "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- |",
        ]
    )
    for idx, item in enumerate(result["sku_anomalies"][:25], 1):
        lines.append(
            f"| {idx} | `{item['store_id']}` | `{item['sku']}` {item['description']} | `{item['anomaly_type']}` | "
            f"{item['book_on_hand_qty']} | {item['days_since_last_pos_scan']} | ${item['shrink_usd']:,.2f} | {item['recommended_action']} |"
        )
    if result["truncation_warnings"]:
        lines.extend(["", "**Truncation Warnings:** " + "; ".join(result["truncation_warnings"])])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze store shrink, phantom inventory, and associate tasks.")
    parser.add_argument("--input", required=True, type=Path, help="Path to SKU/store telemetry JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config, sheet=args.sheet)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
