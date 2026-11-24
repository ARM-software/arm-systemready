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

import json
from pathlib import Path
from typing import Any

try:  # Optional dependency at runtime.
    import coverage
except ImportError:  # pragma: no cover
    coverage = None

try:  # Support package imports and direct harness module loading.
    from .runner_checks import (
        collect_python_symbol_ranges,
        detect_project_root,
        get_git_changed_line_ranges,
    )
except ImportError:  # pragma: no cover
    from runner_checks import (
        collect_python_symbol_ranges,
        detect_project_root,
        get_git_changed_line_ranges,
    )


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
CHANGE_COVERAGE_FILENAME = "change_coverage.json"

TRACEABLE_CASE_TYPES = {
    "py_function",
    "module_cli",
    "module_main_with_env",
}

_STATUS_RANK = {
    "not_applicable": -1,
    "untouched": 0,
    "partial": 1,
    "covered": 2,
}


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def coverage_supported() -> bool:
    return coverage is not None


def expand_line_ranges(ranges: list[tuple[int, int]]) -> list[int]:
    lines: set[int] = set()
    for start, end in ranges:
        lines.update(range(start, end + 1))
    return sorted(lines)


def _plan_entry_from_symbols(
    resolved: Path,
    symbols: list[dict[str, Any]],
    *,
    mode: str = "changed-lines",
) -> dict[str, Any]:
    changed_ranges = [
        [int(symbol["start"]), int(symbol["end"])]
        for symbol in symbols
    ]

    changed_lines = sorted(
        {
            line
            for symbol in symbols
            for line in symbol.get("changed_lines", [])
        }
    )

    return {
        "target_path": str(resolved),
        "target_display": display_path(resolved),
        "changed_ranges": changed_ranges,
        "changed_lines": changed_lines,
        "functions": [
            {
                "name": str(symbol["name"]),
                "start": int(symbol["start"]),
                "end": int(symbol["end"]),
                "changed_lines": [
                    int(line)
                    for line in symbol.get("changed_lines", [])
                ],
                "mode": mode,
            }
            for symbol in symbols
        ],
        "mode": mode,
    }


def build_change_coverage_plan(
    project_root: Path = PROJECT_ROOT,
) -> dict[Path, dict[str, Any]]:
    plan: dict[Path, dict[str, Any]] = {}

    for file_path, ranges in get_git_changed_line_ranges(
        project_root
    ).items():
        resolved = Path(file_path).resolve()

        if resolved.suffix.lower() != ".py" or not resolved.exists():
            continue

        changed_lines = expand_line_ranges(ranges)

        if not changed_lines:
            continue

        functions: list[dict[str, Any]] = []

        for symbol in collect_python_symbol_ranges(resolved):
            function_changed_lines = [
                line
                for line in changed_lines
                if symbol["start"] <= line <= symbol["end"]
            ]

            if not function_changed_lines:
                continue

            functions.append(
                {
                    "name": str(symbol["name"]),
                    "start": int(symbol["start"]),
                    "end": int(symbol["end"]),
                    "changed_lines": function_changed_lines,
                }
            )

        plan[resolved] = _plan_entry_from_symbols(
            resolved,
            functions,
        )

        # Preserve all Git-changed lines, including changes
        # outside function definitions.
        plan[resolved]["changed_lines"] = changed_lines
        plan[resolved]["changed_ranges"] = [
            [int(start), int(end)]
            for start, end in ranges
        ]

    return plan


def build_function_coverage_plan(
    target_paths: list[Path] | set[Path] | tuple[Path, ...],
    function_names: list[str] | set[str] | tuple[str, ...],
) -> dict[Path, dict[str, Any]]:
    requested = {
        name.strip()
        for name in function_names
        if name and name.strip()
    }

    if not requested:
        return {}

    plan: dict[Path, dict[str, Any]] = {}

    for target_path in target_paths:
        resolved = Path(target_path).resolve()

        if resolved.suffix.lower() != ".py" or not resolved.exists():
            continue

        matched_symbols: list[dict[str, Any]] = []

        for symbol in collect_python_symbol_ranges(resolved):
            if str(symbol["name"]) not in requested:
                continue

            matched_symbols.append(
                {
                    "name": str(symbol["name"]),
                    "start": int(symbol["start"]),
                    "end": int(symbol["end"]),
                    "changed_lines": list(
                        range(
                            int(symbol["start"]),
                            int(symbol["end"]) + 1,
                        )
                    ),
                }
            )

        if matched_symbols:
            plan[resolved] = _plan_entry_from_symbols(
                resolved,
                matched_symbols,
                mode="function-reachability",
            )

    return plan


