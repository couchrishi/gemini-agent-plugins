"""Tests for SKILL.md validation, repository-wide validation, cron validation, schema mapping, hygiene scan, and zip packaging."""

from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import package as pkg_tool  # noqa: E402
import skill_validator  # noqa: E402
import validate_repo  # noqa: E402


VALID_SKILL_BODY = """
# Sample Skill

Handles deterministic domain analysis in Gemini Enterprise (`/work`).

## Connector Fetching & Attached Files

Discover and fetch live records via `remote_cli` (`remote_cli mcp <connector>`) or read attached workbooks via `view_file`.

## Schema Inspection & Python Shaping

Inspect uploaded tabs, headers, and JSON keys directly in `pyrepl` using `scripts/enterprise_io.py`, and shape messy custom fields into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`.
Call `ask_question` only when two customer columns remain genuinely ambiguous.

## Config & Baseline

Inspect `references/config.json` for `org_configured`. When false, stamp:
`[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## Execution & Governance

Run `scripts/engine.py` via `pyrepl` (`analyze(payload, config=...)`) or `python3` CLI, and persist drafts with `write_to_file`.
External writes require Agent Gateway (`Auto-Guardian`) approval and explicit user confirmation.
Recurring runs can be configured in chat via `schedule_task`.
"""


def test_full_repository_validation_passes_zero_errors() -> None:
    errors, stats = validate_repo.validate_repository(ROOT)
    assert errors == [], "Repository validation errors:\n" + "\n".join(errors)
    assert stats["plugins"] == 20
    assert stats["skills"] == 60
    assert stats["bundle_zips"] == 20
    assert stats["skill_zips"] == 60
    assert stats["skill_md_validations"] == 140
    assert stats["scheduled_routines"] == 20


def test_catalog_matches_plugins_exactly() -> None:
    catalog = json.loads((ROOT / ".gemini-agent" / "catalog.json").read_text(encoding="utf-8"))
    catalog_schema = json.loads((ROOT / "shared" / "schema" / "catalog.schema.json").read_text(encoding="utf-8"))
    assert validate_repo.validate_against_schema(catalog, catalog_schema, "catalog.json") == []
    assert catalog["total_plugins"] == 20
    assert catalog["total_skills"] == 60
    assert len(catalog["plugins"]) == 20


def test_packaging_check_no_drift() -> None:
    # Must succeed cleanly without raising RuntimeError on drifted references or zips
    pkg_tool.sync_and_build(check_only=True)


