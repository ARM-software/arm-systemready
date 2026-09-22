#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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

"""Check that saved JSON, HTML and optional PDF reports agree with their inputs.

Doctor calls these checks only when the user selects them. Saved report packages
are read without changing them or running their scripts. Findings and supporting
files are written to Doctor's output folder. Browser and PDF checks use separate
sample reports created by Doctor, never the supplied reports.
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
import hashlib
import html
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import shutil
from threading import Thread
from urllib.parse import unquote, urlsplit

from .core import load_json

_strict_json = load_json


# ---------------------------------------------------------------------------
# Check which category file the run used before applying its schema requirements.
# ---------------------------------------------------------------------------

MANIFEST = "config/parser_run.json"
INFO_FIELD = "Test_suite_info"


def _contained_file(root, relative):
    """Allow evidence files inside the supplied package, not outside symlink targets."""
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or Path(relative).is_absolute() or ".." in Path(relative).parts):
        raise ValueError("Category evidence path must be relative to the report package")
    path = root / relative
    if root not in path.resolve().parents:
        raise ValueError("Category evidence path escapes the report package")
    if not path.is_file():
        raise ValueError("Category evidence file is missing: " + relative)
    return path


def category_provenance(report_root, mode):
    """Read the run's saved category choice and verify any supplied-file copy.

    Current repository defaults cannot tell us which file an older run used.
    """
    root = Path(report_root).resolve()
    result = {"source": "unknown", "manifest": str(root / MANIFEST),
              "invalid": False, "message": "Run category provenance is unavailable"}
    manifest = root / MANIFEST
    if not manifest.exists() and not manifest.is_symlink():
        return result
    try:
        data = load_json(_contained_file(root, MANIFEST))
        if not isinstance(data, dict) or type(data.get("format_version")) is not int or data["format_version"] != 1:
            raise ValueError("Unsupported parser-run provenance format")
        if data.get("mode") != mode:
            raise ValueError("Parser-run provenance mode does not match " + mode)
        category = data.get("test_category")
        if not isinstance(category, dict) or category.get("source") not in {"explicit", "bundled"}:
            raise ValueError("Parser-run category source must be explicit or bundled")
        if category["source"] == "explicit":
            # A supplied category only counts as evidence if its saved copy matches
            # the checksum recorded when that run was generated.
            snapshot = _contained_file(root, category.get("path"))
            digest = category.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Explicit category snapshot has no valid SHA-256")
            if hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
                raise ValueError("Explicit category snapshot SHA-256 does not match")
            if not isinstance(load_json(snapshot), dict):
                raise ValueError("Explicit category snapshot must be a JSON object")
            result.update(snapshot=str(snapshot), sha256=digest)
        result.update(source=category["source"], message=(
            "Category explicitly supplied to the generating run" if category["source"] == "explicit"
            else "Generating run used its bundled category"))
    except (OSError, ValueError, TypeError) as error:
        result.update(invalid=True, message="Invalid run category provenance: " + str(error))
    return result


def applicable_schema(schema):
    """Return a copy that does not require missing Test_suite_info fields.

    Only schema rules are visited. Example data and the original schema stay intact.
    """
    result = deepcopy(schema)

    def visit(node):
        if not isinstance(node, dict):
            return
        if isinstance(node.get("required"), list):
            node["required"] = [key for key in node["required"] if key != INFO_FIELD]
        for keyword in ("$defs", "definitions", "properties", "patternProperties",
                        "dependentSchemas", "dependencies"):
            children = node.get(keyword)
            if isinstance(children, dict):
                for child in children.values():
                    visit(child)
        for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = node.get(keyword)
            if isinstance(children, list):
                for child in children:
                    visit(child)
        for keyword in ("items", "additionalItems", "contains", "additionalProperties",
                        "unevaluatedProperties", "unevaluatedItems", "propertyNames",
                        "if", "then", "else", "not", "contentSchema"):
            child = node.get(keyword)
            if isinstance(child, list):
                for item in child:
                    visit(item)
            else:
                visit(child)

    visit(result)
    return result


def _pointer(path):
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in path)


def _all_errors(errors):
    for error in errors:
        yield error
        yield from _all_errors(error.context)


def flatten_errors(errors):
    """Keep parent and nested schema errors with their exact JSON field paths."""
    return [{"path": _pointer(error.absolute_path), "message": error.message,
             "validator": error.validator} for error in _all_errors(errors)]


def evaluate_schema(schema_path, fragment, data, provenance):
    """Check the schema using the generating run's category-file information.

    Keep the strict error count as evidence. Relax only the requirement for a
    missing Test_suite_info when no explicitly supplied category is confirmed.
    """
    from jsonschema import Draft202012Validator
    from validate import _load_schema

    _, strict = _load_schema(Path(schema_path), fragment)
    strict_errors = list(strict.iter_errors(data))
    omitted = []
    errors = strict_errors
    if provenance["source"] != "explicit":
        omitted = sorted({_pointer(error.absolute_path) for error in _all_errors(strict_errors)
                          if error.validator == "required" and INFO_FIELD in error.validator_value
                          and isinstance(error.instance, dict) and INFO_FIELD not in error.instance})
        if omitted:
            # The copy includes all locally referenced schema definitions. A new
            # validator prevents references from returning to the unchanged schema.
            effective = applicable_schema(strict.schema)
            Draft202012Validator.check_schema(effective)
            errors = list(Draft202012Validator(effective).iter_errors(data))
    return {"errors": flatten_errors(errors), "strict_error_count": len(flatten_errors(strict_errors)),
            "omitted_missing_info_paths": omitted, "category_provenance": provenance}


def schema_policy_main():
    """Expose the same schema check to Doctor's packaged-parser subprocess."""
    parser = argparse.ArgumentParser(description="Doctor-only applicability of Test_suite_info, without changing "
                "result/schema files.")
    parser.add_argument("--schema-policy", action="store_true",
                        required=True, help=argparse.SUPPRESS)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--mode", choices=("DT", "SR"), required=True)
    parser.add_argument("json_file")
    args = parser.parse_args()
    try:
        from suite_registry import load_registry
        from validate import _build_file_schema_index, _find_schema_for_file

        registry = load_registry(args.registry)
        exact, patterns = _build_file_schema_index(registry, args.registry)
        info = _find_schema_for_file(args.json_file, exact, patterns)
        if not info:
            raise ValueError("No registered raw schema for " + Path(args.json_file).name)
        result = evaluate_schema(info["schema"], info["schema_fragment"], load_json(args.json_file),
                          category_provenance(args.report, args.mode))
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, ImportError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


# ---------------------------------------------------------------------------
# Compare saved report content without executing HTML or changing input files.
# ---------------------------------------------------------------------------

