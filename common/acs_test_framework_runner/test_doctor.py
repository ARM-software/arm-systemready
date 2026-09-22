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

"""Test Doctor's decisions, safe execution, packaging and coverage checks.

These tests check the checker, not the separate production parser fixes. Small
made-up inputs cover both correct and deliberately broken results. Fake command
responses keep most checks quick; temporary folders keep the real logs safe.
The tests run only when requested and are not part of normal log parsing.
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch
import argparse
import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest

# Import Doctor from this checkout, not an installed or neighbouring copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "log_parser"))
from doctor_checks.core import (
    Context, Finding, extract_package, package_differences, verify_checksum,
)
from doctor_checks.merge import (
    ComplianceHTML, EXPECTED_REQUIREMENTS, aggregate, differences, expected_leaves,
    oracle, payload, policy_differences, scenarios, status,
)
from standalone_runner import record_category_provenance
from doctor_checks import (
    core as doctor, artifacts as policy, merge as doctor_merge, probes as native, probes,
)


# Overall verdicts, optional check groups and safe output locations.

class DoctorTests(unittest.TestCase):
    """Check that Doctor reports success, failure and blocked work honestly."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parser = self.root / "parser"
        self.parser.mkdir()
        self.out = self.root / "results"

    def args(self, **changes):
        """Build minimal command-line options, changing only what a test needs."""
        values = dict(mode=None, doctor_timeout=60, doctor_report=[],
                      doctor_output=str(self.out))
        values.update(changes)
        return argparse.Namespace(**values)

    def finding(self, status):
        """Create one simple check result for overall-verdict tests."""
        return Finding("CONTROL", status, "Example", "Expected", "Actual")

    def test_verdict_never_passes_zero_or_blocked(self):
        """Check verdict never passes zero or blocked."""
        for findings in ([], [self.finding("WARN")], [self.finding("BLOCKED")],
                         [self.finding("PASS"), self.finding("BLOCKED")]):
            self.assertEqual(doctor.verdict(findings), ("INCOMPLETE", 2))

    def test_fail_and_pass_exit_codes(self):
        """Check fail and pass exit codes."""
        self.assertEqual(doctor.verdict([self.finding("PASS")])[1], 0)
        self.assertEqual(doctor.verdict([self.finding("PASS"), self.finding("FAIL")])[1], 1)
        self.assertEqual(doctor.verdict([self.finding("FAIL"), self.finding("BLOCKED")])[1], 1)

    def test_status_is_closed_set(self):
        """Check status is closed set."""
        with self.assertRaises(ValueError):
            self.finding("SKIPPED_AS_PASS")

    def test_registry_empty_and_duplicate_alias(self):
        """Check registry empty and duplicate alias."""
        self.assertTrue(doctor.registry_issues({"suites": []}, self.parser))
        suites = [{"canonical": "A", "aliases": ["shared_alias"]},
                  {"canonical": "B", "aliases": ["SHARED-ALIAS"]}]
        self.assertIn("resolves to both",
                      " ".join(doctor.registry_issues({"suites": suites}, self.parser)))

    def test_registry_missing_parser_and_fragment(self):
        """Check registry missing parser and fragment."""
        suites = [{"canonical": "BSA", "logs_to_json": "absent.py",
                   "schema": "missing.json#/definitions/suite"}]
        issues = doctor.registry_issues({"suites": suites}, self.parser)
        self.assertEqual(len(issues), 3)

    def test_registry_valid_positive_control(self):
        """Check registry valid positive control."""
        data = {"suites": [{"canonical": "A", "modes": ["DT"],
                            "requirement_key": "A", "requirements": {"DT": "M"}}]}
        self.assertEqual(doctor.registry_issues(data, self.parser), [])

    def test_output_cannot_overwrite_or_be_inside_input(self):
        """Check output cannot overwrite or be inside input."""
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            doctor.run_health(self.args(), self.parser)
        for output in (self.parser / "new", self.out / "new"):
            with self.assertRaises(ValueError):
                doctor.run_health(self.args(doctor_output=str(output),
                                           doctor_report=["DT=" + str(self.out)]), self.parser)
            self.assertFalse(output.exists())

    def test_bad_report_and_timeout_arguments(self):
        """Check bad report and timeout arguments."""
        for change in ({"doctor_report": ["/missing/mode"]},
                       {"doctor_report": ["DT="]},
                       {"doctor_report": ["SR=/tmp/example"], "mode": "DT"},
                       {"doctor_timeout": 0}, {"doctor_timeout": 301}):
            with self.assertRaises(ValueError):
                doctor.run_health(self.args(**change), self.parser)
        self.assertFalse(self.out.exists())

    def test_default_temp_directory_must_not_be_inside_protected_input(self):
        """Check default temp directory must not be inside protected input."""
        for protected in (self.parser, self.out):
            with mock.patch.object(doctor.tempfile, "gettempdir", return_value=str(protected)), \
                    mock.patch.object(doctor.tempfile, "mkdtemp") as create:
                with self.assertRaisesRegex(ValueError, "Temporary directory"):
                    doctor.run_health(self.args(doctor_output=None,
                                               doctor_report=["DT=" + str(self.out)]), self.parser)
                create.assert_not_called()

    def test_source_checkout_root_is_protected_not_only_parser_subdirectory(self):
        """Check source checkout root is protected not only parser subdirectory."""
        (self.root / ".git").write_text("gitdir: /unused/test")
        with self.assertRaises(ValueError):
            doctor.run_health(self.args(doctor_output=str(self.root / "new-results")), self.parser)
        self.assertFalse((self.root / "new-results").exists())
        self.assertEqual(doctor.protected_source_root(self.parser), self.root)

    def test_repository_json_rejects_ambiguous_keys_and_nonfinite_values(self):
        """Check repository JSON rejects ambiguous keys and nonfinite values."""
        path = self.parser / "metadata.json"
        for value in ('{"scope":"R","scope":"M"}', '{"count":NaN}', '{"count":1e999}'):
            path.write_text(value)
            with self.assertRaises(ValueError):
                doctor.load_json(path)

    def test_report_escapes_untrusted_text(self):
        """Check report escapes untrusted text."""
        self.out.mkdir()
        ctx = Context(self.parser, self.out)
        ctx.add("TEST", "FAIL", "<script>alert(1)</script>", "A & B", 'actual "value"')
        doctor.render_reports(ctx, {"revision": "control"})
        page = (self.out / "index.html").read_text()
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        payload = json.loads((self.out / "doctor.json").read_text())
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["findings"][0]["expected"], "A & B")

    def test_group_headings_do_not_describe_only_the_first_finding(self):
        """Check group headings do not describe only the first finding."""
        self.out.mkdir()
        ctx = Context(self.parser, self.out)
        for rule, issues, title in (
            ("NATIVE_RAW_SCHEMA", ("bsa.json", "sct.json"),
             "Generated raw JSON does not match its registered schema"),
            ("ARTIFACT.SCHEMA", ("bsa.json violates the JSON schema",
                                 "sct.json violates the JSON schema"),
             "Report JSON files do not match their registered schemas"),
            ("ARTIFACT.PARITY", ("Different records: sct_detailed.html",
                                 "Different records: sbsa_detailed.html"),
             "Raw and displayed result identities do not agree"),
            ("MERGE_OVERALL_POLICY", ("Recommended result incorrectly blocks overall SRS",
                                      "Mandatory input is empty"),
             "Overall SRS compliance does not match the requirement policy"),
            ("FUTURE_CHECK", ("First scenario", "Second scenario"), "Future check")):
            for issue in issues:
                ctx.add(rule, "FAIL", issue, "Expected", "Actual")
            doctor.render_reports(ctx, {"revision": "control"})
            page = (self.out / "index.html").read_text()
            # Plain-language topic titles may change, but the original grouped
            # title must remain searchable alongside every recorded finding.
            self.assertIn(title.lower(), page.lower())
            self.assertIn('data-check-id="%s"' % rule, page)
            for issue in issues:
                self.assertIn(issue, page)

    def test_command_records_success_and_nonzero(self):
        """Check command records success and nonzero."""
        ctx = Context(self.parser, self.out)
        directory = ctx.case_dir("control")
        result = ctx.run([sys.executable, "-c", "print('actual output'); raise SystemExit(7)"],
                         directory)
        self.assertEqual(result.returncode, 7)
        self.assertIn("actual output", result.stdout)
        self.assertTrue((directory / "command.command.json").is_file())

    def test_command_timeout_is_not_success(self):
        """Check command timeout is not success."""
        ctx = Context(self.parser, self.out, timeout=0.05)
        directory = ctx.case_dir("timeout")
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            ctx.run([sys.executable, "-c", "import time; time.sleep(5)"], directory)
        self.assertIn("incomplete", (directory / "command.log").read_text())

    def test_case_directory_cannot_escape(self):
        """Check case directory cannot escape."""
        ctx = Context(self.parser, self.out)
        for name in ("../escape", "/tmp/escape"):
            with self.assertRaises(ValueError):
                ctx.case_dir(name)

    def run_mocked(self, prerequisite, module):
        """Run Doctor with fake checks so each test controls what they report."""
        for group, _ in doctor.GROUPS:
            setattr(module, "run_" + group, module.run)
        with mock.patch.object(doctor, "check_repository", side_effect=prerequisite), \
                mock.patch.object(doctor.importlib, "import_module", return_value=module), \
                mock.patch.object(doctor.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(io.StringIO()):
            code = doctor.run_health(self.args(), self.parser)
        payload = json.loads((self.out / "doctor.json").read_text())
        return code, payload

    def test_missing_dependencies_block_all_probes(self):
        """Check missing dependencies block all probes."""
        module = mock.Mock()
        code, payload = self.run_mocked(lambda ctx: False, module)
        self.assertEqual(code, 2)
        self.assertEqual(payload["counts"]["BLOCKED"], len(doctor.GROUPS))
        module.run.assert_not_called()

    def test_group_selection_is_explicit_and_native_requires_package(self):
        """Check group selection is explicit and native requires package."""
        self.assertEqual(
            [name for name, _ in doctor.selected_groups(self.args(doctor_checks="native"))],
            ["package", "native"])
        self.assertEqual(
            [name for name, _ in doctor.selected_groups(self.args(doctor_checks="reports"))],
            ["reports"])
        for change in ({"doctor_checks": ""}, {"doctor_checks": "typo"},
                       {"doctor_checks": "raw,"}, {"doctor_browser": "/not-requested"}):
            with self.assertRaises(ValueError):
                doctor.selected_groups(self.args(**change))

    def test_unavailable_group_does_not_block_independent_groups(self):
        """Check unavailable group does not block independent groups."""
        module = mock.Mock()
        module.run.side_effect = lambda ctx: ctx.add("CONTROL", "PASS", "Independent group ran",
                                                     "yes", "yes")
        readiness = {name: name in {"policy", "package", "merge"} for name, _ in doctor.GROUPS}
        code, payload = self.run_mocked(lambda ctx: readiness, module)
        self.assertEqual(code, 2)
        self.assertEqual(module.run.call_count, 3)
        self.assertEqual(payload["counts"]["BLOCKED"], 3)

    def test_package_intent_survives_package_module_import_failure(self):
        """Check package intent survives package module import failure."""
        seen = []
        # Simulate a broken package check without disabling independent checks.
        def imported(name):
            """Return a broken package check and a working native check."""
            if name == "doctor_checks.core":
                return mock.Mock(run_package=mock.Mock(
                    side_effect=ImportError("broken package group")))
            def run(ctx):
                """Record the package state seen by the independent check."""
                seen.append((ctx.package_checked, ctx.portable_parser))
                ctx.add("CONTROL", "BLOCKED", "No package", "verified package", "None")
            return mock.Mock(run_native=run)
        with mock.patch.object(doctor, "check_repository", return_value=True), \
                mock.patch.object(doctor.importlib, "import_module", side_effect=imported), \
                mock.patch.object(doctor.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(io.StringIO()):
            code = doctor.run_health(self.args(doctor_checks="native"), self.parser)
        self.assertEqual(code, 2)
        self.assertEqual(seen, [(True, None)])

    def test_legacy_launcher_uses_one_canonical_doctor_module(self):
        # A fresh process catches duplicate imports that this test process could hide.
        """Check legacy launcher uses one canonical doctor module."""
        script = r'''
import contextlib
import importlib
import io
import json
import runpy
import sys
sys.argv = [sys.argv[1], "--help"]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit as error:
    assert error.code == 0
launcher = importlib.import_module("doctor")
canonical = importlib.import_module("doctor_checks.core")
assert launcher.Context is canonical.Context
assert launcher.Finding is canonical.Finding
assert launcher.run_health is canonical.run_health
assert launcher.add_arguments is canonical.add_arguments
assert canonical.Context.__module__ == "doctor_checks.core"
print(json.dumps({"canonical": True, "file": launcher.__file__}))
'''
        launcher = doctor.BASE_DIR / "doctor.py"
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(launcher)],
                                   cwd=doctor.BASE_DIR, capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"canonical": True, "file": str(launcher)})

    def test_normal_argument_registration_does_not_load_health_checks(self):
        # Ordinary parsing can expose the optional flags without loading checks.
        """Check normal argument registration does not load health checks."""
        script = r'''
import sys
import standalone_runner
parser = standalone_runner.build_parser()
assert "--doctor" in parser.format_help()
for name in ("report", "merge", "probes", "artifacts"):
    assert "doctor_checks." + name not in sys.modules, name
'''
        completed = subprocess.run([sys.executable, "-B", "-c", script],
                                   cwd=doctor.BASE_DIR, capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_zero_assertions_from_a_group_is_incomplete(self):
        """Check zero assertions from a group is incomplete."""
        code, payload = self.run_mocked(lambda ctx: True, mock.Mock())
        self.assertEqual(code, 2)
        self.assertTrue(any(item["check_id"] == "ZERO_CHECKS" for item in payload["findings"]))

    def test_probe_exception_is_reported_not_silently_skipped(self):
        """Check probe exception is reported not silently skipped."""
        module = mock.Mock()
        module.run.side_effect = RuntimeError("fixture cannot execute")
        code, payload = self.run_mocked(lambda ctx: True, module)
        self.assertEqual(code, 2)
        self.assertTrue(
            any("fixture cannot execute" in item["actual"] for item in payload["findings"]))


# Expected compliance rules and comparison of merged JSON with displayed results.

def suite(name, requirement="M", mode="DT"):
    """Build a small suite entry for one requirement and execution mode."""
    return {"canonical": name, "modes": [mode], "requirements": {mode: requirement},
            "requirement_key": name}


class DoctorMergeControls(unittest.TestCase):
    """Check the expected rules independently of the production merger."""

    def test_pcie_policy_is_explicit_sr_only_and_recommended(self):
        """Check PCIE policy is explicit SR only and recommended."""
        name = "PCIE-OPTION-ROM-ARCH-AUDIT"
        self.assertEqual(EXPECTED_REQUIREMENTS[name], {"SR": "R"})
        # Deliberately supply the wrong registry policy: it must not change
        # Doctor's independently reviewed answer.
        leaves = expected_leaves([suite(name, "M", "DT")])
        self.assertEqual(leaves[0]["requirements"], {"SR": "R"})
        self.assertEqual(leaves[0]["modes"], ["SR"])
        self.assertEqual(oracle(leaves, "DT", {name: "pass"}), ({}, "compliant"))
        for state, expected in (("pass", "compliant"), ("fail", "not_compliant"),
                                ("missing", "not_run")):
            for selected in (None, [name]):
                with self.subTest(state=state, selected=selected):
                    rows, overall = oracle(leaves, "SR", {name: state}, selected)
                    self.assertEqual(rows[name], {"requirement": "Recommended", "status": expected})
                    self.assertEqual(overall, "compliant")

    def test_pcie_registry_policy_drift_is_not_accepted_as_its_own_oracle(self):
        """Check PCIE registry policy drift is not accepted as its own oracle."""
        registry = native.load_json(doctor.BASE_DIR / "suite_registry.json")
        name = "PCIE-OPTION-ROM-ARCH-AUDIT"
        self.assertFalse([issue for issue in policy_differences(registry) if issue[0] == name])
        for fields in ({"requirements": {"SR": "M"}},
                       {"modes": ["DT", "SR"], "requirements": {"DT": "R", "SR": "R"}}):
            with self.subTest(fields=fields):
                mutated = deepcopy(registry)
                next(item for item in mutated["suites"] if item["canonical"] == name).update(fields)
                self.assertTrue(
                    [issue for issue in policy_differences(mutated) if issue[0] == name])
        registry["suites"] = [item for item in registry["suites"] if item["canonical"] != name]
        self.assertTrue([issue for issue in policy_differences(registry) if issue[0] == name])

    def test_pcie_payload_retains_standalone_identity_and_one_result(self):
        """Check PCIE payload retains standalone identity and one result."""
        for state, wanted in (("pass", "PASSED"), ("fail", "FAILED")):
            with self.subTest(state=state):
                data = payload("PCIE-OPTION-ROM-ARCH-AUDIT", state)
                self.assertEqual(len(data["test_results"]), 1)
                row = data["test_results"][0]
                self.assertEqual(row["Test_case"], "pcie_option_rom_arch_audit")
                self.assertEqual(row["test_result"], wanted)
                self.assertEqual(len(row["subtests"]), 1)

    def test_memory_map_suites_are_explicit_mandatory_dt_contracts(self):
        """Check memory map suites are explicit mandatory DT contracts."""
        registry = json.loads((Path(__file__).resolve().parents[1] / "log_parser" /
                               "suite_registry.json").read_text(encoding="utf-8"))
        names = {"RESERVED-MEMORY-MAP": "RESERVED_MEMORY_MAP", "DTB-ALIGNMENT": "DTB_ALIGNMENT"}
        leaves = expected_leaves(
            [item for item in registry["suites"] if item["canonical"] in names])
        self.assertEqual(len(leaves), 2)
        standalone = next(item for item in registry["suites"] if item["canonical"] == "STANDALONE")
        for leaf in leaves:
            name = leaf["canonical"]
            self.assertEqual(EXPECTED_REQUIREMENTS[name], {"DT": "M"})
            self.assertEqual(leaf["requirement_key"], names[name])
            self.assertIn(name, standalone["included_suites"])
            self.assertEqual(registry["standalone"]["suite_execution"][name]["handler"],
                             "standalone_single")
        for name in names:
            for state in ("pass", "fail", "missing", "waived"):
                with self.subTest(suite=name, state=state):
                    states = {**dict.fromkeys(names, "pass"), name: state}
                    rows, overall = oracle(leaves, "DT", states)
                    self.assertEqual(rows[name]["requirement"], "Mandatory")
                    self.assertEqual(
                        overall, {
                            "pass": "compliant",
                            "fail": "not_compliant",
                            "missing": "not_compliant",
                            "waived": "waived"
                        }[state])
        full = [case for case in scenarios(leaves, "DT") if case[0].startswith("full_")]
        self.assertTrue(full)
        self.assertTrue(all(set(case[1]) == set(names) for case in full))

    def test_recommended_failure_is_visible_but_nonblocking(self):
        """Check recommended failure is visible but nonblocking."""
        rows, overall = oracle([suite("BSA", "R")], "DT", {"BSA": "fail"})
        self.assertEqual(rows["BSA"]["status"], "not_compliant")
        self.assertEqual(overall, "compliant")

    def test_recommended_missing_nonblocking_full_and_selected(self):
        """Check recommended missing nonblocking full and selected."""
        leaves = [suite("BSA", "R"), suite("FWTS")]
        for selection in (None, ["BSA"]):
            self.assertEqual(
                oracle(leaves, "DT", {
                    "BSA": "missing",
                    "FWTS": "pass"
                }, selection)[1], "compliant")

    def test_mandatory_missing_and_unwaived_failure_block(self):
        """Check mandatory missing and unwaived failure block."""
        for state in ("missing", "empty", "header", "fail", "mixed"):
            self.assertEqual(oracle([suite("FWTS")], "DT", {"FWTS": state})[1], "not_compliant")

    def test_only_sr_os_recommended_entries_are_exempt(self):
        """Check only SR OS recommended entries are exempt."""
        for name, mode, wanted in (("OS-TESTS", "SR", "compliant"),
                                   ("OS-TESTS", "DT", "not_compliant"),
                                   ("BSA", "SR", "not_compliant")):
            self.assertEqual(
                oracle([suite(name, mode=mode)], mode,
                       {name: "recommended_fail"})[0][name]["status"], wanted)

    def test_sbmr_missing_interface_promoted_mandatory(self):
        """Check SBMR missing interface promoted mandatory."""
        leaves = [suite("SBMR-IB", "R", "SR"), suite("SBMR-OOB", "R", "SR")]
        rows, overall = oracle(leaves, "SR", {"SBMR-IB": "pass", "SBMR-OOB": "missing"})
        self.assertEqual(rows["SBMR-OOB"], {"requirement": "Mandatory", "status": "not_run"})
        self.assertEqual(overall, "not_compliant")
        self.assertEqual(aggregate(list(rows.values())), "Mandatory (Not Compliant)")

    def test_extensions_do_not_block_srs(self):
        """Check extensions do not block SRS."""
        self.assertEqual(
            oracle([suite("BBSR-TPM", "EM")], "DT", {"BBSR-TPM": "fail"})[1], "compliant")

    def test_conditional_missing_not_blocking_but_failure_blocks(self):
        """Check conditional missing not blocking but failure blocks."""
        leaves = [suite("PFDI", "CM")]
        self.assertEqual(oracle(leaves, "DT", {"PFDI": "missing"})[1], "compliant")
        self.assertEqual(oracle(leaves, "DT", {"PFDI": "fail"})[1], "not_compliant")

    def test_execution_proof_preserves_sbsa_requirement_without_result_json(self):
        """Check execution proof preserves SBSA requirement without result JSON."""
        leaves = [suite("SBSA", "R", "SR")]
        for state in ("missing", "empty", "header"):
            with self.subTest(state=state):
                rows, overall = oracle(leaves, "SR", {"SBSA": state}, executed={"SBSA"})
                self.assertEqual(rows["SBSA"], {"requirement": "Mandatory", "status": "not_run"})
                self.assertEqual(overall, "not_compliant")

    def test_explicit_no_execution_does_not_promote_from_json_presence(self):
        """Check explicit no execution does not promote from JSON presence."""
        names = ("SBSA", "SBMR-IB", "SBMR-OOB")
        leaves = [suite(name, "R", "SR") for name in names]
        for state in ("missing", "empty", "header", "pass", "fail"):
            with self.subTest(state=state):
                rows, overall = oracle(leaves, "SR", dict.fromkeys(names, state), executed=set())
                self.assertEqual({row["requirement"] for row in rows.values()}, {"Recommended"})
                self.assertEqual(overall, "compliant")

    def test_either_sbmr_execution_promotes_both_without_result_json(self):
        """Check either SBMR execution promotes both without result JSON."""
        names = ("SBMR-IB", "SBMR-OOB")
        leaves = [suite(name, "R", "SR") for name in names]
        for executed_name in names:
            for state in ("missing", "empty", "header"):
                with self.subTest(executed=executed_name, state=state):
                    rows, overall = oracle(leaves, "SR", dict.fromkeys(names, state),
                                           executed={executed_name})
                    self.assertEqual(rows, dict.fromkeys(names,
                        {"requirement": "Mandatory", "status": "not_run"}))
                    self.assertEqual(overall, "not_compliant")

    def test_selected_sbmr_requirement_keeps_its_executed_peer(self):
        """Check selected SBMR requirement keeps its executed peer."""
        leaves = [suite(name, "R", "SR") for name in ("SBMR-IB", "SBMR-OOB")]
        rows, overall = oracle(leaves, "SR", {"SBMR-IB": "missing"},
                               selected=["SBMR-IB"], executed={"SBMR-OOB"})
        self.assertEqual(rows, {"SBMR-IB": {"requirement": "Mandatory", "status": "not_run"}})
        self.assertEqual(overall, "not_compliant")

    def test_missing_pfdi_blocks_only_with_execution_proof(self):
        """Check missing pfdi blocks only with execution proof."""
        leaves = [suite("PFDI", "CM")]
        for state in ("missing", "empty", "header"):
            for executed in (None, set(), {"PFDI"}):
                with self.subTest(state=state, executed=executed):
                    rows, overall = oracle(leaves, "DT", {"PFDI": state}, executed=executed)
                    self.assertEqual(rows["PFDI"],
                                     {"requirement": "Conditional-Mandatory", "status": "not_run"})
                    self.assertEqual(overall, "not_compliant" if executed else "compliant")

    def test_execution_proof_wrong_mode_and_unknown_names_are_inert(self):
        """Check execution proof wrong mode and unknown names are inert."""
        leaves = [suite("PFDI", "CM"), suite("BSA", "R"),
                  suite("SBSA", "R", "SR"), suite("SBMR-IB", "R", "SR")]
        wrong_mode = {"SBSA", "SBMR-IB", "UNKNOWN"}
        rows, overall = oracle(leaves, "DT", {"BSA": "pass", "PFDI": "missing"},
                               executed=wrong_mode)
        self.assertEqual(rows["PFDI"]["requirement"], "Conditional-Mandatory")
        self.assertEqual(overall, "compliant")
        # An unregistered peer must not promote a registered SBMR interface.
        rows, overall = oracle(leaves, "SR", {"SBSA": "missing", "SBMR-IB": "missing"},
                               executed={"PFDI", "SBMR-OOB", "UNKNOWN"})
        self.assertEqual({row["requirement"] for row in rows.values()}, {"Recommended"})
        self.assertEqual(overall, "compliant")

    def test_default_oracle_retains_existing_present_result_rules(self):
        """Check default oracle retains existing present result rules."""
        leaves = [suite(name, "R", "SR") for name in ("SBSA", "SBMR-IB", "SBMR-OOB")]
        states = {"SBSA": "pass", "SBMR-IB": "fail", "SBMR-OOB": "missing"}
        default = oracle(leaves, "SR", states)
        self.assertEqual(default, oracle(leaves, "SR", states, executed=None))
        self.assertEqual(default, oracle(leaves, "SR", states, executed={"SBSA", "SBMR-IB"}))
        self.assertEqual({row["requirement"] for row in default[0].values()}, {"Mandatory"})
        self.assertEqual(default[1], "not_compliant")

    def test_waived_and_mixed_failures_distinct(self):
        """Check waived and mixed failures distinct."""
        leaves = [suite("BSA")]
        self.assertEqual(oracle(leaves, "DT", {"BSA": "waived"})[1], "waived")
        self.assertEqual(oracle(leaves, "DT", {"BSA": "mixed"})[1], "not_compliant")

    def test_detector_catches_mutated_status_requirement_absence_extra(self):
        """Check detector catches mutated status requirement absence extra."""
        wanted = {"BSA": {"requirement": "Mandatory", "status": "not_compliant"}}
        self.assertEqual(differences(wanted, wanted), {})
        for actual in ({}, {"BSA": {"requirement": "Mandatory", "status": "compliant"}},
                       {"BSA": {"requirement": "Recommended", "status": "not_compliant"}},
                       {**wanted, "SBSA": wanted["BSA"]}):
            self.assertTrue(differences(wanted, actual))

    def test_html_detector_parses_nested_escaped_labels(self):
        """Check HTML detector parses nested escaped labels."""
        parser = ComplianceHTML()
        parser.feed(
            '<tr data-acs-compliance-tone="fail"><th>BSA</th><td><span>Mandatory</span></td>'
            '<td><span>Not Compliant (Not Run)</span></td></tr>'
            '<span class="acs-suite-compliance">Mandatory (<b>Not Compliant</b>)</span>')
        self.assertEqual(parser.rows, [("BSA", "Mandatory", "Not Compliant (Not Run)")])
        self.assertEqual(parser.badges, ["Mandatory (Not Compliant)"])

    def test_no_guessed_policy_for_unknown_status(self):
        """Check no guessed policy for unknown status."""
        with self.assertRaises(ValueError):
            oracle([suite("BSA")], "DT", {"BSA": "aborted"})
        self.assertEqual(status("garbage"), "unknown")

    def test_bsa_payload_does_not_invent_extra_top_level_outcomes(self):
        """Check BSA payload does not invent extra top level outcomes."""
        data = payload("BSA", "mixed")
        self.assertEqual(len(data["test_results"][0]["testcases"]), 2)
        self.assertEqual(data["suite_summary"]["total_failed"], 1)
        self.assertEqual(data["suite_summary"]["total_failed_with_waiver"], 1)

    def test_matrix_names_are_unique(self):
        """Check matrix names are unique."""
        names = [case[0] for case in scenarios([suite("FWTS"), suite("BSA", "R")], "DT")]
        self.assertEqual(len(names), len(set(names)))

    def exercise_case(self, ctx, ui, registry_requirement="M"):
        """Feed a fixed passing merge result to Doctor's JSON and HTML checks."""
        leaf = {
            **suite("FWTS", registry_requirement), "json_output": "fwts.json",
            "detailed_html": "fwts_detailed.html"
        }
        # The fake merger isolates Doctor's verdict from real parser behaviour.
        def merge_json_files(_paths, output):
            """Write a fixed passing report without invoking the real merger."""
            Path(output).write_text(json.dumps({"Suite_Name: acs_info": {"ACS Results Summary": {
                "Overall Compliance Result": "Compliant",
                "Suite_Name: Mandatory  : EBBR-FWTS_compliance": "Compliant"}}}), encoding="utf-8")
        merger = SimpleNamespace(set_run_mode=lambda mode: None,
                                 build_selected_suite_filter=lambda selected: selected,
                                 merge_json_files=merge_json_files)
        registry = SimpleNamespace(requirement_table=lambda mode: [("FWTS", "M")])
        doctor_merge.run_case(ctx, registry, merger, ui, [leaf], set(), "DT",
                              ("complete_FWTS", {"FWTS": "pass"}, ["FWTS"], None))

    def test_missing_html_capability_keeps_json_findings(self):
        """Check missing HTML capability keeps JSON findings."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(Path(directory) / "parser", directory)
            with patch.object(doctor_merge, "check_html") as html_check:
                self.exercise_case(ctx, None)
            html_check.assert_not_called()
            self.assertEqual([item.status for item in ctx.findings], ["PASS"] * 3)
            self.assertEqual(
                [item.check_id for item in ctx.findings],
                ["MERGE_SUITE_STATUS", "MERGE_OVERALL_POLICY", "MERGE_INPUT_PRESERVED"])
            observation = json.loads(
                (ctx.case_dir("merge/DT_complete_FWTS") / "observed.json").read_text())
            self.assertEqual(observation["html_check"], "not available")

    def test_available_but_broken_html_fails_without_erasing_json(self):
        """Check available but broken HTML fails without erasing JSON."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(Path(directory) / "parser", directory)
            with patch.object(doctor_merge,
                              "check_html",
                              side_effect=RuntimeError("template defect")):
                self.exercise_case(ctx, object())
            self.assertEqual([item.status for item in ctx.findings], ["PASS"] * 3 + ["FAIL"])
            self.assertEqual(ctx.findings[-1].check_id, "HTML_COMPLIANCE_EXECUTION")
            self.assertIn("template defect", ctx.findings[-1].actual)

    def test_supported_html_checked_and_bad_labels_fail(self):
        """Check supported HTML checked and bad labels fail."""
        for difference in ({
                "badges": {},
                "tables": {}
        }, {
                "badges": {
                    "FWTS": "wrong"
                },
                "tables": {}
        }):
            with self.subTest(difference=difference), tempfile.TemporaryDirectory() as directory:
                ctx = Context(Path(directory) / "parser", directory)
                with patch.object(doctor_merge, "check_html",
                                  return_value=difference) as html_check:
                    self.exercise_case(ctx, object())
                html_check.assert_called_once()
                self.assertEqual(ctx.findings[-1].check_id, "HTML_COMPLIANCE_MATCH")
                self.assertEqual(ctx.findings[-1].status,
                                 "FAIL" if any(difference.values()) else "PASS")

    def test_html_capability_reports_missing_helpers_and_checks_checkout(self):
        """Check HTML capability reports missing helpers and checks checkout."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            module = SimpleNamespace(__file__=str(Path(directory) / "generate_acs_summary.py"))
            with patch.object(doctor_merge.importlib, "import_module", return_value=module):
                self.assertIsNone(doctor_merge.usable_html_module(ctx))
            self.assertEqual(len(ctx.findings), 1)
            self.assertEqual(ctx.findings[0].status, "BLOCKED")
            self.assertIn("_summary_cards", ctx.findings[0].actual)
            module._summary_cards = lambda: None
            module.inject_detail_compliance = lambda: None
            with patch.object(doctor_merge.importlib, "import_module", return_value=module):
                self.assertIs(doctor_merge.usable_html_module(ctx), module)
            self.assertEqual(len(ctx.findings), 1)

    def test_live_case_uses_independent_requirement_not_registry_value(self):
        """Check live case uses independent requirement not registry value."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(Path(directory) / "parser", directory)
            real_oracle = doctor_merge.oracle
            with patch.object(doctor_merge, "oracle", wraps=real_oracle) as oracle_call:
                self.exercise_case(ctx, None, registry_requirement="R")
            self.assertEqual(oracle_call.call_args.args[0][0]["requirements"], {
                "DT": "M",
                "SR": "M"
            })


# Raw parser output: expected test identities, counts and suite/mode coverage.

def golden():
    """Return known results and separately written expectations for comparison."""
    data = {
        "suite_summary": {
            "Passed": 1,
            "Failed": 1
        },
        "test_results": [{
            "testcases": [
                {
                    "Test_case": "QA_01",
                    "Test_case_description": "Known passing rule",
                    "Test_result": "PASSED"
                },
                {
                    "Test_case":
                    "QA_02",
                    "Test_case_description":
                    "Known failing rule",
                    "Test_result":
                    "FAILED",
                    "subtests": [{
                        "sub_Test_Number": "QA_CHILD",
                        "sub_Test_Description": "Known failing child",
                        "sub_test_result": "FAILED"
                    }]
                },
            ]
        }]
    }
    expected = {
        "assertions": [{
            "path": ["suite_summary", "Passed"],
            "value": 1
        }, {
            "path": ["suite_summary", "Failed"],
            "value": 1
        }],
        "records": [{
            "path": ["test_results", 0, "testcases", 0],
            "fields": {
                "Test_case": "QA_01",
                "Test_case_description": "Known passing rule",
                "Test_result": "PASSED"
            }
        }, {
            "path": ["test_results", 0, "testcases", 1],
            "fields": {
                "Test_case": "QA_02",
                "Test_case_description": "Known failing rule",
                "Test_result": "FAILED"
            }
        }, {
            "path": ["test_results", 0, "testcases", 1, "subtests", 0],
            "fields": {
                "sub_Test_Number": "QA_CHILD",
                "sub_Test_Description": "Known failing child",
                "sub_test_result": "FAILED"
            }
        }]
    }
    return data, expected


def completed_schema_failure(path, issue="MISSING_KEY"):
    """Mimic a validator that finished and reported an error for the given file."""
    return ("*suite=Suite_Name: BSA issue=" + issue + ": Test_suite_info required count=1\n"
            "--- Files Checked ---\nBSA: " + str(path) + "\n"
            "Schema validation result: \x1b[0;31mFAIL\x1b[0m (1 failed, 0 passed, 0 skipped)\n")


class NativeIdentityTests(unittest.TestCase):
    """Check individual test details as well as totals, so swaps cannot hide."""

    def test_golden_positive_control(self):
        """Check golden positive control."""
        data, expected = golden()
        before = copy.deepcopy((data, expected))
        self.assertEqual(native.raw_issues(data, expected), [])
        self.assertEqual((data, expected), before)

    def test_balanced_status_swap_does_not_pass_on_totals(self):
        """Check balanced status swap does not pass on totals."""
        data, expected = golden()
        rows = data["test_results"][0]["testcases"]
        rows[0]["Test_result"], rows[1]["Test_result"] = "FAILED", "PASSED"
        self.assertEqual(data["suite_summary"], {"Passed": 1, "Failed": 1})
        self.assertIn("Test_result", "\n".join(native.raw_issues(data, expected)))

    def test_balanced_identity_swap_is_detected(self):
        """Check balanced identity swap is detected."""
        data, expected = golden()
        rows = data["test_results"][0]["testcases"]
        rows[0]["Test_case"], rows[1]["Test_case"] = "QA_02", "QA_01"
        self.assertIn("Test_case", "\n".join(native.raw_issues(data, expected)))

    def test_descriptions_and_unknown_statuses_are_checked(self):
        """Check descriptions and unknown statuses are checked."""
        for field, replacement in (("Test_case_description", "Unrelated test"),
                                   ("Test_result", "UNKNOWN")):
            with self.subTest(field=field):
                data, expected = golden()
                data["test_results"][0]["testcases"][0][field] = replacement
                self.assertIn(field, "\n".join(native.raw_issues(data, expected)))

    def test_missing_extra_moved_or_resultless_records_are_detected(self):
        """Check missing extra moved or resultless records are detected."""
        for mutation in ("missing_parent", "missing_child", "extra_child", "moved_child",
                         "missing_result"):
            with self.subTest(mutation=mutation):
                data, expected = golden()
                rows = data["test_results"][0]["testcases"]
                if mutation == "missing_parent":
                    rows.pop()
                elif mutation == "missing_child":
                    rows[1]["subtests"].clear()
                elif mutation == "extra_child":
                    rows[1]["subtests"].append(copy.deepcopy(rows[1]["subtests"][0]))
                elif mutation == "moved_child":
                    rows[0]["subtests"] = rows[1].pop("subtests")
                else:
                    del rows[0]["Test_result"]
                self.assertIn("Result inventory differs",
                              "\n".join(native.raw_issues(data, expected)))

    def test_counts_are_checked_even_when_records_match(self):
        """Check counts are checked even when records match."""
        data, expected = golden()
        data["suite_summary"]["Failed"] = 0
        self.assertIn("suite_summary", "\n".join(native.raw_issues(data, expected)))

    def test_boolean_is_not_an_integer_count(self):
        """Check boolean is not an integer count."""
        data, expected = golden()
        data["suite_summary"]["Passed"] = True
        self.assertTrue(native.raw_issues(data, expected))

    def test_nonzero_unexpected_status_counter_is_detected(self):
        """Check nonzero unexpected status counter is detected."""
        data = {"test_results": [{"subtests": [{"sub_test_result": {
            "PASSED": 1, "FAILED": 0, "FAILED_WITH_WAIVER": 0, "pass_reasons": ["Known pass"]}}]}]}
        expected = {"assertions": [], "records": [{
            "path": ["test_results", 0, "subtests", 0], "fields": {
                "sub_test_result": {"PASSED": 1, "FAILED": 0}}}]}
        self.assertEqual(native.raw_issues(data, expected), [])
        data["test_results"][0]["subtests"][0]["sub_test_result"]["FAILED_WITH_WAIVER"] = 1
        self.assertIn("unexpected nonzero", "\n".join(native.raw_issues(data, expected)))

    def test_multiple_mismatches_are_not_hidden_by_first_error(self):
        """Check multiple mismatches are not hidden by first error."""
        data, expected = golden()
        rows = data["test_results"][0]["testcases"]
        rows[0]["Test_result"] = "UNKNOWN"
        rows[1]["Test_case"] = "wrong"
        issues = "\n".join(native.raw_issues(data, expected))
        self.assertIn("UNKNOWN", issues)
        self.assertIn("wrong", issues)


class NativeContractTests(unittest.TestCase):
    """Check that saved sample logs cover the registered suites and modes."""

    def setUp(self):
        self.data = native.load_json(native.DATA_FILE)
        self.registry = native.load_json(doctor.BASE_DIR / "suite_registry.json")

    def test_bundled_fixture_is_valid_and_independently_attributed(self):
        """Check bundled fixture is valid and independently attributed."""
        self.assertEqual(native.contract_issues(self.data), [])
        self.assertEqual(self.data["provenance"]["commit"],
                         "b6a8a78d1fef3d6e41d2d2aec94006e0a9263c8c")
        self.assertNotIn("compliance", self.data["scenarios"][1])

    def test_bundled_fixture_covers_all_32_routes(self):
        """Check bundled fixture covers all 32 routes."""
        self.assertEqual(native.coverage_issues(self.registry, self.data["scenarios"]), [])
        routes = {(name, case["mode"])
                  for case in self.data["scenarios"]
                  for name in case["suites"]}
        self.assertEqual(len(routes), 32)
        self.assertIn(("PCIE-OPTION-ROM-ARCH-AUDIT", "SR"), routes)
        self.assertNotIn(("PCIE-OPTION-ROM-ARCH-AUDIT", "DT"), routes)

    def test_pcie_native_fixtures_keep_independent_pass_fail_skip_answers(self):
        """Check PCIE native fixtures keep independent pass fail skip answers."""
        cases = {case["name"]: case for case in self.data["scenarios"]}
        for suffix, wanted, counter in (("pass", "PASSED", "total_passed"),
                                       ("fail", "FAILED", "total_failed"),
                                       ("skip", "SKIPPED", "total_skipped")):
            with self.subTest(outcome=suffix):
                case = cases["sr_pcie_" + suffix]
                self.assertEqual(case["mode"], "SR")
                self.assertEqual(case["suites"], ["PCIE-OPTION-ROM-ARCH-AUDIT"])
                self.assertIn("results/uefi_dump/PcieOptionRomArchAudit.log", case["files"])
                expected = case["raw"]["pcie_option_rom_arch_audit.json"]
                self.assertEqual(expected["destination"], "Suite_Name: Standalone")
                assertions = {tuple(item["path"]): item["value"] for item in expected["assertions"]}
                self.assertEqual(assertions[("test_results", 0, "test_result")], wanted)
                self.assertEqual(assertions[("suite_summary", counter)], 1)
                for other in {"total_passed", "total_failed", "total_skipped"} - {counter}:
                    self.assertEqual(assertions[("suite_summary", other)], 0)
                self.assertEqual(len(expected["records"]), 1)
                self.assertEqual(expected["records"][0]["fields"]["sub_test_result"][wanted], 1)

    def test_removing_pcie_fixtures_reports_only_the_sr_pcie_gap(self):
        """Check removing PCIE fixtures reports only the SR PCIE gap."""
        cases = [case for case in self.data["scenarios"]
                 if "PCIE-OPTION-ROM-ARCH-AUDIT" not in case["suites"]]
        self.assertEqual(native.coverage_issues(self.registry, cases), [
            "Missing independent native fixture: SR/PCIE-OPTION-ROM-ARCH-AUDIT"])

    def test_pcie_drift_in_counts_parent_status_or_child_identity_is_detected(self):
        """Check PCIE drift in counts parent status or child identity is detected."""
        case = next(case for case in self.data["scenarios"] if case["name"] == "sr_pcie_fail")
        expected = case["raw"]["pcie_option_rom_arch_audit.json"]
        # This is a small explicit observed result, not output copied from the
        # production parser. Each mutation changes one externally visible fact.
        actual = {
            "suite_summary": {
                "total_passed": 0,
                "total_failed": 1,
                "total_skipped": 0
            },
            "test_results": [{
                "Test_suite":
                "PCIeOptionRomArchAudit",
                "Test_case":
                "pcie_option_rom_arch_audit",
                "test_result":
                "FAILED",
                "subtests": [{
                    "sub_Test_Number": "1",
                    "sub_Test_Description": "PCIe Option ROM UEFI driver architecture compliance",
                    "sub_test_result": {
                        "PASSED": 0,
                        "FAILED": 1,
                        "SKIPPED": 0,
                        "ABORTED": 0,
                        "WARNINGS": 0,
                        "FAILED_WITH_WAIVER": 0
                    }
                }]
            }]
        }
        self.assertEqual(native.raw_issues(actual, expected), [],
                         "Control must match before mutation")
        for mutation in ("count", "parent", "identity", "missing-child"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(actual)
                if mutation == "count":
                    changed["suite_summary"]["total_failed"] = 0
                elif mutation == "parent":
                    changed["test_results"][0]["test_result"] = "PASSED"
                elif mutation == "identity":
                    changed["test_results"][0]["subtests"][0]["sub_Test_Number"] = "2"
                else:
                    changed["test_results"][0]["subtests"] = []
                self.assertTrue(native.raw_issues(changed, expected))

    def test_memory_map_fixtures_keep_independent_identity_and_counts(self):
        """Check memory map fixtures keep independent identity and counts."""
        case = next(case for case in self.data["scenarios"]
                    if case["name"] == "dt_memory_map_routes")
        self.assertEqual(case["mode"], "DT")
        self.assertEqual(case["suites"], ["RESERVED-MEMORY-MAP", "DTB-ALIGNMENT"])
        reserved = case["raw"]["reserved_memory_map.json"]
        self.assertEqual(
            [record["fields"]["sub_Test_Description"] for record in reserved["records"]],
            ["Reserved Memory Map Compliance Test", "Memory Reservation Block Compliance Test"])
        self.assertEqual(
            [record["fields"]["sub_test_result"]["FAILED"] for record in reserved["records"]],
            [0, 1])
        aligned = case["raw"]["dtb_alignment.json"]
        self.assertEqual(aligned["records"][0]["fields"]["sub_test_result"]["PASSED"], 1)
        self.assertIn("RESULTS: FAILED",
                      case["files"]["results/linux_tools/reserved_memory_map_test.log"])
        self.assertIn("RESULT: PASS", case["files"]["results/linux_tools/dtb_alignment_test.log"])

    def test_removing_memory_map_fixture_reports_both_new_coverage_gaps(self):
        """Check removing memory map fixture reports both new coverage gaps."""
        cases = [case for case in self.data["scenarios"] if case["name"] != "dt_memory_map_routes"]
        self.assertEqual(native.coverage_issues(self.registry, cases), [
            "Missing independent native fixture: DT/DTB-ALIGNMENT",
            "Missing independent native fixture: DT/RESERVED-MEMORY-MAP",
        ])

    def test_new_suite_requires_fixture_onboarding(self):
        """Check new suite requires fixture onboarding."""
        self.registry["suites"].append({
            "canonical": "NEW-SUITE",
            "modes": ["DT"],
            "logs_to_json": "new/logs_to_json.py",
            "schema": "new.json"
        })
        self.registry["standalone"]["suite_execution"]["NEW-SUITE"] = {}
        self.assertIn("Missing independent native fixture: DT/NEW-SUITE",
                      native.coverage_issues(self.registry, self.data["scenarios"]))

    def test_new_mode_requires_fixture_onboarding(self):
        """Check new mode requires fixture onboarding."""
        next(suite for suite in self.registry["suites"]
             if suite["canonical"] == "PFDI")["modes"].append("SR")
        self.assertIn("Missing independent native fixture: SR/PFDI",
                      native.coverage_issues(self.registry, self.data["scenarios"]))

    def test_unknown_fixture_route_is_not_silently_ignored(self):
        """Check unknown fixture route is not silently ignored."""
        self.data["scenarios"][0]["suites"].append("TYPO")
        self.assertIn("Fixture targets an unknown/unsupported route: SR/TYPO",
                      native.coverage_issues(self.registry, self.data["scenarios"]))

    def test_missing_raw_expectation_is_a_coverage_gap(self):
        """Check missing raw expectation is a coverage gap."""
        del self.data["scenarios"][0]["raw"]["bsa.json"]
        issues = native.coverage_issues(self.registry, self.data["scenarios"])
        self.assertTrue(
            any("BSA: no independently expected raw output" in issue for issue in issues))

    def test_fixture_cannot_hide_orphan_raw_output(self):
        """Check fixture cannot hide orphan raw output."""
        self.data["scenarios"][0]["raw"]["unexpected.json"] = golden()[1]
        self.assertTrue(any("no selected suite: unexpected.json" in issue for issue in
                            native.coverage_issues(self.registry, self.data["scenarios"])))

    def test_result_inventory_must_be_nonempty(self):
        """Check result inventory must be nonempty."""
        self.data["scenarios"][0]["raw"]["bsa.json"]["records"] = []
        self.assertTrue(any("non-empty exact record inventory" in issue
                            for issue in native.contract_issues(self.data)))

    def test_count_expectations_must_be_nonempty(self):
        """Check count expectations must be nonempty."""
        self.data["scenarios"][0]["raw"]["bsa.json"]["assertions"] = []
        self.assertTrue(any("independent count assertions" in issue
                            for issue in native.contract_issues(self.data)))

    def test_every_record_needs_identity_description_and_status(self):
        """Check every record needs identity description and status."""
        record = self.data["scenarios"][0]["raw"]["bsa.json"]["records"][0]
        del record["fields"]["Test_case"]
        self.assertTrue(any("identity, description and result" in issue
                            for issue in native.contract_issues(self.data)))

    def test_duplicate_expected_path_cannot_mask_missing_record(self):
        """Check duplicate expected path cannot mask missing record."""
        records = self.data["scenarios"][0]["raw"]["bsa.json"]["records"]
        records.append(copy.deepcopy(records[0]))
        self.assertTrue(any("duplicate expected record path" in issue
                            for issue in native.contract_issues(self.data)))

    def test_unknown_expected_status_cannot_be_a_positive_control(self):
        """Check unknown expected status cannot be a positive control."""
        self.data["scenarios"][0]["raw"]["bsa.json"]["records"][0]["fields"][
            "Test_result"] = "UNKNOWN"
        self.assertTrue(any("invalid expected result" in issue
                            for issue in native.contract_issues(self.data)))

    def test_fixture_paths_cannot_escape_evidence(self):
        """Check fixture paths cannot escape evidence."""
        for path in ("../source.py", "/tmp/absolute", "results/../../source.py", "..\\source.py",
                     "."):
            with self.subTest(path=path):
                data = copy.deepcopy(self.data)
                data["scenarios"][0]["files"][path] = "unsafe"
                self.assertTrue(
                    any("unsafe input path" in issue for issue in native.contract_issues(data)))

    def test_malformed_fixture_reports_errors_without_crashing(self):
        """Check malformed fixture reports errors without crashing."""
        for data in (None, [], {}, {"format_version": 1, "scenarios": []},
                     {"format_version": 1, "scenarios": [None, {}, {"name": [], "mode": []}]}):
            with self.subTest(data=data):
                self.assertTrue(native.contract_issues(data))

    def test_boolean_or_negative_path_indices_are_rejected(self):
        """Check boolean or negative path indices are rejected."""
        for index in (True, -1):
            with self.subTest(index=index):
                data = copy.deepcopy(self.data)
                data["scenarios"][0]["raw"]["bsa.json"]["records"][0]["path"][1] = index
                self.assertTrue(
                    any("invalid record path" in issue for issue in native.contract_issues(data)))

    def test_strict_json_rejects_duplicates_and_nonfinite_numbers(self):
        """Check strict JSON rejects duplicates and nonfinite numbers."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for text in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}',
                         '{"x": 1e999}'):
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        native.load_json(path)


class NativeExecutionTests(unittest.TestCase):
    """Check command routing and error reporting using controlled responses."""

    def test_native_contract_and_routes_do_not_require_merge_module_import(self):
        # Block one import in a fresh process to test check-group independence.
        """Check native contract and routes do not require merge module import."""
        script = r'''
import importlib.abc
import json
import sys
import tempfile
from unittest import mock
class NoMerge(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "doctor_checks.merge":
            raise ImportError("merge-only helpers deliberately unavailable")
sys.meta_path.insert(0, NoMerge())
from doctor_checks import core as doctor
from doctor_checks import probes as doctor_probes
assert doctor_probes.contract_issues(doctor_probes.load_json(doctor_probes.DATA_FILE)) == []
with tempfile.TemporaryDirectory() as folder:
    ctx = doctor.Context(doctor.BASE_DIR, folder)
    ctx.package_checked = True
    ctx.portable_parser = doctor.BASE_DIR
    with mock.patch.object(doctor_probes, "_run_route") as route:
        doctor_probes.run_native(ctx)
    assert route.call_count > 0
    assert all(item.status == "PASS" for item in ctx.findings)
assert "doctor_checks.merge" not in sys.modules
print(json.dumps({"routes": route.call_count, "merge_loaded": False}))
'''
        completed = subprocess.run([sys.executable, "-B", "-c", script],
                                   cwd=doctor.BASE_DIR, capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertGreater(result["routes"], 0)
        self.assertFalse(result["merge_loaded"])

    def test_schema_diagnostic_includes_issue_and_path_without_ansi(self):
        """Check schema diagnostic includes issue and path without ansi."""
        completed = subprocess.CompletedProcess([], 1,
            "\x1b[0;31m*suite=BSA issue=MISSING_KEY: Test_suite_info\x1b[0m\n"
            "  *at=BSA.test_results[0]\n")
        text = native.command_diagnostic(completed)
        self.assertIn("MISSING_KEY: Test_suite_info", text)
        self.assertIn("BSA.test_results[0]", text)
        self.assertNotIn("\x1b", text)

    def test_verified_portable_parser_is_used_without_mutating_original_context(self):
        """Check verified portable parser is used without mutating original context."""
        with tempfile.TemporaryDirectory() as folder:
            source = doctor.BASE_DIR
            portable = Path(folder) / "package" / "log_parser"
            portable.mkdir(parents=True)
            (portable / "suite_registry.json").write_text(
                (source / "suite_registry.json").read_text())
            ctx = Context(source, Path(folder) / "evidence", modes=("SR",))
            ctx.package_checked = True
            ctx.portable_parser = portable
            with mock.patch.object(native, "_run_route") as invoke:
                native.run_native(ctx)
            # Three independent PCIe outcomes add three calls, but only one
            # newly covered SR route, to the ten existing SR fixture calls.
            self.assertEqual(invoke.call_count, 13)
            self.assertTrue(
                all(call.args[0].parser_dir == portable for call in invoke.call_args_list))
            self.assertEqual(ctx.parser_dir, source)
            self.assertTrue(ctx.findings)

    def test_failed_package_never_falls_back_to_source(self):
        """Check failed package never falls back to source."""
        with tempfile.TemporaryDirectory() as folder:
            ctx = Context(doctor.BASE_DIR, folder)
            ctx.package_checked = True
            native.run_native(ctx)
            self.assertEqual(len(ctx.findings), 1)
            self.assertEqual(ctx.findings[0].status, "BLOCKED")
            self.assertEqual(ctx.findings[0].check_id, "NATIVE_PACKAGE_PREREQUISITE")

    def test_route_uses_public_cli_and_separate_schema(self):
        """Check route uses public CLI and separate schema."""
        with tempfile.TemporaryDirectory() as folder:
            ctx = Context(doctor.BASE_DIR, folder, modes=("SR",))
            ctx.native_outputs = []
            case = native.load_json(native.DATA_FILE)["scenarios"][0]
            data, expectation = golden()
            case = copy.deepcopy(case)
            case["raw"] = {"bsa.json": expectation}
            calls = []

            def invoke(command, directory, name, **kwargs):
                """Record commands and provide known output without running a parser."""
                calls.append([str(arg) for arg in command])
                if name == "parser":
                    output = Path(directory) / "output" / "acs_jsons"
                    output.mkdir(parents=True)
                    (output / "bsa.json").write_text(json.dumps(data))
                if name.startswith("schema-policy-"):
                    return subprocess.CompletedProcess(command, 0, json.dumps({
                        "category_provenance": {"source": "bundled", "invalid": False},
                        "errors": [], "omitted_missing_info_paths": [], "strict_error_count": 0}))
                return subprocess.CompletedProcess(command, 0, "ok")

            ctx.run = invoke
            native._run_route(ctx, case, "BSA", {"json_output": "bsa.json"})
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0][0], "bash")
            self.assertIn("--standalone", calls[0])
            self.assertIn("raw", calls[1])
            self.assertIn("-m", calls[2])
            self.assertIn("doctor_checks.artifacts", calls[2])
            self.assertIn("--schema-policy", calls[2])
            self.assertTrue(all(finding.status == "PASS" for finding in ctx.findings))
            self.assertEqual(len(ctx.native_outputs), 1)

    def test_policy_result_retains_strict_exit_and_legacy_warning(self):
        """Check policy result retains strict exit and legacy warning."""
        for source in ("explicit", "bundled", "unknown"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as folder:
                ctx = Context(doctor.BASE_DIR, folder)
                omitted = [] if source == "explicit" else ["/test_results/0"]
                errors = [{
                    "path": "/test_results/0",
                    "message": "Test_suite_info required"
                }] if source == "explicit" else []
                result = {
                    "category_provenance": {
                        "source": source,
                        "invalid": False,
                        "message": "Legacy run"
                    },
                    "errors": errors,
                    "omitted_missing_info_paths": omitted,
                    "strict_error_count": 3
                }
                ctx.run = mock.Mock(side_effect=[
                    subprocess.CompletedProcess(
                        [], 1, completed_schema_failure(Path(folder) / "bsa.json")),
                    subprocess.CompletedProcess([], 0, json.dumps(result))
                ])
                base = Path(folder)
                native._check_raw_schema(ctx, base, base / "output", base / "bsa.json", "SR", "BSA")
                schema = next(finding for finding in ctx.findings
                              if finding.check_id == "NATIVE_RAW_SCHEMA")
                self.assertEqual("FAIL" if source == "explicit" else "PASS", schema.status)
                self.assertIn("Strict validator exit 1", schema.actual)
                warnings = [finding for finding in ctx.findings if finding.status == "WARN"]
                self.assertEqual(source == "unknown", bool(warnings))

    def test_policy_evaluator_failure_does_not_turn_strict_failure_green(self):
        """Check policy evaluator failure does not turn strict failure green."""
        with tempfile.TemporaryDirectory() as folder:
            ctx = Context(doctor.BASE_DIR, folder)
            ctx.run = mock.Mock(side_effect=[
                subprocess.CompletedProcess([], 1,
                                            completed_schema_failure(Path(folder) / "bsa.json")),
                subprocess.CompletedProcess([], 2, "policy unavailable")
            ])
            base = Path(folder)
            native._check_raw_schema(ctx, base, base / "output", base / "bsa.json", "SR", "BSA")
            self.assertEqual("BLOCKED", ctx.findings[-1].status)

    def test_strict_validator_crash_or_fatal_file_error_cannot_receive_policy_exemption(self):
        """Check strict validator crash or fatal file error cannot receive policy exemption."""
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            raw = base / "bsa.json"
            completed = completed_schema_failure(raw)
            broken_outputs = [
                "Traceback (most recent call last):\nRuntimeError: independent validator crash",
                "*suite=BSA issue=JSON_FILE: failed to read JSON: permission denied count=1",
                completed_schema_failure(raw, "JSON_FILE"),
                completed_schema_failure(raw, "SCHEMA_FILE"),
                "Traceback (most recent call last):\nRuntimeError: independent validator crash\n" +
                completed,
                completed.replace(str(raw), str(base / "wrong.json")),
                completed.replace("(1 failed, 0 passed, 0 skipped)", "(0 validated)"),
                "ERROR: validation could not execute\n" + completed,
            ]
            for output in broken_outputs:
                with self.subTest(output=output):
                    ctx = Context(doctor.BASE_DIR, folder)
                    passing_policy = {
                        "category_provenance": {
                            "source": "bundled",
                            "invalid": False
                        },
                        "strict_error_count": 3,
                        "errors": [],
                        "omitted_missing_info_paths": ["/test_results/0"]
                    }
                    ctx.run = mock.Mock(side_effect=[
                        subprocess.CompletedProcess([], 1, output),
                        subprocess.CompletedProcess([], 0, json.dumps(passing_policy))
                    ])
                    native._check_raw_schema(ctx, base, base / "output", raw, "SR", "BSA")
                    self.assertEqual("FAIL", ctx.findings[-1].status)
                    self.assertEqual(1, ctx.run.call_count,
                                     "A failed strict execution must not reach applicability")

    def test_failed_parser_and_missing_outputs_do_not_report_identity_pass(self):
        """Check failed parser and missing outputs do not report identity pass."""
        with tempfile.TemporaryDirectory() as folder:
            ctx = Context(doctor.BASE_DIR, folder)
            ctx.native_outputs = []
            ctx.run = mock.Mock(return_value=subprocess.CompletedProcess([], 5, "parse failed"))
            case = native.load_json(native.DATA_FILE)["scenarios"][0]
            native._run_route(ctx, case, "BSA", {"json_output": "bsa.json"})
            statuses = {finding.check_id: finding.status for finding in ctx.findings}
            self.assertEqual(statuses["NATIVE_EXECUTION"], "FAIL")
            self.assertEqual(statuses["NATIVE_OUTPUT_INVENTORY"], "FAIL")
            self.assertEqual(statuses["NATIVE_RAW_IDENTITY"], "BLOCKED")


# Independent requirement rules and safe extraction of portable parser packages.

class IndependentPolicyTests(unittest.TestCase):
    """Ensure a registry change cannot silently change Doctor's expected rules."""

    def registry(self):
        """Build a registry copy from Doctor's separate requirement reference."""
        return {"suites": [{"canonical": name, "requirements": dict(requirements),
                            "modes": list(requirements), "json_output": name + ".json"}
                           for name, requirements in EXPECTED_REQUIREMENTS.items()]}

    def test_exact_contract_is_accepted(self):
        """Check exact contract is accepted."""
        self.assertEqual(policy_differences(self.registry()), [])

    def test_registry_cannot_rewrite_expected_requirement(self):
        """Check registry cannot rewrite expected requirement."""
        registry = self.registry()
        bsa = registry["suites"][0]
        bsa["requirements"]["DT"] = "M"
        expected = expected_leaves(registry["suites"])
        self.assertEqual(expected[0]["requirements"]["DT"], "R")
        self.assertTrue(policy_differences(registry))
        self.assertEqual(bsa["requirements"]["DT"], "M")  # No production mutation.

    def test_new_missing_suite_and_unsupported_mode_are_not_silent(self):
        """Check new missing suite and unsupported mode are not silent."""
        baseline = self.registry()
        for mutation in ("new", "missing", "mode", "requirement"):
            with self.subTest(mutation=mutation):
                registry = copy.deepcopy(baseline)
                if mutation == "new":
                    registry["suites"].append({"canonical": "NEW-SUITE", "json_output": "new.json"})
                elif mutation == "missing":
                    registry["suites"].pop()
                elif mutation == "mode":
                    registry["suites"][0]["modes"].remove("DT")
                else:
                    registry["suites"][0]["requirements"].clear()
                self.assertTrue(policy_differences(registry))


class PackageTests(unittest.TestCase):
    """Check archive paths, checksums and whether packaged files match source."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.archive = self.root / "parser.tar.gz"

    def bundle(self, name="systemready-log-parser/common/log_parser/doctor.py", link=False):
        """Build a tiny archive, optionally with a deliberately unsafe member."""
        with tarfile.open(self.archive, "w:gz") as archive:
            member = tarfile.TarInfo(name)
            if link:
                member.type = tarfile.SYMTYPE
                member.linkname = "/tmp/outside"
                archive.addfile(member)
            else:
                member.size = 4
                archive.addfile(member, io.BytesIO(b"test"))

    def test_matching_package_is_extractable(self):
        """Check matching package is extractable."""
        self.bundle()
        parser = extract_package(self.archive, self.root / "extract")
        self.assertEqual((parser / "doctor.py").read_text(), "test")

    def test_archive_traversal_and_links_are_rejected_before_extract(self):
        """Check archive traversal and links are rejected before extract."""
        for name, link in (("../outside", False), ("/absolute", False),
                           ("systemready-log-parser/../../outside", False),
                           ("systemready-log-parser/linked", True)):
            self.bundle(name, link)
            destination = self.root / "extract"
            with self.assertRaises(ValueError):
                extract_package(self.archive, destination)
            self.assertFalse(destination.exists())

    def test_checksum_and_filename_must_both_match(self):
        """Check checksum and filename must both match."""
        self.bundle()
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        checksum = self.archive.with_name(self.archive.name + ".sha256")
        checksum.write_text(digest + "  " + self.archive.name + "\n")
        self.assertEqual(verify_checksum(self.archive), digest)
        for value in ("0" * 64 + "  " + self.archive.name, digest + " other.tar.gz"):
            checksum.write_text(value)
            with self.assertRaises(ValueError):
                verify_checksum(self.archive)

    def test_missing_fixture_or_changed_runtime_is_detected(self):
        """Check missing fixture or changed runtime is detected."""
        source, packaged = self.root / "source", self.root / "package"
        source.mkdir()
        packaged.mkdir()
        for directory in (source, packaged):
            (directory / "doctor.py").write_text("original")
            (directory / "doctor_checks/data").mkdir(parents=True)
            (directory / "doctor_checks/data/native_cases.json").write_text("{}")
        self.assertEqual(package_differences(source, packaged), {})
        (packaged / "doctor.py").write_text("different")
        (packaged / "doctor_checks/data/native_cases.json").unlink()
        self.assertEqual(package_differences(source, packaged), {
            "missing": ["doctor_checks/data/native_cases.json"],
            "changed": ["doctor.py"]
        })


# Doctor's interpretation of passing, malformed, waived and missing results.

class ConditionalExecutionTests(unittest.TestCase):
    """Keep proof that a conditional suite ran separate from its JSON delivery."""

    def test_conditional_fixtures_cover_exactly_four_mode_filtered_routes(self):
        """Check conditional fixtures cover exactly four mode filtered routes."""
        cases = probes.conditional_execution_cases(("DT", "SR"))
        self.assertEqual({tuple(case[:2]) for case in cases}, {
            ("DT", "PFDI"), ("SR", "SBSA"), ("SR", "SBMR-IB"), ("SR", "SBMR-OOB")})
        self.assertEqual(len(cases), 4)
        self.assertEqual(len(probes.conditional_execution_cases(("DT",))), 1)
        self.assertEqual(len(probes.conditional_execution_cases(("SR",))), 3)
        self.assertEqual(probes.conditional_execution_cases(()), [])
        for mode, name, relative, content, provenance in cases:
            with self.subTest(suite=name):
                self.assertTrue(relative)
                self.assertTrue(provenance)
                self.assertEqual(len(probes.conditional_execution_records(name, content)),
                                 2 if name in ("SBSA", "PFDI") else 1)

    def test_rule_execution_needs_known_rule_and_terminal_result_pair(self):
        """Check rule execution needs known rule and terminal result pair."""
        for name, heading, rule in (("SBSA", "PE", "S_L3PE_01"), ("PFDI", "PFDI", "R0040")):
            header = "*** Running " + heading + " tests ***\n"
            record = rule + " : 23 : Example rule\n"
            for text in ("", header, header + "Tests complete: 0 executed\n", header + record,
                         header + "Result: PASSED\n", header + record + "Result: UNKNOWN\n",
                         header + record + "Result: SKIPPED\n", record + "Result: PASSED\n"):
                with self.subTest(suite=name, text=text):
                    self.assertEqual(probes.conditional_execution_records(name, text), [])
            for result in ("PASSED", "FAILED"):
                self.assertEqual(probes.conditional_execution_records(
                    name, header + record + "   Result:  " + result + "\n"),
                    [(rule + " : 23", "Example rule", result)])

    def test_robot_execution_uses_only_named_test_direct_terminal_status(self):
        """Check robot execution uses only named test direct terminal status."""
        for name in ("SBMR-IB", "SBMR-OOB"):
            for text in (
                    "", "<robot>", '<robot><suite><status status="PASS"/></suite></robot>',
                    '<robot><suite><test name="Host"><kw><status status="PASS"/></kw>'
                    '</test></suite></robot>',
                    '<robot><suite><test name="Host"><status status="UNKNOWN"/></test></suite></robot>',
                    '<robot><suite><test name="Host"><status status="SKIP"/></test></suite></robot>',
                    '<robot><suite><test><status status="PASS"/></test></suite></robot>'):
                with self.subTest(suite=name, text=text):
                    self.assertEqual(probes.conditional_execution_records(name, text), [])
            for direct, nested, expected in (("PASS", "FAIL", "PASSED"), ("FAIL", "PASS",
                                                                          "FAILED")):
                text = ('<robot><suite><test name="Host"><kw><status status="' + nested + '"/></kw>'
                        '<status status="' + direct +
                        '"/></test><status status="PASS"/></suite></robot>')
                self.assertEqual(probes.conditional_execution_records(name, text),
                                 [("Host", expected)])
        self.assertEqual(probes.conditional_execution_records("UNKNOWN", "Result: PASSED\n"), [])

    def control(self, directory):
        """Return literal native SBSA records, not values derived from the oracle."""
        raw = {
            "suite_summary": {
                "Total Rules Run": 2,
                "Passed": 2,
                "Failed": 0,
                "Total_failed_with_waiver": 0,
                "Skipped": 0,
                "Warnings": 0,
                "Passed (Partial)": 0,
                "PAL Not Supported": 0,
                "Not Implemented": 0
            },
            "test_results": [{
                "testcases": [{
                    "Test_case": "S_L3PE_01 : 23",
                    "Test_case_description": "Check PE Granule Support",
                    "Test_result": "PASSED"
                }, {
                    "Test_case": "S_L3PE_02 : 24",
                    "Test_case_description": "Check for 16-bit ASID support",
                    "Test_result": "PASSED"
                }]
            }]
        }
        folder = Path(directory) / "native-control"
        source = folder / "input/acs_results/uefi/SbsaResults.log"
        output = folder / "output/acs_jsons/sbsa.json"
        source.parent.mkdir(parents=True)
        output.parent.mkdir(parents=True)
        case = probes.conditional_execution_cases(("SR",))[0]
        source.write_text(case[3])
        output.write_text(json.dumps(raw))
        return {"exit": 0, "raw": raw, "traceback": False, "folder": str(folder),
                "counts": probes.counts(raw), "status": "Not Compliant", "html_status": None,
                "html_failed": None, "error": "", "evidence": [source, output]}, case

    def registry(self):
        """Limit these plumbing tests to the one selected conditional suite."""
        return {"SBSA": {**suite("SBSA", "R", "SR"), "json_output": "sbsa.json"}}

    def test_conditional_control_failure_or_changed_identity_blocks_probe(self):
        """Check conditional control failure or changed identity blocks probe."""
        for mutation in ("empty", "exit", "traceback", "identity"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                control, case = self.control(directory)
                if mutation == "empty":
                    control["raw"] = {"suite_summary": {}, "test_results": []}
                elif mutation == "identity":
                    # Counts remain exactly correct; identity must still be checked.
                    control["raw"]["test_results"][0]["testcases"][0][
                        "Test_case"] = "S_WRONG_01 : 23"
                elif mutation == "exit":
                    control["exit"] = 5
                else:
                    control["traceback"] = True
                ctx = Context(doctor.BASE_DIR, Path(directory) / "doctor", modes=("SR",))
                ctx.run = mock.Mock()
                with patch.object(probes, "conditional_execution_cases", return_value=[case]), \
                        patch.object(probes, "invoke", return_value=control):
                    probes.run_conditional_execution(ctx, self.registry())
                ctx.run.assert_not_called()
                self.assertEqual([(item.check_id, item.status) for item in ctx.findings],
                                 [("raw.conditional-control", "BLOCKED"),
                                  ("raw.conditional-execution", "BLOCKED")])

    def test_conditional_proof_does_not_require_a_green_merged_control(self):
        """Check conditional proof does not require a green merged control."""
        with tempfile.TemporaryDirectory() as directory:
            control, case = self.control(directory)
            self.assertEqual(control["status"], "Not Compliant")
            ctx = Context(doctor.BASE_DIR, Path(directory) / "doctor", modes=("SR",))
            ctx.run = mock.Mock(
                return_value=subprocess.CompletedProcess([], 5, "controlled merge rejection"))
            with patch.object(probes, "conditional_execution_cases", return_value=[case]), \
                    patch.object(probes, "invoke", return_value=control):
                probes.run_conditional_execution(ctx, self.registry())
            ctx.run.assert_called_once()
            self.assertEqual([(item.check_id, item.status) for item in ctx.findings], [
                ("raw.conditional-control", "PASS"), ("raw.conditional-execution", "BLOCKED")])

    def test_conditional_probe_omits_json_but_preserves_native_proof(self):
        # Direct merger input omission bypasses standalone's delivery guard:
        # its mismatch is a boundary warning, not a proven public-flow failure.
        """Check conditional probe omits JSON but preserves native proof."""
        for retained, verdict in ((True, "PASS"), (False, "WARN")):
            with self.subTest(retained=retained), tempfile.TemporaryDirectory() as directory:
                control, case = self.control(directory)
                originals = {path: path.read_bytes() for path in control["evidence"]}
                ctx = Context(doctor.BASE_DIR, Path(directory) / "doctor", modes=("SR",))

                def merge(command, folder, name):
                    """Model whether a missing JSON keeps its mandatory requirement."""
                    destination = Path(command[5])
                    baseline = name == "merge-baseline"
                    self.assertIn(name, ("merge-baseline", "merge-withheld-json"))
                    self.assertEqual(any(Path(arg).name == "sbsa.json" for arg in command),
                                     baseline)
                    requirement = "Mandatory" if baseline or retained else "Recommended"
                    destination.write_text(
                        json.dumps({
                            "Suite_Name: acs_info": {
                                "ACS Results Summary": {
                                    "Suite_Name: " + requirement + "  : SBSA_compliance":
                                    "Compliant" if baseline else
                                    "Not Compliant: not run" if retained else "Not Run",
                                    "Overall Compliance Result":
                                    "Not Compliant" if retained and not baseline else "Compliant"
                                }
                            }
                        }))
                    return subprocess.CompletedProcess(command, 0, "merged")

                ctx.run = mock.Mock(side_effect=merge)
                with patch.object(probes, "conditional_execution_cases", return_value=[case]), \
                        patch.object(probes, "invoke", return_value=control):
                    probes.run_conditional_execution(ctx, self.registry())
                self.assertEqual(ctx.run.call_count, 2)
                self.assertEqual([(item.check_id, item.status) for item in ctx.findings], [
                    ("raw.conditional-control", "PASS"), ("raw.conditional-execution", verdict)])
                self.assertEqual({path: path.read_bytes() for path in originals}, originals)
                manifest = json.loads(
                    (ctx.case_dir("conditional/SR/SBSA") / "scenario.json").read_text())
                self.assertEqual(manifest["withheld_json"], "sbsa.json")
                self.assertEqual(manifest["executed_suite"], "SBSA")
                self.assertEqual(manifest["expected_overall"], "not_compliant")
                self.assertIn("direct-merger", manifest["scope"])
                self.assertIn("bypasses that safeguard", manifest["scope"])
                self.assertIn("normal-flow conversion failure not tested", ctx.findings[-1].actual)

    def test_conditional_probe_blocks_unrelated_baseline_or_omission_failures(self):
        """Check conditional probe blocks unrelated baseline or omission failures."""
        for break_at, calls in (("merge-baseline", 1), ("merge-withheld-json", 2)):
            with self.subTest(break_at=break_at), tempfile.TemporaryDirectory() as directory:
                control, case = self.control(directory)
                ctx = Context(doctor.BASE_DIR, Path(directory) / "doctor", modes=("SR",))
                registry = {**self.registry(), "FWTS": {
                    **suite("FWTS", "M", "SR"), "json_output": "fwts.json"}}

                def merge(command, folder, name):
                    """Model an unrelated failure in either comparison report."""
                    broken = name == break_at
                    baseline = name == "merge-baseline"
                    Path(command[5]).write_text(
                        json.dumps({
                            "Suite_Name: acs_info": {
                                "ACS Results Summary": {
                                    "Suite_Name: Mandatory  : SBSA_compliance":
                                    "Compliant" if baseline else "Not Compliant: not run",
                                    "Suite_Name: Mandatory  : SBBR-FWTS_compliance":
                                    "Not Compliant" if broken else "Compliant",
                                    "Overall Compliance Result":
                                    "Not Compliant" if broken or not baseline else "Compliant"
                                }
                            }
                        }))
                    return subprocess.CompletedProcess(command, 0, "merged")

                ctx.run = mock.Mock(side_effect=merge)
                with patch.object(probes, "conditional_execution_cases", return_value=[case]), \
                        patch.object(probes, "invoke", return_value=control):
                    probes.run_conditional_execution(ctx, registry)
                self.assertEqual(ctx.run.call_count, calls)
                self.assertEqual([(item.check_id, item.status) for item in ctx.findings], [
                    ("raw.conditional-control", "PASS"), ("raw.conditional-execution", "BLOCKED")])


class ProbeTests(unittest.TestCase):
    """Verify that bad input, crashes and missing evidence never look like success."""

    def test_new_bad_input_jobs_cover_each_requested_route_and_all_four_cases(self):
        """Check new bad input jobs cover each requested route and all four cases."""
        wanted = {("DT", name) for name in (
            "DTB-ALIGNMENT", "NETWORK-BOOT", "OS-TESTS", "PFDI", "POST-SCRIPT",
            "PSCI", "RESERVED-MEMORY-MAP", "SCMI", "SMBIOS", "DT-KSELFTEST", "RUNTIME-DEV-MAP")}
        wanted.update({("SR", "OS-TESTS"), ("SR", "PCIE-OPTION-ROM-ARCH-AUDIT")})
        jobs = probes.additional_raw_jobs(("DT", "SR"))
        self.assertEqual({tuple(job[:2]) for job in jobs}, wanted)
        self.assertEqual(len(jobs), len(wanted), "A duplicate route must not inflate coverage")
        for mode, name, relative, complete, broken, _counts in jobs:
            with self.subTest(mode=mode, suite=name):
                self.assertEqual({case[0] for case in broken}, {
                    "empty-log", "header-only", "truncated-log", "malformed-log"})
                self.assertEqual(len(broken), 4)
                self.assertTrue(complete)
                empty = next(content for kind, content, _ in broken if kind == "empty-log")
                self.assertTrue(all(not text for text in empty.values()) if isinstance(empty, dict)
                                else not empty)
                for kind, content, caveat in broken:
                    self.assertNotEqual(content, complete,
                                        kind + " must actually alter the native input")
                    self.assertFalse(caveat, "Known missing checks must not be silently downgraded")
                if isinstance(complete, dict):
                    self.assertIsNone(relative)
                    self.assertTrue(all(isinstance(value, str) for value in complete.values()))
                else:
                    self.assertIsInstance(relative, str)

    def test_new_bad_input_jobs_respect_selected_modes(self):
        """Check new bad input jobs respect selected modes."""
        dt = probes.additional_raw_jobs(("DT",))
        sr = probes.additional_raw_jobs(("SR",))
        self.assertEqual(len(dt), 11)
        self.assertEqual(len(sr), 2)
        self.assertTrue(all(job[0] == "DT" for job in dt))
        self.assertTrue(all(job[0] == "SR" for job in sr))
        self.assertNotIn("PCIE-OPTION-ROM-ARCH-AUDIT", {job[1] for job in dt})
        self.assertEqual(probes.additional_raw_jobs(()), [])

    def test_psci_header_only_is_a_capture_compatible_kernel_introduction(self):
        """Check psci header only is a capture compatible kernel introduction."""
        job = next(job for job in probes.additional_raw_jobs(("DT",)) if job[1] == "PSCI")
        self.assertEqual(job[2], "linux_tools/psci/psci_kernel.log")
        header = next(content for name, content, _ in job[4] if name == "header-only")
        self.assertEqual(header, "psci: probing for conduit method from DT.\n")
        producer = (Path(__file__).resolve().parents[2] / "SystemReady-devicetree-band" /
                    "Yocto/meta-woden/recipes-acs/install-files/files/init.sh").read_text()
        self.assertIn("dmesg | grep psci >", producer)
        self.assertTrue(all("psci" in line for line in header.splitlines()))
        self.assertNotIn("PSCIv", header)
        self.assertNotIn("Booting Linux kernel", header)

    def test_raw_group_reports_scheduled_but_unevaluated_cases_as_missing_coverage(self):
        """Check raw group reports scheduled but unevaluated cases as missing coverage."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(doctor.BASE_DIR, directory)
            with patch.object(probes, "html_capability", return_value=False), \
                    patch.object(probes, "run_conditional_execution"), \
                    patch.object(probes, "family", return_value=set()) as family, \
                    patch.object(probes, "waiver_probe"), \
                    patch.object(probes, "waiver_idempotence"), \
                    patch.object(probes, "stale_rerun"):
                probes.run_raw(ctx)
            self.assertTrue(family.called)
            coverage = {item.mode: item for item in ctx.findings if item.check_id == "raw.coverage"}
            self.assertEqual(set(coverage), {"DT", "SR"})
            for mode, suite, *_ in probes.additional_raw_jobs(("DT", "SR")):
                self.assertEqual(coverage[mode].status, "WARN")
                self.assertIn(suite + ": empty-log, header-only, malformed-log, truncated-log",
                              coverage[mode].actual)
            self.assertFalse(any(item.status == "PASS" for item in ctx.findings))

    def test_bad_input_control_failure_cannot_claim_negative_coverage(self):
        """Check bad input control failure cannot claim negative coverage."""
        broken = [("empty-log", "", ""), ("header-only", "Introduction\n", "")]
        for change in ({"exit": 5}, {"counts": {"passed": 0, "failed": 0, "failed_with_waiver": 0}},
                       {"status": None}, {"status": "Not Run"}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                ctx = Context(directory, directory)
                actual = {**self.observation(), "html_failed": 0, "evidence": [], **change}
                with patch.object(probes, "invoke", return_value=actual) as invoke:
                    executed = probes.family(ctx, {}, "DT", "PFDI", "uefi/pfdiresults.log",
                                             "complete", broken, html_available=False)
                self.assertEqual(executed, set())
                self.assertEqual(invoke.call_count, 1)
                self.assertEqual([(item.check_id, item.status) for item in ctx.findings], [
                    ("raw.positive", "BLOCKED"), ("raw.incomplete.coverage", "BLOCKED")])

    def test_bad_input_coverage_counts_only_evaluated_not_blocked_cases(self):
        """Check bad input coverage counts only evaluated not blocked cases."""
        positive = {**self.observation(), "html_failed": 0, "evidence": []}
        rejected = {**positive, "exit": 5, "status": None, "html_status": None}
        observations = [
            positive, {
                **positive, "exit": 3
            }, {
                **positive, "exit": 4
            }, rejected, positive
        ]
        broken = [(name, name, "") for name in (
            "empty-log", "header-only", "truncated-log", "malformed-log")]
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            with patch.object(probes, "invoke", side_effect=observations):
                executed = probes.family(ctx, {}, "DT", "PFDI", "uefi/pfdiresults.log",
                                         "complete", broken, html_available=False)
            self.assertEqual(executed, {"truncated-log", "malformed-log"})
            results = {item.check_id: item.status for item in ctx.findings}
            self.assertEqual(results["raw.empty-log"], "BLOCKED")
            self.assertEqual(results["raw.header-only"], "BLOCKED")
            self.assertEqual(results["raw.truncated-log"], "PASS")
            self.assertEqual(results["raw.malformed-log"], "FAIL")

    def test_zero_negative_cases_cannot_claim_bad_input_coverage(self):
        """Check zero negative cases cannot claim bad input coverage."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            actual = {**self.observation(), "html_failed": 0, "evidence": []}
            with patch.object(probes, "invoke", return_value=actual) as invoke:
                executed = probes.family(ctx, {}, "DT", "PFDI", "uefi/pfdiresults.log",
                                         "complete", [], html_available=False)
            self.assertEqual(executed, set())
            self.assertEqual(invoke.call_count, 1)
            self.assertFalse(any(item.check_id != "raw.positive" for item in ctx.findings))

    def test_completed_failure_control_requires_exact_counts_and_non_green_status(self):
        """Check completed failure control requires exact counts and non green status."""
        expected_counts = {**probes.counts({}), "failed": 1}
        complete = {**self.observation(), "status": "Not Compliant", "html_status": "Not Compliant",
                    "counts": dict(expected_counts), "html_failed": 1, "evidence": []}
        for changed, expected_coverage in (
                ({}, {"empty-log"}), ({"status": "Compliant"}, set()),
                ({"status": "UNKNOWN"}, set()), ({"status": "Not Run"}, set()),
                ({"status": "Not Compliant (Not Run)"}, set()),
                ({"counts": {**expected_counts, "failed": 0}}, set()),
                ({"counts": {**expected_counts, "failed": 2}}, set()),
                ({"counts": {**expected_counts, "skipped": 1}}, set()),
                ({"counts": {**expected_counts, "failed_with_waiver": 1}}, set()),
                ({"counts": {**expected_counts, "aborted": 1}}, set()),
                ({"exit": 5}, set())):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                ctx = Context(directory, directory)
                observations = [{**complete, **changed},
                                {**complete, "exit": 5, "status": None, "html_status": None}]
                with patch.object(probes, "invoke", side_effect=observations):
                    executed = probes.family(ctx, {}, "DT", "POST-SCRIPT", "post-script/log.txt",
                                             "A complete recorded failure", [("empty-log", "", "")],
                                             control_counts=expected_counts, html_available=False)
                self.assertEqual(executed, expected_coverage)
                self.assertEqual(ctx.findings[0].status, "PASS" if expected_coverage else "BLOCKED")

    def test_multiple_input_files_are_forwarded_without_changing_controls(self):
        """Check multiple input files are forwarded without changing controls."""
        complete = {"../os-logs/install.log": "Installation: PASSED\n",
                    "../os-logs/runtime/check.log": "Runtime check: PASSED\n"}
        incomplete = {"../os-logs/install.log": "Installation: PASSED\n",
                      "../os-logs/runtime/check.log": "Runtime check started\n"}
        before = deepcopy((complete, incomplete))
        actual = {**self.observation(), "html_failed": 0, "evidence": []}
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            rejected = {**actual, "exit": 5, "status": None, "html_status": None}
            with patch.object(probes, "invoke", side_effect=[actual, rejected]) as invoke:
                executed = probes.family(ctx, {}, "SR", "OS-TESTS", None, complete,
                                         [("truncated-log", incomplete, "")], html_available=False)
            self.assertEqual(executed, {"truncated-log"})
            self.assertEqual(invoke.call_args_list[0].args[5], complete)
            self.assertEqual(invoke.call_args_list[1].args[5], incomplete)
        self.assertEqual((complete, incomplete), before)

    def test_generated_probe_inputs_stay_inside_own_case_directory(self):
        """Check generated probe inputs stay inside own case directory."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, Path(directory) / "output")
            files = {"linux_tools/nested/check.log": "result\n",
                     "../os-logs/setup.log": "setup\n"}
            before = deepcopy(files)
            ctx.run = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "done"))
            with patch.object(probes, "observe", return_value={}) as observe:
                probes.invoke(ctx, {}, "SR", "OS-TESTS", "safe-multifile", files)
            base = ctx.case_dir("raw/SR/OS-TESTS/safe-multifile")
            self.assertEqual((base / "input/acs_results/linux_tools/nested/check.log").read_text(),
                             "result\n")
            self.assertEqual((base / "input/os-logs/setup.log").read_text(), "setup\n")
            self.assertEqual(files, before)
            observe.assert_called_once()
            # A log path may name a sibling OS folder, but never escape the
            # disposable case into another job, the repository or real logs.
            with self.assertRaisesRegex(ValueError, "escaped"):
                probes.invoke(ctx, {}, "SR", "OS-TESTS", "unsafe-multifile",
                              {"../../../outside.log": "must not be written"})
            self.assertFalse((Path(directory) / "outside.log").exists())

    def observation(self):
        """Start with one passing result that each test can change deliberately."""
        return {"exit": 0, "status": "Compliant", "html_status": "Compliant",
                "counts": {"passed": 1, "failed": 0, "failed_with_waiver": 0},
                "traceback": False}

    def test_compliant_is_not_substring_match(self):
        """Check compliant is not substring match."""
        self.assertTrue(probes.green("Compliant (with waivers)"))
        for status in (None, "Not Compliant", "Not Compliant (Not Run)", "Not Run"):
            self.assertFalse(probes.green(status))

    def test_positive_control_requires_real_passed_outcome(self):
        """Check positive control requires real passed outcome."""
        actual = self.observation()
        self.assertTrue(probes.control_ok(actual))
        actual["counts"]["passed"] = 0
        self.assertFalse(probes.control_ok(actual))

    def test_positive_control_requires_both_json_and_html(self):
        """Check positive control requires both JSON and HTML."""
        actual = self.observation()
        actual["html_status"] = None
        self.assertFalse(probes.control_ok(actual))
        actual["html_status"] = "Not Compliant"
        self.assertFalse(probes.control_ok(actual))

    def test_positive_control_rejects_invented_waiver(self):
        """Check positive control rejects invented waiver."""
        actual = self.observation()
        actual["counts"]["failed_with_waiver"] = 1
        self.assertFalse(probes.control_ok(actual))

    def test_incomplete_green_is_failure(self):
        """Check incomplete green is failure."""
        self.assertEqual(probes.invalid_verdict(self.observation()), "FAIL")

    def test_incomplete_non_green_is_safe(self):
        """Check incomplete non green is safe."""
        actual = self.observation()
        actual.update(status="Not Compliant (Not Run)", html_status="Not Compliant (Not Run)")
        self.assertEqual(probes.invalid_verdict(actual), "PASS")

    def test_json_html_disagreement_is_failure(self):
        """Check JSON HTML disagreement is failure."""
        actual = self.observation()
        actual["status"] = "Not Compliant"
        self.assertEqual(probes.invalid_verdict(actual), "FAIL")

    def test_rejected_input_is_not_confused_with_crash(self):
        """Check rejected input is not confused with crash."""
        actual = self.observation()
        actual.update(exit=5, status=None, html_status=None)
        self.assertEqual(probes.invalid_verdict(actual), "PASS")
        actual["traceback"] = True
        self.assertEqual(probes.invalid_verdict(actual), "FAIL")

    def test_rejected_input_cannot_hide_published_green_artifacts(self):
        """Check rejected input cannot hide published green artifacts."""
        for changed in ({"status": "Compliant", "html_status": None},
                        {"status": None, "html_status": "Compliant"},
                        {"status": "Compliant", "html_status": "Compliant"}):
            with self.subTest(changed=changed):
                actual = {**self.observation(), "exit": 5, **changed}
                self.assertEqual(probes.invalid_verdict(actual), "FAIL")

    def test_empty_log_needs_not_run_without_invented_results(self):
        """Check empty log needs not run without invented results."""
        positive = {**self.observation(), "html_failed": 0, "evidence": []}
        zero_counts = probes.counts({})
        empty = {**positive, "status": "Not Run", "html_status": None,
                 "counts": zero_counts}
        cases = [({}, "PASS"), ({"status": "Not Compliant (Not Run)"}, "PASS"),
                 ({"status": "Not Compliant: not run"}, "PASS"),
                 ({"status": "Not Compliant"}, "FAIL"), ({"status": None}, "FAIL"),
                 ({"exit": 5, "status": None}, "FAIL"),
                 ({"exit": 5, "status": "Not Compliant",
                   "counts": {**zero_counts, "failed": 1}}, "FAIL")]
        cases.extend(({"counts": {**zero_counts, counter: 1}}, "FAIL") for counter in zero_counts)
        for changed, wanted in cases:
            for name in ("empty-log", "header-only"):
                with self.subTest(case=name,
                                  changed=changed), tempfile.TemporaryDirectory() as directory:
                    ctx = Context(directory, directory)
                    with patch.object(probes,
                                      "invoke",
                                      side_effect=[positive, {
                                          **empty,
                                          **changed
                                      }]):
                        executed = probes.family(ctx, {}, "DT", "PFDI", "uefi/pfdiresults.log",
                                                 "complete", [(name, "", "")], html_available=False)
                    self.assertEqual(executed, {name})
                    self.assertEqual(ctx.findings[-1].status, wanted)
                    self.assertEqual(ctx.findings[-1].expected,
                                     "Publish Not Run with zero executed outcomes")

    def test_empty_verdict_cannot_accept_nonzero_exit_or_crash(self):
        """Check empty verdict cannot accept nonzero exit or crash."""
        empty = {**self.observation(), "status": "Not Run", "html_status": None,
                 "counts": probes.counts({})}
        for changed in ({"exit": 1}, {"exit": 5}, {"exit": -11}, {"traceback": True},
                        {"exit": 5, "traceback": True}, {"html_status": "Compliant"}):
            with self.subTest(changed=changed):
                self.assertEqual(probes.empty_verdict({**empty, **changed}), "FAIL")

    def test_empty_verdict_keeps_missing_prerequisites_blocked(self):
        """Check empty verdict keeps missing prerequisites blocked."""
        for code in (3, 4):
            for counter in (None, *probes.counts({})):
                with self.subTest(exit=code, counter=counter):
                    actual = {**self.observation(), "exit": code, "status": None,
                              "html_status": None, "counts": probes.counts({})}
                    if counter:
                        actual["counts"][counter] = 1
                    self.assertEqual(probes.empty_verdict(actual), "BLOCKED")

    def test_empty_verdict_rejects_every_invented_outcome_even_on_rejection(self):
        """Check empty verdict rejects every invented outcome even on rejection."""
        for code in (0, 5):
            for counter in probes.counts({}):
                with self.subTest(exit=code, counter=counter):
                    actual = {**self.observation(), "exit": code, "status": "Not Run",
                              "html_status": None, "counts": {**probes.counts({}), counter: 1}}
                    self.assertEqual(probes.empty_verdict(actual), "FAIL")

    def test_missing_dependencies_or_invalid_fixture_are_blocked(self):
        """Check missing dependencies or invalid fixture are blocked."""
        for code in (3, 4):
            actual = self.observation()
            actual["exit"] = code
            self.assertEqual(probes.invalid_verdict(actual), "BLOCKED")

    def test_missing_artifacts_cannot_pass(self):
        """Check missing artifacts cannot pass."""
        for field in ("status", "html_status"):
            actual = self.observation()
            actual.update(status="Not Run", html_status="Not Run")
            actual[field] = None
            self.assertEqual(probes.invalid_verdict(actual), "BLOCKED")
        # When the other artifact is actually green, that is already evidence
        # of the defect, even if its partner artifact is missing.
        for field in ("status", "html_status"):
            actual = self.observation()
            actual[field] = None
            self.assertEqual(probes.invalid_verdict(actual), "FAIL")

    def test_parent_only_fixture_keeps_failures_not_subtests(self):
        """Check parent only fixture keeps failures not subtests."""
        complete = probes.sct_log(failed=True)
        parent_only = probes.sct_log(failed=True, parent_only=True)
        self.assertEqual(parent_only.count(": [FAIL]"), 2)
        self.assertNotIn(" -- FAIL", parent_only)
        self.assertEqual(complete.count(" -- FAIL"), 2)

    def test_fwts_fixture_preserves_assertion_multiplicity(self):
        """Check FWTS fixture preserves assertion multiplicity."""
        text = probes.fwts_log(failed=2)
        self.assertEqual(text.count("FAILED: Test 1"), 2)
        self.assertIn("0 passed, 2 failed", text)

    def test_robot_unknown_and_missing_are_distinct(self):
        """Check robot unknown and missing are distinct."""
        self.assertNotIn("<status", probes.robot_log(None))
        self.assertIn('status="UNKNOWN"', probes.robot_log("UNKNOWN"))

    def test_counts_do_not_count_waiver_as_failed(self):
        """Check counts do not count waiver as failed."""
        raw = {"suite_summary": {"total_passed": 1, "total_failed": 0,
                                  "total_failed_with_waiver": 2}}
        before = copy.deepcopy(raw)
        self.assertEqual(probes.counts(raw)["failed"], 0)
        self.assertEqual(probes.counts(raw)["failed_with_waiver"], 2)
        self.assertEqual(raw, before)

    def test_bsa_uses_its_native_summary_keys(self):
        """Check BSA uses its native summary keys."""
        self.assertEqual(
            probes.counts(
                {"suite_summary": {
                    "Passed": 2,
                    "Failed": 1,
                    "Total_failed_with_waiver": 3
                }})["passed"], 2)
        self.assertEqual(probes.counts({"suite_summary": {"Failed": 1}})["failed"], 1)

    def test_crash_description_is_in_plain_output(self):
        """Check crash description is in plain output."""
        actual = self.observation()
        actual.update(html_failed=None,
                      error='TypeError: can only concatenate list (not "str") to list')
        self.assertIn("TypeError:", probes.brief(actual))

    def test_html_cells_and_entities_are_read_without_script_execution(self):
        """Check HTML cells and entities are read without script execution."""
        html = probes.ReportTables()
        html.feed('<table class="acs-compliance-table"><tr><th>BSA</th>'
                  '<td><span>Recommended</span></td><td>Not Compliant</td></tr></table>'
                  '<table><tr><td>Failed</td><td>2</td></tr></table>')
        self.assertEqual(html.tables[0]["rows"], [["BSA", "Recommended", "Not Compliant"]])
        self.assertEqual(html.tables[1]["rows"], [["Failed", "2"]])

    def test_mode_aware_suite_status(self):
        """Check mode aware suite status."""
        registry = {"SCT": {"requirement_key": "SCT"}}
        merged = {"Suite_Name: acs_info": {"ACS Results Summary": {
            "Suite_Name: Mandatory  : EBBR-SCT_compliance": "Not Compliant",
            "Suite_Name: Mandatory  : SBBR-SCT_compliance": "Compliant"}}}
        self.assertEqual(probes.suite_status(merged, "SCT", "DT", registry), "Not Compliant")
        self.assertEqual(probes.suite_status(merged, "SCT", "SR", registry), "Compliant")

    def test_json_positive_control_does_not_depend_on_new_html_layout(self):
        """Check JSON positive control does not depend on new HTML layout."""
        actual = self.observation()
        actual["html_status"] = None
        self.assertTrue(probes.control_ok(actual, require_html=False))
        self.assertEqual(probes.invalid_verdict(actual, require_html=False), "FAIL")
        actual["status"] = "Not Compliant (Not Run)"
        self.assertEqual(probes.invalid_verdict(actual, require_html=False), "PASS")
        actual["status"] = None
        self.assertEqual(probes.invalid_verdict(actual, require_html=False), "BLOCKED")

    def test_missing_html_does_not_suppress_malformed_log_case(self):
        """Check missing HTML does not suppress malformed log case."""
        actual = {**self.observation(), "html_status": None, "html_failed": 0, "evidence": []}
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            with patch.object(probes, "invoke", return_value=actual) as invoke:
                probes.family(ctx, {}, "DT", "BSA", "bsa.log", "good",
                              [("empty-log", "", "")], html_available=False)
            self.assertEqual(invoke.call_count, 2)
            self.assertEqual([(item.check_id, item.status) for item in ctx.findings],
                             [("raw.positive", "PASS"), ("raw.empty-log", "FAIL")])

    def test_supported_but_missing_html_is_failure_and_raw_checks_continue(self):
        """Check supported but missing HTML is failure and raw checks continue."""
        actual = {**self.observation(), "html_status": None, "html_failed": 0, "evidence": []}
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            with patch.object(probes, "invoke", return_value=actual) as invoke:
                probes.family(ctx, {}, "DT", "BSA", "bsa.log", "good", [("empty-log", "", "")])
            self.assertEqual(invoke.call_count, 2)
            self.assertEqual([(item.check_id, item.status) for item in ctx.findings],
                             [("raw.positive", "PASS"), ("raw.html-compliance", "FAIL"),
                              ("raw.empty-log", "FAIL"), ("raw.html-compliance", "FAIL")])

    def test_waiver_json_checks_do_not_require_new_html_layout(self):
        """Check waiver JSON checks do not require new HTML layout."""
        actual = {**self.observation(), "html_status": None, "html_failed": 0, "evidence": []}
        expected = ({
            "passed": 1,
            "failed": 0
        }, {
            "passed": 1,
            "failed": 0
        }, "Unmatched waiver is inert")
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            with patch.object(probes, "invoke", return_value=actual):
                probes.waiver_probe(ctx, {}, "DT-KSELFTEST", "test.log", "pass", {},
                                   "unmatched", expected, html_available=False)
            self.assertEqual([(item.check_id, item.status) for item in ctx.findings],
                             [("waiver.unmatched", "PASS")])

    def test_raw_html_capability_absent_is_one_blocked_check(self):
        """Check raw HTML capability absent is one blocked check."""
        with tempfile.TemporaryDirectory() as directory:
            ctx = Context(directory, directory)
            source = Path(directory) / "generate_acs_summary.py"
            source.write_text("def legacy_report():\n    pass\n", encoding="utf-8")
            self.assertFalse(probes.html_capability(ctx))
            self.assertEqual(len(ctx.findings), 1)
            self.assertEqual(ctx.findings[0].check_id, "raw.html-capability")
            self.assertEqual(ctx.findings[0].status, "BLOCKED")
            source.write_text("def _summary_cards():\n    raise RuntimeError('broken')\n"
                              "def inject_detail_compliance():\n    pass\n", encoding="utf-8")
            self.assertTrue(probes.html_capability(ctx))
            # Present functions are not certified correct by source detection:
            # render failures/missing tables must still fail the per-report check.
            self.assertEqual(len(ctx.findings), 1)


# When category metadata is required, and how its supplied file is recorded.

class SchemaPolicyTests(unittest.TestCase):
    """Check category-specific schema rules without changing the saved schema."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="doctor_category_policy_")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "definitions": {
                "metadata": {
                    "type": "object",
                    "required": ["Main Readiness Grouping", "SRS scope", "Waivable"],
                    "properties": {
                        "Main Readiness Grouping": {
                            "type": "string"
                        },
                        "SRS scope": {
                            "type": "string"
                        },
                        "Waivable": {
                            "type": "string"
                        },
                        "Test_suite_info": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    }
                },
                "entry": {
                    "allOf": [{
                        "$ref": "#/definitions/metadata"
                    }, {
                        "required": ["Test_suite", "Test_suite_info"],
                        "properties": {
                            "Test_suite": {
                                "type": "string",
                                "not": {
                                    "const": "Unknown"
                                }
                            }
                        }
                    }],
                    "unevaluatedProperties":
                    False
                },
                "raw": {
                    "type": "object",
                    "required": ["test_results"],
                    "properties": {
                        "test_results": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/entry"
                            }
                        }
                    },
                    "unevaluatedProperties": False
                }
            },
            "properties": {
                "Suite_Name: BSA": {
                    "$ref": "#/definitions/raw"
                }
            }
        }
        self.path = self.base / "schema.json"
        self.path.write_text(json.dumps(self.schema))
        self.entry = {"Test_suite": "PE", "Main Readiness Grouping": "physical",
                      "SRS scope": "Mandatory", "Waivable": "no"}

    def evaluate(self, source="bundled", entry=None, merged=False):
        """Check a raw or merged sample and verify both inputs stay unchanged."""
        raw = {"test_results": [self.entry if entry is None else entry]}
        data = {"Suite_Name: BSA": raw} if merged else raw
        before = deepcopy(data)
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        result = policy.evaluate_schema(self.path, "" if merged else "#/definitions/raw", data,
                                        {"source": source})
        self.assertEqual(before, data)
        self.assertEqual(digest, hashlib.sha256(self.path.read_bytes()).hexdigest())
        return result

    def test_bundled_and_legacy_omit_only_missing_info_and_its_cascades(self):
        """Check bundled and legacy omit only missing info and its cascades."""
        for source in ("bundled", "unknown"):
            for merged in (False, True):
                with self.subTest(source=source, merged=merged):
                    result = self.evaluate(source, merged=merged)
                    self.assertEqual([], result["errors"])
                    self.assertGreater(result["strict_error_count"], 1)
                    self.assertEqual(1, len(result["omitted_missing_info_paths"]))

    def test_explicit_missing_info_stays_required_even_without_description(self):
        """Check explicit missing info stays required even without description."""
        result = self.evaluate("explicit")
        self.assertTrue(
            any(error["validator"] == "required" and "Test_suite_info" in error["message"]
                for error in result["errors"]))
        self.assertEqual([], result["omitted_missing_info_paths"])

    def test_info_present_is_always_validated(self):
        """Check info present is always validated."""
        for value in (None, "not a list", 1, {}, [True]):
            for source in ("explicit", "bundled", "unknown"):
                with self.subTest(value=value, source=source):
                    result = self.evaluate(source, dict(self.entry, Test_suite_info=value))
                    self.assertTrue(any(error["validator"] == "type" for error in result["errors"]))
        self.assertEqual([],
                         self.evaluate("explicit",
                                       dict(self.entry,
                                            Test_suite_info=["PE information"]))["errors"])

    def test_other_required_fields_unknown_suite_and_unknown_properties_still_fail(self):
        """Check other required fields unknown suite and unknown properties still fail."""
        for field in ("Main Readiness Grouping", "SRS scope", "Waivable"):
            row = deepcopy(self.entry)
            del row[field]
            result = self.evaluate(entry=row)
            self.assertTrue(
                any(error["validator"] == "required" and field in error["message"]
                    for error in result["errors"]))
        result = self.evaluate(entry=dict(self.entry, Test_suite="Unknown"))
        self.assertTrue(any(error["validator"] == "not" for error in result["errors"]))
        result = self.evaluate(entry=dict(self.entry, unexpected="real extra field"))
        self.assertTrue(
            any(error["validator"] == "unevaluatedProperties" and "unexpected" in error["message"]
                for error in result["errors"]))

    def test_only_schema_required_lists_are_changed(self):
        """Check only schema required lists are changed."""
        schema = {"required": ["Test_suite_info", "other"],
                  "const": {"required": ["Test_suite_info"]},
                  "default": {"required": ["Test_suite_info"]},
                  "examples": [{"required": ["Test_suite_info"]}]}
        original = deepcopy(schema)
        effective = policy.applicable_schema(schema)
        self.assertEqual(["other"], effective["required"])
        for key in ("const", "default", "examples"):
            self.assertEqual(schema[key], effective[key])
        self.assertEqual(original, schema)


class CategoryProvenanceTests(unittest.TestCase):
    """Check the record of which category file a report actually used."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="doctor_category_provenance_")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.report = self.base / "report"
        self.report.mkdir()
        self.source = self.base / "supplied.json"
        self.source.write_text('{"category":[{"Suite":"BSA","Test Suite":"PE"}]}')

    def record(self, explicit=True):
        """Record a supplied category file or the use of bundled defaults."""
        return record_category_provenance(
            self.report,
            SimpleNamespace(mode="SR", test_category=str(self.source) if explicit else None),
            self.source)

    def test_explicit_snapshot_is_consumed_and_bound_to_mode_and_digest(self):
        """Check explicit snapshot is consumed and bound to mode and digest."""
        original = self.source.read_bytes()
        effective = self.record()
        self.assertNotEqual(self.source, effective)
        self.assertEqual(original, effective.read_bytes())
        self.assertEqual(original, self.source.read_bytes())
        self.source.write_text('{"changed_after_snapshot":true}')
        self.assertEqual(original, effective.read_bytes())
        provenance = policy.category_provenance(self.report, "SR")
        self.assertEqual("explicit", provenance["source"])
        self.assertFalse(provenance["invalid"])
        self.assertEqual(hashlib.sha256(original).hexdigest(), provenance["sha256"])

    def test_bundled_is_explicitly_recorded_without_guessing(self):
        """Check bundled is explicitly recorded without guessing."""
        self.assertEqual(self.source, self.record(explicit=False))
        self.assertEqual("bundled", policy.category_provenance(self.report, "SR")["source"])
        self.assertFalse((self.report / "config/test_category.json").exists())

    def test_legacy_category_filename_does_not_prove_it_was_used(self):
        """Check legacy category filename does not prove it was used."""
        (self.report / "test_category.json").write_text(self.source.read_text())
        provenance = policy.category_provenance(self.report, "SR")
        self.assertEqual("unknown", provenance["source"])
        self.assertFalse(provenance["invalid"])

    def test_tampered_hash_mode_missing_snapshot_and_bad_manifest_are_invalid(self):
        """Check tampered hash mode missing snapshot and bad manifest are invalid."""
        effective = self.record()
        self.assertTrue(policy.category_provenance(self.report, "DT")["invalid"])
        effective.write_text('{"tampered":true}')
        self.assertIn("SHA-256 does not match",
                      policy.category_provenance(self.report, "SR")["message"])
        effective.unlink()
        self.assertTrue(policy.category_provenance(self.report, "SR")["invalid"])
        (self.report / policy.MANIFEST).write_text('{"mode":"SR","mode":"DT"}')
        self.assertTrue(policy.category_provenance(self.report, "SR")["invalid"])

    def test_escaping_manifest_and_snapshot_paths_are_not_read(self):
        """Check escaping manifest and snapshot paths are not read."""
        self.record()
        manifest_path = self.report / policy.MANIFEST
        manifest = json.loads(manifest_path.read_text())
        for path in ("../supplied.json", str(self.source)):
            manifest["test_category"]["path"] = path
            manifest_path.write_text(json.dumps(manifest))
            self.assertTrue(policy.category_provenance(self.report, "SR")["invalid"])
        snapshot = self.report / "config/external.json"
        snapshot.symlink_to(self.source)
        manifest["test_category"]["path"] = "config/external.json"
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn("escapes", policy.category_provenance(self.report, "SR")["message"])
        manifest_path.unlink()
        manifest_path.symlink_to(self.source)
        self.assertIn("escapes", policy.category_provenance(self.report, "SR")["message"])


if __name__ == "__main__":
    unittest.main()
