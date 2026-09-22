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

"""Turn recorded Doctor findings into an easy-to-read, self-contained HTML page.

The input is the completed checks and run details. The output is HTML with plain
explanations, filters and evidence links. This file does not run checks, read
evidence files or change their results. CSS and browser controls are kept here so
the report can be opened without downloading extra assets.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json
import re
from urllib.parse import quote
import ast


# These helpers explain existing findings. They return text, not new verdicts.
# The HTML renderer below escapes that text before placing it on the page.

SCHEMA_CHECKS = frozenset({"NATIVE_RAW_SCHEMA", "ARTIFACT.SCHEMA"})
STATUS_CHECKS = frozenset({"raw.missing-status", "raw.unknown-status"})
CATEGORY_PROVENANCE_CHECKS = frozenset(
    {"NATIVE_CATEGORY_PROVENANCE", "ARTIFACT.CATEGORY_PROVENANCE"})
SBMR_SUITES = frozenset({"SBMR", "SBMR-IB", "SBMR-OOB"})


def _text(item, name):
    """Read text from either a finding object or a saved finding dictionary."""
    value = item.get(name, "") if isinstance(item, Mapping) else getattr(item, name, "")
    return "" if value is None else str(value)


def _description(title, happened, impact, next_step, category="issues"):
    return dict(title=title, happened=happened, impact=impact,
                next_step=next_step, category=category)


def _short(text, limit=260):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _literal(text):
    """Read small recorded dictionaries as data; never execute their contents."""
    if not text or len(text) > 100000:
        return None
    try:
        tree = ast.parse(text, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 5000:
            return None
        return ast.literal_eval(tree)
    except (ValueError, TypeError, SyntaxError, RecursionError, MemoryError):
        return None


def _label(value):
    """Translate Doctor's saved status names without deciding compliance again."""
    labels = {"not_run": "Not Run", "not_compliant": "Not Compliant",
              "compliant": "Compliant", "waived": "Compliant with waivers"}
    if isinstance(value, Mapping):
        requirement = str(value.get("requirement", ""))
        result = _label(value.get("status", "Not recorded"))
        return requirement + " (" + result + ")" if requirement else result
    if value is None:
        return "Missing"
    return labels.get(str(value), str(value))


def _comparisons(item):
    """Turn the known JSON/HTML mismatch shapes into readable comparison rows."""
    identifier = _text(item, "check_id")
    actual = _literal(_text(item, "actual"))
    rows = []
    if identifier == "HTML_COMPLIANCE_MATCH" and isinstance(actual, Mapping):
        badges, tables = actual.get("badges"), actual.get("tables")
        for name, difference in (badges.items() if isinstance(badges, Mapping) else ()):
            if isinstance(difference, Mapping):
                rows.append(("Summary card · " + str(name), _label(difference.get("expected")),
                             _label(difference.get("actual"))))
        for page, difference in (tables.items() if isinstance(tables, Mapping) else ()):
            if not isinstance(difference, Mapping):
                continue
            def table_rows(value):
                return Counter(tuple(map(str, row)) for row in value
                               if isinstance(row, (tuple, list)) and len(row) == 3)
            expected = table_rows(difference["expected"]) if isinstance(
                difference.get("expected"), list) else Counter()
            observed = table_rows(difference["actual"]) if isinstance(
                difference.get("actual"), list) else Counter()
            # Matching rows are noise here. Keep repeated missing/extra rows,
            # and pair changed rows by name so the exact difference is visible.
            missing, extra = defaultdict(list), defaultdict(list)
            for source, target in ((expected - observed, missing), (observed - expected, extra)):
                for name, requirement, result in source.elements():
                    target[name].append(requirement + " (" + result + ")")
            for name in sorted(missing.keys() | extra.keys()):
                for index in range(max(len(missing[name]), len(extra[name]))):
                    rows.append((str(page) + " · " + name,
                        missing[name][index] if index < len(missing[name]) else "No row expected",
                        extra[name][index] if index < len(extra[name]) else "Row missing"))
    elif identifier in {"MERGE_INCOMPLETE_NOT_GREEN", "MERGE_SUITE_STATUS"}:
        expected = _literal(_text(item, "expected"))
        if isinstance(expected, Mapping) and isinstance(actual, Mapping):
            for name in expected.keys() | actual.keys():
                rows.append(("Merged JSON · " + str(name),
                            _label(expected.get(name)), _label(actual.get(name))))
    elif identifier in {"MERGE_OVERALL_POLICY", "MERGE_EXTENSION_AGGREGATION"}:
        rows.append(("Overall SRS" if identifier == "MERGE_OVERALL_POLICY" else "BBSR extension",
                     _label(_text(item, "expected")), _label(_text(item, "actual"))))
    return sorted(rows)


def _scenario(item):
    """Explain generated case names, so a reader knows what input was tested."""
    case = _text(item, "issue").split(":", 1)[0]
    states = {"pass": "all its tests pass", "fail": "has an unwaived failure",
              "mixed": "has one waived failure and one unwaived failure",
              "waived": "all its failures are waived", "missing": "its result file is missing",
              "empty": "its JSON has no test outcomes", "header": "its JSON has only a suite heading",
              "recommended_fail": "has a failed group marked Recommended"}
    for prefix, scope in (("full_", "Full run"), ("selected_", "Selected-suite run")):
        if case.startswith(prefix):
            for state in sorted(states, key=len, reverse=True):
                suffix = "_" + state
                if case.endswith(suffix):
                    name = case[len(prefix):-len(suffix)]
                    return scope + ": " + name + " — " + states[state] + (
                        "; other suites pass." if prefix == "full_" else ".")
    if case.startswith("requirement_"):
        parts = case.split("_", 2)
        if len(parts) == 3:
            requirements = {"M": "Mandatory", "R": "Recommended", "CM": "Conditional-Mandatory",
                            "EM": "Extension"}
            return "FWTS classified as " + requirements.get(parts[1], parts[1]) + ": " + states.get(parts[2], parts[2]) + "."
    if case.startswith("recommended_group_"):
        return "Full run: " + case[len("recommended_group_"):] + " has a failed group marked Recommended; other suites pass."
    match = re.fullmatch(r"SBMR_IB_(\w+)_OOB_(\w+)", case)
    if match:
        return "SBMR-IB: " + states.get(match[1], match[1]) + "; SBMR-OOB: " + states.get(match[2], match[2]) + "."
    if case.startswith("BBSR_") and len(case.split("_")) == 4:
        return "; ".join(name + ": " + states.get(state, state)
                         for name, state in zip(("BBSR-FWTS", "BBSR-SCT", "BBSR-TPM"), case.split("_")[1:])) + "."
    return ""


def _probe_counts(item):
    match = re.search(r"(?:^|;\s*)raw counts=(\{[^;\n]*\})", _text(item, "actual"))
    result = _literal(match[1]) if match else None
    return result if isinstance(result, Mapping) else {}


def _count_label(counts):
    names = {"passed": "passed", "failed": "failed", "failed_with_waiver": "waived",
             "aborted": "aborted", "skipped": "skipped", "warnings": "warnings", "ignored": "ignored"}
    return ", ".join(str(counts[key]) + " " + label for key, label in names.items()
                     if key in counts and (key in {"passed", "failed", "failed_with_waiver"} or counts[key]))


def _probe_result(item):
    """Explain exits, counts and report statuses without calling a rejection a pass."""
    code, fields = _observation(item)
    parts = []
    error = re.search(r"\b([A-Za-z]+Error):\s*([^\n;]*)", _text(item, "actual"))
    if error:
        parts.append("The parser stopped with " + error[1] + ": " + error[2])
    elif _no_report(item):
        parts.append("The parser stopped with exit code " +
                     str(code) + " and produced no compliance report")
    elif code is not None and code != 0:
        parts.append("The parser exited with code " + str(code))
    counts = _count_label(_probe_counts(item))
    if counts:
        parts.append("Generated results: " + counts)
    for key, label in (("merged", "Merged JSON"), ("HTML", "HTML")):
        if key in fields and fields[key] is not None and fields[key] != "None":
            parts.append(label + " says " + str(_status_value(fields[key])))
    return ". ".join(parts) + "." if parts else _short(_text(item, "actual"))


def _observation(item):
    """Read only the fixed scalar fields emitted by doctor_probes.brief.

    Unknown or repeated fields remain unknown. In particular, raw-count maps
    and arbitrary status strings are never evaluated as Python expressions.
    """
    fields = {}
    for match in re.finditer(r"(?:^|;\s*)(exit|merged|HTML)\s*=\s*([^;\n]*)",
                             _text(item, "actual")):
        key, value = match.groups()
        value = value.strip()
        if key in fields:
            fields[key] = None
        else:
            fields[key] = value
    code = fields.get("exit")
    code = int(code) if code is not None and re.fullmatch(r"-?\d{1,9}", code) else None
    return code, fields


def _no_report(item):
    code, fields = _observation(item)
    return code is not None and code != 0 and fields.get("merged") == "None" and fields.get("HTML") == "None"


def _status_value(value):
    if value is None:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _has_compliant(item):
    _, fields = _observation(item)
    return any((_status_value(fields.get(key)) or "").strip().casefold() == "compliant"
               for key in ("merged", "HTML"))


def _raw_description(items):
    """Explain status checks without confusing a stopped run with a green report."""
    sbmr = bool(items) and all(_text(item, "suite") in SBMR_SUITES for item in items)
    subject = "SBMR" if sbmr else "Test"
    if items and all(_no_report(item) for item in items):
        return _description(
            subject + " status cases did not produce a completed report",
            "Runs with missing or unrecognized test statuses exited with an error. "
            "No completed merged result or HTML status was recorded in these cases.",
            "This is not evidence of a completed report incorrectly marked Compliant. "
            "The original Doctor findings still require investigation.",
            "Inspect the parser log and raw result for each case. Check why status handling "
            "stopped the run instead of meeting the recorded expected outcome.")
    if any(_has_compliant(item) for item in items):
        return _description(
            subject + " tests with missing or UNKNOWN statuses can produce a Compliant result",
            "At least one missing- or unrecognized-status case recorded Compliant in merged JSON "
            "or HTML. Other cases may have different outcomes.",
            "Incomplete status evidence may be presented as compliant. Inspect each observation; "
            "do not assume that all cases completed or had the same result.",
            "Trace the affected raw status through the parser and merger. Compare the observed "
            "result with the expected rejection or non-green outcome.")
    return _description(
        subject + " status handling needs investigation",
        "Doctor checked how missing or unrecognized test statuses are handled. "
        "The individual observations below show the recorded outcomes.",
        "A status-handling finding does not by itself prove that a report was incorrectly marked "
        "Compliant. Stopped runs and completed reports must be reviewed separately.",
        "Compare each exit code and merged/HTML status with its expected outcome, then inspect "
        "the linked parser log.")


