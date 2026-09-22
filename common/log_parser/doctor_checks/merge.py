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

"""Check that merged JSON and HTML show the expected compliance decisions.

This optional Doctor group builds small sample suite results, runs the checkout's
real merger and HTML helpers, and records expected versus actual results. Expected
answers are written here separately so a parser mistake cannot define its own
passing answer. Samples and findings stay in Doctor's evidence folder; this file
does not repair the parser or change real logs. Raw-log and schema checks live in
other Doctor groups.
"""

import contextlib
import copy
import html
from html.parser import HTMLParser
import importlib
import itertools
import json
from pathlib import Path
import re
import sys

from .core import load_json


# These reviewed expectations must not be copied from the registry at runtime:
# otherwise an incorrect registry entry would also change the expected answer.
# Suite inventory: CI b6a8a78d1fef3d6e41d2d2aec94006e0a9263c8c.
# DT memory-map requirements: upstream decc0aaa9902da57b18d5fd3ec40efa511fb5273.
# PCIe Option ROM: SR-only Recommended, reviewed in PJ03164-4076/719dab25.
# The scenarios below also check SR rules that become Mandatory when present.

EXPECTED_REQUIREMENTS = {
    "BSA": {"DT": "R", "SR": "M"},
    "SBSA": {"SR": "R"},
    "FWTS": {"DT": "M", "SR": "M"},
    "SCT": {"DT": "M", "SR": "M"},
    "BBSR-FWTS": {"DT": "EM", "SR": "EM"},
    "BBSR-SCT": {"DT": "EM", "SR": "EM"},
    "BBSR-TPM": {"DT": "EM", "SR": "EM"},
    "PFDI": {"DT": "CM"},
    "SCMI": {"DT": "EM"},
    "SBMR-IB": {"SR": "R"},
    "SBMR-OOB": {"SR": "R"},
    "POST-SCRIPT": {"DT": "R"},
    "OS-TESTS": {"DT": "M", "SR": "M"},
    "DT-KSELFTEST": {"DT": "R"},
    "DT-VALIDATE": {"DT": "M"},
    "ETHTOOL-TEST": {"DT": "M"},
    "READ-WRITE-CHECK-BLK-DEVICES": {"DT": "M"},
    "CAPSULE-UPDATE": {"DT": "M"},
    "PSCI": {"DT": "R"},
    "SMBIOS": {"DT": "R"},
    "NETWORK-BOOT": {"DT": "R"},
    "RUNTIME-DEV-MAP": {"DT": "R"},
    "RESERVED-MEMORY-MAP": {"DT": "M"},
    "DTB-ALIGNMENT": {"DT": "M"},
    "PCIE-OPTION-ROM-ARCH-AUDIT": {"SR": "R"},
}


def expected_leaves(leaves):
    """Use registered file names, but use our reviewed requirement expectations."""
    result = []
    for suite in leaves:
        if suite["canonical"] not in EXPECTED_REQUIREMENTS:
            continue  # Explicitly reported by POLICY_INVENTORY, never assumed covered.
        expected = copy.deepcopy(suite)
        expected["requirements"] = dict(EXPECTED_REQUIREMENTS[suite["canonical"]])
        expected["modes"] = list(expected["requirements"])
        result.append(expected)
    return result


def policy_differences(registry):
    """Detect metadata drift and new suites that need independently reviewed tests."""
    leaves = {suite["canonical"]: suite for suite in registry["suites"]
              if suite.get("json_output")}
    issues = []
    for name in sorted(set(leaves) | set(EXPECTED_REQUIREMENTS)):
        expected = EXPECTED_REQUIREMENTS.get(name)
        actual = leaves.get(name)
        if expected is None:
            issues.append((name, "Reviewed requirement contract and fixture",
                           "New suite has no independent policy expectation"))
        elif actual is None:
            issues.append((name, expected, "Expected suite missing from registry"))
        elif actual.get("requirements") != expected or set(actual.get("modes", [])) != set(expected):
            issues.append((name, {"requirements": expected, "modes": sorted(expected)},
                           {"requirements": actual.get("requirements"), "modes": actual.get("modes")}))
    return issues