def should_trace_case(
    file_path: Path,
    case_type: str,
    plan: dict[Path, dict[str, Any]] | None,
) -> bool:
    if not plan or case_type not in TRACEABLE_CASE_TYPES:
        return False

    return file_path.resolve() in plan


def begin_change_coverage(file_path: Path) -> Any:
    if coverage is None:
        raise RuntimeError(
            "coverage.py is required for --change-coverage "
            "but is not installed"
        )

    cov = coverage.Coverage(
        data_file=None,
        include=[str(file_path.resolve())],
        branch=False,
    )

    cov.start()

    return cov


def _measured_lines(cov: Any, file_path: Path) -> list[int]:
    data = cov.get_data()
    resolved = file_path.resolve()

    for measured_file in data.measured_files():
        try:
            if Path(measured_file).resolve() != resolved:
                continue
        except OSError:
            continue

        return sorted(set(data.lines(measured_file) or []))

    return []


def _analyze_source_lines(
    cov: Any,
    file_path: Path,
) -> tuple[set[int], set[int], set[int]]:
    """Return executable, excluded, and covered statement lines.

    Use coverage.py's public analysis API rather than treating
    every physical source line as an executable statement.
    """
    _, statements, excluded, missing, _ = cov.analysis2(
        str(file_path.resolve())
    )

    executable_lines = set(statements)
    excluded_lines = set(excluded)

    covered_statement_lines = (
        executable_lines - set(missing)
    )

    return (
        executable_lines,
        excluded_lines,
        covered_statement_lines,
    )


def _classify_changed_lines(
    changed_lines: list[int],
    executable_lines: set[int],
    excluded_lines: set[int],
) -> tuple[list[int], list[int], list[int]]:
    """Classify changed source lines for coverage reporting."""
    changed_line_set = set(changed_lines)

    executable_changed_lines = sorted(
        changed_line_set & executable_lines
    )

    excluded_changed_lines = sorted(
        changed_line_set & excluded_lines
    )

    non_executable_changed_lines = sorted(
        changed_line_set
        - executable_lines
        - excluded_lines
    )

    return (
        executable_changed_lines,
        non_executable_changed_lines,
        excluded_changed_lines,
    )


def _coverage_status(
    changed_lines: list[int],
    executed_lines: set[int],
) -> tuple[str, list[int]]:
    """Calculate coverage status for executable changed lines."""
    changed_line_set = set(changed_lines)

    if not changed_line_set:
        return "not_applicable", []

    covered_lines = sorted(
        changed_line_set & executed_lines
    )

    if not covered_lines:
        return "untouched", covered_lines

    if len(covered_lines) == len(changed_line_set):
        return "covered", covered_lines

    return "partial", covered_lines


