#!/usr/bin/env python3
"""Zero-dependency enterprise file ingestion layer (.xlsx, .docx, .csv, .tsv, .json, .jsonl).

Uses strictly Python 3.11+ standard library modules (`zipfile`, `xml.etree.ElementTree`,
`csv`, `json`, `re`, `datetime`, `pathlib`) so every skill and department bundle works inside
air-gapped or minimal sandboxes without requiring `openpyxl`, `python-docx`, or `pandas`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

_CELL_REF_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_DATE_STYLE_CHAR_RE = re.compile(r"[ymdhs]", re.IGNORECASE)
_BRACKET_COLOR_RE = re.compile(r"\[[^\]]*\]")
_QUOTED_STR_RE = re.compile(r'"[^"]*"')
_SECTION_HEADING_RE = re.compile(
    r"^(?:(?:section|article|clause|schedule|exhibit|appendix|part)\s+[0-9A-Za-z.]+(?:\s*[:.-]\s*|\s+)|"
    r"\d+(?:\.\d+){0,3}\s+[A-Z]).{2,120}$",
    re.IGNORECASE,
)

# Built-in Excel date/time number format IDs
_EXCEL_DATE_NUMFMT_IDS = set(range(14, 23)) | {27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 45, 46, 47}

# Cross-enterprise column aliases (applied non-destructively after snake_case canonicalization)
COMMON_FIELD_ALIASES: dict[str, str] = {
    # SAP / ERP P2P & AP / GR-IR
    "ebeln": "po_number",
    "po_no": "po_number",
    "po_id": "po_number",
    "purchase_order": "po_number",
    "purchase_order_number": "po_number",
    "ebelp": "line_item",
    "po_line": "line_item",
    "item_no": "line_item",
    "line_no": "line_item",
    "lifnr": "vendor_id",
    "vendor_code": "vendor_id",
    "supplier_code": "vendor_id",
    "name1": "vendor_name",
    "vendor": "vendor_name",
    "belnr": "invoice_id",
    "inv_id": "invoice_id",
    "xblnr": "invoice_number",
    "inv_no": "invoice_number",
    "invoice_no": "invoice_number",
    "ref_doc_no": "invoice_number",
    "bldat": "invoice_date",
    "inv_date": "invoice_date",
    "budat": "posting_date",
    "post_date": "posting_date",
    "waers": "currency",
    "curr": "currency",
    "currency_code": "currency",
    "doc_currency": "currency",
    "drcr": "shkzg",
    "debit_credit": "shkzg",
    "drcr_ind": "shkzg",
    "tcurx_raw_encoding": "sap_raw_encoding",
    "raw_encoding": "sap_raw_encoding",
    "remittance_changed": "bank_account_changed",
    "bank_changed": "bank_account_changed",
    # Finance GL & AR
    "acct_id": "account_id",
    "gl_account": "account_id",
    "saknr": "account_id",
    "acct_name": "account_name",
    "gl_description": "account_name",
    "account_description": "account_name",
    "parent_acct": "parent_account",
    "rollup_account": "parent_account",
    "actual_amt": "actual_local",
    "act_local": "actual_local",
    "budget_amt": "budget_local",
    "plan_local": "budget_local",
    "forecast_amt": "forecast_local",
    "fcst_local": "forecast_local",
    "cust_id": "customer_id",
    "kunnr": "customer_id",
    "cust_name": "customer_name",
    "doc_due_date": "due_date",
    "net_due_date": "due_date",
    "invoice_open_amount_usd": "open_amount_usd",
    "open_amt_usd": "open_amount_usd",
    # HR / Workday
    "emp_id": "worker_id",
    "employee_no": "worker_id",
    "worker_classification": "worker_type",
    "emp_type": "worker_type",
    "worker_status": "employment_status",
    "eff_date": "effective_date",
    "effective_dt": "effective_date",
    "grade_level": "job_level",
    "compensation_grade": "job_level",
    "annual_salary": "base_pay_amount",
    "base_salary": "base_pay_amount",
    "compensation_amount": "base_pay_amount",
    "band_midpoint": "band_midpoint_usd",
    # CRM / Commercial / RFP / ITSM
    "opp_id": "opportunity_id",
    "deal_id": "opportunity_id",
    "opp_name": "name",
    "deal_name": "name",
    "stage_name": "stage",
    "forecast_cat": "forecast_category",
    "last_activity_date": "days_since_last_activity",
    "ticket_number": "incident_id",
    "number": "incident_id",
    "inc_id": "incident_id",
    "chg_id": "change_id",
    "change_number": "change_id",
    # Retail / Industrial / Telco
    "store_num": "store_id",
    "store_code": "store_id",
    "sku_id": "sku",
    "item_sku": "sku",
    "qty_on_hand_book": "book_on_hand_qty",
    "book_qty": "book_on_hand_qty",
    "physical_qty": "physical_count_qty",
    "days_zero_scan": "days_since_last_pos_scan",
    "lel_pct": "gas_test_lel_pct",
    "o2_pct": "gas_test_o2_pct",
}

# Field names whose string representations ("true"/"false"/"yes"/"no") should map to Python bool
_BOOLEAN_KEYS = {
    "truncated",
    "done",
    "org_configured",
    "sap_raw_encoding",
    "bank_account_changed",
    "disputed",
    "is_mandatory",
    "is_draft",
    "irm_protected",
    "is_external",
    "requires_preread",
    "competitor_threat",
    "termination_for_convenience",
    "is_closed",
    "documentation_complete",
    "is_pep",
    "irb_approved",
    "is_fatal_or_life_threatening",
    "is_serious",
    "issuer_signed",
    "fire_watch_assigned",
    "loto_isolated",
    "has_tested_rollback",
    "reversible_migration",
    "staging_validated",
    "canary_enabled",
    "uncapped_cpi",
    "auto_renewal",
    "verified_weather_force_majeure",
    "residency_verified",
    "is_indirect_fa",
    "mtdc_exempt",
    "coi_declaration_signed",
    "debarred_or_sanctioned",
    "tax_clearance_valid",
    "bid_bond_submitted",
    "eas_tag_required",
    "require_partition_filter",
    "single_source",
    "uncapped_liability",
    "unilateral_cap",
    "silent_evergreen",
    "uncapped_price_escalator",
    "vendor_ai_training_allowed",
    "assigns_customer_preexisting_ip",
    "shared_background_ip_license",
    "vague_timing",
    "unilateral_venue_or_appeal_waiver",
    "enforce_safety_cert_expiry",
    "allow_draft_versions_in_answers",
    "forbid_customer_data_training",
}

# Strictly string-list columns (excludes dict-valued columns such as certifications/sublimits/required_spares)
_LIST_KEYS = {
    "procedures",
    "required_procedures",
    "topics",
    "tags",
    "preread_links",
    "ticket_topics",
    "required_domains",
    "mapped_articles",
    "required_skills",
    "skills",
    "required_safety_certs",
    "approved_translations",
    "covered_icd10_prefixes",
    "icd10_codes",
    "required_labs",
    "do_not_translate_terms",
    "target_locales",
    "tariff_shock_countries",
    "target_assemblies",
    "primary_keys",
    "entrypoints",
    "db_reads",
    "db_writes",
    "covers_requirements",
    "excluded_perils",
    "submitted_documents",
    "blocked_by",
    "channels",
    "target_audiences",
    "client_dependencies",
    "inactive_owners",
}


# ---------------------------------------------------------------------------
# Low-Level Coercion & Header Helpers
# ---------------------------------------------------------------------------


def canonicalize_header(name: str) -> str:
    """Normalize an arbitrary spreadsheet or table column header into snake_case."""
    cleaned = (name or "").lstrip("\ufeff").strip()
    cleaned = cleaned.replace("%", " pct ").replace("$", " usd ")
    slug = _NON_ALNUM_RE.sub("_", cleaned.lower()).strip("_")
    return slug


def coerce_bool(val: Any, default: bool | None = None) -> bool | None:
    """Safely interpret boolean flags without treating 'false'/'no'/'0' as True."""
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"true", "yes", "y", "1", "on"}:
        return True
    if s in {"false", "no", "n", "0", "off"}:
        return False
    return default


def coerce_cell_value(val: Any, col_name: str = "") -> Any:
    """Decode JSON-encoded cells, delimited list fields, and boolean strings cleanly."""
    if val is None:
        return None
    if isinstance(val, (bool, int, float, list, dict)):
        return val
    s = str(val).strip()
    if not s:
        return ""
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, (list, dict)):
                return parsed
        except (ValueError, json.JSONDecodeError):
            pass
    lower = s.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    canon = canonicalize_header(col_name) if col_name else ""
    if canon in _BOOLEAN_KEYS or canon.startswith(("is_", "has_")):
        b = coerce_bool(s)
        if b is not None:
            return b
    if canon in _LIST_KEYS:
        sep = ";" if ";" in s else ","
        parts = [item.strip() for item in s.split(sep) if item.strip()]
        return parts
    return s


_VALUE_DICT_KEYS = {
    "fx_rates",
    "decimal_places",
    "depot_spares_qty",
    "category_medians_usd",
    "stage_median_days",
    "sublimits",
    "certifications",
    "required_spares",
    "metadata",
    "attributes",
}


def parse_mapping_arg(raw: str | dict[str, Any] | None) -> dict[str, str]:
    """Parse --column-map / --sheet-map from dict, JSON string, or comma-separated k=v pairs."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {
            str(k).strip(): str(v).strip()
            for k, v in raw.items()
            if k is not None and v is not None and str(k).strip() and str(v).strip()
        }
    s = str(raw).strip()
    if not s:
        return {}
    if s.startswith("{"):
        parsed = json.loads(s)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object for mapping, got {type(parsed).__name__}")
        return {
            str(k).strip(): str(v).strip()
            for k, v in parsed.items()
            if k is not None and v is not None and str(k).strip() and str(v).strip()
        }
    out: dict[str, str] = {}
    for part in s.split(","):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid mapping entry {item!r}; expected JSON object or key=value pairs.")
        k, v = item.split("=", 1)
        ks, vs = k.strip(), v.strip()
        if ks and vs:
            out[ks] = vs
    return out