def run_policy(ctx):
    """Report new suites or changed requirements that need a reviewed expectation."""
    source = ctx.parser_dir / "suite_registry.json"
    registry = load_json(source)
    issues = policy_differences(registry)
    if issues:
        for name, expected, actual in issues:
            ctx.add("POLICY_INVENTORY", "FAIL",
                    "Registry and independent requirement contract disagree; review before updating expectations",
                    expected, actual, suite=name, evidence=(source, __file__))
    else:
        ctx.add("POLICY_INVENTORY", "PASS", "All suites have independently reviewed base requirements",
                "Exact suite/mode/requirement mapping", "%d suites, %d suite/mode routes match" %
                (len(EXPECTED_REQUIREMENTS), sum(map(len, EXPECTED_REQUIREMENTS.values()))),
                evidence=(source, __file__))


# Sample combinations for the real merger and the visible HTML compliance labels.

REQUIREMENTS = {"M": "Mandatory", "R": "Recommended",
                "CM": "Conditional-Mandatory", "EM": "Extension"}
UNAVAILABLE = {"missing", "empty", "header"}
STATES = ("pass", "fail", "waived", "mixed", "missing", "empty", "header")
HTML_HELPERS = ("_summary_cards", "inject_detail_compliance")


def usable_html_module(ctx):
    """Check HTML support without stopping the separate merged-JSON checks."""
    try:
        ui = importlib.import_module("generate_acs_summary")
        if Path(ui.__file__).resolve().parent != ctx.parser_dir.resolve():
            raise ValueError("Refusing cached UI module from another checkout: " + str(ui.__file__))
        missing = [name for name in HTML_HELPERS if not callable(getattr(ui, name, None))]
        if not missing:
            return ui
        reason = "This checkout does not provide " + ", ".join(missing)
    except Exception as error:
        reason = type(error).__name__ + ": " + str(error)
    ctx.add("HTML_COMPLIANCE_CAPABILITY", "BLOCKED",
            "Summary/detail compliance HTML coverage is unavailable; merged JSON checks still run.",
            "Importable current-checkout HTML compliance helpers", reason,
            evidence=(ctx.parser_dir / "generate_acs_summary.py",))
    return None


def identity(value):
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def status(value, overall=False):
    """Interpret a public label; do not call the production compliance helpers."""
    value = str(value).strip().lower()
    if "not run" in value and not overall:
        return "not_run"
    for prefix, normalized in (("not compliant", "not_compliant"),
                               ("compliant with waiver", "waived"),
                               ("compliant", "compliant"), ("not run", "not_run")):
        if value.startswith(prefix):
            return normalized
    return "unknown"


def display_name(key, mode):
    if key in ("FWTS", "SCT"):
        return ("EBBR-" if mode == "DT" else "SBBR-") + key
    return key


def oracle(leaves, mode, states, selected=None, override=None, executed=None):
    """Calculate the agreed answer without using the parser's compliance code.

    Recommended failures or missing results never block overall SRS compliance.
    Required SR OS entries alone affect OS compliance. Executed SBSA and either
    executed SBMR interface promote the relevant SR requirements to Mandatory.
    Conditional-Mandatory is required when run; extensions have separate results.
    When supplied, executed contains independently proven current-run execution;
    missing result JSON must not erase that proof. Without it, existing synthetic
    scenarios use their known result states. The not_run row describes unavailable
    report results, not a claim that a proven execution never happened.
    This is an explicit repository contract, not an external certification claim.
    """
    applicable = {suite["canonical"]: suite for suite in leaves
                  if mode in suite["modes"] and mode in suite["requirements"]
                  and (selected is None or suite["canonical"] in selected)}
    if executed is None:
        present = {name for name, state in states.items() if state not in UNAVAILABLE}
    else:
        # Only proof for a suite in this mode can activate its requirements.
        # A selected SBMR interface can still depend on its executed peer.
        mode_suites = {suite["canonical"] for suite in leaves
                       if mode in suite["modes"] and mode in suite["requirements"]}
        present = set(executed).intersection(mode_suites)
    rows = {}
    blockers, waivers = False, False
    for name, suite in applicable.items():
        requirement = (override or {}).get(name, suite["requirements"][mode])
        if mode == "SR" and ((name == "SBSA" and name in present) or
                             (name.startswith("SBMR-") and
                              present.intersection({"SBMR-IB", "SBMR-OOB"}))):
            requirement = "M"
        state = states.get(name, "missing")
        result = "compliant"
        if state in UNAVAILABLE:
            result = "not_run"
            blockers |= requirement == "M" or (requirement == "CM" and name in present)
        elif state in ("fail", "mixed", "recommended_fail"):
            if not (mode == "SR" and name == "OS-TESTS" and state == "recommended_fail"):
                result = "not_compliant"
                blockers |= requirement in ("M", "CM")
        elif state == "waived":
            result = "waived"
            waivers |= requirement in ("M", "CM")
        elif state != "pass":
            raise ValueError("No agreed compliance oracle for state " + state)
        rows[name] = {"requirement": REQUIREMENTS[requirement], "status": result}
    return rows, "not_compliant" if blockers else "waived" if waivers else "compliant"