def _coverage_description(items):
    """Explain what was not checked without calling it a confirmed parser defect."""
    actual = "\n".join(_text(item, "actual") for item in items)
    charts = "aggregate/unmapped chart" in actual
    external = "link outside supplied package not inspected" in actual
    if charts and not external:
        return _description(
            "Some combined chart totals were not checked",
            "Doctor could not safely match these aggregate charts to raw result count units.",
            "These chart comparisons remain unverified. This warning does not establish that "
            "the displayed totals are wrong.",
            "Add an explicit chart-to-result mapping and count units, then rerun the comparisons.",
            "coverage")
    if external and not charts:
        return _description(
            "Links outside the supplied package were not checked",
            "Some report links lead outside the supplied package. Doctor did not "
            "inspect those targets.",
            "Those linked pages remain unverified. This warning does not establish "
            "that the links are broken.",
            "Provide a self-contained report package or check the external targets separately.",
            "coverage")
    return _description(
        "Some report comparisons remain unverified",
        "Doctor could not safely complete all artifact comparisons. The recorded notes identify "
        "unmapped charts, out-of-package links, or other comparison limits.",
        "These are coverage limits, not proof that the affected values or links are wrong.",
        "Review the coverage notes and supply the missing mapping or in-package "
        "evidence before rerunning.",
        "coverage")


WARNING_DESCRIPTIONS = {
    "PACKAGE_ENVIRONMENT": (
        "Dependency installation was not retested in a clean environment",
        "Doctor used the recorded Python environment without installing or upgrading packages.",
        "The run does not prove that dependencies install cleanly or work across "
        "every supported Python version.",
        "Use separate clean-environment CI jobs to verify dependency installation and "
        "supported Python versions."),
    "MERGE_UNAGREED_STATUS_POLICY": (
        "Some compliance rules still need owner agreement",
        "Expected compliance for all-skipped, warning-only, and aborted-only results "
        "is not covered "
        "by the agreed compliance checks.",
        "Doctor cannot certify those states against a policy that has not been agreed. "
        "This warning does not change the existing compliance policy.",
        "Agree the expected outcomes with the policy owner, then add explicit checks "
        "for those states."),
    "raw.coverage": (
        "Some suites still need malformed-log tests",
        "The listed suites have no complete malformed/incomplete-log coverage in the "
        "raw-input group.",
        "Handling of bad input remains unverified for those suites. Native "
        "positive-input checks are separate.",
        "Add a complete native control plus malformed and incomplete examples for "
        "each listed suite."),
    "VISUAL_SCOPE": (
        "Rendering checks cover selected examples only",
        "Browser and export smoke checks cover a limited set of synthetic report examples.",
        "This is not full browser, pagination, paper-size, suite, or hardware certification.",
        "Run the additional browser, print, and suite scenarios required for the "
        "intended release."),
    "VISUAL_COVERAGE": (
        "Browser and PDF checks were not requested",
        "This run did not include the optional browser and PDF export checks.",
        "Successful data checks do not establish that browser rendering or PDF output works.",
        "Run Doctor with --doctor-visual and its required rendering dependencies to "
        "check this scope."),
    "SCOPE_LIMIT": (
        "This run checked selected groups only",
        "The run was focused on selected Doctor groups; other groups were omitted.",
        "The verdict applies to the selected checks, not to the untested groups.",
        "Review the recorded group selection and run the omitted groups when full "
        "coverage is needed."),
    "ARTIFACT.INPUT": (
        "No captured report package was checked",
        "No real-capture report package was supplied for artifact comparisons.",
        "Synthetic probes do not establish the correctness of a captured report package.",
        "Supply --doctor-report DT=/path or SR=/path to check a report package read-only."),
}


# Each topic names the failed behavior and the place to investigate it.
# Case-specific input and observed values are shown separately below the topic.
FAILURE_DESCRIPTIONS = {
    "HTML_COMPLIANCE_MATCH": (
        "HTML compliance labels do not match the expected results",
        "Some summary cards or detail-page rows show the wrong requirement or compliance status. "
        "Each example below shows what the report should say and what it actually says.",
        "A partner can read Compliant for missing or failed results, or see the wrong "
        "Mandatory/Recommended label.",
        "Check the named summary card or detail row against its merged JSON. If JSON "
        "is already wrong, "
        "trace the merger; otherwise check how the HTML label is built."),
    "HTML_COMPLIANCE_EXECUTION": (
        "Compliance HTML could not be generated",
        "The report generator raised an error while building summary badges or detail "
        "compliance tables.",
        "The recorded JSON checks are available, but this case has no verified compliance HTML.",
        "Open the generation error and fix the failing report helper, then rerun the same case."),
    "MERGE_INCOMPLETE_NOT_GREEN": (
        "Empty suite results are being treated as completed tests",
        "Doctor supplied JSON with no test outcomes, or only a suite heading. The "
        "merger did not preserve "
        "the expected Not Run status.",
        "A suite with no completed results can appear Compliant. Its "
        "Mandatory/Recommended requirement "
        "must still be retained when marking it Not Run.",
        "Check how merge_jsons.py detects completed outcomes. An empty result list or "
        "heading alone "
        "must not count as successful execution."),
    "MERGE_OVERALL_POLICY": (
        "Overall SRS compliance does not follow the requirement rules",
        "The overall result differs from the expected result for the supplied "
        "Mandatory, Recommended "
        "and extension inputs. These cases include both incorrect passes and incorrect failures.",
        "Recommended failures or missing Recommended results must not block overall SRS. Missing "
        "or failed applicable Mandatory requirements must block it.",
        "Compare the expected and recorded overall labels for each case, then check "
        "which requirements "
        "merge_jsons.py includes in its overall decision."),
    "MERGE_EXTENSION_AGGREGATION": (
        "The combined BBSR extension result is wrong",
        "The combined BBSR status does not match the supplied BBSR-FWTS, BBSR-SCT and "
        "BBSR-TPM results.",
        "Missing or failed BBSR members can be hidden by a Compliant extension label. "
        "BBSR has its own "
        "combined result; it does not decide overall SRS compliance.",
        "Check all three BBSR member statuses against the extension aggregation in "
        "merge_jsons.py."),
    "MERGE_FAILURE_COUNT": (
        "The merger loses explicit SCT failures",
        "SCT input contains failed parent tests with no subtest details, but the "
        "merger counts fewer failures.",
        "The chart can show failures while compliance says Compliant because the "
        "merger only counted subtests.",
        "Count an explicit failed SCT parent when it has no child results. Keep "
        "parent/child counting "
        "separate so a parent with failed children is not counted twice."),
    "MERGE_INVALID_INPUT_SAFETY": (
        "Invalid result data can still receive Compliant",
        "Doctor supplied a malformed result structure. The merger did not reject it "
        "or keep its status non-green.",
        "An unreadable or unsupported result shape can be mistaken for a successful test run.",
        "Check the recorded invalid input and the merger's shape checks before it "
        "calculates compliance."),
    "MERGE_SUITE_STATUS": (
        "A suite's requirement or compliance status is wrong",
        "The merged suite label differs from the expected label for its test results "
        "and requirement.",
        "The report can misstate whether a suite is required or whether its own tests "
        "satisfy compliance.",
        "Compare the suite's input outcomes, requirement and waiver state with the "
        "merged decision."),
    "NATIVE_EXECUTION": (
        "The parser failed while reading a sample log",
        "The public standalone command could not finish a known sample. The example "
        "below names the "
        "suite and the recorded parser error.",
        "This input cannot produce a complete report. Any checks that need its output "
        "remain unverified.",
        "Open parser.log for the affected suite and follow the reported exception to "
        "its parser file."),
    "NATIVE_OUTPUT_INVENTORY": (
        "Expected parser output files are missing or unexpected files appeared",
        "The standalone command's output folder does not contain exactly the expected "
        "suite JSON files.",
        "Missing output prevents downstream checks. When the parser also failed, "
        "these findings can "
        "describe consequences of the same error.",
        "Compare the named missing/unexpected files with parser.log. Resolve an "
        "earlier parser error first."),
    "normal.stale-rerun": (
        "A rerun reuses a previous result after its log is removed",
        "Doctor parsed a passing suite log, removed that log, and ran the parser "
        "again in the same output folder. "
        "The rerun kept the earlier Compliant status; a fresh run reported Not Run.",
        "A later CI job can display an old passing result for a suite that has no current input.",
        "Check how normal runs remove or replace previous suite JSON before "
        "regenerating the merged report."),
    "raw.sct-parent-failure": (
        "SCT has two failed tests, but compliance says Compliant",
        "The raw SCT result contains two explicit failed parent tests with no subtest details. "
        "The compliance decision does not match those failures.",
        "A partner sees Failed: 2 in the chart and Compliant in the same report.",
        "Trace the two failed parent entries from raw SCT JSON into the merger's failure count."),
    "waiver.whole-suite-multiple-assertions": (
        "A whole-suite FWTS waiver leaves one failure unwaived",
        "The sample contains two failed assertions covered by one whole-suite waiver. "
        "Only one assertion "
        "is moved into the waived count.",
        "The remaining failure makes the suite Not Compliant even though the "
        "whole-suite waiver covers both.",
        "Check how apply_waivers.py applies a whole-suite waiver to multiple failures "
        "in the same test."),
    "waiver.runtime-map-whole-suite": (
        "A Runtime Device Map waiver crashes the parser",
        "Applying a valid whole-suite waiver to a nested Runtime Device Map failure "
        "raises a TypeError.",
        "The run stops before it can publish the waived result and complete report.",
        "Check how apply_waivers.py combines nested failure reasons with the waiver reason."),
    "waiver.passed-test-matching-waiver": (
        "A waiver creates a failure for a test that already passed",
        "A waiver matching a passing Standalone test changes its counts as though a "
        "failure was waived.",
        "The report invents a waived failure instead of preserving the original pass.",
        "Apply waivers only to actual failures; leave passing tests and their counts unchanged."),
}


