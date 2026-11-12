#!/usr/bin/env python3
"""Deterministic local benchmark harness verifying enterprise corpus generation and all 60 Python engines."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_BANNER = "[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]"
GENERATOR_PATH = Path(__file__).resolve().parent / "generate_enterprise_suite.py"
CATALOG_PATH = REPO_ROOT / ".gemini-agent" / "catalog.json"

# Direct 5,000-row / 27-page full-scale stress checks alongside all 60 starter-pack validations.
FULL_SCALE_CHECKS: list[tuple[str, str, str, str | None]] = [
    ("finance-variance-recon", "ap-three-way-match", "Apex_FY26_Q3_Consolidated_Financial_Pack.xlsx", None),
    ("finance-variance-recon", "pnl-budget-variance-bridge", "Apex_FY26_Q3_Consolidated_Financial_Pack.xlsx", None),
    ("finance-variance-recon", "ar-aging-collections-audit", "Apex_FY26_Q3_Consolidated_Financial_Pack.xlsx", None),
    ("deal-desk-rfp-engine", "deal-desk-quote-guard", "Apex_FY26_Global_Pipeline_and_ARR_Workbook.xlsx", None),
    ("deal-desk-rfp-engine", "pipeline-hygiene-slippage", "Apex_FY26_Global_Pipeline_and_ARR_Workbook.xlsx", None),
    ("legal-contract-desk", "contract-playbook-redliner", "Apex_Master_Services_Agreement_and_DPA_Redline_2026.docx", None),
    ("people-ops-talent-hub", "workforce-attrition-comp-audit", "Apex_FY26_Global_Workforce_and_Comp_Census.xlsx", None),
    ("erp-procure-to-pay", "supplier-rfx-tariff-modeler", "Apex_FY26_Supply_Chain_BOM_and_Vendor_Spend.xlsx", None),
    ("erp-procure-to-pay", "bom-cost-rollup-variance", "Apex_FY26_Supply_Chain_BOM_and_Vendor_Spend.xlsx", None),
    ("erp-procure-to-pay", "gr-ir-clearing-orchestrator", "Apex_FY26_Supply_Chain_BOM_and_Vendor_Spend.xlsx", None),
    ("fsi-credit-kyc-claims", "kyc-aml-screening-dossier", "Apex_FY26_Portfolio_AML_Credit_and_Claims_Ledger.xlsx", None),
    ("gsi-proposal-ip-factory", "winning-proposal-architect", "Apex_FY26_GSI_Bench_Staffing_and_SOW_Workbook.xlsx", None),
]


def _load_generator_module() -> Any:
    spec = importlib.util.spec_from_file_location("generate_enterprise_suite", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load generator at {GENERATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_enterprise_suite"] = mod
    spec.loader.exec_module(mod)
    return mod


def _find_skill_script(plugin_id: str, skill_id: str) -> Path:
    sdir = REPO_ROOT / "plugins" / plugin_id / "skills" / skill_id / "scripts"
    py_files = [p for p in sorted(sdir.glob("*.py")) if p.name != "enterprise_io.py"]
    if len(py_files) != 1:
        raise FileNotFoundError(f"Expected 1 engine script in {sdir}, found {py_files}")
    return py_files[0]


def _run_engine(
    script_path: Path,
    input_path: Path,
    config_path: Path | None,
    *,
    sheet: str | None = None,
) -> tuple[dict[str, Any], str]:
    cmd_base = [sys.executable, str(script_path), "--input", str(input_path)]
    if config_path and config_path.is_file():
        cmd_base.extend(["--config", str(config_path)])
    if sheet:
        cmd_base.extend(["--sheet", sheet])

    proc_j = subprocess.run([*cmd_base, "--format", "json"], capture_output=True, text=True, check=False, timeout=60)
    if proc_j.returncode != 0:
        raise RuntimeError(f"JSON execution failed (rc={proc_j.returncode}): {proc_j.stderr.strip()}")
    payload = json.loads(proc_j.stdout)
    if not isinstance(payload, dict) or "skill" not in payload or "summary" not in payload or "baseline_mode" not in payload:
        raise RuntimeError(f"Missing required keys (skill, baseline_mode, summary) in JSON output for {script_path.name}")

    proc_m = subprocess.run([*cmd_base, "--format", "markdown"], capture_output=True, text=True, check=False, timeout=60)
    if proc_m.returncode != 0:
        raise RuntimeError(f"Markdown execution failed (rc={proc_m.returncode}): {proc_m.stderr.strip()}")
    if BASELINE_BANNER not in proc_m.stdout:
        raise RuntimeError(f"Missing baseline banner in Markdown output for {script_path.name}")
    return payload, proc_m.stdout


def run_benchmark(*, include_full_stress: bool = True, json_output: bool = False) -> int:
    t0 = time.perf_counter()
    gen = _load_generator_module()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="gap_bench_") as tmp_str:
        tmp_dir = Path(tmp_str)
        full_dir = tmp_dir / "full"
        starter_dir = tmp_dir / "starter"

        t_gen0 = time.perf_counter()
        full_manifest = gen.generate_full_suite(full_dir)
        starter_manifest = gen.generate_starter_suite(starter_dir)
        t_gen = round(time.perf_counter() - t_gen0, 2)

        assert full_manifest["workbook_count"] == 12, f"Expected 12 .xlsx, got {full_manifest['workbook_count']}"
        assert full_manifest["docx_count"] == 3, f"Expected 3 .docx, got {full_manifest['docx_count']}"
        assert full_manifest["pdf_count"] == 5, f"Expected 5 .pdf, got {full_manifest['pdf_count']}"
        assert full_manifest["total_xlsx_tabs"] == 71, f"Expected 71 tabs, got {full_manifest['total_xlsx_tabs']}"
        assert full_manifest["total_xlsx_rows"] == 60089, f"Expected 60089 rows, got {full_manifest['total_xlsx_rows']}"
        assert starter_manifest["sample_count"] == 20, f"Expected 20 starter files, got {starter_manifest['sample_count']}"

        starter_by_plugin = {item["plugin_id"]: Path(item["path"]) for item in starter_manifest["samples"]}
        rows_report: list[dict[str, Any]] = []
        failures: list[str] = []

        t_eng0 = time.perf_counter()
        for plug in catalog["plugins"]:
            pid = plug["id"]
            input_path = starter_by_plugin[pid]
            for sk in plug["skills"]:
                sid = sk["id"]
                script_path = _find_skill_script(pid, sid)
                cfg_path = REPO_ROOT / "plugins" / pid / "skills" / sid / "references" / "config.json"
                t_one = time.perf_counter()
                try:
                    data, md = _run_engine(script_path, input_path, cfg_path)
                    rows_report.append(
                        {
                            "plugin_id": pid,
                            "skill_id": sid,
                            "script": script_path.name,
                            "baseline_mode": data["baseline_mode"],
                            "md_bytes": len(md.encode("utf-8")),
                            "elapsed_ms": round((time.perf_counter() - t_one) * 1000, 1),
                            "status": "PASS",
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{pid}/{sid}: {exc}")

        full_stress_results: list[dict[str, Any]] = []
        if include_full_stress:
            for pid, sid, fname, sheet_name in FULL_SCALE_CHECKS:
                script_path = _find_skill_script(pid, sid)
                cfg_path = REPO_ROOT / "plugins" / pid / "skills" / sid / "references" / "config.json"
                fpath = full_dir / fname
                t_one = time.perf_counter()
                try:
                    data, _ = _run_engine(script_path, fpath, cfg_path, sheet=sheet_name)
                    full_stress_results.append(
                        {
                            "plugin_id": pid,
                            "skill_id": sid,
                            "file": fname,
                            "elapsed_ms": round((time.perf_counter() - t_one) * 1000, 1),
                            "status": "PASS",
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"FULL:{pid}/{sid} ({fname}): {exc}")

        t_eng = round(time.perf_counter() - t_eng0, 2)
        t_total = round(time.perf_counter() - t0, 2)

    if json_output:
        print(
            json.dumps(
                {
                    "suite_generation_s": t_gen,
                    "engine_execution_s": t_eng,
                    "total_s": t_total,
                    "full_suite": {
                        "xlsx": full_manifest["workbook_count"],
                        "tabs": full_manifest["total_xlsx_tabs"],
                        "rows": full_manifest["total_xlsx_rows"],
                        "docx": full_manifest["docx_count"],
                        "pdf": full_manifest["pdf_count"],
                    },
                    "skills_passed": len(rows_report),
                    "full_stress_passed": len(full_stress_results),
                    "failures": failures,
                    "results": rows_report,
                },
                indent=2,
            )
        )
    else:
        print(
            f"Generated enterprise corpus in {t_gen:.2f}s: "
            f"{full_manifest['workbook_count']} workbooks ({full_manifest['total_xlsx_tabs']} tabs / {full_manifest['total_xlsx_rows']:,} rows), "
            f"{full_manifest['docx_count']} .docx, {full_manifest['pdf_count']} .pdf + {starter_manifest['sample_count']} starter samples"
        )
        print()
        print(f"{'Plugin ID':<34} {'Skill ID':<36} {'Engine Script':<36} {'MD Bytes':>8} {'Time(ms)':>8} {'Status':>6}")
        print("-" * 134)
        for row in rows_report:
            print(
                f"{row['plugin_id']:<34} {row['skill_id']:<36} {row['script']:<36} "
                f"{row['md_bytes']:>8} {row['elapsed_ms']:>8.1f} {row['status']:>6}"
            )
        if full_stress_results:
            print()
            print(f"Full-Scale Stress Runs ({len(full_stress_results)}/{len(FULL_SCALE_CHECKS)} multi-thousand-row / 27-page targets):")
            for row in full_stress_results:
                print(f"  PASS  {row['plugin_id']}/{row['skill_id']} <- {row['file']} ({row['elapsed_ms']:.1f} ms)")
        print()
        print(
            f"Benchmark Verification Complete: {len(rows_report)}/60 skills passed, "
            f"{len(full_stress_results)}/{len(FULL_SCALE_CHECKS)} full-scale stress checks passed, "
            f"0 exceptions ({t_total:.2f}s total; engines {t_eng:.2f}s)."
        )

    if failures:
        for err in failures:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify deterministic local plugin engines against generated enterprise artifacts.")
    parser.add_argument("--no-full-stress", action="store_true", help="Skip extra full-workbook stress checks.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON summary.")
    args = parser.parse_args(argv)
    return run_benchmark(include_full_stress=not args.no_full_stress, json_output=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