def identity(value):
    """Match display spelling without changing a compliance decision."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def decision(value):
    text = str(value).lower()
    if text.startswith("not compliant"):
        return "Not Compliant"
    if text.startswith("compliant with waiver"):
        return "Compliant with waivers"
    if text.startswith("compliant"):
        return "Compliant"
    if "not run" in text:
        return "Not Run"
    return "Unknown"


class ReportHTML(HTMLParser):
    """Collect table text, badges and local links without running page scripts."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack, self.tables, self.badges, self.links = [], [], [], []
        self.ids, self.anchors = Counter(), set()
        self.active_tables = []
        self.badge = None
        self.detail_headings, self.heading, self.detail_heading = [], None, None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if attrs.get("id"):
            self.ids[attrs["id"]] += 1
        if tag == "a" and attrs.get("name"):
            self.anchors.add(attrs["name"])
        card = next((item[2] for item in reversed(self.stack) if item[2]), "")
        if "summary" in classes and attrs.get("id"):
            card = attrs["id"]
        for key in ("href", "src"):
            if attrs.get(key):
                self.links.append(attrs[key])
        if tag == "table":
            # Nested tables have separate rows. Mark the outer cell so its wrapper
            # is not mistaken for an extra test result later.
            if self.active_tables and self.active_tables[-1]["cell"] is not None:
                self.active_tables[-1]["cell"]["nested"] = True
            table = {"kind": "compliance" if "acs-compliance-table" in classes
                     else "counts" if "summary-table" in classes else "detail",
                     "card": card, "rows": [], "cells": [], "row": None, "cell": None}
            self.tables.append(table)
            self.active_tables.append(table)
            if table["kind"] == "detail" and self.detail_heading is not None:
                self.detail_heading["tables"].append(table)
        if self.active_tables:
            table = self.active_tables[-1]
            if tag == "tr":
                table["row"] = []
            elif tag in ("td", "th") and table["row"] is not None:
                table["cell"] = {"tag": tag, "text": [], "nested": False}
        if "acs-suite-compliance" in classes:
            self.badge = {"card": card, "context": attrs.get("title", ""),
                          "text": []}
        if "heading" in classes:
            self.heading = {"tag": tag, "depth": len(self.stack), "text": []}
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img",
                       "input", "link", "meta", "param", "source", "wbr"}:
            self.stack.append((tag, classes, card))

    def handle_data(self, data):
        # BSA/SBSA reason buttons display the actual rule ID. Other buttons
        # contain hierarchy/action controls, not result-cell content.
        if self.active_tables and not any(item[0] == "button" and "reason-rule-toggle" not in item[1]
                                          for item in self.stack):
            cell = self.active_tables[-1]["cell"]
            if cell is not None:
                cell["text"].append(data)
        if self.badge is not None:
            self.badge["text"].append(data)
        if self.heading is not None:
            self.heading["text"].append(data)

    def handle_endtag(self, tag):
        if (self.heading is not None and tag == self.heading["tag"]
                and len(self.stack) == self.heading["depth"] + 1):
            label, separator, value = " ".join("".join(self.heading["text"]).split()).partition(":")
            if separator:
                field = identity(label)
                if field == "TESTCASE":
                    self.detail_heading = {"id": value.strip(), "description": "",
                                           "status": "", "tables": []}
                    self.detail_headings.append(self.detail_heading)
                elif self.detail_heading is not None:
                    if field == "TESTCASEDESCRIPTION":
                        self.detail_heading["description"] = value.strip()
                    elif field == "TESTRESULT":
                        self.detail_heading["status"] = value.strip()
            self.heading = None
        if self.active_tables:
            table = self.active_tables[-1]
            if tag in ("td", "th") and table["cell"] is not None:
                cell = table["cell"]
                cell["text"] = " ".join("".join(cell["text"]).split())
                table["row"].append(cell)
                table["cell"] = None
            elif tag == "tr" and table["row"] is not None:
                table["cells"].append(table["row"])
                table["rows"].append([cell["text"] for cell in table["row"]])
                table["row"] = None
            elif tag == "table":
                self.active_tables.pop()
        if tag == "span" and self.badge is not None:
            self.badge["text"] = " ".join("".join(self.badge["text"]).split())
            self.badges.append(self.badge)
            self.badge = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def _records(merged):
    """Read suite requirements and decisions recorded in the merged summary."""
    info = merged.get("Suite_Name: acs_info", {})
    summary = info.get("ACS Results Summary", {}) if isinstance(info, dict) else {}
    if not isinstance(summary, dict):
        return {}
    records = {}
    for key, value in summary.items():
        match = re.fullmatch(r"Suite_Name:\s*(.*?)\s*:\s*(.*?)_compliance", key)
        if match:
            requirement, suite = match.groups()
            records[identity(suite)] = {"suite": suite, "requirement": requirement,
                                       "value": str(value)}
    return records


def _record_names(suite):
    names = [suite["canonical"], suite.get("requirement_key", "")]
    if suite["canonical"] in ("FWTS", "SCT"):
        names.extend(prefix + "-" + suite["canonical"] for prefix in ("EBBR", "SBBR"))
    if suite["canonical"] == "OS-TESTS":
        names.extend(("OS_TEST", "OS Tests"))
    return [identity(name) for name in names]


def _counts(raw):
    """Normalize counter names so JSON and chart labels can be compared."""
    aliases = {"totalrulesrun": "total", "totaltests": "total", "total": "total",
               "failedwithwaiver": "failedwithwaiver"}
    result = {}
    summary = raw.get("suite_summary", {})
    if not isinstance(summary, dict):
        return result
    for key, value in summary.items():
        name = identity(key).lower()
        name = aliases.get(name, name[5:] if name.startswith("total") else name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result[name] = value
    return result


def _chart_counts(table):
    result = {}
    for row in table["rows"]:
        if len(row) == 2 and re.fullmatch(r"\d[\d,]*", row[1]):
            name = identity(row[0]).lower()
            result["total" if name in ("totaltests", "totalrulesrun") else name] = int(
                row[1].replace(",", ""))
    return result


def _result_payload(value):
    """Keep result and waiver data, excluding metadata added during merging."""
    enriched = {"Waivable", "SRS scope", "Test_suite_info", "Main Readiness Grouping"}
    if isinstance(value, dict):
        return {key: _result_payload(child) for key, child in value.items() if key not in enriched}
    if isinstance(value, list):
        return [_result_payload(child) for child in value]
    return value


def _json_inventory(values):
    return Counter(json.dumps(_result_payload(value), sort_keys=True, ensure_ascii=True)
                   for value in values)


def _result_entries(data):
    """Do not iterate malformed result collections as if they were test records."""
    value = data.get("test_results", [])
    return value if isinstance(value, list) else None


def _first_difference(expected, actual, path=""):
    """Point to the first changed JSON field without changing either input."""
    if type(expected) is not type(actual):
        return {"path": path or "/", "expected": type(expected).__name__, "actual": type(actual).__name__}
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in expected or key not in actual:
                return {"path": pointer, "expected": "Present" if key in expected else "Absent",
                        "actual": "Present" if key in actual else "Absent"}
            different = _first_difference(expected[key], actual[key], pointer)
            if different:
                return different
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path, "expected": f"{len(expected)} entries", "actual": f"{len(actual)} entries"}
        for index, (left, right) in enumerate(zip(expected, actual)):
            different = _first_difference(left, right, path + "/" + str(index))
            if different:
                return different
    elif expected != actual:
        return {"path": path, "expected": expected, "actual": actual}
    return None


