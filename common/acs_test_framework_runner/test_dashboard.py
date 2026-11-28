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

from __future__ import annotations

import importlib.util
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))


def load_harness_module(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dashboard = load_harness_module("yaml_harness_dashboard", "dashboard.py")


def write_xml_report(xml_path: Path) -> None:
    testsuite = ET.Element("testsuite")
    testsuite.set("name", "sample_suite")
    testsuite.set("tests", "3")
    testsuite.set("failures", "1")
    testsuite.set("errors", "0")
    testsuite.set("skipped", "1")

    properties = ET.SubElement(testsuite, "properties")
    ET.SubElement(
        properties,
        "property",
        name="yaml_file",
        value="common/acs_test_framework_manifests/sample.yaml",
    )

    passed_case = ET.SubElement(
        testsuite,
        "testcase",
        name="suite::sample.py::passes",
        file="common/sample.py",
    )
    ET.SubElement(passed_case, "system-out").text = "ok"

    failed_case = ET.SubElement(
        testsuite,
        "testcase",
        name="suite::sample.py::fails",
        file="common/sample.py",
    )
    failure = ET.SubElement(failed_case, "failure")
    failure.set("message", "expected failure")
    failure.text = "assertion details"

    warning_case = ET.SubElement(
        testsuite,
        "testcase",
        name="suite::other.py::warns",
        file="common/other.py",
    )
    skipped = ET.SubElement(warning_case, "skipped")
    skipped.set("message", "warning surfaced as skipped")
    skipped.text = "warning details"

    ET.ElementTree(testsuite).write(xml_path, encoding="utf-8", xml_declaration=True)


def write_case_logs(reports_dir: Path) -> None:
    passes_dir = reports_dir / "_work" / "sample_suite" / "sample" / "1_passes"
    fails_dir = reports_dir / "_work" / "sample_suite" / "sample" / "2_fails"
    passes_dir.mkdir(parents=True, exist_ok=True)
    fails_dir.mkdir(parents=True, exist_ok=True)
    (passes_dir.parent / "combined.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::passes\n"
        + "STATUS: PASS\n"
        + "MESSAGE: ok\n\n"
        + "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::fails\n"
        + "STATUS: FAIL\n"
        + "MESSAGE: expected failure\n",
        encoding="utf-8",
    )
    (passes_dir / "case.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::passes\n"
        + "STATUS: PASS\n"
        + "MESSAGE: ok\n",
        encoding="utf-8",
    )
    (fails_dir / "case.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::fails\n"
        + "STATUS: FAIL\n"
        + "MESSAGE: expected failure\n"
        + "DETAILS: assertion details\n",
        encoding="utf-8",
    )


def write_previous_xml_report(xml_path: Path) -> None:
    testsuite = ET.Element("testsuite")
    testsuite.set("name", "sample_suite_previous")
    testsuite.set("tests", "3")
    testsuite.set("failures", "2")
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    properties = ET.SubElement(testsuite, "properties")
    ET.SubElement(
        properties,
        "property",
        name="yaml_file",
        value="common/acs_test_framework_manifests/sample.yaml",
    )

    previous_fail_then_fixed = ET.SubElement(
        testsuite,
        "testcase",
        name="suite::sample.py::passes",
        file="common/sample.py",
    )
    previous_failure = ET.SubElement(previous_fail_then_fixed, "failure")
    previous_failure.set("message", "previous failure")
    previous_failure.text = "was failing before"

    previous_pass_then_regressed = ET.SubElement(
        testsuite,
        "testcase",
        name="suite::sample.py::fails",
        file="common/sample.py",
    )
    ET.SubElement(previous_pass_then_regressed, "system-out").text = "was passing before"

    removed_case = ET.SubElement(
        testsuite,
        "testcase",
        name="suite::sample.py::removed",
        file="common/sample.py",
    )
    removed_failure = ET.SubElement(removed_case, "failure")
    removed_failure.set("message", "removed from current run")
    removed_failure.text = "removed case"

    ET.ElementTree(testsuite).write(xml_path, encoding="utf-8", xml_declaration=True)


def write_previous_case_logs(reports_dir: Path) -> None:
    passes_dir = reports_dir / "_work" / "sample_suite_previous" / "sample" / "1_passes"
    fails_dir = reports_dir / "_work" / "sample_suite_previous" / "sample" / "2_fails"
    removed_dir = reports_dir / "_work" / "sample_suite_previous" / "sample" / "3_removed"
    passes_dir.mkdir(parents=True, exist_ok=True)
    fails_dir.mkdir(parents=True, exist_ok=True)
    removed_dir.mkdir(parents=True, exist_ok=True)
    (passes_dir.parent / "combined.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::passes\n"
        + "STATUS: FAIL\n"
        + "MESSAGE: previous failure\n\n"
        + "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::fails\n"
        + "STATUS: PASS\n"
        + "MESSAGE: was passing before\n\n"
        + "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::removed\n"
        + "STATUS: FAIL\n"
        + "MESSAGE: removed from current run\n",
        encoding="utf-8",
    )
    (passes_dir / "case.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::passes\n"
        + "STATUS: FAIL\n"
        + "MESSAGE: previous failure\n"
        + "DETAILS: was failing before\n",
        encoding="utf-8",
    )
    (fails_dir / "case.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::fails\n"
        + "STATUS: PASS\n"
        + "MESSAGE: was passing before\n",
        encoding="utf-8",
    )
    (removed_dir / "case.log").write_text(
        "=" * 80 + "\n"
        + "TEST CASE: suite::sample.py::removed\n"
        + "STATUS: FAIL\n"
        + "MESSAGE: removed from current run\n"
        + "DETAILS: removed case\n",
        encoding="utf-8",
    )


def test_build_dashboard_data_handles_empty_reports_dir() -> None:
    reports_dir = HARNESS_DIR / "_dashboard_empty_reports"
    shutil.rmtree(reports_dir, ignore_errors=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = dashboard.build_dashboard_data(
            reports_dir=reports_dir,
            generated_at="2026-11-11 18:00:00",
            case_logs=[],
            testgap_hints=[],
        )

        assert data["summary"] == {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "warnings": 0,
        }
        assert data["targets"] == []
        assert data["manifests"] == []

        html = dashboard.render_dashboard_html(data)
        assert "YAML Runner Dashboard" in html
        assert "No YAML runner case results were found" in html
        assert 'data-acs-report-kind="acs-summary"' in html
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)


def test_build_dashboard_data_parses_xml_and_renders_testgap() -> None:
    reports_dir = HARNESS_DIR / "_dashboard_xml_reports"
    shutil.rmtree(reports_dir, ignore_errors=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    try:
        xml_path = reports_dir / "sample.xml"
        write_xml_report(xml_path)
        write_case_logs(reports_dir)

        case_logs = [
            {
                "name": "suite::sample.py::passes",
                "description": "Passing sample case",
                "status": "passed",
                "details": "ok",
            },
            {
                "name": "suite::sample.py::fails",
                "description": "Failing sample case",
                "status": "failed",
                "details": "assertion details",
            },
        ]
        testgap_hints = [
            (
                "common/sample.py",
                [
                    ("helper_name@44", "exact", ["sample.yaml::suite::fails"]),
                    ("validate_input@18", "review", []),
                ],
            )
        ]

        data = dashboard.build_dashboard_data(
            reports_dir=reports_dir,
            generated_at="2026-11-11 18:05:00",
            case_logs=case_logs,
            testgap_hints=testgap_hints,
        )

        assert data["summary"] == {
            "total": 3,
            "passed": 1,
            "failed": 1,
            "errors": 0,
            "warnings": 1,
        }
        assert [target["target"] for target in data["targets"]] == [
            "common/other.py",
            "common/sample.py",
        ]
        assert data["manifests"] == [
            "common/acs_test_framework_manifests/sample.yaml"
        ]

        html = dashboard.render_dashboard_html(data)
        assert "Passing sample case" in html
        assert "Failing sample case" in html
        assert "common/sample.py" in html
        assert "helper_name@44" in html
        assert "Review" in html
        assert "sample.yaml::suite::fails" in html
        assert "case.log" in html
        assert html.count('>combined.log<') == 1
        assert "View details" in html
        assert "Choose target" in html
        assert "All targets" in html
        assert "Showing all 2 targets" in html
        assert 'data-dashboard-target-select' in html
        assert 'data-dashboard-target-card' in html
        assert 'data-target="common/sample.py"' in html
        assert 'data-target-status-filter' in html
        assert 'data-case-status="passed"' in html
        assert 'data-case-status="failed"' in html
        assert 'No cases match the selected status filter.' in html
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)


def test_build_dashboard_data_renders_run_comparison() -> None:
    reports_dir = HARNESS_DIR / "_dashboard_compare_reports"
    previous_reports_dir = HARNESS_DIR / "_dashboard_previous_reports"
    shutil.rmtree(reports_dir, ignore_errors=True)
    shutil.rmtree(previous_reports_dir, ignore_errors=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    previous_reports_dir.mkdir(parents=True, exist_ok=True)
    try:
        write_xml_report(reports_dir / "sample.xml")
        write_case_logs(reports_dir)
        write_previous_xml_report(previous_reports_dir / "sample_previous.xml")
        write_previous_case_logs(previous_reports_dir)

        data = dashboard.build_dashboard_data(
            reports_dir=reports_dir,
            generated_at="2026-11-11 18:09:00",
            case_logs=[],
            testgap_hints=[],
            previous_reports_dir=previous_reports_dir,
        )

        comparison = data["comparison"]
        assert comparison is not None
        assert comparison["available"] is True
        assert comparison["summary"]["current_total"] == 3
        assert comparison["summary"]["previous_total"] == 3
        assert comparison["summary"]["regressed"] == 1
        assert comparison["summary"]["fixed"] == 1
        assert comparison["summary"]["new"] == 1
        assert comparison["summary"]["removed"] == 1
        assert comparison["targets"][0]["target"] == "common/sample.py"

        html = dashboard.render_dashboard_html(data)
        assert "Run Comparison" in html
        assert "Per-Target Diff" in html
        assert "Regressed Cases" in html
        assert "Fixed Cases" in html
        assert "New Cases" in html
        assert "Removed Cases" in html
        assert "suite::sample.py::fails" in html
        assert "suite::sample.py::passes" in html
        assert "suite::sample.py::removed" in html
        assert "suite::other.py::warns" in html
        assert "sample_previous.xml" in html
        assert "Incident Summary" in html
        assert "Root-Cause Clusters" in html
        assert "Needs Attention" in html
        assert "1 regression introduced" in html
        assert "0 targets recovered" in html
        assert "1 new case added" in html
        assert "Likely dominant issue" in html
        assert "Assertion / expectation mismatch" in html
        assert "Current artifacts" in html
        assert "Previous baseline artifacts" in html
        assert "Previous result" in html
        assert "Current result" in html
        assert 'comparison-jump-link' in html
        assert 'id="case-common-sample-py-common-acs-test-framework-manifests-sample-yaml-suite-sample-py-fails"' in html
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)
        shutil.rmtree(previous_reports_dir, ignore_errors=True)


def test_write_dashboard_creates_html_file() -> None:
    reports_dir = HARNESS_DIR / "_dashboard_write_reports"
    shutil.rmtree(reports_dir, ignore_errors=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / "dashboard.html"
    try:
        write_xml_report(reports_dir / "sample.xml")
        write_case_logs(reports_dir)

        written = dashboard.write_dashboard(
            output_path=output_path,
            options=dashboard.DashboardWriteOptions(
                reports_dir=reports_dir,
                generated_at="2026-11-11 18:10:00",
                case_logs=[],
                testgap_hints=[],
            ),
        )

        assert written == output_path
        contents = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in contents
        assert "ACS YAML Runner Dashboard" in contents
        assert "sample.xml" in contents
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)