def _input_description(identifier):
    """Explain the deliberate raw-log mutation without assuming how it ended."""
    if identifier in {"raw.empty-log", "raw.header-only"}:
        return _description(
            "Empty or introductory-only logs are not reported as Not Run",
            "Doctor supplied logs with no completed tests. The parser should report "
            "Not Run with zero "
            "test outcomes. Some cases instead stop with an error, invent outcomes or "
            "report Compliant.",
            "These are different problems: a stopped command has no report, while an "
            "invented pass or "
            "Compliant label can mislead a reader. The examples show which occurred.",
            "Check the suite's empty-input handling. Preserve its requirement, publish Not Run, "
            "and keep all executed-outcome counts at zero.")
    cases = {
        "raw.truncated-final-subtest": ("A log ends during a subtest, but the report can still say Compliant",
            "One test finishes, another subtest starts, then its final result is missing."),
        "raw.truncated-log": ("An unfinished test log can still produce Compliant",
            "Doctor cut the log after execution started and before the required final result."),
        "raw.missing-terminal-result": ("A test has no final result, but the report can still say Compliant",
            "The input has introductory or intermediate test text without a final test result."),
        "raw.malformed-log": ("Invalid log content can still produce Compliant",
            "Doctor changed a result marker or supplied malformed log data to the native parser."),
    }
    if identifier not in cases:
        return None
    title, happened = cases[identifier]
    return _description(title, happened,
        "A completed passing test can hide another test that has no usable result. "
        "A Compliant label is not supported by that incomplete input.",
        "Check the changed input against the passing control. Verify required result markers and "
        "handle unfinished or invalid input before calculating compliance.")


def describe_group(check_ids, items):
    """Explain an already-selected display group without changing its findings.

    Related checks may share an explanation, but keep their original severity,
    expected results, observations and counts.
    """
    items = tuple(items)
    ids = {check_ids} if isinstance(check_ids, str) else set(check_ids)
    statuses = {_text(item, "status") for item in items}
    if ids == {"NATIVE_RAW_IDENTITY"} and statuses == {"BLOCKED"}:
        return _description(
            "Test contents could not be checked because the parser produced no JSON",
            "The earlier parser command did not generate the suite's expected JSON file.",
            "Doctor cannot compare its test names, counts and statuses with the sample log.",
            "Resolve the parser/output-file failure above, then rerun this check.", "coverage")
    if statuses == {"BLOCKED"}:
        return _description(
            "Checks could not finish",
            "Doctor could not complete these checks. The recorded observations "
            "identify the missing "
            "input, dependency, or other blocker.",
            "The affected behavior remains unverified; a blocked check is not a "
            "confirmed parser defect.",
            "Resolve the recorded blocker and rerun the same checks before drawing a "
            "correctness conclusion.",
            "coverage")
    if statuses == {"PASS"}:
        return _description(
            "Checks completed successfully",
            "The recorded checks met their expected outcomes.",
            "This result applies only to the scenarios and evidence checked in this run.",
            "Keep the recorded evidence with the run; review any separately reported "
            "coverage limits.",
            "summaries")
    if not items:
        return _description(
            "No findings in this group", "No observations were supplied for this display group.",
            "An empty group does not establish a passing result.", "Review the run scope and recorded findings.",
            "coverage")
    if ids and ids <= SCHEMA_CHECKS:
        return _description(
            "Some JSON files do not match the expected format",
            "The recorded JSON checks did not satisfy the applicable format requirements. "
            "Review the validator messages for missing fields, invalid values, or "
            "validation errors.",
            "Consumers that require the schema may reject these files. A format-check "
            "failure alone "
            "does not prove that test outcomes or compliance decisions are wrong.",
            "Inspect the named JSON file and field path, then align the producer output with the "
            "registered schema. Repeated messages are not necessarily separate defects.")
    if ids and ids <= CATEGORY_PROVENANCE_CHECKS:
        if statuses == {"WARN"}:
            return _description(
                "The run's category-file choice is not recorded",
                "Test_suite_info is missing, but Doctor could not verify whether a "
                "category file was "
                "explicitly supplied to the run that produced these results.",
                "Doctor did not treat this missing field as a failure because its "
                "requirement could "
                "not be confirmed. All other format checks remain active.",
                "Keep the generating run's category-file record and any explicitly "
                "supplied category "
                "file with the results, then recheck. Known bundled defaults alone do not make "
                "Test_suite_info mandatory or cause this warning.", "coverage")
        return _description(
            "The run's category-file record cannot be verified",
            "Doctor found an invalid record of which category file the generating run used. "
            "The recorded error explains what could not be verified.",
            "The category-file record cannot be trusted for this conditional requirement. "
            "This does not by itself prove that a test outcome is wrong.",
            "Check the recorded error against the generating run's saved category "
            "file and run record. "
            "Do not replace missing run evidence with an assumption about today's "
            "bundled defaults.")
    if ids and ids <= STATUS_CHECKS:
        return _raw_description(items)
    if ids == {"raw.conditional-execution"} and statuses == {"WARN"}:
        return _description(
            "Conditional requirements need execution evidence beyond JSON",
            "The raw-log control proves these tests ran. Doctor then deliberately left their "
            "generated JSON out of a separate, disposable input passed directly to the merger. "
            "This JSON-only replay could not retain the obligation established by the raw logs.",
            "Missing result JSON does not mean a test never ran. Executed SR SBSA is Mandatory; "
            "either executed SBMR interface makes both interfaces Mandatory. Executed DT PFDI "
            "remains applicable as Conditional-Mandatory. Losing those required results must "
            "not allow overall Compliant. This controlled fault injection does not establish a "
            "public-flow failure: standalone already rejects parser errors and missing generated "
            "output. The replay did not test whether normal runs can reach this state.",
            "Compare the raw control, the deliberately reduced merge input, and the recorded "
            "requirement and compliance labels. Verify the public-flow guards before claiming "
            "a parser defect; if this state is reachable, preserve the fact that a required "
            "test ran when passing results to the merger.", "coverage")
    if ids == {"ARTIFACT.CONSISTENCY"}:
        return _description(
            "Report-package check summary",
            "This records the package-level result across JSON, result identities, "
            "HTML, and local links.",
            "Package-level result; inspect individual findings before treating it as "
            "an additional defect.",
            "Open the package evidence and review its individual findings and "
            "coverage notes.", "summaries")
    if ids == {"ARTIFACT.PARITY"}:
        return _description(
            "Report details do not match the source results",
            "A test identifier, name, or status differs between the compared report "
            "and source results.",
            "A reader may see a different result description from the raw data. "
            "A changed label alone does not establish a changed test outcome.",
            "Compare the missing and changed records. Check HTML text escaping when "
            "literal angle-bracket "
            "text disappears from a test name.")
    if statuses == {"FAIL"} and len(ids) == 1:
        identifier = next(iter(ids))
        if identifier in FAILURE_DESCRIPTIONS:
            return _description(*FAILURE_DESCRIPTIONS[identifier])
        raw_description = _input_description(identifier)
        if raw_description:
            return raw_description
    if statuses == {"WARN"}:
        if ids == {"ARTIFACT.COVERAGE"}:
            return _coverage_description(items)
        if ids == {"raw.completion-evidence"}:
            compliant = any(_has_compliant(item) for item in items)
            return _description(
                "Empty-input completion policy needs confirmation",
                ("An empty-input probe recorded Compliant without recorded completion evidence."
                 if compliant else "The completion-evidence probe needs review; its observations are "
                "recorded below."),
                "An empty log alone does not prove the producer finished. A quiet but "
                "completed validation "
                "is a separate valid case.",
                "Confirm what establishes producer completion and add separate "
                "controls for empty and "
                "quiet-but-completed logs.", "coverage")
        if len(ids) == 1 and next(iter(ids)) in WARNING_DESCRIPTIONS:
            return _description(*WARNING_DESCRIPTIONS[next(iter(ids))], category="coverage")
        return _description(
            _short(_text(items[0], "issue")) or "A coverage limit or caution needs review",
            "Doctor recorded a warning. Review the exact observation before "
            "interpreting its cause.",
            "This warning is not a passing check or an automatically confirmed defect.",
            "Review the expected and observed values and any linked evidence.", "coverage")
    return _description(
        _short(_text(items[0], "issue")) or "A Doctor check needs investigation",
        "The recorded check did not establish its expected outcome; the original "
        "details are shown below.",
        "The effect depends on the mismatch. Do not infer a wrong compliance result "
        "without checking the evidence.",
        "Compare expected and observed values, inspect the linked evidence, and rerun "
        "the affected check.")


