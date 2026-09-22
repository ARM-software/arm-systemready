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

"""Check the parser with small known logs, broken logs, waivers and reruns.

These optional Doctor checks run the real parser commands and compare the raw
JSON, merged compliance and HTML with expected answers written separately. All
sample logs and generated reports stay in Doctor's evidence folder. Real user
logs and parser source files are never changed. Findings include the commands
and output files needed to reproduce a problem.
"""

import ast
from collections import Counter
from copy import copy
from concurrent.futures import ThreadPoolExecutor
import fnmatch
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from xml.etree import ElementTree

from .core import load_json


# The native group uses known complete logs to check each standalone parser route.
# Fixtures originate in CI b6a8a78d1fef3d6e41d2d2aec94006e0a9263c8c.
# It checks raw JSON before merging, so a broken merger cannot hide good parsing.

DATA_FILE = Path(__file__).with_name("data") / "native_cases.json"
RESULT_FIELDS = {"Test_result", "sub_test_result"}
IDENTITY_FIELDS = {"Test_case", "sub_Test_Number", "sub_Test_GUID"}
DESCRIPTION_FIELDS = {"Test_case_description", "sub_Test_Description"}
KNOWN_STATUSES = {"PASS", "PASSED", "FAIL", "FAILED", "SKIP", "SKIPPED",
                  "ABORT", "ABORTED", "WARNING", "WARNINGS", "WAIVED",
                  "FAILED_WITH_WAIVER", "PASSED (PARTIAL)", "PASSED_PARTIAL",
                  "NOT IMPLEMENTED", "NOT_IMPLEMENTED", "PAL NOT SUPPORTED",
                  "PAL_NOT_SUPPORTED", "IGNORED"}


