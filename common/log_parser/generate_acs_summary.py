#!/usr/bin/env python3
# Copyright (c) 2024-2026, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generate the consolidated ACS summary HTML report."""

# Legacy HTML/template strings are intentionally kept intact for readability.
# pylint: disable=line-too-long

import json
import argparse
import os
import subprocess
import re
import html
from jinja2 import Template

from report_ui import enhance_html_report
from suite_registry import get_suite, load_registry, normalize_suite_name


YOCTO_FLAG_PATH = "/mnt/yocto_image.flag"
LEGACY_SUITE_KEYS = {"Suite_Name: FWTS", "Suite_Name: SCT"}
OBSOLETE_DT_SUITE_KEYS = {"Suite_Name: BBR-FWTS", "Suite_Name: BBR-SCT"}

COMPLIANCE_KEY_PATTERN = re.compile(
    r"^Suite_Name:\s*([^:]+?)\s*:\s*(.+?)_compliance\s*$",
    re.IGNORECASE,
)

DETAIL_COMPLIANCE_TARGETS = (
    ("bsa_detailed.html", ("BSA",), "BSA"),
    ("sbsa_detailed.html", ("SBSA",), "SBSA"),
    (
        "fwts_detailed.html",
        ("SBBR-FWTS", "EBBR-FWTS", "FWTS"),
        "FWTS",
    ),
    (
        "sct_detailed.html",
        ("SBBR-SCT", "EBBR-SCT", "SCT"),
        "SCT",
    ),
    ("bbsr_fwts_detailed.html", ("BBSR-FWTS",), "BBSR-FWTS"),
    ("bbsr_sct_detailed.html", ("BBSR-SCT",), "BBSR-SCT"),
    ("bbsr_tpm_detailed.html", ("BBSR-TPM",), "BBSR-TPM"),
    ("pfdi_detailed.html", ("PFDI",), "PFDI"),
    ("post_script_detailed.html", ("POST_SCRIPT",), "POST-SCRIPT"),
    ("scmi_detailed.html", ("SCMI",), "SCMI"),
    ("sbmr_ib_detailed.html", ("SBMR-IB",), "SBMR-IB"),
    ("sbmr_oob_detailed.html", ("SBMR-OOB",), "SBMR-OOB"),
)


def _prefix_from_band(band):
    """Map an ACS band label to its specification prefix, if recognized."""
    normalized_band = str(band).strip().lower()
    if "devicetree" in normalized_band or "device tree" in normalized_band:
        return "EBBR"
    if "systemready" in normalized_band:
        return "SBBR"
    return ""


def get_report_suite_prefix(merged_json_path="", config_band=""):
    """Return the externally visible specification prefix for this report."""
    if merged_json_path and os.path.isfile(merged_json_path):
        try:
            with open(merged_json_path, "r", encoding="utf-8") as merged_file:
                merged_data = json.load(merged_file)
        except (OSError, ValueError, AttributeError):
            merged_data = {}

        if isinstance(merged_data, dict):
            legacy_keys = sorted(LEGACY_SUITE_KEYS.intersection(merged_data))
            if legacy_keys:
                raise ValueError(
                    "Legacy merged suite keys are not supported: "
                    + ", ".join(legacy_keys)
                )

            obsolete_dt_keys = sorted(
                OBSOLETE_DT_SUITE_KEYS.intersection(merged_data)
            )
            if obsolete_dt_keys:
                raise ValueError(
                    "Obsolete DT merged suite keys are not supported; "
                    "use EBBR: " + ", ".join(obsolete_dt_keys)
                )

            suite_keys = merged_data.keys()
            wrapper_prefixes = {
                prefix
                for prefix in ("SBBR", "EBBR")
                if any(
                    f"Suite_Name: {prefix}-{suite}" in suite_keys
                    for suite in ("FWTS", "SCT")
                )
            }
            if len(wrapper_prefixes) > 1:
                raise ValueError(
                    "Mixed EBBR/SBBR merged suite keys are not supported"
                )

            acs_info = merged_data.get("Suite_Name: acs_info", {})
            band_prefix = ""
            for section_name in ("ACS Results Summary", "System Info"):
                prefix = _prefix_from_band(
                    acs_info.get(section_name, {}).get("Band", "")
                )
                if prefix:
                    if band_prefix and band_prefix != prefix:
                        raise ValueError(
                            "Conflicting Band values in merged acs_info"
                        )
                    band_prefix = prefix

            wrapper_prefix = next(iter(wrapper_prefixes), "")
            if (
                wrapper_prefix
                and band_prefix
                and wrapper_prefix != band_prefix
            ):
                raise ValueError(
                    f"Merged {wrapper_prefix} suite keys do not match "
                    f"the {band_prefix} Band"
                )
            if wrapper_prefix:
                return wrapper_prefix
            if band_prefix:
                return band_prefix

    prefix = _prefix_from_band(config_band)
    if prefix:
        return prefix

    return "EBBR" if os.path.isfile(YOCTO_FLAG_PATH) else "SBBR"


