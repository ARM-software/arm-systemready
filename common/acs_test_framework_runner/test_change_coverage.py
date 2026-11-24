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
import json
import sys


HARNESS_DIR = __import__("pathlib").Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))


def load_harness_module(module_name: str, filename: str):
    """Load a harness module directly from the local test directory."""
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


change_coverage = load_harness_module("yaml_harness_change_coverage", "change_coverage.py")
dashboard = load_harness_module("yaml_harness_dashboard_for_coverage", "dashboard.py")
pytest_runner = load_harness_module("yaml_harness_pytest_runner_for_coverage", "pytest_runner.py")


def test_build_change_coverage_plan_collects_changed_function(monkeypatch, tmp_path) -> None:
    target = tmp_path / "target_module.py"
    target.write_text(
        "def touched():\n"
        "    value = 1\n"
        "    return value + 1\n\n"
        "def untouched():\n"
        "    return 0\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        change_coverage,
        "get_git_changed_line_ranges",
        lambda _root: {target.resolve(): [(2, 3)]},
    )

    plan = change_coverage.build_change_coverage_plan(tmp_path)

    assert list(plan) == [target.resolve()]
    entry = plan[target.resolve()]
    assert entry["changed_lines"] == [2, 3]
    assert entry["functions"] == [
        {"name": "touched", "start": 1, "end": 3, "changed_lines": [2, 3]}
    ]


def test_build_function_coverage_plan_collects_requested_function(tmp_path) -> None:
    target = tmp_path / "target_module.py"
    target.write_text(
        "def parse_memmap():\n"
        "    value = 1\n"
        "    return value + 1\n\n"
        "def untouched():\n"
        "    return 0\n",
        encoding="utf-8",
    )

    plan = change_coverage.build_function_coverage_plan(
        [target],
        ["parse_memmap"],
    )

    assert list(plan) == [target.resolve()]
    entry = plan[target.resolve()]
    assert entry["mode"] == "function-reachability"
    assert entry["changed_lines"] == [1, 2, 3]
    assert entry["functions"] == [
        {
            "name": "parse_memmap",
            "start": 1,
            "end": 3,
            "changed_lines": [1, 2, 3],
            "mode": "function-reachability",
        }
    ]


def test_run_case_writes_change_coverage_artifact(tmp_path) -> None:
    target = tmp_path / "covered_module.py"
    target.write_text(
        "def parse_memmap():\n"
        "    value = 41\n"
        "    return value + 1\n",
        encoding="utf-8",
    )
    plan = {
        target.resolve(): {
            "target_path": str(target.resolve()),
            "target_display": target.name,
            "changed_ranges": [[2, 3]],
            "changed_lines": [2, 3],
            "functions": [
                {
                    "name": "parse_memmap",
                    "start": 1,
                    "end": 3,
                    "changed_lines": [2, 3],
                }
            ],
        }
    }

    outcome = pytest_runner.run_case(
        suite_name="coverage_suite",
        file_entry=str(target),
        case_index=1,
        case_def={
            "name": "executes_function",
            "type": "py_function",
            "function": "parse_memmap",
        },
        options=pytest_runner.RunCaseOptions(
            reports_dir=tmp_path,
            change_coverage_plan=plan,
        ),
    )

    assert outcome.passed is True
    work_dir = (
        pytest_runner.get_file_work_dir(
            "coverage_suite",
            str(target),
            reports_dir=tmp_path,
        )
        / pytest_runner.sanitize_name("1_executes_function")
    )
    artifact = work_dir / change_coverage.CHANGE_COVERAGE_FILENAME
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_status"] == "covered"
    assert payload["summary"]["covered_function_count"] == 1
    assert payload["missed_changed_lines"] == []


def test_run_case_writes_function_reachability_artifact(tmp_path) -> None:
    target = tmp_path / "covered_module.py"
    target.write_text(
        "def parse_memmap():\n"
        "    value = 41\n"
        "    return value + 1\n",
        encoding="utf-8",
    )
    plan = {
        target.resolve(): {
            "target_path": str(target.resolve()),
            "target_display": target.name,
            "changed_ranges": [[1, 3]],
            "changed_lines": [1, 2, 3],
            "mode": "function-reachability",
            "functions": [
                {
                    "name": "parse_memmap",
                    "start": 1,
                    "end": 3,
                    "changed_lines": [1, 2, 3],
                    "mode": "function-reachability",
                }
            ],
        }
    }

    outcome = pytest_runner.run_case(
        suite_name="coverage_suite",
        file_entry=str(target),
        case_index=1,
        case_def={
            "name": "executes_function",
            "type": "py_function",
            "function": "parse_memmap",
        },
        options=pytest_runner.RunCaseOptions(
            reports_dir=tmp_path,
            change_coverage_plan=plan,
        ),
    )

    assert outcome.passed is True
    work_dir = (
        pytest_runner.get_file_work_dir(
            "coverage_suite",
            str(target),
            reports_dir=tmp_path,
        )
        / pytest_runner.sanitize_name("1_executes_function")
    )
    artifact = work_dir / change_coverage.CHANGE_COVERAGE_FILENAME
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["mode"] == "function-reachability"
    assert payload["summary"]["overall_status"] == "covered"
    assert payload["summary"]["covered_function_count"] == 1
    assert payload["summary"]["untouched_function_count"] == 0


def test_build_change_coverage_summary_aggregates_case_statuses() -> None:
    summary = dashboard.build_change_coverage_summary(
        [
            {
                "name": "suite::target.py::covered_case",
                "target": "target.py",
                "manifest": "first.yaml",
                "change_coverage": {
                    "target_display": "target.py",
                    "changed_lines": [10, 11],
                    "covered_changed_lines": [10, 11],
                    "functions": [
                        {
                            "name": "parse_memmap",
                            "start": 9,
                            "end": 14,
                            "status": "covered",
                        }
                    ],
                },
            },
            {
                "name": "suite::target.py::untouched_case",
                "target": "target.py",
                "manifest": "second.yaml",
                "change_coverage": {
                    "target_display": "target.py",
                    "changed_lines": [10, 11],
                    "covered_changed_lines": [],
                    "functions": [
                        {
                            "name": "parse_memmap",
                            "start": 9,
                            "end": 14,
                            "status": "untouched",
                        },
                        {"name": "helper", "start": 20, "end": 24, "status": "untouched"},
                    ],
                },
            },
        ]
    )

    assert summary is not None
    assert summary["summary"] == {
        "changed_files": 1,
        "changed_functions": 2,
        "covered_functions": 1,
        "partial_functions": 0,
        "untouched_functions": 1,
    }
    target = summary["targets"][0]
    assert target["target_display"] == "target.py"
    assert target["covered_changed_line_count"] == 2
    assert [item["status"] for item in target["functions"]] == ["covered", "untouched"]
