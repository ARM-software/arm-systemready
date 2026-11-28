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

import argparse
import shutil
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_BOOTSTRAP = SCRIPT_DIR.parent.parent
for bootstrap_path in (PROJECT_ROOT_BOOTSTRAP, SCRIPT_DIR):
    bootstrap_text = str(bootstrap_path)
    if bootstrap_text not in sys.path:
        sys.path.insert(0, bootstrap_text)

try:  # Support package imports and direct harness module loading.
    from .change_coverage import (
        begin_change_coverage,
        build_change_coverage_plan,
        build_function_coverage_plan,
        coverage_supported,
        finalize_change_coverage,
        should_trace_case,
        write_change_coverage_artifact,
    )
    from .dashboard import (
        DashboardWriteOptions,
        LAST_RUN_REPORTS_DIR,
        write_dashboard,
    )
    from .case_data_builders import CaseBuildError
    from .runner_checks import (
        ConfigError,
        RunCaseOptions,
        SkipCase,
        TestMeta,
        TestOutcome,
        create_outcome,
        detect_project_root,
        format_outcome_message,
        load_yaml_config,
        json_value,
        normalize_suites,
        resolve_target_path,
        run_single_check,
        sanitize_name,
        target_work_name,
        changed_lines_to_functions,
        get_git_changed_line_ranges,
    )
    from .runner_reporting import (
        append_combined_case_log,
        append_run_header,
        build_config_error_outcome,
        build_report_path,
        cleanup_old_pytest_xml_reports,
        create_placeholder_xml,
        print_group_summary,
        remove_placeholder_xml,
        sanitize_xml_text,
        write_case_log,
        write_junit_xml,
    )
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from change_coverage import (
        begin_change_coverage,
        build_change_coverage_plan,
        build_function_coverage_plan,
        coverage_supported,
        finalize_change_coverage,
        should_trace_case,
        write_change_coverage_artifact,
    )
    from dashboard import (
        DashboardWriteOptions,
        LAST_RUN_REPORTS_DIR,
        write_dashboard,
    )
    from case_data_builders import CaseBuildError
    from runner_checks import (
        ConfigError,
        RunCaseOptions,
        SkipCase,
        TestMeta,
        TestOutcome,
        create_outcome,
        detect_project_root,
        format_outcome_message,
        load_yaml_config,
        json_value,
        normalize_suites,
        resolve_target_path,
        run_single_check,
        sanitize_name,
        target_work_name,
        changed_lines_to_functions,
        get_git_changed_line_ranges,
    )
    from runner_reporting import (
        append_combined_case_log,
        append_run_header,
        build_config_error_outcome,
        build_report_path,
        cleanup_old_pytest_xml_reports,
        create_placeholder_xml,
        print_group_summary,
        remove_placeholder_xml,
        sanitize_xml_text,
        write_case_log,
        write_junit_xml,
    )

PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
HARNESS_DIR = PROJECT_ROOT / "common" / "acs_test_framework_runner"
TEST_YAML_DIR = PROJECT_ROOT / "common" / "acs_test_framework_manifests"
REPORTS_DIR = PROJECT_ROOT / "common" / "reports"
LAST_RUN_SNAPSHOT_DIR = LAST_RUN_REPORTS_DIR

SUPPORTED_SUFFIXES = {".yaml", ".yml"}
IN_PROCESS_CASE_TYPES = {"py_function", "module_main_with_env", "module_cli"}
RESERVED_REPORT_FILENAMES = {
    "_runner_work",
    "_work",
    "pytest-placeholder.xml",
}


@dataclass(frozen=True)
class TestGroup:
    test_id: str
    yaml_file: Path
    suite_name: str
    targets: tuple[str, ...]
    case_count: int

    @property
    def outcome_count(self) -> int:
        return len(self.targets) * self.case_count


@dataclass(frozen=True)
class RunYamlOptions:
    jobs: int = 4
    require_tests: bool = False
    fail_on_warnings: bool = False
    fail_on_skips: bool = False
    selected_group_ids: frozenset[str] | None = None
    reports_dir: Path | None = None
    xml_report: Path | None = None
    change_coverage_plan: dict[Path, dict[str, Any]] | None = None