def payload(name, state):
    """Make one small suite input in the nesting that its real parser uses."""
    if state == "missing":
        return None
    if state == "empty":
        return {"suite_summary": {}, "test_results": []}
    if state == "header":
        return {"test_results": [{"Test_suite": name, "subtests": []}]}
    outcomes = {"pass": ["PASSED"], "fail": ["FAILED"],
                "waived": ["FAILED (WITH WAIVER)"],
                "mixed": ["FAILED (WITH WAIVER)", "FAILED"],
                "recommended_fail": ["FAILED"]}[state]
    counts = dict.fromkeys(("total_passed", "total_failed", "total_failed_with_waiver",
                           "total_aborted", "total_skipped", "total_warnings",
                           "total_ignored"), 0)
    keys = {"PASSED": "total_passed", "FAILED": "total_failed",
            "FAILED (WITH WAIVER)": "total_failed_with_waiver"}
    for result in outcomes:
        counts[keys[result]] += 1
    if name == "PCIE-OPTION-ROM-ARCH-AUDIT":
        # PCIe reports one parent decision per audit. Its merger reads that
        # decision, while its HTML uses the Standalone-style child counters.
        entries = []
        for result in outcomes:
            record_counts = dict.fromkeys(counts, 0)
            record_counts[keys[result]] = 1
            entries.append({
                "Test_suite": "PCIeOptionRomArchAudit",
                "Test_case": "pcie_option_rom_arch_audit",
                "SRS scope": "Recommended", "Waivable": "yes",
                "test_result": result, "test_suite_summary": record_counts,
                "subtests": [{"sub_Test_Number": "1",
                    "sub_Test_Description": "PCIe Option ROM UEFI driver architecture compliance",
                    "sub_test_result": {
                        "PASSED": int(result == "PASSED"),
                        "FAILED": int(result == "FAILED"),
                        "FAILED_WITH_WAIVER": int(result == "FAILED (WITH WAIVER)"),
                        "ABORTED": 0, "SKIPPED": 0, "WARNINGS": 0}}],
            })
        return {"suite_summary": counts, "test_results": entries}
    entry = {"Test_suite": "TIMER" if name in ("BSA", "SBSA", "PFDI") else name,
             "Test_case": name, "Waivable": "yes",
             "SRS scope": "Recommended" if state == "recommended_fail" else "Required",
             "test_suite_summary": dict(counts)}
    children = [{"sub_Test_Number": str(index), "sub_Test_Description": "Doctor fixture",
                 "sub_test_result": result, "reason": "Doctor approved waiver" if
                 "WAIVER" in result else ""} for index, result in enumerate(outcomes, 1)]
    if name in ("BSA", "SBSA", "PFDI"):
        # A parent and its child describe one outcome, not two separate tests.
        entry["testcases"] = [{"Test_case": str(index), "Test_case_description": "Doctor fixture",
                                "Test_result": result, "subtests": [children[index - 1]]}
                               for index, result in enumerate(outcomes, 1)]
    elif name.startswith("SBMR-"):
        entry["Test_cases"] = [{"Test_case": "Doctor management case", "subtests": children,
                                 "test_case_summary": dict(counts)}]
    else:
        entry["subtests"] = children
    return {"suite_summary": counts, "test_results": [entry]}