def finalize_change_coverage(
    cov: Any,
    file_path: Path,
    plan_entry: dict[str, Any],
    testcase_name: str,
) -> dict[str, Any]:
    cov.stop()

    mode = str(
        plan_entry.get("mode") or "changed-lines"
    )

    # Preserve the raw execution trace for diagnostics.
    executed_lines = _measured_lines(cov, file_path)
    executed_line_set = set(executed_lines)

    # Obtain executable, excluded and covered statement lines
    # using coverage.py source analysis.
    (
        executable_lines,
        excluded_lines,
        covered_statement_lines,
    ) = _analyze_source_lines(cov, file_path)

    # Preserve all original Git-changed source lines.
    changed_lines = sorted(
        {
            int(line)
            for line in plan_entry.get("changed_lines", [])
        }
    )

    (
        executable_changed_lines,
        non_executable_changed_lines,
        excluded_changed_lines,
    ) = _classify_changed_lines(
        changed_lines,
        executable_lines,
        excluded_lines,
    )

    # Only executable statements contribute to the
    # changed-line coverage status.
    overall_status, covered_changed_lines = _coverage_status(
        executable_changed_lines,
        covered_statement_lines,
    )

    missed_changed_lines = sorted(
        set(executable_changed_lines)
        - covered_statement_lines
    )

    function_summaries: list[dict[str, Any]] = []

    covered_functions = 0
    partial_functions = 0
    untouched_functions = 0
    not_applicable_functions = 0

    for function in plan_entry.get("functions", []):
        function_changed_lines = sorted(
            {
                int(line)
                for line in function.get("changed_lines", [])
            }
        )

        function_mode = str(
            function.get("mode") or mode
        )

        (
            function_executable_lines,
            function_non_executable_lines,
            function_excluded_lines,
        ) = _classify_changed_lines(
            function_changed_lines,
            executable_lines,
            excluded_lines,
        )

        if function_mode == "function-reachability":
            # Preserve the existing function-reachability
            # behavior independently of changed-line coverage.
            covered_lines = sorted(
                set(function_changed_lines)
                & executed_line_set
            )

            status = (
                "covered" if covered_lines else "untouched"
            )
        else:
            status, covered_lines = _coverage_status(
                function_executable_lines,
                covered_statement_lines,
            )

        function_missed_lines = sorted(
            set(function_executable_lines)
            - covered_statement_lines
        )

        if status == "covered":
            covered_functions += 1
        elif status == "partial":
            partial_functions += 1
        elif status == "not_applicable":
            not_applicable_functions += 1
        else:
            untouched_functions += 1

        function_summaries.append(
            {
                "name": str(
                    function.get("name") or "<unknown>"
                ),
                "start": int(
                    function.get("start") or 0
                ),
                "end": int(
                    function.get("end") or 0
                ),
                "changed_lines": function_changed_lines,
                "executable_changed_lines": (
                    function_executable_lines
                ),
                "non_executable_changed_lines": (
                    function_non_executable_lines
                ),
                "excluded_changed_lines": (
                    function_excluded_lines
                ),
                "covered_changed_lines": covered_lines,
                "missed_changed_lines": (
                    function_missed_lines
                ),
                "status": status,
            }
        )

    if mode == "function-reachability":
        if covered_functions and untouched_functions:
            overall_status = "partial"
        elif covered_functions:
            overall_status = "covered"
        else:
            overall_status = "untouched"

    return {
        "schema_version": 1,
        "mode": mode,
        "testcase_name": testcase_name,
        "target_path": plan_entry.get(
            "target_path",
            str(file_path.resolve()),
        ),
        "target_display": plan_entry.get(
            "target_display",
            display_path(file_path),
        ),
        "changed_ranges": plan_entry.get(
            "changed_ranges",
            [],
        ),
        "changed_lines": changed_lines,
        "executable_changed_lines": (
            executable_changed_lines
        ),
        "non_executable_changed_lines": (
            non_executable_changed_lines
        ),
        "excluded_changed_lines": (
            excluded_changed_lines
        ),
        "executed_lines": executed_lines,
        "covered_changed_lines": covered_changed_lines,
        "missed_changed_lines": missed_changed_lines,
        "functions": function_summaries,
        "summary": {
            "overall_status": overall_status,
            "changed_line_count": len(
                changed_lines
            ),
            "executable_changed_line_count": len(
                executable_changed_lines
            ),
            "non_executable_changed_line_count": len(
                non_executable_changed_lines
            ),
            "excluded_changed_line_count": len(
                excluded_changed_lines
            ),
            "covered_changed_line_count": len(
                covered_changed_lines
            ),
            "missed_changed_line_count": len(
                missed_changed_lines
            ),
            "changed_function_count": len(
                function_summaries
            ),
            "covered_function_count": covered_functions,
            "partial_function_count": partial_functions,
            "untouched_function_count": untouched_functions,
            "not_applicable_function_count": (
                not_applicable_functions
            ),
        },
    }


def write_change_coverage_artifact(
    work_dir: Path,
    payload: dict[str, Any],
) -> Path:
    output_path = work_dir / CHANGE_COVERAGE_FILENAME

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return output_path


def load_change_coverage_artifact(
    artifact_path: Path,
) -> dict[str, Any] | None:
    try:
        raw = json.loads(
            artifact_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError, TypeError):
        return None

    if not isinstance(raw, dict):
        return None

    return raw


def stronger_status(current: str, candidate: str) -> str:
    if _STATUS_RANK.get(candidate, 0) > _STATUS_RANK.get(
        current, 0
    ):
        return candidate

    return current
