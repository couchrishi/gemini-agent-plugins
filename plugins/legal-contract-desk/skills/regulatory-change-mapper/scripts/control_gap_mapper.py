#!/usr/bin/env python3
"""Maps regulatory mandates against internal compliance controls and identifies uncovered/stale gaps."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
DEFAULT_CONFIG: dict[str, Any] = {
    "org_configured": False,
    "organization_name": "Standard Baseline Tenant",
    "max_control_evidence_days": 365,
}
SEVERITY_WEIGHT = {"CRITICAL": 4.0, "HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}


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
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    if isinstance(input_arg, (dict, list)):
        if _ENTERPRISE_IO is not None:
            return _ENTERPRISE_IO.apply_column_map_to_payload(
                input_arg,
                skill_id="regulatory-change-mapper",
                column_map=column_map,
                sheet_map=sheet_map,
            )
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {"controls": input_arg}
    if _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.load_enterprise_payload(input_arg, skill_id="regulatory-change-mapper", sheet=sheet, column_map=column_map, sheet_map=sheet_map)
    p = Path(input_arg)
    if p.suffix.lower() == ".csv":
        with p.open("r", encoding="utf-8", newline="") as fh:
            return {"controls": list(csv.DictReader(fh))}
    loaded = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return {"controls": loaded}
    return loaded if isinstance(loaded, dict) else {}


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    return _safe_date(s)


def analyze(
    payload: str | Path | dict[str, Any],
    config: str | Path | dict[str, Any] | None = None,
    as_of_date: str | None = None,

    *,
    sheet: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    cfg, org_configured, banner = load_config(config)
    if _ENTERPRISE_IO is not None:
        eff_col_map, eff_sheet_map = _ENTERPRISE_IO.merge_mappings(cfg, column_map=column_map, sheet_map=sheet_map)
    else:
        eff_col_map, eff_sheet_map = {}, {}
    data = _strip_null_items(load_payload(payload, sheet=sheet, column_map=eff_col_map, sheet_map=eff_sheet_map))
    if _ENTERPRISE_IO is not None:
        schema_diag = _ENTERPRISE_IO.validate_payload_schema(data, skill_id="regulatory-change-mapper")
        if schema_diag["status"] == "SCHEMA_MAPPING_REQUIRED":
            return _ENTERPRISE_IO.build_schema_error_result(
                "regulatory-change-mapper",
                schema_diag,
                org_configured=org_configured,
                banner=banner,
                source=payload,
                config=cfg,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                sheet=sheet,
            )
    as_of = _parse_date(as_of_date or data.get("as_of_date")) or date(2026, 11, 10)
    max_ev_days = _to_int(cfg.get("max_control_evidence_days"), 365)

    articles = _as_list(data.get("articles"))
    controls = _as_list(data.get("controls"))

    # Index controls by mapped article_id and also evaluate individual control freshness
    article_to_controls: dict[str, list[dict[str, Any]]] = {}
    control_health: dict[str, dict[str, Any]] = {}
    for ctrl in controls:
        cid = str(ctrl.get("control_id") or "CTRL-1")
        tested_dt = _parse_date(ctrl.get("last_tested_date"))
        ev_uri = str(ctrl.get("evidence_uri") or "").strip()
        raw_status = str(ctrl.get("control_status") or "UNKNOWN").upper()
        age_days = (as_of - tested_dt).days if tested_dt else None
        missing_ev = tested_dt is None or not ev_uri
        stale_ev = age_days is not None and age_days > max_ev_days

        if raw_status == "NOT_IMPLEMENTED":
            eff_status = "NOT_IMPLEMENTED"
        elif raw_status == "FAILED":
            eff_status = "FAILED"
        elif missing_ev:
            eff_status = "UNVERIFIED_MISSING_EVIDENCE"
        elif stale_ev:
            eff_status = "STALE_EVIDENCE"
        elif raw_status == "PARTIAL":
            eff_status = "PARTIAL"
        else:
            eff_status = "PASSING"

        info = {
            "control_id": cid,
            "domain": str(ctrl.get("domain") or "general").lower(),
            "owner": str(ctrl.get("owner") or "Unassigned"),
            "effective_status": eff_status,
            "evidence_age_days": age_days,
            "last_tested_date": tested_dt.isoformat() if tested_dt else None,
        }
        control_health[cid] = info
        for aid in _as_list(ctrl.get("mapped_articles")):
            article_to_controls.setdefault(str(aid), []).append(info)

    mappings: list[dict[str, Any]] = []
    remediation_queue: list[dict[str, Any]] = []

    for art in articles:
        aid = str(art.get("article_id") or "ART-1")
        reg = str(art.get("regulation") or "Regulation")
        title = str(art.get("title") or aid)
        sev = str(art.get("severity") or "HIGH").upper()
        req_domains = {str(d).lower() for d in _as_list(art.get("required_domains"))}

        linked = _as_list(article_to_controls.get(aid))
        active_impl = [c for c in linked if c["effective_status"] != "NOT_IMPLEMENTED"]
        covered_domains = {c["domain"] for c in active_impl}
        missing_domains = sorted(req_domains - covered_domains)

        bad_controls = [
            c
            for c in linked
            if c["effective_status"] in {"FAILED", "UNVERIFIED_MISSING_EVIDENCE", "STALE_EVIDENCE", "NOT_IMPLEMENTED"}
        ]
        partial_controls = [c for c in linked if c["effective_status"] == "PARTIAL"]

        if not active_impl:
            status = "UNCOVERED_GAP"
        elif bad_controls:
            status = "FAILING_OR_STALE_EVIDENCE"
        elif missing_domains or partial_controls:
            status = "PARTIAL_COVERAGE"
        else:
            status = "COMPLIANT_COVERED"

        base_sev = SEVERITY_WEIGHT.get(sev, 2.0)
        status_mult = {
            "UNCOVERED_GAP": 3.0,
            "FAILING_OR_STALE_EVIDENCE": 2.5,
            "PARTIAL_COVERAGE": 1.5,
            "COMPLIANT_COVERED": 0.0,
        }[status]
        priority_score = round(base_sev * status_mult * (1.0 + 0.25 * len(missing_domains)), 2)

        entry = {
            "article_id": aid,
            "regulation": reg,
            "title": title,
            "severity": sev,
            "coverage_status": status,
            "mapped_control_ids": [c["control_id"] for c in linked],
            "missing_domains": missing_domains,
            "stale_or_unverified_controls": [
                c["control_id"]
                for c in bad_controls
                if c["effective_status"] in {"UNVERIFIED_MISSING_EVIDENCE", "STALE_EVIDENCE"}
            ],
            "remediation_priority_score": priority_score,
        }
        mappings.append(entry)
        if status != "COMPLIANT_COVERED":
            remediation_queue.append(
                {
                    "article_id": aid,
                    "regulation": reg,
                    "severity": sev,
                    "coverage_status": status,
                    "priority_score": priority_score,
                    "action": (
                        f"Implement control for domains {missing_domains}"
                        if status == "UNCOVERED_GAP" or missing_domains
                        else f"Refresh evidence / remediate controls {entry['stale_or_unverified_controls'] or entry['mapped_control_ids']}"
                    ),
                }
            )

    remediation_queue.sort(key=lambda r: -r["priority_score"])
    total_arts = len(mappings)
    compliant_cnt = sum(1 for m in mappings if m["coverage_status"] == "COMPLIANT_COVERED")
    compliance_pct = (compliant_cnt / total_arts * 100.0) if total_arts > 0 else 0.0

    return {
        "skill": "regulatory-change-mapper",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "as_of_date": as_of.isoformat(),
        "summary": {
            "articles_evaluated": total_arts,
            "compliant_count": compliant_cnt,
            "uncovered_gap_count": sum(1 for m in mappings if m["coverage_status"] == "UNCOVERED_GAP"),
            "failing_or_stale_count": sum(
                1 for m in mappings if m["coverage_status"] == "FAILING_OR_STALE_EVIDENCE"
            ),
            "partial_coverage_count": sum(1 for m in mappings if m["coverage_status"] == "PARTIAL_COVERAGE"),
            "overall_compliance_pct": round(compliance_pct, 2),
        },
        "article_mappings": mappings,
        "remediation_queue": remediation_queue,
        "truncation_warnings": _collect_truncation_warnings(data, count=len(controls)),
    }


def render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") == "SCHEMA_MAPPING_REQUIRED" and _ENTERPRISE_IO is not None:
        return _ENTERPRISE_IO.format_schema_mapping_markdown(result)
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    s = result["summary"]
    lines.extend(
        [
            f"# Regulatory Change & Control Gap Matrix (As Of {result['as_of_date']})",
            "",
            f"- **Articles Evaluated:** {s['articles_evaluated']} | **Compliance Rate:** {s['overall_compliance_pct']:.1f}%",
            f"- **Uncovered Gaps:** {s['uncovered_gap_count']} | **Failing/Stale Controls:** {s['failing_or_stale_count']} | "
            f"**Partial:** {s['partial_coverage_count']}",
            "",
            "| Article | Regulation | Severity | Status | Mapped Controls | Missing Domains | Priority |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | ---: |",
        ]
    )
    for m in result["article_mappings"]:
        ctrls = ", ".join(m["mapped_control_ids"]) or "NONE"
        miss = ", ".join(m["missing_domains"]) or "—"
        lines.append(
            f"| `{m['article_id']}` | {m['regulation']} | {m['severity']} | `{m['coverage_status']}` | "
            f"{ctrls} | {miss} | {m['remediation_priority_score']:.1f} |"
        )
    if result.get("truncation_warnings"):
        lines.extend(["", "## Data Completeness & Truncation Warnings"])
        for w in result["truncation_warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map regulatory mandates to compliance controls and find gaps.")
    parser.add_argument("--input", required=True, type=Path, help="Path to regulatory & controls JSON")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name when loading Excel workbooks")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v worksheet/table mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--as-of", type=str, help="Reference ISO date YYYY-MM-DD")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.inspect and _ENTERPRISE_IO is not None:
        diag = _ENTERPRISE_IO.inspect_enterprise_source(
            args.input,
            skill_id="regulatory-change-mapper",
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        out = json.dumps(diag, indent=2, default=str)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0
    result = analyze(args.input, config=args.config, as_of_date=args.as_of, sheet=args.sheet, column_map=args.column_map, sheet_map=args.sheet_map)
    out = json.dumps(result, indent=2) if args.format == "json" else render_markdown(result)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