def result_paths(value, path=()):
    """Find parent and child results; matching totals alone can hide lost tests."""
    if isinstance(value, dict):
        if RESULT_FIELDS.intersection(value):
            yield path
        for key, child in value.items():
            yield from result_paths(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from result_paths(child, (*path, index))


def _path(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(part, str) or type(part) is int and part >= 0 for part in value)


def _relative(value):
    return isinstance(value, str) and value and not Path(value).is_absolute() and (
        ".." not in Path(value).parts) and bool(Path(value).parts) and "\\" not in value


def _get(data, path):
    for part in path:
        data = data[part]
    return data


def _exact(actual, expected):
    """Match values and types, so True cannot count as the expected number 1."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _exact(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _exact(left, right) for left, right in zip(actual, expected))
    return actual == expected


def contract_issues(data):
    """Check that sample logs have clear expected results and safe file paths."""
    issues = []
    if not isinstance(data, dict) or data.get("format_version") != 1:
        return ["Expected native fixture format_version 1"]
    cases = data.get("scenarios")
    if not isinstance(cases, list) or not cases:
        return ["At least one meaningful native scenario is required"]
    names = set()
    for index, case in enumerate(cases):
        label = "scenario " + str(index)
        if not isinstance(case, dict):
            issues.append(label + " must be an object")
            continue
        name = case.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]+", name):
            issues.append(label + " has an invalid name")
        elif name in names:
            issues.append("Duplicate scenario name: " + name)
        else:
            names.add(name)
            label = name
        if not isinstance(case.get("mode"), str) or case["mode"] not in {"DT", "SR"}:
            issues.append(label + ": mode must be DT or SR")
        suites = case.get("suites")
        if not isinstance(suites, list) or not suites or not all(
                isinstance(suite, str) and suite for suite in suites):
            issues.append(label + ": non-empty suites list is required")
        elif len(suites) != len(set(suites)):
            issues.append(label + ": duplicate selected suite")
        files = case.get("files")
        if not isinstance(files, dict) or not files:
            issues.append(label + ": non-empty native input files are required")
        elif any(not _relative(name) or not isinstance(content, str) or not content.strip()
                 for name, content in files.items()):
            issues.append(label + ": unsafe input path or empty/non-text native input")
        outputs = case.get("raw")
        if not isinstance(outputs, dict) or not outputs:
            issues.append(label + ": expected raw output files are required")
            continue
        for filename, expectation in outputs.items():
            where = label + ": " + filename
            if not _relative(filename) or Path(filename).name != filename or not filename.endswith(".json"):
                issues.append(where + ": raw output must be a JSON basename")
            if not isinstance(expectation, dict):
                issues.append(where + ": expectation must be an object")
                continue
            assertions, records = expectation.get("assertions"), expectation.get("records")
            if not isinstance(assertions, list) or not assertions:
                issues.append(where + ": independent count assertions are required")
            else:
                for assertion in assertions:
                    if not isinstance(assertion, dict) or not _path(assertion.get("path")) or "value" not in assertion:
                        issues.append(where + ": invalid count/metadata assertion")
            if not isinstance(records, list) or not records:
                issues.append(where + ": non-empty exact record inventory is required")
                continue
            seen = set()
            for record in records:
                if not isinstance(record, dict) or not _path(record.get("path")):
                    issues.append(where + ": invalid record path")
                    continue
                path = tuple(record["path"])
                if path in seen:
                    issues.append(where + ": duplicate expected record path " + str(path))
                seen.add(path)
                fields = record.get("fields")
                if not isinstance(fields, dict) or not all(group.intersection(fields) for group in (
                        RESULT_FIELDS, IDENTITY_FIELDS, DESCRIPTION_FIELDS)):
                    issues.append(where + ": each record needs identity, description and result fields")
                    continue
                for key in RESULT_FIELDS.intersection(fields):
                    value = fields[key]
                    if isinstance(value, str):
                        valid = value in KNOWN_STATUSES
                    elif isinstance(value, dict):
                        valid = bool(value) and all(status in KNOWN_STATUSES and type(count) is int
                                                   and count >= 0 for status, count in value.items())
                    else:
                        valid = False
                    if not valid:
                        issues.append(where + ": invalid expected result status or counter")
    return issues


def expected_outputs(case, suite):
    patterns = [suite.get("json_output", ""), *suite.get("json_output_patterns", [])]
    return {name: value for name, value in case["raw"].items()
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns if pattern)}


def coverage_issues(registry, cases):
    """List parser routes that lack a sample log or target an unsupported mode."""
    by_name = {suite["canonical"]: suite for suite in registry["suites"]}
    executable = set(registry["standalone"]["suite_execution"])
    issues = []
    for name in sorted(executable - by_name.keys()):
        issues.append("Execution route has no registered suite: " + name)
    required = {(name, mode) for name in executable if name in by_name
                for mode in by_name[name].get("modes", [])}
    covered = {(name, case["mode"]) for case in cases for name in case["suites"]}
    if not required:
        issues.append("No executable suite/mode routes are registered")
    for name, mode in sorted(required - covered):
        issues.append("Missing independent native fixture: " + mode + "/" + name)
    for name, mode in sorted(covered - required):
        issues.append("Fixture targets an unknown/unsupported route: " + mode + "/" + name)
    for case in cases:
        matched = set()
        for name in case["suites"]:
            suite = by_name.get(name)
            if not suite:
                continue
            outputs = expected_outputs(case, suite)
            matched.update(outputs)
            if not outputs:
                issues.append(case["name"] + "/" + name + ": no independently expected raw output")
            if not suite.get("schema"):
                issues.append(name + ": no raw schema registered")
        for filename in sorted(case["raw"].keys() - matched):
            issues.append(case["name"] + ": expected output has no selected suite: " + filename)
    for suite in registry["suites"]:
        if suite.get("logs_to_json") and suite["canonical"] not in executable:
            issues.append(suite["canonical"] + ": parser has no standalone execution route")
    return issues


def raw_issues(data, expectation):
    """Compare every expected test, description, status and count with raw JSON."""
    issues = []
    actual_paths = set(result_paths(data))
    expected_paths = {tuple(record["path"]) for record in expectation["records"]}
    missing, extra = expected_paths - actual_paths, actual_paths - expected_paths
    if missing or extra:
        issues.append("Result inventory differs: missing=" + repr(sorted(missing, key=repr))
                      + "; extra=" + repr(sorted(extra, key=repr)))
    for assertion in expectation["assertions"]:
        try:
            actual = _get(data, assertion["path"])
        except (KeyError, IndexError, TypeError):
            issues.append("Missing assertion path " + repr(assertion["path"]))
            continue
        if not _exact(actual, assertion["value"]):
            issues.append(repr(assertion["path"]) + ": expected " + repr(assertion["value"])
                          + ", actual " + repr(actual))
    for record in expectation["records"]:
        try:
            actual = _get(data, record["path"])
        except (KeyError, IndexError, TypeError):
            continue
        for field, expected in record["fields"].items():
            label = repr(record["path"]) + "." + field
            if not isinstance(actual, dict) or field not in actual:
                issues.append(label + ": missing field")
                continue
            value = actual[field]
            if isinstance(expected, dict) and isinstance(value, dict):
                additional = {key: count for key, count in value.items() if key not in expected
                              and isinstance(count, (int, float)) and count != 0}
                if additional:
                    issues.append(label + ": unexpected nonzero result counters " + repr(additional))
                value = {key: value[key] for key in expected if key in value}
            if not _exact(value, expected):
                issues.append(label + ": expected " + repr(expected) + ", actual " + repr(value))
    return issues


def command_diagnostic(completed):
    """Include actionable issue/path text in the report, not just a log link."""
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", completed.stdout or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    useful = [line for line in lines if any(marker in line for marker in (
        "issue=", "*at=", "ERROR:", "Error:", "Missing required Python package", "Exception:"))]
    chosen = useful[:16] if useful else lines[-8:]
    return "Exit " + str(completed.returncode) + ("\n" + "\n".join(chosen) if chosen else "")


def _completed_schema_failure(completed, raw_path, suite):
    """Distinguish a completed schema check from a crash or unrelated error."""
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", completed.stdout or "")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    tags = re.findall(r"(?m)^\*suite=.*?\bissue=([A-Z_]+):", output)
    schema_tags = {"MISSING_KEY", "UNEXPECTED_KEY", "DISALLOWED_VALUE", "TYPE_MISMATCH", "ENUM", "VALIDATION"}
    fatal = re.search(r"(?m)^(?:Traceback\b|ERROR:|Error:|(?:\w+Error|Exception):)", output)
    return bool(lines and lines[-1] == "Schema validation result: FAIL (1 failed, 0 passed, 0 skipped)"
                and "--- Files Checked ---" in lines and suite + ": " + str(raw_path) in lines
                and tags and set(tags) <= schema_tags and not fatal)


def _check_raw_schema(ctx, directory, output, raw_path, mode, name):
    """Keep strict schema evidence and apply Doctor's supplied-category rule."""
    filename = raw_path.name
    stem = filename[:-5]
    validation = ctx.run([ctx.python, "-B", ctx.parser_dir / "validate.py", "raw",
                          "--registry", ctx.parser_dir / "suite_registry.json", raw_path],
                         directory, "schema-" + stem, cwd=directory,
                         env={"PYTHONPATH": "", "PYTHONNOUSERSITE": "1"})
    evidence = [raw_path, directory / ("schema-" + stem + ".log")]
    if validation.returncode not in (0, 1) or (
            validation.returncode == 1 and not _completed_schema_failure(validation, raw_path, name)):
        status = "BLOCKED" if "Missing required Python package" in validation.stdout else "FAIL"
        ctx.add("NATIVE_RAW_SCHEMA", status, "Strict raw schema validator did not complete normally: " + filename,
                "Completed strict validation before Doctor applicability is evaluated",
                command_diagnostic(validation), mode, name, evidence)
        return
    # Missing Test_suite_info is required only when the run supplied a category
    # file. Keep all other schema errors and the original validator log visible.
    policy = ctx.run([ctx.python, "-B", "-m", "doctor_checks.artifacts", "--schema-policy",
                      "--registry", ctx.parser_dir / "suite_registry.json", "--report", output,
                      "--mode", mode, raw_path], directory, "schema-policy-" + stem, cwd=ctx.parser_dir,
                     env={"PYTHONPATH": "", "PYTHONNOUSERSITE": "1"})
    evidence.append(directory / ("schema-policy-" + stem + ".log"))
    if policy.returncode:
        ctx.add("NATIVE_RAW_SCHEMA", "BLOCKED", "Doctor schema applicability could not be evaluated: " + filename,
                "Completed policy evaluation without modifying the strict schema or raw JSON",
                "Strict validator exit " + str(validation.returncode) + "; " + command_diagnostic(policy),
                mode, name, evidence)
        return
    result = json.loads(policy.stdout)
    provenance = result["category_provenance"]
    errors = result["errors"]
    omitted = result["omitted_missing_info_paths"]
    if provenance["invalid"]:
        ctx.add("NATIVE_CATEGORY_PROVENANCE", "FAIL", "Generated category provenance is invalid",
                "Run mode and explicit category snapshot/hash are verifiable", provenance["message"],
                mode, name, evidence)
    elif provenance["source"] == "unknown" and omitted:
        ctx.add("NATIVE_CATEGORY_PROVENANCE", "WARN", "Missing Test_suite_info has unknown category provenance",
                "Verified generating-run category choice", provenance["message"]
                + "; only the missing-info requirement was not applied", mode, name, evidence)
    disagreement = bool(result["strict_error_count"]) != bool(validation.returncode)
    actual = "Strict validator exit " + str(validation.returncode) + "; category source: " + provenance["source"]
    if omitted:
        actual += "; missing Test_suite_info not required at " + str(len(omitted)) + " record(s)"
    if disagreement:
        actual += "; strict CLI and policy evaluator disagree about original schema validity"
    elif errors:
        actual += "\n" + "\n".join(error["path"] + ": " + error["message"] for error in errors[:16])
    else:
        actual += "; all applicable Doctor schema checks passed"
    ctx.add("NATIVE_RAW_SCHEMA", "FAIL" if errors or disagreement else "PASS",
            "Generated raw file must satisfy applicable Doctor schema checks: " + filename,
            "Registered schema; missing Test_suite_info is required only for an explicitly supplied category",
            actual, mode, name, evidence)


def _run_route(ctx, case, name, suite):
    """Run one known log through the public CLI and check its raw output files."""
    mode = case["mode"]
    directory = ctx.case_dir("native/" + mode + "/" + name + "/" + case["name"])
    inputs = directory / "input"
    for relative, content in case["files"].items():
        path = inputs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (inputs / "results").mkdir(parents=True, exist_ok=True)
    output = directory / "output"
    command = ["bash", ctx.parser_dir / "main_log_parser.sh", "--standalone", "--mode", mode,
               "--suite", name, "--input-log", inputs / "results", "--output", output,
               "--outputs", "json"]
    try:
        completed = ctx.run(command, directory, "parser", cwd=directory,
                            env={"PYTHONPATH": "", "PYTHONNOUSERSITE": "1"})
    except (OSError, RuntimeError) as error:
        ctx.add("NATIVE_EXECUTION", "BLOCKED", "Public standalone native fixture did not finish",
                "Successful JSON-only generation; raw checks then run independently", str(error),
                mode, name, [directory])
        return
    status = "PASS" if completed.returncode == 0 else (
        "BLOCKED" if completed.returncode == 3 else "FAIL")
    ctx.add("NATIVE_EXECUTION", status, "Public CLI must parse the known native fixture",
            "Exit 0", case["name"] + "; " + ("Exit 0" if completed.returncode == 0
                                               else command_diagnostic(completed)),
            mode, name, [directory / "parser.log", directory / "parser.command.json"])
    expected = expected_outputs(case, suite)
    json_dir = output / "acs_jsons"
    if json_dir.is_dir():
        ctx.native_outputs.append((mode, output))
    generated = {path.name for path in json_dir.glob("*.json")}
    auxiliary = set(case.get("auxiliary", []))
    missing = set(expected) - generated
    extra = generated - set(expected) - auxiliary
    ctx.add("NATIVE_OUTPUT_INVENTORY", "FAIL" if missing or extra or not expected else "PASS",
            "Native route must produce exactly its expected suite JSON files",
            ", ".join(sorted(expected)), "missing=" + repr(sorted(missing))
            + "; unexpected=" + repr(sorted(extra)), mode, name, [directory])
    for filename, expectation in expected.items():
        raw_path = json_dir / filename
        if not raw_path.is_file():
            ctx.add("NATIVE_RAW_IDENTITY", "BLOCKED", "Raw identity check has no input: " + filename,
                    "Generated raw JSON with exact fixture record inventory", "File was not generated",
                    mode, name, [directory / "parser.log"])
            continue
        try:
            issues = raw_issues(load_json(raw_path), expectation)
            ctx.add("NATIVE_RAW_IDENTITY", "FAIL" if issues else "PASS",
                    "Raw test identities, nested paths and statuses must match the native log: " + filename,
                    str(len(expectation["records"])) + " exact records and independent count assertions",
                    "\n".join(issues) or "Every expected record and assertion matches",
                    mode, name, [raw_path, DATA_FILE])
        except (OSError, ValueError, TypeError, KeyError) as error:
            ctx.add("NATIVE_RAW_IDENTITY", "FAIL", "Raw JSON cannot be checked: " + filename,
                    "Strict JSON with independent fixture identities", str(error), mode, name, [raw_path])
        try:
            _check_raw_schema(ctx, directory, output, raw_path, mode, name)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
            ctx.add("NATIVE_RAW_SCHEMA", "BLOCKED", "Native raw schema check did not finish: " + filename,
                    "Completed raw validation", str(error), mode, name, [directory])


def run_native(ctx):
    """Run known logs for the requested modes and report any missing coverage."""
    ctx.native_outputs = []
    portable = getattr(ctx, "portable_parser", None)
    if getattr(ctx, "package_checked", False) and portable is None:
        ctx.add("NATIVE_PACKAGE_PREREQUISITE", "BLOCKED",
                "Native routes require the verified standalone package",
                "Successful extraction and verification in the package group",
                "No verified portable parser is available; source-tree fallback was not used")
        return
    if portable is not None:
        # A shallow copy changes only this group's parser path. Findings still
        # go to the same Doctor report, but checks use the extracted package.
        ctx = copy(ctx)
        ctx.parser_dir = Path(portable).resolve()
    try:
        data = load_json(DATA_FILE)
        problems = contract_issues(data)
    except (OSError, ValueError, TypeError) as error:
        problems = [str(error)]
    ctx.add("NATIVE_FIXTURE_CONTRACT", "FAIL" if problems else "PASS",
            "Native fixtures must be independent, meaningful and safe to generate",
            "Non-empty exact identities and native inputs; no ambiguous paths or statuses",
            "\n".join(problems) or "Fixture contracts are well-formed", evidence=[DATA_FILE])
    if problems:
        return
    try:
        registry = load_json(ctx.parser_dir / "suite_registry.json")
        cases = data["scenarios"]
        issues = coverage_issues(registry, cases)
        by_name = {suite["canonical"]: suite for suite in registry["suites"]}
    except (OSError, ValueError, TypeError, KeyError) as error:
        ctx.add("NATIVE_ROUTE_COVERAGE", "FAIL", "Native coverage cannot be mapped to the registry",
                "Every executable suite/mode has an independent native fixture", str(error))
        return
    routes = {(name, case["mode"]) for case in cases for name in case["suites"]}
    ctx.add("NATIVE_ROUTE_COVERAGE", "FAIL" if issues else "PASS",
            "Every executable suite and supported mode must have a meaningful native fixture",
            "No uncovered or unknown routes; new suites require explicit fixture onboarding",
            "\n".join(issues) or str(len(routes)) + " independently covered suite/mode routes",
            evidence=[DATA_FILE, ctx.parser_dir / "suite_registry.json"])
    executed = Counter()
    for case in cases:
        if case["mode"] not in ctx.modes:
            continue
        for name in case["suites"]:
            suite = by_name.get(name)
            if not suite or name not in registry["standalone"]["suite_execution"] or (
                    case["mode"] not in suite.get("modes", [])):
                continue
            try:
                _run_route(ctx, case, name, suite)
            except (OSError, ValueError, TypeError, KeyError) as error:
                ctx.add("NATIVE_EXECUTION", "BLOCKED", "Native fixture route could not be checked",
                        "Completed public CLI and raw identity checks", str(error), case["mode"], name)
            executed[case["mode"]] += 1
    for mode in ctx.modes:
        count = executed[mode]
        ctx.add("NATIVE_MODE_EXECUTION", "PASS" if count else "BLOCKED",
                "Selected mode must execute native fixture routes", "At least one route attempted",
                str(count) + " routes attempted; consult individual verdicts for results", mode=mode)


# The raw group checks bad logs, waiver behaviour and old results left by reruns.

def html_capability(ctx):
    """Skip table checks only if unsupported; a broken renderer is still a bug."""
    from .merge import HTML_HELPERS

    source = ctx.parser_dir / "generate_acs_summary.py"
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        functions = {node.name for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        missing = sorted(set(HTML_HELPERS) - functions)
        if not missing:
            return True
        reason = "This checkout does not define " + ", ".join(missing)
    except (OSError, SyntaxError) as error:
        reason = type(error).__name__ + ": " + str(error)
    ctx.add("raw.html-capability", "BLOCKED",
            "Detailed compliance HTML checks are unavailable; native raw/merged JSON checks still run.",
            "Detail compliance generation in this checkout", reason, evidence=(source,))
    return False

class ReportTables(HTMLParser):
    """Read source table cells without requiring a browser or BeautifulSoup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.stack = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            table = {"class": dict(attrs).get("class", ""), "rows": []}
            self.tables.append(table)
            self.stack.append(table)
        elif tag == "tr" and self.stack:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.stack:
            self.stack[-1]["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.stack:
            self.stack.pop()


def green(value):
    """Do not confuse 'Not Compliant' with 'Compliant'."""
    return str(value).strip().lower().startswith("compliant")


def counts(raw):
    summary = raw.get("suite_summary", {}) if isinstance(raw, dict) else {}
    return {name: summary.get("total_" + name,
                              summary.get("Total_failed_with_waiver" if name == "failed_with_waiver"
                                          else name.title(), 0))
            for name in ("passed", "failed", "failed_with_waiver", "aborted",
                         "skipped", "warnings", "ignored")}


def label_for(suite, mode):
    return (("EBBR-" if mode == "DT" else "SBBR-") + suite
            if suite in ("SCT", "FWTS") else suite)


def suite_status(merged, suite, mode, registry):
    summary = merged.get("Suite_Name: acs_info", {}).get("ACS Results Summary", {})
    labels = {label_for(suite, mode), registry[suite]["requirement_key"]}
    # DT publishes one OS result per distribution, not a single os_test.json.
    # Keep the least successful decision so a passing neighbour cannot hide it.
    if suite == "OS-TESTS" and mode == "DT":
        statuses = [value for key, value in summary.items()
                    if key.endswith("_compliance") and "  : OS_" in key]
        if statuses:
            return next((value for value in statuses if not green(value)), "Compliant")
    for key, value in summary.items():
        if any(key.endswith("  : " + label + "_compliance") for label in labels):
            return value
    return None


def bsa_log(suite="BSA", status="PASSED"):
    prefix = "B" if suite == "BSA" else "S"
    return (f" {suite} Architecture Compliance Suite\n          Version 1.2.1\n\n"
            "    *** Running PE tests ***\n\n"
            f"{prefix}_PE_01 : 1 : Check Arch symmetry across PE\n"
            f"   Result:  {status}\n\n"
            "-------------------- Suite run complete --------------------\n"
            "---------- ACS Summary ----------\n   Total Rules Run        : 1\n"
            f"   Passed                 : {int(status == 'PASSED')}\n"
            f"   Failed                 : {int(status == 'FAILED')}\n"
            "   Skipped                : 0\n---------------------------------\n"
            f"      *** {suite} tests complete. Reset the system. ***\n")


def fwts_log(suite="FWTS", failed=0):
    group = "smccc" if suite == "FWTS" else "uefirtauthvar"
    lines = (f"Results generated by fwts: Version V26.01.00.\nRunning tests: {group}\n"
             + "-" * 80 + f"\n{group}: Synthetic doctor check.\n" + "-" * 80
             + "\nTest 1 of 1: Synthetic doctor check.\n")
    for index in range(failed or 1):
        lines += (f"{'FAILED' if failed else 'PASSED'}: Test 1, "
                  f"synthetic doctor assertion {index + 1}.\n")
    return (lines + "\n" + "=" * 80 + f"\n{int(not failed)} passed, {failed} failed, "
            "0 warning, 0 aborted, 0 skipped, 0 info only.\n" + "=" * 80 + "\n")


def sct_log(suite="SCT", failed=False, parent_only=False):
    names = (["CalculateCrc32_Func", "GetVariable_Func"] if suite == "SCT"
             else ["GetVariable_Func", "SetVariable_Func"])
    status = "FAIL" if failed else "PASS"
    result = ""
    for index, name in enumerate(names, 1):
        guid = f"00000000-0000-4000-8000-{index:012d}"
        result += (f"BBR ACS 2.1.1 (SBBR)\n{name}\nRevision 0x00010001\n"
                   f"Test Entry Point GUID: {guid}\nTest Configuration #0\n"
                   "Synthetic doctor check\nTest Started: 09/17/26 05:55a\n")
        if not parent_only:
            result += (f"Synthetic check {index} -- {status}\n{guid}\n"
                       f"/synthetic/Test.c:{index}:synthetic doctor result\n")
        result += f"\nReturned Status Code: 0x00000000\n{name}: [{status}]\n"
    return result


def robot_log(status="PASS"):
    terminal = f'<status status="{status}"/>' if status else ""
    return ('<robot><suite name="SBMR-ACS IB"><suite name="Host">'
            f'<test name="Synthetic doctor check">{terminal}</test>'
            '</suite></suite></robot>')


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def config_files(folder, mode):
    """Create enough synthetic run information for a DT or SR summary report."""
    suffix = "_dt" if mode == "DT" else ""
    acs = folder / ("acs_config" + suffix + ".txt")
    system = folder / ("system_config" + suffix + ".txt")
    band = "SystemReady Devicetree band" if mode == "DT" else "SystemReady band"
    write_text(acs, "ACS version: Synthetic doctor\nSRS version: SRS 3.1.1\n"
               "BSA version: BSA v1.2\nSBSA version: SBSA v8.0\n"
               "SBBR version: BBR v2.1\nEBBR version: EBBR v2.2.0\n"
               "BBSR version: BBSR v1.3\nSBMR version: SBMR v2.1\n"
               "Device Tree Version: v0.4\nBand: " + band + "\n")
    write_text(system, "FW source code: Synthetic doctor fixture\n")
    return acs, system


def invoke(ctx, registry, mode, suite, name, files, waiver=None):
    """Create an isolated sample, run the parser and collect its report evidence."""
    folder = ctx.case_dir("raw/" + mode + "/" + suite + "/" + name)
    inputs = folder / "input" / "acs_results"
    inputs.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        target = (inputs / relative).resolve()
        if folder.resolve() not in target.parents:
            raise ValueError("Synthetic input escaped its evidence directory")
        write_text(target, content)
    acs, system = config_files(folder, mode)
    output = folder / "output"
    command = [ctx.python, "-B", ctx.parser_dir / "standalone_runner.py",
               "--mode", mode, "--input-log", inputs, "--suite", suite,
               "--output", output, "--outputs", "json,html,summary",
               "--acs-config", acs, "--system-config", system]
    if waiver is not None:
        path = folder / "waiver.json"
        write_text(path, json.dumps(waiver, indent=2) + "\n")
        command.extend(["--waiver", path])
    completed = ctx.run(command, folder, name="parser")
    return observe(registry, mode, suite, output, folder, completed)


def observe(registry, mode, suite, output, folder, completed):
    """Read what the command actually published, including errors and HTML labels."""
    raw_path = output / "acs_jsons" / registry[suite]["json_output"]
    merged_path = output / "acs_jsons" / "merged_results.json"
    html_path = output / "html_detailed_summaries" / registry[suite]["detailed_html"]
    # Combined SBMR pages retain interface-specific compliance rows.
    if suite.startswith("SBMR-"):
        combined = html_path.with_name("sbmr_detailed.html")
        if combined.is_file():
            html_path = combined
    raw_paths = [raw_path] if raw_path.is_file() else []
    if suite == "OS-TESTS" and mode == "DT":
        raw_paths = sorted((output / "acs_jsons").glob("ethtool_test_*.json"))
    raw_values = [load_json(path) for path in raw_paths]
    raw = raw_values[0] if len(raw_values) == 1 else {}
    if len(raw_values) > 1:
        # These are separate distribution totals; no parent/child rows are added.
        raw = {"suite_summary": {"total_" + key: sum(counts(value)[key] for value in raw_values)
                                 for key in counts({})}}
    merged = json.loads(merged_path.read_text()) if merged_path.is_file() else {}
    tables = ReportTables()
    if html_path.is_file():
        tables.feed(html_path.read_text(encoding="utf-8"))
    rows = [row for table in tables.tables
            if "acs-compliance-table" in table["class"].split()
            for row in table["rows"] if len(row) == 3]
    label = label_for(suite, mode)
    html_status = next((row[2] for row in rows if row[0] == label), None)
    # Standalone row labels use visible aliases from registry requirement keys.
    if suite == "OS-TESTS" and mode == "DT":
        body = [row for row in rows if row[0].casefold() not in ("test suite", "test case")]
        if body:
            html_status = next((row[2] for row in body if not green(row[2])), "Compliant")
    elif html_status is None and not suite.startswith("SBMR-"):
        body = [row for row in rows if row[0] not in ("Test suite", "Test case")]
        if len(body) == 1:
            html_status = body[0][2]
    chart_failed = next((int(row[1]) for table in tables.tables
                         if "acs-compliance-table" not in table["class"].split()
                         for row in table["rows"]
                         if len(row) == 2 and row[0] == "Failed"
                         and row[1].isdigit()), None)
    result = {"exit": completed.returncode, "counts": counts(raw),
              "status": suite_status(merged, suite, mode, registry),
              "html_status": html_status, "html_failed": chart_failed,
              "traceback": "Traceback (most recent call last)" in completed.stdout,
              "error": next((line.strip() for line in reversed(completed.stdout.splitlines())
                             if line.partition(":")[0].endswith(("Error", "Exception"))), ""),
              "raw": raw, "log": completed.stdout, "folder": str(folder),
              "evidence": [path for path in (folder / "parser.log", folder / "parser.command.json",
                                              *raw_paths, merged_path, html_path) if path.is_file()]}
    write_text(folder / "observation.json", json.dumps(
        {key: value for key, value in result.items()
         if key not in ("raw", "log", "evidence")}, indent=2) + "\n")
    return result


def brief(observation):
    description = (f"exit={observation['exit']}; raw counts={observation['counts']}; "
            f"merged={observation['status']!r}; HTML={observation['html_status']!r}; "
            f"HTML Failed={observation['html_failed']!r}")
    return description + ("; " + observation["error"] if observation.get("error") else "")


def control_ok(observation, require_html=True):
    """Require a working passing sample before trusting checks with broken logs."""
    return (observation["exit"] == 0 and green(observation["status"])
            and (not require_html or green(observation["html_status"]))
            and observation["counts"]["passed"] > 0
            and observation["counts"]["failed"] == 0
            and observation["counts"]["failed_with_waiver"] == 0)


def invalid_verdict(observation, require_html=True):
    """Check that a broken log is rejected or does not produce a green report."""
    if observation["exit"] in (3, 4):
        return "BLOCKED"
    if observation["traceback"]:
        return "FAIL"
    # A later command failure must not excuse a Compliant artifact already saved.
    if green(observation["status"]) or green(observation["html_status"]):
        return "FAIL"
    if observation["exit"] != 0:
        return "PASS" if observation["exit"] == 5 else "FAIL"
    if observation["status"] is None or (require_html and observation["html_status"] is None):
        return "BLOCKED"
    return "PASS"


def empty_verdict(observation):
    """Empty/introductory logs must complete as Not Run with no test outcomes."""
    if observation["exit"] in (3, 4):
        return "BLOCKED"
    if observation["exit"] != 0 or observation["traceback"]:
        return "FAIL"
    if green(observation["status"]) or green(observation["html_status"]):
        return "FAIL"
    not_run = "not run" in str(observation["status"]).casefold()
    return "PASS" if not_run and not any(observation["counts"].values()) else "FAIL"


def record(ctx, ident, status, issue, expected, observation, mode, suite):
    ctx.add(ident, status, issue, expected, brief(observation), mode=mode,
            suite=suite, evidence=observation["evidence"])


def record_html(ctx, observation, mode, suite, case, enabled=True):
    """Check HTML against merged JSON separately from checking the input log."""
    if not enabled or observation["exit"] != 0 or observation["status"] is None:
        return
    from .merge import status as compliance_status

    wanted = compliance_status(observation["status"])
    actual = compliance_status(observation["html_status"])
    record(ctx, "raw.html-compliance", "PASS" if wanted != "unknown" and actual == wanted else "FAIL",
           case + ": detailed HTML must retain the merged JSON suite decision.",
           "A present compliance row matching merged JSON: " + str(observation["status"]),
           observation, mode, suite)


def family(ctx, registry, mode, suite, relative, good, malformed, control_counts=None,
           html_available=True):
    """Check a complete log first, then its empty, cut-short or invalid versions."""
    def files(content):
        return dict(content) if isinstance(content, dict) else {relative: content}

    positive = invoke(ctx, registry, mode, suite, "positive", files(good))
    ready = control_ok(positive, require_html=False)
    expected_control = "At least one passed result, no failures/waivers, Compliant in merged JSON"
    if control_counts is not None:
        # Post-Script records errors rather than positive INFO lines. Its known
        # complete error is a valid control; never fabricate a passing subtest.
        expected_counts = {**counts({}), **control_counts}
        expected_green = not expected_counts["failed"]
        status_text = str(positive["status"]).strip().casefold()
        status_matches = (green(positive["status"]) if expected_green else
                          status_text.startswith("not compliant") and "not run" not in status_text)
        ready = (positive["exit"] == 0 and positive["status"] is not None
                 and status_matches and positive["counts"] == expected_counts)
        expected_control = str(expected_counts) + ("; Compliant" if expected_green else "; Not Compliant")
    record(ctx, "raw.positive", "PASS" if ready else "BLOCKED",
           "A complete native-log control must parse before malformed-log checks are meaningful.",
           expected_control,
           positive, mode, suite)
    record_html(ctx, positive, mode, suite, "Positive control", html_available)
    if not ready:
        ctx.add("raw.incomplete.coverage", "BLOCKED",
                "Malformed-log cases were not evaluated because the positive control failed.",
                ", ".join(name for name, _, _ in malformed), "Control unavailable",
                mode=mode, suite=suite, evidence=positive["evidence"])
        return set()
    evaluated = set()
    for name, text, caveat in malformed:
        observation = invoke(ctx, registry, mode, suite, name, files(text))
        empty = name in ("empty-log", "header-only")
        verdict = empty_verdict(observation) if empty else invalid_verdict(observation, require_html=False)
        # Quiet completed dt-validate is valid. Empty input alone cannot prove completion.
        if caveat and verdict == "FAIL" and not observation["traceback"]:
            verdict = "WARN"
        record(ctx, "raw." + name, verdict,
               caveat or ("Empty or introductory-only input must be Not Run, not invented test outcomes."
                          if empty else "Incomplete or unrecognized raw evidence must not become a green result."),
               ("Publish Not Run with zero executed outcomes" if empty else
                "Reject the input clearly or publish non-green/incomplete status; do not invent a pass"),
               observation, mode, suite)
        record_html(ctx, observation, mode, suite, name, html_available)
        if verdict != "BLOCKED":
            evaluated.add(name)
    if suite in ("SCT", "BBSR-SCT"):
        observation = invoke(ctx, registry, mode, suite, "parent-only-failures",
                             {relative: sct_log(suite, failed=True, parent_only=True)})
        valid = (observation["exit"] == 0 and observation["counts"]["failed"] == 2
                 and observation["status"] is not None)
        verdict = ("BLOCKED" if not valid else "FAIL"
                   if green(observation["status"])
                   else "PASS")
        record(ctx, "raw.sct-parent-failure", verdict,
               "Two explicit failed SCT entries must remain non-compliant when subtest detail is absent.",
               "Failed=2 in raw JSON; Not Compliant in merged JSON",
               observation, mode, suite)
        if observation["exit"] == 0:
            record(ctx, "raw.sct-parent-chart", "PASS" if observation["html_failed"] == 2 else "FAIL",
                   "The detailed chart must preserve both explicit failed SCT entries.",
                   "Failed=2 in the detailed HTML chart", observation, mode, suite)
        record_html(ctx, observation, mode, suite, "Parent-only SCT failures", html_available)
    return evaluated


def additional_raw_jobs(modes):
    """Small producer-format controls for routes the older raw probes missed.

    Text comes from the bundled native fixtures and the DT network, memory-map,
    alignment and ethtool producers. Mutations change only Doctor-owned copies:
    remove all evidence, keep only introductory text, cut a started check short,
    or corrupt the required result field. OS inputs retain their directory shape.
    """
    jobs = []

    def add(mode, suite, relative, good, header, truncated, malformed, expected=None):
        if mode not in modes:
            return
        empty = {name: "" for name in good} if isinstance(good, dict) else ""
        cases = [("empty-log", empty, ""), ("header-only", header, ""),
                 ("truncated-log", truncated, ""), ("malformed-log", malformed, "")]
        jobs.append((mode, suite, relative, good, cases, expected))

    dtb_header = "INFO: Starting DTB alignment test\n"
    dtb = (dtb_header + "INFO: DTB address is 0xFCEAD000\n"
           "INFO: Required alignment is 8 bytes\n"
           "INFO: DTB address 0xFCEAD000 is 8-byte aligned\nRESULT: PASS\n")
    add("DT", "DTB-ALIGNMENT", "linux_tools/dtb_alignment_test.log", dtb, dtb_header,
        dtb.rsplit("RESULT:", 1)[0], dtb.replace("RESULT: PASS", "RESULT: UNKNOWN"),
        {"passed": 1, "failed": 0})

    network_header = "[INFO] network_boot_checks\n"
    network_first = network_header + "Image URL: PASSED (URL Found: http://example.invalid/boot.img)\n"
    network = (network_first + "EFI System Partition (ESP): PASSED (detected ESP on the system)\n"
               "Logs captured: PASSED (lsblk, blkid and dmesg logs exist)\nNetwork_Boot_Result: PASSED\n")
    add("DT", "NETWORK-BOOT", "network_boot/network_boot_results.log", network, network_header,
        network_first + "EFI System Partition (ESP): ",
        network_first + "EFI System Partition (ESP): UNKNOWN\nNetwork_Boot_Result: UNKNOWN\n",
        {"passed": 3, "failed": 0})

    pfdi_header = "*** Running PFDI tests ***\n"
    pfdi_first = pfdi_header + "PFDI_01 : 1 : QA passing rule\nResult: PASSED\n"
    add("DT", "PFDI", "uefi/pfdiresults.log", pfdi_first, pfdi_header,
        pfdi_first + "PFDI_02 : 2 : QA unfinished rule\n",
        pfdi_first + "PFDI_02 : 2 : QA malformed rule\nResult: UNKNOWN\n",
        {"passed": 1, "failed": 0})

    post_header = "INFO <module>: INFO config: using check-sr-results-dt3.yaml\n"
    # A complete ERROR line is an independently known result. INFO is deliberately
    # not counted as a pass by this producer, so this control expects one failure.
    post_error = "ERROR check_file: `/doctor/sample.log' missing\n"
    add("DT", "POST-SCRIPT", "post-script/post-script.log", post_header + post_error,
        post_header, post_header + "ERROR check_file: `/doctor/sample.log' miss",
        post_header + "ERRO? check_file: `/doctor/sample.log' missing\n",
        {"passed": 0, "failed": 1, "failed_with_waiver": 0, "warnings": 0})

    # DT producer (Yocto/meta-woden/recipes-acs/install-files/files/init.sh)
    # captures `dmesg | grep psci`. This real kernel introduction survives that
    # filter but contains no firmware-version result (timestamps omitted).
    psci_header = "psci: probing for conduit method from DT.\n"
    add("DT", "PSCI", "linux_tools/psci/psci_kernel.log",
        "psci: PSCIv1.1 detected in firmware.\n", psci_header,
        "psci: PSCIv1.1 detected in firm", "psci: PSCIv1.2.3 detected in firmware.\n",
        {"passed": 1, "failed": 0})

    memory_header = "Testing Devicetree Reserved Memory Map Compliance Test\n"
    memory_first = memory_header + "INFO: Reserved Memory Map Compliance Test: PASSED\n"
    memory = (memory_first + "INFO: Checking Memory Reservation Block entries\n"
              "INFO: Memory Reservation Block Compliance Test: PASSED\nRESULTS: PASSED\n")
    add("DT", "RESERVED-MEMORY-MAP", "linux_tools/reserved_memory_map_test.log", memory,
        memory_header, memory_first + "INFO: Checking Memory Reservation Block entries\n",
        memory.replace("RESULTS: PASSED", "RESULTS: UNKNOWN"), {"passed": 2, "failed": 0})

    scmi_header = "**** SCMI Compliance Suite ****\n*** Starting BASE tests ***\n"
    scmi_first = scmi_header + "1 : QA passing protocol : CONFORMANT\n"
    add("DT", "SCMI", "linux_acs/scmi_acs_app/arm_scmi_test_log.txt", scmi_first, scmi_header,
        scmi_first + "2 : QA unfinished protocol\n", scmi_first + "2 : QA invalid protocol : UNKNOWN\n",
        {"passed": 1, "failed": 0})

    smbios_header = "BBR ACS 2.1\nSmbiosTable\nTest Configuration #0\nQA SMBIOS table check\n"
    smbios = smbios_header + "SMBIOS table -- PASS\n00000000-0000-0000-0000-000000000001\nQA table found\n"
    add("DT", "SMBIOS", "sct_results/Overall/Summary.log", smbios, "BBR ACS 2.1\n",
        smbios_header + "SMBIOS table -- ", smbios.replace("-- PASS", "-- UNKNOWN"),
        {"passed": 1, "failed": 0})

    kself_header = "selftests: dt: test_unprobed_devices.sh\n"
    kself_first = kself_header + "# ok 1 synthetic passing device check\n"
    add("DT", "DT-KSELFTEST", "linux_tools/dt_kselftest.log", kself_first, kself_header,
        kself_first + "# not ok 2", kself_first + "# UNKNOWN 2 synthetic missing status\n",
        {"passed": 1, "failed": 0})

    runtime_header = "Testing Runtime Device Mapping Conflict Test\n"
    runtime = runtime_header + "RESULTS: PASSED\n"
    add("DT", "RUNTIME-DEV-MAP", "linux_tools/runtime_device_mapping_conflict_test.log",
        runtime, runtime_header, runtime_header + "DEBUG: Checking device mapping\n",
        runtime_header + "RESULTS: UNKNOWN\n", {"passed": 1, "failed": 0})

    # DT checks three separate OS directories. Corrupt only the final OS for
    # partial-input cases, retaining passed neighbours to catch hidden omissions.
    os_header = "****************************************************************\nRunning ethtool\n****************************************************************\n"
    os_start = (os_header + "INFO: Detected following ethernet interfaces via ip command :\n"
                "0: eth0\n\n"
                "INFO: Bringing up ethernet interface: eth0\n"
                "INFO: Ethernet interface eth0 supports ethtool self test.\n")
    os_complete = (os_start + "The test result is PASS\n"
                   "INFO: Ping to router/gateway[192.0.2.1] for eth0 is successful\n"
                   "INFO: Ping to www.arm.com is successful\n")
    os_paths = ["../os-logs/" + name + "/ethtool_test.log"
                for name in ("linux-Fedora-40", "linux-ubuntu-24", "linux-Tumbleweed")]
    os_good = dict.fromkeys(os_paths, os_complete)
    add("DT", "OS-TESTS", None, os_good, dict.fromkeys(os_paths, os_header),
        {**os_good, os_paths[-1]: os_start},
        {**os_good, os_paths[-1]: os_start + "The test result is UNKNOWN\n"},
        {"passed": 15, "failed": 0})

    # SR's mandatory OS check reads /etc/os-release, not DT's ethtool format.
    release_rhel = "../os-logs/rhel/cat-etc-os-release.txt"
    release_sle = "../os-logs/sle/cat-etc-os-release.txt"
    sr_good = {release_rhel: 'NAME="Red Hat Enterprise Linux"\nVERSION_ID="9.3"\n',
               release_sle: 'NAME="SLES"\nVERSION_ID="15"\n',
               "post-script/post-script.log": "INFO <module>: OS log validation completed\n"}
    add("SR", "OS-TESTS", None, sr_good,
        {name: "# OS log capture started\n" for name in sr_good},
        {**sr_good, release_sle: 'NAME="SLES"\nVERSION_ID='},
        {**sr_good, release_sle: 'NAME: "SLES"\nVERSION_ID: "15"\n'},
        {"passed": 2, "failed": 0})

    pcie_header = ("PcieOptionRomArchAudit: report all live PCIe devices and classify option ROM contents\n")
    pcie = (pcie_header + "Scanned 3 EFI_PCI_IO handles and found 1 PCIe devices with Option ROM images:\n"
            "PCIe devices with ROM : 1\nNon-compliant devices : 0\n"
            "BBR (UEFI 6.3.3.1 UEFI Drivers) Result Summary: FAIL\n")
    add("SR", "PCIE-OPTION-ROM-ARCH-AUDIT", "uefi_dump/PcieOptionRomArchAudit.log", pcie,
        pcie_header, pcie.split("Non-compliant devices", 1)[0],
        pcie.replace("Non-compliant devices : 0", "Non-compliant devices : invalid"),
        {"passed": 1, "failed": 0})
    return jobs


def waiver_probe(ctx, registry, suite, relative, content, waiver, name, expected, html_available=True):
    """Compare the same log before and after its waiver, including exact counts."""
    baseline = invoke(ctx, registry, "DT", suite, name + "-unwaived", {relative: content})
    expected_base = expected[0]
    if baseline["exit"] or any(baseline["counts"][key] != value
                               for key, value in expected_base.items()):
        record(ctx, "waiver." + name, "BLOCKED",
               "The unwaived native-log control did not establish this waiver case.",
               str(expected_base), baseline, "DT", suite)
        return
    result = invoke(ctx, registry, "DT", suite, name, {relative: content}, waiver)
    desired = expected[1]
    okay = (result["exit"] == 0 and all(result["counts"][key] == value
                                       for key, value in desired.items()))
    if okay:
        okay = green(result["status"])
    verdict = "PASS" if okay else "BLOCKED" if result["exit"] in (3, 4) else "FAIL"
    record(ctx, "waiver." + name, verdict, expected[2],
           str(desired) + "; Compliant in merged JSON", result, "DT", suite)
    record_html(ctx, result, "DT", suite, name, html_available)


def waiver_idempotence(ctx, registry, html_available=True):
    """Check that applying the same waiver twice does not change results again."""
    waiver = {"Suites": [{"Suite": "FWTS", "Reason": "Synthetic doctor idempotence waiver"}]}
    first = invoke(ctx, registry, "DT", "FWTS", "waiver-idempotence",
                   {"fwts/FWTSResults.log": fwts_log(failed=1)}, waiver)
    established = (first["exit"] == 0 and first["counts"]["failed"] == 0
                   and first["counts"]["failed_with_waiver"] == 1
                   and green(first["status"]))
    record_html(ctx, first, "DT", "FWTS", "Waiver idempotence control", html_available)
    if not established:
        record(ctx, "waiver.idempotence", "BLOCKED",
               "A valid one-failure waiver must work before repeat application can be checked.",
               "One waived failure; zero remaining failures", first, "DT", "FWTS")
        return
    folder = Path(first["folder"])
    raw = folder / "output/acs_jsons/fwts.json"
    second = folder / "second-application.json"
    shutil.copy2(raw, second)
    result = ctx.run([ctx.python, "-B", ctx.parser_dir / "apply_waivers.py",
                      "FWTS", second, folder / "waiver.json",
                      ctx.parser_dir / "test_categoryDT.json", "--quiet"],
                     folder, "second-application")
    after = counts(json.loads(second.read_text()))
    ctx.add("waiver.idempotence", "PASS" if result.returncode == 0
            and after == first["counts"] else "FAIL",
            "Applying an identical waiver twice must not change totals or invent another waived result.",
            str(first["counts"]), f"exit={result.returncode}; second counts={after}",
            mode="DT", suite="FWTS", evidence=[raw, second, folder / "second-application.log"])


def stale_rerun(ctx, registry, html_available=True, suite="BSA"):
    """Compare a reused output folder with a fresh run after its log is removed."""
    mode = "DT" if Path("/mnt/yocto_image.flag").is_file() else "SR"
    if mode not in ctx.modes:
        ctx.add("normal.stale-rerun", "BLOCKED",
                "The normal wrapper selects its mode using the host Yocto flag; doctor will not change it.",
                "Normal rerun in a requested mode", "Host mode is " + mode,
                mode=mode, suite=suite)
        return
    folder = ctx.case_dir("raw/normal-stale-" + mode + "-" + suite)
    acs, system = config_files(folder, mode)
    inputs = folder / "input" / "acs_results"
    relative, content = {
        "BSA": ("uefi/BsaResults.log", bsa_log()),
        "FWTS": ("fwts/FWTSResults.log", fwts_log()),
        "SCT": ("sct_results/Overall/Summary.log", sct_log("SCT")),
    }[suite]
    log_path = inputs / relative
    write_text(log_path, content)
    command = ["bash", ctx.parser_dir / "main_log_parser.sh", inputs, acs, system, ""]
    first = ctx.run(command, folder, "first")
    output = inputs / "acs_summary"
    baseline = observe(registry, mode, suite, output, folder / "first", first)
    baseline["evidence"] = [folder / "first.log", folder / "first.command.json", *baseline["evidence"]]
    record_html(ctx, baseline, mode, suite, "Normal rerun control", html_available)
    if not control_ok(baseline, require_html=False):
        record(ctx, "normal.stale-rerun", "BLOCKED",
               "Normal wrapper positive control failed; stale-result behavior is untested.",
               "A fresh passed " + suite + " report", baseline, mode, suite)
        return
    # Preserve the first report, remove only our sample log, then rerun into the
    # same folder. A separate fresh run gives the expected missing-log result.
    shutil.copytree(output, folder / "first-report")
    # Move only the fixture created here. Never alter user logs or the host flag.
    log_path.rename(folder / "saved-input.log")
    second = ctx.run(command, folder, "missing-rerun")
    rerun = observe(registry, mode, suite, output, folder / "rerun", second)
    fresh = folder / "fresh" / "acs_results"
    fresh.mkdir(parents=True)
    third = ctx.run(["bash", ctx.parser_dir / "main_log_parser.sh", fresh, acs, system, ""],
                    folder, "fresh-missing")
    clean = observe(registry, mode, suite, fresh / "acs_summary", folder / "fresh", third)
    valid = clean["status"] is not None and "not run" in str(clean["status"]).lower()
    rerun_missing = rerun["status"] is not None and "not run" in str(rerun["status"]).lower()
    verdict = ("BLOCKED" if not valid else "PASS" if rerun_missing and second.returncode == 0 else "FAIL")
    ctx.add("normal.stale-rerun", verdict,
            "Removing the " + suite + " raw log must not reuse the previous run's Compliant JSON.",
            "Rerun and fresh missing-input run both show " + suite + " Not Run",
            f"first={baseline['status']!r}; rerun={rerun['status']!r}; fresh={clean['status']!r}",
            mode=mode, suite=suite, evidence=[folder / "first.log", folder / "missing-rerun.log",
                                             folder / "fresh-missing.log",
                                             folder / "first-report/acs_jsons/merged_results.json",
                                             output / "acs_jsons/merged_results.json",
                                             fresh / "acs_summary/acs_jsons/merged_results.json"])


def conditional_execution_records(suite, text):
    """Read completed tests in these small controls, not banners or JSON presence.

    This is deliberately limited to the conditional-rule fixture formats below,
    not a replacement parser for arbitrary partner logs. Unknown and skip-only
    records do not prove completion here; their policy is checked separately.
    """
    if suite in ("SBSA", "PFDI"):
        heading = "PE" if suite == "SBSA" else "PFDI"
        if f"*** Running {heading} tests ***" not in text:
            return []
        rule = r"S_[A-Z0-9_]+" if suite == "SBSA" else r"R[0-9]{4}"
        return [(f"{name} : {number}", description.strip(), result)
                for name, number, description, result in re.findall(
                    rf"(?m)^[ \t]*({rule}) : ([0-9]+) : ([^\r\n]+)\r?\n"
                    r"[ \t]*Result:[ \t]+(PASSED|FAILED)[ \t]*\r?$", text)]
    if suite not in ("SBMR-IB", "SBMR-OOB"):
        return []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    if root.tag != "robot":
        return []
    records = []
    for test in root.iter("test"):
        # A keyword or suite can say NOT RUN while its enclosing test ran.
        # Only the direct test status belongs to that test.
        terminal = test.find("status")
        result = terminal.get("status") if terminal is not None else None
        name = (test.get("name") or "").strip()
        if name and result in ("PASS", "FAIL"):
            records.append((name, "PASSED" if result == "PASS" else "FAILED"))
    return records


def conditional_execution_cases(modes):
    """Replay source-backed result records; these are not hardware test runs."""
    # Rule IDs/descriptions and their PASSED results were checked in FR_SBSA.log
    # and acs_results_templat_perfect/acs_results/uefi/pfdiresults.log. The grammar
    # and IDs also match sysarch-acs 4fdfb75e, val/src/rule_based_execution_helpers.c
    # and val/src/rule_metadata.c. Only the relevant records are replayed.
    cases = [
        ("SR", "SBSA", "uefi/SbsaResults.log",
         "*** Running PE tests ***\n"
         "S_L3PE_01 : 23 : Check PE Granule Support\n   Result:  PASSED\n"
         "S_L3PE_02 : 24 : Check for 16-bit ASID support\n   Result:  PASSED\n",
         "Captured SBSA rule/result excerpt; producer grammar checked at sysarch-acs 4fdfb75e."),
        ("DT", "PFDI", "uefi/pfdiresults.log",
         "*** Running PFDI tests ***\n"
         "R0040 : 11 : Check if X5 to X17 are preserved\n   Result:  PASSED\n"
         "R0053 : 1 : Check PFDI Version is returned\n   Result:  PASSED\n",
         "Captured PFDI rule/result excerpt; producer grammar checked at sysarch-acs 4fdfb75e."),
    ]
    # Robot test names and direct-status layout were checked against saved XML
    # and sbmr-acs 35c333f3/70d0a581. IB retains a captured PASS. OOB deliberately
    # substitutes PASS for a captured setup FAIL: it is a positive replay, not
    # evidence that this OOB hardware test passed or its original body executed.
    for interface, folder, category, name in (
            ("IB", "in", "Test Ipmi Shell Inband Interface Check",
             "Test Host IPMI Inband Interface Functionality"),
            ("OOB", "out_of", "Test Ipmi Outband Boot Select",
             "Test IPMI Out-of-Band Boot Device Selection")):
        content = (f'<robot><suite name="SBMR-ACS {interface}"><suite name="Ipmi">'
                   f'<suite name="{category}"><test name="{name}">'
                   '<status status="PASS"/></test></suite></suite></suite></robot>')
        cases.append(("SR", "SBMR-" + interface,
                      f"sbmr/sbmr_{folder}_band_logs/output.xml", content,
                      "Source-backed Robot identity/layout; " +
                      ("captured direct test PASS." if interface == "IB" else
                       "controlled PASS mutation of a captured OOB setup FAIL, not a hardware result.")))
    return [case for case in cases if case[0] in modes]


def conditional_raw_expectation(suite, records):
    """Require exact native result identities and counts before losing the JSON."""
    expected = []
    for index, record in enumerate(records):
        if suite in ("SBSA", "PFDI"):
            name, description, result = record
            path = ["test_results", 0, "testcases", index]
            fields = {"Test_case": name, "Test_case_description": description, "Test_result": result}
        else:
            description, result = record
            path = ["test_results", 0, "Test_cases", 0, "subtests", index]
            fields = {"sub_Test_Number": str(index + 1), "sub_Test_Description": description,
                      "sub_test_result": result}
        expected.append({"path": path, "fields": fields})
    passed = sum(record[-1] == "PASSED" for record in records)
    failed = sum(record[-1] == "FAILED" for record in records)
    if suite in ("SBSA", "PFDI"):
        summary = {"Total Rules Run": len(records), "Passed": passed, "Failed": failed,
                   "Total_failed_with_waiver": 0, "Skipped": 0, "Warnings": 0,
                   "Passed (Partial)": 0, "PAL Not Supported": 0, "Not Implemented": 0}
    else:
        summary = {**dict.fromkeys(("total_" + key for key in counts({})), 0),
                   "total_passed": passed, "total_failed": failed}
    return {"records": expected, "assertions": [
        {"path": ["suite_summary", key], "value": value} for key, value in summary.items()]}


def run_conditional_execution(ctx, registry):
    """Check the log-to-merge boundary when executed results are unavailable.

    Keep the successful raw-log control intact and omit its JSON only from a
    separate merge command. The current merger sees JSON, not source logs; a
    mismatch identifies a pipeline evidence gap, not a raw parser repair.
    """
    from .merge import differences, expected_leaves, merged_records, oracle, payload, status

    leaves = expected_leaves(list(registry.values()))
    for mode, suite, relative, content, provenance in conditional_execution_cases(ctx.modes):
        folder = ctx.case_dir("conditional/" + mode + "/" + suite)
        try:
            records = conditional_execution_records(suite, content)
            control = invoke(ctx, registry, mode, suite, "conditional-control", {relative: content})
            issues = raw_issues(control["raw"], conditional_raw_expectation(suite, records))
            valid = bool(records) and control["exit"] == 0 and not control["traceback"] and not issues
            source = Path(control["folder"]) / "input" / "acs_results" / relative
            evidence = [source, *control["evidence"]]
            ctx.add("raw.conditional-control", "PASS" if valid else "BLOCKED",
                    "Known executed tests must retain their exact identities and results before JSON is withheld.",
                    records, issues or brief(control), mode, suite, evidence)
            if not valid:
                ctx.add("raw.conditional-execution", "BLOCKED",
                        "Cannot verify conditional requirements without a working native execution control.",
                        "Verified native execution before the missing-JSON probe", issues or brief(control),
                        mode, suite, evidence)
                continue

            affected = {"SBMR-IB", "SBMR-OOB"} if suite.startswith("SBMR-") else {suite}
            states = {item["canonical"]: "missing" if item["canonical"] in affected else "pass"
                      for item in leaves if mode in item["modes"]}
            # Other suites get passing semantic JSON so their failures cannot
            # mask this defect. Neither SBMR peer JSON is present in its probe.
            executed = {name for name, state in states.items() if state == "pass"} | {suite}
            expected, overall = oracle(leaves, mode, states, executed=executed)
            info = folder / "acs_info.json"
            write_text(info, json.dumps({"ACS Results Summary": {"Band":
                       "SystemReady Devicetree band" if mode == "DT" else "SystemReady band"}}))
            paths = [info]
            for item in leaves:
                name = item["canonical"]
                if states.get(name) == "pass":
                    path = folder / item["json_output"]
                    write_text(path, json.dumps(payload(name, "pass")))
                    paths.append(path)
            scenario = {"mode": mode, "executed_suite": suite, "provenance": provenance,
                        "raw_records": records, "withheld_json": registry[suite]["json_output"],
                        "expected_suites": expected, "expected_overall": overall,
                        "scope": "Controlled direct-merger JSON omission, not observed routine JSON loss. "
                                 "Normal-flow conversion failure is not exercised here. Standalone validates "
                                 "generated JSON before publishing; this probe bypasses that safeguard. "
                                 "Other suites use passing semantic fixtures; original control is unchanged."}
            write_text(folder / "scenario.json", json.dumps(scenario, indent=2))
            # Verify the same full-run baseline first. An unrelated failure in
            # these supporting fixtures must not be blamed on losing this JSON.
            native_path = Path(control["folder"]) / "output" / "acs_jsons" / registry[suite]["json_output"]
            baseline_path = folder / "baseline_merged_results.json"
            baseline = ctx.run([ctx.python, "-B", ctx.parser_dir / "merge_jsons.py", "--mode", mode,
                                baseline_path, *paths, native_path], folder, "merge-baseline")
            evidence.extend([folder / "scenario.json", folder / "merge-baseline.log",
                             folder / "merge-baseline.command.json", baseline_path])
            if baseline.returncode or not baseline_path.is_file():
                baseline_issue = command_diagnostic(baseline)
            else:
                baseline_rows, baseline_summary = merged_records(load_json(baseline_path), leaves, mode)
                baseline_expected, baseline_overall = oracle(leaves, mode, {**states, suite: "pass"},
                                                             executed=executed)
                baseline_issue = differences(baseline_expected, baseline_rows)
                if status(baseline_summary["Overall Compliance Result"], overall=True) != baseline_overall:
                    baseline_issue = {**baseline_issue, "overall": baseline_summary["Overall Compliance Result"]}
            if baseline_issue:
                ctx.add("raw.conditional-execution", "BLOCKED",
                        "Full-run control already differs before JSON is withheld; conditional loss was not isolated.",
                        "Same supporting inputs and real native JSON match the independent baseline",
                        baseline_issue, mode, suite, evidence)
                continue
            destination = folder / "merged_results.json"
            process = ctx.run([ctx.python, "-B", ctx.parser_dir / "merge_jsons.py", "--mode", mode,
                               destination, *paths], folder, "merge-withheld-json")
            evidence.extend([folder / "scenario.json", folder / "merge-withheld-json.log",
                             folder / "merge-withheld-json.command.json", destination])
            if process.returncode or not destination.is_file():
                ctx.add("raw.conditional-execution", "BLOCKED",
                        "Missing-JSON probe did not publish inspectable compliance decisions.",
                        "Retained conditional requirement and non-green result, or an explicit missing-result diagnostic",
                        command_diagnostic(process), mode, suite, evidence)
                continue
            actual, summary = merged_records(load_json(destination), leaves, mode)
            changes = differences(expected, actual)
            actual_overall = status(summary["Overall Compliance Result"], overall=True)
            unrelated = set(changes) - affected
            observation = {"suite_differences": changes, "actual_suites": actual,
                           "actual_overall": actual_overall, "expected_overall": overall}
            write_text(folder / "observed.json", json.dumps(observation, indent=2))
            evidence.append(folder / "observed.json")
            ctx.add("raw.conditional-execution", "BLOCKED" if unrelated else
                    "WARN" if changes or actual_overall != overall else "PASS",
                    "Unrelated suite decisions changed; conditional loss was not isolated." if unrelated else
                    "Conditional execution evidence must reach the merger; JSON-only omission cannot establish no execution.",
                    "Executed " + suite + "; results missing, not proof of no execution. " +
                    str({name: expected[name] for name in sorted(affected)}) + "; overall=" + overall,
                    str({name: actual.get(name, "missing") for name in sorted(affected)}) +
                    "; overall=" + actual_overall + "; all suite differences=" + str(changes) +
                    "; direct-merger boundary check only; normal-flow conversion failure not tested here",
                    mode, suite, evidence)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            ctx.add("raw.conditional-execution", "BLOCKED",
                    "Conditional execution evidence could not be verified.",
                    "Source-backed control and an isolated missing-JSON merge",
                    str(error), mode, suite, (folder,))


def run_raw(ctx):
    """Run bad-input, waiver and rerun checks and keep all reproduction evidence."""
    registry = {item["canonical"]: item for item in json.loads(
        (ctx.parser_dir / "suite_registry.json").read_text())["suites"]}
    run_conditional_execution(ctx, registry)
    html_available = html_capability(ctx)
    jobs = []
    for mode in ctx.modes:
        for suite in ("BSA", "SBSA", "FWTS", "SCT", "BBSR-FWTS", "BBSR-SCT", "BBSR-TPM"):
            if mode not in registry[suite]["modes"]:
                continue
            if suite in ("BSA", "SBSA"):
                relative = "uefi/" + ("BsaResults.log" if suite == "BSA" else "SbsaResults.log")
                good, header = bsa_log(suite), f" {suite} Architecture Compliance Suite\n"
            elif "FWTS" in suite:
                relative = ("bbsr/" if suite.startswith("BBSR") else "") + "fwts/FWTSResults.log"
                good, header = fwts_log(suite), "Results generated by fwts: Version V26.01.00.\n"
            elif "SCT" in suite:
                relative = ("bbsr/" if suite.startswith("BBSR") else "") + "sct_results/Overall/Summary.log"
                good, header = sct_log(suite), "BBR ACS 2.1.1 (SBBR)\n"
            else:
                relative = "bbsr/tpm2/verify_tpm_measurements.log"
                good, header = "Verify synthetic TPM measurement : PASS\n", "Capture ended before TPM results\n"
            malformed = [("empty-log", "", ""), ("header-only", header, "")]
            if "FWTS" in suite:
                truncated = good.split("\n" + "=" * 80 + "\n", 1)[0]
                truncated = truncated.replace("Test 1 of 1:", "Test 1 of 2:")
                malformed.append(("truncated-final-subtest",
                                  truncated + "\nTest 2 of 2: Unfinished final check.\n", ""))
            jobs.append((mode, suite, relative, good, malformed))
    if "SR" in ctx.modes:
        for suite, interface in (("SBMR-IB", "in"), ("SBMR-OOB", "out_of")):
            jobs.append(("SR", suite, f"sbmr/sbmr_{interface}_band_logs/output.xml", robot_log(),
                         [("missing-status", robot_log(None), ""),
                          ("unknown-status", robot_log("UNKNOWN"), "")]))
    if "DT" in ctx.modes:
        jobs.extend([
            ("DT", "ETHTOOL-TEST", "linux_tools/ethtool-test.log",
             "Running Networking Checks\nSUMMARY\nDetected Interfaces : 1 (eth0)\nInterface eth0\nBring up : PASSED\nEthtool Compliance : PASSED\n",
             [("header-only", "Running Networking Checks\n", "")]),
            ("DT", "READ-WRITE-CHECK-BLK-DEVICES", "linux_tools/read_write_check_blk_devices.log",
             "Read block devices tool\nINFO: Block device : /dev/sda\nINFO: No valid partition table found for sda, treating as raw device.\nINFO: Performing block read on /dev/sda\nINFO: Block read on /dev/sda successful\n",
             [("header-only", "Read block devices tool\n", "")]),
            ("DT", "CAPSULE-UPDATE", "../fw/capsule_test_results.log",
             "Testing ESRT FW version update\nINFO: Synthetic ESRT check\nRESULTS: Overall Capsule Update Result: PASSED\n",
             [("missing-terminal-result", "Testing ESRT FW version update\nINFO: Synthetic ESRT check\n", "")]),
            ("DT", "DT-VALIDATE", "linux_tools/dt-validate-parser.log",
             "DeviceTree bindings of Linux kernel version 6.19\nINFO parse: 0 entries\nNon-ignored entries\n-------------------\n",
             [("completion-evidence", "", "An empty DT validation log is accepted without completion evidence; quiet completed validation is a separate valid control. Producer completion policy needs confirmation.")]),
        ])
    jobs.extend(additional_raw_jobs(ctx.modes))

    def execute(job):
        mode, suite = job[:2]
        try:
            evaluated = family(ctx, registry, *job, html_available=html_available)
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            ctx.add("raw.probe-blocked", "BLOCKED", "Raw probe could not complete.",
                    "Executed native-log positive and negative controls", str(error), mode=mode, suite=suite)
            evaluated = set()
        return mode, suite, evaluated

    with ThreadPoolExecutor(max_workers=2) as pool:
        # Each job owns a separate folder, so two parser runs cannot share logs.
        attempted = list(pool.map(execute, jobs))
    for mode in ctx.modes:
        # A scheduled job or a waiver check is not bad-input coverage. List each
        # missing category, including cases blocked by a failed complete control.
        aliases = {"truncated-final-subtest": "truncated-log", "missing-terminal-result": "truncated-log",
                   "missing-status": "truncated-log", "unknown-status": "malformed-log",
                   "completion-evidence": "empty-log"}
        categories = {"empty-log", "header-only", "truncated-log", "malformed-log"}
        observed = {suite: {aliases.get(name, name) for name in evaluated}
                    for case_mode, suite, evaluated in attempted if case_mode == mode}
        missing = [suite + ": " + ", ".join(sorted(categories - observed.get(suite, set())))
                   for suite, item in sorted(registry.items())
                   if mode in item["modes"] and item.get("logs_to_json")
                   and categories - observed.get(suite, set())]
        if missing:
            ctx.add("raw.coverage", "WARN",
                    "Some bad-input categories were not evaluated; declared or blocked probes do not count as coverage.",
                    "A working complete control, then empty, introductory, truncated and malformed checks per route",
                    "; ".join(missing), mode=mode)
    if "DT" in ctx.modes:
        suite_waiver = {"Suites": [{"Suite": "FWTS", "Reason": "Synthetic whole-suite doctor waiver"}]}
        checks = [
            ("FWTS", "fwts/FWTSResults.log", fwts_log(failed=2), suite_waiver,
             "whole-suite-multiple-assertions",
             ({"failed": 2}, {"failed": 0, "failed_with_waiver": 2},
              "A whole-suite waiver must cover both failed FWTS assertions, not just one.")),
            ("DT-KSELFTEST", "linux_tools/dt_kselftest.log",
             "selftests: dt: test_unprobed_devices.sh\n# ok 1 synthetic passing device check\n",
             {"Suites": [{"Suite": "Standalone", "TestSuites": [{"TestCase": {"SubTests": [
                 {"sub_Test_Description": "synthetic passing device check", "Reason": "Synthetic doctor waiver"}]}}]}]},
             "passed-test-matching-waiver",
             ({"passed": 1, "failed": 0}, {"passed": 1, "failed": 0, "failed_with_waiver": 0},
              "A waiver matching an already-passed test must not invent a waived failure.")),
            ("RUNTIME-DEV-MAP", "linux_tools/runtime_device_mapping_conflict_test.log",
             "Testing Runtime Device Mapping Conflict Test\nDEBUG: Synthetic mapping conflict\nRESULTS: FAILED\n",
             {"Suites": [{"Suite": "Standalone", "Reason": "Synthetic whole-suite doctor waiver"}]},
             "runtime-map-whole-suite",
             ({"failed": 1}, {"failed": 0, "failed_with_waiver": 1},
              "A valid Runtime Device Map whole-suite waiver must not crash on nested failure reasons.")),
            ("DT-KSELFTEST", "linux_tools/dt_kselftest.log",
             "selftests: dt: test_unprobed_devices.sh\n# ok 1 synthetic passing device check\n",
             {"Suites": [{"Suite": "Standalone", "TestSuites": [{"TestCase": {"SubTests": [
                 {"sub_Test_Description": "another test that was not run", "Reason": "Synthetic unmatched waiver"}]}}]}]},
             "unmatched-waiver",
             ({"passed": 1, "failed": 0}, {"passed": 1, "failed": 0, "failed_with_waiver": 0},
              "An unmatched waiver must leave the actual passed result unchanged.")),
        ]
        for args in checks:
            try:
                waiver_probe(ctx, registry, *args, html_available=html_available)
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                ctx.add("waiver.probe-blocked", "BLOCKED", "Waiver probe could not complete.",
                        "Executed before/after waiver comparison", str(error), mode="DT", suite=args[0])
        try:
            waiver_idempotence(ctx, registry, html_available=html_available)
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            ctx.add("waiver.idempotence", "BLOCKED", "Repeated-waiver probe could not complete.",
                    "Apply the same valid waiver twice without changing counts", str(error), mode="DT", suite="FWTS")
    for suite in ("BSA", "FWTS", "SCT"):
        try:
            stale_rerun(ctx, registry, html_available=html_available, suite=suite)
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            ctx.add("normal.stale-rerun", "BLOCKED", "Normal rerun probe could not complete.",
                    "Fresh, missing-input rerun and clean missing-input comparison", str(error), suite=suite)
