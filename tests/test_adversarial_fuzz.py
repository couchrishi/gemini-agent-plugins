"""Adversarial fuzz & resilience tests across all 60 deterministic skill computation engines."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_all_scripts as tas  # noqa: E402

BASELINE_BANNER = tas.BASELINE_BANNER
CATALOG = tas.CATALOG


def _all_catalog_skills() -> list[tuple[str, str, Path]]:
    rows: list[tuple[str, str, Path]] = []
    for plugin in CATALOG["plugins"]:
        for skill in plugin["skills"]:
            rows.append((plugin["id"], skill["id"], ROOT / skill["path"] / skill["script"]))
    return rows


def _mutate_str_numbers(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _mutate_str_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mutate_str_numbers(x) for x in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return f"{obj:,}.00"
    if isinstance(obj, float):
        return f"${obj:,.2f}"
    return obj


def _mutate_none_scalars(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _mutate_none_scalars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mutate_none_scalars(x) for x in obj]
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return None
    return obj


def _mutate_zero_scalars(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _mutate_zero_scalars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mutate_zero_scalars(x) for x in obj]
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return 0
    return obj


def _mutate_bad_dates(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if (
                isinstance(v, str)
                and any(tok in k for tok in ("date", "_at", "_time", "timestamp"))
                and any(c.isdigit() for c in v)
            ):
                out[k] = "NOT-A-DATE"
            else:
                out[k] = _mutate_bad_dates(v)
        return out
    if isinstance(obj, list):
        return [_mutate_bad_dates(x) for x in obj]
    return obj


def _mutate_nested_none(obj: Any, depth: int = 0) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if depth >= 1 and isinstance(v, (dict, list)):
                out[k] = None
            else:
                out[k] = _mutate_nested_none(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [_mutate_nested_none(x, depth) for x in obj]
    return obj


def _mutate_sparse_items(obj: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in obj.items():
        if isinstance(v, list):
            out[k] = [{}]
        elif isinstance(v, dict):
            out[k] = {}
        else:
            out[k] = v
    return out


def _assert_valid_output(skill_id: str, res: dict[str, Any], md: str) -> None:
    assert isinstance(res, dict)
    assert res["skill"] == skill_id
    assert isinstance(res.get("summary"), dict)
    assert isinstance(res.get("truncation_warnings"), list)
    assert isinstance(md, str) and len(md.strip()) > 20


@pytest.mark.parametrize("plugin_id,skill_id,script_path", _all_catalog_skills(), ids=lambda v: str(v))
def test_adversarial_empty_zero_null_and_sparse_inputs(
    plugin_id: str, skill_id: str, script_path: Path
) -> None:
    mod = tas._load_module(script_path, f"fuzz_empty_{skill_id.replace('-', '_')}")
    base_payload = copy.deepcopy(tas.SKILL_PAYLOADS[skill_id])
    cfg_path = script_path.parent.parent / "references" / "config.json"

    # 1. Completely empty dict {}
    res_empty = mod.analyze({}, config=cfg_path)
    _assert_valid_output(skill_id, res_empty, mod.render_markdown(res_empty))

    # 2. All top-level lists/dicts emptied [] / {}
    emptied = {
        k: ([] if isinstance(v, list) else ({} if isinstance(v, dict) else v))
        for k, v in base_payload.items()
    }
    res_emptied = mod.analyze(emptied, config=cfg_path)
    _assert_valid_output(skill_id, res_emptied, mod.render_markdown(res_emptied))

    # 3. Every scalar set to 0 (zero-denominator guard)
    res_zero = mod.analyze(_mutate_zero_scalars(base_payload), config=cfg_path)
    _assert_valid_output(skill_id, res_zero, mod.render_markdown(res_zero))

    # 4. Sparse empty dict elements [{}] and literal null list elements [None]
    res_sparse = mod.analyze(_mutate_sparse_items(base_payload), config=cfg_path)
    _assert_valid_output(skill_id, res_sparse, mod.render_markdown(res_sparse))

    list_none_payload = {
        k: ([None] if isinstance(v, list) else v) for k, v in base_payload.items()
    }
    res_list_none = mod.analyze(list_none_payload, config=cfg_path)
    _assert_valid_output(skill_id, res_list_none, mod.render_markdown(res_list_none))

    # 5. Each top-level collection set explicitly to None
    for k, v in base_payload.items():
        if isinstance(v, (list, dict)):
            null_payload = copy.deepcopy(base_payload)
            null_payload[k] = None
            res_null = mod.analyze(null_payload, config=cfg_path)
            _assert_valid_output(skill_id, res_null, mod.render_markdown(res_null))


@pytest.mark.parametrize("plugin_id,skill_id,script_path", _all_catalog_skills(), ids=lambda v: str(v))
def test_adversarial_malformed_strings_null_scalars_and_bad_dates(
    plugin_id: str, skill_id: str, script_path: Path
) -> None:
    mod = tas._load_module(script_path, f"fuzz_types_{skill_id.replace('-', '_')}")
    base_payload = copy.deepcopy(tas.SKILL_PAYLOADS[skill_id])

    # 1. Formatted string numbers ("$12,500.00", "1,000.00")
    res_str = mod.analyze(_mutate_str_numbers(base_payload))
    _assert_valid_output(skill_id, res_str, mod.render_markdown(res_str))

    # 2. Null scalars everywhere
    res_none = mod.analyze(_mutate_none_scalars(base_payload))
    _assert_valid_output(skill_id, res_none, mod.render_markdown(res_none))

    # 3. Invalid ISO date strings ("NOT-A-DATE")
    res_date = mod.analyze(_mutate_bad_dates(base_payload))
    _assert_valid_output(skill_id, res_date, mod.render_markdown(res_date))

    # 4. Nested sub-lists / sub-dicts set to None
    res_nested = mod.analyze(_mutate_nested_none(base_payload))
    _assert_valid_output(skill_id, res_nested, mod.render_markdown(res_nested))


@pytest.mark.parametrize("plugin_id,skill_id,script_path", _all_catalog_skills(), ids=lambda v: str(v))
def test_adversarial_truncation_warnings_and_config_toggle(
    plugin_id: str, skill_id: str, script_path: Path, tmp_path: Path
) -> None:
    mod = tas._load_module(script_path, f"fuzz_trunc_{skill_id.replace('-', '_')}")
    base_payload = copy.deepcopy(tas.SKILL_PAYLOADS[skill_id])

    # 1. Top-level truncated=True & metadata.truncated=True & done=False
    for variant in (
        {**copy.deepcopy(base_payload), "truncated": True, "total_available": 9999},
        {**copy.deepcopy(base_payload), "done": False},
        {**copy.deepcopy(base_payload), "metadata": {"truncated": True, "total_available": 9999}},
    ):
        res_t = mod.analyze(variant)
        warnings = res_t.get("truncation_warnings") or []
        assert len(warnings) >= 1, f"{skill_id} omitted truncation_warnings for truncated payload"
        md_t = mod.render_markdown(res_t)
        assert warnings[0][:20] in md_t, f"{skill_id} render_markdown omitted truncation warning"

    # 2. Explicit config toggle + nonexistent config fallback safety
    res_missing_cfg = mod.analyze(base_payload, config=tmp_path / "does_not_exist.json")
    assert res_missing_cfg["baseline_mode"] == "STANDARD_BASELINE"
    assert res_missing_cfg["baseline_banner"] == BASELINE_BANNER
    assert BASELINE_BANNER in mod.render_markdown(res_missing_cfg)

    res_org = mod.analyze(
        base_payload,
        config={"org_configured": True, "organization_name": "Meridian BioPharma"},
    )
    assert res_org["baseline_mode"] == "ORG_CONFIGURED"
    assert res_org["baseline_banner"] == ""
    assert BASELINE_BANNER not in mod.render_markdown(res_org)


@pytest.mark.parametrize("plugin_id,skill_id,script_path", _all_catalog_skills(), ids=lambda v: str(v))
def test_all_60_cli_executions_from_external_cwd(
    plugin_id: str, skill_id: str, script_path: Path, tmp_path: Path
) -> None:
    """Verify every skill CLI runs cleanly via python3 from an unrelated CWD (/tmp / tmp_path)."""
    in_path = tmp_path / f"{skill_id}.json"
    in_path.write_text(json.dumps(tas.SKILL_PAYLOADS[skill_id]), encoding="utf-8")
    cfg_path = script_path.parent.parent / "references" / "config.json"

    proc_json = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(in_path),
            "--config",
            str(cfg_path),
            "--format",
            "json",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(proc_json.stdout)
    assert parsed["skill"] == skill_id
    assert parsed["baseline_banner"] == BASELINE_BANNER


def test_absent_is_not_zero_and_numeric_coercion_safety_guards() -> None:
    """Verify malformed string safety fields never coerce dangerously into clean 0 values."""
    # EHS gas test with unparseable 'UNKNOWN' LEL must remain STOP_WORK_BLOCKED (never coerce to 0.0% LEL!)
    ehs_path = next(sp for _, sid, sp in _all_catalog_skills() if sid == "ehs-safety-permit-auditor")
    ehs_mod = tas._load_module(ehs_path, "fuzz_ehs_guard")
    ehs_res = ehs_mod.analyze(
        {
            "as_of_date": "2026-11-10",
            "permits": [
                {
                    "permit_id": "PTW-BAD-GAS",
                    "work_type": "confined_space",
                    "work_date": "2026-11-10",
                    "worker_cert_valid_until": "2027-01-01",
                    "issuer_signed": True,
                    "loto_isolated": True,
                    "gas_test_o2_pct": "20.9%",
                    "gas_test_lel_pct": "UNKNOWN",
                    "gas_test_age_mins": "15",
                }
            ],
        }
    )
    assert ehs_res["permit_audits"][0]["permit_status"] == "STOP_WORK_BLOCKED"

    # Contract LoL unparseable 'unknown' cap_months must stay score >= 3 (absent != 0 months blocker confusion)
    con_path = next(sp for _, sid, sp in _all_catalog_skills() if sid == "contract-playbook-redliner")
    con_mod = tas._load_module(con_path, "fuzz_con_guard")
    con_res = con_mod.analyze(
        {
            "clauses": [
                {
                    "clause_id": "CL-AMB",
                    "clause_family": "limitation_of_liability",
                    "metrics": {"lol_cap_months": "TBD"},
                    "text": "Liability shall follow standard commercial schedule.",
                }
            ]
        }
    )
    assert con_res["clause_evaluations"][0]["risk_score"] >= 3

    # AP 3-way match accepts formatted currency strings cleanly
    ap_path = next(sp for _, sid, sp in _all_catalog_skills() if sid == "ap-three-way-match")
    ap_mod = tas._load_module(ap_path, "fuzz_ap_guard")
    ap_res = ap_mod.analyze(_mutate_str_numbers(tas.SKILL_PAYLOADS["ap-three-way-match"]))
    assert ap_res["summary"]["invoices_evaluated"] >= 4


@pytest.mark.parametrize("plugin_id,skill_id,script_path", _all_catalog_skills(), ids=lambda v: str(v))
def test_all_60_coercion_and_nan_inf_safety(
    plugin_id: str, skill_id: str, script_path: Path
) -> None:
    """Every script must coerce string-encoded dynamic defaults and reject NaN/Inf safely."""
    mod = tas._load_module(script_path, f"fuzz_coerce_{skill_id.replace('-', '_')}")
    assert mod._to_float(None, "$1,250.50") == 1250.5
    assert mod._to_float("NOT_A_NUM", "762,400") == 762400.0
    assert mod._to_float("nan", "10.5") == 10.5
    assert mod._to_float("inf", 0.0) == 0.0
    assert mod._to_opt_float("NaN") is None
    assert mod._to_opt_float("-inf") is None
    assert mod._to_opt_float(float("nan")) is None
    assert mod._to_int(None, "42") == 42
    assert mod._to_int("nan", "7") == 7


def test_dynamic_fallback_coercion_and_csv_ingestion_regressions(tmp_path: Path) -> None:
    """Regression coverage for live string-encoded fallback keys, CSV ingestion, and config defaults."""
    # 1. pnl-budget-variance-bridge with string budget_usd/actual_usd fallback keys & real CSV file
    pnl_path = next(sp for _, sid, sp in _all_catalog_skills() if sid == "pnl-budget-variance-bridge")
    pnl_mod = tas._load_module(pnl_path, "fuzz_pnl_fallback")
    pnl_res = pnl_mod.analyze(
        {
            "lines": [
                {
                    "account_id": "GL-5101",
                    "account_name": "Engineering - Cloud Infrastructure",
                    "category": "opex",
                    "budget_usd": "450000",
                    "actual_usd": "$762,400.00",
                },
                {
                    "account_id": "GL-5109",
                    "account_name": "Engineering - Contractor Augmentation",
                    "category": "opex",
                    "budget_usd": "160,000.00",
                    "actual_usd": "131200",
                },
            ]
        }
    )
    assert pnl_res["summary"]["actual_cost_usd"] == 893600.0
    assert pnl_res["summary"]["budget_cost_usd"] == 610000.0
    assert pnl_res["summary"]["net_ebitda_variance_usd"] == -283600.0
    assert pnl_res["variance_lines"][0]["variance_vs_budget_usd"] == 312400.0

    csv_path = tmp_path / "gl_variance.csv"
    csv_path.write_text(
        "account_id,account_name,category,budget_usd,actual_usd\n"
        "GL-5101,Cloud Infrastructure,opex,450000,762400\n"
        "GL-5109,Contractor Augmentation,opex,160000,131200\n",
        encoding="utf-8",
    )
    csv_res = pnl_mod.analyze(csv_path)
    assert csv_res["summary"]["leaf_line_count"] == 2
    assert csv_res["summary"]["net_ebitda_variance_usd"] == -283600.0

    # 2. pipeline-hygiene-slippage with string metadata.total_available fallback
    pipe_path = next(sp for _, sid, sp in _all_catalog_skills() if sid == "pipeline-hygiene-slippage")
    pipe_mod = tas._load_module(pipe_path, "fuzz_pipe_fallback")
    pipe_res = pipe_mod.analyze(
        {
            "metadata": {"total_available": "10"},
            "opportunities": [
                {
                    "opportunity_id": "OPP-STR",
                    "name": "Apex Expansion",
                    "stage": "Negotiation",
                    "forecast_category": "Commit",
                    "amount": "$250,000.00",
                    "currency": "USD",
                    "push_count": "3",
                }
            ],
        }
    )
    assert len(pipe_res["truncation_warnings"]) == 1

    # 3. sre-incident-postmortem with string config default_slo_availability_pct fallback
    sre_path = next(sp for _, sid, sp in _all_catalog_skills() if sid == "sre-incident-postmortem")
    sre_mod = tas._load_module(sre_path, "fuzz_sre_fallback")
    sre_res = sre_mod.analyze(
        {
            "window_days": "30",
            "incidents": [
                {
                    "incident_id": "INC-STR",
                    "service": "checkout",
                    "started_at": "2026-11-05T10:00:00Z",
                    "detected_at": "2026-11-05T10:05:00Z",
                    "mitigated_at": "2026-11-05T10:35:00Z",
                }
            ],
        },
        config={"org_configured": True, "organization_name": "Meridian BioPharma", "default_slo_availability_pct": "99.95"},
    )
    assert sre_res["summary"]["incident_count"] == 1
    assert sre_res["summary"]["slo_target_pct"] == 99.95
    assert sre_res["baseline_mode"] == "ORG_CONFIGURED"