def test_skill_validator_positive_and_negative_cases() -> None:
    inventory = ["SKILL.md", "scripts/engine.py", "scripts/enterprise_io.py", "references/config.json"]

    # Valid manifest
    ok_md = (
        '---\n'
        'name: valid-sample-skill\n'
        'description: "Validates inputs cleanly. Use when testing valid manifests. Don\'t use for invalid inputs."\n'
        'created_by: gemini-agent-plugins\n'
        '---\n'
        + VALID_SKILL_BODY
    )
    assert (
        skill_validator.validate_skill_content(ok_md, inventory, expected_name="valid-sample-skill")
        == []
    )

    # Reject angle brackets in description
    bad_angles = ok_md.replace("Use when", "Use <x> when")
    issues = skill_validator.validate_skill_content(bad_angles, inventory, expected_name="valid-sample-skill")
    assert any("'<'" in i.message or "'>'" in i.message for i in issues)

    # Reject missing negative anti-trigger
    bad_no_anti = ok_md.replace(" Don't use for invalid inputs.", "")
    issues = skill_validator.validate_skill_content(bad_no_anti, inventory, expected_name="valid-sample-skill")
    assert any("anti-trigger" in i.message for i in issues)

    # Reject forbidden edit tool string
    bad_tool = ok_md.replace("write_to_file", "file" + "_edit")
    issues = skill_validator.validate_skill_content(bad_tool, inventory, expected_name="valid-sample-skill")
    assert any("forbidden tool name" in i.message for i in issues)

    # Reject broken code path reference and unreferenced resource
    bad_link = ok_md.replace("`scripts/engine.py`", "`scripts/missing.py`")
    issues = skill_validator.validate_skill_content(bad_link, inventory, expected_name="valid-sample-skill")
    assert any("Broken skill path reference" in i.message for i in issues)
    assert any("Unreferenced resource" in i.message for i in issues)

    # Reject missing /work Python shaping/entry markers
    bad_norm = ok_md.replace("ask_question", "ask_user")
    issues = skill_validator.validate_skill_content(bad_norm, inventory, expected_name="valid-sample-skill")
    assert any("ask_question" in i.message for i in issues)

    # Reject legacy phrasing or fake hardcoded tool names (decoded only in test RAM)
    legacy_mode = base64.b64decode("TW9kZSBB").decode("utf-8")
    fake_sap_tool = base64.b64decode("c2FwX3Bvc3RfaW52b2ljZV9wYXltZW50").decode("utf-8")
    issues_legacy = skill_validator.validate_skill_content(
        ok_md + f"\nLegacy phrase: {legacy_mode}\n",
        inventory,
        expected_name="valid-sample-skill",
    )
    assert any("forbidden legacy" in i.message for i in issues_legacy)
    issues_fake = skill_validator.validate_skill_content(
        ok_md + f"\nFake tool: `{fake_sap_tool}`\n",
        inventory,
        expected_name="valid-sample-skill",
    )
    assert any("forbidden legacy" in i.message for i in issues_fake)

    # Reject non-web markdown link while allowing https:// links
    non_web_md = ok_md.replace("`scripts/engine.py`", "[engine.py](scripts/engine.py)")
    issues = skill_validator.validate_skill_content(non_web_md, inventory, expected_name="valid-sample-skill")
    assert any("non-web markdown link" in i.message for i in issues)

    web_md = ok_md + "\nSee [Reference Docs](https://example.com/docs) for API details.\n"
    assert (
        skill_validator.validate_skill_content(web_md, inventory, expected_name="valid-sample-skill")
        == []
    )


def test_cron_expression_validator() -> None:
    assert validate_repo.validate_cron_expression("0 6 * * 1-5") == []
    assert validate_repo.validate_cron_expression("*/15 8-18 * * *") == []
    assert validate_repo.validate_cron_expression("0 6 * *") != []
    assert validate_repo.validate_cron_expression("0 6 * * * 2026") != []
    assert validate_repo.validate_cron_expression("every weekday morning") != []


def test_hygiene_scanner_flags_encoded_internal_terms_and_passes_clean_text() -> None:
    clean = "Cymbal Financial validated SAP S/4HANA and ServiceNow connectors with Gemini Enterprise (/work)."
    assert validate_repo.scan_text_hygiene(clean, "synthetic.md") == []

    # Decode forbidden tokens only inside test RAM so static repo remains 100% clean
    for b64_val, label in [
        ("c29iaQ==", "internal product"),
        ("Yi8xMjM0NTY=", "bug shortlink"),
        ("TW9kZSBB", "legacy mode label"),
        ("cG9saWN5LmNlbA==", "legacy policy file"),
        ("c2FwX3Bvc3RfaW52b2ljZV9wYXltZW50", "fake hardcoded SAP action"),
        ("Q0VM", "legacy rule acronym"),
        ("c2NoZWR1bGVzLw==", "legacy schedules dir"),
        ("YmlncXVlcnlfc3FsX2FwaQ==", "fake api token"),
    ]:
        decoded = base64.b64decode(b64_val).decode("utf-8")
        findings = validate_repo.scan_text_hygiene(f"Test {label}: {decoded}", "leak.md")
        assert findings, f"Expected hygiene finding for {label}"