def _merged_parity(root, raw_files, merged, registry, issues):
    """Check that merging preserves each raw result, not just the total counts."""
    by_suite = {suite["canonical"]: suite for suite in registry}
    expected = defaultdict(list)
    merged_path = root / "acs_jsons" / "merged_results.json"
    for canonical, items in raw_files.items():
        suite = by_suite[canonical]
        for path, data in items:
            if suite.get("waiver_suite") == "Standalone":
                destination = "Suite_Name: Standalone"
            elif canonical == "OS-TESTS" and path.name != suite.get("json_output"):
                destination = "Suite_Name: OS Tests - " + path.stem
            else:
                matches = [key for key in merged if key.startswith("Suite_Name: ")
                           and identity(key[len("Suite_Name: "):]) in _record_names(suite)]
                if len(matches) != 1:
                    issues.append({"file": str(merged_path), "issue": "Raw suite has no unique merged section",
                                   "suite": canonical, "expected": str(path), "actual": matches})
                    continue
                destination = matches[0]
            expected[destination].append((path, data))
    for destination, items in expected.items():
        actual = merged.get(destination)
        if destination == "Suite_Name: Standalone":
            # Standalone combines several input files into one list. Compare the
            # records without assuming that their order stays the same.
            collections = [_result_entries(data) for _, data in items]
            if any(entries is None for entries in collections):
                # The input-shape finding is kept by run_reports. This comparison
                # cannot run, but other suites and supplied packages still can.
                continue
            entries = [entry for collection in collections for entry in collection]
            equivalent = isinstance(actual, list) and _json_inventory(
                entries) == _json_inventory(actual)
        else:
            # OS distributions have separate sections; duplicate non-aggregate producers
            # are ambiguous, never silently overwritten by the last filename.
            equivalent = len(items) == 1 and _result_payload(items[0][1]) == _result_payload(actual)
        if not equivalent:
            difference = (_first_difference(_result_payload(items[0][1]), _result_payload(actual))
                          if len(items) == 1 and destination != "Suite_Name: Standalone" else None)
            issues.append({"file": str(merged_path), "issue": "Raw and merged result records differ",
                           "suite": destination, "expected": "Identical identities, nested results, statuses and waiver evidence",
                           "actual": difference or "Missing, extra or changed records; compare raw files " +
                           ", ".join(path.name for path, _ in items)})
    expected_names = set(expected)
    for destination in sorted(set(merged) - {"Suite_Name: acs_info"} - expected_names):
        # Report stale/unregistered result sections even if the suite counters happen to match.
        issues.append({"file": str(merged_path), "issue": "Merged result section has no matching raw input",
                       "suite": destination, "expected": "Every result section is traceable to current raw JSON",
                       "actual": destination})


def _local_links(path, parsed, root, documents, issues, coverage):
    """Check local files and anchors; report links outside the package as unchecked."""
    for anchor, count in sorted(parsed.ids.items()):
        if count > 1:
            issues.append({"file": str(path), "issue": "Duplicate HTML element ID",
                           "expected": "One unique element", "actual": {"id": anchor, "count": count}})
    for link in sorted(set(parsed.links)):
        try:
            target = urlsplit(link)
            if target.scheme or target.netloc:
                continue  # Never fetch remote content or execute a URL.
            destination = (path.parent / unquote(target.path)
                           ).resolve() if target.path else path.resolve()
            if root != destination and root not in destination.parents:
                coverage.append(
                    path.name + ": link outside supplied package not inspected: " + link)
                continue
            if not destination.is_file() or not destination.stat().st_size:
                issues.append({"file": str(path), "issue": "Broken local HTML link",
                               "expected": "A non-empty local file", "actual": link})
                continue
            if target.fragment:
                if destination.suffix.lower() not in (".html", ".htm"):
                    coverage.append(path.name + ": non-HTML fragment not inspected: " + link)
                    continue
                if destination not in documents:
                    documents[destination] = ReportHTML(destination.read_text(encoding="utf-8"))
                document = documents[destination]
                anchor = unquote(target.fragment)
                if document.ids[anchor] != 1 and anchor not in document.anchors:
                    issues.append({"file": str(path), "issue": "Broken local HTML fragment",
                                   "expected": "Exactly one local anchor", "actual": link})
        except (OSError, ValueError, UnicodeError) as error:
            issues.append({"file": str(path), "issue": "Local HTML link could not be inspected",
                           "actual": link + ": " + str(error)})


def _status(value):
    token = identity(value)
    aliases = {"PASS": "PASSED", "FAIL": "FAILED", "WARNING": "WARNINGS",
               "SKIP": "SKIPPED", "ABORT": "ABORTED", "WAIVED": "FAILEDWITHWAIVER",
               "FAILWITHWAIVER": "FAILEDWITHWAIVER", "TESTNOTIMPLEMENTED": "NOTIMPLEMENTED",
               "NOTTESTEDTESTNOTIMPLEMENTED": "NOTIMPLEMENTED",
               "NOTTESTEDPALNOTSUPPORTED": "PALNOTSUPPORTED"}
    if token.startswith("KNOWN") and token.endswith("LIMITATION"):
        return "IGNORED"
    return aliases.get(token, token)


def _display_status(value, renderer):
    if not isinstance(value, dict):
        return _status(value)
    positive = {_status(key) for key, count in value.items()
                if isinstance(count, (int, float)) and not isinstance(count, bool) and count > 0}
    if not positive:
        return "INFO" if renderer.endswith("os_tests/json_to_html.py") else "UNKNOWN"
    order = ["PASSED", "FAILEDWITHWAIVER", "FAILED", "ABORTED", "SKIPPED", "WARNINGS",
             "IGNORED", "PASSEDPARTIAL", "NOTIMPLEMENTED", "PALNOTSUPPORTED", "NOTTESTED"]
    if renderer.endswith("bbr/fwts/json_to_html.py"):
        order[:3] = ["FAILED", "PASSED", "FAILEDWITHWAIVER"]
    elif renderer.endswith(("post_script/json_to_html.py", "os_tests/json_to_html.py")):
        order[:3] = ["PASSED", "FAILED", "FAILEDWITHWAIVER"]
    return next((status for status in order if status in positive), "UNKNOWN")


def _raw_detail_records(value, renderer):
    """Build expected visible rows from raw results without calling the renderer.

    BSA displays parent and child results. Other supported pages display the
    deepest result rows, with a parent used only when it has no result children.
    """
    records = []
    def visit(node, position=None):
        if isinstance(node, list):
            for index, child in enumerate(node, 1):
                visit(child, index)
        elif isinstance(node, dict):
            fields = {identity(key): child for key, child in node.items()}
            result_keys = [key for key in fields if key in ("TESTRESULT", "SUBTESTRESULT")]
            before = len(records)
            for key, child in node.items():
                if identity(key) not in result_keys:
                    visit(child)
            if not result_keys or (len(records) != before and not renderer.endswith("bsa/json_to_html.py")):
                return
            def field(names):
                return next((" ".join(str(fields[name]).split()) for name in names
                             if fields.get(name) not in (None, "")), "")
            identifier = field(("SUBTESTGUID", "SUBTESTNUMBER", "TESTCASENUMBER",
                               "TESTNUMBER", "TESTID", "TESTCASE", "GUID", "ID"))
            if renderer.endswith("bbr/tpm/json_to_html.py"):
                identifier = str(position)
            if not identifier:
                raise ValueError("Result record lacks a stable visible ID: " + ", ".join(node))
            description = field(("SUBTESTDESCRIPTION", "TESTCASEDESCRIPTION",
                                "TESTDESCRIPTION", "DESCRIPTION", "NAME"))
            records.append((identifier, description, _display_status(
                fields[result_keys[0]], renderer)))
    visit(value)
    return Counter(records)