def describe_finding(item):
    """Return a short case label and an observation grounded in recorded text."""
    identifier, status = _text(item, "check_id"), _text(item, "status")
    issue, actual, suite = (_text(item, name) for name in ("issue", "actual", "suite"))
    title = _short(issue) or identifier or "Doctor finding"
    observed = _short(actual) or "No observation was recorded."
    comparisons = _comparisons(item)
    scenario = _scenario(item)
    if comparisons:
        observed = " ".join(where + " should show " + expected + "; the report shows " + recorded + "."
                            for where, expected, recorded in comparisons[:3])
        title = (suite + ": " if suite else "") + {
            "HTML_COMPLIANCE_MATCH": "incorrect compliance label",
            "MERGE_INCOMPLETE_NOT_GREEN": "empty results received the wrong status",
            "MERGE_SUITE_STATUS": "incorrect requirement or suite status",
            "MERGE_OVERALL_POLICY": "incorrect overall SRS result",
            "MERGE_EXTENSION_AGGREGATION": "incorrect combined BBSR result",
        }[identifier]
        return dict(title=title, observed=observed, comparisons=comparisons, scenario=scenario)
    if status == "BLOCKED":
        if identifier == "NATIVE_RAW_IDENTITY":
            title = (suite + ": " if suite else "") + "JSON was not generated"
            observed = "Test names and results could not be compared because the expected output file is missing."
        return dict(title=title, observed="Check did not complete: " + observed)
    if identifier in CATEGORY_PROVENANCE_CHECKS and status == "WARN":
        title = "Category-file choice could not be confirmed"
        observed = ("Missing Test_suite_info was not treated as a failure because the "
                    "generating run's "
                    "category-file choice could not be verified. Other format checks still apply.")
    elif identifier in CATEGORY_PROVENANCE_CHECKS and status == "FAIL":
        title = "Category-file run record could not be verified"
    elif identifier in SCHEMA_CHECKS and status == "FAIL":
        filename = re.search(r"[\w.-]+\.json\b", issue)
        title = (filename.group(0) if filename else suite or "JSON file") + ": format check failed"
        missing = list(dict.fromkeys(re.findall(r"'([^'\r\n]+)' is a required property", actual)))
        if missing:
            observed = "Validator reports missing required fields: " + ", ".join(missing) + "."
        else:
            observed = "Validator observation: " + observed
    elif identifier == "NATIVE_EXECUTION":
        title = (suite + ": " if suite else "") + "parser failed on the sample log"
        error = re.search(r"\b([A-Za-z]+Error):\s*([^\n]*)", actual)
        code = re.search(r"\bExit (\d+)", actual)
        observed = ("The standalone parser stopped" + (" with exit code " + code[1] if code else "") +
                    (". " + error[1] + ": " + error[2] if error else ". See the recorded command output") + ".")
    elif identifier == "NATIVE_OUTPUT_INVENTORY":
        title = (suite + ": " if suite else "") + "expected JSON output is missing or unexpected"
        messages = []
        for field, label in (("missing", "Missing output"), ("unexpected", "Unexpected output")):
            match = re.search(field + r"=(\[[^\n;]*\])", actual)
            files = _literal(match[1]) if match else None
            if isinstance(files, list) and files:
                messages.append(label + ": " + ", ".join(map(str, files)))
        observed = ". ".join(messages) + "." if messages else observed
    elif identifier == "MERGE_FAILURE_COUNT":
        title = (suite + ": " if suite else "") + "SCT parent failures were not counted"
        expected_counts = re.search(r"Failed/waived=\((\d+),\s*(\d+)\)", _text(item, "expected"))
        actual_counts = re.search(r"Failed/waived=\((\d+),\s*(\d+)\)", actual)
        if expected_counts and actual_counts:
            observed = ("Input contains " + expected_counts[1] + " failed and " + expected_counts[2] +
                        " waived tests. The merger counted " + actual_counts[1] + " failed and " +
                        actual_counts[2] + " waived tests.")
    elif identifier == "MERGE_INVALID_INPUT_SAFETY":
        title = (suite + ": " if suite else "") + "invalid input accepted"
        observed = ("The supplied result structure is invalid. The merger returned " +
                    _label(actual) + ".")
    elif identifier == "raw.conditional-execution" and status == "WARN":
        title = (suite + ": " if suite else "") + "JSON-only merge replay after recorded execution"
        expected_rows = _literal(_text(item, "expected").split(". ", 1)
                                 [-1].split("; overall=", 1)[0])
        actual_rows = _literal(actual.split("; overall=", 1)[0])
        labels = []
        if isinstance(expected_rows, Mapping) and isinstance(actual_rows, Mapping):
            for name in expected_rows:
                labels.append(str(name) + " should stay " + _label(expected_rows[name]) +
                              "; JSON-only replay returned " + _label(actual_rows.get(name)))
            expected_overall = re.search(r"; overall=(\w+)", _text(item, "expected"))
            actual_overall = re.search(r"; overall=(\w+)", actual)
            if expected_overall and actual_overall:
                labels.append("Overall SRS should be " + _label(expected_overall[1]) +
                              "; replay returned " + _label(actual_overall[1]))
        observed = ("Controlled merge-boundary replay; public-flow failure not established. " +
                    (". ".join(labels) + "." if labels else
                     "Generated JSON was deliberately omitted after raw execution was established. "
                     "Review the recorded requirement and overall decision below."))
    elif identifier in STATUS_CHECKS:
        case = "missing test status" if identifier == "raw.missing-status" else "unrecognized test status"
        title = (suite + ": " if suite else "") + case
        code, fields = _observation(item)
        if _no_report(item):
            observed = ("Exit code " + str(code) +
                        "; no completed merged result or HTML status was recorded.")
        elif code is not None:
            parts = ["Exit code " + str(code)]
            for key, label in (("merged", "merged JSON"), ("HTML", "HTML")):
                if key in fields and fields[key] is not None:
                    value = _status_value(fields[key])
                    parts.append(
                        label + (" status was not recorded" if fields[key] == "None" else " says " + value))
            observed = "; ".join(parts) + "."
    elif identifier.startswith("raw.") and identifier not in {"raw.coverage", "raw.positive"}:
        names = {"raw.empty-log": "empty log", "raw.header-only": "introductory text only",
                 "raw.truncated-final-subtest": "log ends during a subtest",
                 "raw.truncated-log": "log ends before execution finishes",
                 "raw.missing-terminal-result": "no final test result",
                 "raw.malformed-log": "malformed log", "raw.sct-parent-failure": "two failed SCT parents",
                 "raw.completion-evidence": "empty validation log"}
        title = (suite + ": " if suite else "") + names.get(identifier, issue)
        observed = _probe_result(item)
        if identifier in {"raw.empty-log", "raw.header-only"}:
            observed = ("No completed tests were supplied. " +
                        observed + " Expected: Not Run with zero test outcomes.")
        elif identifier == "raw.sct-parent-failure":
            observed = "Two parent tests explicitly failed. " + observed
    elif identifier.startswith("waiver."):
        title = (suite + ": " if suite else "") + {
            "waiver.whole-suite-multiple-assertions": "only one of two failures was waived",
            "waiver.runtime-map-whole-suite": "applying the suite waiver crashed",
            "waiver.passed-test-matching-waiver": "a passing test became a waived failure",
        }.get(identifier, issue)
        observed = _probe_result(item)
        expected_counts = _literal(_text(item, "expected").split(";", 1)[0])
        if isinstance(expected_counts, Mapping):
            observed = "Expected: " + _count_label(expected_counts) + ". " + observed
    elif identifier == "normal.stale-rerun":
        title = (suite + ": " if suite else "") + "old result survives after its log is removed"
        results = dict(re.findall(r"(first|rerun|fresh)='([^']*)'", actual))
        if len(results) == 3:
            observed = ("First run: " + results["first"] + ". Rerun after removing the log: " + results["rerun"] +
                        ". Fresh run without the log: " + results["fresh"] + ". The rerun retained an old result.")
    elif identifier == "ARTIFACT.CONSISTENCY":
        match = re.search(r"JSON schema validation failed:\s*(\d+)", actual)
        title = "Saved report package: check summary"
        if match:
            observed = ("This package has " + match[1] + " JSON format findings, listed in the format topic above. "
                        "This entry summarizes that package's result.")
    elif identifier == "ARTIFACT.COVERAGE":
        notes = []
        for source, chart in re.findall(r"([^;]+?): aggregate/unmapped chart ([^;]+)", actual):
            notes.append("In " + source.strip() + ", the chart " + chart.strip() +
                         " could not be matched to raw result counts")
        observed = ". ".join(notes) + "." if notes else observed
    elif identifier == "raw.coverage":
        observed = "Bad-input cases not yet checked: " + actual
        for key, label in (("empty-log", "empty log"), ("header-only", "introductory text only"),
                           ("truncated-log", "unfinished log"), ("malformed-log", "invalid log")):
            observed = observed.replace(key, label)
    elif identifier == "PACKAGE_ENVIRONMENT":
        observed = "The current Python environment was used. A fresh dependency installation and other Python versions were not tested."
    elif identifier == "MERGE_UNAGREED_STATUS_POLICY":
        observed = "There is no agreed expected compliance result for runs containing only skipped tests, warnings or aborted tests."
    elif identifier == "ARTIFACT.PARITY" and "HTML" in issue:
        for original in re.findall(r"'([^'\r\n]*<[^>\r\n]+>[^'\r\n]*)'", _text(item, "expected")):
            displayed = re.sub(r"<[^>]+>", "", original)
            if displayed and repr(displayed) in actual:
                observed = "Raw test name: " + original + ". Displayed test name: " + displayed + "."
                break
    return dict(title=title, observed=observed, scenario=scenario)


# Keep the page usable offline: all styles and browser controls are embedded.