def discover_yaml_files() -> list[Path]:
    if not TEST_YAML_DIR.exists() or not TEST_YAML_DIR.is_dir():
        return []
    return sorted(
        path
        for path in TEST_YAML_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def get_group_name(yaml_file: Path) -> str:
    try:
        rel_path = yaml_file.relative_to(TEST_YAML_DIR)
    except ValueError:
        return yaml_file.stem
    return rel_path.parts[0] if len(rel_path.parts) > 1 else yaml_file.stem


def get_manifest_id(yaml_file: Path) -> str:
    try:
        return yaml_file.relative_to(TEST_YAML_DIR).with_suffix("").as_posix()
    except ValueError:
        return yaml_file.with_suffix("").name


def build_test_id(yaml_file: Path, suite_name: str) -> str:
    return f"{get_manifest_id(yaml_file)}::{suite_name}"


def display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_reports_dir(value: str | None) -> Path:
    if not value:
        return REPORTS_DIR
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if path.exists() and not path.is_dir():
        raise ConfigError(f"Report output path is not a directory: {path}")
    return path


def cleanup_default_reports(reports_dir: Path) -> None:
    if reports_dir != REPORTS_DIR.resolve():
        return
    reports_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_pytest_xml_reports(reports_dir)


def snapshot_reports_as_last_run(reports_dir: Path) -> Path | None:
    if reports_dir.resolve() != REPORTS_DIR.resolve():
        return None
    if not reports_dir.exists():
        return None

    entries = [child for child in reports_dir.iterdir()]
    if not entries:
        return None

    if LAST_RUN_SNAPSHOT_DIR.exists():
        shutil.rmtree(LAST_RUN_SNAPSHOT_DIR)
    shutil.copytree(reports_dir, LAST_RUN_SNAPSHOT_DIR)
    return LAST_RUN_SNAPSHOT_DIR


def get_file_work_dir(
    suite_name: str,
    file_entry: str,
    reports_dir: Path | None = None,
) -> Path:
    reports_root = REPORTS_DIR if reports_dir is None else Path(reports_dir)
    return (
        reports_root
        / "_work"
        / sanitize_name(suite_name)
        / target_work_name(file_entry)
    )


def requires_serial_case_execution(suite_cases: list[dict[str, Any]]) -> bool:
    return any(
        str(case_def.get("type", "cli")) in IN_PROCESS_CASE_TYPES
        for case_def in suite_cases
    )


def run_case(
    suite_name: str,
    file_entry: str,
    case_index: int,
    case_def: dict[str, Any],
    options: RunCaseOptions | None = None,
) -> TestOutcome:
    if options is None:
        options = RunCaseOptions()

    file_path = resolve_target_path(file_entry)
    case_name = case_def["name"].strip()
    testcase_name = f"{suite_name}::{Path(file_entry).name}::{case_name}"
    case_type = str(case_def.get("type", "cli"))

    file_work_dir = get_file_work_dir(
        suite_name,
        file_entry,
        reports_dir=options.reports_dir,
    )
    work_dir = file_work_dir / sanitize_name(f"{case_index}_{case_name}")
    work_dir.mkdir(parents=True, exist_ok=True)

    effective_case = dict(case_def)
    if options.suite_command is not None and "command" not in effective_case:
        effective_case["command"] = options.suite_command

    meta = TestMeta(
        suite_name=suite_name,
        phase="case",
        test_type=case_type,
        expectations=json_value({key: value for key, value in effective_case.items()
                                 if key.startswith("expect_") or key == "post_checks"}),
    )

    def persist_case_logs(status: str, outcome: TestOutcome) -> None:
        case_description = effective_case.get("description")
        append_combined_case_log(
            file_work_dir=file_work_dir,
            testcase_name=testcase_name,
            status=status,
            message=outcome.message,
            details=outcome.details,
            description=case_description,
        )
        write_case_log(
            case_work_dir=work_dir,
            testcase_name=testcase_name,
            status=status,
            message=outcome.message,
            details=outcome.details,
            description=case_description,
        )

    coverage_plan_entry = None
    coverage_session = None
    case_type = str(effective_case.get("type", "cli"))
    if should_trace_case(file_path, case_type, options.change_coverage_plan):
        coverage_plan_entry = options.change_coverage_plan[file_path.resolve()]
        coverage_session = begin_change_coverage(file_path)

    try:
        try:
            passed, message, details, is_error = run_single_check(
                file_path, effective_case, work_dir
            )
        finally:
            if coverage_session is not None and coverage_plan_entry is not None:
                payload = finalize_change_coverage(
                    coverage_session,
                    file_path,
                    coverage_plan_entry,
                    testcase_name,
                )
                write_change_coverage_artifact(work_dir, payload)

        warn_only = bool(effective_case.get("warn_only", False))
        final_passed = passed
        final_warning = False

        if warn_only and not passed and not is_error:
            final_passed = True
            final_warning = True

        outcome = create_outcome(
            testcase_name=testcase_name,
            file_path=file_entry,
            passed=final_passed,
            message=sanitize_xml_text(message),
            meta=meta,
            details=sanitize_xml_text(details),
            error=is_error,
            warning=final_warning,
        )

        status = (
            "ERROR"
            if is_error
            else (
                "WARNING"
                if outcome.warning
                else ("PASS" if outcome.passed else "FAIL")
            )
        )
        persist_case_logs(status, outcome)
        return outcome
    except SkipCase as exc:
        outcome = create_outcome(
            testcase_name=testcase_name,
            file_path=file_entry,
            passed=True,
            message=sanitize_xml_text(str(exc)),
            meta=meta,
            details=sanitize_xml_text(
                f"Case skipped in work directory: {work_dir}\nReason: {exc}"
            ),
            skipped=True,
        )
        persist_case_logs("SKIPPED", outcome)
        return outcome
    except (ConfigError, CaseBuildError) as exc:
        outcome = create_outcome(
            testcase_name=testcase_name,
            file_path=file_entry,
            passed=False,
            message=sanitize_xml_text(
                format_outcome_message("Configuration error", str(exc))
            ),
            meta=meta,
            details=sanitize_xml_text(traceback.format_exc()),
            error=True,
        )
        persist_case_logs("ERROR", outcome)
        return outcome
    except Exception as exc:  # pylint: disable=broad-exception-caught
        outcome = create_outcome(
            testcase_name=testcase_name,
            file_path=file_entry,
            passed=False,
            message=sanitize_xml_text(
                format_outcome_message("Unhandled exception", str(exc))
            ),
            meta=meta,
            details=sanitize_xml_text(traceback.format_exc()),
            error=True,
        )
        persist_case_logs("ERROR", outcome)
        return outcome


def git_changed_paths_for_query(args: list[str]) -> set[Path]:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()

    paths: set[Path] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        paths.add((PROJECT_ROOT / line).resolve())
    return paths


def get_recently_changed_paths() -> set[Path]:
    changed: set[Path] = set()
    changed.update(git_changed_paths_for_query(["diff", "--name-only"]))
    changed.update(git_changed_paths_for_query(["diff", "--cached", "--name-only"]))
    changed.update(
        git_changed_paths_for_query(["ls-files", "--others", "--exclude-standard"])
    )
    return changed


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def harness_sources_changed(changed_paths: set[Path]) -> bool:
    for changed_path in changed_paths:
        if not path_is_within(changed_path, HARNESS_DIR):
            continue
        if "__pycache__" in changed_path.parts:
            continue
        return True
    return False


def normalize_target_for_matching(file_entry: str) -> Path:
    return resolve_target_path(file_entry)


def format_yaml_config_warning(yaml_file: Path, message: str) -> str:
    rel_path = yaml_file.relative_to(PROJECT_ROOT).as_posix()
    return f"Skipping {rel_path} due to configuration error: {message}"


def load_yaml_suites_for_selection(
    yaml_file: Path,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    try:
        config = load_yaml_config(yaml_file)
        suites = normalize_suites(config)
    except ConfigError as exc:
        return None, format_yaml_config_warning(yaml_file, str(exc))
    return suites, None


def get_yaml_target_entries(yaml_file: Path) -> tuple[set[str], str | None]:
    suites, warning = load_yaml_suites_for_selection(yaml_file)
    if suites is None:
        return set(), warning

    targets: set[str] = set()
    for suite in suites:
        for file_entry in suite["files"]:
            targets.add(Path(file_entry).as_posix())
    return targets, None


def yaml_targets_changed_files(
    yaml_file: Path,
    changed_paths: set[Path],
) -> tuple[set[str], str | None]:
    suites, warning = load_yaml_suites_for_selection(yaml_file)
    if suites is None:
        return set(), warning

    matched: set[str] = set()
    for suite in suites:
        for file_entry in suite["files"]:
            target_path = normalize_target_for_matching(file_entry)
            if target_path in changed_paths:
                matched.add(Path(file_entry).as_posix())
    return matched, None


def select_yaml_runs(
    yaml_files: list[Path],
) -> tuple[list[tuple[Path, set[str]]], list[str]]:
    changed_paths = get_recently_changed_paths()

    if not changed_paths:
        return [], []

    run_all_yaml_groups = harness_sources_changed(changed_paths)
    selected_map: dict[Path, set[str]] = {}
    config_warnings: list[str] = []

    for yaml_file in yaml_files:
        yaml_abs = yaml_file.resolve()
        matched_targets, warning = yaml_targets_changed_files(yaml_file, changed_paths)
        if warning is not None:
            config_warnings.append(warning)

        if run_all_yaml_groups or yaml_abs in changed_paths:
            yaml_targets, target_warning = get_yaml_target_entries(yaml_file)
            if target_warning is not None and target_warning not in config_warnings:
                config_warnings.append(target_warning)
            matched_targets.update(yaml_targets)

        if matched_targets:
            selected_map[yaml_file] = matched_targets

    return list(selected_map.items()), config_warnings


def target_matches(file_entry: str, target_path: Path, *, directory: bool) -> bool:
    """Use one exact-file or descendant-directory rule for both selectors."""
    file_path = resolve_target_path(file_entry)
    return file_path == target_path or (
        directory and path_is_within(file_path, target_path)
    )


def select_yaml_runs_for_target(
    yaml_files: list[Path],
    target: str,
) -> tuple[list[tuple[Path, set[str]]], list[str]]:
    target_path = resolve_target_path(target)
    target_is_directory = target_path.is_dir()
    selected_runs: list[tuple[Path, set[str]]] = []
    config_warnings: list[str] = []

    for yaml_file in yaml_files:
        suites, warning = load_yaml_suites_for_selection(yaml_file)
        if suites is None:
            if warning is not None:
                config_warnings.append(warning)
            continue

        matched_targets: set[str] = set()
        for suite in suites:
            for file_entry in suite["files"]:
                if target_matches(file_entry, target_path, directory=target_is_directory):
                    matched_targets.add(Path(file_entry).as_posix())

        if matched_targets:
            selected_runs.append((yaml_file, matched_targets))

    return selected_runs, config_warnings

def case_matches_changed_functions(
    case_def: dict[str, Any],
    changed_functions: set[str],
) -> bool:
    return (
        case_def.get("type") == "py_function"
        and isinstance(case_def.get("function"), str)
        and case_def["function"] in changed_functions
    )


def select_yaml_runs_by_lines(
    yaml_files: list[Path],
) -> tuple[list[tuple[Path, set[str]]], list[str], dict[Path, set[str]]]:
    changed_line_map = get_git_changed_line_ranges(PROJECT_ROOT)
    selected_runs: list[tuple[Path, set[str]]] = []
    config_warnings: list[str] = []
    matched_functions_by_target: dict[Path, set[str]] = {}

    for yaml_file in yaml_files:
        suites, warning = load_yaml_suites_for_selection(yaml_file)
        if suites is None:
            if warning is not None:
                config_warnings.append(warning)
            continue

        matched_targets: set[str] = set()

        for suite in suites:
            for file_entry in suite["files"]:
                target_path = resolve_target_path(file_entry)
                ranges = changed_line_map.get(target_path)
                if not ranges or target_path.suffix.lower() != ".py":
                    continue

                changed_functions = changed_lines_to_functions(target_path, ranges)
                if not changed_functions:
                    continue

                if any(
                    case_matches_changed_functions(case_def, changed_functions)
                    for case_def in suite["cases"]
                ):
                    matched_targets.add(Path(file_entry).as_posix())
                    matched_functions_by_target.setdefault(target_path, set()).update(
                        changed_functions
                    )

        if matched_targets:
            selected_runs.append((yaml_file, matched_targets))

    return selected_runs, config_warnings, matched_functions_by_target


def select_yaml_runs_with_mode(
    yaml_files: list[Path],
    selection_mode: str,
) -> tuple[list[tuple[Path, set[str]]], list[str], dict[Path, set[str]]]:
    if selection_mode == "file":
        selected_runs, warnings = select_yaml_runs(yaml_files)
        return selected_runs, warnings, {}

    line_runs, line_warnings, matched_functions = select_yaml_runs_by_lines(yaml_files)

    if selection_mode == "changed-lines":
        return line_runs, line_warnings, matched_functions

    file_runs, file_warnings = select_yaml_runs(yaml_files)
    merged: dict[Path, set[str]] = {}

    for yaml_file, targets in file_runs:
        merged.setdefault(yaml_file, set()).update(targets)
    for yaml_file, targets in line_runs:
        merged.setdefault(yaml_file, set()).update(targets)

    return list(merged.items()), line_warnings + file_warnings, matched_functions


def discover_test_groups(
    yaml_files: list[Path],
) -> tuple[list[TestGroup], list[str]]:
    groups: list[TestGroup] = []
    warnings: list[str] = []
    seen: dict[str, Path] = {}

    for yaml_file in yaml_files:
        suites, warning = load_yaml_suites_for_selection(yaml_file)
        if suites is None:
            if warning is not None:
                warnings.append(warning)
            continue

        for suite in suites:
            suite_name = suite["name"]
            if not suite["cases"]:
                warnings.append(
                    f"{display_path(yaml_file)} suite {suite_name!r} "
                    "has no test cases"
                )
                continue
            test_id = build_test_id(yaml_file, suite_name)
            if test_id in seen:
                warnings.append(
                    f"Duplicate test group ID {test_id!r} in "
                    f"{display_path(seen[test_id])} and "
                    f"{display_path(yaml_file)}"
                )
                continue
            seen[test_id] = yaml_file
            groups.append(
                TestGroup(
                    test_id=test_id,
                    yaml_file=yaml_file,
                    suite_name=suite_name,
                    targets=tuple(
                        Path(file_entry).as_posix()
                        for file_entry in suite["files"]
                    ),
                    case_count=len(suite["cases"]),
                )
            )

    return groups, warnings


def filter_test_groups_for_target(
    groups: list[TestGroup],
    target: str | None,
) -> list[TestGroup]:
    if not target:
        return groups

    target_path = resolve_target_path(target)
    target_is_directory = target_path.is_dir()
    scoped_groups: list[TestGroup] = []
    for group in groups:
        targets = tuple(
            file_entry
            for file_entry in group.targets
            if target_matches(file_entry, target_path, directory=target_is_directory)
        )
        if targets:
            scoped_groups.append(
                TestGroup(
                    test_id=group.test_id,
                    yaml_file=group.yaml_file,
                    suite_name=group.suite_name,
                    targets=targets,
                    case_count=group.case_count,
                )
            )
    return scoped_groups


def selected_runs_from_groups(
    groups: list[TestGroup],
) -> list[tuple[Path, set[str]]]:
    selected: dict[Path, set[str]] = {}
    for group in groups:
        selected.setdefault(group.yaml_file, set()).update(group.targets)
    return list(selected.items())


def print_test_catalog(groups: list[TestGroup]) -> None:
    outcome_count = sum(group.outcome_count for group in groups)
    print(f"Available YAML test groups ({len(groups)} groups, {outcome_count} checks):")
    for group in groups:
        print(
            f"  {group.test_id} (checks: {group.outcome_count}, "
            f"targets: {len(group.targets)}, cases: {group.case_count})"
        )


def _validate_report_filename(filename: str) -> str:
    filename = filename.strip()
    invalid_name = any(
        (
            not filename,
            filename in {".", ".."},
            "\0" in filename,
            Path(filename).name != filename,
            "/" in filename,
            "\\" in filename,
        )
    )
    if invalid_name:
        raise ConfigError(
            "Report names must be non-empty filenames; use --reports-dir "
            "to choose a directory"
        )
    return filename


def build_selected_report_paths(
    selected_runs: list[tuple[Path, set[str]]],
    reports_dir: Path,
    report_name_options: list[str],
) -> dict[Path, Path]:
    selected_manifests: dict[str, Path] = {}
    for yaml_file, _targets in selected_runs:
        manifest_id = get_manifest_id(yaml_file)
        previous = selected_manifests.get(manifest_id)
        if previous is not None and previous != yaml_file:
            raise ConfigError(
                f"Manifest ID collision between {display_path(previous)} and "
                f"{display_path(yaml_file)}: {manifest_id}"
            )
        selected_manifests[manifest_id] = yaml_file
    overrides: dict[str, str] = {}
    unnamed: list[str] = []

    for value in report_name_options:
        if "=" not in value:
            unnamed.append(value)
            continue
        manifest_id, filename = (part.strip() for part in value.split("=", 1))
        if not manifest_id:
            raise ConfigError("--report-name has an empty manifest ID")
        if manifest_id in overrides:
            raise ConfigError(f"Duplicate --report-name for {manifest_id}")
        overrides[manifest_id] = _validate_report_filename(filename)

    if unnamed:
        if len(unnamed) != 1 or len(selected_manifests) != 1:
            raise ConfigError(
                "An unqualified --report-name requires exactly one selected "
                "manifest; use MANIFEST=FILENAME for multiple manifests"
            )
        only_manifest = next(iter(selected_manifests))
        if only_manifest in overrides:
            raise ConfigError(f"Duplicate --report-name for {only_manifest}")
        overrides[only_manifest] = _validate_report_filename(unnamed[0])

    unknown = sorted(set(overrides) - set(selected_manifests))
    if unknown:
        raise ConfigError(
            "--report-name refers to unselected manifests: " + ", ".join(unknown)
        )

    report_paths: dict[Path, Path] = {}
    destinations: dict[Path, str] = {}
    for manifest_id, yaml_file in selected_manifests.items():
        filename = overrides.get(manifest_id)
        if filename is None:
            filename = build_report_path(
                get_group_name(yaml_file),
                yaml_file,
                reports_dir=reports_dir,
            ).name
        destination = reports_dir / filename
        if filename.casefold() in RESERVED_REPORT_FILENAMES:
            raise ConfigError(f"Report filename is reserved by the runner: {filename}")
        if (
            reports_dir == REPORTS_DIR.resolve()
            and filename.casefold() == "pylint-report.xml"
        ):
            raise ConfigError("Report filename is reserved for pylint: pylint-report.xml")
        if destination.is_symlink():
            raise ConfigError(f"Report destination must not be a symlink: {filename}")
        if destination.exists() and not destination.is_file():
            raise ConfigError(
                f"Report destination is not a regular file: {filename}"
            )
        resolved = destination.resolve()
        if resolved in destinations:
            raise ConfigError(
                "Report filename collision between manifests "
                f"{destinations[resolved]} and {manifest_id}: {filename}"
            )
        destinations[resolved] = manifest_id
        report_paths[yaml_file] = destination

    return report_paths


def run_yaml(  # pylint: disable=too-many-arguments
    yaml_file: Path,
    selected_targets: set[str],
    jobs: int | None = None,
    require_tests: bool | None = None,
    fail_on_warnings: bool | None = None,
    *,
    options: RunYamlOptions | None = None,
) -> int:
    if options is None:
        options = RunYamlOptions(
            jobs=4 if jobs is None else jobs,
            require_tests=False if require_tests is None else require_tests,
            fail_on_warnings=(
                False if fail_on_warnings is None else fail_on_warnings
            ),
        )
    elif any(
        value is not None for value in (jobs, require_tests, fail_on_warnings)
    ):
        raise TypeError("Use either legacy run_yaml options or RunYamlOptions, not both")
    reports_root = (
        REPORTS_DIR if options.reports_dir is None else Path(options.reports_dir)
    )
    reports_root.mkdir(parents=True, exist_ok=True)

    group_name = get_group_name(yaml_file)
    xml_report = options.xml_report
    if xml_report is None:
        xml_report = build_report_path(group_name, yaml_file, reports_root)

    print(f"\n[INFO] Running group : {group_name}")
    print(
        f"[INFO] YAML file     : "
        f"{yaml_file.relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(
        f"[INFO] XML report    : "
        f"{display_path(xml_report)}"
    )

    try:
        config = load_yaml_config(yaml_file)
        suites = normalize_suites(config)
    except ConfigError as exc:
        outcome = build_config_error_outcome(
            yaml_file=yaml_file,
            message=format_outcome_message("Configuration error", str(exc)),
            details=traceback.format_exc(),
        )
        write_junit_xml(xml_report, group_name, yaml_file, [outcome])
        print_group_summary(group_name, [outcome], xml_report)
        return 1

    outcomes: list[TestOutcome] = []

    for suite_index, suite in enumerate(suites, start=1):
        suite_name = suite["name"]
        if (
            options.selected_group_ids is not None
            and build_test_id(yaml_file, suite_name)
            not in options.selected_group_ids
        ):
            continue
        run_case_options = RunCaseOptions(
            suite_command=suite.get("command"),
            reports_dir=reports_root,
            change_coverage_plan=options.change_coverage_plan,
        )
        suite_files = suite["files"]
        suite_cases = suite["cases"]

        filtered_files = []
        for file_entry in suite_files:
            normalized_file_entry = Path(file_entry).as_posix()
            if normalized_file_entry in selected_targets:
                filtered_files.append(file_entry)

        if not filtered_files:
            continue

        print(f"[INFO] Suite         : {suite_name}")

        if not suite_cases:
            outcomes.append(
                create_outcome(
                    testcase_name=f"{suite_name}::no_cases",
                    file_path="",
                    passed=False,
                    message="Suite has no cases defined",
                    meta=TestMeta(
                        suite_name=suite_name,
                        phase="suite",
                        test_type="config",
                    ),
                    details=f"suites[{suite_index}] has an empty 'cases' list.",
                    error=True,
                )
            )
            continue

        for file_entry in filtered_files:
            print(f"[INFO] Target file   : {file_entry}")

            case_jobs = list(enumerate(suite_cases, start=1))

            file_work_dir = get_file_work_dir(
                suite_name,
                file_entry,
                reports_dir=reports_root,
            )

            if file_work_dir.exists():
                shutil.rmtree(file_work_dir)
            file_work_dir.mkdir(parents=True, exist_ok=True)

            append_run_header(
                file_work_dir=file_work_dir,
                suite_name=suite_name,
                yaml_file=yaml_file,
                targets=[file_entry],
            )

            file_jobs = (
                1
                if requires_serial_case_execution(suite_cases)
                else options.jobs
            )

            if file_jobs <= 1:
                for case_index, case_def in case_jobs:
                    outcomes.append(
                        run_case(
                            suite_name=suite_name,
                            file_entry=file_entry,
                            case_index=case_index,
                            case_def=case_def,
                            options=run_case_options,
                        )
                    )
            else:
                case_results: list[tuple[int, TestOutcome]] = []
                with ThreadPoolExecutor(max_workers=file_jobs) as executor:
                    future_map = {
                        executor.submit(
                            run_case,
                            suite_name,
                            file_entry,
                            case_index,
                            case_def,
                            run_case_options,
                        ): case_index
                        for case_index, case_def in case_jobs
                    }
                    for future in as_completed(future_map):
                        case_index = future_map[future]
                        case_results.append((case_index, future.result()))

                for _case_index, outcome in sorted(
                    case_results,
                    key=lambda item: item[0],
                ):
                    outcomes.append(outcome)

    if not outcomes and options.require_tests:
        outcome = build_config_error_outcome(
            yaml_file=yaml_file,
            message="Selected YAML run produced no test outcomes",
            details=(
                "The selected targets did not execute any test cases. "
                "A required pre-check-in gate must never pass without running tests."
            ),
        )
        write_junit_xml(xml_report, group_name, yaml_file, [outcome])
        print_group_summary(group_name, [outcome], xml_report)
        return 1

    if not outcomes:
        return 0

    if options.fail_on_warnings:
        outcomes = [
            replace(
                item,
                passed=False,
                message=f"Warning treated as failure: {item.message}",
                flags={**item.flags, "warning": False},
            ) if item.warning else item
            for item in outcomes
        ]

    write_junit_xml(xml_report, group_name, yaml_file, outcomes)
    print_group_summary(group_name, outcomes, xml_report)

    if options.fail_on_skips and any(item.skipped for item in outcomes):
        return 1

    return 0 if all(item.passed or item.skipped or item.warning for item in outcomes) else 1



def generate_runner_dashboard(
    output_path: Path,
    reports_dir: Path,
    previous_reports_dir: Path | None,
) -> None:
    """Generate the requested dashboard and print its location."""
    write_dashboard(
        output_path=output_path,
        options=DashboardWriteOptions(
            reports_dir=reports_dir,
            previous_reports_dir=previous_reports_dir,
        ),
    )
    print(f"[INFO] Dashboard written to: {display_path(output_path)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run YAML-driven tests for impacted files or a manual target."
    )
    parser.add_argument(
        "--target",
        help="Run tests only for the specified Python file target from YAML suites",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Number of YAML test cases to run in parallel (default: 4)",
    )
    parser.add_argument(
        "--selection-mode",
        choices=("file", "hybrid", "changed-lines"),
        default="file",
        help="Selection strategy for impacted YAML groups (default: file)",
    )
    parser.add_argument(
        "--list-impacted-cases",
        action="store_true",
        help="List impacted YAML groups/targets and exit without running them",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Generate a static HTML dashboard from YAML runner reports",
    )
    parser.add_argument(
        "--change-coverage",
        action="store_true",
        help="Trace changed Python functions/lines reached by existing YAML tests",
    )
    parser.add_argument(
        "--change-coverage-function",
        action="append",
        default=[],
        help="Track whether the named Python function is reached by existing YAML tests. Repeatable.",
    )
    parser.add_argument(
        "--dashboard-output",
        help="Optional output path for the generated dashboard HTML",
    )
    parser.add_argument(
        "--dashboard-compare-reports-dir",
        help="Optional previous reports directory for dashboard comparison (defaults to last run snapshot)",
    )

    args = parser.parse_args()

    jobs = max(1, args.jobs)
    reports_dir = REPORTS_DIR

    function_coverage_requested = bool(args.change_coverage_function)
    change_coverage_requested = not args.list_impacted_cases and (
        args.change_coverage or function_coverage_requested
    )

    change_coverage_plan: dict[Path, dict[str, Any]] | None = None
    if change_coverage_requested:
        if not coverage_supported():
            print("[ERROR] --change-coverage requires coverage.py to be installed.")
            return 1


    dashboard_output = (
        Path(args.dashboard_output).resolve()
        if args.dashboard_output
        else reports_dir / "dashboard.html"
    )

    # Listing is read-only, including when --dashboard is also supplied.
    if not args.list_impacted_cases:
        reports_dir.mkdir(parents=True, exist_ok=True)
        snapshot_reports_as_last_run(reports_dir)
        cleanup_old_pytest_xml_reports()

    dashboard_compare_reports_dir = (
        Path(args.dashboard_compare_reports_dir).resolve()
        if args.dashboard_compare_reports_dir
        else (LAST_RUN_SNAPSHOT_DIR if LAST_RUN_SNAPSHOT_DIR.exists() else None)
    )

    yaml_files = discover_yaml_files()

    if not yaml_files:
        reason = (
            f"No YAML files found in "
            f"{TEST_YAML_DIR.relative_to(PROJECT_ROOT).as_posix()}"
        )
        print(f"WARNING: {reason}")
        if args.list_impacted_cases:
            return 0
        create_placeholder_xml(reason, reports_dir)
        if args.dashboard:
            generate_runner_dashboard(
                dashboard_output, reports_dir, dashboard_compare_reports_dir
            )
        return 0

    if not args.list_impacted_cases:
        remove_placeholder_xml()

    if args.target:
        print(f"[INFO] Manual target override enabled: {args.target}")
        selected_runs, config_warnings = select_yaml_runs_for_target(
            yaml_files,
            args.target,
        )
    else:
        selected_runs, config_warnings, _matched_functions_by_target = (
            select_yaml_runs_with_mode(
                yaml_files,
                selection_mode=args.selection_mode,
            )
        )

    for warning in config_warnings:
        print(f"[WARNING] {warning}")

    if change_coverage_requested:
        selected_target_paths = sorted(
            {
                resolve_target_path(target).resolve()
                for _yaml_file, selected_targets in selected_runs
                for target in selected_targets
            }
        )

        if function_coverage_requested:
            change_coverage_plan = build_function_coverage_plan(
                selected_target_paths,
                args.change_coverage_function,
            )
            matched_function_names = sorted(
                {
                    str(function.get("name"))
                    for entry in change_coverage_plan.values()
                    for function in entry.get("functions", [])
                    if function.get("name")
                }
            )
            requested_function_names = [
                name.strip()
                for name in args.change_coverage_function
                if isinstance(name, str) and name.strip()
            ]
            missing_function_names = [
                name for name in requested_function_names if name not in matched_function_names
            ]
            covered_target_count = len(change_coverage_plan)
            print(
                "[INFO] Function-aware coverage enabled for "
                f"{covered_target_count} selected Python files and "
                f"{len(matched_function_names)} requested functions."
            )
            if missing_function_names:
                print(
                    "[WARNING] Requested functions not found in selected targets: "
                    + ", ".join(missing_function_names)
                )
        else:
            change_coverage_plan = build_change_coverage_plan(PROJECT_ROOT)
            changed_function_count = sum(
                len(item.get("functions", [])) for item in change_coverage_plan.values()
            )
            print(
                "[INFO] Change-aware coverage enabled for "
                f"{len(change_coverage_plan)} changed Python files and "
                f"{changed_function_count} changed functions."
            )

    if not selected_runs:
        if args.target:
            if config_warnings:
                message = (
                    f"No valid YAML test groups found for manual target: {args.target}"
                )
                print(f"[ERROR] {message}")
                if args.list_impacted_cases:
                    return 1
                cleanup_default_reports(reports_dir)
                reports_dir.mkdir(parents=True, exist_ok=True)
                create_placeholder_xml(message, reports_dir)
                if args.dashboard:
                    generate_runner_dashboard(
                        dashboard_output, reports_dir, dashboard_compare_reports_dir
                    )
                return 1
            message = f"No YAML test groups found for manual target: {args.target}"
        else:
            message = "No impacted YAML test groups found for changed files."

        print(f"[INFO] {message}")
        if args.list_impacted_cases:
            return 0
        print(
            f"[INFO] Reports written to: "
            f"{reports_dir.relative_to(PROJECT_ROOT).as_posix()}"
        )
        cleanup_default_reports(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        create_placeholder_xml(message, reports_dir)
        if args.dashboard:
            generate_runner_dashboard(
                dashboard_output, reports_dir, dashboard_compare_reports_dir
            )
        return 0

    if args.list_impacted_cases:
        if args.target:
            print("[INFO] Impacted YAML test groups for manual target:")
        else:
            print("[INFO] Impacted YAML test groups:")
        for yaml_file, selected_targets in selected_runs:
            print(f"  - {yaml_file.relative_to(PROJECT_ROOT).as_posix()}")
            for target in sorted(selected_targets):
                print(f"      * target: {target}")
        return 0

    if args.target:
        print("[INFO] Running YAML test groups for manual target:")
    else:
        print("[INFO] Running only impacted YAML test groups:")

    for yaml_file, selected_targets in selected_runs:
        print(f"  - {yaml_file.relative_to(PROJECT_ROOT).as_posix()}")
        for target in sorted(selected_targets):
            print(f"      * target: {target}")

    overall_exit_code = 0
    for yaml_file, selected_targets in selected_runs:
        exit_code = run_yaml(
            yaml_file,
            selected_targets=selected_targets,
            options=RunYamlOptions(
                jobs=jobs,
                change_coverage_plan=change_coverage_plan,
            ),
        )
        if exit_code != 0:
            overall_exit_code = exit_code

    print("\n[INFO] Custom YAML test execution completed.")
    print(
        f"[INFO] Reports written to: "
        f"{reports_dir.relative_to(PROJECT_ROOT).as_posix()}"
    )

    if args.dashboard:
        generate_runner_dashboard(
            dashboard_output, reports_dir, dashboard_compare_reports_dir
        )

    return overall_exit_code


if __name__ == "__main__":
    sys.exit(main())