def _html_detail_records(parsed, sct_headings=False):
    """Read displayed IDs, descriptions and statuses, including SCT parent headings."""
    records, tables = [], 0
    populated_tables = set()
    for table in (table for table in parsed.tables if table["kind"] == "detail"):
        columns = None
        for row in table["cells"]:
            if any(cell["tag"] == "th" for cell in row):
                headers = [identity(cell["text"]) for cell in row]
                results = [i for i, name in enumerate(headers) if name in (
                    "TESTRESULT", "SUBTESTRESULT", "RESULT", "STATUS", "OUTCOME")]
                if not results:
                    continue
                ids = [i for i, name in enumerate(headers) if name in ("TESTCASE", "SUBTEST", "TEST", "ID", "GUID", "SUBTESTGUID")
                       or name.endswith("NUMBER") or "#" in row[i]["text"]]
                descriptions = [i for i, name in enumerate(
                    headers) if "DESCRIPTION" in name or name == "NAME"]
                if len(ids) > 1:
                    ids = [i for i in ids if "GUID" in headers[i]]
                if len(results) != 1 or len(ids) != 1 or len(descriptions) != 1:
                    raise ValueError("Ambiguous result table columns: " + ", ".join(headers))
                columns = ids[0], descriptions[0], results[0]
                tables += 1
            elif columns and row:
                if len(row) == 1 and row[0]["nested"]:
                    continue
                if max(columns) >= len(row):
                    raise ValueError("Result row is missing ID, description or status cells")
                records.append((row[columns[0]]["text"], row[columns[1]]
                               ["text"], _status(row[columns[2]]["text"])))
                populated_tables.add(id(table))
    if sct_headings:
        for heading in parsed.detail_headings:
            # SCT renders a parent result in headings, and child outcomes in the
            # following table. Count the parent only when that table has no rows.
            if not any(id(table) in populated_tables for table in heading["tables"]):
                records.append((heading["id"], heading["description"], _status(heading["status"])))
                tables += 1
    return Counter(records), tables


def _detail_parity(path, parsed, raw_files, registry, issues, coverage):
    """Report missing or changed result rows between raw JSON and detailed HTML."""
    suites = [suite for suite in registry if suite.get("detailed_html") == path.name
              and suite["canonical"] in raw_files]
    if path.name == "sbmr_detailed.html":
        suites = [suite for suite in registry if suite["canonical"] in ("SBMR-IB", "SBMR-OOB")
                  and suite["canonical"] in raw_files]
    if not suites:
        return
    try:
        expected = Counter()
        for suite in suites:
            for _, data in raw_files[suite["canonical"]]:
                expected.update(_raw_detail_records(data, suite.get("json_to_html", "")))
        actual, tables = _html_detail_records(parsed, sct_headings=all(
            suite.get("json_to_html", "").endswith("bbr/sct/json_to_html.py") for suite in suites))
        if expected and not tables:
            issues.append({"file": str(path), "issue": "Detailed result rows are missing",
                           "expected": sum(expected.values()), "actual": 0})
        elif expected != actual:
            issues.append({"file": str(path), "issue": "Raw and detailed HTML result identities differ",
                           "expected": {"missing": list((expected - actual).elements())[:10]},
                           "actual": {"extra_or_changed": list((actual - expected).elements())[:10]}})
    except ValueError as error:
        issues.append({"file": str(path), "issue": "Detailed identity comparison could not execute",
                       "blocked": True, "expected": "A supported unambiguous result-row identity contract",
                       "actual": str(error)})