def merged_records(merged, leaves, mode):
    """Read each suite's requirement and compliance from the merged report."""
    summary = merged["Suite_Name: acs_info"]["ACS Results Summary"]
    if not isinstance(summary, dict) or "Overall Compliance Result" not in summary:
        raise ValueError("Merged report has no ACS compliance summary")
    names = {identity(display_name(suite["requirement_key"], mode)): suite["canonical"]
             for suite in leaves}
    rows = {}
    for key, value in summary.items():
        match = re.fullmatch(r"Suite_Name:\s*(.*?)\s*:\s*(.*?)_compliance", key)
        if match and identity(match.group(2)) in names:
            name = names[identity(match.group(2))]
            if name in rows:
                raise ValueError("Duplicate compliance label for " + name)
            rows[name] = {"requirement": match.group(1).strip(), "status": status(value)}
    return rows, summary


def differences(expected, actual):
    """List missing, unexpected or changed values with both sides for the report."""
    return {key: {"expected": expected.get(key, "absent"), "actual": actual.get(key, "absent")}
            for key in sorted(set(expected) | set(actual)) if expected.get(key) != actual.get(key)}


class ComplianceHTML(HTMLParser):
    """Read visible compliance table cells and badges without a browser."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.badges, self.row, self.cell = [], [], None, None
        self.badge_depth, self.badge_text = 0, ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and "data-acs-compliance-tone" in attrs:
            self.row = []
        if self.row is not None and tag in ("th", "td"):
            self.cell = ""
        if self.badge_depth:
            self.badge_depth += 1
        elif "acs-suite-compliance" in attrs.get("class", "").split():
            self.badge_depth, self.badge_text = 1, ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data
        if self.badge_depth:
            self.badge_text += data

    def handle_endtag(self, tag):
        if self.cell is not None and tag in ("th", "td"):
            self.row.append(" ".join(self.cell.split()))
            self.cell = None
        if self.row is not None and tag == "tr":
            self.rows.append(tuple(self.row))
            self.row = None
        if self.badge_depth:
            self.badge_depth -= 1
            if not self.badge_depth:
                self.badges.append(" ".join(self.badge_text.split()))


def aggregate(rows):
    """Work out the expected badge for a card containing one or several suites."""
    mandatory = [row for row in rows if row["requirement"] in
                 ("Mandatory", "Conditional-Mandatory")]
    relevant = mandatory or rows
    requirements = {row["requirement"] for row in relevant}
    requirement = "Mandatory" if "Mandatory" in requirements else " / ".join(sorted(requirements))
    if all(row["status"] == "not_run" for row in rows):
        result = "Not Run"
    elif any(row["status"] == "not_compliant" or (row["status"] == "not_run" and
             row["requirement"] == "Mandatory") for row in relevant):
        result = "Not Compliant"
    elif any(row["status"] == "waived" for row in relevant):
        result = "Compliant with waivers"
    else:
        result = "Compliant"
    return requirement + " (" + result + ")"


def check_html(ui, directory, merged_path, leaves, mode, states, expected, standalone):
    """Compare generated summary badges and detail rows with our expected labels."""
    output = directory / "html"
    output.mkdir()
    by_name = {suite["canonical"]: suite for suite in leaves}
    collected = {name for name in expected if states.get(name, "missing") not in UNAVAILABLE}
    groups = {}
    for name in expected:
        # SBMR interfaces and Standalone tests share a card but retain their rows.
        group = "Standalone" if name in standalone else "SBMR" if name.startswith("SBMR-") else name
        groups.setdefault(group, []).append(name)
    sources, desired_badges, desired_rows = [], {}, {}
    for group, names in groups.items():
        detail = ("sbmr_detailed.html" if group == "SBMR" else
                  "standalone_tests_detailed.html" if group == "Standalone" else by_name[names[0]]["detailed_html"])
        present = any(name in collected for name in names)
        if present:
            (output / detail).write_text("<html><body><h1>Doctor semantic fixture</h1></body></html>", encoding="utf-8")
        section = {"Standalone": "standalone_summary", "OS-TESTS": "OS_tests_summary"}.get(group, group.lower() + "_summary")
        content = "<h1>" + html.escape(group) + " Test Summary</h1>" if present else ""
        candidates = tuple(display_name(by_name[name]["requirement_key"], mode) for name in names)
        sources.append((section, group, content, detail, candidates))
        desired_badges[group] = aggregate([expected[name] for name in names])
        for name in names:
            row = expected[name]
            # Missing mandatory Standalone tests and missing SBMR interfaces must
            # remain visible inside an existing combined detail page.
            visible = name in collected or (present and (group == "SBMR" or
                       (group == "Standalone" and row["requirement"] == "Mandatory")))
            if not visible:
                continue
            component = display_name(name, mode) if name in ("FWTS", "SCT") else name
            if name == "PCIE-OPTION-ROM-ARCH-AUDIT":
                component = "PCIE_OPTION_ROM_ARCH_AUDIT"
            label = {"compliant": "Compliant", "not_compliant": "Not Compliant",
                     "waived": "Compliant with waivers", "not_run": "Not Run"}[row["status"]]
            if row["status"] == "not_run" and row["requirement"] == "Mandatory":
                label = "Not Compliant (Not Run)"
            desired_rows.setdefault(detail, []).append((component, row["requirement"], label))
    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    cards = ui._summary_cards(merged, sources, str(output))
    actual_badges = {}
    for card in cards:
        parser = ComplianceHTML()
        parser.feed(card["content"])
        actual_badges[card["label"]] = parser.badges[0] if len(parser.badges) == 1 else parser.badges
    (output / "summary_badges.html").write_text("<html><body><p>Synthetic semantic fixture, not a hardware report.</p>" +
        "".join(card["content"] for card in cards) + "</body></html>", encoding="utf-8")
    ui.inject_detail_compliance(str(merged_path), str(output))
    actual_rows = {}
    for page in output.glob("*detailed.html"):
        parser = ComplianceHTML()
        parser.feed(page.read_text(encoding="utf-8"))
        actual_rows[page.name] = sorted(parser.rows)
    desired_rows = {name: sorted(rows) for name, rows in desired_rows.items()}
    return {"badges": differences(desired_badges, actual_badges),
            "tables": differences(desired_rows, actual_rows)}


def scenarios(leaves, mode):
    """Vary each suite and requirement, then check combined SBMR and BBSR cases."""
    suites = [suite["canonical"] for suite in leaves if mode in suite["requirements"] and mode in suite["modes"]]
    baseline = dict.fromkeys(suites, "pass")
    for name in suites:
        for selected in (None, [name]):
            for state in STATES:
                yield ("selected" if selected else "full") + "_" + name + "_" + state, \
                    {name: state} if selected else {**baseline, name: state}, selected, None
    for requirement in REQUIREMENTS:
        for state in STATES:
            yield "requirement_" + requirement + "_" + state, {**baseline, "FWTS": state}, None, {"FWTS": requirement}
    if mode == "SR":
        for ib, oob in itertools.product(("pass", "fail", "waived", "missing", "empty"), repeat=2):
            yield "SBMR_IB_" + ib + "_OOB_" + oob, {**baseline, "SBMR-IB": ib, "SBMR-OOB": oob}, None, None
        for bsa, sbsa in (("pass", "fail"), ("fail", "pass")):
            yield "BSA_" + bsa + "_SBSA_" + sbsa, {**baseline, "BSA": bsa, "SBSA": sbsa}, None, None
    for name in suites:
        yield "recommended_group_" + name, {**baseline, name: "recommended_fail"}, None, None
    bbsr = ("BBSR-FWTS", "BBSR-SCT", "BBSR-TPM")
    if set(bbsr).issubset(suites):
        for values in itertools.product(("pass", "fail", "waived", "missing"), repeat=3):
            yield "BBSR_" + "_".join(values), {**baseline, **dict(zip(bbsr, values))}, None, None


def run_case(ctx, registry, merger, ui, leaves, standalone, mode, case):
    """Run one sample and save its inputs, decisions and HTML comparisons."""
    name, states, selected, override = case
    directory = ctx.case_dir("merge/" + mode + "_" + name)
    write = lambda path, data: path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    manifest = {"synthetic": True, "scope": "merger and semantic HTML, not raw-log/schema acceptance",
                "mode": mode, "states": states, "selected": selected, "requirement_overrides": override}
    write(directory / "scenario.json", manifest)
    write(directory / "acs_info.json", {"ACS Results Summary": {"Date": "Doctor synthetic fixture", "Band":
          "SystemReady Devicetree band" if mode == "DT" else "SystemReady band"}})
    paths, original = [str(directory / "acs_info.json")], {}
    for suite in leaves:
        canonical = suite["canonical"]
        if canonical not in states:
            continue
        data = payload(canonical, states[canonical])
        if data is not None:
            path = directory / suite["json_output"]
            write(path, data)
            paths.append(str(path))
            original[path] = data
    # The merger stores run settings in module globals. Reset them for every
    # sample so a previous sample cannot decide this sample's result.
    merger.set_run_mode(mode)
    merger._REQUIREMENT_MAP = {}
    merger._SELECTED_SUITE_FILTER = merger.build_selected_suite_filter(selected or [])
    merger.DT_SRS_SCOPE_TABLE = registry.requirement_table("DT")
    merger.SR_SRS_SCOPE_TABLE = registry.requirement_table("SR")
    table = merger.DT_SRS_SCOPE_TABLE if mode == "DT" else merger.SR_SRS_SCOPE_TABLE
    table[:] = [(key, (override or {}).get(key, requirement)) for key, requirement in table]
    merged_path = directory / "merged_results.json"
    with (directory / "merge.log").open("w", encoding="utf-8") as stream, contextlib.redirect_stdout(stream):
        merger.merge_json_files(paths, str(merged_path))
    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    expected, overall = oracle(expected_leaves(leaves), mode, states, selected, override)
    actual, summary = merged_records(merged, leaves, mode)
    changed = differences(expected, actual)
    observation = {"expected_suites": expected, "actual_suites": actual, "expected_overall": overall,
                   "actual_overall": summary["Overall Compliance Result"], "suite_differences": changed,
                   "html_check": "not available" if ui is None else "pending"}
    write(directory / "observed.json", observation)
    focus = ", ".join(name for name, state in states.items() if state != "pass") or "all suites"
    evidence = (directory / "scenario.json", directory / "observed.json", merged_path, directory / "html")
    empty = any(state in ("empty", "header") for state in states.values())
    changed_expected = {suite: row["expected"] for suite, row in changed.items()}
    changed_actual = {suite: row["actual"] for suite, row in changed.items()}
    issue = "Empty/header-only input was marked as completed" if changed and empty else "Suite requirements and statuses agree with their evidence"
    if changed and not empty:
        issue = "Suite requirement or compliance differs from its own result"
    ctx.add("MERGE_INCOMPLETE_NOT_GREEN" if empty else "MERGE_SUITE_STATUS",
            "FAIL" if changed else "PASS", name + ": " + issue,
            changed_expected or "All applicable suite decisions match", changed_actual or "All match", mode, focus, evidence)
    actual_overall = status(summary["Overall Compliance Result"], overall=True)
    ctx.add("MERGE_OVERALL_POLICY", "PASS" if overall == actual_overall else "FAIL",
            name + (": Recommended result incorrectly blocks overall SRS" if overall == "compliant" and actual_overall == "not_compliant" else
                    ": overall SRS follows Mandatory results; Recommended and Extension are non-blocking"),
            overall, summary["Overall Compliance Result"], mode, focus, evidence)
    preserved = all(json.loads(path.read_text(encoding="utf-8")) == data for path, data in original.items())
    ctx.add("MERGE_INPUT_PRESERVED", "PASS" if preserved else "FAIL", name + ": merger must not alter input results",
            "Input suite JSON values unchanged", "Unchanged" if preserved else "Input suite JSON changed", mode, focus, evidence)
    if selected is None and all(name in states for name in ("BBSR-FWTS", "BBSR-SCT", "BBSR-TPM")):
        # BBSR is an extension with its own combined result, separate from SRS.
        values = [states[name] for name in ("BBSR-FWTS", "BBSR-SCT", "BBSR-TPM")]
        wanted = "not_run" if all(value in UNAVAILABLE for value in values) else "not_compliant" if any(
            value in UNAVAILABLE or value in ("fail", "mixed", "recommended_fail") for value in values) else "waived" if "waived" in values else "compliant"
        got = summary.get("BBSR compliance results", "MISSING")
        ctx.add("MERGE_EXTENSION_AGGREGATION", "PASS" if status(got, True) == wanted else "FAIL",
                name + ": BBSR aggregates its three members separately from SRS", wanted, got, mode, "BBSR", evidence)
    # Keep JSON assertions and their evidence even when the optional HTML stage
    # is absent, raises, or renders an incorrect compliance label.
    if ui is not None:
        try:
            html_changes = check_html(ui, directory, merged_path, leaves, mode, states, expected, standalone)
            observation.update(html_check="completed", html_differences=html_changes)
            ctx.add("HTML_COMPLIANCE_MATCH", "FAIL" if any(html_changes.values()) else "PASS",
                    name + ": summary badges and detail tables must agree with the independent compliance expectation",
                    "Exactly one correct badge/row for each applicable card/test",
                    html_changes if any(html_changes.values()) else "All labels match", mode, focus, evidence)
        except Exception as error:
            observation.update(html_check="failed", html_error=type(error).__name__ + ": " + str(error))
            ctx.add("HTML_COMPLIANCE_EXECUTION", "FAIL",
                    name + ": available HTML compliance generation failed; JSON checks were retained",
                    "Inspectable summary badges and detail compliance tables", observation["html_error"], mode, focus, evidence)
        write(directory / "observed.json", observation)


def edge_probes(ctx, merger, mode):
    """Check nested failure counts and whether invalid input is safely rejected."""
    parent = {"test_result": "FAILED", "subtests": []}
    probes = (
        ("SCT parent-only failures", {"test_results": [parent, dict(parent)]}, (2, 0)),
        ("SCT failure with outcome-less child header", {"test_results": [
            {"test_result": "FAILED", "subtests": [{"sub_Test_GUID": "unfinished"}]}]}, (1, 0)),
        ("Numeric failure and waiver counters", {"test_results": [{"subtests": [
            {"sub_test_result": {"FAILED": 2, "FAILED_WITH_WAIVER": 3}}]}]}, (2, 3)),
        ("Waived BSA parent remains authoritative", {"test_results": [{"testcases": [
            {"Test_result": "FAILED (WITH WAIVER)", "subtests": [{"sub_test_result": "FAILED"}]}]}]}, (0, 1)),
        ("Failed BSA parent with waived child remains failed", {"test_results": [{"testcases": [
            {"Test_result": "FAILED", "subtests": [{"sub_test_result": "FAILED (WITH WAIVER)"}]}]}]}, (1, 0)),
    )
    for index, (issue, data, wanted) in enumerate(probes):
        directory = ctx.case_dir("merge/" + mode + "_counter_" + str(index))
        observed = merger.count_fails_in_json(data)
        record = {"input": data, "expected_failed_waived": wanted, "actual_failed_waived": observed}
        (directory / "observed.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        ctx.add("MERGE_FAILURE_COUNT", "PASS" if tuple(observed) == wanted else "FAIL", issue,
                "Failed/waived=" + str(wanted), "Failed/waived=" + str(observed), mode,
                "SCT/BBSR-SCT" if issue.startswith("SCT") else "counter contract", (directory / "observed.json",))
    corrupt = {"test_results": "not a result list"}
    unknown = payload("SBMR-IB", "pass")
    unknown["test_results"][0]["Test_cases"][0]["subtests"][0]["sub_test_result"] = "UNKNOWN"
    unknown["suite_summary"]["total_passed"] = 0
    cases = [("BSA", "bsa.json", "invalid result shape", corrupt)]
    cases.append(("BSA", "bsa.json", "unknown result counter", {"test_results": [
        {"subtests": [{"sub_test_result": {"PASSED": 1, "UNKNOWN": 1}}]}]}))
    if mode == "SR":
        cases.append(("SBMR-IB", "sbmr_ib.json", "UNKNOWN outcome", unknown))
    for suite, filename, issue, data in cases:
        directory = ctx.case_dir("merge/" + mode + "_invalid_" + suite + "_" + issue.replace(" ", "-"))
        source, destination = directory / filename, directory / "merged_results.json"
        source.write_text(json.dumps(data, indent=2), encoding="utf-8")
        process = ctx.run([ctx.python, "-B", str(ctx.parser_dir / "merge_jsons.py"), "--mode", mode,
                           "--selected-suites", suite, str(destination), str(source)], directory)
        if process.returncode:
            controlled = "Traceback (most recent call last)" not in process.stdout
            result, actual = ("PASS" if controlled else "FAIL"), "Rejected input; exit " + str(process.returncode)
            if not controlled:
                actual += " with an uncaught traceback instead of a clear diagnostic"
        elif not destination.is_file():
            result, actual = "FAIL", "Exit 0 without a merged result or rejection diagnostic"
        else:
            summary = json.loads(destination.read_text(encoding="utf-8"))["Suite_Name: acs_info"]["ACS Results Summary"]
            value = next((value for key, value in summary.items() if key.endswith("  : " + suite + "_compliance")), "MISSING")
            result = "FAIL" if status(value) in ("compliant", "waived") or value == "MISSING" else "PASS"
            actual = value
        ctx.add("MERGE_INVALID_INPUT_SAFETY", result, suite + ": " + issue + " must not produce a green result",
                "Clear rejection or a non-green suite status", actual, mode, suite, (source, directory / "command.log", destination))


def run_merge(ctx):
    """Run all reviewed suite/mode cases, not just suites with modified files."""
    original_path = list(sys.path)
    sys.path.insert(0, str(ctx.parser_dir))
    merger = None
    saved = {}
    try:
        registry = importlib.import_module("suite_registry")
        merger = importlib.import_module("merge_jsons")
        for module in (registry, merger):
            if Path(module.__file__).resolve().parent != ctx.parser_dir.resolve():
                raise ValueError("Refusing cached module from another checkout: " + str(module.__file__))
        leaves = [suite for suite in registry.load_registry() if suite.get("json_output") and suite.get("requirements")]
        # PCIe shares the Standalone report in SR but is deliberately absent
        # from the DT-only STANDALONE suite-selection alias.
        standalone = {suite["canonical"] for suite in leaves
                      if suite.get("detailed_html") == "standalone_tests_detailed.html"}
        if not leaves:
            raise ValueError("Registry contains no testable leaf suites")
        ui = usable_html_module(ctx)
        for key in ("DT_OR_SR_MODE", "DT_SRS_SCOPE_TABLE", "SR_SRS_SCOPE_TABLE", "_REQUIREMENT_MAP",
                    "_SELECTED_SUITE_FILTER", "test_category_data", "test_cat_dict"):
            saved[key] = copy.deepcopy(getattr(merger, key))
        count, blocked = 0, 0
        for mode in ctx.modes:
            for case in scenarios(expected_leaves(leaves), mode):
                count += 1
                try:
                    run_case(ctx, registry, merger, ui, leaves, standalone, mode, case)
                except Exception as error:  # One broken case must not hide later cases.
                    blocked += 1
                    ctx.add("MERGE_CASE_EXECUTION", "BLOCKED", case[0] + ": cannot finish merged JSON check",
                            "Merger produces inspectable JSON", type(error).__name__ + ": " + str(error), mode,
                            evidence=(ctx.case_dir("merge/" + mode + "_" + case[0]),))
            edge_probes(ctx, merger, mode)
        ctx.add("MERGE_MATRIX_COVERAGE", "PASS" if count and not blocked else "BLOCKED", "Explicit registry-wide merged JSON matrix executed",
                "Nonzero full/selected leaf, requirement, waiver, SBMR and extension probes", str(count - blocked) + " JSON scenarios completed; " + str(blocked) + " blocked; HTML coverage is reported separately")
        ctx.add("MERGE_UNAGREED_STATUS_POLICY", "WARN", "All-skipped, warning-only and aborted-only compliance needs an agreed rule",
                "Owner-approved expected compliance for these states", "Not claimed covered by the compliance oracle")
    except Exception as error:
        ctx.add("MERGE_PREREQUISITE", "BLOCKED", "Merger health probes could not start",
                "Importable merger and nonempty registry", type(error).__name__ + ": " + str(error))
    finally:
        # Leave imported modules as we found them for any later Doctor groups.
        if merger is not None:
            for key, value in saved.items():
                setattr(merger, key, value)
        sys.path[:] = original_path