def get_system_info():
    """Collect fallback firmware and platform information from the host."""
    system_info = {}

    # Get Firmware Version
    try:
        fw_version_output = subprocess.check_output(
            ["dmidecode", "-t", "bios"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in fw_version_output.split('\n'):
            if 'Version:' in line:
                system_info['Firmware Version'] = line.split('Version:')[1].strip()
                break
    except Exception:
        system_info['Firmware Version'] = 'Unknown'

    # SoC Family
    try:
        soc_family_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL
        )
        # Iterate each line looking for "Family:"
        for line in soc_family_output.split('\n'):
            if 'Family:' in line:
                system_info['SoC Family'] = line.split('Family:', 1)[1].strip()
                break
        else:
            # #If we didn't find 'Family:'
            system_info['SoC Family'] = 'Unknown'
    except Exception:
        system_info['SoC Family'] = 'Unknown'

    # Get System Name
    try:
        system_name_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in system_name_output.split('\n'):
            if 'Product Name:' in line:
                system_info['System Name'] = line.split('Product Name:')[1].strip()
                break
        else:
            # If we didn't find 'Product Name:'
            system_info['System Name'] = 'Unknown'
    except Exception:
        system_info['System Name'] = 'Unknown'

    # Get Vendor
    try:
        vendor_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in vendor_output.split('\n'):
            if 'Manufacturer:' in line:
                system_info['Vendor'] = line.split('Manufacturer:')[1].strip()
                break
    except Exception:
        system_info['Vendor'] = 'Unknown'

    # Add date when the summary was generated
    try:
        system_info['Summary Generated On Date/time'] = subprocess.check_output(
            ["date", "+%Y-%m-%d %H:%M:%S"], universal_newlines=True).strip()
    except Exception:
        system_info['Summary Generated On Date/time'] = 'Unknown'

    return system_info

def parse_config(config_path):
    """Read colon-separated values from an ACS configuration file."""
    config_info = {}
    try:
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as config_file:
                for line in config_file:
                    # Stop parsing at the user-defined configs section
                    if line.strip().startswith('# User-defined configs'):
                        break
                    if ':' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split(':', 1)
                        config_info[key.strip()] = value.strip()
        else:
            print(f"Config file {config_path} not provided or does not exist.")
    except Exception as error:
        print(f"Error reading {config_path}: {error}")
    return config_info

def get_uefi_version(uefi_version_log):
    """Read the UEFI version from its UTF-16 log when available."""
    uefi_version = 'Unknown'
    try:
        if uefi_version_log and os.path.exists(uefi_version_log):
            with open(uefi_version_log, 'r', encoding='utf-16') as file:
                for line in file:
                    if 'UEFI v' in line:
                        uefi_version = line.strip()
                        break
        else:
            uefi_version = 'Not provided'
    except Exception as error:
        print(f"Error reading UEFI version log: {error}")
    return uefi_version

def read_acs_info_system_info(acs_info_json_path):
    """Load System Info from acs_info.json if available."""
    if not acs_info_json_path or not os.path.exists(acs_info_json_path):
        return {}
    try:
        with open(acs_info_json_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        return data.get("System Info", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}

def build_system_info(acs_config_path, system_config_path, uefi_version_log,
                      acs_info_json_path, use_acs_info_system_info=False):
    """Build summary system information without changing the legacy default path."""
    acs_info_system = read_acs_info_system_info(acs_info_json_path)
    if use_acs_info_system_info:
        system_info = dict(acs_info_system) if isinstance(acs_info_system, dict) else {}
        summary_generated_date = system_info.pop('Summary Generated On', None)
        legacy_date = system_info.pop('Summary Generated On Date/time', None)
        return (
            system_info,
            summary_generated_date or legacy_date or 'Unknown',
            system_info.get('Band', 'Unknown'),
        )

    system_info = get_system_info()
    acs_config_info = parse_config(acs_config_path)
    system_info.update(acs_config_info)
    system_info.update(parse_config(system_config_path))
    system_info['UEFI Version'] = get_uefi_version(uefi_version_log)

    if isinstance(acs_info_system, dict) and "BMC Firmware Version" in acs_info_system:
        system_info["BMC Firmware Version"] = acs_info_system.get("BMC Firmware Version", "N/A")
    if isinstance(acs_info_system, dict) and "PSCI version" in acs_info_system:
        system_info["PSCI version"] = acs_info_system.get("PSCI version", "Unknown")

    summary_generated_date = system_info.pop('Summary Generated On Date/time', 'Unknown')
    return system_info, summary_generated_date, acs_config_info.get('Band', 'Unknown')

def remove_result_summary_headings(content):
    """Remove nested result-summary headings before suite HTML is embedded."""
    # Use regular expressions to remove any heading containing 'Result Summary'
    pattern = r'<h[1-6][^>]*>\s*Result Summary\s*</h[1-6]>'
    content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    return content

def read_html_content(file_path):
    """Return sanitized body content from a generated suite summary."""
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            # Suite summaries are complete standalone documents.  Embed only
            # their body markup in the consolidated report so nested <html>,
            # CSS, and interaction scripts cannot leak into the parent page.
            body_match = re.search(
                r'<body\b[^>]*>(.*?)</body\s*>',
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if body_match:
                content = body_match.group(1)
            content = re.sub(
                r'<script\b[^>]*>.*?</script\s*>',
                '',
                content,
                flags=re.IGNORECASE | re.DOTALL,
            )
            # Remove 'Result Summary' headings
            content = remove_result_summary_headings(content)
            return content
    else:
        return None

def inject_test_suite_info(merged_json_path, output_dir):
    """Inject suite descriptions from merged JSON into detailed reports."""
    # Add Test_suite_info into detailed HTMLs after they are generated.
    if not merged_json_path or not os.path.isfile(merged_json_path):
        return
    try:
        with open(merged_json_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
    except Exception:
        return

    def entries(value):
        # Always return a list of suite entries.
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and isinstance(value.get("test_results"), list):
            return value["test_results"]
        if isinstance(value, dict):
            return [value]
        return []

    suite_map = {}
    if isinstance(data, dict):
        for suite_key, suite_data in data.items():
            map_key = suite_key
            if suite_key.lower().startswith("suite_name: os tests -"):
                map_key = "Suite_Name: OS Tests"
            for entry in entries(suite_data):
                if not isinstance(entry, dict):
                    continue
                name = (entry.get("Test_suite") or entry.get("Test_suite_name") or "").strip()
                info = entry.get("Test_suite_info")
                if name and info is not None:
                    # Store by lowercase name so PCIe/PCIE still matches.
                    suite_map.setdefault(map_key, {})[name.lower()] = info

    def fmt_info(info):
        # Format list info as bullets; otherwise keep as plain text.
        if isinstance(info, list):
            items = "".join(f"<li>{html.escape(str(i))}</li>" for i in info)
            return f"<ul style=\"margin: 6px 0 0 18px;\">{items}</ul>"
        return html.escape(str(info))

    patterns = [
        # Different detailed HTML templates use different headers.
        (r'(<div class="test-suite-header">Test Suite:\s*([^<]+)</div>)', 2),
        (r'(<div class="suite-header">Test Suite:\s*([^<]+)</div>)', 2),
        (r'(<div class="heading">Test Suite Name:\s*<span>([^<]+)</span></div>)', 2),
        (r'(<h3>\s*([^:<]+)\s*:[^<]*</h3>)', 2),
    ]
    files = [
        # All detailed HTML files that should get Test_suite_info.
        ("bsa_detailed.html", "Suite_Name: BSA"),
        ("sbsa_detailed.html", "Suite_Name: SBSA"),
        ("fwts_detailed.html", (
            "Suite_Name: SBBR-FWTS",
            "Suite_Name: EBBR-FWTS",
        )),
        ("sct_detailed.html", (
            "Suite_Name: SBBR-SCT",
            "Suite_Name: EBBR-SCT",
        )),
        ("bbsr_fwts_detailed.html", "Suite_Name: BBSR-FWTS"),
        ("bbsr_sct_detailed.html", "Suite_Name: BBSR-SCT"),
        ("bbsr_tpm_detailed.html", "Suite_Name: BBSR-TPM"),
        ("pfdi_detailed.html", "Suite_Name: PFDI"),
        ("post_script_detailed.html", "Suite_Name: POST_SCRIPT"),
        ("scmi_detailed.html", "Suite_Name: SCMI"),
        ("sbmr_ib_detailed.html", "Suite_Name: SBMR-IB"),
        ("sbmr_oob_detailed.html", "Suite_Name: SBMR-OOB"),
        ("standalone_tests_detailed.html", "Suite_Name: Standalone"),
        ("os_tests_detailed.html", "Suite_Name: OS Tests"),
    ]

    for filename, suite_keys in files:
        if isinstance(suite_keys, str):
            suite_keys = (suite_keys,)
        info_map = next(
            (suite_map[key] for key in suite_keys if suite_map.get(key)),
            None,
        )
        if not info_map:
            continue
        file_path = os.path.join(output_dir, filename)
        if not os.path.exists(file_path):
            continue
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        updated = re.sub(
            r"(<strong>)Test_suite_info:(</strong>)",
            r"\1Test suite info:\2",
            content,
            flags=re.IGNORECASE,
        )
        for pattern, name_group in patterns:
            out = []
            last = 0
            for match in re.finditer(pattern, updated, re.IGNORECASE):
                out.append(updated[last:match.end()])
                suite_name = (match.group(name_group) or "").strip().lower()
                info = info_map.get(suite_name)
                if info is not None:
                    # Avoid duplicating Test_suite_info in the same section.
                    lookahead = updated[match.end():match.end() + 300]
                    if not re.search(r"Test[_ ]suite[_ ]info", lookahead, re.IGNORECASE):
                        block = (
                            "<div class=\"test-suite-info\" "
                            "style=\"margin: 6px 0 16px 0; color: #7f8c8d; font-size: 16px;\">"
                            "<strong>Test suite info:</strong>"
                            f"{fmt_info(info)}</div>"
                        )
                        out.append(block)
                last = match.end()
            out.append(updated[last:])
            updated = "".join(out)
        if updated != content:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(updated)


def _compliance_identity(value):
    """Return a stable identifier for matching merged compliance entries."""
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _compliance_display(value):
    """Return the user-facing compliance value without its count/reason."""
    raw_value = " ".join(str(value or "Unknown").split()) or "Unknown"
    normalized = raw_value.lower()
    if normalized.startswith("not compliant"):
        return "Not Compliant", "fail"
    if normalized.startswith("compliant with waiver"):
        return "Compliant with waivers", "pass"
    if normalized.startswith("compliant"):
        return "Compliant", "pass"
    if normalized.startswith("not run"):
        return "Not Run", "not-run"
    if normalized.startswith("unknown"):
        return "Unknown", "unknown"
    return raw_value, "unknown"


def _requirement_display(value):
    """Normalize known requirement labels while preserving future values."""
    raw_value = " ".join(str(value or "Unknown").split())
    normalized = raw_value.lower().replace("-", " ")
    labels = {
        "mandatory": "Mandatory",
        "recommended": "Recommended",
        "conditional mandatory": "Conditional-Mandatory",
        "extension": "Extension",
    }
    return labels.get(normalized, raw_value or "Unknown")


def _compliance_slug(value):
    """Return a CSS-safe slug for a requirement or status label."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "unknown"


def _compliance_records(merged_data):
    """Read run-specific suite compliance records from merged ACS data."""
    if not isinstance(merged_data, dict):
        return []
    acs_info = merged_data.get("Suite_Name: acs_info", {})
    if not isinstance(acs_info, dict):
        return []
    results = acs_info.get("ACS Results Summary", {})
    if not isinstance(results, dict):
        return []

    records = []
    for key, value in results.items():
        match = COMPLIANCE_KEY_PATTERN.match(str(key))
        if not match:
            continue
        requirement = _requirement_display(match.group(1))
        component = " ".join(match.group(2).split())
        compliance, tone = _compliance_display(value)
        records.append({
            "component": component,
            "identity": _compliance_identity(component),
            "requirement": requirement,
            "requirement_slug": _compliance_slug(requirement),
            "compliance": compliance,
            "tone": tone,
            "not_run": bool(re.search(
                r"\bnot[\s_-]*run\b", str(value or "").lower()
            )),
        })
    return records


def _merged_entries(value):
    """Return merged suite entries without changing their source order."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("test_results"), list):
        return value["test_results"]
    if isinstance(value, dict):
        return [value]
    return []


def _summary_compliance(rows):
    """Summarize existing decisions for a card, without evaluating raw tests."""
    if not rows:
        return {"requirement": "Unknown", "compliance": "Unknown", "tone": "unknown"}
    mandatory = [row for row in rows if row["requirement"] in (
        "Mandatory", "Conditional-Mandatory"
    )]
    relevant = mandatory or rows
    requirements = {row["requirement"] for row in relevant}
    requirement = "Mandatory" if "Mandatory" in requirements else " / ".join(sorted(requirements))
    if all(row.get("not_run") for row in rows):
        status, tone = "Not Run", "fail" if "Mandatory" in requirements else "not-run"
    elif any(row["tone"] == "fail" or
             (row.get("not_run") and row["requirement"] == "Mandatory") for row in relevant):
        status, tone = "Not Compliant", "fail"
    elif any(row["tone"] == "unknown" for row in relevant):
        status, tone = "Unknown", "unknown"
    elif any("waiver" in row["compliance"].lower() for row in relevant):
        status, tone = "Compliant with waivers", "pass"
    else:
        status, tone = "Compliant", "pass"
    return {"requirement": requirement, "compliance": status, "tone": tone}


def _summary_cards(merged_data, sources, output_dir):
    """Decorate collected summaries and show missing applicable suites only."""
    records = _compliance_records(merged_data)
    by_identity = {row["identity"]: row for row in records}
    registry = load_registry()
    standalone_keys = {
        _compliance_identity(item.get("requirement_key", item["canonical"]))
        for item in registry
        if item["canonical"] in get_suite("STANDALONE", registry)["included_suites"]
    }
    cards = []
    for section_id, label, content, detail, candidates in sources:
        if section_id == "standalone_summary":
            rows = [row for row in records if row["identity"] in standalone_keys]
        elif section_id == "OS_tests_summary":
            rows = [row for row in records if row["identity"].startswith("OS")]
        else:
            rows = [by_identity[key] for key in map(_compliance_identity, candidates)
                    if key in by_identity]
        if not content and not rows:
            continue
        not_run = bool(rows) and all(row.get("not_run") for row in rows)
        state = _summary_compliance(rows)
        if not_run or not content:
            message = "Not Run" if not_run else "Summary unavailable"
            explanation = ("No results were collected for this suite." if not_run else
                           "The summary report was not provided for this suite.")
            content = (
                f'<h1>{html.escape(label)} Test Summary</h1>'
                '<div class="acs-suite-empty">'
                f'<strong>{message}</strong><p>{explanation}</p></div>'
            )
        badge_text = f'{state["requirement"]} ({state["compliance"]})'
        context = "; ".join(
            f'{row["component"]}: {row["requirement"]} '
            f'({row["compliance"]}{"; Not Run" if row.get("not_run") else ""})'
            for row in rows
        ) or "Run-specific compliance information was not provided."
        badge = (
            f'<span class="acs-suite-compliance acs-compliance-{state["tone"]}" '
            f'title="{html.escape(context, quote=True)}">{html.escape(badge_text)}</span>'
        )
        content = re.sub(
            r"(<h[1-6]\b[^>]*>.*?</h[1-6]\s*>)",
            lambda match: '<div class="acs-suite-heading">' + match.group(1) + badge + '</div>',
            content, count=1, flags=re.IGNORECASE | re.DOTALL,
        )
        cards.append({"id": section_id, "label": label, "content": content,
                      "detail": detail if not not_run and
                      os.path.isfile(os.path.join(output_dir, detail)) else ""})
    return cards


def _standalone_rows(merged_data, records):
    """Return one compliance row for each Standalone component in this run."""
    registry = load_registry()
    standalone = get_suite("STANDALONE", registry) or {}
    included_order = standalone.get("included_suites", [])
    included = set(included_order)
    registry_by_name = {
        item.get("canonical"): item
        for item in registry
        if item.get("canonical") in included
    }
    records_by_identity = {record["identity"]: record for record in records}
    special_cases = {
        _compliance_identity("Runtime device mapping conflict test"):
            "RUNTIME-DEV-MAP",
        _compliance_identity("SmbiosTable"): "SMBIOS",
    }

    rows = []
    seen = set()
    standalone_data = merged_data.get("Suite_Name: Standalone", {})
    for entry in _merged_entries(standalone_data):
        if not isinstance(entry, dict) or not entry:
            continue
        candidates = [
            entry.get("Test_case"),
            entry.get("Test_suite"),
            entry.get("Test_suite_name"),
        ]
        canonical = ""
        for candidate in candidates:
            normalized = normalize_suite_name(str(candidate or ""), registry)
            if normalized in included:
                canonical = normalized
                break
            special = special_cases.get(_compliance_identity(candidate))
            if special:
                canonical = special
                break

        record = None
        display_name = ""
        identity = ""
        if canonical:
            registry_entry = registry_by_name.get(canonical, {})
            requirement_key = registry_entry.get("requirement_key", canonical)
            identity = _compliance_identity(requirement_key)
            record = records_by_identity.get(identity)
            display_name = canonical
        else:
            for candidate in candidates:
                candidate_identity = _compliance_identity(candidate)
                if candidate_identity in records_by_identity:
                    identity = candidate_identity
                    record = records_by_identity[candidate_identity]
                    break
            display_name = (
                record["component"] if record else
                next((str(value).strip() for value in candidates if value),
                     "Unknown component")
            )
            identity = identity or _compliance_identity(display_name)

        if identity in seen:
            continue
        seen.add(identity)
        if record:
            rows.append({**record, "component": display_name})
        else:
            rows.append({
                "component": display_name,
                "identity": identity,
                "requirement": "Unknown",
                "requirement_slug": "unknown",
                "compliance": "Unknown",
                "tone": "unknown",
            })

    if not rows:
        return rows

    # Keep a missing Mandatory component visible in the existing Standalone
    # compliance table without creating an empty result report for it.
    for canonical in included_order:
        registry_entry = registry_by_name.get(canonical, {})
        requirement_key = registry_entry.get("requirement_key", canonical)
        identity = _compliance_identity(requirement_key)
        record = records_by_identity.get(identity)
        if identity in seen or not record or not record.get("not_run"):
            continue
        if (
            record["requirement"] != "Mandatory" or
            record["compliance"] != "Not Compliant"
        ):
            continue
        missing_record = {**record, "component": canonical}
        if missing_record["compliance"] == "Not Compliant":
            missing_record["compliance"] = "Not Compliant (Not Run)"
        rows.append(missing_record)
        seen.add(identity)

    registry_position = {
        _compliance_identity(
            registry_by_name.get(canonical, {}).get(
                "requirement_key", canonical
            )
        ): index
        for index, canonical in enumerate(included_order)
    }
    rows.sort(key=lambda row: registry_position.get(
        row["identity"], len(registry_position)
    ))
    return rows


def _detail_compliance_markup(rows, unit_label):
    """Build the shared semantic compliance table for a detailed report."""
    body_rows = []
    for row in rows:
        component = html.escape(str(row["component"]), quote=True)
        requirement = html.escape(str(row["requirement"]), quote=True)
        compliance = html.escape(str(row["compliance"]), quote=True)
        tone = html.escape(str(row["tone"]), quote=True)
        requirement_slug = html.escape(
            str(row["requirement_slug"]), quote=True
        )
        body_rows.append(
            f'<tr data-acs-compliance-tone="{tone}">'
            f'<th scope="row">{component}</th>'
            '<td><span class="acs-requirement-badge '
            f'acs-requirement-{requirement_slug}">{requirement}</span></td>'
            '<td><span class="acs-compliance-badge '
            f'acs-compliance-{tone}">{compliance}</span></td>'
            '</tr>'
        )
    return (
        '<section class="acs-detail-compliance" '
        'data-acs-detail-compliance="true" '
        f'data-acs-compliance-row-count="{len(rows)}" '
        'aria-labelledby="acs-detail-compliance-title">'
        '<div class="acs-compliance-tab">'
        '<h2 id="acs-detail-compliance-title">Compliance results</h2></div>'
        '<table class="acs-compliance-table">'
        '<caption class="acs-visually-hidden">Run-specific requirement and '
        f'compliance for each {html.escape(unit_label.lower())} in this '
        'detailed report</caption>'
        '<colgroup><col class="acs-compliance-component-column">'
        '<col class="acs-compliance-requirement-column">'
        '<col class="acs-compliance-status-column"></colgroup>'
        f'<thead><tr><th scope="col">{html.escape(unit_label)}</th>'
        '<th scope="col">Requirement</th>'
        '<th scope="col">Compliance</th></tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></section>'
    )


def inject_detail_compliance(merged_json_path, output_dir):
    """Inject run-specific requirement/compliance tables into detail pages."""
    if not merged_json_path or not os.path.isfile(merged_json_path):
        return
    try:
        with open(merged_json_path, "r", encoding="utf-8") as json_file:
            merged_data = json.load(json_file)
    except (OSError, ValueError, TypeError):
        return

    records = _compliance_records(merged_data)
    records_by_identity = {record["identity"]: record for record in records}
    targets = []
    for filename, candidates, fallback_name in DETAIL_COMPLIANCE_TARGETS:
        record = next(
            (
                records_by_identity.get(_compliance_identity(candidate))
                for candidate in candidates
                if records_by_identity.get(_compliance_identity(candidate))
            ),
            None,
        )
        display_name = (
            record["component"]
            if record and fallback_name in ("FWTS", "SCT")
            else fallback_name
        )
        row = {**record, "component": display_name} if record else {
            "component": display_name,
            "identity": _compliance_identity(display_name),
            "requirement": "Unknown",
            "requirement_slug": "unknown",
            "compliance": "Unknown",
            "tone": "unknown",
        }
        targets.append((filename, [row], "Test suite"))

    # Include applicable Not Run interfaces in the existing compliance table,
    # without creating empty result sections or detailed pages.
    sbmr_rows = []
    for label in ("SBMR-IB", "SBMR-OOB"):
        record = records_by_identity.get(_compliance_identity(label))
        if not _merged_entries(merged_data.get(f"Suite_Name: {label}")) and not (
            record and record.get("not_run")
        ):
            continue
        row = {**record, "component": label} if record else {
            "component": label, "requirement": "Unknown", "requirement_slug": "unknown",
            "compliance": "Unknown", "tone": "unknown",
        }
        if row.get("not_run") and row["compliance"] != "Not Run":
            row["compliance"] += " (Not Run)"
        sbmr_rows.append(row)
    if sbmr_rows:
        targets.append(("sbmr_detailed.html", sbmr_rows, "Test suite"))

    standalone_rows = _standalone_rows(merged_data, records)
    if standalone_rows:
        targets.append((
            "standalone_tests_detailed.html", standalone_rows, "Test case"
        ))

    dynamic_os_rows = [
        {**record, "component": record["component"].replace("_", "-")}
        for record in records
        if record["identity"].startswith("OS") and
        record["identity"] != _compliance_identity("OS_TEST")
    ]
    if dynamic_os_rows:
        targets.append(("os_tests_detailed.html", dynamic_os_rows, "Test case"))
    else:
        os_record = records_by_identity.get(_compliance_identity("OS_TEST"))
        os_row = {**os_record, "component": "OS-TESTS"} if os_record else {
            "component": "OS-TESTS",
            "identity": _compliance_identity("OS_TEST"),
            "requirement": "Unknown",
            "requirement_slug": "unknown",
            "compliance": "Unknown",
            "tone": "unknown",
        }
        targets.append((
            "os_tests_detailed.html", [os_row], "Test case"
        ))

    existing_table = re.compile(
        r"<section\b[^>]*\bdata-acs-detail-compliance\s*=\s*"
        r"([\"'])true\1[^>]*>.*?</section>",
        re.IGNORECASE | re.DOTALL,
    )
    for filename, rows, unit_label in targets:
        file_path = os.path.join(output_dir, filename)
        if not os.path.isfile(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as detail_file:
                content = detail_file.read()
        except OSError:
            continue
        markup = _detail_compliance_markup(rows, unit_label)
        if existing_table.search(content):
            updated, replacements = existing_table.subn(
                markup, content, count=1
            )
        else:
            updated, replacements = re.subn(
                r"(</h1\s*>)",
                lambda match: match.group(1) + "\n" + markup,
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if not replacements:
            updated, replacements = re.subn(
                r"(<div\b[^>]*class\s*=\s*([\"'])[^\"']*"
                r"\bdetailed-(?:summary|container)\b[^\"']*\2[^>]*>)",
                lambda match: markup + "\n" + match.group(1),
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if replacements and updated != content:
            with open(file_path, "w", encoding="utf-8") as detail_file:
                detail_file.write(updated)

def adjust_bbsr_headings(content, suite_name):
    """Replace a generic BBSR heading with the selected suite name."""
    if content:
        pattern = r'(<h[1-6][^>]*>)(.*? Test Summary)(</h[1-6]>)'
        replacement = r'\1' + suite_name + r' Test Summary\3'
        content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
    return content


def adjust_suite_headings(content, suite_name):
    """Update the first test-summary heading and document title."""
    content = adjust_bbsr_headings(content, suite_name)
    if content:
        title_pattern = r'(<title>)(.*? Test Summary)(</title>)'
        content = re.sub(
            title_pattern,
            r'\1' + suite_name + r' Test Summary\3',
            content,
            count=1,
            flags=re.IGNORECASE,
        )
    return content


def adjust_detailed_summary_heading(file_path, suite_name, adjust_title=False):
    """Update the first test-summary heading in an existing report."""
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        if adjust_title:
            content = adjust_suite_headings(content, suite_name)
        else:
            content = adjust_bbsr_headings(content, suite_name)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)


def link_detailed_reports_to_main(output_html_path):
    """Mark detailed reports that have a generated main summary page."""
    output_dir = os.path.dirname(output_html_path) or "."
    main_page = html.escape(os.path.basename(output_html_path), quote=True)
    for filename in sorted(os.listdir(output_dir)):
        if not filename.endswith("_detailed.html"):
            continue
        file_path = os.path.join(output_dir, filename)
        with open(file_path, "r", encoding="utf-8") as html_file:
            content = html_file.read()
        main_page_attribute = re.compile(
            r"\bdata-acs-main-page\s*=\s*([\"']).*?\1",
            re.IGNORECASE,
        )
        if main_page_attribute.search(content):
            content, replacements = main_page_attribute.subn(
                f'data-acs-main-page="{main_page}"', content, count=1
            )
        else:
            content, replacements = re.subn(
                r"<body\b",
                f'<body data-acs-main-page="{main_page}"',
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        if replacements:
            with open(file_path, "w", encoding="utf-8") as html_file:
                html_file.write(content)

def read_overall_compliance_from_merged_json(merged_json_path):
    """
    Opens the merged_results.json and retrieves the final
    "Overall Compliance Result" from:
      data["Suite_Name: acs_info"]["ACS Results Summary"]["Overall Compliance Result"]

    Returns: (overall_result, bbsr_result, scmi_result, mandatory_details, recommended_details, bbsr_details)
    where mandatory_details, recommended_details, and bbsr_details are dicts with 'not_run' and 'failed' lists
    """
    overall_result = "Unknown"
    bbsr_result = "Unknown"
    mandatory_details = {"not_run": [], "failed": []}
    recommended_details = {"not_run": [], "failed": []}
    bbsr_details = {"not_run": [], "failed": []}
    scmi_result = "Unknown"

    try:
        with open(merged_json_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        acs_info_data = data.get("Suite_Name: acs_info", {})
        acs_summary = acs_info_data.get("ACS Results Summary", {})
        overall_result = acs_summary.get("Overall Compliance Result", "Unknown")

        # Parse the overall result to extract mandatory and recommended details
        # Format: "Not Compliant : Mandatory - (not run: X; failed: Y) : Recommended - (not run: A; failed: B)"
        if "Mandatory -" in overall_result or "Recommended -" in overall_result:
            # Split by " : " to get sections
            sections = overall_result.split(" : ")
            for section in sections:
                if section.startswith("Mandatory -"):
                    # Extract content within parentheses
                    match = re.search(r'Mandatory - \((.*?)\)', section)
                    if match:
                        content = match.group(1)
                        # Parse "not run: X; failed: Y"
                        parts = content.split("; ")
                        for part in parts:
                            if part.startswith("not run:"):
                                suites = part.replace("not run:", "").strip()
                                mandatory_details["not_run"] = [s.strip() for s in suites.split(",")]
                            elif part.startswith("failed:"):
                                suites = part.replace("failed:", "").strip()
                                mandatory_details["failed"] = [s.strip() for s in suites.split(",")]

                elif section.startswith("Recommended -"):
                    match = re.search(r'Recommended - \((.*?)\)', section)
                    if match:
                        content = match.group(1)
                        parts = content.split("; ")
                        for part in parts:
                            if part.startswith("not run:"):
                                suites = part.replace("not run:", "").strip()
                                recommended_details["not_run"] = [s.strip() for s in suites.split(",")]
                            elif part.startswith("failed:"):
                                suites = part.replace("failed:", "").strip()
                                recommended_details["failed"] = [s.strip() for s in suites.split(",")]

        # Get BBSR compliance result and parse it
        if "BBSR compliance results" in acs_info_data:
            bbsr_result = acs_info_data.get("BBSR compliance results", "Unknown")
        else:
            bbsr_result = acs_summary.get("BBSR compliance results", "Unknown")

        # Parse BBSR result to extract mandatory details
        # Format: "Not Compliant : Mandatory - (not run: X; failed: Y)"
        if "Mandatory -" in bbsr_result:
            match = re.search(r'Mandatory - \((.*?)\)', bbsr_result)
            if match:
                content = match.group(1)
                parts = content.split("; ")
                for part in parts:
                    if part.startswith("not run:"):
                        suites = part.replace("not run:", "").strip()
                        bbsr_details["not_run"] = [s.strip() for s in suites.split(",")]
                    elif part.startswith("failed:"):
                        suites = part.replace("failed:", "").strip()
                        bbsr_details["failed"] = [s.strip() for s in suites.split(",")]

        # Get SCMI compliance result from ACS Results Summary
        scmi_result = acs_summary.get("SCMI compliance results", "")

    except Exception as error:
        print(
            "Warning: Could not read merged JSON or find "
            f"'Overall Compliance Result': {error}"
        )

    # Derive SCMI details for the Extensions table (without storing in merged JSON)
    scmi_details = {"not_run": [], "failed": []}
    scmi_low = (scmi_result or "").lower()
    if "not compliant" in scmi_low:
        scmi_details["failed"] = ["SCMI"]

    return overall_result, bbsr_result, scmi_result, mandatory_details, recommended_details, bbsr_details, scmi_details

def generate_html(system_info, acs_results_summary,
                  bsa_summary_path, sbsa_summary_path, fwts_summary_path, sct_summary_path,
                  sbmr_ib_summary_path, sbmr_oob_summary_path, scmi_summary_path,
                  bbsr_fwts_summary_path, bbsr_sct_summary_path, bbsr_tpm_summary_path, pfdi_summary_path,
                  post_script_summary_path,
                  standalone_summary_path, os_tests_summary_path,
                  output_html_path, suite_prefix="SBBR", sbmr_combined_summary_path="",
                  merged_json_path=""):
    """Generate the consolidated ACS summary from all suite summaries."""

    fwts_suite_name = f"{suite_prefix}-FWTS"
    sct_suite_name = f"{suite_prefix}-SCT"

    # Read the summary HTML content from each suite
    bsa_summary_content = read_html_content(bsa_summary_path)
    sbsa_summary_content = read_html_content(sbsa_summary_path)
    fwts_summary_content = read_html_content(fwts_summary_path)
    sct_summary_content = read_html_content(sct_summary_path)
    sbmr_ib_summary_content  = read_html_content(sbmr_ib_summary_path)
    sbmr_oob_summary_content = read_html_content(sbmr_oob_summary_path)
    sbmr_summary_content = read_html_content(sbmr_combined_summary_path)
    if sbmr_combined_summary_path and not sbmr_summary_content:
        raise ValueError("The requested combined SBMR summary was not generated")
    if sbmr_summary_content:
        sbmr_ib_summary_content = sbmr_oob_summary_content = None
    scmi_summary_content = read_html_content(scmi_summary_path)
    bbsr_fwts_summary_content = read_html_content(bbsr_fwts_summary_path)
    bbsr_sct_summary_content = read_html_content(bbsr_sct_summary_path)
    bbsr_tpm_summary_content = read_html_content(bbsr_tpm_summary_path)
    pfdi_summary_content = read_html_content(pfdi_summary_path)
    post_script_summary_content = read_html_content(post_script_summary_path)
    standalone_summary_content = read_html_content(standalone_summary_path)
    os_tests_summary_content = read_html_content(os_tests_summary_path)

    # Add the specification/recipe prefix to suite headings in the combined report.
    fwts_summary_content = adjust_suite_headings(
        fwts_summary_content, fwts_suite_name
    )
    sct_summary_content = adjust_suite_headings(
        sct_summary_content, sct_suite_name
    )
    bbsr_fwts_summary_content = adjust_bbsr_headings(bbsr_fwts_summary_content, 'BBSR-FWTS')
    bbsr_sct_summary_content = adjust_bbsr_headings(bbsr_sct_summary_content, 'BBSR-SCT')
    bbsr_tpm_summary_content = adjust_bbsr_headings(bbsr_tpm_summary_content, 'BBSR-TPM')
    post_script_summary_content = adjust_bbsr_headings(post_script_summary_content, 'POST-SCRIPT')
    os_tests_summary_content = adjust_bbsr_headings(
        os_tests_summary_content, 'OS'
    )
    standalone_summary_content = adjust_bbsr_headings(standalone_summary_content, 'Standalone')

    merged_data = {}
    if merged_json_path and os.path.isfile(merged_json_path):
        with open(merged_json_path, encoding="utf-8") as merged_file:
            merged_data = json.load(merged_file)
    sources = [
        ("bsa_summary", "BSA", bsa_summary_content, "bsa_detailed.html", ("BSA",)),
        ("sbsa_summary", "SBSA", sbsa_summary_content, "sbsa_detailed.html", ("SBSA",)),
        ("fwts_summary", fwts_suite_name, fwts_summary_content, "fwts_detailed.html", (fwts_suite_name, "FWTS")),
        ("sct_summary", sct_suite_name, sct_summary_content, "sct_detailed.html", (sct_suite_name, "SCT")),
        ("scmi_summary", "SCMI", scmi_summary_content, "scmi_detailed.html", ("SCMI",)),
    ]
    if sbmr_summary_content or not (sbmr_ib_summary_content or sbmr_oob_summary_content):
        sources.append(("sbmr_summary", "SBMR", sbmr_summary_content, "sbmr_detailed.html", ("SBMR-IB", "SBMR-OOB")))
    else:
        sources.extend([
            ("sbmr_ib_summary", "SBMR-IB", sbmr_ib_summary_content, "sbmr_ib_detailed.html", ("SBMR-IB",)),
            ("sbmr_oob_summary", "SBMR-OOB", sbmr_oob_summary_content, "sbmr_oob_detailed.html", ("SBMR-OOB",)),
        ])
    sources.extend([
        ("post_script_summary", "POST-SCRIPT", post_script_summary_content, "post_script_detailed.html", ("POST_SCRIPT",)),
        ("standalone_summary", "Standalone", standalone_summary_content, "standalone_tests_detailed.html", ()),
        ("bbsr_fwts_summary", "BBSR-FWTS", bbsr_fwts_summary_content, "bbsr_fwts_detailed.html", ("BBSR-FWTS",)),
        ("bbsr_sct_summary", "BBSR-SCT", bbsr_sct_summary_content, "bbsr_sct_detailed.html", ("BBSR-SCT",)),
        ("bbsr_tpm_summary", "BBSR-TPM", bbsr_tpm_summary_content, "bbsr_tpm_detailed.html", ("BBSR-TPM",)),
        ("pfdi_summary", "PFDI", pfdi_summary_content, "pfdi_detailed.html", ("PFDI",)),
        ("OS_tests_summary", "OS Tests", os_tests_summary_content, "os_tests_detailed.html", ("OS_TEST",)),
    ])
    summary_cards = _summary_cards(merged_data, sources, os.path.dirname(output_html_path))

    # Jinja2 template for the final HTML page
    html_template = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>ACS Summary</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f5f5f5;
                color: #333;
                margin: 0;
                padding: 0;
            }
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 24px;
            }
            .container {
                width: 80%;
                margin: 40px auto;
                padding: 20px;
                background-color: #fff;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            h1, h2 {
                color: #2c3e50;
                text-align: left;
            }
            .system-info, .acs-results-summary {
                margin-bottom: 40px;
                padding: 20px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            .system-info h2, .acs-results-summary h2 {
                text-align: left;
                color: #2c3e50;
            }
            .acs-results-summary table, .system-info table {
                width: 100%;
                table-layout: fixed;
            }
            .acs-results-summary table th, .system-info table th {
                width: 320px;        /* set your fixed left column width */
                vertical-align: top;
                white-space: normal;
            }
            .summary-section {
                margin-bottom: 40px;
            }
            .summary {
                margin-bottom: 40px;
                padding: 20px;
                border-bottom: 1px solid #ddd;
            }
            .details-link {
                text-align: center;
                margin-top: 10px;
            }
            .details-link a {
                color: #3498db;
                text-decoration: none;
                font-weight: bold;
                padding: 10px 20px;
                border: 2px solid #3498db;
                border-radius: 5px;
                display: inline-block;
                transition: background-color 0.3s, color 0.3s;
            }
            .details-link a:hover {
                background-color: #3498db;
                color: white;
            }
            .dropdown {
                text-align: center;
                margin-bottom: 40px;
                position: relative;
                display: inline-block;
            }
            .dropdown button {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            .dropdown-content {
                display: none;
                position: absolute;
                background-color: #f9f9f9;
                min-width: 220px;
                box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
                z-index: 1;
                left: 50%;
                transform: translateX(-50%);
            }
            .dropdown-content a {
                color: black;
                padding: 12px 16px;
                text-decoration: none;
                display: block;
                text-align: left;
            }
            .dropdown-content a:hover {
                background-color: #f1f1f1;
            }
            .dropdown:hover .dropdown-content {
                display: block;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }
            table, th, td {
                border: 1px solid #ddd;
            }
            th, td {
                padding: 12px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        </style>
    </head>
    <body>
        <div class="header">
            ACS Summary
        </div>
        <div class="container">
            <div class="system-info">
                <h2>System Information</h2>
                <table>
                    <tr>
                        <th>Vendor</th>
                        <td>{{ system_info.get('Vendor', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>System</th>
                        <td>{{ system_info.get('System Name', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>SoC Family</th>
                        <td>{{ system_info.get('SoC Family', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>Firmware Version</th>
                        <td>{{ system_info.get('Firmware Version', 'Unknown') }}</td>
                    </tr>
                    {% if system_info.get('BMC Firmware Version') %}
                    <tr>
                        <th>BMC Firmware Version</th>
                        <td>{{ system_info.get('BMC Firmware Version') }}</td>
                    </tr>
                    {% endif %}
                    {% for key, value in system_info.items() %}
                    {% if key not in ['Vendor', 'System Name', 'SoC Family', 'Firmware Version', 'BMC Firmware Version'] %}
                    <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                    </tr>
                    {% endif %}
                    {% endfor %}
                </table>
            </div>
            <div class="acs-results-summary">
                <h2>ACS Results Summary</h2>
                <table>
                    <tr>
                        <th>Band</th>
                        <td>{{ acs_results_summary.get('Band', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>Date</th>
                        <td>{{ acs_results_summary.get('Date', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th rowspan="3">SRS requirements compliance results</th>
                        <td style="
                            color:
                            {% if 'Not Compliant' in acs_results_summary.get('Overall Compliance Results', '') %}
                                red
                            {% elif 'Compliant with Waivers' in acs_results_summary.get('Overall Compliance Results', '') %}
                                #FFBF00
                            {% elif 'Compliant' in acs_results_summary.get('Overall Compliance Results', '') %}
                                green
                            {% else %}
                                black
                            {% endif %}
                        ">
                            {% set overall = acs_results_summary.get('Overall Compliance Results', 'Unknown') %}
                            {% if ':' in overall %}
                                {{ overall.split(':')[0].strip() }}
                            {% else %}
                                {{ overall }}
                            {% endif %}
                        </td>
                    </tr>
                    {% set mandatory = acs_results_summary.get('Mandatory Details', {}) %}
                    {% set recommended = acs_results_summary.get('Recommended Details', {}) %}
                    {% if mandatory.get('not_run') or mandatory.get('failed') %}
                    <tr>
                        <td style="padding-left: 20px; color: red;">
                            <strong>Mandatory:</strong>
                            {% if mandatory.get('not_run') %}
                                not run: {{ mandatory.get('not_run')|join(', ') }}
                            {% endif %}
                            {% if mandatory.get('not_run') and mandatory.get('failed') %}; {% endif %}
                            {% if mandatory.get('failed') %}
                                failed: {{ mandatory.get('failed')|join(', ') }}
                            {% endif %}
                        </td>
                    </tr>
                    {% endif %}
                    {% if recommended.get('not_run') or recommended.get('failed') %}
                    <tr>
                        <td style="padding-left: 20px; color: red;">
                            <strong>Recommended:</strong>
                            {% if recommended.get('not_run') %}
                                not run: {{ recommended.get('not_run')|join(', ') }}
                            {% endif %}
                            {% if recommended.get('not_run') and recommended.get('failed') %}; {% endif %}
                            {% if recommended.get('failed') %}
                                failed: {{ recommended.get('failed')|join(', ') }}
                            {% endif %}
                        </td>
                    </tr>
                    {% endif %}
                </table>
            </div>
            <div class="acs-results-summary">
                <h2>Extensions</h2>
                <table>
                    {% set bbsr_ext = acs_results_summary.get('BBSR Details', {}) %}
                    {% set bbsr_has_details = bbsr_ext.get('not_run') or bbsr_ext.get('failed') %}
                    <tr>
                        <th rowspan="{{ 2 if bbsr_has_details else 1 }}">BBSR compliance results</th>
                        <td style="
                            color:
                            {% if 'Not Compliant' in acs_results_summary.get('BBSR compliance results', '') %}
                                red
                            {% elif 'waiver' in acs_results_summary.get('BBSR compliance results', '')|lower %}
                                #FFBF00
                            {% elif 'Compliant' in acs_results_summary.get('BBSR compliance results', '') %}
                                green
                            {% else %}
                                black
                            {% endif %}
                        ">
                            {% set bbsr = acs_results_summary.get('BBSR compliance results', 'Not run') %}
                            {% if ':' in bbsr %}
                                {{ bbsr.split(':')[0].strip() }}
                            {% else %}
                                {{ bbsr }}
                            {% endif %}
                        </td>
                    </tr>
                    {% if bbsr_has_details %}
                    <tr>
                        <td style="padding-left: 20px; color: red;">
                            <strong>Mandatory:</strong>
                            {% if bbsr_ext.get('not_run') %}
                                not run: {{ bbsr_ext.get('not_run')|join(', ') }}
                            {% endif %}
                            {% if bbsr_ext.get('not_run') and bbsr_ext.get('failed') %}; {% endif %}
                            {% if bbsr_ext.get('failed') %}
                                failed: {{ bbsr_ext.get('failed')|join(', ') }}
                            {% endif %}
                        </td>
                    </tr>
                    {% endif %}
                    {% if 'SCMI compliance results' in acs_results_summary %}
                    {% set scmi_ext = acs_results_summary.get('SCMI Details', {}) %}
                    {% set scmi_has_details = scmi_ext.get('not_run') or scmi_ext.get('failed') %}
                    <tr>
                        <th rowspan="{{ 2 if scmi_has_details else 1 }}">SCMI compliance results</th>
                        <td style="
                            color:
                            {% if 'not compliant' in acs_results_summary.get('SCMI compliance results', '')|lower %}
                                red
                            {% elif 'waiver' in acs_results_summary.get('SCMI compliance results', '')|lower %}
                                #FFBF00
                            {% elif 'Compliant' in acs_results_summary.get('SCMI compliance results', '') %}
                                green
                            {% else %}
                                black
                            {% endif %}
                        ">
                            {% set scmi = acs_results_summary.get('SCMI compliance results', 'Not run') %}
                            {% if ':' in scmi %}
                                {{ scmi.split(':')[0].strip() }}
                            {% else %}
                                {{ scmi }}
                            {% endif %}
                        </td>
                    </tr>
                    {% if scmi_has_details %}
                    <tr>
                        <td style="padding-left: 20px; color: red;">
                            <strong>Mandatory:</strong>
                            {% if scmi_ext.get('not_run') %}
                                not run: {{ scmi_ext.get('not_run')|join(', ') }}
                            {% endif %}
                            {% if scmi_ext.get('not_run') and scmi_ext.get('failed') %}; {% endif %}
                            {% if scmi_ext.get('failed') %}
                                failed: {{ scmi_ext.get('failed')|join(', ') }}
                            {% endif %}
                        </td>
                    </tr>
                    {% endif %}
                    {% endif %}
                </table>
            </div>
            <div class="dropdown">
                <button>Go to Summary</button>
                <div class="dropdown-content">
                    {% for card in summary_cards %}
                    <a href="#{{ card.id }}">{{ card.label }} Summary</a>
                    {% endfor %}
                </div>
            </div>
            <div class="summary-section">
                <h2>Test Summaries</h2>
                {% for card in summary_cards %}
                <div class="summary" id="{{ card.id }}">
                    {{ card.content | safe }}
                    {% if card.detail %}
                    <div class="details-link">
                        <a href="{{ card.detail }}">View {{ card.label }} detailed results</a>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    '''

    template = Template(html_template)
    html_output = template.render(
        system_info=system_info,
        acs_results_summary=acs_results_summary,
        summary_cards=summary_cards,
    )

    html_output = enhance_html_report(html_output, page_type="acs-summary")
    with open(output_html_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_output)

    # Keep the individual summary and detailed pages consistent with the
    # headings embedded in acs_summary.html.
    prefixed_summaries = [
        (fwts_summary_path, fwts_suite_name),
        (sct_summary_path, sct_suite_name),
        (
            os.path.join(
                os.path.dirname(output_html_path), "fwts_detailed.html"
            ),
            fwts_suite_name,
        ),
        (
            os.path.join(
                os.path.dirname(output_html_path), "sct_detailed.html"
            ),
            sct_suite_name,
        ),
    ]
    for file_path, suite_name in prefixed_summaries:
        adjust_detailed_summary_heading(
            file_path, suite_name, adjust_title=True
        )

    detailed_summaries = [
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_fwts_detailed.html'), 'BBSR-FWTS'),
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_sct_detailed.html'), 'BBSR-SCT'),
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_tpm_detailed.html'), 'BBSR-TPM'),
        (os.path.join(os.path.dirname(output_html_path), 'sbmr_ib_detailed.html'),  'SBMR-IB'),
        (os.path.join(os.path.dirname(output_html_path), 'sbmr_oob_detailed.html'), 'SBMR-OOB'),
        (os.path.join(os.path.dirname(output_html_path), 'pfdi_detailed.html'), 'PFDI'),
        (os.path.join(os.path.dirname(output_html_path), 'os_tests_detailed.html'), 'OS'),
        (os.path.join(os.path.dirname(output_html_path), 'standalone_tests_detailed.html'), 'Standalone'),
        (os.path.join(os.path.dirname(output_html_path), 'post_script_detailed.html'), 'POST-SCRIPT')
    ]
    for file_path, suite_name in detailed_summaries:
        adjust_detailed_summary_heading(file_path, suite_name)
    link_detailed_reports_to_main(output_html_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ACS Summary HTML page")
    parser.add_argument("--merged_json", default="", help="Path to merged_results.json if you want to pull final compliance from there")
    parser.add_argument("--sbmr-combined-summary", default="", help="Combined SBMR summary retaining per-interface counts")
    parser.add_argument("bsa_summary_path", help="Path to the BSA summary HTML file")
    parser.add_argument("sbsa_summary_path", help="Path to the SBSA summary HTML file")
    parser.add_argument("fwts_summary_path", help="Path to the FWTS summary HTML file")
    parser.add_argument("sct_summary_path", help="Path to the SCT summary HTML file")
    parser.add_argument("bbsr_fwts_summary_path", help="Path to the BBSR FWTS summary HTML file")
    parser.add_argument("bbsr_sct_summary_path", help="Path to the BBSR SCT summary HTML file")
    parser.add_argument("bbsr_tpm_summary_path", help="Path to the BBSR TPM summary HTML file")
    parser.add_argument("pfdi_summary_path",help="Path to the pfdi summary HTML file")
    parser.add_argument("post_script_summary_path", help="Path to the post-script summary HTML file")
    parser.add_argument("standalone_summary_path", help="Path to the Standalone tests summary HTML file")
    parser.add_argument("OS_tests_summary_path", help="Path to the OS Tests summary HTML file")
    parser.add_argument("capsule_update_summary_path", help="Path to the Capsule Update summary HTML file")
    parser.add_argument("sbmr_ib_summary_path", help="Path to the SBMR-IB summary HTML file")
    parser.add_argument("sbmr_oob_summary_path", help="Path to the SBMR-OOB summary HTML file")
    parser.add_argument("scmi_summary_path", help="Path to the SCMI summary HTML file")
    parser.add_argument("output_html_path", help="Path to the output ACS summary HTML file")
    parser.add_argument("--acs_config_path", default="", help="Path to the acs_config.txt file")
    parser.add_argument("--system_config_path", default="", help="Path to the system_config.txt file")
    parser.add_argument("--uefi_version_log", default="", help="Path to the uefi_version.log file")
    parser.add_argument("--device_tree_dts", default="", help="Path to the device_tree.dts file")
    parser.add_argument("--acs_info_json", default="", help="Path to acs_info.json for System Info fields")
    parser.add_argument(
        "--use-acs-info-system-info",
        action="store_true",
        help="Use acs_info.json as the complete System Information source",
    )

    args = parser.parse_args()

    system_info, summary_generated_date, summary_band = build_system_info(
        args.acs_config_path,
        args.system_config_path,
        args.uefi_version_log,
        args.acs_info_json,
        args.use_acs_info_system_info,
    )
    suite_prefix = get_report_suite_prefix(
        args.merged_json,
        summary_band,
    )

    # 5) Read in the stand-alone & capsule summary, then combine them
    standalone_summary_content = read_html_content(args.standalone_summary_path)
    capsule_update_summary_content = read_html_content(args.capsule_update_summary_path)
    if capsule_update_summary_content:
        # Append capsule content to standalone if it exists
        if not standalone_summary_content:
            standalone_summary_content = capsule_update_summary_content
        else:
            standalone_summary_content += "<hr/>\n" + capsule_update_summary_content

    # 6) Collect the summary contents for each suite so we can get the fail/waiver counts (purely for printing)
    suite_content_map = {
        "BSA": read_html_content(args.bsa_summary_path),
        "SBSA": read_html_content(args.sbsa_summary_path),
        f"{suite_prefix}-FWTS": read_html_content(args.fwts_summary_path),
        f"{suite_prefix}-SCT": read_html_content(args.sct_summary_path),
        "SCMI": read_html_content(args.scmi_summary_path),
        "SBMR-IB":  read_html_content(args.sbmr_ib_summary_path),
        "SBMR-OOB": read_html_content(args.sbmr_oob_summary_path),
        "BBSR-FWTS": read_html_content(args.bbsr_fwts_summary_path),
        "BBSR-SCT": read_html_content(args.bbsr_sct_summary_path),
        "BBSR-TPM": read_html_content(args.bbsr_tpm_summary_path),
        "PFDI": read_html_content(args.pfdi_summary_path),
        "POST-SCRIPT": read_html_content(args.post_script_summary_path),
        "Standalone tests": standalone_summary_content,
        "OS tests": read_html_content(args.OS_tests_summary_path)
    }

    # 8) Read overall compliance solely from merged JSON (if provided)
    overall_compliance = "Unknown"
    mandatory_details = {"not_run": [], "failed": []}
    recommended_details = {"not_run": [], "failed": []}
    bbsr_details = {"not_run": [], "failed": []}
    scmi_details = {"not_run": [], "failed": []}
    if args.merged_json and os.path.isfile(args.merged_json):
        overall_compliance, bbsr_compliance, scmi_compliance, mandatory_details, recommended_details, bbsr_details, scmi_details = read_overall_compliance_from_merged_json(args.merged_json)
    else:
        print("Warning: merged JSON not provided or does not exist => Overall compliance unknown")
        overall_compliance, bbsr_compliance, scmi_compliance = "Unknown", "Unknown", "Unknown"

    # 9) Prepare the dictionary that will be used in the final HTML
    acs_results_summary = {
        'Band': summary_band,
        'Date': summary_generated_date,
        'Overall Compliance Results': overall_compliance,
        'BBSR compliance results': bbsr_compliance,
        'Mandatory Details': mandatory_details,
        'Recommended Details': recommended_details,
        'BBSR Details': bbsr_details,
        'SCMI Details': scmi_details
    }
    if scmi_compliance:
        acs_results_summary['SCMI compliance results'] = scmi_compliance

    # 10) Finally, generate the consolidated HTML page
    generate_html(
        system_info,
        acs_results_summary,
        args.bsa_summary_path,
        args.sbsa_summary_path,
        args.fwts_summary_path,
        args.sct_summary_path,
        args.sbmr_ib_summary_path,
        args.sbmr_oob_summary_path,
        args.scmi_summary_path,
        args.bbsr_fwts_summary_path,
        args.bbsr_sct_summary_path,
        args.bbsr_tpm_summary_path,
        args.pfdi_summary_path,
        args.post_script_summary_path,
        args.standalone_summary_path,
        args.OS_tests_summary_path,
        args.output_html_path,
        suite_prefix,
        args.sbmr_combined_summary,
        args.merged_json,
    )

    # Inject Test_suite_info into detailed HTMLs (no change to suite parsers)
    detail_output_dir = os.path.dirname(args.output_html_path)
    inject_test_suite_info(args.merged_json, detail_output_dir)
    inject_detail_compliance(args.merged_json, detail_output_dir)