def _raw_integrity(path, data, record, issues, sr_os=False):
    """Check counter totals and flag clear contradictions with suite compliance."""
    counts = _counts(data)
    categories = {"passed", "failed", "failedwithwaiver", "aborted", "skipped",
                  "warnings", "passedpartial", "notimplemented", "palnotsupported", "ignored"}
    summary = data.get("suite_summary", {})
    for name, value in summary.items() if isinstance(summary, dict) else []:
        if (not isinstance(value, (int, float)) or isinstance(value, bool) or
                not math.isfinite(value) or value < 0 or int(value) != value):
            issues.append({"file": str(path), "issue": "Invalid suite counter", "count": name,
                           "expected": "A non-negative whole number", "actual": value})
    if "total" in counts and set(counts) <= categories | {"total"}:
        summed = sum(value for key, value in counts.items() if key != "total")
        if summed != counts["total"]:
            issues.append({"file": str(path), "issue": "Suite categories do not sum to declared total",
                           "expected": counts["total"], "actual": summed})
    def unknown(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in ("test_result", "sub_test_result") and value == "UNKNOWN":
                    return True
                if unknown(value):
                    return True
        elif isinstance(node, list):
            return any(unknown(value) for value in node)
        return False
    if record and decision(record["value"]).startswith("Compliant") and unknown(data):
        issues.append({"file": str(path), "issue": "UNKNOWN result is reported as compliant",
                       "expected": "Unknown execution evidence must not silently become success",
                       "actual": record["value"]})
    if record and decision(record["value"]).startswith("Compliant"):
        if data.get("test_results") == []:
            issues.append({"file": str(path), "issue": "Empty execution evidence is reported as compliant",
                           "actual": record["value"]})
        if counts.get("failed", 0) > 0 and not sr_os:
            issues.append({"file": str(path), "issue": "Unwaived suite failures are reported as compliant",
                           "expected": "Not Compliant at suite level; Recommended may remain non-blocking "
                "overall",
                           "actual": {"failed": counts["failed"], "compliance": record["value"]}})


def _aggregate(records):
    """Calculate the expected combined display badge, not overall SRS compliance."""
    mandatory = [r for r in records if r["requirement"] in (
        "Mandatory", "Conditional-Mandatory")]
    relevant = mandatory or records
    requirements = sorted({r["requirement"] for r in relevant})
    requirement = "Mandatory" if "Mandatory" in requirements else " / ".join(requirements)
    if all("not run" in r["value"].lower() for r in records):
        status = "Not Run"
    elif any(decision(r["value"]) == "Not Compliant" for r in relevant):
        status = "Not Compliant"
    elif any(decision(r["value"]) == "Unknown" for r in relevant):
        status = "Unknown"
    elif any(decision(r["value"]) == "Compliant with waivers" for r in relevant):
        status = "Compliant with waivers"
    else:
        status = "Compliant"
    return requirement + " (" + status + ")"


def _inspect_html(path, parsed, records, raw_by_suite, registry, issues, coverage,
                  overall=None):
    """Compare HTML compliance with merged JSON and chart totals with raw JSON."""
    if path.name == "acs_summary.html" and overall is not None:
        # Compare the displayed SRS decision, not a suite badge or extension's
        # verdict. The report may omit the explanatory suffix after the decision.
        displayed = [row[1] for table in parsed.tables for row in table["rows"]
                     if len(row) >= 2 and identity(row[0]) == "SRSREQUIREMENTSCOMPLIANCERESULTS"]
        if len(displayed) != 1:
            issues.append({"file": str(path), "issue": "Main HTML overall compliance verdict is missing or ambiguous",
                           "expected": decision(overall), "actual": displayed})
        elif decision(displayed[0]) != decision(overall):
            issues.append({"file": str(path), "issue": "Overall HTML compliance differs from merged JSON",
                           "expected": decision(overall), "actual": displayed[0]})
    aliases = {name: record for suite in registry for name in _record_names(suite)
               for key, record in records.items() if key in _record_names(suite)}
    aliases.update(records)
    detail_rows = [row for table in parsed.tables if table["kind"] == "compliance"
                   for row in table["rows"] if len(row) == 3 and row[1] != "Requirement"]
    for name, requirement, status in detail_rows:
        record = aliases.get(identity(name))
        if record is None:
            coverage.append(str(path.name) + ": unmapped compliance row " + name)
        elif (identity(requirement), decision(status), "not run" in status.lower()) != (
                identity(record["requirement"]), decision(record["value"]),
                "not run" in record["value"].lower()):
            issues.append({"file": str(path), "issue": "Detail compliance differs from merged JSON",
                           "suite": name, "expected": record, "actual": [requirement, status]})
    if path.name == "sbmr_detailed.html":
        expected_rows = {key for key in ("SBMRIB", "SBMROOB") if key in records}
    elif path.name == "standalone_tests_detailed.html":
        expected_rows = {name for suite in registry if suite.get("waiver_suite") == "Standalone"
                         for name in _record_names(suite) if name in records and (
                             suite["canonical"] in raw_by_suite or (
                                 records[name]["requirement"] == "Mandatory" and
                                 "not run" in records[name]["value"].lower()))}
    else:
        expected_rows = set()
    present_rows = {identity(row[0]) for row in detail_rows}
    present_rows.update(identity(aliases[name]["suite"])
                        for name in list(present_rows) if name in aliases)
    for missing in sorted(expected_rows - present_rows):
        issues.append({"file": str(path), "issue": "Applicable compliance row is missing",
                       "expected": records[missing], "actual": "No row for " + records[missing]["suite"]})
    if path.name.endswith("_detailed.html") and not detail_rows:
        issues.append({"file": str(path), "issue": "Detailed report has no compliance rows"})
    if path.name == "acs_summary.html" and records and not parsed.badges:
        issues.append({"file": str(path), "issue": "Main report has no suite compliance badges"})
    for badge in parsed.badges:
        names = re.findall(r"(?:^|; )([^:;]+): (?:Mandatory|Recommended|Extension|Conditional-Mandatory)\s*\(",
                           badge["context"])
        rows = [aliases[identity(name)] for name in names if identity(name) in aliases]
        if len(rows) != len(names) or not rows:
            coverage.append(path.name + ": unmapped summary badge " + badge["card"])
        elif badge["text"] != _aggregate(rows):
            issues.append({"file": str(path), "issue": "Summary badge differs from merged JSON",
                           "card": badge["card"], "expected": _aggregate(rows), "actual": badge["text"]})
    for table in (table for table in parsed.tables if table["kind"] == "counts"):
        filename = table["card"] + ".html" if table["card"] else path.name
        suites = [s for s in registry if filename in (s.get("summary_html"), s.get("detailed_html"))
                  and s["canonical"] in raw_by_suite]
        if filename in ("sbmr_summary.html", "sbmr_detailed.html"):
            suites = [s for s in registry if s["canonical"] in ("SBMR-IB", "SBMR-OOB")
                      and s["canonical"] in raw_by_suite]
        if not suites or any(s.get("waiver_suite") == "Standalone" or
                             s["canonical"] == "OS-TESTS" for s in suites):
            coverage.append(path.name + ": aggregate/unmapped chart " + filename)
            continue
        expected = Counter()
        for suite in suites:
            counts = _counts(raw_by_suite[suite["canonical"]])
            # Most producers store status counters only; HTML derives its Total
            # Tests row from those counters rather than a missing JSON total=0.
            categories = {"passed", "failed", "failedwithwaiver", "aborted", "skipped",
                          "warnings", "passedpartial", "notimplemented", "palnotsupported", "ignored"}
            if counts and "total" not in counts and set(counts) <= categories:
                counts["total"] = sum(counts.values())
            # The SBMR renderer has no Ignored row. Its schema includes the
            # unused zero counter; a nonzero value must still be reported.
            if suite["canonical"] in ("SBMR-IB", "SBMR-OOB") and counts.get("ignored") == 0:
                counts.pop("ignored")
            expected.update(counts)
        actual = _chart_counts(table)
        if not actual or not expected:
            coverage.append(path.name + ": no comparable suite-summary counts " + filename)
            continue
        for key in sorted(set(expected) | set(actual)):
            value = expected.get(key, 0)
            if (key in expected and key not in actual) or actual.get(key, 0) != value:
                issues.append({"file": str(path), "issue": "Chart differs from raw suite summary",
                               "chart": filename, "count": key, "expected": value,
                               "actual": actual.get(key, "Missing chart category")})


def run_reports(ctx):
    """Inspect user-supplied reports and save findings in Doctor's output folder."""
    if not ctx.report_inputs:
        ctx.add("ARTIFACT.INPUT", "WARN", "Real-capture artifact checks were not run",
                "Supply --doctor-report DT=/path or SR=/path to a report package",
                "No report input supplied; synthetic probes are separate")
        return
    from validate import _build_file_schema_index, _find_schema_for_file
    from suite_registry import load_registry
    registry = load_registry(ctx.parser_dir / "suite_registry.json")
    exact, patterns = _build_file_schema_index(registry, ctx.parser_dir / "suite_registry.json")
    for index, (mode, supplied) in enumerate(ctx.report_inputs):
        if mode not in ctx.modes:
            continue
        root = Path(supplied).resolve()
        if not (root / "acs_jsons").is_dir() and (root / "acs_summary" / "acs_jsons").is_dir():
            root = root / "acs_summary"
        evidence_dir = ctx.case_dir("artifacts/" + str(index) + "_" + mode)
        issue_file = evidence_dir / "issues.json"
        issues, coverage, raw, merged, json_count = [], [], {}, None, 0
        provenance = category_provenance(root, mode)
        schema_checks = []
        if provenance["invalid"]:
            issues.append({"file": provenance["manifest"], "issue": "Invalid category provenance",
                           "actual": provenance["message"]})
        raw_files = defaultdict(list)
        json_dir = root / "acs_jsons"
        if not json_dir.is_dir():
            ctx.add("ARTIFACT.INPUT", "BLOCKED", "Report JSON directory is missing",
                    "A report package containing acs_jsons/merged_results.json", str(root), mode)
            continue
        for path in sorted(json_dir.glob("*.json")):
            # Even an in-package filename can point outside the package through a
            # symlink. Do not follow those links into unrelated user data.
            if root not in path.resolve().parents:
                issues.append({"file": str(path), "issue": "Report input escapes supplied package",
                               "actual": "External symlink target was not read"})
                continue
            info = _find_schema_for_file(path, exact, patterns)
            is_merged = path.name == "merged_results.json"
            if not info and not is_merged:
                if path.name not in ("acs_info.json", "edk2_test_parser.json"):
                    coverage.append("No registered raw schema for " + path.name)
                continue
            json_count += 1
            schema_path = (ctx.parser_dir / "acs-results-schema.json"
                           if is_merged else info["schema"])
            fragment = "" if is_merged else info["schema_fragment"]
            try:
                data = _strict_json(path)
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object, got " + type(data).__name__)
            except (OSError, ValueError) as error:
                issues.append(
                    {"file": str(path), "issue": "Malformed report JSON", "actual": str(error)})
                continue
            try:
                evaluation = evaluate_schema(schema_path, fragment, data, provenance)
                errors = evaluation["errors"]
                schema_checks.append({"file": str(path), "strict_error_count": evaluation["strict_error_count"],
                                      "applicable_error_count": len(errors),
                                      "omitted_missing_info_paths": evaluation["omitted_missing_info_paths"]})
                if errors:
                    issues.append({"file": str(path), "issue": "JSON schema validation failed",
                                   "schema": str(schema_path) + fragment, "errors": errors})
            except Exception as error:  # A broken schema must not suppress the other supplied checks.
                issues.append({"file": str(path), "issue": "Schema validation could not execute",
                               "actual": str(error)})
            if is_merged:
                merged = data
            else:
                if _result_entries(data) is None:
                    issues.append({"file": str(path), "issue": "Invalid result collection",
                                   "suite": info["canonical"], "expected": "test_results is an array of test records",
                                   "actual": "test_results is " + type(data["test_results"]).__name__})
                raw_files[info["canonical"]].append((path, data))
        # Charts need combined counts, while exact parity retains every input file.
        for canonical, items in raw_files.items():
            if len(items) == 1:
                raw[canonical] = items[0][1]
            else:
                counters = Counter()
                entries = []
                for _, data in items:
                    counters.update(_counts(data))
                    values = _result_entries(data)
                    if values is not None:
                        entries.extend(values)
                raw[canonical] = {"suite_summary": dict(counters), "test_results": entries}
        if merged is None:
            issues.append({"file": str(json_dir / "merged_results.json"),
                           "issue": "Merged JSON is missing or unreadable"})
        if not raw:
            issues.append(
                {"file": str(json_dir), "issue": "No readable registered raw suite JSON found"})
        if merged is not None:
            _merged_parity(root, raw_files, merged, registry, issues)
        records = _records(merged or {})
        info = (merged or {}).get("Suite_Name: acs_info", {})
        results = info.get("ACS Results Summary", {}) if isinstance(info, dict) else {}
        band = str(results.get("Band", "")) if isinstance(results, dict) else ""
        detected_mode = "DT" if "devicetree" in band.lower() else "SR" if band == "SystemReady band" else mode
        if detected_mode != mode:
            issues.append({"file": str(json_dir / "merged_results.json"), "issue": "Supplied mode does not match report band",
                           "expected": mode, "actual": band})
        if not records:
            issues.append({"file": str(json_dir / "merged_results.json"),
                           "issue": "No run-specific compliance decisions found"})
        html_dir = root / "html_detailed_summaries"
        for suite in registry:
            canonical = suite["canonical"]
            if canonical not in raw:
                continue
            record = next((records[name] for name in _record_names(suite) if name in records), None)
            for source, data in raw_files[canonical]:
                _raw_integrity(source, data, record, issues,
                               sr_os=detected_mode == "SR" and canonical == "OS-TESTS")
            detail = suite.get("detailed_html", "")
            if canonical.startswith("SBMR-") and (html_dir / "sbmr_detailed.html").is_file():
                detail = "sbmr_detailed.html"
            if detail and raw[canonical].get("test_results") and not (html_dir / detail).is_file():
                issues.append({"file": str(html_dir / detail), "issue": "Detailed HTML for collected results is missing",
                               "suite": canonical})
            merged_suite = next((value for key, value in (merged or {}).items()
                                 if key.startswith("Suite_Name: ") and
                                 identity(key[len("Suite_Name: "):]) in _record_names(suite)), None)
            if isinstance(merged_suite, dict) and _counts(raw[canonical]) != _counts(merged_suite):
                issues.append({"file": str(source), "issue": "Raw and merged suite counters differ",
                               "suite": canonical, "expected": _counts(raw[canonical]),
                               "actual": _counts(merged_suite)})
        pages = list(sorted(html_dir.glob("*.html")))
        if not (html_dir / "acs_summary.html").is_file():
            issues.append({"file": str(html_dir / "acs_summary.html"),
                          "issue": "Main HTML report is missing"})
        documents = {}
        for path in pages:
            try:
                if root not in path.resolve().parents:
                    issues.append({"file": str(path), "issue": "Report input escapes supplied package",
                                   "actual": "External HTML symlink target was not read"})
                    continue
                parsed = ReportHTML(path.read_text(encoding="utf-8"))
                documents[path.resolve()] = parsed
                _inspect_html(path, parsed, records, raw, registry, issues, coverage,
                              overall=results.get("Overall Compliance Result") if isinstance(results, dict) else None)
                _detail_parity(path, parsed, raw_files, registry, issues, coverage)
                _local_links(path, parsed, root, documents, issues, coverage)
            except (OSError, ValueError, TypeError, AttributeError) as error:
                issues.append(
                    {"file": str(path), "issue": "HTML could not be inspected", "actual": str(error)})
        issue_file.write_text(json.dumps({"source": str(root), "mode": mode,
            "not_checked": ["Browser rendering, PDF output, external URLs and JavaScript-created "
                "anchors",
                            "Standalone component chart totals and multi-file OS aggregate chart "
                "totals"],
            "issues": issues, "coverage_gaps": sorted(set(coverage)),
            "category_provenance": provenance, "schema_policy_checks": schema_checks}, indent=2) + "\n", encoding="utf-8")
        for item in issues:
            # Keep each concrete issue separate. The package-level result below is
            # only a summary and must not be mistaken for another distinct bug.
            if item["issue"] == "JSON schema validation failed":
                first = item["errors"][0]
                ctx.add("ARTIFACT.SCHEMA", "FAIL", Path(item["file"]).name + " violates applicable Doctor schema checks",
                        "Registered schema; missing Test_suite_info is required only for an "
                "explicitly supplied category",
                        f'{first["path"]}: {first["message"][:220]}; {len(item["errors"])} error records in evidence',
                        mode, evidence=[issue_file])
            elif item["issue"] != "Schema validation could not execute":
                category = ("CATEGORY_PROVENANCE" if item["issue"] == "Invalid category provenance" else
                            "JSON" if "JSON" in item["issue"] else "PARITY" if "record" in item["issue"].lower()
                            or "identit" in item["issue"].lower() else "HTML" if "HTML" in item["issue"] else "DATA")
                ctx.add("ARTIFACT." + category, "BLOCKED" if item.get("blocked") else "FAIL",
                        item["issue"] + ": " + Path(item["file"]).name,
                        item.get("expected", "Consistent current-run report artifacts"),
                        item.get("actual", item.get("suite", "See evidence for the discrepancy")),
                        mode, suite=item.get("suite", ""), evidence=[issue_file])
        schema_blocked = [item for item in issues if item["issue"]
            == "Schema validation could not execute"]
        blocked = schema_blocked + [item for item in issues if item.get("blocked")]
        for item in schema_blocked:
            ctx.add("ARTIFACT.SCHEMA", "BLOCKED", "Schema evaluator could not check " + Path(item["file"]).name,
                    "The registered schema loads and validation completes", item["actual"], mode, evidence=[issue_file])
        counts = Counter(issue["issue"] for issue in issues)
        omitted_files = [
            Path(check["file"]).name for check in schema_checks if check["omitted_missing_info_paths"]]
        if provenance["source"] == "unknown" and omitted_files:
            ctx.add("ARTIFACT.CATEGORY_PROVENANCE", "WARN", "Missing Test_suite_info could not be attributed to a supplied category",
                    "Verified generating-run category provenance for this conditional requirement",
                    provenance["message"] + "; missing-info requirement not applied in " +
                        ", ".join(omitted_files)
                    + "; all other schema checks remain active", mode, evidence=[issue_file])
        verdict = "FAIL" if len(issues) > len(blocked) else "BLOCKED" if blocked else "PASS"
        ctx.add("ARTIFACT.CONSISTENCY", verdict,
                "Supplied report package has correctness problems" if issues else "Supplied static report checks agree",
                "Strict JSON, applicable Doctor schema checks, raw/merged identities, "
                "HTML decisions/counts/rows, and local links/anchors",
                f"{json_count} JSON files, {len(pages)} HTML pages; " + (
                    "; ".join(f"{name}: {count}" for name, count in counts.items()) or "no discrepancies"),
                mode, evidence=[issue_file])
        if coverage:
            ctx.add("ARTIFACT.COVERAGE", "WARN", "Some artifact comparisons could not be safely evaluated",
                    "Explicit count units and a registered schema/display mapping",
                    "; ".join(sorted(set(coverage))[:5]) +
                              f"; {len(set(coverage))} coverage notes in evidence",
                    mode, evidence=[issue_file])


# ---------------------------------------------------------------------------
# Optionally check browser controls and PDF content using Doctor's sample reports.
# ---------------------------------------------------------------------------

FWTS_LOG = """Running tests: uefirtmisc
====================
uefirtmisc: Doctor interface checks
Test 1 of 2: Doctor passing interface
PASSED: Test 1, Doctor passed
Test 2 of 2: Doctor failing interface
FAILED [HIGH] Doctor failed
"""
OUTCOMES = {"pass": (2, 0, 0, "Compliant"),
            "fail": (1, 1, 0, "Not Compliant"),
            "waived": (1, 0, 1, "Compliant with waivers")}

# Check what a report reader sees and clicks; do not call private renderer helpers.
BROWSER_ASSERTIONS = r"""<script>
window.addEventListener('load', function () { setTimeout(function () {
  var failures = window.doctorErrors || [], checks = 0;
  function expect(ok, message) { checks++; if (!ok) failures.push(message); }
  try {
    expect(document.body.classList.contains('acs-report-ui'), 'Report UI did not initialize');
    expect(!!document.querySelector('h1,h2'), 'Report has no heading');
    var tables = document.querySelectorAll('table.summary-table');
    expect(tables.length > 0, 'No source summary tables checked');
    tables.forEach(function (table) {
      var chart = table.closest('.acs-compact-summary');
      expect(!!chart, 'Source summary was not converted to a visible chart');
      if (!chart) return;
      var source = Array.from(table.querySelectorAll('tr')).filter(function (row) {
        return row.cells.length >= 2 && !row.querySelector('th') &&
          !/^Total\b/i.test(row.cells[0].textContent.trim());
      }).map(function (row) { return Number(row.cells[row.cells.length - 1].textContent); });
      var visible = Array.from(chart.querySelectorAll('.acs-progress-count')).map(function (node) {
        return Number(node.textContent);
      });
      expect(JSON.stringify(source) === JSON.stringify(visible), 'Visible counts differ from source table');
    });
    if (document.body.getAttribute('data-acs-view') === 'detail') {
      var search = document.querySelector('input[type="search"]');
      var counter = document.querySelector('.acs-filter-count');
      expect(!!search && !!counter, 'Search or result counter missing');
      if (search && counter) {
        var initial = counter.textContent;
        search.value = 'doctor-no-result-79c498f8';
        search.dispatchEvent(new Event('input', {bubbles:true}));
        expect(counter.textContent !== initial && /0/.test(counter.textContent), 'Search did not filter results');
        search.value = ''; search.dispatchEvent(new Event('input', {bubbles:true}));
        expect(counter.textContent === initial, 'Clearing search did not restore results');
        var filter = document.querySelector('.acs-status-filter[aria-pressed="false"]');
        expect(!!filter, 'No status filter checked');
        if (filter) {
          filter.click(); expect(filter.getAttribute('aria-pressed') === 'true', 'Filter did not activate');
          filter.click(); expect(counter.textContent === initial, 'Filter reset did not restore results');
        }
      }
    }
    expect(document.documentElement.scrollWidth <= window.innerWidth + 2, 'Report overflows viewport');
  } catch (error) { failures.push(String(error)); }
  var result = document.createElement('pre'); result.id = 'doctor-browser-result';
  result.textContent = JSON.stringify({checks: checks, failures: failures});
  document.body.appendChild(result);
}, 100); });</script>"""


def browser_result(output):
    """Read the browser's check results; a missing result is not a passing check."""
    match = re.search(r'<pre id="doctor-browser-result">(.*?)</pre>', output, re.DOTALL)
    if not match:
        raise ValueError("Browser exited without running the report assertions")
    data = json.loads(html.unescape(match.group(1)))
    if (not isinstance(data, dict) or type(data.get("checks")) is not int or
            data["checks"] < 4 or not isinstance(data.get("failures"), list)):
        raise ValueError("Incomplete browser assertions: " + str(data))
    return data


def pdf_problems(text, prefix, outcome):
    """Check expected suite names, compliance and counters in extracted PDF text."""
    passed, failed, waived, compliance = OUTCOMES[outcome]
    text = " ".join(text.split())
    issues = []
    if not re.search(r"(?<![\w-])" + prefix + r"-FWTS(?![\w-])", text):
        issues.append("Missing suite identity " + prefix + "-FWTS")
    matches = re.findall(r"SRS requirements compliance results\s+(Not Compliant|Compliant with waivers|Compliant)\b",
                         text, re.IGNORECASE)
    if not matches or any(value.casefold() != compliance.casefold() for value in matches):
        issues.append("Expected overall " + compliance + "; actual " +
                      (str(matches) if matches else "missing"))
    for label, count in (("Total Tests", 2), ("Passed", passed), ("Failed", failed), ("Failed with Waiver", waived)):
        values = re.findall(r"\b" + label + r"\s+(-?\d+)\b", text)
        if not values or any(value != str(count) for value in values):
            issues.append("Expected PDF count %s=%d" % (label, count))
    return issues


class QuietHandler(SimpleHTTPRequestHandler):
    """Serve temporary browser fixtures without logging every HTTP request."""
    def log_message(self, format, *args):
        pass


def check_browser(ctx, browser, page, directory, mode, outcome):
    """Run desktop and mobile checks on an instrumented copy of a sample page."""
    content = page.read_text(encoding="utf-8")
    capture = ('<script>window.doctorErrors=[];window.addEventListener("error",function(e){'
               'window.doctorErrors.push(e.message);});window.addEventListener("unhandledrejection",'
               'function(e){window.doctorErrors.push(String(e.reason));});</script>')
    content = re.sub(r"<head\b[^>]*>", lambda match: match.group(0) +
                     capture, content, count=1, flags=re.I)
    content = re.sub(r"</body>", lambda _: BROWSER_ASSERTIONS +
                     "</body>", content, count=1, flags=re.I)
    (directory / page.name).write_text(content, encoding="utf-8")
    # Use a loopback-only web server so scripts behave as on a normal web page.
    # The original sample page is left unchanged.
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(directory)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def check_size(size):
        name = page.stem + "-" + size.replace(",", "x")
        try:
            completed = ctx.run([browser, "--headless", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking", "--disable-component-update",
                "--disable-extensions", "--disable-default-apps", "--disable-sync", "--no-proxy-server",
                "--no-first-run", "--user-data-dir=" + str(directory / (name + "-profile")),
                "--window-size=" + size, "--virtual-time-budget=2500", "--dump-dom",
                "http://127.0.0.1:%d/%s" % (server.server_port, page.name)], directory, name)
            try:
                result = browser_result(completed.stdout)
                ok = completed.returncode == 0 and not result["failures"]
                actual = dict(result, exit_code=completed.returncode)
            except (ValueError, TypeError) as error:
                ok, actual = False, str(error)
            return size, name, "PASS" if ok else "FAIL", actual
        except (OSError, RuntimeError) as error:
            return size, name, "BLOCKED", str(error)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for size, name, status, actual in pool.map(check_size, ("1600,900", "430,900")):
                ctx.add("VISUAL_BROWSER", status,
                        outcome + " " + page.name + " at " + size + ": UI, visible counts, filters and overflow",
                        "All browser assertions execute and pass", actual, mode, "FWTS",
                        (directory / (name + ".log"),))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def run_visual(ctx):
    """Generate selected sample reports, then check browser and PDF output.

    Missing optional tools produce BLOCKED findings, not an implied pass.
    """
    directory = ctx.case_dir("visual")
    parser = getattr(ctx, "portable_parser", None)
    if not parser:
        ctx.add("VISUAL_PACKAGE", "BLOCKED", "Visual probes require the verified standalone package",
                "Package checks completed", "No verified extracted parser")
        return
    browser = getattr(ctx, "browser", None) or shutil.which(
        "chromium") or shutil.which("chromium-browser")
    if not browser or not Path(browser).is_file():
        ctx.add("VISUAL_BROWSER_DEPENDENCY", "BLOCKED", "Requested browser checks cannot run",
                "Chromium on PATH or --doctor-browser /absolute/path", "Chromium executable unavailable")
        browser = None
    probe = ctx.run([ctx.python, "-B", "-c", "import weasyprint; import pypdf"],
                    directory, "pdf-dependencies")
    pdf_ready = probe.returncode == 0
    if not pdf_ready:
        ctx.add("VISUAL_PDF_DEPENDENCY", "BLOCKED", "Requested PDF checks cannot run",
                "weasyprint and pypdf import in the recorded Python environment",
                "Install optional PDF dependencies separately; see pdf-dependencies.log", evidence=(directory,))
    if not browser and not pdf_ready:
        return
    for mode in ctx.modes:
        for outcome in OUTCOMES:
            case = ctx.case_dir("visual/" + mode + "_" + outcome)
            source, category = case / "fwts.log", case / "category.json"
            source.write_text(FWTS_LOG.replace("FAILED [HIGH] Doctor failed", "PASSED: Test 2, Doctor passed")
                              if outcome == "pass" else FWTS_LOG, encoding="utf-8")
            category.write_text(json.dumps({"doctor": [{"Suite": "FWTS", "Test Suite": "uefirtmisc",
                "Waivable": "yes", "SRS scope": "core", "Main Readiness Grouping": "Doctor",
                "Description": ["Doctor synthetic FWTS interface checks"]}]}), encoding="utf-8")
            output = case / "output"
            command = ["bash", parser / "main_log_parser.sh", "--standalone", "--mode", mode,
                "--suite", "FWTS", "--input-log", source, "--output", output,
                "--outputs", "pdf" if pdf_ready else "summary", "--schema", "--test-category", category]
            if outcome == "waived":
                waiver = case / "waiver.json"
                waiver.write_text(json.dumps(
                    {"Suites": [{"Suite": "FWTS", "Reason": "Doctor approved waiver"}]}), encoding="utf-8")
                command.extend(["--waiver", waiver])
            try:
                generated = ctx.run(command, case, "generate", cwd=case, env={"PYTHONPATH": ""})
                ctx.add("VISUAL_GENERATION", "PASS" if generated.returncode == 0 else "FAIL",
                        outcome + ": public standalone report export", "Exit 0",
                        "Exit " + str(generated.returncode), mode, "FWTS", (case / "generate.log",))
                if generated.returncode:
                    ctx.add("VISUAL_DEPENDENT_CHECKS", "BLOCKED",
                            outcome + ": browser/PDF assertions could not run because report generation "
                "failed",
                            "Inspect successfully generated reports", "Fix the generation error, then rerun",
                            mode, "FWTS", (case / "generate.log",))
                    continue
                if pdf_ready:
                    pdf = output / "acs_summary.pdf"
                    text_file = case / "pdf-text.txt"
                    script = ("import sys; from pathlib import Path; from pypdf import PdfReader; "
                              "p=Path(sys.argv[1]); assert p.stat().st_size>1000 and "
                "p.read_bytes().startswith(b'%PDF-'); "
                              "r=PdfReader(p,strict=True); assert not r.is_encrypted and "
                "len(r.pages)>0; "
                              "Path(sys.argv[2]).write_text('\\n'.join(x.extract_text() or '' for x "
                "in r.pages),encoding='utf-8')")
                    extracted = ctx.run([ctx.python, "-B", "-c", script,
                                        pdf, text_file], case, "pdf-read")
                    problems = pdf_problems(text_file.read_text(encoding="utf-8"),
                                            "EBBR" if mode == "DT" else "SBBR", outcome) if extracted.returncode == 0 else ["PDF missing or unreadable"]
                    ctx.add("VISUAL_PDF", "FAIL" if problems else "PASS", outcome + ": PDF preserves identity, compliance and counts",
                            OUTCOMES[outcome], problems or "Readable PDF; all expected fields retained", mode, "FWTS",
                            (pdf, text_file, case / "pdf-read.log"))
                if browser:
                    reports = output / "html_detailed_summaries"
                    pages = [reports / "acs_summary.html", reports / "fwts_detailed.html"]
                    browser_dir = case / "browser"
                    # Add browser assertions only to this disposable copy.
                    if reports.is_dir():
                        shutil.copytree(reports, browser_dir)
                    for page in pages:
                        if page.is_file():
                            check_browser(ctx, browser, page, browser_dir, mode, outcome)
                        else:
                            ctx.add("VISUAL_BROWSER_INPUT", "FAIL", "Expected browser input report missing",
                                    str(page), "Not generated", mode, "FWTS", (case / "generate.log",))
            except (OSError, ValueError, RuntimeError) as error:
                ctx.add("VISUAL_EXECUTION", "BLOCKED", outcome + ": visual probe could not complete",
                        "Browser/PDF checks execute", str(error), mode, "FWTS", (case,))
    ctx.add("VISUAL_SCOPE", "WARN", "Rendering smoke checks are not full print or hardware certification",
            "Separate pagination, other suites, paper sizes and supported-browser testing",
            "Synthetic DT/SR FWTS pass/fail/waiver exports; Chromium desktop/mobile only")


if __name__ == "__main__":
    raise SystemExit(schema_policy_main())
