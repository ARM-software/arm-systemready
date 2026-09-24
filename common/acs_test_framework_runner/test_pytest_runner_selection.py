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
"""Tests for pytest runner selection and reporting behavior."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))


def load_harness_module(module_name: str, filename: str):
    """Load a harness module directly from a file in the harness directory."""
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pytest_runner = load_harness_module("yaml_harness_pytest_runner", "pytest_runner.py")
report = load_harness_module("yaml_harness_report", "report.py")
runner_reporting = load_harness_module(
    "yaml_harness_runner_reporting",
    "runner_reporting.py",
)


def test_harness_sources_changed_ignores_pycache() -> None:
    """Verify that __pycache__ files do not count as harness source changes."""
    changed_paths = {
        pytest_runner.HARNESS_DIR / "__pycache__" / "pytest_runner.cpython-313.pyc",
    }

    assert pytest_runner.harness_sources_changed(changed_paths) is False


def test_select_yaml_runs_runs_all_groups_when_harness_changes(monkeypatch) -> None:
    """Verify that harness changes select all YAML groups and their targets."""
    yaml_files = [
        pytest_runner.PROJECT_ROOT / "common" / "acs_test_framework_manifests" / "group_one.yaml",
        pytest_runner.PROJECT_ROOT / "common" / "acs_test_framework_manifests" / "group_two.yaml",
    ]
    changed_paths = {pytest_runner.HARNESS_DIR / "mock_loader.py"}

    monkeypatch.setattr(
        pytest_runner,
        "get_recently_changed_paths",
        lambda: changed_paths,
    )
    monkeypatch.setattr(
        pytest_runner,
        "yaml_targets_changed_files",
        lambda yaml_file, _changed: ({f"{yaml_file.stem}.py"}, None),
    )
    monkeypatch.setattr(
        pytest_runner,
        "get_yaml_target_entries",
        lambda yaml_file: ({f"{yaml_file.stem}.py", f"{yaml_file.stem}_extra.py"}, None),
    )

    selected_runs, warnings = pytest_runner.select_yaml_runs(yaml_files)

    assert warnings == []
    assert selected_runs == [
        (yaml_files[0], {"group_one.py", "group_one_extra.py"}),
        (yaml_files[1], {"group_two.py", "group_two_extra.py"}),
    ]


def test_select_yaml_runs_preserves_target_only_selection(monkeypatch) -> None:
    """Verify that direct target changes preserve target-only selection."""
    yaml_files = [pytest_runner.PROJECT_ROOT / "common" / "acs_test_framework_manifests" / "group_one.yaml"]

    monkeypatch.setattr(
        pytest_runner,
        "get_recently_changed_paths",
        lambda: {pytest_runner.PROJECT_ROOT / "common" / "linux_scripts" / "target.py"},
    )
    monkeypatch.setattr(
        pytest_runner,
        "yaml_targets_changed_files",
        lambda _yaml_file, _changed: ({"target.py"}, None),
    )
    get_yaml_target_entries_called = False

    def fake_get_yaml_target_entries(_yaml_file: Path) -> tuple[set[str], None]:
        nonlocal get_yaml_target_entries_called
        get_yaml_target_entries_called = True
        return {"target.py", "unrelated.py"}, None

    monkeypatch.setattr(
        pytest_runner,
        "get_yaml_target_entries",
        fake_get_yaml_target_entries,
    )

    selected_runs, warnings = pytest_runner.select_yaml_runs(yaml_files)

    assert warnings == []
    assert get_yaml_target_entries_called is False
    assert selected_runs == [(yaml_files[0], {"target.py"})]


def test_report_changed_yaml_adds_python_targets_for_static_checks(monkeypatch) -> None:
    """Verify that changed YAML files contribute Python targets to static checks."""
    yaml_path = report.PROJECT_ROOT / "common" / "acs_test_framework_manifests" / "group_one.yaml"
    yaml_target = report.PROJECT_ROOT / "common" / "linux_scripts" / "target.py"
    direct_python_change = report.PROJECT_ROOT / "common" / "linux_scripts" / "direct.py"

    monkeypatch.setattr(
        report,
        "get_recently_changed_paths",
        lambda: [yaml_path, direct_python_change],
    )
    monkeypatch.setattr(
        report,
        "is_yaml_suite_file",
        lambda changed_path: changed_path == yaml_path,
    )
    monkeypatch.setattr(
        report,
        "get_python_targets_from_yaml_file",
        lambda changed_yaml: {yaml_target} if changed_yaml == yaml_path else set(),
    )

    assert report.get_recently_changed_python_files() == [
        direct_python_change,
        yaml_target,
    ]


def test_report_yaml_target_filter_keeps_only_existing_python_files(monkeypatch) -> None:
    """Verify that YAML target discovery keeps only existing Python files."""
    yaml_path = report.PROJECT_ROOT / "common" / "acs_test_framework_manifests" / "group_one.yaml"
    py_target = report.PROJECT_ROOT / "common" / "linux_scripts" / "target.py"
    sh_target = report.PROJECT_ROOT / "common" / "linux_scripts" / "target.sh"

    monkeypatch.setattr(report, "load_yaml_config", lambda _yaml_file: {"suites": []})
    monkeypatch.setattr(
        report,
        "normalize_suites",
        lambda _config: [{"files": ["common/linux_scripts/target.py", "common/linux_scripts/target.sh"]}],
    )

    def fake_exists(self) -> bool:
        return self in {yaml_path, py_target, sh_target}

    def fake_is_file(self) -> bool:
        return self in {yaml_path, py_target, sh_target}

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "is_file", fake_is_file)

    assert report.get_python_targets_from_yaml_file(yaml_path) == {py_target}


def test_collect_pytest_case_logs_reads_persisted_case_description(
    monkeypatch,
) -> None:
    """Verify that persisted case descriptions are read into collected logs."""
    temp_path = HARNESS_DIR / "_case_log_test_reports"
    shutil.rmtree(temp_path, ignore_errors=True)
    try:
        runner_reporting.append_combined_case_log(
            file_work_dir=temp_path / "_work" / "suite" / "target",
            testcase_name="suite::target.py::case_with_description",
            status="PASS",
            message="case passed",
            details="",
            description="First line of description\nSecond line of description",
        )
        monkeypatch.setattr(report, "REPORTS_DIR", temp_path)

        assert report.collect_pytest_case_logs() == [
            {
                "name": "suite::target.py::case_with_description",
                "description": "First line of description Second line of description",
                "status": "passed",
                "details": "case passed",
            }
        ]
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


def test_collect_pytest_case_logs_skips_missing_case_description(
    monkeypatch,
) -> None:
    """Verify that missing case descriptions are represented as empty text."""
    temp_path = HARNESS_DIR / "_case_log_test_reports"
    shutil.rmtree(temp_path, ignore_errors=True)
    try:
        runner_reporting.append_combined_case_log(
            file_work_dir=temp_path / "_work" / "suite" / "target",
            testcase_name="suite::target.py::case_without_description",
            status="PASS",
            message="case passed",
            details="",
        )
        monkeypatch.setattr(report, "REPORTS_DIR", temp_path)

        assert report.collect_pytest_case_logs() == [
            {
                "name": "suite::target.py::case_without_description",
                "description": "",
                "status": "passed",
                "details": "case passed",
            }
        ]
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)