def test_org_config_stamping_builds_valid_zips_and_suppresses_baseline_banner(tmp_path: Path) -> None:
    org_cfg_path = ROOT / "tests" / "fixtures" / "sample_org_config.json"
    out_dir = tmp_path / "cymbal-dist"
    manifest = pkg_tool.sync_and_build(
        org_payload=pkg_tool.load_json(org_cfg_path),
        output_dir=out_dir,
        check_only=False,
    )
    assert manifest["org_configured"] is True
    assert manifest["organization_name"] == "Cymbal Financial"
    assert len(manifest["bundles"]) == 20
    assert len(manifest["skills"]) == 60

    bundle_zip = out_dir / "bundles" / "fsi-credit-kyc-claims.zip"
    skill_zip = out_dir / "skills" / "commercial-credit-memo-analyst.zip"
    assert skill_validator.validate_skill_zip(bundle_zip, expected_name="fsi-credit-kyc-claims", is_bundle=True) == []
    assert skill_validator.validate_skill_zip(skill_zip, expected_name="commercial-credit-memo-analyst", is_bundle=False) == []

    with zipfile.ZipFile(skill_zip, "r") as zf:
        cfg_inside = json.loads(zf.read("references/config.json").decode("utf-8"))
        assert cfg_inside["org_configured"] is True
        assert cfg_inside["organization_name"] == "Cymbal Financial"
        assert cfg_inside["min_dscr"] == 1.35
        assert cfg_inside["max_net_leverage"] == 3.25
        assert cfg_inside["sheet_map"] == {}
        assert cfg_inside["column_map"] == {}

        # Extract script + config and verify baseline banner is suppressed when org_configured=True
        script_path = tmp_path / "credit_covenant_stress.py"
        cfg_path = tmp_path / "config.json"
        script_path.write_bytes(zf.read("scripts/credit_covenant_stress.py"))
        cfg_path.write_text(json.dumps(cfg_inside), encoding="utf-8")

    sys.path.insert(0, str(tmp_path))
    try:
        mod = importlib.import_module("credit_covenant_stress")
        res = mod.analyze(
            {
                "borrower_id": "B1",
                "revenue_usd": 10000000,
                "ebitda_usd": 2000000,
                "total_debt_usd": 6000000,
                "cash_usd": 500000,
                "interest_expense_usd": 350000,
                "principal_amortization_usd": 1000000,
            },
            config=cfg_path,
        )
        assert res["baseline_mode"] == "ORG_CONFIGURED"
        assert res["baseline_banner"] == ""
        md = mod.render_markdown(res)
        assert "[EVALUATED AGAINST STANDARD BASELINE" not in md
    finally:
        sys.path.pop(0)


def test_org_config_binds_sheet_map_and_column_map_and_rejects_invalid_entries(tmp_path: Path) -> None:
    custom_cfg = {
        "organization_name": "Meridian Manufacturing",
        "plugins": {
            "finance-variance-recon": {
                "sheet_map": {"invoices": "Vendor_Bills"},
                "column_map": {"Bill Ref": "invoice_id", "Purchasing Doc #": "po_number"},
            }
        },
    }
    out_dir = tmp_path / "meridian-dist"
    pkg_tool.sync_and_build(org_payload=custom_cfg, output_dir=out_dir, check_only=False)

    ap_zip = out_dir / "skills" / "ap-three-way-match.zip"
    with zipfile.ZipFile(ap_zip, "r") as zf:
        cfg_inside = json.loads(zf.read("references/config.json").decode("utf-8"))
        assert cfg_inside["org_configured"] is True
        assert cfg_inside["sheet_map"] == {"invoices": "Vendor_Bills"}
        assert cfg_inside["column_map"] == {"Bill Ref": "invoice_id", "Purchasing Doc #": "po_number"}

    bad_map = {
        "plugins": {
            "finance-variance-recon": {
                "column_map": {"Bill Ref": 123},
            }
        }
    }
    with pytest.raises(ValueError, match="string mapping value"):
        pkg_tool.sync_and_build(org_payload=bad_map, output_dir=tmp_path / "out_bad_map")


def test_org_config_rejects_out_of_range_or_unknown_properties(tmp_path: Path) -> None:
    bad_range = tmp_path / "bad_range.json"
    bad_range.write_text(
        json.dumps({"plugins": {"fsi-credit-kyc-claims": {"min_dscr": 0.1}}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="minimum"):
        pkg_tool.sync_and_build(org_payload=pkg_tool.load_json(bad_range), output_dir=tmp_path / "out1")

    bad_unknown = tmp_path / "bad_unknown.json"
    bad_unknown.write_text(
        json.dumps({"plugins": {"fsi-credit-kyc-claims": {"nonexistent_flag": True}}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown config property"):
        pkg_tool.sync_and_build(org_payload=pkg_tool.load_json(bad_unknown), output_dir=tmp_path / "out2")