def merge_mappings(
    cfg: dict[str, Any] | None = None,
    *,
    column_map: str | dict[str, Any] | None = None,
    sheet_map: str | dict[str, Any] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Combine config.json column_map/sheet_map defaults with explicit call-site overrides."""
    base_col = parse_mapping_arg(cfg.get("column_map") if isinstance(cfg, dict) else None)
    base_col.update(parse_mapping_arg(column_map))
    base_sh = parse_mapping_arg(cfg.get("sheet_map") if isinstance(cfg, dict) else None)
    base_sh.update(parse_mapping_arg(sheet_map))
    return base_col, base_sh


def _compile_column_map(column_map: dict[str, str] | None) -> tuple[dict[str, str], dict[str, str]]:
    parsed = parse_mapping_arg(column_map)
    raw_lower: dict[str, str] = {}
    canon_lower: dict[str, str] = {}
    for k, v in parsed.items():
        raw_lower[k.strip().lower()] = v.strip()
        ck = canonicalize_header(k)
        if ck:
            canon_lower[ck] = v.strip()
    return raw_lower, canon_lower


def normalize_row(
    row: dict[str, Any],
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a copy of row retaining original keys plus explicit column_map, snake_case, and alias keys."""
    if not isinstance(row, dict):
        return {}
    out: dict[str, Any] = {}
    aliases = dict(COMMON_FIELD_ALIASES)
    if field_aliases:
        aliases.update(field_aliases)
    col_raw_lower, col_canon_lower = _compile_column_map(column_map)

    # 1. Preserve original keys cleanly coerced
    for k, v in row.items():
        if k is None:
            continue
        k_str = str(k).lstrip("\ufeff").strip()
        if not k_str:
            continue
        out[k_str] = coerce_cell_value(v, k_str)

    # 2. Apply explicit customer column_map FIRST (highest precedence before canonical/aliases)
    if col_raw_lower or col_canon_lower:
        for k, v in list(out.items()):
            mapped_tgt = col_raw_lower.get(k.strip().lower())
            if not mapped_tgt:
                ck = canonicalize_header(k)
                if ck:
                    mapped_tgt = col_canon_lower.get(ck)
            if mapped_tgt:
                if mapped_tgt not in out or out[mapped_tgt] in ("", None) or v not in ("", None):
                    out[mapped_tgt] = coerce_cell_value(v, mapped_tgt)

    # 3. Non-destructively overlay canonical snake_case + alias keys
    for k, v in list(out.items()):
        canon = canonicalize_header(k)
        if not canon:
            continue
        if canon not in out or out[canon] in ("", None):
            out[canon] = coerce_cell_value(v, canon)
        target = aliases.get(canon)
        if target and (target not in out or out[target] in ("", None)):
            out[target] = coerce_cell_value(v, target)
    return out


def _map_json_dict(
    row: dict[str, Any],
    *,
    col_raw_lower: dict[str, str],
    col_canon_lower: dict[str, str],
    aliases: dict[str, str],
) -> dict[str, Any]:
    """Non-destructively map custom JSON connector object keys (preserving native JSON types/values)."""
    if not isinstance(row, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k is None:
            continue
        if isinstance(v, list):
            v_norm: Any = [
                _map_json_dict(x, col_raw_lower=col_raw_lower, col_canon_lower=col_canon_lower, aliases=aliases)
                if isinstance(x, dict)
                else x
                for x in v
            ]
        elif isinstance(v, dict) and str(k) not in _VALUE_DICT_KEYS and canonicalize_header(str(k)) not in _VALUE_DICT_KEYS:
            v_norm = _map_json_dict(v, col_raw_lower=col_raw_lower, col_canon_lower=col_canon_lower, aliases=aliases)
        else:
            v_norm = v
        out[k] = v_norm

    if col_raw_lower or col_canon_lower:
        for map_k, map_tgt in list(col_raw_lower.items()):
            if "." in map_k:
                cur: Any = row
                for part in map_k.split("."):
                    if isinstance(cur, dict):
                        m_key = next((ck for ck in cur if str(ck).strip().lower() == part), None)
                        cur = cur.get(m_key) if m_key is not None else None
                    else:
                        cur = None
                        break
                if cur is not None and (cur not in ("", None) or map_tgt not in out):
                    if map_tgt not in out or out[map_tgt] in ("", None) or cur not in ("", None):
                        out[map_tgt] = coerce_cell_value(cur, map_tgt) if isinstance(cur, str) else cur
        for k, v in list(out.items()):
            ks = str(k).strip()
            mapped_tgt = col_raw_lower.get(ks.lower())
            if not mapped_tgt:
                ck = canonicalize_header(ks)
                if ck:
                    mapped_tgt = col_canon_lower.get(ck)
            if mapped_tgt and (mapped_tgt not in out or out[mapped_tgt] in ("", None) or v not in ("", None)):
                if v not in ("", None) or mapped_tgt not in out:
                    out[mapped_tgt] = coerce_cell_value(v, mapped_tgt) if isinstance(v, str) else v

    if aliases or col_raw_lower or col_canon_lower:
        for k, v in list(out.items()):
            ks = str(k).strip()
            canon = canonicalize_header(ks)
            if not canon:
                continue
            # Copy snake_case key only when key differed in case/punctuation and target missing
            if canon != k and (canon not in out or out[canon] in ("", None)):
                if canonicalize_header(ks) != ks or any(ch.isupper() for ch in ks):
                    out[canon] = coerce_cell_value(v, canon) if (isinstance(v, str) and (canon in _BOOLEAN_KEYS or canon in _LIST_KEYS)) else v
            tgt = aliases.get(canon)
            if tgt and (tgt not in out or out[tgt] in ("", None)):
                out[tgt] = coerce_cell_value(v, tgt) if (isinstance(v, str) and (tgt in _BOOLEAN_KEYS or tgt in _LIST_KEYS)) else v
    return out


def apply_column_map_to_payload(
    payload: Any,
    *,
    skill_id: str | None = None,
    primary_key: str | None = None,
    field_aliases: dict[str, str] | None = None,
    column_map: str | dict[str, Any] | None = None,
    sheet_map: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize dict/list/JSON connector payloads using sheet_map and column_map."""
    profile = SKILL_INGESTION_PROFILES.get(skill_id or "", {})
    eff_primary = primary_key or profile.get("primary_key") or "records"
    eff_aliases = dict(COMMON_FIELD_ALIASES)
    eff_aliases.update(profile.get("field_aliases", {}))
    if field_aliases:
        eff_aliases.update(field_aliases)
    parsed_col = parse_mapping_arg(column_map)
    parsed_sheet = parse_mapping_arg(sheet_map)
    col_raw_lower, col_canon_lower = _compile_column_map(parsed_col)

    if payload is None:
        return {}
    if isinstance(payload, list):
        data: dict[str, Any] = {eff_primary: payload}
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        return {}

    # Apply sheet_map top-level table remapping for JSON/dict connector responses too
    if parsed_sheet:
        for target_key, source_key in parsed_sheet.items():
            if target_key not in data or not data.get(target_key):
                if source_key in data:
                    data[target_key] = data[source_key]
                else:
                    match_k = next((k for k in data if str(k).lower() == source_key.lower()), None)
                    if match_k is not None:
                        data[target_key] = data[match_k]

    if not parsed_col and not parsed_sheet:
        # Still allow alias / camelCase normalization non-destructively for custom connector JSON payloads
        needs_norm = False
        for k, v in data.items():
            if isinstance(v, list):
                for item in v[:3]:
                    if isinstance(item, dict) and any(
                        canonicalize_header(str(ik)) != str(ik) or canonicalize_header(str(ik)) in eff_aliases
                        for ik in item
                    ):
                        needs_norm = True
                        break
            if needs_norm:
                break
        if not needs_norm:
            return data

    normalized = _map_json_dict(
        data,
        col_raw_lower=col_raw_lower,
        col_canon_lower=col_canon_lower,
        aliases=eff_aliases,
    )
    return _rollup_nested_records(normalized, skill_id=skill_id)


def _col_letters_to_index(letters: str) -> int:
    idx = 0
    for ch in letters.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _excel_serial_to_iso(serial: float, *, epoch_1904: bool = False) -> str:
    """Convert an Excel numeric date serial into an ISO-8601 date or datetime string."""
    days_int = int(serial)
    frac = serial - days_int
    if epoch_1904:
        base = dt.datetime(1904, 1, 1)
        target = base + dt.timedelta(days=days_int, seconds=round(frac * 86400))
    else:
        # Excel treats 1900 as a leap year (serial 60 = fictitious Feb 29, 1900)
        base = dt.datetime(1899, 12, 31)
        adj = days_int - 1 if days_int >= 60 else days_int
        target = base + dt.timedelta(days=adj, seconds=round(frac * 86400))
    if abs(frac) < 1e-6:
        return target.date().isoformat()
    return target.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CSV / TSV & JSON / JSONL Readers
# ---------------------------------------------------------------------------


def _read_text_with_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_csv_tsv(
    path: Path,
    *,
    delimiter: str | None = None,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Read CSV/TSV with BOM removal, delimiter sniffing, and non-destructive alias + column_map normalization."""
    text = _read_text_with_fallback(path)
    if not text.strip():
        return []
    if delimiter is None:
        if path.suffix.lower() == ".tsv":
            delimiter = "\t"
        else:
            sample = "\n".join(text.splitlines()[:10])
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows: list[dict[str, Any]] = []
    for raw_row in reader:
        if not raw_row:
            continue
        if all(v is None or str(v).strip() == "" for v in raw_row.values()):
            continue
        rows.append(normalize_row(raw_row, field_aliases=field_aliases, column_map=column_map))
    return rows


def _inspect_csv_tsv_fast(
    path: Path,
    *,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
    sample_limit: int = 12,
) -> tuple[list[str], int, list[dict[str, Any]]]:
    """Quickly extract CSV/TSV headers, exact non-empty row count, and sample rows without normalizing all rows."""
    text = _read_text_with_fallback(path)
    if not text.strip():
        return [], 0, []
    delimiter = "\t" if path.suffix.lower() == ".tsv" else None
    lines = text.splitlines()
    if delimiter is None:
        sample = "\n".join(lines[:10])
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.reader(lines, delimiter=delimiter)
    raw_headers: list[str] = []
    for row in reader:
        if any(c.strip() for c in row):
            raw_headers = [c.lstrip("\ufeff").strip() for c in row]
            break
    if not raw_headers:
        return [], 0, []
    sample_rows: list[dict[str, Any]] = []
    row_count = 0
    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue
        row_count += 1
        if len(sample_rows) < sample_limit:
            raw_dict = {raw_headers[i]: (row[i] if i < len(row) else "") for i in range(len(raw_headers)) if raw_headers[i]}
            sample_rows.append(normalize_row(raw_dict, field_aliases=field_aliases, column_map=column_map))
    return raw_headers, row_count, sample_rows


def read_json_or_jsonl(path: Path) -> Any:
    """Read standard JSON or newline-delimited JSONL (common in analytics warehouse exports)."""
    text = _read_text_with_fallback(path)
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        rows: list[Any] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
        return rows


# ---------------------------------------------------------------------------
# Pure-Stdlib OpenXML (.xlsx) Multi-Tab Workbook Reader
# ---------------------------------------------------------------------------


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _attr_ci(elem: ET.Element, name: str) -> str:
    if name in elem.attrib:
        return elem.attrib[name]
    for k, v in elem.attrib.items():
        if _local_tag(k) == name:
            return v
    return ""


_ROW_OPEN_RE = re.compile(rb"<(?:\w+:)?row\b")
_ROW_CLOSE_RE = re.compile(rb"</(?:\w+:)?row\b[^>]*>")


def _parse_xlsx_shared_strings(zf: zipfile.ZipFile, *, max_index: int | None = None) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    raw = zf.read("xl/sharedStrings.xml")
    if max_index is not None:
        strings: list[str] = []
        with io.BytesIO(raw) as bio:
            for _, elem in ET.iterparse(bio, events=("end",)):
                if _local_tag(elem.tag) == "si":
                    parts: list[str] = []
                    for sub in elem.iter():
                        if _local_tag(sub.tag) == "t" and sub.text:
                            parts.append(sub.text)
                    strings.append("".join(parts))
                    elem.clear()
                    if len(strings) > max_index:
                        break
        return strings
    root = ET.fromstring(raw)
    strings = []
    for si in root:
        if _local_tag(si.tag) != "si":
            continue
        parts = []
        for child in si:
            tag = _local_tag(child.tag)
            if tag == "t":
                if child.text:
                    parts.append(child.text)
            elif tag == "r":
                for sub in child:
                    if _local_tag(sub.tag) == "t" and sub.text:
                        parts.append(sub.text)
        strings.append("".join(parts))
    return strings


def _extract_xlsx_preview_slice(xml_bytes: bytes, *, max_rows: int = 20) -> tuple[bytes, int]:
    """Return XML prefix containing <=max_rows rows plus exact total non-empty <row> count."""
    non_empty_rows = 0
    slice_end = -1
    seen_rows = 0
    pos = 0
    # Scan <row> ... </row> segments quickly in C-accelerated bytes search/regex
    for m_open in _ROW_OPEN_RE.finditer(xml_bytes):
        start = m_open.start()
        if start < pos:
            continue
        gt = xml_bytes.find(b">", start)
        if gt == -1:
            break
        # Self-closing empty <row .../> has no cells
        if gt > start and xml_bytes[gt - 1 : gt] == b"/":
            pos = gt + 1
            seen_rows += 1
            if seen_rows == max_rows and slice_end == -1:
                slice_end = pos
            continue
        m_close = _ROW_CLOSE_RE.search(xml_bytes, gt + 1)
        if not m_close:
            break
        end = m_close.end()
        pos = end
        seen_rows += 1
        # Check if row contains at least one cell with a non-empty value or text element
        seg = xml_bytes[gt:end]
        if b"<v>" in seg or b"<is>" in seg or b"<is " in seg or b"<t>" in seg or b"<t " in seg:
            non_empty_rows += 1
        if seen_rows == max_rows and slice_end == -1:
            slice_end = end

    if slice_end == -1 or seen_rows <= max_rows:
        return xml_bytes, non_empty_rows

    prefix = xml_bytes[:slice_end] + b"</sheetData></worksheet>"
    return prefix, non_empty_rows


def _is_date_format_code(fmt_code: str) -> bool:
    if not fmt_code:
        return False
    stripped = _QUOTED_STR_RE.sub("", _BRACKET_COLOR_RE.sub("", fmt_code))
    if "$" in stripped or "#" in stripped or "%" in stripped or "0." in stripped:
        # Pure currency/number format even if literal text had y/m/d
        if not any(tok in stripped.lower() for tok in ("yy", "mm", "dd", "hh:mm")):
            return False
    lower = stripped.lower()
    return ("yy" in lower) or ("dd" in lower and "mm" in lower) or ("yyyy" in lower)


def _parse_xlsx_date_style_indices(zf: zipfile.ZipFile) -> set[int]:
    if "xl/styles.xml" not in zf.namelist():
        return set()
    root = ET.fromstring(zf.read("xl/styles.xml"))
    custom_fmts: dict[int, str] = {}
    for num_fmts in root:
        if _local_tag(num_fmts.tag) == "numFmts":
            for nf in num_fmts:
                if _local_tag(nf.tag) == "numFmt":
                    fid = nf.attrib.get("numFmtId")
                    if fid and fid.isdigit():
                        custom_fmts[int(fid)] = nf.attrib.get("formatCode", "")
    date_styles: set[int] = set()
    for elem in root:
        if _local_tag(elem.tag) == "cellXfs":
            for idx, xf in enumerate(elem):
                if _local_tag(xf.tag) != "xf":
                    continue
                fid_str = xf.attrib.get("numFmtId", "")
                if not fid_str.isdigit():
                    continue
                fid = int(fid_str)
                if fid in _EXCEL_DATE_NUMFMT_IDS or _is_date_format_code(custom_fmts.get(fid, "")):
                    date_styles.add(idx)
    return date_styles


def _resolve_xlsx_sheet_targets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    names = set(zf.namelist())
    wb_xml = "xl/workbook.xml"
    if wb_xml not in names:
        return []
    wb_root = ET.fromstring(zf.read(wb_xml))
    rels_map: dict[str, str] = {}
    rels_path = "xl/_rels/workbook.xml.rels"
    if rels_path in names:
        rels_root = ET.fromstring(zf.read(rels_path))
        for rel in rels_root:
            if _local_tag(rel.tag) != "Relationship":
                continue
            rid = rel.attrib.get("Id", "")
            tgt = rel.attrib.get("Target", "").lstrip("/")
            if tgt and not tgt.startswith("xl/"):
                tgt = posixpath.normpath(posixpath.join("xl", tgt))
            if rid and tgt:
                rels_map[rid] = tgt

    sheets_out: list[tuple[str, str]] = []
    sheet_idx = 0
    for elem in wb_root.iter():
        if _local_tag(elem.tag) == "sheet":
            sheet_idx += 1
            sname = elem.attrib.get("name", f"Sheet{sheet_idx}")
            rid = _attr_ci(elem, "id")
            tgt = rels_map.get(rid, f"xl/worksheets/sheet{sheet_idx}.xml")
            if tgt in names:
                sheets_out.append((sname, tgt))
    return sheets_out


def _workbook_uses_1904(zf: zipfile.ZipFile) -> bool:
    if "xl/workbook.xml" not in zf.namelist():
        return False
    wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
    for elem in wb_root.iter():
        if _local_tag(elem.tag) == "workbookPr":
            return elem.attrib.get("date1904", "0") in {"1", "true", "True"}
    return False


def _parse_xlsx_sheet_rows(
    xml_bytes: bytes,
    shared_strings: list[str],
    date_styles: set[int],
    epoch_1904: bool,
) -> list[list[Any]]:
    root = ET.fromstring(xml_bytes)
    grid: list[list[Any]] = []
    prev_row_num = 0
    for row_elem in root.iter():
        if _local_tag(row_elem.tag) != "row":
            continue
        r_attr = row_elem.attrib.get("r", "")
        if r_attr.isdigit():
            row_num = int(r_attr)
            if prev_row_num > 0 and row_num > prev_row_num + 1:
                for _ in range(min(row_num - prev_row_num - 1, 4)):
                    grid.append([])
            prev_row_num = row_num
        row_cells: dict[int, Any] = {}
        next_col = 0
        for cell in row_elem:
            if _local_tag(cell.tag) != "c":
                continue
            ref = cell.attrib.get("r", "")
            m = _CELL_REF_RE.match(ref)
            if m:
                col_idx = _col_letters_to_index(m.group(1))
                next_col = col_idx + 1
            else:
                col_idx = next_col
                next_col += 1

            ctype = cell.attrib.get("t", "")
            style_str = cell.attrib.get("s", "")
            style_idx = int(style_str) if style_str.isdigit() else -1

            val_text: str | None = None
            is_parts: list[str] = []
            for child in cell:
                ctag = _local_tag(child.tag)
                if ctag == "v":
                    val_text = child.text
                elif ctag == "is":
                    for sub in child.iter():
                        if _local_tag(sub.tag) == "t" and sub.text:
                            is_parts.append(sub.text)

            if ctype == "inlineStr":
                parsed_val: Any = "".join(is_parts)
            elif ctype == "s":
                if val_text is not None and val_text.strip().isdigit():
                    s_idx = int(val_text.strip())
                    parsed_val = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                else:
                    parsed_val = ""
            elif ctype == "b":
                parsed_val = val_text in {"1", "true", "True"}
            elif ctype == "e":
                parsed_val = None
            elif ctype == "str":
                parsed_val = val_text if val_text is not None else ""
            else:
                if val_text is None or val_text == "":
                    parsed_val = None
                else:
                    try:
                        fval = float(val_text)
                        if style_idx in date_styles and 1 <= fval <= 2958465:
                            parsed_val = _excel_serial_to_iso(fval, epoch_1904=epoch_1904)
                        elif fval.is_integer() and "." not in val_text and "e" not in val_text.lower():
                            parsed_val = int(val_text)
                        else:
                            parsed_val = fval
                    except ValueError:
                        parsed_val = val_text

            if parsed_val is not None:
                row_cells[col_idx] = parsed_val

        if row_cells:
            max_col = max(row_cells)
            grid.append([row_cells.get(i) for i in range(max_col + 1)])
        elif grid:
            grid.append([])
    while grid and not grid[-1]:
        grid.pop()
    return grid


def _extract_banner_kv(banner_rows: list[list[Any]]) -> dict[str, Any]:
    kv: dict[str, Any] = {}
    for r in banner_rows:
        non_empty = [c for c in r if c is not None and str(c).strip() != ""]
        if len(non_empty) == 1 and ":" in str(non_empty[0]):
            k, v = str(non_empty[0]).split(":", 1)
            ck = canonicalize_header(k)
            if ck and v.strip():
                kv[ck] = coerce_cell_value(v.strip(), ck)
        elif len(non_empty) == 2 and isinstance(non_empty[0], str):
            ck = canonicalize_header(non_empty[0].rstrip(":"))
            if ck:
                kv[ck] = coerce_cell_value(non_empty[1], ck)
    return kv


def _detect_header_row_index(grid: list[list[Any]]) -> int:
    if not grid:
        return 0
    top = grid[: min(15, len(grid))]
    max_width = max((sum(1 for c in r if c is not None and str(c).strip() != "") for r in top), default=0)
    if max_width == 0:
        return 0

    start_idx = 0
    for gap_idx in range(1, min(9, len(top))):
        if not any(c is not None and str(c).strip() != "" for c in top[gap_idx]):
            pre_rows = [r for r in top[:gap_idx] if any(c is not None and str(c).strip() != "" for c in r)]
            post_rows = [r for r in top[gap_idx + 1 :] if sum(1 for c in r if c is not None and str(c).strip() != "") >= 2]
            if pre_rows and post_rows and all(sum(1 for c in r if c is not None and str(c).strip() != "") <= 2 for r in pre_rows):
                start_idx = gap_idx + 1
                break

    best_idx = start_idx
    best_score = -1.0
    for idx in range(start_idx, len(top)):
        row = top[idx]
        non_empty = [c for c in row if c is not None and str(c).strip() != ""]
        if len(non_empty) < 2:
            continue
        str_count = sum(1 for c in non_empty if isinstance(c, str) and not c.strip().lstrip("$-").replace(",", "").replace(".", "").isdigit())
        str_ratio = str_count / len(non_empty)
        density = len(non_empty) / max_width
        # Prefer earliest wide row that consists overwhelmingly of non-numeric header labels
        if str_ratio >= 0.65 and density >= 0.55:
            next_row_bonus = 1.0 if (idx + 1 < len(grid) and any(c is not None and str(c).strip() != "" for c in grid[idx + 1])) else 0.0
            score = str_ratio * 2.0 + density + next_row_bonus - (idx * 0.05)
            if score > best_score:
                best_score = score
                best_idx = idx
    return best_idx


def _extract_table_from_grid(
    grid: list[list[Any]],
    *,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    if not grid:
        return [], [], {}
    h_idx = _detect_header_row_index(grid)
    banner_kv = _extract_banner_kv(grid[:h_idx])
    raw_headers = grid[h_idx]
    headers: list[str] = []
    seen_counts: dict[str, int] = {}
    for c_idx, cell in enumerate(raw_headers):
        h = str(cell).lstrip("\ufeff").strip() if cell is not None else ""
        h = " ".join(h.split())
        if not h:
            h = f"col_{c_idx + 1}"
        if h in seen_counts:
            seen_counts[h] += 1
            h = f"{h}_{seen_counts[h]}"
        else:
            seen_counts[h] = 1
        headers.append(h)

    rows: list[dict[str, Any]] = []
    for raw_row in grid[h_idx + 1 :]:
        if not raw_row or all(c is None or str(c).strip() == "" for c in raw_row):
            continue
        row_dict: dict[str, Any] = {}
        for col_i, h in enumerate(headers):
            val = raw_row[col_i] if col_i < len(raw_row) else None
            row_dict[h] = val
        rows.append(normalize_row(row_dict, field_aliases=field_aliases, column_map=column_map))

    return headers, rows, banner_kv


def read_xlsx_workbook(
    path: Path,
    *,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read every worksheet from an .xlsx workbook via pure stdlib XML parsing."""
    sheets: dict[str, list[dict[str, Any]]] = {}
    sheet_headers: dict[str, list[str]] = {}
    sheet_order: list[str] = []
    metadata_kv: dict[str, Any] = {}

    with zipfile.ZipFile(path, "r") as zf:
        shared_strings = _parse_xlsx_shared_strings(zf)
        date_styles = _parse_xlsx_date_style_indices(zf)
        epoch_1904 = _workbook_uses_1904(zf)
        targets = _resolve_xlsx_sheet_targets(zf)

        for sname, spath in targets:
            grid = _parse_xlsx_sheet_rows(zf.read(spath), shared_strings, date_styles, epoch_1904)
            headers, rows, banner_kv = _extract_table_from_grid(
                grid,
                field_aliases=field_aliases,
                column_map=column_map,
            )
            sheet_order.append(sname)
            sheet_headers[sname] = headers
            sheets[sname] = rows
            metadata_kv.update(banner_kv)

            # Extract key/value parameter sheets automatically
            norm_sname = canonicalize_header(sname)
            if any(tok in norm_sname for tok in ("param", "metadata", "config", "assumption", "summary")) and rows:
                h_canons = [canonicalize_header(h) for h in headers]
                if len(h_canons) >= 2 and any(k in h_canons[0] for k in ("key", "param", "metric", "setting", "field")):
                    val_col = headers[1]
                    key_col = headers[0]
                    for r in rows:
                        k_raw = r.get(key_col)
                        if k_raw:
                            ck = canonicalize_header(str(k_raw))
                            if ck and r.get(val_col) not in (None, ""):
                                metadata_kv[ck] = coerce_cell_value(r.get(val_col), ck)

    return {
        "sheets": sheets,
        "sheet_order": sheet_order,
        "sheet_headers": sheet_headers,
        "metadata_kv": metadata_kv,
    }


def _inspect_xlsx_fast(
    path: Path,
    *,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
    max_preview_rows: int = 20,
) -> dict[str, Any]:
    """Sub-100ms structural preview of all .xlsx tabs (headers, exact row count, sample_row)."""
    sheets: dict[str, list[dict[str, Any]]] = {}
    sheet_headers: dict[str, list[str]] = {}
    sheet_row_counts: dict[str, int] = {}
    sheet_order: list[str] = []
    metadata_kv: dict[str, Any] = {}

    with zipfile.ZipFile(path, "r") as zf:
        date_styles = _parse_xlsx_date_style_indices(zf)
        epoch_1904 = _workbook_uses_1904(zf)
        targets = _resolve_xlsx_sheet_targets(zf)

        previews: list[tuple[str, bytes, int]] = []
        max_s_idx = -1
        for sname, spath in targets:
            xml_bytes = zf.read(spath)
            slice_xml, total_nonempty = _extract_xlsx_preview_slice(xml_bytes, max_rows=max_preview_rows)
            previews.append((sname, slice_xml, total_nonempty))
            for m_idx in re.finditer(rb't="s"[^>]*><v>(\d+)</v>', slice_xml):
                idx_val = int(m_idx.group(1))
                if idx_val > max_s_idx:
                    max_s_idx = idx_val

        shared_strings = _parse_xlsx_shared_strings(zf, max_index=max_s_idx if max_s_idx >= 0 else 0)

        for sname, slice_xml, total_nonempty in previews:
            grid = _parse_xlsx_sheet_rows(slice_xml, shared_strings, date_styles, epoch_1904)
            h_idx = _detect_header_row_index(grid) if grid else 0
            headers, sample_rows, banner_kv = _extract_table_from_grid(
                grid,
                field_aliases=field_aliases,
                column_map=column_map,
            )
            prefix_nonempty = sum(1 for r in grid if any(c is not None and str(c).strip() != "" for c in r))
            prefix_data_nonempty = sum(
                1 for r in grid[h_idx + 1 :] if any(c is not None and str(c).strip() != "" for c in r)
            )
            non_data_rows = max(0, prefix_nonempty - prefix_data_nonempty)
            data_count = max(len(sample_rows), total_nonempty - non_data_rows)
            sheet_order.append(sname)
            sheet_headers[sname] = headers
            sheets[sname] = sample_rows
            sheet_row_counts[sname] = data_count
            metadata_kv.update(banner_kv)

            norm_sname = canonicalize_header(sname)
            if any(tok in norm_sname for tok in ("param", "metadata", "config", "assumption", "summary")) and sample_rows:
                h_canons = [canonicalize_header(h) for h in headers]
                if len(h_canons) >= 2 and any(k in h_canons[0] for k in ("key", "param", "metric", "setting", "field")):
                    val_col = headers[1]
                    key_col = headers[0]
                    for r in sample_rows:
                        k_raw = r.get(key_col)
                        if k_raw:
                            ck = canonicalize_header(str(k_raw))
                            if ck and r.get(val_col) not in (None, ""):
                                metadata_kv[ck] = coerce_cell_value(r.get(val_col), ck)

    return {
        "sheets": sheets,
        "sheet_order": sheet_order,
        "sheet_headers": sheet_headers,
        "sheet_row_counts": sheet_row_counts,
        "metadata_kv": metadata_kv,
    }


# ---------------------------------------------------------------------------
# Pure-Stdlib OpenXML (.docx) Reader
# ---------------------------------------------------------------------------


def _docx_para_text_and_style(p_elem: ET.Element) -> tuple[str, str]:
    style = ""
    parts: list[str] = []
    for child in p_elem:
        ctag = _local_tag(child.tag)
        if ctag == "pPr":
            for prop in child:
                if _local_tag(prop.tag) == "pStyle":
                    style = _attr_ci(prop, "val")
                    break
        elif ctag in {"r", "hyperlink", "ins", "smartTag"}:
            for node in child.iter():
                ntag = _local_tag(node.tag)
                if ntag == "t" and node.text:
                    parts.append(node.text)
                elif ntag == "tab":
                    parts.append("\t")
                elif ntag in {"br", "cr"}:
                    parts.append("\n")
    return "".join(parts).strip(), style


def _docx_extract_table(
    tbl_elem: ET.Element,
    section_heading: str,
    table_idx: int,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    raw_rows: list[list[str]] = []
    for tr in tbl_elem:
        if _local_tag(tr.tag) != "tr":
            continue
        cells: list[str] = []
        for tc in tr:
            if _local_tag(tc.tag) != "tc":
                continue
            span = 1
            text_parts: list[str] = []
            for tc_child in tc:
                ttag = _local_tag(tc_child.tag)
                if ttag == "tcPr":
                    for prop in tc_child:
                        if _local_tag(prop.tag) == "gridSpan":
                            val = _attr_ci(prop, "val")
                            if val.isdigit():
                                span = max(1, int(val))
                elif ttag == "p":
                    ptxt, _ = _docx_para_text_and_style(tc_child)
                    if ptxt:
                        text_parts.append(ptxt)
            cell_text = "\n".join(text_parts).strip()
            cells.append(cell_text)
            for _ in range(span - 1):
                cells.append("")
        if any(cells):
            raw_rows.append(cells)

    if not raw_rows:
        return {"table_index": table_idx, "section": section_heading, "headers": [], "rows": []}

    raw_hdrs = raw_rows[0]
    headers: list[str] = []
    seen: dict[str, int] = {}
    for idx, h in enumerate(raw_hdrs):
        label = " ".join((h or "").split()) or f"col_{idx + 1}"
        if label in seen:
            seen[label] += 1
            label = f"{label}_{seen[label]}"
        else:
            seen[label] = 1
        headers.append(label)

    rows: list[dict[str, Any]] = []
    for r in raw_rows[1:]:
        row_dict = {h: (r[i] if i < len(r) else "") for i, h in enumerate(headers)}
        rows.append(normalize_row(row_dict, field_aliases=field_aliases, column_map=column_map))

    return {
        "table_index": table_idx,
        "section": section_heading,
        "headers": headers,
        "rows": rows,
    }


def _read_docx_annotations(zf: zipfile.ZipFile) -> list[str]:
    notes: list[str] = []
    for part_name in ("word/footnotes.xml", "word/comments.xml"):
        if part_name not in zf.namelist():
            continue
        root = ET.fromstring(zf.read(part_name))
        for elem in root:
            ltag = _local_tag(elem.tag)
            if ltag in {"footnote", "comment"}:
                fid = _attr_ci(elem, "id")
                if fid in {"-1", "0"} and ltag == "footnote":
                    continue
                texts = [n.text for n in elem.iter() if _local_tag(n.tag) == "t" and n.text]
                combined = "".join(texts).strip()
                if combined:
                    notes.append(f"[{ltag}:{fid}] {combined}")
    return notes


def read_docx(
    path: Path,
    *,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Read headings, ordered sections, full text, embedded tables, and annotations from .docx."""
    paragraphs: list[dict[str, Any]] = []
    headings: list[str] = []
    tables: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    metadata_kv: dict[str, Any] = {}
    title = path.stem

    with zipfile.ZipFile(path, "r") as zf:
        if "word/document.xml" not in zf.namelist():
            return {
                "title": title,
                "headings": [],
                "paragraphs": [],
                "sections": [],
                "tables": [],
                "full_text": "",
                "metadata_kv": {},
                "annotations": [],
            }
        doc_root = ET.fromstring(zf.read("word/document.xml"))
        annotations = _read_docx_annotations(zf)

    body = None
    for child in doc_root:
        if _local_tag(child.tag) == "body":
            body = child
            break
    if body is None:
        return {
            "title": title,
            "headings": [],
            "paragraphs": [],
            "sections": [],
            "tables": [],
            "full_text": "",
            "metadata_kv": {},
            "annotations": annotations,
        }

    current_section = title
    curr_sec_paras: list[str] = []

    def _flush_section() -> None:
        if curr_sec_paras or current_section != title:
            sections.append(
                {
                    "heading": current_section,
                    "paragraphs": list(curr_sec_paras),
                    "text": "\n".join(curr_sec_paras),
                }
            )

    tbl_idx = 0
    all_lines: list[str] = []
    for elem in body:
        ltag = _local_tag(elem.tag)
        if ltag == "p":
            txt, style = _docx_para_text_and_style(elem)
            if not txt:
                continue
            style_lower = style.lower()
            is_title = style_lower == "title"
            is_heading = style_lower.startswith(("heading", "title", "subtitle")) or (
                len(txt) <= 120 and bool(_SECTION_HEADING_RE.match(txt)) and not txt.endswith(".")
            )
            if is_title and title == path.stem:
                title = txt
            if is_heading:
                _flush_section()
                curr_sec_paras = []
                current_section = txt
                headings.append(txt)
            else:
                curr_sec_paras.append(txt)
                if ":" in txt and len(txt) <= 120:
                    k, v = txt.split(":", 1)
                    ck = canonicalize_header(k)
                    if ck and v.strip() and len(ck) <= 40:
                        metadata_kv.setdefault(ck, coerce_cell_value(v.strip(), ck))
            paragraphs.append({"text": txt, "style": style, "section": current_section, "is_heading": is_heading})
            all_lines.append(txt)
        elif ltag == "tbl":
            tbl = _docx_extract_table(elem, current_section, tbl_idx, field_aliases=field_aliases, column_map=column_map)
            tbl_idx += 1
            tables.append(tbl)
            if len(tbl["headers"]) == 2:
                h0 = canonicalize_header(tbl["headers"][0])
                if any(tok in h0 for tok in ("key", "field", "metric", "parameter", "attribute")):
                    for r in tbl["rows"]:
                        k_raw = r.get(tbl["headers"][0])
                        v_raw = r.get(tbl["headers"][1])
                        if k_raw and v_raw not in (None, ""):
                            ck = canonicalize_header(str(k_raw))
                            if ck:
                                metadata_kv.setdefault(ck, coerce_cell_value(v_raw, ck))

    _flush_section()
    return {
        "title": title,
        "headings": headings,
        "paragraphs": paragraphs,
        "sections": sections,
        "tables": tables,
        "full_text": "\n".join(all_lines),
        "metadata_kv": metadata_kv,
        "annotations": annotations,
    }


# ---------------------------------------------------------------------------
# Skill-Aware Multi-Tab Workbook & Document Routing Registry
# ---------------------------------------------------------------------------

# Maps skill_id -> routing profile for multi-tab .xlsx and multi-section .docx files
SKILL_INGESTION_PROFILES: dict[str, dict[str, Any]] = {
    "ap-three-way-match": {
        "primary_key": "invoices",
        "sheet_routes": {
            "purchase_orders": ("purchase_order", "ekpo", "po_line", "po_header"),
            "goods_receipts": ("goods_receipt", "ekbe_gr", "gr_line", "receipt"),
            "invoices": ("vendor_invoice", "rbkp", "rseg", "ap_invoice", "invoice"),
            "fx_rates": ("fx_rate", "tcurr", "currency_rate"),
            "decimal_places": ("tcurx", "decimal_place", "currency_decimal"),
        },
        "field_aliases": {
            "unit_price_raw": "unit_price",
            "netpr": "unit_price",
        },
        "row_hints": {
            "purchase_orders": {"ordered_qty", "po_number"},
            "goods_receipts": {"received_qty", "po_number"},
            "invoices": {"invoiced_qty", "invoice_id", "invoice_number"},
        },
        "required_fields": {
            "purchase_orders": (("po_number",), ("ordered_qty", "quantity", "qty"), ("unit_price", "amount")),
            "goods_receipts": (("po_number",), ("received_qty", "quantity", "qty")),
            "invoices": (("po_number",), ("invoice_id", "invoice_number"), ("unit_price", "amount")),
        },
    },
    "gr-ir-clearing-orchestrator": {
        "primary_key": "gr_ir_postings",
        "sheet_routes": {
            "gr_ir_postings": ("gr_ir", "clearing", "ekbe", "open_item", "posting"),
            "fx_rates": ("fx_rate", "tcurr"),
            "decimal_places": ("tcurx", "decimal"),
        },
        "scalar_keys": ("as_of_date",),
        "row_hints": {"gr_ir_postings": {"gr_amount", "ir_amount", "po_number"}},
        "required_fields": {
            "gr_ir_postings": (("po_number",), ("gr_amount", "ir_amount", "gr_qty", "ir_qty", "amount")),
        },
    },
    "pnl-budget-variance-bridge": {
        "primary_key": "lines",
        "sheet_routes": {
            "lines": ("gl", "pnl", "p_l", "consolidated_summary", "variance", "budget"),
            "fx_rates": ("fx_schedule", "fx_rate", "tcurr", "currency_rate"),
            "_exclude_aux": ("chart_of_account", "coa", "ar_open", "aging", "open_invoice", "receivable"),
        },
        "merge_matching_sheets": {"lines"},
        "row_hints": {
            "lines": {"account_id", "budget_local", "actual_local", "budget_usd", "actual_usd"},
            "fx_rates": {"currency", "fx_rate", "rate_to_usd"},
        },
        "required_fields": {
            "lines": (
                ("account_id", "account_name"),
                ("actual_local", "actual_usd", "actual"),
                ("budget_local", "budget_usd", "budget"),
            ),
        },
    },
    "ar-aging-collections-audit": {
        "primary_key": "open_items",
        "sheet_routes": {
            "open_items": ("ar_open", "aging", "receivable", "open_invoice", "open_item"),
        },
        "scalar_keys": ("as_of_date", "trailing_90d_credit_sales_usd"),
        "field_aliases": {"amount_usd": "open_amount_usd", "balance_usd": "open_amount_usd"},
        "row_hints": {"open_items": {"open_amount_usd", "customer_id", "due_date"}},
        "required_fields": {
            "open_items": (("customer_id", "customer_name"), ("open_amount_usd",), ("due_date",)),
        },
    },
    "workforce-attrition-comp-audit": {
        "primary_key": "workers",
        "sheet_routes": {
            "workers": ("worker", "roster", "workforce", "employee", "hris", "history"),
            "comp_bands": ("comp_band", "salary_band", "grade_band", "pay_band"),
            "fx_rates": ("fx_rate", "currency_rate"),
        },
        "scalar_keys": ("as_of_date",),
        "row_hints": {"workers": {"worker_id", "job_level", "base_pay_amount"}, "comp_bands": {"job_level", "midpoint_usd"}},
        "required_fields": {
            "workers": (("worker_id",), ("job_level", "base_pay_amount", "base_pay")),
            "comp_bands": (("job_level",), ("midpoint_usd",)),
        },
    },
    "structured-hiring-rubric": {
        "primary_key": "candidates",
        "sheet_routes": {
            "candidates": ("candidate", "scorecard", "interview", "rubric", "hiring"),
            "interviewers": ("interviewer", "panel_score", "feedback"),
        },
        "single_entity_root_markers": ("interviewers",),
        "row_hints": {
            "candidates": {"candidate_id", "role"},
            "interviewers": {"candidate_id", "interviewer_id", "score", "evidence_text"},
        },
        "required_fields": {
            "candidates": (("candidate_id", "candidate_name"), ("interviewers", "interviewer_id", "score")),
        },
    },
    "employee-onboarding-navigator": {
        "primary_key": "hires",
        "sheet_routes": {
            "hires": ("hire", "new_hire", "onboarding", "employee"),
            "tasks": ("task", "checklist", "provisioning"),
        },
        "scalar_keys": ("as_of_date",),
        "single_entity_root_markers": ("employee_id",),
        "row_hints": {
            "hires": {"employee_id", "start_date"},
            "tasks": {"employee_id", "task_id", "due_day_offset"},
        },
        "required_fields": {
            "hires": (("employee_id", "employee_name"), ("start_date", "tasks", "task_id")),
        },
    },
    "pipeline-hygiene-slippage": {
        "primary_key": "opportunities",
        "table_aliases": {"opportunities": ("records",)},
        "sheet_routes": {
            "opportunities": ("pipeline", "crm", "deal", "opportunit"),
            "fx_rates": ("fx_rate",),
        },
        "scalar_keys": ("remaining_quota_usd", "stage_median_days"),
        "row_hints": {"opportunities": {"opportunity_id", "stage", "forecast_category"}},
        "required_fields": {
            "opportunities": (("opportunity_id", "name"), ("stage", "forecast_category", "amount")),
        },
    },
    "rfp-questionnaire-responder": {
        "primary_key": "questions",
        "table_aliases": {"questions": ("requirements",)},
        "sheet_routes": {
            "questions": ("rfp", "question", "requirement"),
            "answer_library": ("answer_bank", "answer_library", "approved_bid"),
        },
        "row_hints": {"questions": {"question_id", "question"}, "answer_library": {"answer", "source_id"}},
        "required_fields": {
            "questions": (("question_id", "id"), ("question", "text")),
            "answer_library": (("answer",),),
        },
    },
    "deal-desk-quote-guard": {
        "primary_key": "quotes",
        "sheet_routes": {
            "quotes": ("quote", "deal_desk", "dealdesk", "pricing"),
            "line_items": ("line_item", "quote_line", "sku_line"),
        },
        "single_entity_keys": ("quote",),
        "single_entity_root_markers": ("quote_id",),
        "row_hints": {
            "quotes": {"quote_id", "customer_name", "term_months"},
            "line_items": {"quote_id", "unit_list_price_annual", "unit_net_price_annual"},
        },
        "required_fields": {
            "quotes": (
                ("quote_id",),
                ("customer_name", "term_months", "line_items", "unit_net_price_annual", "unit_list_price_annual"),
            ),
        },
    },
    "supplier-rfx-tariff-modeler": {
        "primary_key": "bids",
        "sheet_routes": {"bids": ("rfx", "bid", "supplier", "quote")},
        "scalar_keys": ("annual_demand_units", "tariff_shock_pct", "tariff_shock_countries"),
        "row_hints": {"bids": {"supplier_id", "unit_fob_usd", "origin_country"}},
        "required_fields": {
            "bids": (("supplier_id", "supplier_name"), ("unit_fob_usd",), ("origin_country", "base_tariff_pct")),
        },
    },
    "bom-cost-rollup-variance": {
        "primary_key": "bom_edges",
        "sheet_routes": {
            "bom_edges": ("bom", "tree", "edge", "bill_of_material"),
            "items": ("item", "sku", "plant_master", "material", "cost"),
        },
        "scalar_keys": ("target_assemblies",),
        "row_hints": {"bom_edges": {"parent_sku", "child_sku", "qty_per_parent"}, "items": {"sku", "standard_unit_cost_usd"}},
        "required_fields": {
            "bom_edges": (("parent_sku",), ("child_sku",), ("qty_per_parent",)),
            "items": (("sku",), ("standard_unit_cost_usd", "actual_unit_cost_usd")),
        },
    },
    "winning-proposal-architect": {
        "primary_key": "phases",
        "sheet_routes": {
            "phases": ("phase", "staffing", "pyramid", "proposal"),
            "roles": ("role", "rate_card", "resource_plan"),
        },
        "row_hints": {
            "phases": {"phase_name", "duration_weeks"},
            "roles": {"phase_name", "bill_rate_hourly", "cost_rate_hourly"},
        },
        "required_fields": {
            "phases": (("phase_name",), ("duration_weeks", "roles", "bill_rate_hourly")),
        },
    },
    "sow-scope-margin-auditor": {
        "primary_key": "deliverables",
        "sheet_routes": {
            "deliverables": ("deliverable", "sow", "milestone"),
            "clauses": ("clause", "term"),
        },
        "scalar_keys": ("sow_id", "fixed_fee_usd", "estimated_cost_usd", "acceptance_business_days", "client_dependencies"),
        "required_fields": {
            "deliverables": (("deliverable_id",), ("acceptance_criteria", "title")),
            "clauses": (("clause_id", "text"),),
        },
    },
    "bench-skill-demand-matcher": {
        "primary_key": "consultants",
        "sheet_routes": {
            "consultants": ("bench", "consultant", "roster", "talent"),
            "demands": ("demand", "staffing_req", "role"),
        },
        "row_hints": {"consultants": {"consultant_id", "skills"}, "demands": {"role_id", "required_skills"}},
        "required_fields": {
            "consultants": (("consultant_id",), ("skills",)),
            "demands": (("role_id",), ("required_skills",)),
        },
    },
    "critical-escalation-warroom": {
        "primary_key": "escalations",
        "sheet_routes": {"escalations": ("escalation", "warroom", "account")},
        "required_fields": {
            "escalations": (("escalation_id", "account_name"), ("arr_usd", "open_sev1_tickets", "sla_breached_count")),
        },
    },
    "csat-churn-signal-miner": {
        "primary_key": "responses",
        "sheet_routes": {"responses": ("csat", "nps", "verbatim", "survey", "response")},
        "required_fields": {
            "responses": (("response_id", "account_id"), ("csat_score", "nps_score", "verbatim")),
        },
    },
    "troubleshooting-tree-author": {
        "primary_key": "nodes",
        "sheet_routes": {"nodes": ("node", "decision", "tree")},
        "scalar_keys": ("root_node_id",),
        "required_fields": {
            "nodes": (("node_id",), ("node_type", "branches")),
        },
    },
    "commercial-credit-memo-analyst": {
        "primary_key": "borrowers",
        "sheet_routes": {"borrowers": ("borrower", "credit", "financial", "covenant")},
        "single_entity_root_markers": ("ebitda_usd",),
        "row_hints": {"borrowers": {"borrower_id", "ebitda_usd", "total_debt_usd"}},
        "required_fields": {
            "borrowers": (("borrower_id", "borrower_name"), ("ebitda_usd",), ("total_debt_usd",)),
        },
    },
    "kyc-aml-screening-dossier": {
        "primary_key": "ownership_edges",
        "sheet_routes": {
            "ownership_edges": ("ownership", "ubo", "registry", "sharehold"),
            "transactions": ("transaction", "wire", "tx"),
        },
        "scalar_keys": ("target_entity_id", "rolling_30d_volume_usd", "trailing_90d_monthly_avg_usd"),
        "row_hints": {"ownership_edges": {"owner_id", "target_id", "direct_pct"}, "transactions": {"tx_id", "amount_usd"}},
        "required_fields": {
            "ownership_edges": (("owner_id",), ("target_id",), ("direct_pct",)),
            "transactions": (("tx_id",), ("amount_usd",)),
        },
    },
    "insurance-claims-triage-pack": {
        "primary_key": "claims",
        "sheet_routes": {
            "claims": ("claim", "loss", "triage"),
            "policies": ("polic", "coverage_schedule", "underwriting"),
        },
        "single_entity_root_markers": ("claim_id",),
        "row_hints": {
            "claims": {"claim_id", "claimed_amount_usd"},
            "policies": {"policy_id", "effective_date", "expiration_date", "aggregate_limit_usd"},
        },
        "required_fields": {
            "claims": (("claim_id",), ("claimed_amount_usd",), ("peril", "policy", "policy_id")),
        },
    },
    "asset-reliability-spares-planner": {
        "primary_key": "spare_parts",
        "sheet_routes": {"spare_parts": ("spare", "safetystock", "safety_stock", "inventory", "cmms")},
        "row_hints": {"spare_parts": {"part_id", "on_hand_qty", "observed_failures"}},
        "required_fields": {
            "spare_parts": (("part_id",), ("on_hand_qty",), ("observed_failures", "lead_time_days")),
        },
    },
    "quality-capex-rca-copilot": {
        "primary_key": "events",
        "sheet_routes": {
            "events": ("inspection", "lot", "defect", "scrap", "quality"),
            "capex_proposals": ("capex", "proposal"),
        },
        "row_hints": {"events": {"defect_type", "scrap_cost_usd"}, "capex_proposals": {"proposal_id", "capex_cost_usd"}},
        "required_fields": {
            "events": (("defect_type",), ("scrap_cost_usd", "scrap_units")),
            "capex_proposals": (("proposal_id",), ("capex_cost_usd",)),
        },
    },
    "ehs-safety-permit-auditor": {
        "primary_key": "permits",
        "sheet_routes": {"permits": ("permit", "ehs", "hse", "ptw")},
        "scalar_keys": ("as_of_date",),
        "row_hints": {"permits": {"permit_id", "gas_test_lel_pct", "loto_isolated"}},
        "required_fields": {
            "permits": (("permit_id",), ("gas_test_lel_pct", "gas_test_o2_pct", "loto_isolated")),
        },
    },
    "clinical-protocol-feasibility": {
        "primary_key": "visits",
        "sheet_routes": {
            "visits": ("soa", "schedule_of_assessment", "visit"),
            "endpoints": ("endpoint", "efficacy"),
            "sites": ("site", "feasibility"),
        },
        "scalar_keys": ("protocol_id", "target_sample_size", "enrollment_window_months"),
        "row_hints": {
            "visits": {"visit_id", "window_start_day", "window_end_day", "procedures"},
            "endpoints": {"endpoint_id", "target_visit_day", "required_procedures"},
            "sites": {"site_id", "irb_approved", "projected_monthly_screened"},
        },
        "required_fields": {
            "visits": (("visit_id",), ("procedures",)),
            "endpoints": (("endpoint_id",), ("required_procedures",)),
            "sites": (("site_id",), ("projected_monthly_screened", "irb_approved")),
        },
    },
    "pharmacovigilance-safety-intake": {
        "primary_key": "cases",
        "sheet_routes": {"cases": ("icsr", "safety", "adverse", "case")},
        "scalar_keys": ("as_of_date",),
        "row_hints": {"cases": {"case_id", "adverse_event_term", "awareness_date"}},
        "required_fields": {
            "cases": (("case_id",), ("adverse_event_term",), ("awareness_date",)),
        },
    },
    "prior-auth-medical-necessity": {
        "primary_key": "requests",
        "sheet_routes": {
            "policies": ("policy", "policies", "payer"),
            "requests": ("request", "prior_auth", "auth"),
        },
        "row_hints": {
            "policies": {"cpt_code", "covered_icd10_prefixes", "required_labs"},
            "requests": {"auth_id", "cpt_code", "icd10_codes"},
        },
        "required_fields": {
            "requests": (("auth_id",), ("cpt_code",), ("icd10_codes",)),
            "policies": (("cpt_code",), ("covered_icd10_prefixes",)),
        },
    },
    "store-ops-shrink-copilot": {
        "primary_key": "sku_store_records",
        "table_aliases": {"sku_store_records": ("records",)},
        "sheet_routes": {"sku_store_records": ("shrink", "osa", "store_sku", "inventory")},
        "row_hints": {"sku_store_records": {"store_id", "book_on_hand_qty", "days_since_last_pos_scan"}},
        "required_fields": {
            "sku_store_records": (("store_id",), ("sku",), ("book_on_hand_qty",)),
        },
    },
    "merchandising-assortment-planner": {
        "primary_key": "campaigns",
        "table_aliases": {"campaigns": ("promotions",)},
        "sheet_routes": {"campaigns": ("pos", "promo", "campaign", "weekly_store")},
        "row_hints": {"campaigns": {"campaign_id", "baseline_units", "promo_units"}},
        "required_fields": {
            "campaigns": (
                ("campaign_id", "campaign_name"),
                ("baseline_units", "baseline_revenue_usd"),
                ("promo_units", "promo_revenue_usd"),
            ),
        },
    },
    "supplier-otif-chargeback-auditor": {
        "primary_key": "po_deliveries",
        "table_aliases": {"po_deliveries": ("deliveries",)},
        "sheet_routes": {"po_deliveries": ("otif", "shipment", "carrier", "delivery", "detention")},
        "row_hints": {"po_deliveries": {"po_number", "ordered_units", "received_units", "dwell_minutes"}},
        "required_fields": {
            "po_deliveries": (("po_number",), ("ordered_units",), ("received_units",)),
        },
    },
    "merchant-catalog-trust-gate": {
        "primary_key": "listings",
        "sheet_routes": {
            "listings": ("merchant", "catalog", "listing"),
            "category_medians_usd": ("category_median", "median_usd"),
        },
        "scalar_keys": ("category_medians_usd",),
        "row_hints": {"listings": {"listing_id", "merchant_id", "price_usd"}},
        "required_fields": {
            "listings": (("listing_id",), ("merchant_id",), ("price_usd", "title")),
        },
    },
    "logistics-sla-dispute-resolver": {
        "primary_key": "disputes",
        "table_aliases": {"disputes": ("orders",)},
        "sheet_routes": {"disputes": ("dispute", "geozone", "dispatch_dispute", "order_sla")},
        "row_hints": {"disputes": {"order_id", "zone_id", "promised_total_minutes"}},
        "required_fields": {
            "disputes": (("order_id",), ("promised_total_minutes",), ("actual_total_minutes",)),
        },
    },
    "commission-payout-reconciler": {
        "primary_key": "merchant_payouts",
        "table_aliases": {"merchant_payouts": ("settlements",)},
        "sheet_routes": {"merchant_payouts": ("payout", "gmv", "settlement", "seller")},
        "row_hints": {"merchant_payouts": {"merchant_id", "gross_gmv_local", "actual_psp_settled_amount"}},
        "required_fields": {
            "merchant_payouts": (("merchant_id",), ("gross_gmv_local",), ("actual_psp_settled_amount", "actual_psp_settled")),
        },
    },
    "noc-outage-topology-correlator": {
        "primary_key": "alarms",
        "sheet_routes": {
            "alarms": ("alarm", "ran_core", "fault"),
            "nodes": ("node", "topology_node"),
            "edges": ("edge", "link"),
        },
        "row_hints": {"alarms": {"alarm_code", "node_id"}, "nodes": {"node_id", "node_type"}},
        "required_fields": {
            "alarms": (("node_id",), ("alarm_code",)),
            "nodes": (("node_id",), ("node_type",)),
            "edges": (("upstream_node_id",), ("downstream_node_id",)),
        },
    },
    "field-dispatch-spares-prep": {
        "primary_key": "work_orders",
        "sheet_routes": {
            "work_orders": ("work_order", "dispatch"),
            "technicians": ("tech", "engineer"),
            "depot_spares_qty": ("depot_spare", "spare_stock"),
        },
        "scalar_keys": ("dispatch_date", "depot_spares_qty"),
        "required_fields": {
            "work_orders": (("work_order_id",), ("site_id", "required_skills", "required_spares")),
            "technicians": (("tech_id",), ("skills",)),
        },
    },
    "b2b-order-fallout-resolver": {
        "primary_key": "fallout_orders",
        "table_aliases": {"fallout_orders": ("orders",)},
        "sheet_routes": {"fallout_orders": ("fallout", "mvno", "b2b_order")},
        "row_hints": {"fallout_orders": {"order_id", "fallout_code", "mrc_usd"}},
        "required_fields": {
            "fallout_orders": (("order_id",), ("fallout_code", "error_message"), ("mrc_usd",)),
        },
    },
    "citizen-case-eligibility-triager": {
        "primary_key": "cases",
        "sheet_routes": {"cases": ("applicant", "benefit", "citizen", "case")},
        "required_fields": {
            "cases": (("case_id",), ("household_size",), ("annual_household_income_usd", "annual_income_usd")),
        },
    },
    "procurement-tender-evaluator": {
        "primary_key": "bids",
        "table_aliases": {"bids": ("proposals",)},
        "sheet_routes": {"bids": ("tender", "bid", "vendor", "proposal")},
        "scalar_keys": ("tender_id",),
        "required_fields": {
            "bids": (("bid_id", "vendor_name"), ("total_bid_price_usd",), ("technical_score_100",)),
        },
    },
    "grant-accreditation-evidence-pack": {
        "primary_key": "budget_lines",
        "sheet_routes": {
            "budget_lines": ("budget", "grant"),
            "pi_effort_allocations": ("effort", "pi_effort", "faculty"),
            "accreditation_artifacts": ("accreditation", "artifact", "ssr"),
        },
        "scalar_keys": ("as_of_date", "grant_id", "required_cost_share_pct", "sponsor_fa_cap_pct"),
        "row_hints": {
            "budget_lines": {"line_id", "category", "amount_usd"},
            "pi_effort_allocations": {"pi_name", "existing_commitments_pct", "proposed_effort_pct"},
            "accreditation_artifacts": {"artifact_id", "last_verified_date", "status"},
        },
        "required_fields": {
            "budget_lines": (("line_id",), ("category",), ("amount_usd",)),
            "pi_effort_allocations": (("pi_name",), ("proposed_effort_pct",)),
            "accreditation_artifacts": (("artifact_id",), ("status",)),
        },
    },
    "contract-playbook-redliner": {
        "primary_key": "clauses",
        "sheet_routes": {"clauses": ("clause", "redline")},
        "scalar_keys": ("contract_id", "contract_type", "counterparty"),
        "row_hints": {"clauses": {"clause_id", "clause_text"}},
        "required_fields": {
            "clauses": (("clause_id", "id"), ("clause_text", "text", "clause_family")),
        },
    },
    "executed-obligation-extractor": {
        "primary_key": "contracts",
        "sheet_routes": {
            "contracts": ("contract", "renewal", "master"),
            "obligations": ("obligation", "deliverable", "covenant"),
        },
        "scalar_keys": ("as_of_date",),
        "row_hints": {
            "contracts": {"contract_id", "counterparty", "renewal_date"},
            "obligations": {"contract_id", "obligation_type", "due_date"},
        },
        "required_fields": {
            "contracts": (("contract_id",), ("counterparty", "renewal_date", "annual_value_usd")),
            "obligations": (("contract_id", "obligation_type"),),
        },
    },
    "regulatory-change-mapper": {
        "primary_key": "controls",
        "sheet_routes": {"articles": ("article", "regulation"), "controls": ("control", "gap")},
        "scalar_keys": ("as_of_date",),
        "row_hints": {
            "articles": {"article_id", "regulation", "required_domains"},
            "controls": {"control_id", "control_status", "mapped_articles"},
        },
        "required_fields": {
            "controls": (("control_id",), ("control_status", "mapped_articles", "domain")),
            "articles": (("article_id", "regulation"),),
        },
    },
    "policy-sop-answering": {
        "primary_key": "clauses",
        "table_aliases": {"clauses": ("records",)},
        "sheet_routes": {"clauses": ("policy", "sop", "clause")},
        "scalar_keys": ("query", "jurisdiction", "entity", "as_of_date"),
        "row_hints": {"clauses": {"clause_id", "text", "jurisdiction"}},
        "required_fields": {
            "clauses": (("clause_id", "id"), ("text", "clause_text", "title")),
        },
    },
    "cross-source-knowledge-synthesis": {
        "primary_key": "sources",
        "table_aliases": {"sources": ("records",)},
        "sheet_routes": {"sources": ("source", "doc"), "draft_claims": ("claim", "draft")},
        "scalar_keys": ("as_of_date",),
        "required_fields": {
            "sources": (("id", "doc_id", "source_id"), ("title", "name")),
            "draft_claims": (("claim_id", "id"), ("statement", "text")),
        },
    },
    "knowledge-gap-freshness-audit": {
        "primary_key": "documents",
        "table_aliases": {"documents": ("records",)},
        "sheet_routes": {"documents": ("document", "knowledge", "article", "gap")},
        "scalar_keys": ("as_of_date", "ticket_topics", "inactive_owners"),
        "required_fields": {
            "documents": (("doc_id", "id"), ("title",)),
        },
    },
    "daily-executive-briefing": {
        "primary_key": "events",
        "sheet_routes": {
            "events": ("event", "calendar", "meeting"),
            "priority_threads": ("thread", "email", "priority"),
            "commitments": ("commitment", "action"),
        },
        "scalar_keys": ("briefing_date",),
        "required_fields": {
            "events": (("event_id", "title"),),
            "priority_threads": (("thread_id", "subject"),),
            "commitments": (("id", "commitment_id", "task", "owner"),),
        },
    },
    "meeting-to-execution-pack": {
        "primary_key": "segments",
        "sheet_routes": {
            "segments": ("transcript", "segment"),
            "prior_open_commitments": ("commitment", "prior", "action"),
        },
        "raw_text_key": "raw_transcript",
        "scalar_keys": ("meeting_title",),
        "required_fields": {
            "segments": (("text", "transcript"),),
            "prior_open_commitments": (("id", "commitment_id", "task"),),
        },
    },
    "stakeholder-account-prep": {
        "primary_key": "accounts",
        "table_aliases": {"accounts": ("records",)},
        "sheet_routes": {"accounts": ("account", "stakeholder", "customer")},
        "scalar_keys": ("as_of_date",),
        "single_entity_keys": ("account",),
        "single_entity_root_markers": ("account_id", "account_name"),
        "required_fields": {
            "accounts": (("account_id", "account_name"), ("arr_usd", "renewal_date", "nps_score")),
        },
    },
    "incident-triage-routing": {
        "primary_key": "incidents",
        "table_aliases": {"incidents": ("records",)},
        "sheet_routes": {"incidents": ("incident", "sev", "ticket"), "runbooks": ("runbook", "kb")},
        "scalar_keys": ("as_of_time",),
        "required_fields": {
            "incidents": (("incident_id", "number"), ("priority", "short_description", "state")),
            "runbooks": (("runbook_id", "title"),),
        },
    },
    "change-risk-cab-review": {
        "primary_key": "changes",
        "table_aliases": {"changes": ("records",)},
        "sheet_routes": {"changes": ("change", "chg", "cab"), "freeze_windows": ("freeze", "blackout")},
        "required_fields": {
            "changes": (("change_id",), ("cmdb_ci", "service_tier", "planned_start")),
            "freeze_windows": (("name", "start_time"),),
        },
    },
    "problem-rca-kb-generator": {
        "primary_key": "tickets",
        "table_aliases": {"tickets": ("records",)},
        "sheet_routes": {"tickets": ("ticket", "problem", "incident"), "kcs_drafts": ("kcs", "kb", "article")},
        "scalar_keys": ("sample_window_days",),
        "required_fields": {
            "tickets": (("ticket_id",), ("category", "root_cause_signature", "state")),
            "kcs_drafts": (("article_id", "title"),),
        },
    },
    "legacy-code-to-prd": {
        "primary_key": "modules",
        "table_aliases": {"modules": ("files",)},
        "sheet_routes": {
            "modules": ("module", "code", "service", "inventory"),
            "requirements": ("requirement", "prd", "spec"),
            "tests": ("test", "coverage"),
        },
        "required_fields": {
            "modules": (("path", "module"), ("source", "entrypoints", "cyclomatic_complexity")),
            "requirements": (("req_id", "title"),),
            "tests": (("test_id",),),
        },
    },
    "sre-incident-postmortem": {
        "primary_key": "incidents",
        "sheet_routes": {
            "incidents": ("incident", "outage", "timeline"),
            "action_items": ("action", "remediation"),
        },
        "scalar_keys": ("as_of_time", "slo_target_pct", "window_days"),
        "single_entity_keys": ("incident",),
        "single_entity_root_markers": ("detected_at",),
        "required_fields": {
            "incidents": (("incident_id", "service"), ("started_at", "detected_at", "mitigated_at")),
            "action_items": (("action_id", "title"),),
        },
    },
    "security-pr-readiness-gate": {
        "primary_key": "dependencies",
        "sheet_routes": {"dependencies": ("dependenc", "package", "vuln")},
        "raw_text_key": "diff",
        "scalar_keys": ("pr_id",),
        "required_fields": {
            "dependencies": (("name", "package"), ("version", "source_url")),
        },
    },
    "brand-voice-compliance-gate": {
        "primary_key": "assets",
        "sheet_routes": {"assets": ("asset", "copy", "brand")},
        "single_entity_root_markers": ("body", "headline"),
        "required_fields": {
            "assets": (("asset_id", "headline", "body"), ("body", "headline", "channel")),
        },
    },
    "multimodal-campaign-brief": {
        "primary_key": "deliverables",
        "sheet_routes": {"deliverables": ("deliverable", "campaign", "asset_plan")},
        "scalar_keys": ("campaign_name", "total_budget_usd", "launch_date", "channels", "target_audiences"),
        "required_fields": {
            "deliverables": (("asset_id", "channel"), ("estimated_cost_usd", "due_date", "audience")),
        },
    },
    "market-localization-adapter": {
        "primary_key": "translations",
        "sheet_routes": {"translations": ("translation", "locale"), "glossary": ("glossary", "term")},
        "scalar_keys": ("source_text", "do_not_translate_terms", "target_locales"),
        "required_fields": {
            "translations": (("locale",), ("translated_text",)),
            "glossary": (("source_term",), ("approved_translations",)),
        },
    },
    "schema-grounded-sql-analyst": {
        "primary_key": "tables",
        "table_aliases": {"tables": ("schema",)},
        "sheet_routes": {"tables": ("table", "schema", "partition")},
        "raw_text_key": "sql",
        "scalar_keys": ("estimated_scan_gb",),
        "required_fields": {
            "tables": (("table_name", "name"),),
        },
    },
    "kpi-anomaly-driver-tree": {
        "primary_key": "segments",
        "table_aliases": {"segments": ("records",)},
        "sheet_routes": {"segments": ("segment", "kpi", "driver", "bridge")},
        "required_fields": {
            "segments": (("segment",), ("current_revenue", "prior_revenue", "current_volume")),
        },
    },
    "executive-data-story-pack": {
        "primary_key": "rows",
        "table_aliases": {"rows": ("records",)},
        "sheet_routes": {"rows": ("data", "metric", "story", "kpi", "row")},
        "scalar_keys": ("title",),
        "required_fields": {},
    },
}


def _kv_sheet_to_map(
    rows: list[dict[str, Any]],
    *,
    value_as_int: bool = False,
    upper_key: bool = True,
) -> dict[str, Any]:
    """Convert lookup sheet rows ([{currency, rate_to_usd}] or [{currency, decimals}]) to a flat dict."""
    out: dict[str, Any] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        key = (
            r.get("currency")
            or r.get("curr")
            or r.get("waers")
            or r.get("sku")
            or r.get("part_id")
            or r.get("category")
            or r.get("key")
            or r.get("code")
        )
        val = None
        for vk in (
            "rate_to_usd",
            "fx_rate",
            "rate",
            "decimals",
            "decimal_places",
            "currdec",
            "median_usd",
            "qty",
            "value",
        ):
            if r.get(vk) not in (None, ""):
                val = r.get(vk)
                break
        if key and val is not None:
            k_str = str(key).strip()
            if upper_key:
                k_str = k_str.upper()
            fval = _safe_float_io(val)
            if fval is not None:
                out[k_str] = int(round(fval)) if value_as_int else fval
    return out


def _score_sheet_match(
    sheet_name: str,
    headers: list[str],
    patterns: tuple[str, ...],
    hint_cols: set[str] | None = None,
) -> float:
    norm_name = canonicalize_header(sheet_name)
    score = 0.0
    for idx, pat in enumerate(patterns):
        pnorm = canonicalize_header(pat)
        if not pnorm:
            continue
        if norm_name == pnorm:
            score += 100.0 - idx
        elif pnorm in norm_name:
            score += 40.0 + len(pnorm) * 0.5 - idx
    if hint_cols:
        norm_hdrs = {canonicalize_header(h) for h in headers}
        overlap = len(norm_hdrs & hint_cols)
        if overlap > 0:
            score += overlap * 15.0
    return score


_NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
    "eighteen": 18,
    "twenty": 20,
    "twenty-four": 24,
    "thirty": 30,
    "thirty-six": 36,
    "forty-five": 45,
    "forty-eight": 48,
    "sixty": 60,
    "seventy-two": 72,
    "ninety": 90,
    "ninety-six": 96,
    "one hundred twenty": 120,
    "hundred twenty": 120,
}


def _find_num_before_unit(text_lower: str, unit_pattern: str) -> float | None:
    """Extract numeric quantities like '3 months', 'three (3) months', or 'twelve months'."""
    m = re.search(rf"(?:[a-z-]+\s*)?\((\d+(?:\.\d+)?)\)\s*(?:-|\s)?{unit_pattern}", text_lower)
    if m:
        return float(m.group(1))
    m_num = re.search(rf"\b(\d+(?:\.\d+)?)\s*(?:-|\s)?{unit_pattern}", text_lower)
    if m_num:
        return float(m_num.group(1))
    for word, val in sorted(_NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(word)}\s*(?:-|\s)?{unit_pattern}", text_lower):
            return float(val)
    return None


def _has_affirmative_match(text_lower: str, phrase_pattern: str) -> bool:
    """Return True if phrase_pattern matches without a preceding negation cue."""
    neg_re = re.compile(r"\b(?:not|never|no|shall not|will not|may not|forbid|prohibit(?:ed)?|without)\b")
    for m in re.finditer(phrase_pattern, text_lower):
        prefix = text_lower[max(0, m.start() - 48) : m.start()]
        if not neg_re.search(prefix):
            return True
    return False


def _synthesize_docx_clauses(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert parsed .docx sections and annotations into clause dicts for contract/policy analysis."""
    clauses: list[dict[str, Any]] = []
    family_map = [
        ("limitation_of_liability", ("limitation of liability", "liability cap", "aggregate liability")),
        ("auto_renewal", ("auto-renewal", "automatic renewal", "renewal", "term and termination")),
        ("dpa_breach_notification", ("breach notification", "security breach", "data breach", "personal data breach", "security incident", "incident notification", "data processing", "dpa")),
        ("data_rights_ai_training", ("ai training", "machine learning", "model training", "data rights", "intellectual property", "customer data", "customer content")),
        ("governing_law", ("governing law", "jurisdiction", "venue", "dispute resolution")),
        ("indemnification", ("indemnification", "indemnity", "hold harmless")),
    ]
    for idx, sec in enumerate(doc.get("sections", []), 1):
        heading = str(sec.get("heading") or f"Section {idx}")
        text = str(sec.get("text") or "").strip()
        if not text:
            continue
        combined_lower = f"{heading}\n{text}".lower()
        family = "general"
        for fam, kws in family_map:
            if any(kw in combined_lower for kw in kws):
                family = fam
                break
        metrics: dict[str, Any] = {}
        if family == "limitation_of_liability":
            cap_m = _find_num_before_unit(combined_lower, r"months?(?:\s+of|\s+trailing|\s+preceding)?\s+(?:the\s+)?fees")
            if cap_m is None:
                cap_m = _find_num_before_unit(combined_lower, r"months?\s+(?:aggregate\s+)?(?:cap|fees)")
            if cap_m is not None:
                metrics["lol_cap_months"] = float(cap_m)
            super_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|times)\s+(?:the\s+)?(?:general\s+cap|fees|trailing)", combined_lower)
            if super_m:
                metrics["super_cap_multiplier"] = float(super_m.group(1))
            if "unlimited liability" in combined_lower or "uncapped liability" in combined_lower or "without any cap" in combined_lower:
                metrics["uncapped_liability"] = True
            if (
                "applies solely to vendor" in combined_lower
                or "vendor's aggregate liability only" in combined_lower
                or "unilateral liability cap" in combined_lower
                or ("customer's liability" in combined_lower and "unlimited" in combined_lower)
            ):
                metrics["unilateral_cap"] = True
        elif family == "auto_renewal":
            notice_d = _find_num_before_unit(combined_lower, r"days?(?:\s+prior|\s+written|\s+advance)?\s+notice")
            if notice_d is not None:
                metrics["notice_days"] = int(notice_d)
            m_cpi = re.search(r"(\d+(?:\.\d+)?)\s*%", combined_lower)
            if m_cpi:
                metrics["price_escalator_pct"] = float(m_cpi.group(1))
            if "automatically renew" in combined_lower or "auto-renew" in combined_lower or "evergreen" in combined_lower:
                metrics["silent_evergreen"] = True
            if ("uncapped" in combined_lower or "without cap" in combined_lower) and (
                "cpi" in combined_lower or "increase" in combined_lower or "uplift" in combined_lower or "escalat" in combined_lower
            ):
                metrics["uncapped_price_escalator"] = True
        elif family == "data_rights_ai_training":
            if _has_affirmative_match(
                combined_lower,
                r"\b(?:train(?:ing)?\s+(?:its|vendor|general|foundation|ai|ml|machine learning)\s+models?|improve\s+(?:vendor\s+)?ai|use\s+(?:customer\s+)?(?:data|content|prompts?)\s+(?:to|for)\s+train(?:ing)?)\b",
            ):
                metrics["vendor_ai_training_allowed"] = True
            if _has_affirmative_match(
                combined_lower,
                r"\bassigns?\s+(?:all\s+)?(?:rights?\s+in\s+)?(?:customer\s+)?(?:pre-?existing|background)\s+ip\b",
            ):
                metrics["assigns_customer_preexisting_ip"] = True
            if _has_affirmative_match(
                combined_lower,
                r"\b(?:perpetual|irrevocable|royalty-free)\s+(?:worldwide\s+)?license\b",
            ):
                metrics["shared_background_ip_license"] = True
        elif family == "dpa_breach_notification":
            hrs = _find_num_before_unit(combined_lower, r"hours?")
            if hrs is None:
                days_val = _find_num_before_unit(combined_lower, r"(?:calendar\s+|business\s+)?days?")
                if days_val is not None:
                    hrs = days_val * 24.0
            if hrs is not None:
                metrics["breach_notify_hours"] = int(hrs)
            if "commercially reasonable" in combined_lower or "without undue delay" in combined_lower:
                if "breach_notify_hours" not in metrics:
                    metrics["vague_timing"] = True
                elif "or as soon as commercially reasonable" in combined_lower:
                    metrics["vague_timing"] = True
        elif family == "governing_law":
            for jur in ("Delaware", "New York", "England and Wales", "Singapore", "California", "Texas", "Switzerland"):
                if jur.lower() in combined_lower:
                    metrics["jurisdiction"] = jur
                    break
            if any(
                kw in combined_lower
                for kw in ("waives any right to appeal", "unilateral venue", "waives jury trial solely")
            ):
                metrics["unilateral_venue_or_appeal_waiver"] = True

        # Extract optional policy/SOP scoping attributes for policy-sop-answering
        status = "published"
        if "superseded" in combined_lower or "retired" in combined_lower or "archived" in combined_lower:
            status = "superseded"
        elif re.search(r"\bdraft\b", heading.lower()) or "status: draft" in combined_lower:
            status = "draft"
        jur_match = re.search(r"(?:jurisdiction|region|country)\s*:\s*([A-Za-z0-9_-]+)", combined_lower, re.IGNORECASE)
        eff_match = re.search(r"effective(?:\s+date)?\s*:\s*(\d{4}-\d{2}-\d{2})", combined_lower, re.IGNORECASE)
        exp_match = re.search(r"expir(?:ation|es)(?:\s+date)?\s*:\s*(\d{4}-\d{2}-\d{2})", combined_lower, re.IGNORECASE)
        ver_match = re.search(r"\bv(?:ersion)?\s*([0-9]+(?:\.[0-9]+)+)", combined_lower, re.IGNORECASE)
        ent_match = re.search(r"(?:entity|legal entity)\s*:\s*([A-Za-z0-9 &.,_-]{2,50})", text, re.IGNORECASE)

        clause_obj: dict[str, Any] = {
            "clause_id": f"SEC-{idx:02d}",
            "title": heading,
            "policy_name": heading,
            "clause_family": family,
            "clause_text": f"{heading}: {text}",
            "text": text,
            "status": status,
            "metrics": metrics,
        }
        if jur_match:
            clause_obj["jurisdiction"] = jur_match.group(1).upper()
        if eff_match:
            clause_obj["effective_date"] = eff_match.group(1)
        if exp_match:
            clause_obj["expiration_date"] = exp_match.group(1)
        if ver_match:
            clause_obj["version"] = ver_match.group(1)
        if ent_match:
            clause_obj["entity"] = ent_match.group(1).strip()
        clauses.append(clause_obj)

    for a_idx, note in enumerate(doc.get("annotations", []), 1):
        clauses.append(
            {
                "clause_id": f"ANNOTATION-{a_idx:02d}",
                "title": "Document Footnote / Comment",
                "clause_family": "general",
                "clause_text": note,
                "text": note,
                "status": "published",
                "metrics": {},
            }
        )
    return clauses


def _safe_float_io(val: Any) -> float | None:
    """Parse accounting negatives like ($12,450.00) or plain numbers to float."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "inf", "-inf", "+inf", "null", "none", "n/a", "-", "--"}:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    s = s.replace("$", "").replace("€", "").replace("£", "").replace("¥", "").replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        out = float(s)
        return -abs(out) if neg else out
    except ValueError:
        return None


def _rollup_nested_records(payload: dict[str, Any], *, skill_id: str | None) -> dict[str, Any]:
    """Assemble nested child lists/dicts when multi-tab workbooks or flat CSVs split parent/child rows."""
    if skill_id == "pnl-budget-variance-bridge" and "lines" in payload:
        fx_map = payload.get("fx_rates") or {}
        if isinstance(fx_map, dict) and fx_map:
            for row in payload.get("lines") or []:
                if not isinstance(row, dict):
                    continue
                curr = str(row.get("currency") or "USD").strip().upper()
                if curr in fx_map:
                    if row.get("fx_rate_actual") in (None, ""):
                        row["fx_rate_actual"] = fx_map[curr]
                    if row.get("fx_rate_budget") in (None, ""):
                        row["fx_rate_budget"] = fx_map[curr]

    if skill_id == "ap-three-way-match":
        for po in payload.get("purchase_orders") or []:
            if isinstance(po, dict):
                if po.get("ordered_qty") in (None, ""):
                    for qk in ("quantity", "qty", "menge", "invoiced_qty"):
                        if po.get(qk) not in (None, ""):
                            po["ordered_qty"] = po[qk]
                            break
                if po.get("unit_price") in (None, "") and po.get("amount") not in (None, ""):
                    amt_f = _safe_float_io(po["amount"])
                    qty_f = _safe_float_io(po.get("ordered_qty"))
                    if amt_f is not None:
                        po["unit_price"] = amt_f / (qty_f if qty_f and qty_f > 0 else 1.0)
        for gr in payload.get("goods_receipts") or []:
            if isinstance(gr, dict) and gr.get("received_qty") in (None, ""):
                for qk in ("quantity", "qty", "menge", "invoiced_qty"):
                    if gr.get(qk) not in (None, ""):
                        gr["received_qty"] = gr[qk]
                        break
        for inv in payload.get("invoices") or []:
            if isinstance(inv, dict):
                if inv.get("invoiced_qty") in (None, ""):
                    for qk in ("quantity", "qty", "menge"):
                        if inv.get(qk) not in (None, ""):
                            inv["invoiced_qty"] = inv[qk]
                            break
                if inv.get("unit_price") in (None, ""):
                    amt_val = None
                    for ak in ("amount", "wrbtr", "rmwwr", "gross_amount", "line_amount"):
                        if inv.get(ak) not in (None, ""):
                            amt_val = inv[ak]
                            break
                    amt_f = _safe_float_io(amt_val)
                    if amt_f is not None:
                        qty_f = _safe_float_io(inv.get("invoiced_qty")) or 0.0
                        if qty_f > 0:
                            inv["unit_price"] = amt_f / qty_f
                        else:
                            inv["invoiced_qty"] = 1.0
                            inv["unit_price"] = amt_f

    if skill_id == "deal-desk-quote-guard" and "quotes" in payload:
        raw_quotes = payload.get("quotes") or []
        raw_lines = payload.pop("line_items", None) or []
        quote_ids = {id(q) for q in raw_quotes}
        if raw_lines and any(id(li) in quote_ids for li in raw_lines):
            raw_lines = []
        if raw_lines:
            lines_by_q: dict[str, list[dict[str, Any]]] = {}
            for li in raw_lines:
                if isinstance(li, dict) and li.get("quote_id"):
                    lines_by_q.setdefault(str(li["quote_id"]), []).append(li)
            for q in raw_quotes:
                if isinstance(q, dict) and not q.get("line_items"):
                    qid = str(q.get("quote_id") or "")
                    if qid in lines_by_q:
                        q["line_items"] = lines_by_q[qid]
        elif raw_quotes and isinstance(raw_quotes[0], dict) and not raw_quotes[0].get("line_items") and (
            "unit_list_price_annual" in raw_quotes[0] or "unit_net_price_annual" in raw_quotes[0]
        ):
            grouped_q: dict[str, dict[str, Any]] = {}
            order_q: list[str] = []
            for r in raw_quotes:
                qid = str(r.get("quote_id") or "Q-1")
                if qid not in grouped_q:
                    grouped_q[qid] = {**r, "line_items": []}
                    order_q.append(qid)
                grouped_q[qid]["line_items"].append(
                    {
                        "quantity": r.get("quantity", 1),
                        "unit_list_price_annual": r.get("unit_list_price_annual", 0.0),
                        "unit_net_price_annual": r.get("unit_net_price_annual", r.get("unit_list_price_annual", 0.0)),
                        "unit_cogs_annual": r.get("unit_cogs_annual", 0.0),
                    }
                )
            payload["quotes"] = [grouped_q[qid] for qid in order_q]

    elif skill_id == "structured-hiring-rubric" and "candidates" in payload:
        raw_cands = payload.get("candidates") or []
        raw_ivs = payload.pop("interviewers", None) or []
        cand_ids = {id(c) for c in raw_cands}
        if raw_ivs and any(id(iv) in cand_ids for iv in raw_ivs):
            raw_ivs = []
        if raw_ivs:
            ivs_by_c: dict[str, list[dict[str, Any]]] = {}
            for iv in raw_ivs:
                if isinstance(iv, dict) and iv.get("candidate_id"):
                    ivs_by_c.setdefault(str(iv["candidate_id"]), []).append(iv)
            for c in raw_cands:
                if isinstance(c, dict) and not c.get("interviewers"):
                    cid = str(c.get("candidate_id") or "")
                    if cid in ivs_by_c:
                        c["interviewers"] = ivs_by_c[cid]
        elif raw_cands and isinstance(raw_cands[0], dict) and not raw_cands[0].get("interviewers") and (
            "interviewer_id" in raw_cands[0] or "score" in raw_cands[0]
        ):
            grouped_c: dict[str, dict[str, Any]] = {}
            order_c: list[str] = []
            for r in raw_cands:
                cid = str(r.get("candidate_id") or "CAND-1")
                if cid not in grouped_c:
                    grouped_c[cid] = {
                        "candidate_id": cid,
                        "candidate_name": r.get("candidate_name", cid),
                        "role": r.get("role", "Unspecified Role"),
                        "interviewers": [],
                    }
                    order_c.append(cid)
                grouped_c[cid]["interviewers"].append(
                    {
                        "interviewer_id": r.get("interviewer_id"),
                        "competency": r.get("competency", "General"),
                        "score": r.get("score"),
                        "evidence_text": r.get("evidence_text", ""),
                    }
                )
            payload["candidates"] = [grouped_c[cid] for cid in order_c]

    elif skill_id == "employee-onboarding-navigator" and "hires" in payload:
        raw_hires = payload.get("hires") or []
        raw_tasks = payload.pop("tasks", None) or []
        hire_ids = {id(h) for h in raw_hires}
        if raw_tasks and any(id(t) in hire_ids for t in raw_tasks):
            raw_tasks = []
        if raw_tasks:
            tasks_by_e: dict[str, list[dict[str, Any]]] = {}
            for t in raw_tasks:
                if isinstance(t, dict) and t.get("employee_id"):
                    tasks_by_e.setdefault(str(t["employee_id"]), []).append(t)
            for h in raw_hires:
                if isinstance(h, dict) and not h.get("tasks"):
                    eid = str(h.get("employee_id") or "")
                    if eid in tasks_by_e:
                        h["tasks"] = tasks_by_e[eid]
        elif raw_hires and isinstance(raw_hires[0], dict) and not raw_hires[0].get("tasks") and "task_id" in raw_hires[0]:
            grouped_h: dict[str, dict[str, Any]] = {}
            order_h: list[str] = []
            for r in raw_hires:
                eid = str(r.get("employee_id") or "EMP-1")
                if eid not in grouped_h:
                    grouped_h[eid] = {
                        "employee_id": eid,
                        "employee_name": r.get("employee_name", eid),
                        "department": r.get("department", "General"),
                        "start_date": r.get("start_date"),
                        "tasks": [],
                    }
                    order_h.append(eid)
                grouped_h[eid]["tasks"].append(
                    {
                        "task_id": r.get("task_id"),
                        "title": r.get("title", r.get("task_id")),
                        "owner_team": r.get("owner_team", "HR"),
                        "status": r.get("status", "PENDING"),
                        "due_day_offset": r.get("due_day_offset", 30),
                        "blocked_by": r.get("blocked_by", []),
                    }
                )
            payload["hires"] = [grouped_h[eid] for eid in order_h]

    elif skill_id == "winning-proposal-architect" and "phases" in payload:
        raw_phases = payload.get("phases") or []
        raw_roles = payload.pop("roles", None) or []
        phase_ids = {id(ph) for ph in raw_phases}
        if raw_roles and any(id(rl) in phase_ids for rl in raw_roles):
            raw_roles = []
        if raw_roles:
            roles_by_p: dict[str, list[dict[str, Any]]] = {}
            for role in raw_roles:
                if isinstance(role, dict) and role.get("phase_name"):
                    roles_by_p.setdefault(str(role["phase_name"]), []).append(role)
            for ph in raw_phases:
                if isinstance(ph, dict) and not ph.get("roles"):
                    pname = str(ph.get("phase_name") or "")
                    if pname in roles_by_p:
                        ph["roles"] = roles_by_p[pname]
        elif raw_phases and isinstance(raw_phases[0], dict) and not raw_phases[0].get("roles") and (
            "bill_rate_hourly" in raw_phases[0] or "cost_rate_hourly" in raw_phases[0]
        ):
            grouped_p: dict[str, dict[str, Any]] = {}
            order_p: list[str] = []
            for r in raw_phases:
                pname = str(r.get("phase_name") or "Delivery Phase")
                if pname not in grouped_p:
                    grouped_p[pname] = {
                        "phase_name": pname,
                        "duration_weeks": r.get("duration_weeks", 1.0),
                        "roles": [],
                    }
                    order_p.append(pname)
                grouped_p[pname]["roles"].append(r)
            payload["phases"] = [grouped_p[pname] for pname in order_p]

    elif skill_id == "executed-obligation-extractor" and "contracts" in payload:
        raw_contracts = payload.get("contracts") or []
        raw_obs = payload.pop("obligations", None) or []
        contract_ids = {id(c) for c in raw_contracts}
        if raw_obs and any(id(ob) in contract_ids for ob in raw_obs):
            raw_obs = []
        obs_by_c: dict[str, list[dict[str, Any]]] = {}
        for ob in raw_obs:
            if isinstance(ob, dict) and ob.get("contract_id"):
                obs_by_c.setdefault(str(ob["contract_id"]), []).append(ob)
        for c in raw_contracts:
            if isinstance(c, dict) and not c.get("obligations"):
                cid = str(c.get("contract_id") or "")
                c["obligations"] = obs_by_c.get(cid, [])

    elif skill_id == "insurance-claims-triage-pack" and "claims" in payload:
        raw_claims = payload.get("claims") or []
        raw_pols = payload.pop("policies", None) or []
        claim_ids = {id(c) for c in raw_claims}
        if raw_pols and any(id(p) in claim_ids for p in raw_pols):
            raw_pols = []
        pol_map: dict[str, dict[str, Any]] = {}
        for p in raw_pols:
            if isinstance(p, dict) and p.get("policy_id"):
                pol_map[str(p["policy_id"])] = p
        for c in raw_claims:
            if not isinstance(c, dict) or isinstance(c.get("policy"), dict) and c["policy"]:
                continue
            pid = str(c.get("policy_id") or "")
            if pid and pid in pol_map:
                c["policy"] = pol_map[pid]
            elif any(k in c for k in ("effective_date", "expiration_date", "deductible_usd", "aggregate_limit_usd")):
                c["policy"] = {
                    "policy_id": pid or "POL-1",
                    "effective_date": c.get("effective_date"),
                    "expiration_date": c.get("expiration_date"),
                    "deductible_usd": c.get("deductible_usd", 0.0),
                    "insurer_coinsurance_pct": c.get("insurer_coinsurance_pct", 100.0),
                    "aggregate_limit_usd": c.get("aggregate_limit_usd"),
                    "excluded_perils": c.get("excluded_perils", []),
                    "sublimits": c.get("sublimits", {}),
                }
    return payload


def _resolve_sheet_name(sheet_order: list[str], sheet: str | int) -> str:
    """Resolve an Excel worksheet by exact/case-insensitive name OR 0-based numeric tab index."""
    s_req = str(sheet).strip()
    exact = next((s for s in sheet_order if s == s_req or s.lower() == s_req.lower() or s.strip().lower() == s_req.lower()), None)
    if exact is not None:
        return exact
    if re.fullmatch(r"\d+", s_req):
        idx = int(s_req)
        if 0 <= idx < len(sheet_order):
            return sheet_order[idx]
    raise KeyError(f"Worksheet {sheet!r} not found. Available sheets: {sheet_order}")


def _resolve_sheet_name_opt(sheet_order: list[str], sheet: str | int) -> str | None:
    try:
        return _resolve_sheet_name(sheet_order, sheet)
    except KeyError:
        return None


def _route_workbook_to_payload(
    wb: dict[str, Any],
    *,
    skill_id: str | None,
    primary_key: str | None,
    sheet: str | int | None,
    sheet_routes: dict[str, tuple[str, ...]],
    merge_matching_sheets: set[str],
    scalar_keys: tuple[str, ...],
    row_hints: dict[str, set[str]],
    raw_text_key: str | None = None,
    sheet_map: dict[str, str] | str | None = None,
    table_aliases: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    sheets: dict[str, list[dict[str, Any]]] = wb["sheets"]
    sheet_headers: dict[str, list[str]] = wb["sheet_headers"]
    sheet_order: list[str] = wb["sheet_order"]

    payload: dict[str, Any] = {}
    for sk in scalar_keys:
        if sk in wb["metadata_kv"]:
            payload[sk] = wb["metadata_kv"][sk]
    if raw_text_key and raw_text_key in wb["metadata_kv"]:
        payload[raw_text_key] = wb["metadata_kv"][raw_text_key]
    for trunc_key in ("truncated", "done", "total_available"):
        if trunc_key in wb["metadata_kv"]:
            payload[trunc_key] = wb["metadata_kv"][trunc_key]

    # Single explicit sheet request (by name or 0-based index)
    if sheet is not None and str(sheet).strip() != "":
        exact = _resolve_sheet_name(sheet_order, sheet)
        target_key = primary_key or "rows"
        payload[target_key] = sheets[exact]
        return _rollup_nested_records(payload, skill_id=skill_id)

    assigned: dict[str, list[str]] = {}
    explicit_assigned_sheets: set[str] = set()
    parsed_sheet_map = parse_mapping_arg(sheet_map)
    rev_table_aliases: dict[str, str] = {}
    for canon_tbl, al_list in (table_aliases or {}).items():
        for al in al_list:
            rev_table_aliases[al] = canon_tbl
    valid_targets = (
        set(sheet_routes.keys())
        | ({primary_key} if primary_key else {"rows"})
        | set(merge_matching_sheets)
        | {"fx_rates", "decimal_places", "depot_spares_qty", "category_medians_usd"}
    )
    if parsed_sheet_map:
        for raw_tgt, mapped_sheet in parsed_sheet_map.items():
            tgt = rev_table_aliases.get(raw_tgt, raw_tgt)
            if skill_id is not None and tgt not in valid_targets:
                continue
            resolved_sn = _resolve_sheet_name_opt(sheet_order, mapped_sheet)
            if resolved_sn is not None:
                assigned[tgt] = [resolved_sn]
                explicit_assigned_sheets.add(resolved_sn)

    if len(sheet_order) == 1 and not assigned:
        only_name = sheet_order[0]
        target_key = primary_key or "rows"
        payload[target_key] = sheets[only_name]
        return _rollup_nested_records(payload, skill_id=skill_id)

    for target_key, patterns in sheet_routes.items():
        if target_key.startswith("_exclude") or target_key in assigned:
            continue
        hint_cols = row_hints.get(target_key, set())
        scored: list[tuple[float, str]] = []
        for sname in sheet_order:
            if sname in explicit_assigned_sheets:
                continue
            sc = _score_sheet_match(sname, sheet_headers.get(sname, []), patterns, hint_cols)
            if sc > 0:
                scored.append((sc, sname))
        scored.sort(key=lambda x: (-x[0], sheet_order.index(x[1])))
        if target_key in merge_matching_sheets and scored:
            chosen: list[str] = []
            for sc, sname in scored:
                better_other = False
                for other_key, other_pats in sheet_routes.items():
                    if other_key == target_key:
                        continue
                    osc = _score_sheet_match(sname, sheet_headers.get(sname, []), other_pats, row_hints.get(other_key))
                    if osc > sc or (other_key.startswith("_exclude") and osc >= 40.0):
                        better_other = True
                        break
                if better_other:
                    continue
                if skill_id == "pnl-budget-variance-bridge" and target_key == "lines":
                    hdr_set = {canonicalize_header(h) for h in sheet_headers.get(sname, [])}
                    resolved_set = {COMMON_FIELD_ALIASES.get(h, h) for h in hdr_set}
                    if not (hdr_set | resolved_set) & {"actual_local", "actual_usd", "budget_local", "budget_usd"}:
                        continue
                chosen.append(sname)
            if skill_id == "pnl-budget-variance-bridge" and target_key == "lines" and len(chosen) > 1:
                has_gl_detail = any(
                    any(tok in canonicalize_header(s) for tok in ("_gl", "gl_detail", "consolidated_summary"))
                    for s in chosen
                )
                if has_gl_detail:
                    filtered = [s for s in chosen if "budget_comparison" not in canonicalize_header(s)]
                    if filtered:
                        chosen = filtered
            if chosen:
                assigned[target_key] = chosen
        elif scored:
            assigned[target_key] = [scored[0][1]]

    for target_key, s_names in assigned.items():
        combined: list[dict[str, Any]] = []
        for sn in s_names:
            rows = sheets[sn]
            if skill_id == "pnl-budget-variance-bridge" and "summary" in canonicalize_header(sn):
                for r in rows:
                    if "row_type" not in r or r.get("row_type") in ("", None):
                        r = {**r, "row_type": "summary"}
                    combined.append(r)
            else:
                combined.extend(rows)
        if target_key == "fx_rates":
            fx_map = _kv_sheet_to_map(combined, value_as_int=False)
            if fx_map:
                payload["fx_rates"] = fx_map
        elif target_key == "decimal_places":
            dec_map = _kv_sheet_to_map(combined, value_as_int=True)
            if dec_map:
                payload["decimal_places"] = dec_map
        elif target_key == "depot_spares_qty":
            spares_map = _kv_sheet_to_map(combined, value_as_int=True, upper_key=False)
            if spares_map:
                payload["depot_spares_qty"] = spares_map
        elif target_key == "category_medians_usd":
            med_map = _kv_sheet_to_map(combined, value_as_int=False, upper_key=False)
            if med_map:
                payload["category_medians_usd"] = {k.lower(): v for k, v in med_map.items()}
        else:
            payload[target_key] = combined

    # Fallback: if primary_key was not matched by name/hints/sheet_map, pick largest unclaimed non-parameter sheet
    if primary_key and primary_key not in payload and sheet_order:
        claimed_sheets = {sn for sns in assigned.values() for sn in sns}
        unclaimed = [s for s in sheet_order if s not in claimed_sheets]
        candidates = unclaimed or sheet_order
        best_sheet = max(
            candidates,
            key=lambda s: (
                0
                if any(tok in canonicalize_header(s) for tok in ("param", "metadata", "config", "tcurx", "fx_rate"))
                else len(sheets[s])
            ),
        )
        payload[primary_key] = sheets[best_sheet]

    return _rollup_nested_records(payload, skill_id=skill_id)


def _route_docx_to_payload(
    doc: dict[str, Any],
    *,
    skill_id: str | None,
    primary_key: str | None,
    sheet_routes: dict[str, tuple[str, ...]],
    raw_text_key: str | None,
    scalar_keys: tuple[str, ...],
    row_hints: dict[str, set[str]] | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    hints = row_hints or {}
    parsed_sheet_map = parse_mapping_arg(sheet_map)
    for sk in scalar_keys:
        if sk in doc["metadata_kv"]:
            payload[sk] = doc["metadata_kv"][sk]
    if "title" in scalar_keys and "title" not in payload:
        payload["title"] = doc["title"]
    if raw_text_key:
        payload[raw_text_key] = doc["full_text"]

    full_text = doc.get("full_text", "")
    if skill_id == "clinical-protocol-feasibility":
        if "protocol_id" not in payload:
            m_pid = re.search(r"\bProtocol(?:\s+ID|\s+No\.?)?\s*[:#]\s*([A-Z0-9-]{4,32})", full_text, re.IGNORECASE)
            if m_pid:
                payload["protocol_id"] = m_pid.group(1)
        if "target_sample_size" not in payload:
            m_n = re.search(
                r"(?:target\s+sample\s+size|sample\s+size|planned\s+enrollment)[^0-9]{0,20}(\d{2,5})\b",
                full_text,
                re.IGNORECASE,
            )
            if m_n:
                payload["target_sample_size"] = int(m_n.group(1))
        if "enrollment_window_months" not in payload:
            m_ew = re.search(
                r"(\d{1,3})\s*-\s*months?\s+enrollment|enrollment\s+window[^0-9]{0,16}(\d{1,3})\s*months?",
                full_text,
                re.IGNORECASE,
            )
            if m_ew:
                payload["enrollment_window_months"] = int(m_ew.group(1) or m_ew.group(2))
    elif skill_id == "contract-playbook-redliner":
        if "contract_id" not in payload:
            m_cid = re.search(r"\b(?:Agreement|Contract)\s+(?:ID|No\.?)\s*[:#]\s*([A-Z0-9-]{4,40})", full_text, re.IGNORECASE)
            if m_cid:
                payload["contract_id"] = m_cid.group(1)

    # Route embedded Word tables to collection keys when present
    tables = doc.get("tables", [])
    if tables and parsed_sheet_map:
        for tgt, sel in parsed_sheet_map.items():
            matched_tbl = None
            if re.fullmatch(r"\d+", sel.strip()):
                idx = int(sel.strip())
                if 0 <= idx < len(tables):
                    matched_tbl = tables[idx]
            else:
                sel_low = sel.strip().lower()
                for tbl in tables:
                    if sel_low in str(tbl.get("section", "")).lower():
                        matched_tbl = tbl
                        break
            if matched_tbl is not None and matched_tbl.get("rows"):
                payload[tgt] = matched_tbl["rows"]

    if tables and sheet_routes:
        for target_key, patterns in sheet_routes.items():
            if target_key.startswith("_exclude") or target_key in payload:
                continue
            best_tbl = None
            best_sc = 0.0
            t_hints = hints.get(target_key, set())
            for tbl in tables:
                hdrs = tbl.get("headers", [])
                if target_key == "clauses":
                    norm_hdrs = {canonicalize_header(h) for h in hdrs}
                    if not (norm_hdrs & {"clause_id", "clause_text", "text", "clause_family"}):
                        continue
                sc = _score_sheet_match(tbl.get("section", ""), hdrs, patterns, t_hints)
                hdr_blob = "_".join(canonicalize_header(h) for h in hdrs)
                for p in patterns:
                    if canonicalize_header(p) in hdr_blob:
                        sc += 25.0
                if sc > best_sc and tbl.get("rows"):
                    best_sc = sc
                    best_tbl = tbl
            if best_tbl is not None:
                payload[target_key] = best_tbl["rows"]

    if primary_key and primary_key not in payload:
        if skill_id in {"contract-playbook-redliner", "policy-sop-answering"} and primary_key == "clauses":
            payload["clauses"] = _synthesize_docx_clauses(doc)
        elif tables:
            largest_tbl = max(tables, key=lambda t: len(t.get("rows", [])))
            payload[primary_key] = largest_tbl["rows"]
        elif primary_key == "clauses":
            payload["clauses"] = _synthesize_docx_clauses(doc)
        elif doc.get("sections"):
            payload[primary_key] = [
                {"id": f"SEC-{i + 1:02d}", "title": s["heading"], "text": s["text"]}
                for i, s in enumerate(doc["sections"])
            ]

    return _rollup_nested_records(payload, skill_id=skill_id)


def load_enterprise_payload(
    input_arg: str | Path | dict[str, Any] | list[Any] | None = None,
    *,
    skill_id: str | None = None,
    primary_key: str | None = None,
    sheet: str | int | None = None,
    sheet_routes: dict[str, tuple[str, ...]] | None = None,
    field_aliases: dict[str, str] | None = None,
    raw_text_key: str | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    """Universal enterprise loader supporting dict, JSON, JSONL, CSV, TSV, XLSX, DOCX, SQL, DIFF, MD/TXT."""
    profile = SKILL_INGESTION_PROFILES.get(skill_id or "", {})
    eff_primary = primary_key or profile.get("primary_key")
    eff_routes = dict(profile.get("sheet_routes", {}))
    if sheet_routes:
        eff_routes.update(sheet_routes)
    eff_aliases = dict(profile.get("field_aliases", {}))
    if field_aliases:
        eff_aliases.update(field_aliases)
    eff_merge = set(profile.get("merge_matching_sheets", set()))
    eff_scalars = tuple(profile.get("scalar_keys", ()))
    eff_hints = dict(profile.get("row_hints", {}))
    eff_raw_key = raw_text_key or profile.get("raw_text_key")
    eff_table_aliases = profile.get("table_aliases") or {}
    parsed_col_map = parse_mapping_arg(column_map)
    parsed_sheet_map = parse_mapping_arg(sheet_map)

    if input_arg is None:
        return {}
    if isinstance(input_arg, (dict, list)):
        return apply_column_map_to_payload(
            input_arg,
            skill_id=skill_id,
            primary_key=eff_primary,
            field_aliases=eff_aliases,
            column_map=parsed_col_map,
            sheet_map=parsed_sheet_map,
        )

    p = Path(input_arg)
    suffix = p.suffix.lower()

    if suffix in {".xlsx", ".xlsm"}:
        wb = read_xlsx_workbook(p, field_aliases=eff_aliases, column_map=parsed_col_map)
        return _route_workbook_to_payload(
            wb,
            skill_id=skill_id,
            primary_key=eff_primary,
            sheet=sheet,
            sheet_routes=eff_routes,
            merge_matching_sheets=eff_merge,
            scalar_keys=eff_scalars,
            row_hints=eff_hints,
            raw_text_key=eff_raw_key,
            sheet_map=parsed_sheet_map,
            table_aliases=eff_table_aliases,
        )

    if suffix == ".docx":
        doc = read_docx(p, field_aliases=eff_aliases, column_map=parsed_col_map)
        return _route_docx_to_payload(
            doc,
            skill_id=skill_id,
            primary_key=eff_primary,
            sheet_routes=eff_routes,
            raw_text_key=eff_raw_key,
            scalar_keys=eff_scalars,
            row_hints=eff_hints,
            sheet_map=parsed_sheet_map,
        )

    if suffix in {".csv", ".tsv"}:
        rows = read_csv_tsv(p, field_aliases=eff_aliases, column_map=parsed_col_map)
        return _rollup_nested_records({eff_primary or "records": rows}, skill_id=skill_id)

    if suffix in {".sql", ".diff", ".patch", ".txt", ".md"}:
        text = _read_text_with_fallback(p)
        if suffix in {".txt", ".md"} and eff_primary != "clauses" and not eff_raw_key:
            try:
                loaded = json.loads(text)
                if isinstance(loaded, (dict, list)):
                    return apply_column_map_to_payload(
                        loaded,
                        skill_id=skill_id,
                        primary_key=eff_primary,
                        field_aliases=eff_aliases,
                        column_map=parsed_col_map,
                        sheet_map=parsed_sheet_map,
                    )
            except json.JSONDecodeError:
                pass
        key = eff_raw_key or ("sql" if suffix == ".sql" else ("diff" if suffix in {".diff", ".patch"} else "raw_text"))
        out: dict[str, Any] = {key: text}
        if skill_id == "meeting-to-execution-pack":
            out.setdefault("meeting_title", p.stem)
        elif skill_id == "security-pr-readiness-gate":
            out.setdefault("pr_id", p.stem)
        elif skill_id == "schema-grounded-sql-analyst":
            out.setdefault("tables", [])
        return out

    loaded = read_json_or_jsonl(p)
    return apply_column_map_to_payload(
        loaded,
        skill_id=skill_id,
        primary_key=eff_primary,
        field_aliases=eff_aliases,
        column_map=parsed_col_map,
        sheet_map=parsed_sheet_map,
    )


def read_enterprise_table(
    path: str | Path,
    *,
    sheet: str | int | None = None,
    field_aliases: dict[str, str] | None = None,
    column_map: dict[str, str] | str | None = None,
    fallback_keys: tuple[str, ...] = ("rows", "items", "records"),
) -> list[dict[str, Any]]:
    """Read a flat table from JSON, JSONL, CSV, TSV, XLSX, or DOCX (first table)."""
    p = Path(path)
    suffix = p.suffix.lower()
    parsed_col = parse_mapping_arg(column_map)
    if suffix in {".xlsx", ".xlsm"}:
        wb = read_xlsx_workbook(p, field_aliases=field_aliases, column_map=parsed_col)
        if not wb["sheet_order"]:
            return []
        if sheet is not None and str(sheet).strip() != "":
            exact = _resolve_sheet_name(wb["sheet_order"], sheet)
            return wb["sheets"][exact]
        return wb["sheets"][wb["sheet_order"][0]]
    if suffix == ".docx":
        doc = read_docx(p, field_aliases=field_aliases, column_map=parsed_col)
        return doc["tables"][0]["rows"] if doc.get("tables") else []
    if suffix in {".csv", ".tsv"}:
        return read_csv_tsv(p, field_aliases=field_aliases, column_map=parsed_col)
    loaded = read_json_or_jsonl(p)
    rows_raw: list[dict[str, Any]] = []
    if isinstance(loaded, list):
        rows_raw = [x for x in loaded if isinstance(x, dict)]
    elif isinstance(loaded, dict):
        if sheet is not None and str(sheet).strip() != "" and isinstance(loaded.get(str(sheet).strip()), list):
            rows_raw = [x for x in loaded[str(sheet).strip()] if isinstance(x, dict)]
        else:
            for k in fallback_keys:
                if isinstance(loaded.get(k), list):
                    rows_raw = [x for x in loaded[k] if isinstance(x, dict)]
                    break
    if not rows_raw:
        return []
    mapped = apply_column_map_to_payload({"rows": rows_raw}, field_aliases=field_aliases, column_map=parsed_col)
    return [x for x in mapped.get("rows", []) if isinstance(x, dict)]


# ---------------------------------------------------------------------------
# Schema Inspector & Fail-Closed Validation Gate (--inspect / column_map)
# ---------------------------------------------------------------------------

# Conservative mapping hints surfaced ONLY in --inspect diagnostics (never silently applied).
_SUGGESTED_HEADER_HINTS: dict[str, str] = {
    "purchasing_doc": "po_number",
    "purchasing_document": "po_number",
    "po_ref": "po_number",
    "order_number": "po_number",
    "bill_ref": "invoice_id",
    "bill_no": "invoice_id",
    "vendor_invoice_id": "invoice_id",
    "vendor_invoice_no": "invoice_number",
    "vendor_title": "vendor_id",
    "supplier_id": "vendor_id",
    "supplier_name": "vendor_name",
    "net_val": "amount",
    "net_value": "amount",
    "net_amount": "amount",
    "gross_amt": "amount",
    "inv_amt": "amount",
    "unit_cost": "unit_price",
    "units_billed": "invoiced_qty",
    "billed_qty": "invoiced_qty",
    "units_ordered": "ordered_qty",
    "units_received": "received_qty",
    "gr_amt": "gr_amount",
    "ir_amt": "ir_amount",
    "acct": "account_id",
    "gl_acct": "account_id",
    "account_code": "account_id",
    "acct_desc": "account_name",
    "actual_amt_usd": "actual_usd",
    "budget_amt_usd": "budget_usd",
    "client_id": "customer_id",
    "client_name": "customer_name",
    "open_bal": "open_amount_usd",
    "balance_due": "open_amount_usd",
    "staff_id": "worker_id",
    "ee_id": "worker_id",
    "emp_num": "worker_id",
    "grade": "job_level",
    "level": "job_level",
    "annual_comp": "base_pay_amount",
    "salary_amt": "base_pay_amount",
    "deal_stage": "stage",
    "stage_label": "stage",
    "deal_val": "amount_usd",
    "arr_value": "arr_usd",
    "inc_num": "incident_id",
    "ticket_id": "incident_id",
    "sev": "severity",
    "short_desc": "short_description",
}


def _nonempty_dict_rows(val: Any) -> list[dict[str, Any]]:
    if not isinstance(val, list):
        return []
    return [r for r in val if isinstance(r, dict) and len(r) > 0]


def _suggest_column_mappings(
    raw_headers: list[str],
    missing_groups: list[list[str]],
    existing_keys: set[str],
    field_aliases: dict[str, str],
) -> dict[str, str]:
    missing_flat = {f for grp in missing_groups for f in grp}
    if not missing_flat:
        return {}
    suggestions: dict[str, str] = {}
    seen_targets: set[str] = set()
    for raw_h in raw_headers:
        canon = canonicalize_header(raw_h)
        if not canon or canon in missing_flat:
            continue
        tgt = _SUGGESTED_HEADER_HINTS.get(canon) or field_aliases.get(canon) or COMMON_FIELD_ALIASES.get(canon)
        if tgt and tgt in missing_flat and tgt not in existing_keys and tgt not in seen_targets:
            suggestions[raw_h] = tgt
            seen_targets.add(tgt)
            continue
        # Simple token normalization match against missing canonical fields
        stripped = re.sub(r"_(?:no|num|ref|id|val|amt|dt|txt)$", "", canon)
        for cand in sorted(missing_flat):
            cand_base = re.sub(r"_(?:no|num|ref|id|usd|local|pct|date)$", "", cand)
            if cand == canon or (len(stripped) >= 4 and stripped == cand_base):
                if cand not in existing_keys and cand not in seen_targets:
                    suggestions[raw_h] = cand
                    seen_targets.add(cand)
                    break
    return suggestions


def validate_payload_schema(
    payload: dict[str, Any] | Any,
    *,
    skill_id: str | None,
    row_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Fail-closed schema gate for non-empty tables. Empty datasets always return READY."""
    profile = SKILL_INGESTION_PROFILES.get(skill_id or "", {})
    req_spec: dict[str, tuple[tuple[str, ...], ...]] = profile.get("required_fields") or {}
    primary_key: str | None = profile.get("primary_key")
    table_aliases: dict[str, tuple[str, ...]] = profile.get("table_aliases") or {}
    single_keys: tuple[str, ...] = profile.get("single_entity_keys") or ()
    single_markers: tuple[str, ...] = profile.get("single_entity_root_markers") or ()
    raw_text_key: str | None = profile.get("raw_text_key")
    field_aliases: dict[str, str] = dict(profile.get("field_aliases") or {})

    if not isinstance(payload, dict) or not req_spec:
        return {
            "status": "READY",
            "skill_id": skill_id,
            "tables_checked": {},
            "matched_required_fields": {},
            "missing_required_fields": {},
            "unrecognized_nonempty_tables": [],
            "suggested_column_map": {},
        }

    # Resolve canonical tables that have >= 1 non-empty dict row
    resolved_tables: dict[str, list[dict[str, Any]]] = {}
    recognized_source_keys: set[str] = set()

    for tbl_key in req_spec:
        candidates = [tbl_key, *table_aliases.get(tbl_key, ())]
        for ck in candidates:
            if ck in payload:
                rows = _nonempty_dict_rows(payload.get(ck))
                if rows:
                    resolved_tables[tbl_key] = rows
                    recognized_source_keys.add(ck)
                    break

    if primary_key and primary_key not in resolved_tables:
        for sk in single_keys:
            sv = payload.get(sk)
            if isinstance(sv, dict) and len(sv) > 0:
                resolved_tables[primary_key] = [sv]
                recognized_source_keys.add(sk)
                break
        if primary_key not in resolved_tables and single_markers:
            if any(m in payload for m in single_markers):
                resolved_tables[primary_key] = [payload]

    has_raw_text = bool(raw_text_key and isinstance(payload.get(raw_text_key), str) and payload[raw_text_key].strip())

    # Detect unrecognized list-of-dicts tables (e.g., raw ServiceNow {"result": [...]} without sheet_map)
    unrecognized_tables: list[str] = []
    known_aux_keys = (
        set(req_spec.keys())
        | {al for al_list in table_aliases.values() for al in al_list}
        | set(profile.get("sheet_routes", {}).keys())
        | set(single_keys)
    )
    for k, v in payload.items():
        if k in known_aux_keys or k.startswith("_"):
            continue
        if _nonempty_dict_rows(v):
            unrecognized_tables.append(k)

    # Empty datasets ({}, [], [{}], [None], scalar-only config dicts) ALWAYS pass as empty datasets
    if not resolved_tables and not unrecognized_tables:
        return {
            "status": "READY",
            "skill_id": skill_id,
            "tables_checked": {},
            "matched_required_fields": {},
            "missing_required_fields": {},
            "unrecognized_nonempty_tables": [],
            "suggested_column_map": {},
        }

    # If only unrecognized table(s) have rows and zero recognized tables matched (and no raw_text fallback):
    # validate the first unrecognized table against primary_key's required fields AND fail closed!
    matched_req: dict[str, list[str]] = {}
    missing_req: dict[str, list[list[str]]] = {}
    tables_checked: dict[str, dict[str, Any]] = {}
    suggested_map: dict[str, str] = {}

    if not resolved_tables and unrecognized_tables and not has_raw_text:
        unrec_k = unrecognized_tables[0]
        rows = _nonempty_dict_rows(payload[unrec_k])
        target_tbl = primary_key or unrec_k
        grps = req_spec.get(target_tbl, ())
        keys_present: set[str] = set()
        raw_hdrs: list[str] = []
        seen_hdr: set[str] = set()
        for r in rows[:50]:
            for rk in r:
                if rk is None:
                    continue
                rks = str(rk)
                keys_present.add(rks)
                if rks not in seen_hdr:
                    seen_hdr.add(rks)
                    raw_hdrs.append(rks)
        matched_list: list[str] = []
        missing_list: list[list[str]] = []
        for grp in grps:
            hit = next((f for f in grp if f in keys_present), None)
            if hit:
                matched_list.append(hit)
            else:
                missing_list.append(list(grp))
        tables_checked[unrec_k] = {
            "canonical_table": target_tbl,
            "row_count": (row_counts or {}).get(unrec_k, len(rows)),
            "headers": raw_hdrs,
            "sample_row": rows[0],
        }
        matched_req[unrec_k] = matched_list
        if missing_list:
            missing_req[unrec_k] = missing_list
            suggested_map.update(_suggest_column_mappings(raw_hdrs, missing_list, keys_present, field_aliases))
        return {
            "status": "SCHEMA_MAPPING_REQUIRED",
            "skill_id": skill_id,
            "tables_checked": tables_checked,
            "matched_required_fields": matched_req,
            "missing_required_fields": missing_req,
            "unrecognized_nonempty_tables": unrecognized_tables,
            "suggested_column_map": suggested_map,
        }

    for tbl_key, rows in resolved_tables.items():
        grps = req_spec.get(tbl_key, ())
        keys_present = set()
        raw_hdrs = []
        seen_hdr = set()
        for r in rows[:50]:
            for rk in r:
                if rk is None:
                    continue
                rks = str(rk)
                keys_present.add(rks)
                if rks not in seen_hdr:
                    seen_hdr.add(rks)
                    raw_hdrs.append(rks)
        matched_list = []
        missing_list = []
        for grp in grps:
            hit = next((f for f in grp if f in keys_present), None)
            if hit:
                matched_list.append(hit)
            else:
                missing_list.append(list(grp))
        tables_checked[tbl_key] = {
            "canonical_table": tbl_key,
            "row_count": (row_counts or {}).get(tbl_key, len(rows)),
            "headers": raw_hdrs,
            "sample_row": rows[0],
        }
        matched_req[tbl_key] = matched_list
        if missing_list:
            missing_req[tbl_key] = missing_list
            suggested_map.update(_suggest_column_mappings(raw_hdrs, missing_list, keys_present, field_aliases))

    status = "SCHEMA_MAPPING_REQUIRED" if missing_req else "READY"
    return {
        "status": status,
        "skill_id": skill_id,
        "tables_checked": tables_checked,
        "matched_required_fields": matched_req,
        "missing_required_fields": missing_req,
        "unrecognized_nonempty_tables": unrecognized_tables if not resolved_tables else [],
        "suggested_column_map": suggested_map,
    }


def inspect_enterprise_source(
    source: str | Path | dict[str, Any] | list[Any] | None,
    *,
    skill_id: str | None = None,
    config: str | Path | dict[str, Any] | None = None,
    sheet: str | int | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
    max_preview_rows: int = 20,
) -> dict[str, Any]:
    """Fast (<100ms) structural schema inspection without loading full bulk datasets."""
    cfg_dict: dict[str, Any] = {}
    if isinstance(config, dict):
        cfg_dict = config
    elif config is not None:
        cp = Path(config)
        if cp.is_file():
            try:
                loaded_cfg = json.loads(cp.read_text(encoding="utf-8"))
                if isinstance(loaded_cfg, dict):
                    cfg_dict = loaded_cfg
            except (OSError, ValueError, json.JSONDecodeError):
                pass
    eff_col_map, eff_sheet_map = merge_mappings(cfg_dict, column_map=column_map, sheet_map=sheet_map)

    profile = SKILL_INGESTION_PROFILES.get(skill_id or "", {})
    eff_primary = profile.get("primary_key")
    eff_routes = dict(profile.get("sheet_routes", {}))
    eff_aliases = dict(profile.get("field_aliases", {}))
    eff_merge = set(profile.get("merge_matching_sheets", set()))
    eff_scalars = tuple(profile.get("scalar_keys", ()))
    eff_hints = dict(profile.get("row_hints", {}))
    eff_raw_key = profile.get("raw_text_key")
    eff_table_aliases = profile.get("table_aliases") or {}
    req_spec: dict[str, tuple[tuple[str, ...], ...]] = profile.get("required_fields") or {}

    tables_detected: dict[str, dict[str, Any]] = {}
    row_counts: dict[str, int] = {}

    if source is None:
        routed_preview: dict[str, Any] = {}
    elif isinstance(source, (dict, list)):
        # Take shallow preview slice for large in-memory tables
        if isinstance(source, list):
            row_counts[eff_primary or "records"] = len(source)
            src_slice: Any = source[:max_preview_rows]
            raw_samples = {eff_primary or "records": ([x for x in src_slice if isinstance(x, dict)], len(source))}
        else:
            src_slice = {}
            raw_samples = {}
            for k, v in source.items():
                if isinstance(v, list):
                    row_counts[k] = len(v)
                    src_slice[k] = v[:max_preview_rows]
                    raw_samples[k] = ([x for x in src_slice[k] if isinstance(x, dict)], len(v))
                else:
                    src_slice[k] = v
        routed_preview = apply_column_map_to_payload(
            src_slice,
            skill_id=skill_id,
            primary_key=eff_primary,
            field_aliases=eff_aliases,
            column_map=eff_col_map,
            sheet_map=eff_sheet_map,
        )
        for tbl_name, (sample_dicts, total_cnt) in raw_samples.items():
            raw_hdrs: list[str] = []
            seen_r: set[str] = set()
            for r in sample_dicts[:10]:
                for rk in r:
                    if str(rk) not in seen_r:
                        seen_r.add(str(rk))
                        raw_hdrs.append(str(rk))
            mapped_tbl = eff_primary if isinstance(source, list) else tbl_name
            mapped_rows = routed_preview.get(mapped_tbl) if isinstance(routed_preview.get(mapped_tbl), list) else []
            sample_m = mapped_rows[0] if mapped_rows and isinstance(mapped_rows[0], dict) else (sample_dicts[0] if sample_dicts else {})
            tables_detected[tbl_name] = {
                "row_count": total_cnt,
                "raw_headers": raw_hdrs,
                "mapped_headers": [str(k) for k in sample_m.keys()],
                "sample_row": sample_m,
            }
    else:
        p = Path(source)
        sfx = p.suffix.lower()
        if sfx in {".xlsx", ".xlsm"}:
            wb_fast = _inspect_xlsx_fast(
                p,
                field_aliases=eff_aliases,
                column_map=eff_col_map,
                max_preview_rows=max_preview_rows,
            )
            routed_preview = _route_workbook_to_payload(
                wb_fast,
                skill_id=skill_id,
                primary_key=eff_primary,
                sheet=sheet,
                sheet_routes=eff_routes,
                merge_matching_sheets=eff_merge,
                scalar_keys=eff_scalars,
                row_hints=eff_hints,
                raw_text_key=eff_raw_key,
                sheet_map=eff_sheet_map,
                table_aliases=eff_table_aliases,
            )
            for sname in wb_fast["sheet_order"]:
                sample_rows = wb_fast["sheets"].get(sname, [])
                raw_hdrs = wb_fast["sheet_headers"].get(sname, [])
                cnt = wb_fast["sheet_row_counts"].get(sname, len(sample_rows))
                sample_row = sample_rows[0] if sample_rows else {}
                mapped_hdrs = [str(k) for k in sample_row.keys()] if sample_row else [canonicalize_header(h) for h in raw_hdrs]
                tables_detected[sname] = {
                    "row_count": cnt,
                    "raw_headers": raw_hdrs,
                    "mapped_headers": mapped_hdrs,
                    "sample_row": sample_row,
                }
                row_counts[sname] = cnt
        elif sfx in {".csv", ".tsv"}:
            raw_hdrs, row_cnt, sample_rows = _inspect_csv_tsv_fast(
                p,
                field_aliases=eff_aliases,
                column_map=eff_col_map,
                sample_limit=max_preview_rows,
            )
            tgt_key = eff_primary or "records"
            routed_preview = _rollup_nested_records({tgt_key: sample_rows}, skill_id=skill_id)
            sample_row = (routed_preview.get(tgt_key) or sample_rows or [{}])[0] if (sample_rows or routed_preview.get(tgt_key)) else {}
            tables_detected[p.name] = {
                "row_count": row_cnt,
                "raw_headers": raw_hdrs,
                "mapped_headers": [str(k) for k in sample_row.keys()] if sample_row else [canonicalize_header(h) for h in raw_hdrs],
                "sample_row": sample_row,
            }
            row_counts[tgt_key] = row_cnt
        elif sfx == ".docx":
            doc = read_docx(p, field_aliases=eff_aliases, column_map=eff_col_map)
            routed_preview = _route_docx_to_payload(
                doc,
                skill_id=skill_id,
                primary_key=eff_primary,
                sheet_routes=eff_routes,
                raw_text_key=eff_raw_key,
                scalar_keys=eff_scalars,
                row_hints=eff_hints,
                sheet_map=eff_sheet_map,
            )
            for tbl in doc.get("tables", []):
                t_name = f"table_{tbl['table_index']}_{tbl.get('section') or 'body'}"
                t_rows = tbl.get("rows", [])
                t_sample = t_rows[0] if t_rows else {}
                tables_detected[t_name] = {
                    "row_count": len(t_rows),
                    "raw_headers": tbl.get("headers", []),
                    "mapped_headers": [str(k) for k in t_sample.keys()],
                    "sample_row": t_sample,
                }
            if eff_primary and isinstance(routed_preview.get(eff_primary), list) and not tables_detected:
                prows = routed_preview[eff_primary]
                sample_p = prows[0] if prows and isinstance(prows[0], dict) else {}
                tables_detected[eff_primary] = {
                    "row_count": len(prows),
                    "raw_headers": [str(k) for k in sample_p.keys()],
                    "mapped_headers": [str(k) for k in sample_p.keys()],
                    "sample_row": sample_p,
                }
        elif sfx in {".sql", ".diff", ".patch", ".txt", ".md"}:
            routed_preview = load_enterprise_payload(
                p,
                skill_id=skill_id,
                sheet=sheet,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
            )
            for tk, tv in routed_preview.items():
                if isinstance(tv, list):
                    t_sample = tv[0] if tv and isinstance(tv[0], dict) else {}
                    tables_detected[tk] = {
                        "row_count": len(tv),
                        "raw_headers": [str(k) for k in t_sample.keys()],
                        "mapped_headers": [str(k) for k in t_sample.keys()],
                        "sample_row": t_sample,
                    }
        else:
            loaded = read_json_or_jsonl(p)
            return inspect_enterprise_source(
                loaded,
                skill_id=skill_id,
                config=cfg_dict,
                sheet=sheet,
                column_map=eff_col_map,
                sheet_map=eff_sheet_map,
                max_preview_rows=max_preview_rows,
            )

    val_res = validate_payload_schema(routed_preview, skill_id=skill_id, row_counts=row_counts)
    req_json = {k: [list(g) for g in grps] for k, grps in req_spec.items()}

    # Enrich raw suggested_column_map using detected raw_headers per table (avoid cross-table masking)
    sug_map = dict(val_res.get("suggested_column_map") or {})
    if val_res.get("missing_required_fields"):
        all_missing = [g for grps in val_res["missing_required_fields"].values() for g in grps]
        used_targets = set(sug_map.values())
        for tinfo in tables_detected.values():
            extra_sug = _suggest_column_mappings(
                tinfo.get("raw_headers") or [],
                all_missing,
                set(tinfo.get("mapped_headers") or []),
                eff_aliases,
            )
            for rk, cv in extra_sug.items():
                if cv not in used_targets:
                    sug_map.setdefault(rk, cv)
                    used_targets.add(cv)

    return {
        "status": val_res["status"],
        "skill_id": skill_id,
        "tables_detected": tables_detected,
        "required_fields": req_json,
        "matched_required_fields": val_res["matched_required_fields"],
        "missing_required_fields": val_res["missing_required_fields"],
        "unrecognized_nonempty_tables": val_res.get("unrecognized_nonempty_tables", []),
        "suggested_column_map": sug_map,
    }


def build_schema_error_result(
    skill_id: str,
    schema_diag: dict[str, Any],
    *,
    org_configured: bool = False,
    banner: str = "",
    source: Any = None,
    config: str | Path | dict[str, Any] | None = None,
    column_map: dict[str, str] | str | None = None,
    sheet_map: dict[str, str] | str | None = None,
    sheet: str | int | None = None,
) -> dict[str, Any]:
    """Construct fail-closed SCHEMA_MAPPING_REQUIRED response when non-empty inputs lack required fields."""
    if source is not None and not schema_diag.get("tables_detected"):
        try:
            full_diag = inspect_enterprise_source(
                source,
                skill_id=skill_id,
                config=config,
                sheet=sheet,
                column_map=column_map,
                sheet_map=sheet_map,
            )
            if full_diag.get("missing_required_fields") or full_diag.get("unrecognized_nonempty_tables"):
                schema_diag = full_diag
        except Exception:
            pass
    missing = schema_diag.get("missing_required_fields") or {}
    unrec = schema_diag.get("unrecognized_nonempty_tables") or []
    parts: list[str] = []
    for tbl, grps in missing.items():
        grp_str = ", ".join(" | ".join(g) for g in grps)
        parts.append(f"table '{tbl}' missing required field group(s): [{grp_str}]")
    if unrec and not missing:
        parts.append(f"unrecognized table key(s) {unrec} without sheet_map")
    msg = (
        f"Schema mapping required for '{skill_id}': " + "; ".join(parts)
        if parts
        else f"Schema mapping required for '{skill_id}'."
    )
    return {
        "skill": skill_id,
        "status": "SCHEMA_MAPPING_REQUIRED",
        "baseline_mode": "ORG_CONFIGURED" if org_configured else "STANDARD_BASELINE",
        "baseline_banner": banner,
        "error": msg,
        "schema_diagnostic": schema_diag,
        "summary": {
            "status": "SCHEMA_MAPPING_REQUIRED",
            "records_evaluated": 0,
            "missing_tables": sorted(missing.keys()),
        },
        "truncation_warnings": [],
    }


def format_schema_mapping_markdown(result: dict[str, Any]) -> str:
    """Render an actionable Markdown schema diagnostic when status == SCHEMA_MAPPING_REQUIRED."""
    lines: list[str] = []
    if result.get("baseline_banner"):
        lines.extend([result["baseline_banner"], ""])
    diag = result.get("schema_diagnostic") or {}
    skill_id = result.get("skill") or diag.get("skill_id") or "skill"
    lines.extend(
        [
            "# Schema Mapping Required",
            "",
            f"- **Skill:** `{skill_id}`",
            f"- **Status:** `{result.get('status', 'SCHEMA_MAPPING_REQUIRED')}`",
            f"- **Reason:** {result.get('error', 'Non-empty input data does not match required canonical fields.')}",
            "",
        ]
    )
    tables = diag.get("tables_detected") or diag.get("tables_checked") or {}
    if tables:
        lines.extend(
            [
                "## Detected Tables & Headers",
                "",
                "| Table / Tab | Rows | Detected Headers |",
                "| :--- | ---: | :--- |",
            ]
        )
        for tname, info in tables.items():
            hdrs = info.get("raw_headers") or info.get("headers") or []
            cnt = info.get("row_count", 0)
            lines.append(f"| `{tname}` | {cnt} | {', '.join(f'`{h}`' for h in hdrs[:16]) or '(none)'} |")
        lines.append("")

    missing = diag.get("missing_required_fields") or {}
    if missing:
        lines.extend(["## Missing Canonical Field Groups", ""])
        for tname, grps in missing.items():
            grp_desc = "; ".join(" or ".join(f"`{f}`" for f in grp) for grp in grps)
            lines.append(f"- **`{tname}`**: {grp_desc}")
        lines.append("")

    sug = diag.get("suggested_column_map") or {}
    unrec = diag.get("unrecognized_nonempty_tables") or []
    profile = SKILL_INGESTION_PROFILES.get(str(skill_id), {})
    primary = profile.get("primary_key") or "records"
    lines.extend(["## Next Step (`--column-map` / `--sheet-map`)", ""])
    if sug:
        lines.append(f"```bash\n--column-map '{json.dumps(sug)}'\n```")
    else:
        lines.append('```bash\n--column-map \'{"Customer Header": "canonical_field"}\'\n```')
    if unrec:
        lines.append(f"```bash\n--sheet-map '{json.dumps({primary: unrec[0]})}'\n```")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect enterprise .xlsx, .docx, .csv, or .json files.")
    parser.add_argument("input", type=Path, help="Input file path (.xlsx, .docx, .csv, .tsv, .json, .jsonl)")
    parser.add_argument("--skill", help="Optional skill_id routing profile")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name or 0-based tab index")
    parser.add_argument("--config", "--org-config", dest="config", type=Path, help="Optional references/config.json path")
    parser.add_argument("--column-map", help="Optional JSON or k=v header/field mapping")
    parser.add_argument("--sheet-map", help="Optional JSON or k=v table/worksheet mapping")
    parser.add_argument("--inspect", action="store_true", help="Fast schema inspection (<100ms) with suggested column_map")
    parser.add_argument("--summary", action="store_true", help="Print structural summary only")
    args = parser.parse_args(argv)

    p: Path = args.input
    if args.inspect:
        diag = inspect_enterprise_source(
            p,
            skill_id=args.skill,
            config=args.config,
            sheet=args.sheet,
            column_map=args.column_map,
            sheet_map=args.sheet_map,
        )
        print(json.dumps(diag, indent=2, default=str))
        return 2 if diag.get("status") == "SCHEMA_MAPPING_REQUIRED" else 0

    if args.summary:
        sfx = p.suffix.lower()
        if sfx in {".xlsx", ".xlsm"}:
            wb_fast = _inspect_xlsx_fast(p, column_map=parse_mapping_arg(args.column_map))
            summary = {
                "file": str(p),
                "format": "xlsx",
                "metadata_kv": wb_fast["metadata_kv"],
                "sheets": {
                    s: {
                        "rows": wb_fast["sheet_row_counts"].get(s, len(wb_fast["sheets"][s])),
                        "headers": wb_fast["sheet_headers"][s],
                    }
                    for s in wb_fast["sheet_order"]
                },
            }
            print(json.dumps(summary, indent=2))
            return 0
        if sfx == ".docx":
            doc = read_docx(p, column_map=parse_mapping_arg(args.column_map))
            summary = {
                "file": str(p),
                "format": "docx",
                "title": doc["title"],
                "headings_count": len(doc["headings"]),
                "paragraphs_count": len(doc["paragraphs"]),
                "annotations_count": len(doc["annotations"]),
                "tables": [
                    {"table_index": t["table_index"], "section": t["section"], "rows": len(t["rows"]), "headers": t["headers"]}
                    for t in doc["tables"]
                ],
            }
            print(json.dumps(summary, indent=2))
            return 0

    cfg_dict: dict[str, Any] = {}
    if args.config and args.config.is_file():
        loaded_cfg = json.loads(args.config.read_text(encoding="utf-8"))
        if isinstance(loaded_cfg, dict):
            cfg_dict = loaded_cfg
    eff_col_map, eff_sheet_map = merge_mappings(cfg_dict, column_map=args.column_map, sheet_map=args.sheet_map)
    payload = load_enterprise_payload(
        p,
        skill_id=args.skill,
        sheet=args.sheet,
        column_map=eff_col_map,
        sheet_map=eff_sheet_map,
    )
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
