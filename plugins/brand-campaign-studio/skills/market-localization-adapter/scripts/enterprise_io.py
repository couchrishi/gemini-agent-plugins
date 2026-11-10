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


def normalize_row(
    row: dict[str, Any],
    field_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a copy of row retaining original keys plus canonical snake_case & alias keys."""
    if not isinstance(row, dict):
        return {}
    out: dict[str, Any] = {}
    aliases = dict(COMMON_FIELD_ALIASES)
    if field_aliases:
        aliases.update(field_aliases)

    # 1. Preserve original keys cleanly coerced
    for k, v in row.items():
        if k is None:
            continue
        k_str = str(k).lstrip("\ufeff").strip()
        if not k_str:
            continue
        out[k_str] = coerce_cell_value(v, k_str)

    # 2. Non-destructively overlay canonical snake_case + alias keys
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
) -> list[dict[str, Any]]:
    """Read CSV/TSV with BOM removal, delimiter sniffing, and non-destructive alias normalization."""
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
        rows.append(normalize_row(raw_row, field_aliases=field_aliases))
    return rows


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


def _parse_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root:
        if _local_tag(si.tag) != "si":
            continue
        parts: list[str] = []
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
        rows.append(normalize_row(row_dict, field_aliases=field_aliases))

    return headers, rows, banner_kv


def read_xlsx_workbook(
    path: Path,
    *,
    field_aliases: dict[str, str] | None = None,
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
            headers, rows, banner_kv = _extract_table_from_grid(grid, field_aliases=field_aliases)
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
        rows.append(normalize_row(row_dict, field_aliases=field_aliases))

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
            tbl = _docx_extract_table(elem, current_section, tbl_idx, field_aliases=field_aliases)
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
    },
    "ar-aging-collections-audit": {
        "primary_key": "open_items",
        "sheet_routes": {
            "open_items": ("ar_open", "aging", "receivable", "open_invoice", "open_item"),
        },
        "scalar_keys": ("as_of_date", "trailing_90d_credit_sales_usd"),
        "field_aliases": {"amount_usd": "open_amount_usd", "balance_usd": "open_amount_usd"},
        "row_hints": {"open_items": {"open_amount_usd", "customer_id", "due_date"}},
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
    },
    "structured-hiring-rubric": {
        "primary_key": "candidates",
        "sheet_routes": {
            "candidates": ("candidate", "scorecard", "interview", "rubric", "hiring"),
            "interviewers": ("interviewer", "panel_score", "feedback"),
        },
        "row_hints": {
            "candidates": {"candidate_id", "role"},
            "interviewers": {"candidate_id", "interviewer_id", "score", "evidence_text"},
        },
    },
    "employee-onboarding-navigator": {
        "primary_key": "hires",
        "sheet_routes": {
            "hires": ("hire", "new_hire", "onboarding", "employee"),
            "tasks": ("task", "checklist", "provisioning"),
        },
        "scalar_keys": ("as_of_date",),
        "row_hints": {
            "hires": {"employee_id", "start_date"},
            "tasks": {"employee_id", "task_id", "due_day_offset"},
        },
    },
    "pipeline-hygiene-slippage": {
        "primary_key": "opportunities",
        "sheet_routes": {
            "opportunities": ("pipeline", "crm", "deal", "opportunit"),
            "fx_rates": ("fx_rate",),
        },
        "scalar_keys": ("remaining_quota_usd",),
        "row_hints": {"opportunities": {"opportunity_id", "stage", "forecast_category"}},
    },
    "rfp-questionnaire-responder": {
        "primary_key": "questions",
        "sheet_routes": {
            "questions": ("rfp", "question", "requirement"),
            "answer_library": ("answer_bank", "answer_library", "approved_bid"),
        },
        "row_hints": {"questions": {"question_id", "question"}, "answer_library": {"answer", "source_id"}},
    },
    "deal-desk-quote-guard": {
        "primary_key": "quotes",
        "sheet_routes": {
            "quotes": ("quote", "deal_desk", "dealdesk", "pricing"),
            "line_items": ("line_item", "quote_line", "sku_line"),
        },
        "row_hints": {
            "quotes": {"quote_id", "customer_name", "term_months"},
            "line_items": {"quote_id", "unit_list_price_annual", "unit_net_price_annual"},
        },
    },
    "supplier-rfx-tariff-modeler": {
        "primary_key": "bids",
        "sheet_routes": {"bids": ("rfx", "bid", "supplier", "quote")},
        "scalar_keys": ("annual_demand_units", "tariff_shock_pct"),
        "row_hints": {"bids": {"supplier_id", "unit_fob_usd", "origin_country"}},
    },
    "bom-cost-rollup-variance": {
        "primary_key": "bom_edges",
        "sheet_routes": {
            "bom_edges": ("bom", "tree", "edge", "bill_of_material"),
            "items": ("item", "sku", "plant_master", "material", "cost"),
        },
        "row_hints": {"bom_edges": {"parent_sku", "child_sku", "qty_per_parent"}, "items": {"sku", "standard_unit_cost_usd"}},
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
    },
    "sow-scope-margin-auditor": {
        "primary_key": "deliverables",
        "sheet_routes": {
            "deliverables": ("deliverable", "sow", "milestone"),
            "clauses": ("clause", "term"),
        },
        "scalar_keys": ("sow_id", "fixed_fee_usd", "estimated_cost_usd", "acceptance_business_days"),
    },
    "bench-skill-demand-matcher": {
        "primary_key": "consultants",
        "sheet_routes": {
            "consultants": ("bench", "consultant", "roster", "talent"),
            "demands": ("demand", "staffing_req", "role"),
        },
        "row_hints": {"consultants": {"consultant_id", "skills"}, "demands": {"role_id", "required_skills"}},
    },
    "critical-escalation-warroom": {
        "primary_key": "escalations",
        "sheet_routes": {"escalations": ("escalation", "warroom", "account")},
    },
    "csat-churn-signal-miner": {
        "primary_key": "responses",
        "sheet_routes": {"responses": ("csat", "nps", "verbatim", "survey", "response")},
    },
    "troubleshooting-tree-author": {
        "primary_key": "nodes",
        "sheet_routes": {"nodes": ("node", "decision", "tree")},
        "scalar_keys": ("root_node_id",),
    },
    "commercial-credit-memo-analyst": {
        "primary_key": "borrowers",
        "sheet_routes": {"borrowers": ("borrower", "credit", "financial", "covenant")},
        "row_hints": {"borrowers": {"borrower_id", "ebitda_usd", "total_debt_usd"}},
    },
    "kyc-aml-screening-dossier": {
        "primary_key": "ownership_edges",
        "sheet_routes": {
            "ownership_edges": ("ownership", "ubo", "registry", "sharehold"),
            "transactions": ("transaction", "wire", "tx"),
        },
        "scalar_keys": ("target_entity_id", "rolling_30d_volume_usd", "trailing_90d_monthly_avg_usd"),
        "row_hints": {"ownership_edges": {"owner_id", "target_id", "direct_pct"}, "transactions": {"tx_id", "amount_usd"}},
    },
    "insurance-claims-triage-pack": {
        "primary_key": "claims",
        "sheet_routes": {
            "claims": ("claim", "loss", "triage"),
            "policies": ("polic", "coverage_schedule", "underwriting"),
        },
        "row_hints": {
            "claims": {"claim_id", "claimed_amount_usd"},
            "policies": {"policy_id", "effective_date", "expiration_date", "aggregate_limit_usd"},
        },
    },
    "asset-reliability-spares-planner": {
        "primary_key": "spare_parts",
        "sheet_routes": {"spare_parts": ("spare", "safetystock", "safety_stock", "inventory", "cmms")},
        "row_hints": {"spare_parts": {"part_id", "on_hand_qty", "observed_failures"}},
    },
    "quality-capex-rca-copilot": {
        "primary_key": "events",
        "sheet_routes": {
            "events": ("inspection", "lot", "defect", "scrap", "quality"),
            "capex_proposals": ("capex", "proposal"),
        },
        "row_hints": {"events": {"defect_type", "scrap_cost_usd"}, "capex_proposals": {"proposal_id", "capex_cost_usd"}},
    },
    "ehs-safety-permit-auditor": {
        "primary_key": "permits",
        "sheet_routes": {"permits": ("permit", "ehs", "hse", "ptw")},
        "scalar_keys": ("as_of_date",),
        "row_hints": {"permits": {"permit_id", "gas_test_lel_pct", "loto_isolated"}},
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
    },
    "pharmacovigilance-safety-intake": {
        "primary_key": "cases",
        "sheet_routes": {"cases": ("icsr", "safety", "adverse", "case")},
        "scalar_keys": ("as_of_date",),
        "row_hints": {"cases": {"case_id", "adverse_event_term", "awareness_date"}},
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
    },
    "store-ops-shrink-copilot": {
        "primary_key": "sku_store_records",
        "sheet_routes": {"sku_store_records": ("shrink", "osa", "store_sku", "inventory")},
        "row_hints": {"sku_store_records": {"store_id", "book_on_hand_qty", "days_since_last_pos_scan"}},
    },
    "merchandising-assortment-planner": {
        "primary_key": "campaigns",
        "sheet_routes": {"campaigns": ("pos", "promo", "campaign", "weekly_store")},
        "row_hints": {"campaigns": {"campaign_id", "baseline_units", "promo_units"}},
    },
    "supplier-otif-chargeback-auditor": {
        "primary_key": "po_deliveries",
        "sheet_routes": {"po_deliveries": ("otif", "shipment", "carrier", "delivery", "detention")},
        "row_hints": {"po_deliveries": {"po_number", "ordered_units", "received_units", "dwell_minutes"}},
    },
    "merchant-catalog-trust-gate": {
        "primary_key": "listings",
        "sheet_routes": {"listings": ("merchant", "catalog", "listing")},
        "row_hints": {"listings": {"listing_id", "merchant_id", "price_usd"}},
    },
    "logistics-sla-dispute-resolver": {
        "primary_key": "disputes",
        "sheet_routes": {"disputes": ("dispute", "geozone", "dispatch_dispute", "order_sla")},
        "row_hints": {"disputes": {"order_id", "zone_id", "promised_total_minutes"}},
    },
    "commission-payout-reconciler": {
        "primary_key": "merchant_payouts",
        "sheet_routes": {"merchant_payouts": ("payout", "gmv", "settlement", "seller")},
        "row_hints": {"merchant_payouts": {"merchant_id", "gross_gmv_local", "actual_psp_settled_amount"}},
    },
    "noc-outage-topology-correlator": {
        "primary_key": "alarms",
        "sheet_routes": {
            "alarms": ("alarm", "ran_core", "fault"),
            "nodes": ("node", "topology_node"),
            "edges": ("edge", "link"),
        },
        "row_hints": {"alarms": {"alarm_code", "node_id"}, "nodes": {"node_id", "node_type"}},
    },
    "field-dispatch-spares-prep": {
        "primary_key": "work_orders",
        "sheet_routes": {
            "work_orders": ("work_order", "dispatch"),
            "technicians": ("tech", "engineer"),
        },
        "scalar_keys": ("dispatch_date",),
    },
    "b2b-order-fallout-resolver": {
        "primary_key": "fallout_orders",
        "sheet_routes": {"fallout_orders": ("fallout", "mvno", "b2b_order")},
        "row_hints": {"fallout_orders": {"order_id", "fallout_code", "mrc_usd"}},
    },
    "citizen-case-eligibility-triager": {
        "primary_key": "cases",
        "sheet_routes": {"cases": ("applicant", "benefit", "citizen", "case")},
    },
    "procurement-tender-evaluator": {
        "primary_key": "bids",
        "sheet_routes": {"bids": ("tender", "bid", "vendor", "proposal")},
        "scalar_keys": ("tender_id",),
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
    },
    "contract-playbook-redliner": {
        "primary_key": "clauses",
        "sheet_routes": {"clauses": ("clause", "redline")},
        "scalar_keys": ("contract_id", "contract_type", "counterparty"),
        "row_hints": {"clauses": {"clause_id", "clause_text"}},
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
    },
    "regulatory-change-mapper": {
        "primary_key": "controls",
        "sheet_routes": {"articles": ("article", "regulation"), "controls": ("control", "gap")},
        "scalar_keys": ("as_of_date",),
        "row_hints": {
            "articles": {"article_id", "regulation", "required_domains"},
            "controls": {"control_id", "control_status", "mapped_articles"},
        },
    },
    "policy-sop-answering": {
        "primary_key": "clauses",
        "sheet_routes": {"clauses": ("policy", "sop", "clause")},
        "scalar_keys": ("query", "jurisdiction", "entity", "as_of_date"),
        "row_hints": {"clauses": {"clause_id", "text", "jurisdiction"}},
    },
    "cross-source-knowledge-synthesis": {
        "primary_key": "sources",
        "sheet_routes": {"sources": ("source", "doc"), "draft_claims": ("claim", "draft")},
        "scalar_keys": ("as_of_date",),
    },
    "knowledge-gap-freshness-audit": {
        "primary_key": "documents",
        "sheet_routes": {"documents": ("document", "knowledge", "article", "gap")},
        "scalar_keys": ("as_of_date",),
    },
    "daily-executive-briefing": {
        "primary_key": "events",
        "sheet_routes": {
            "events": ("event", "calendar", "meeting"),
            "priority_threads": ("thread", "email", "priority"),
            "commitments": ("commitment", "action"),
        },
        "scalar_keys": ("briefing_date",),
    },
    "meeting-to-execution-pack": {
        "primary_key": "segments",
        "sheet_routes": {
            "segments": ("transcript", "segment"),
            "prior_open_commitments": ("commitment", "prior", "action"),
        },
        "raw_text_key": "raw_transcript",
        "scalar_keys": ("meeting_title",),
    },
    "stakeholder-account-prep": {
        "primary_key": "accounts",
        "sheet_routes": {"accounts": ("account", "stakeholder", "customer")},
        "scalar_keys": ("as_of_date",),
    },
    "incident-triage-routing": {
        "primary_key": "incidents",
        "sheet_routes": {"incidents": ("incident", "sev", "ticket"), "runbooks": ("runbook", "kb")},
        "scalar_keys": ("as_of_time",),
    },
    "change-risk-cab-review": {
        "primary_key": "changes",
        "sheet_routes": {"changes": ("change", "chg", "cab"), "freeze_windows": ("freeze", "blackout")},
    },
    "problem-rca-kb-generator": {
        "primary_key": "tickets",
        "sheet_routes": {"tickets": ("ticket", "problem", "incident"), "kcs_drafts": ("kcs", "kb", "article")},
        "scalar_keys": ("sample_window_days",),
    },
    "legacy-code-to-prd": {
        "primary_key": "modules",
        "sheet_routes": {
            "modules": ("module", "code", "service", "inventory"),
            "requirements": ("requirement", "prd", "spec"),
            "tests": ("test", "coverage"),
        },
    },
    "sre-incident-postmortem": {
        "primary_key": "incidents",
        "sheet_routes": {
            "incidents": ("incident", "outage", "timeline"),
            "action_items": ("action", "remediation"),
        },
        "scalar_keys": ("as_of_time", "slo_target_pct", "window_days"),
    },
    "security-pr-readiness-gate": {
        "primary_key": "dependencies",
        "sheet_routes": {"dependencies": ("dependenc", "package", "vuln")},
        "raw_text_key": "diff",
        "scalar_keys": ("pr_id",),
    },
    "brand-voice-compliance-gate": {
        "primary_key": "assets",
        "sheet_routes": {"assets": ("asset", "copy", "brand")},
    },
    "multimodal-campaign-brief": {
        "primary_key": "deliverables",
        "sheet_routes": {"deliverables": ("deliverable", "campaign", "asset_plan")},
        "scalar_keys": ("campaign_name", "total_budget_usd", "launch_date"),
    },
    "market-localization-adapter": {
        "primary_key": "translations",
        "sheet_routes": {"translations": ("translation", "locale"), "glossary": ("glossary", "term")},
        "scalar_keys": ("source_text",),
    },
    "schema-grounded-sql-analyst": {
        "primary_key": "tables",
        "sheet_routes": {"tables": ("table", "schema", "partition")},
        "raw_text_key": "sql",
        "scalar_keys": ("estimated_scan_gb",),
    },
    "kpi-anomaly-driver-tree": {
        "primary_key": "segments",
        "sheet_routes": {"segments": ("segment", "kpi", "driver", "bridge")},
    },
    "executive-data-story-pack": {
        "primary_key": "rows",
        "sheet_routes": {"rows": ("data", "metric", "story", "kpi", "row")},
        "scalar_keys": ("title",),
    },
}


def _kv_sheet_to_map(rows: list[dict[str, Any]], *, value_as_int: bool = False) -> dict[str, Any]:
    """Convert lookup sheet rows ([{currency, rate_to_usd}] or [{currency, decimals}]) to a flat dict."""
    out: dict[str, Any] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        key = r.get("currency") or r.get("curr") or r.get("waers") or r.get("key") or r.get("code")
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
            k_str = str(key).strip().upper()
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
) -> dict[str, Any]:
    sheets: dict[str, list[dict[str, Any]]] = wb["sheets"]
    sheet_headers: dict[str, list[str]] = wb["sheet_headers"]
    sheet_order: list[str] = wb["sheet_order"]

    payload: dict[str, Any] = {}
    for sk in scalar_keys:
        if sk in wb["metadata_kv"]:
            payload[sk] = wb["metadata_kv"][sk]
    for trunc_key in ("truncated", "done", "total_available"):
        if trunc_key in wb["metadata_kv"]:
            payload[trunc_key] = wb["metadata_kv"][trunc_key]

    # Single explicit sheet request (by name or 0-based index)
    if sheet is not None and str(sheet).strip() != "":
        exact = _resolve_sheet_name(sheet_order, sheet)
        target_key = primary_key or "rows"
        payload[target_key] = sheets[exact]
        return _rollup_nested_records(payload, skill_id=skill_id)

    if len(sheet_order) == 1:
        only_name = sheet_order[0]
        target_key = primary_key or "rows"
        payload[target_key] = sheets[only_name]
        return _rollup_nested_records(payload, skill_id=skill_id)

    assigned: dict[str, list[str]] = {}
    for target_key, patterns in sheet_routes.items():
        if target_key.startswith("_exclude"):
            continue
        hint_cols = row_hints.get(target_key, set())
        scored: list[tuple[float, str]] = []
        for sname in sheet_order:
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
        else:
            payload[target_key] = combined

    # Fallback: if primary_key was not matched by name/hints, pick largest non-parameter sheet
    if primary_key and primary_key not in payload:
        best_sheet = max(
            sheet_order,
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
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    hints = row_hints or {}
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
    if tables and sheet_routes:
        for target_key, patterns in sheet_routes.items():
            if target_key.startswith("_exclude"):
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

    if input_arg is None:
        return {}
    if isinstance(input_arg, dict):
        return input_arg
    if isinstance(input_arg, list):
        return {eff_primary or "records": input_arg}

    p = Path(input_arg)
    suffix = p.suffix.lower()

    if suffix in {".xlsx", ".xlsm"}:
        wb = read_xlsx_workbook(p, field_aliases=eff_aliases)
        return _route_workbook_to_payload(
            wb,
            skill_id=skill_id,
            primary_key=eff_primary,
            sheet=sheet,
            sheet_routes=eff_routes,
            merge_matching_sheets=eff_merge,
            scalar_keys=eff_scalars,
            row_hints=eff_hints,
        )

    if suffix == ".docx":
        doc = read_docx(p, field_aliases=eff_aliases)
        return _route_docx_to_payload(
            doc,
            skill_id=skill_id,
            primary_key=eff_primary,
            sheet_routes=eff_routes,
            raw_text_key=eff_raw_key,
            scalar_keys=eff_scalars,
            row_hints=eff_hints,
        )

    if suffix in {".csv", ".tsv"}:
        rows = read_csv_tsv(p, field_aliases=eff_aliases)
        return _rollup_nested_records({eff_primary or "records": rows}, skill_id=skill_id)

    if suffix in {".sql", ".diff", ".patch", ".txt", ".md"}:
        text = _read_text_with_fallback(p)
        if suffix in {".txt", ".md"} and eff_primary != "clauses" and not eff_raw_key:
            try:
                loaded = json.loads(text)
                if isinstance(loaded, dict):
                    return loaded
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
    if isinstance(loaded, list):
        return {eff_primary or "records": loaded}
    return loaded if isinstance(loaded, dict) else {}


def read_enterprise_table(
    path: str | Path,
    *,
    sheet: str | int | None = None,
    field_aliases: dict[str, str] | None = None,
    fallback_keys: tuple[str, ...] = ("rows", "items", "records"),
) -> list[dict[str, Any]]:
    """Read a flat table from JSON, JSONL, CSV, TSV, XLSX, or DOCX (first table)."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        wb = read_xlsx_workbook(p, field_aliases=field_aliases)
        if not wb["sheet_order"]:
            return []
        if sheet is not None and str(sheet).strip() != "":
            exact = _resolve_sheet_name(wb["sheet_order"], sheet)
            return wb["sheets"][exact]
        return wb["sheets"][wb["sheet_order"][0]]
    if suffix == ".docx":
        doc = read_docx(p, field_aliases=field_aliases)
        return doc["tables"][0]["rows"] if doc.get("tables") else []
    if suffix in {".csv", ".tsv"}:
        return read_csv_tsv(p, field_aliases=field_aliases)
    loaded = read_json_or_jsonl(p)
    if isinstance(loaded, list):
        return [x for x in loaded if isinstance(x, dict)]
    if isinstance(loaded, dict):
        for k in fallback_keys:
            if isinstance(loaded.get(k), list):
                return [x for x in loaded[k] if isinstance(x, dict)]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect enterprise .xlsx, .docx, .csv, or .json files.")
    parser.add_argument("input", type=Path, help="Input file path (.xlsx, .docx, .csv, .tsv, .json, .jsonl)")
    parser.add_argument("--skill", help="Optional skill_id routing profile")
    parser.add_argument("--sheet", help="Optional .xlsx worksheet name or 0-based tab index")
    parser.add_argument("--summary", action="store_true", help="Print structural summary only")
    args = parser.parse_args(argv)

    p: Path = args.input
    if args.summary:
        sfx = p.suffix.lower()
        if sfx in {".xlsx", ".xlsm"}:
            wb = read_xlsx_workbook(p)
            summary = {
                "file": str(p),
                "format": "xlsx",
                "metadata_kv": wb["metadata_kv"],
                "sheets": {
                    s: {"rows": len(wb["sheets"][s]), "headers": wb["sheet_headers"][s]}
                    for s in wb["sheet_order"]
                },
            }
            print(json.dumps(summary, indent=2))
            return 0
        if sfx == ".docx":
            doc = read_docx(p)
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

    payload = load_enterprise_payload(p, skill_id=args.skill, sheet=args.sheet)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