STYLE = r"""
:root {
  color-scheme: light;
  --bg:#f3f6fb; --panel:#fff; --text:#172033; --heading:#102a4c;
  --muted:#667085; --line:#d8e1ed; --brand:#163b68; --focus:#1769e0;
  --shadow:0 8px 26px rgba(16,42,76,.06);
  --fail:#b42318; --fail-soft:#fff1f0; --pass:#168044; --pass-soft:#ecfdf3;
  --warn:#945a09; --warn-soft:#fff8e7; --blocked:#6941a5; --blocked-soft:#f4efff;
}
* {box-sizing:border-box}
body {margin:0; background:var(--bg); color:var(--text); font:14px/1.5 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
button,input,select {font:inherit}
button,a,input,select,summary {-webkit-tap-highlight-color:transparent}
button,a,summary {touch-action:manipulation}
button {cursor:pointer}
a {color:#175cd3; text-underline-offset:3px}
a:hover {color:var(--brand)}
:focus-visible {outline:3px solid var(--focus); outline-offset:4px}
summary:focus-visible {outline-offset:-3px}
[hidden] {display:none!important}
.shell {width:calc(100% - 48px); max-width:1360px; margin:24px auto}
.hero {background:linear-gradient(115deg,#0f2c50,#1b4573); color:white; border-radius:16px; padding:23px 26px; box-shadow:var(--shadow)}
.hero-top,.hero-bottom,.section-heading,.toolbar-actions,.group-heading,.finding-heading {display:flex; align-items:center; gap:16px}
.hero-top {justify-content:space-between; align-items:flex-start}
.eyebrow {font-size:11px; font-weight:750; letter-spacing:.16em; color:#c5d9f4; margin:0 0 8px}
h1 {font-size:32px; line-height:1.2; letter-spacing:-.04em; margin:0; font-weight:750}
.hero-description {color:#d0def0; margin:9px 0 0; font-size:14px}
.verdict {border:1px solid rgba(255,255,255,.26); border-radius:12px; padding:11px 16px; background:rgba(255,255,255,.08); min-width:180px}
.verdict-label {display:block; font-size:10px; letter-spacing:.12em; color:#d0def0; font-weight:700; margin-bottom:4px}
.verdict-value {display:flex; align-items:center; gap:9px; font-size:17px; font-weight:750}
.verdict-value::before {content:""; width:9px; height:9px; border-radius:50%; background:#fd9c94; box-shadow:0 0 0 4px rgba(253,156,148,.12)}
.verdict.pass .verdict-value::before {background:#86efac; box-shadow:0 0 0 4px rgba(134,239,172,.12)}
.verdict.blocked .verdict-value::before {background:#dac0ff; box-shadow:0 0 0 4px rgba(218,192,255,.12)}
.hero-bottom {justify-content:space-between; flex-wrap:wrap; margin-top:22px; padding-top:17px; border-top:1px solid rgba(255,255,255,.15)}
.run-meta {display:flex; gap:20px; align-items:center; flex-wrap:wrap; color:#d0def0; font-size:12px; min-width:0}
.run-meta strong {color:white; font-weight:650}
.run-meta code {color:white; font-size:12px}
.exports {display:flex; align-items:center; gap:8px; flex-wrap:wrap}
.button {display:inline-flex; align-items:center; justify-content:center; gap:7px; border:1px solid var(--line); background:white; color:var(--brand); border-radius:9px; padding:9px 13px; text-decoration:none; font-weight:650; white-space:nowrap; line-height:1.4}
.button:hover {background:#edf4ff; color:var(--heading); border-color:#b8cde8}
.hero .button {border-color:rgba(255,255,255,.26); color:white; background:rgba(255,255,255,.08); font-size:12px}
.hero .button:hover {background:rgba(255,255,255,.17)}
.hero .button.primary {background:white; color:var(--brand); border-color:white}
.icon {width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; flex-shrink:0}
.metrics {display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin:16px 0 12px}
.metric {background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 17px; box-shadow:var(--shadow)}
.metric-label {font-size:12px; font-weight:650; color:var(--muted); display:flex; gap:8px; align-items:center}
.metric-dot {width:7px; height:7px; border-radius:50%; background:var(--muted)}
.metric-value {display:block; font-size:26px; letter-spacing:-.04em; line-height:1.3; font-weight:750; margin-top:4px; color:var(--heading); font-variant-numeric:tabular-nums}
.metric.fail .metric-dot {background:var(--fail)} .metric.fail .metric-value {color:var(--fail)}
.metric.pass .metric-dot {background:var(--pass)} .metric.pass .metric-value {color:var(--pass)}
.metric.warn .metric-dot {background:var(--warn)} .metric.warn .metric-value {color:var(--warn)}
.metric.blocked .metric-dot {background:var(--blocked)} .metric.blocked .metric-value {color:var(--blocked)}
.scope-note {display:flex; gap:10px; align-items:flex-start; margin:0 0 17px; color:var(--muted); font-size:12px}
.info-icon {display:inline-flex; align-items:center; justify-content:center; width:19px; height:19px; flex-shrink:0; color:var(--brand); background:#e5eefb; border-radius:50%; font-weight:750}
.scope-note p {margin:0}
.scope-note strong {color:#344054; font-weight:650}
.section-heading {justify-content:space-between; margin-bottom:15px}
h2 {font-size:21px; letter-spacing:-.025em; color:var(--heading); margin:0}
.section-description {margin:4px 0 0; color:var(--muted); font-size:12px}
.review-guide {border:1px solid var(--line); border-radius:13px; background:white; padding:16px 19px; margin:0 0 16px}
.review-guide h2 {font-size:18px}
.review-guide p {margin:5px 0 12px; color:#526176; font-size:13px}
.quick-nav {display:flex; flex-wrap:wrap; gap:8px}
.quick-nav a {display:inline-flex; align-items:center; gap:9px; border:1px solid var(--line); border-radius:7px; padding:6px 11px; color:var(--heading); text-decoration:none; font-size:12px; font-weight:650}
.quick-nav a:hover {background:#f2f6fc}
.quick-nav strong {font-variant-numeric:tabular-nums; border-radius:4px; padding:0 5px; background:#edf2f8}
.findings-section {margin-top:24px; scroll-margin-top:20px}
.findings-section>.section-heading {align-items:flex-start; margin-bottom:11px}
.section-kicker {font-size:10px; text-transform:uppercase; letter-spacing:.11em; color:var(--muted); font-weight:750; margin:0 0 4px}
.group-explanation {display:grid; grid-template-columns:1fr 1fr; gap:10px 22px; margin:0; padding:0 19px 15px}
.group-explanation>div:first-child {grid-column:1/-1}
.group-explanation dt {font-size:11px; font-weight:750; color:var(--muted); margin-bottom:3px}
.group-explanation dd {font-size:13px; color:#344054; margin:0; overflow-wrap:anywhere}
.group-explanation>div:last-child {border-left:2px solid #bdcfe5; padding-left:13px}
.topic-examples {margin:0 19px 14px; border:1px solid #e3eaf3; background:#f7f9fc; border-radius:7px; padding:9px 12px}
.topic-examples h4 {margin:0 0 4px; font-size:11px; color:#62738a}
.topic-examples p {margin:4px 0; font-size:12px; color:#344054; overflow-wrap:anywhere}
.topic-examples strong {color:var(--heading); font-weight:650}
.topic-examples .example {padding:10px 0; border-top:1px solid var(--line)}
.topic-examples .example:first-of-type {border-top:0; padding-top:2px}
.input-scenario {color:#526176; font-size:12px; margin:4px 0 10px; overflow-wrap:anywhere}
.result-comparison {width:100%; border-collapse:collapse; table-layout:fixed; font-size:12px; margin:8px 0}
.result-comparison th,.result-comparison td {padding:8px 10px; border:1px solid var(--line); text-align:left; vertical-align:top; overflow-wrap:anywhere}
.result-comparison th {font-size:10px; color:#526176; background:#edf2f8; font-weight:750}
.result-comparison td {background:white}
.result-comparison td:last-child {background:#fff5f4; font-weight:650; color:var(--fail)}
.result-comparison th:first-child {width:36%}
.technical-data {margin-top:12px; padding-top:10px; border-top:1px solid var(--line)}
.technical-data>summary {font-size:11px; color:var(--muted); font-weight:650; padding:3px 0 8px}
.technical-data>summary::before {content:'+ '; color:var(--brand)}
.technical-data[open]>summary::before {content:'− '}
.group-checks {border-top:1px solid #e5ebf3; background:#fafbfd}
.group-checks>summary {padding:10px 19px; color:var(--brand); font-size:12px; font-weight:650; display:flex; justify-content:space-between; gap:10px}
.group-checks>summary::after {content:'+'; font-size:16px; line-height:1}
.group-checks[open]>summary::after {content:'−'}
.group-checks .group-content {border:0; background:transparent}
.finding-observed {font-size:12px; line-height:1.55; color:#475467; background:#f4f7fb; border-radius:6px; padding:9px 11px; margin:0 0 10px; overflow-wrap:anywhere}
.finding-observed strong {color:var(--heading)}
.original-issue {font-size:12px; color:var(--muted); overflow-wrap:anywhere; margin:6px 0 10px}
.technical-id {font:10px ui-monospace,SFMono-Regular,Consolas,monospace; color:#69788d}
.presentation-note {font-size:11px; color:#dae5f3; margin:12px 0 0}
.filter-panel {background:#fff; border:1px solid var(--line); border-radius:13px; padding:15px 18px; margin-bottom:16px; box-shadow:var(--shadow)}
.filters {display:grid; grid-template-columns:minmax(230px,2.1fr) repeat(3,minmax(130px,1fr)); gap:12px}
.field {display:flex; flex-direction:column; gap:5px; min-width:0}
.field label {font-size:11px; font-weight:700; color:var(--muted)}
.field input,.field select {width:100%; min-width:0; border:1px solid var(--line); border-radius:8px; height:40px; padding:8px 11px; color:var(--text); background:white}
.field input::placeholder {color:#8994a5}
.field input:focus,.field select:focus {border-color:var(--focus)}
.toolbar-bottom {display:flex; justify-content:space-between; gap:12px; align-items:center; flex-wrap:wrap; margin-top:12px}
.match-count {font-size:12px; color:var(--muted); margin:0}
.toolbar-actions {gap:7px}
.toolbar-actions .button {padding:6px 10px; font-size:12px}
.toolbar-actions .quiet {border-color:transparent; background:transparent; color:var(--muted)}
.finding-group {border:1px solid var(--line); border-left:4px solid var(--warn); border-radius:12px; background:white; margin:0 0 13px; box-shadow:var(--shadow); overflow:hidden}
.finding-group.fail {border-left-color:var(--fail)}
.finding-group.blocked {border-left-color:var(--blocked)}
summary {cursor:pointer; list-style:none}
summary::-webkit-details-marker {display:none}
.group-heading {padding:16px 19px 12px; gap:13px; position:relative; align-items:flex-start}
.finding-heading::after {content:""; border-right:1.8px solid #6b7c92; border-bottom:1.8px solid #6b7c92; width:7px; height:7px; transform:rotate(45deg); margin:0 2px 4px 3px; flex-shrink:0; transition:transform .15s}
details[open]>.finding-heading::after {transform:rotate(225deg); margin-top:6px}
.group-copy {flex:1; min-width:0}
.group-title {display:block; font-size:17px; line-height:1.4; font-weight:750; color:var(--heading); overflow-wrap:anywhere; margin:0}
.group-meta {display:flex; align-items:center; gap:9px; flex-wrap:wrap; color:var(--muted); font-size:11px; margin-top:5px}
.affected-list>summary {text-decoration:underline; text-underline-offset:3px}
.affected-list p {margin:6px 0 0; line-height:1.6}
.badge {display:inline-flex; gap:5px; align-items:center; justify-content:center; border-radius:6px; padding:4px 8px; font-size:10px; font-weight:750; letter-spacing:.035em; background:var(--warn-soft); color:var(--warn); min-width:55px; flex-shrink:0}
.badge.fail {background:var(--fail-soft); color:var(--fail)}
.badge.blocked {background:var(--blocked-soft); color:var(--blocked)}
.group-count {font-size:11px; font-weight:650; color:var(--muted); white-space:nowrap; font-variant-numeric:tabular-nums; padding-top:2px}
.group-content {padding:0 20px 18px; border-top:1px solid #e8edf4; background:#fbfcfe}
.group-hint {font-size:11px; color:var(--muted); margin:12px 0 9px}
.finding {border:1px solid #e1e7ef; border-radius:9px; background:white; margin:8px 0 0; overflow:hidden}
.finding-heading {padding:12px 14px; gap:12px}
.finding-heading:hover {background:#f8fafd}
.case-number {font:11px ui-monospace,SFMono-Regular,Consolas,monospace; color:#7b879b; width:22px; flex-shrink:0}
.finding-title {flex:1; min-width:0; color:#344054; font-size:13px; font-weight:650; overflow-wrap:anywhere}
.context-chip {font-size:10px; padding:3px 7px; background:#f0f4fa; color:#4f627d; border-radius:5px; font-weight:650; overflow-wrap:anywhere}
.finding-body {padding:0 16px 16px}
.comparison {display:grid; grid-template-columns:1fr 1fr; gap:12px; padding-top:5px}
.comparison-panel {padding:13px 15px; border:1px solid #e4eaf1; border-radius:9px; background:#f8fafc; min-width:0}
.comparison-panel.actual {background:#fff7f6; border-color:#f2d4d1}
.blocked .comparison-panel.actual {background:#f8f5ff; border-color:#e6dbf7}
.warn .comparison-panel.actual {background:#fffbf0; border-color:#efdfb9}
.comparison h4 {font-size:10px; text-transform:uppercase; letter-spacing:.09em; margin:0 0 8px; color:var(--muted)}
.comparison .actual h4 {color:var(--fail)}
.blocked .actual h4 {color:var(--blocked)} .warn .actual h4 {color:var(--warn)}
.comparison pre {margin:0; white-space:pre-wrap; overflow-wrap:anywhere; max-height:280px; overflow:auto; font:12px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace; color:#344054}
.evidence-heading {font-size:11px; font-weight:700; color:#475467; margin:15px 0 7px}
.evidence-list {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; list-style:none; padding:0; margin:0}
.evidence-link {display:flex; gap:9px; align-items:flex-start; border:1px solid #e4eaf1; border-radius:7px; padding:9px 10px; color:#245a96; text-decoration:none; min-width:0}
.evidence-link:hover {background:#edf4ff; border-color:#bfd3f2}
.evidence-link .icon {margin-top:2px; width:14px; height:14px}
.evidence-link span {min-width:0}
.evidence-link strong {display:block; font-size:11px; font-weight:650; overflow-wrap:anywhere}
.evidence-link small {display:block; margin-top:1px; font-size:10px; color:var(--muted); overflow-wrap:anywhere}
.no-evidence {font-size:11px; color:var(--muted); margin:12px 0 0}
.empty-state {padding:40px 20px; text-align:center; background:white; border:1px dashed #bfd0e4; border-radius:13px; color:var(--muted)}
.empty-state h3 {font-size:18px; color:var(--heading); margin:0 0 8px}
.empty-state p {margin:0; font-size:13px}
.summary-group {box-shadow:none; background:#fcfdff}
.run-details {margin-top:23px; border-top:1px solid var(--line); padding-top:16px; color:var(--muted)}
.run-details>summary {font-size:12px; font-weight:650; display:inline-flex; gap:8px; align-items:center}
.run-details>summary::before {content:"+"; font-size:16px; color:var(--brand)}
.run-details[open]>summary::before {content:"−"}
.metadata-grid {display:grid; grid-template-columns:1fr 1fr; gap:14px 24px; margin:16px 0}
.metadata-grid>div {min-width:0}
.metadata-grid dt {font-size:10px; letter-spacing:.04em; text-transform:uppercase; font-weight:750; margin-bottom:3px}
.metadata-grid dd {margin:0; color:#344054; overflow-wrap:anywhere; font-size:12px}
.metadata-grid pre {margin:0; font:11px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace; white-space:pre-wrap; overflow-wrap:anywhere; max-height:180px; overflow:auto}
footer {margin-top:22px; display:flex; justify-content:space-between; gap:12px; color:#7c8899; font-size:11px}
.skip-link {position:fixed; top:-60px; left:16px; z-index:10; background:white; padding:12px; border:2px solid var(--focus)}
.skip-link:focus {top:12px}
.js-only {display:none}
.js .js-only {display:flex}
.js .filters {display:grid}
.print-note {display:none}
@media(max-width:900px) {
  .shell {width:calc(100% - 36px); margin:18px auto}
  .hero {padding:22px}
  .filters {grid-template-columns:1fr 1fr}
  .metric {padding:14px}
  .metric-value {font-size:26px}
  .comparison {grid-template-columns:1fr}
  .group-explanation {gap:10px 16px}
}
@media(max-width:560px) {
  .shell {width:calc(100% - 24px); margin:12px auto}
  .hero {padding:20px; border-radius:13px}
  .hero-top {flex-direction:column; gap:16px}
  h1 {font-size:28px}
  .hero-description {font-size:13px}
  .verdict {min-width:0; display:flex; align-items:center; gap:13px; padding:7px 11px}
  .verdict-label {margin:0; font-size:9px}
  .verdict-value {font-size:13px}
  .run-meta {gap:8px 14px}
  .exports {gap:6px; width:100%}
  .hero .button {padding:8px 10px; font-size:11px}
  .metrics {grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:12px}
  .metric:first-child {grid-column:1/-1; display:flex; justify-content:space-between; align-items:center; padding:10px 15px}
  .metric:first-child .metric-value {margin:0; font-size:25px}
  .metric {padding:12px 15px}
  .metric-value {font-size:26px}
  .scope-note {font-size:11px; margin-bottom:18px}
  .filter-panel {padding:12px}
  .filters {grid-template-columns:1fr 1fr; gap:9px}
  .field:first-child {grid-column:1/-1}
  .field:last-child {grid-column:1/-1}
  .toolbar-bottom {align-items:flex-start}
  .toolbar-actions {flex-wrap:wrap}
  .group-heading {padding:14px 12px 10px; gap:9px; flex-wrap:wrap}
  .group-heading .badge {min-width:49px; padding:3px 6px; font-size:9px}
  .group-copy {flex-basis:calc(100% - 75px)}
  .group-title {font-size:15px}
  .group-count {margin-left:58px; font-size:11px; padding:0}
  .group-explanation {grid-template-columns:1fr; padding:0 12px 13px; gap:10px}
  .group-explanation>div:last-child {padding-left:10px}
  .group-checks>summary {padding:10px 12px}
  .review-guide {padding:13px}
  .group-content {padding:0 10px 12px}
  .finding-heading {padding:11px 10px; gap:8px; flex-wrap:wrap}
  .case-number {width:17px}
  .finding-title {flex-basis:calc(100% - 60px); font-size:12px}
  .finding-heading::after {margin-left:auto}
  .context-chip {font-size:9px}
  .finding-body {padding:0 10px 12px}
  .comparison-panel {padding:11px}
  .comparison pre {font-size:11px}
  .evidence-list,.metadata-grid {grid-template-columns:1fr}
  .section-heading {gap:10px}
  h2 {font-size:19px}
  footer {flex-direction:column; gap:3px}
}
@media(prefers-reduced-motion:reduce) {*{scroll-behavior:auto!important; transition:none!important}}
@media print {
  @page {size:A4; margin:12mm}
  :focus-visible {outline:none}
  body {background:white; font-size:10pt; -webkit-print-color-adjust:exact; print-color-adjust:exact}
  .shell {width:100%; max-width:none; margin:0}
  .hero {padding:16px 20px; border-radius:9px; box-shadow:none; break-inside:avoid}
  .hero-description {font-size:10pt}
  h1 {font-size:24pt}
  .hero-bottom {margin-top:12px; padding-top:10px}
  .exports,.filter-panel,.skip-link,.run-details,footer,.js-only,.quick-nav {display:none!important}
  .metrics {gap:7px; margin:12px 0}
  .metric {padding:10px; box-shadow:none; break-inside:avoid}
  .metric-value {font-size:21pt}
  .metric-label {font-size:8pt}
  .scope-note {font-size:8pt; margin-bottom:12px}
  .print-note {display:block; font-size:9pt; color:#475467}
  .finding-group {box-shadow:none; border-radius:6px; overflow:visible; break-inside:auto}
  .group-explanation {font-size:9pt; break-inside:avoid}
  .group-explanation dd {font-size:9pt}
  .review-guide {padding:10px 13px; break-inside:avoid}
  .group-heading {padding:10px 12px; break-after:avoid}
  .group-title {font-size:11pt}
  .group-content {padding:0 10px 10px; background:white}
  .finding {overflow:visible; break-inside:auto}
  .finding-heading {padding:9px; break-after:avoid}
  .finding-body {padding:0 10px 10px}
  .comparison {grid-template-columns:1fr; gap:7px}
  .comparison-panel {break-inside:auto}
  .comparison pre,.metadata-grid pre {max-height:none; overflow:visible; font-size:8pt}
  .evidence-list {grid-template-columns:1fr}
  .evidence-link {break-inside:avoid}
  .finding-heading::after,.group-checks>summary::after,.group-hint {display:none}
  details::details-content {content-visibility:visible!important; height:auto!important}
  details>:not(summary) {display:block!important}
  .finding-group[hidden],.finding[hidden],.findings-section[hidden] {display:block!important}
  .empty-state[hidden] {display:none!important}
}
"""

