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


def load_config(config_arg: str | Path | dict[str, Any] | None) -> tuple[dict[str, Any], bool, str]:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(config_arg, dict):
        cfg.update(config_arg)
    elif config_arg is not None:
        p = Path(config_arg)
        if p.is_file():
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
    org_cfg = bool(cfg.get("org_configured", False))
    return cfg, org_cfg, ("" if org_cfg else BASELINE_BANNER)


def load_payload(input_arg: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_arg, dict):
        return input_arg
    return json.loads(Path(input_arg).read_text(encoding="utf-8"))


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = load_payload(payload)
    cfg, org_configured, banner = load_config(config)

    rows = data.get("sku_store_records") or data.get("records") or []
    trunc_warnings: list[str] = []
    if data.get("truncated"):
        trunc_warnings.append("POS/WMS query returned truncated results; shrink ranking covers partial store subset only.")

    zero_days_thresh = int(cfg.get("zero_scan_days_threshold", 5))
    min_phantom_qty = int(cfg.get("min_book_qty_for_phantom", 4))
    high_shrink_usd = float(cfg.get("high_shrink_usd_threshold", 250.0))

    store_shrink: dict[str, dict[str, Any]] = {}
    sku_anomalies: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    unpolled_skips = 0

    for row in rows:
        store_id = str(row.get("store_id") or "STR-UNK")
        sku = str(row.get("sku") or row.get("item_id") or "SKU-UNK")
        desc = str(row.get("description") or sku)
        book_qty = int(row.get("book_on_hand_qty") or 0)
        counted_qty = row.get("physical_count_qty")
        unit_cost = float(row.get("unit_cost_usd") or 0.0)
        days_since_scan = int(row.get("days_since_last_pos_scan") or 0)
        expected_daily_units = float(row.get("expected_daily_sales_units") or 0.0)
        pos_status = str(row.get("pos_poll_status") or "POLLED").upper()
        eas_protected = bool(row.get("eas_tag_required", False))

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
        "truncation_warnings": trunc_warnings,
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
    parser.add_argument("--config", type=Path, help="Optional config.json path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    result = analyze(args.input, config=args.config)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