SCRIPT = r"""
(function () {
  'use strict';
  document.documentElement.classList.add('js');
  const groups = Array.from(document.querySelectorAll('.finding-group'));
  const findings = Array.from(document.querySelectorAll('.finding'));
  const sections = Array.from(document.querySelectorAll('.findings-section'));
  const detailPanels = Array.from(document.querySelectorAll('#findings details'));
  const search = document.getElementById('doctor-search');
  const severity = document.getElementById('severity-filter');
  const mode = document.getElementById('mode-filter');
  const suite = document.getElementById('suite-filter');
  const count = document.getElementById('match-count');
  const empty = document.getElementById('no-matches');
  let printState = null;
  function filter() {
    // Hide non-matching rows only. Recorded verdicts and totals stay unchanged.
    const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let visible = 0, visibleGroups = 0;
    findings.forEach(function (item) {
      const matches = (!severity.value || item.dataset.severity === severity.value) &&
        (!mode.value || (item.dataset.mode || 'Repository') === mode.value) &&
        (!suite.value || JSON.parse(item.dataset.suites).includes(suite.value)) &&
        words.every(word => item.dataset.search.includes(word));
      item.hidden = !matches;
      if (matches) visible++;
    });
    groups.forEach(function (group) {
      const matches = Array.from(group.querySelectorAll('.finding')).filter(item => !item.hidden).length;
      group.hidden = !matches;
      if (matches) visibleGroups++;
      const label = group.querySelector('.group-count');
      const total = Number(group.dataset.total);
      label.textContent = (matches === total ? total : matches + ' / ' + total) + (total === 1 ? ' check' : ' checks');
      group.querySelector('.details-count').textContent = matches;
      group.querySelector('.details-unit').textContent = matches === 1 ? 'check' : 'checks';
    });
    sections.forEach(section => {section.hidden = !Array.from(section.querySelectorAll('.finding-group')).some(group => !group.hidden);});
    count.textContent = 'Showing ' + visible + ' of ' + findings.length + ' flagged checks across ' + visibleGroups +
      (visibleGroups === 1 ? ' topic' : ' topics');
    empty.hidden = visible !== 0 || findings.length === 0;
  }
  search.addEventListener('input', filter);
  [severity, mode, suite].forEach(input => input.addEventListener('change', filter));
  document.getElementById('reset-filters').addEventListener('click', function () {
    search.value = severity.value = mode.value = suite.value = ''; filter(); search.focus();
  });
  document.getElementById('expand-all').addEventListener('click', function () {
    detailPanels.filter(item => !item.hidden && !item.closest('.finding-group').hidden).forEach(item => {item.open = true;});
  });
  document.getElementById('collapse-all').addEventListener('click', function () {
    detailPanels.forEach(item => {item.open = false;});
  });
  function preparePrint() {
    if (printState) return;
    // Printing includes all flagged checks, even those hidden by a screen filter.
    // Save the current view so it can be restored after the print dialog closes.
    printState = [...new Set(sections.concat(groups, detailPanels))].map(item => [item, item.open, item.hidden]);
    printState.forEach(([item]) => {item.hidden = false; if (item.tagName === 'DETAILS') item.open = true;});
    groups.forEach(function (group) {
      const total = Number(group.dataset.total);
      group.querySelector('.group-count').textContent = total + (total === 1 ? ' check' : ' checks');
      group.querySelector('.details-count').textContent = total;
      group.querySelector('.details-unit').textContent = total === 1 ? 'check' : 'checks';
    });
    empty.hidden = true;
  }
  function finishPrint() {
    if (!printState) return;
    printState.forEach(([item, open, hidden]) => {if (item.tagName === 'DETAILS') item.open = open; item.hidden = hidden;});
    printState = null; filter();
  }
  window.addEventListener('beforeprint', preparePrint);
  window.addEventListener('afterprint', finishPrint);
  document.getElementById('print-report').addEventListener('click', function () {window.print();});
  filter();
})();
"""


# HTML rendering of the unchanged findings and explanation text.


def _icon(kind):
    paths = {
        "download": '<path d="M8 2v8m-3-3 3 3 3-3M3 11v3h10v-3"/>',
        "print": '<path d="M4 6V2h8v4M4 11H2V6h12v5h-2M4 9h8v5H4z"/>',
        "file": '<path d="M9 1H3v14h10V5L9 1zM9 1v4h4M5 8h6M5 11h4"/>',
    }
    return '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true">' + paths[kind] + '</svg>'


def _evidence_link(value, output_dir):
    """Link to recorded evidence, preferring portable paths inside the report folder."""
    path = Path(value)
    try:
        relative = path.relative_to(output_dir).as_posix()
        href = quote(relative, safe="/")
        display = relative
    except ValueError:
        href = path.as_uri() if path.is_absolute() else quote(str(path), safe="/")
        display = str(path)
    return ('<li><a class="evidence-link" href="' + escape(href, quote=True) + '">' + _icon("file") +
            '<span><strong>' + escape(path.name or str(path)) + '</strong><small>' + escape(display) +
            '</small></span></a></li>')


def _options(values, label):
    return '<option value="">' + label + '</option>' + ''.join(
        '<option value="' + escape(value, quote=True) + '">' + escape(value) + '</option>'
        for value in sorted(values))


def _topic_key(item):
    """Combine related display topics without merging or dropping assertions."""
    if item.check_id in SCHEMA_CHECKS:
        return "json-format"
    if item.check_id in STATUS_CHECKS:
        return "input-status"
    return item.check_id


def _suite_names(value):
    return sorted({name.strip() for name in value.split(",") if name.strip()})


def _comparison_html(rows):
    if not rows:
        return ""
    return ('<table class="result-comparison"><thead><tr><th>Where</th><th>Should show</th>'
            '<th>Report shows</th></tr></thead><tbody>' + ''.join(
                '<tr>' + ''.join('<td>' + escape(str(value)) + '</td>' for value in row) + '</tr>'
                for row in rows) + '</tbody></table>')


def _finding_html(item, number, output_dir, topic_title, original_title):
    """Show one check's explanation beside its unchanged technical evidence."""
    explanation = describe_finding(item)
    searchable = ' '.join(map(str, (topic_title, original_title, item.check_id, item.issue,
                                    item.expected, item.actual, item.mode, item.suite,
                                    explanation["title"], explanation["observed"], *item.evidence))).lower()
    chips = ''.join('<span class="context-chip">' + escape(value) + '</span>'
                    for value in (item.mode or "Repository", item.suite) if value)
    evidence = ('<p class="evidence-heading">Logs, files and reproduction '
                'commands</p><ul class="evidence-list">' +
                ''.join(_evidence_link(value, output_dir) for value in item.evidence) + '</ul>'
                if item.evidence else '<p class="no-evidence">No evidence files recorded for this check.</p>')
    scenario = ('<p class="input-scenario"><strong>Input checked: </strong>' + escape(explanation["scenario"]) +
                '</p>') if explanation.get("scenario") else ''
    readable = _comparison_html(explanation.get("comparisons")) or (
        '<p class="finding-observed"><strong>What Doctor found: </strong>' + escape(explanation["observed"]) + '</p>')
    return ('<details class="finding" data-severity="' + item.status + '" data-check-id="' +
            escape(item.check_id, quote=True) + '" data-mode="' + escape(item.mode, quote=True) +
            '" data-suite="' + escape(item.suite, quote=True) + '" data-suites="' +
            escape(json.dumps(_suite_names(item.suite) or ["General"]), quote=True) + '" data-search="' +
            escape(searchable, quote=True) + '"><summary class="finding-heading"><span class="case-number">' +
            f'{number:02d}' + '</span><span class="finding-title">' + escape(explanation["title"]) +
            '</span>' + chips + '</summary><div class="finding-body">' + scenario +
            readable +
            '<details class="technical-data"><summary>Original check data</summary><p '
            'class="original-issue"><span class="technical-id">' +
            escape(item.check_id) + '</span><br>' + escape(item.issue) + '</p>' +
            '<div class="comparison"><section class="comparison-panel"><h4>Expected '
            'by the check</h4><pre>' +
            escape(item.expected) + '</pre></section><section class="comparison-panel '
                'actual"><h4>Recorded result</h4><pre>' +
            escape(item.actual) + '</pre></section></div></details>' + evidence + '</div></details>')


def render_html(findings, metadata, output_dir, status, counts, group_titles):
    """Build the HTML page without recalculating any check result or total."""
    output_dir = Path(output_dir)
    findings = list(findings)
    # Successful checks remain in doctor.json. The review page focuses on failures,
    # blocked checks and warnings so readers can find what needs attention.
    actionable = [item for item in findings if item.status != "PASS"]
    groups = defaultdict(list)
    for item in actionable:
        groups[item.status, _topic_key(item)].append(item)
    section_definitions = (
        ("issues", "Failed checks", "Start here",
         "These checks failed. Each topic explains the observation and what to investigate."),
        ("blocked", "Checks that could not run", "Not verified",
         "These checks were blocked. They are not counted as passed."),
        ("warnings", "Warnings and coverage limits", "Review next",
         "These need a policy decision, more test coverage or an environment check. A "
         "warning is not proof of a parser defect."),
        ("summaries", "Report package summaries", "Read with the findings above",
         "These are package-level results. They can repeat individual findings and "
         "are not automatically additional bugs."),
    )
    section_cards = defaultdict(list)
    section_counts = defaultdict(int)
    for (severity, topic), items in sorted(groups.items(), key=lambda row: row[0]):
        check_ids = sorted({item.check_id for item in items})
        description = describe_group(check_ids, items)
        section = ("summaries" if description["category"] == "summaries" else
                   "blocked" if severity == "BLOCKED" else
                   "warnings" if severity == "WARN" else "issues")
        modes = ' / '.join(sorted({item.mode or "Repository" for item in items}))
        suites = sorted({name for item in items for name in _suite_names(item.suite)})
        context = modes + (' · ' + ', '.join(suites) if suites else ' · Report / repository checks')
        if "ARTIFACT.SCHEMA" in check_ids and suites:
            context += ' · plus saved report files'
        context_html = escape(context)
        if len(suites) > 6:
            context_html = (escape(modes) + ' · <details class="affected-list"><summary>' +
                            str(len(suites)) + ' affected suites</summary><p>' +
                            escape(', '.join(suites)) + '</p></details>')
        rows = ''.join(_finding_html(item, number, output_dir, description["title"],
                                   group_titles.get((item.status, item.check_id), item.issue))
                       for number, item in enumerate(items, 1))
        explanations = ''.join('<div><dt>' + label + '</dt><dd>' + escape(description[key]) + '</dd></div>'
                               for label, key in (("What happened", "happened"),
                                                  ("Why it matters", "impact"), ("Next step", "next_step")))
        examples, seen = [], set()
        # A short preview helps readers understand the topic. Every underlying
        # assertion is still available in the expandable evidence section.
        for item in items:
            observation = describe_finding(item)
            if observation["observed"] in seen:
                continue
            seen.add(observation["observed"])
            label = ' · '.join(value for value in (item.mode, item.suite) if value)
            scenario = ('<p class="input-scenario">' + escape(observation["scenario"]) + '</p>'
                        if observation.get("scenario") else '')
            readable = (_comparison_html(observation.get("comparisons")) or
                        '<p>' + escape(observation["observed"]) + '</p>')
            examples.append('<div class="example"><p><strong>' + escape(label or observation["title"]) +
                            '</strong></p>' + scenario + readable + '</div>')
            if len(examples) == 3:
                break
        example_html = ('<div class="topic-examples"><h4>Examples from this run</h4>' +
                        ''.join(examples) + '</div>')
        section_cards[section].append(
            '<article class="finding-group ' + severity.lower() +
            (' summary-group' if section == "summaries" else '') + '" data-severity="' + severity +
            '" data-topic="' + escape(topic, quote=True) + '" data-check-id="' +
            escape(' '.join(check_ids), quote=True) + '" data-total="' + str(len(items)) +
            '"><header class="group-heading"><span class="badge ' + severity.lower() + '">' + severity +
            '</span><div class="group-copy"><h3 class="group-title">' + escape(description["title"]) +
            '</h3><div class="group-meta">Affected: ' + context_html +
            '</div></div><span class="group-count">' + str(len(items)) +
            (' check' if len(items) == 1 else ' checks') + '</span></header><dl class="group-explanation">' +
            explanations + '</dl>' + example_html + '<details class="group-checks"><summary><span>View ' +
            '<span class="details-count">' + str(len(items)) + '</span> ' +
            '<span class="details-unit">' + ('check' if len(items) == 1 else 'checks') + '</span>' +
            ' &amp; supporting evidence</span></summary><div class="group-content">' +
            '<p class="group-hint">Original check IDs, expected results and recorded '
            'observations are preserved below.</p>' +
            rows + '</div></details></article>')
        section_counts[section] += len(items)

    section_html, nav_html = [], []
    for key, title, kicker, subtitle in section_definitions:
        if not section_cards[key]:
            continue
        identifier = key + "-section"
        nav_html.append('<a href="#' + identifier + '">' + title + '<strong>' +
                        str(section_counts[key]) + '</strong></a>')
        section_html.append('<section class="findings-section" id="' + identifier +
                            '" aria-labelledby="' + identifier + '-heading"><div class="section-heading"><div>' +
                            '<p class="section-kicker">' + kicker + '</p><h2 id="' + identifier + '-heading">' +
                            title + '</h2><p class="section-description">' + subtitle + '</p></div></div>' +
                            ''.join(section_cards[key]) + '</section>')

    revision = str(metadata.get("revision") or "Not recorded")
    short_revision = revision[:12] if len(revision) >= 12 and all(
        char in '0123456789abcdefABCDEF' for char in revision) else revision
    modes = ' / '.join(metadata.get("modes") or []) or "Not recorded"
    started = str(metadata.get("started_utc") or "Not recorded")
    try:
        parsed = datetime.fromisoformat(started.replace('Z', '+00:00'))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)
        started = parsed.strftime('%d %b %Y · %H:%M UTC')
    except ValueError:
        pass
    total = sum(counts.values())
    metrics = ['<div class="metric"><span class="metric-label">Total '
               'checks</span><strong class="metric-value">' + f'{total:,}' + '</strong></div>']
    for key, label in (("PASS", "Passed"), ("FAIL", "Failed checks"), ("WARN", "Warnings"), ("BLOCKED", "Not verified")):
        number = counts.get(key, 0)
        metrics.append('<div class="metric ' + key.lower() + '" data-count-status="' + key + '" data-count="' + str(number) +
                       '"><span class="metric-label"><span class="metric-dot"></span>' + label +
                       '</span><strong class="metric-value">' + f'{number:,}' + '</strong></div>')
    empty_message = ('<section class="empty-state"><h3>No findings to '
                     'review</h3><p>All recorded checks passed. '
                     'See the JSON report for every assertion and its '
                     'evidence.</p></section>' if total else
                     '<section class="empty-state"><h3>No checks were '
                     'recorded</h3><p>This run is incomplete; '
                     'a lack of findings is not a passing result.</p></section>')
    fields = (("Revision", revision), ("Modes", modes),
              ("Check groups", ', '.join(metadata.get("check_groups") or []) or "Not recorded"),
              ("Started", started), ("Parser source", metadata.get("parser_dir")),
              ("Python", metadata.get("python")), ("Scope", metadata.get("scope")),
              ("Worktree", metadata.get("worktree_status")))
    metadata_html = ''.join('<div><dt>' + name + '</dt><dd><pre>' + escape(str(value or "Not recorded")) +
                            '</pre></dd></div>' for name, value in fields)
    tone = 'fail' if status == 'FAIL' else 'blocked' if status == 'INCOMPLETE' else 'pass'
    human_status = "Needs attention" if status == "FAIL" else "Checks incomplete" if status == "INCOMPLETE" else "Checked scope passed"
    presentation_note = ('<p class="presentation-note">' + escape(str(metadata["presentation_note"])) + '</p>'
                         if metadata.get("presentation_note") else '')
    guide = ('<section class="review-guide" aria-label="How to read this '
             'report"><h2>What needs attention?</h2>'
             '<p>Start with the failed topics, then review warnings. <strong>Several '
             'failed checks can describe the same problem.</strong> '
             'Package summaries are listed separately. Open the evidence only when '
             'you need the technical detail.</p>'
             '<nav class="quick-nav" aria-label="Finding sections">' + ''.join(nav_html) + '</nav></section>') if actionable else ''
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Log parser doctor · Health report</title><style>' + STYLE + '</style></head><body>'
            '<a class="skip-link" href="#findings">Skip to findings</a><main class="shell">'
            '<header class="hero"><div class="hero-top"><div><p '
            'class="eyebrow">SYSTEMREADY ACS · REPOSITORY HEALTH</p>'
            '<h1>Log parser health report</h1><p class="hero-description">What '
            'happened, why it matters, and what to check next.</p></div>'
            '<div class="verdict ' + tone + '"><span class="verdict-label">DOCTOR RESULT · ' + escape(status) +
            '</span><strong class="verdict-value">' + human_status +
            '</strong></div></div><div class="hero-bottom"><div class="run-meta">'
            '<span>Revision <code title="' +
                escape(revision, quote=True) + '">' + escape(short_revision) + '</code></span>'
            '<span>Modes <strong>' +
                escape(modes) + '</strong></span><span>Tested ' + escape(started) + '</span></div>'
            '<nav class="exports" aria-label="Report exports"><a class="button" '
            'href="doctor.json">' + _icon("download") +
            'All checks · JSON</a><a class="button" href="doctor.md">' +
                _icon("file") + 'Original findings · Text</a>'
            '<button type="button" class="button primary js-only" id="print-report">' + _icon("print") +
            'Print / PDF</button></nav></div>' + presentation_note + '</header>'
            '<section class="metrics" aria-label="Check totals">' + ''.join(metrics) + '</section>'
            '<div class="scope-note"><span class="info-icon" aria-hidden="true">i</span><p>'
            '<strong>These are parser-health checks, not hardware test '
            'results.</strong> Counts are assertions, not distinct bugs. '
            'Blocked checks have not been verified.</p></div>' + guide +
            '<section id="findings" aria-label="Findings"><div class="filter-panel">'
            '<div class="filters js-only"><div class="field"><label '
            'for="doctor-search">Find a topic or test suite</label>'
            '<input id="doctor-search" type="search" placeholder="For example: SBMR, '
            'missing description, PDF…" autocomplete="off"></div>'
            '<div class="field"><label for="severity-filter">Check '
            'status</label><select id="severity-filter">'
            '<option value="">All findings</option><option '
            'value="FAIL">Failed</option><option value="WARN">Warnings</option>'
            '<option value="BLOCKED">Not verified</option></select></div>'
            '<div class="field"><label for="mode-filter">Mode</label><select id="mode-filter">' +
            _options({item.mode or "Repository" for item in actionable},
                     'All modes') + '</select></div>'
            '<div class="field"><label for="suite-filter">Suite recorded by '
            'check</label><select id="suite-filter">' +
            _options({name for item in actionable for name in (_suite_names(
                item.suite) or ["General"])}, 'All suites') + '</select></div></div>'
            '<div class="toolbar-bottom"><p class="match-count" id="match-count" '
            'role="status" aria-live="polite">'
            'Showing all ' + str(len(actionable)) +
                                 ' flagged checks</p><div class="toolbar-actions js-only">'
            '<button class="button" type="button" id="expand-all">Open all evidence</button>'
            '<button class="button" type="button" id="collapse-all">Close all evidence</button>'
            '<button class="button quiet" type="button" id="reset-filters">Reset '
            'filters</button></div></div>'
            '<noscript><p class="section-description">All explanations are visible '
            'below. You can open evidence without JavaScript.</p></noscript></div>'
            '<p class="print-note">All flagged checks and evidence are included, even '
            'if filtered or collapsed on screen. '
            'Passed checks remain in the JSON report.</p>' + (''.join(section_html) if groups else empty_message) +
            '<section class="empty-state" id="no-matches" hidden><h3>No matching findings</h3>'
            '<p>Try a different search or reset the filters. The recorded check '
            'totals above are unchanged.</p></section></section>'
            '<details class="run-details"><summary>Run details &amp; '
            'provenance</summary><dl class="metadata-grid">' + metadata_html +
            '</dl></details><footer><span>SYSTEMREADY ACS · LOG PARSER DOCTOR</span>'
            '<span>All recorded results are retained. Explanations do not change '
            'check outcomes.</span></footer></main>'
            '<script id="doctor-interactions">' + SCRIPT + '</script></body></html>')
