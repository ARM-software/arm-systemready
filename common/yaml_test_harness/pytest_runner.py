from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from case_data_builders import CaseBuildError
from runner_checks import (
    ConfigError,
    RunCaseOptions,
    SkipCase,
    TestMeta,
    TestOutcome,
    create_outcome,
    format_outcome_message,
    load_yaml_config,
    normalize_suites,
    resolve_target_path,
    run_single_check,
    sanitize_name,
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

SCRIPT_DIR = Path(__file__).resolve().parent


def detect_project_root(script_dir: Path) -> Path:
    if script_dir.parent.name == "common":
        return script_dir.parent.parent
    return script_dir.parent


PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
TEST_YAML_DIR = PROJECT_ROOT / "common" / "test_yaml"
REPORTS_DIR = PROJECT_ROOT / "common" / "reports"
SUPPORTED_SUFFIXES = {".yaml", ".yml"}
IN_PROCESS_CASE_TYPES = {"py_function", "module_main_with_env", "module_cli"}


def discover_yaml_files() -> list[Path]:
    if not TEST_YAML_DIR.exists() or not TEST_YAML_DIR.is_dir():
        return []
    return sorted(
        path
        for path in TEST_YAML_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def get_group_name(yaml_file: Path) -> str:
    rel_path = yaml_file.relative_to(TEST_YAML_DIR)
    return rel_path.parts[0] if len(rel_path.parts) > 1 else yaml_file.stem



def get_file_work_dir(suite_name: str, file_entry: str) -> Path:
    return (
        REPORTS_DIR
        / "_work"
        / sanitize_name(suite_name)
        / sanitize_name(Path(file_entry).stem)
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

    file_work_dir = get_file_work_dir(suite_name, file_entry)
    work_dir = file_work_dir / sanitize_name(f"{case_index}_{case_name}")
    work_dir.mkdir(parents=True, exist_ok=True)

    effective_case = dict(case_def)
    if options.suite_command is not None and "command" not in effective_case:
        effective_case["command"] = options.suite_command

    meta = TestMeta(
        suite_name=suite_name,
        phase="case",
        test_type=case_type,
    )

    def persist_case_logs(status: str, outcome: TestOutcome) -> None:
        append_combined_case_log(
            file_work_dir=file_work_dir,
            testcase_name=testcase_name,
            status=status,
            message=outcome.message,
            details=outcome.details,
        )
        write_case_log(
            case_work_dir=work_dir,
            testcase_name=testcase_name,
            status=status,
            message=outcome.message,
            details=outcome.details,
        )

    try:
        passed, message, details, is_error = run_single_check(
            file_path, effective_case, work_dir
        )

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

    selected_map: dict[Path, set[str]] = {}
    config_warnings: list[str] = []

    for yaml_file in yaml_files:
        yaml_abs = yaml_file.resolve()
        matched_targets, warning = yaml_targets_changed_files(yaml_file, changed_paths)
        if warning is not None:
            config_warnings.append(warning)

        if yaml_abs in changed_paths:
            yaml_targets, target_warning = get_yaml_target_entries(yaml_file)
            if target_warning is not None and target_warning not in config_warnings:
                config_warnings.append(target_warning)
            matched_targets.update(yaml_targets)

        if matched_targets:
            selected_map[yaml_file] = matched_targets

    return list(selected_map.items()), config_warnings


def select_yaml_runs_for_target(
    yaml_files: list[Path],
    target: str,
) -> tuple[list[tuple[Path, set[str]]], list[str]]:
    target_path = resolve_target_path(target)
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
                if resolve_target_path(file_entry) == target_path:
                    matched_targets.add(Path(file_entry).as_posix())

        if matched_targets:
            selected_runs.append((yaml_file, matched_targets))

    return selected_runs, config_warnings



def run_yaml(
    yaml_file: Path,
    selected_targets: set[str],
    jobs: int = 4,
) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    group_name = get_group_name(yaml_file)
    xml_report = build_report_path(group_name, yaml_file)

    print(f"\n[INFO] Running group : {group_name}")
    print(
        f"[INFO] YAML file     : "
        f"{yaml_file.relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(
        f"[INFO] XML report    : "
        f"{xml_report.relative_to(PROJECT_ROOT).as_posix()}"
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
        run_case_options = RunCaseOptions(
            suite_command=suite.get("command"),
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

            file_work_dir = get_file_work_dir(suite_name, file_entry)

            if file_work_dir.exists():
                shutil.rmtree(file_work_dir)
            file_work_dir.mkdir(parents=True, exist_ok=True)

            append_run_header(
                file_work_dir=file_work_dir,
                suite_name=suite_name,
                yaml_file=yaml_file,
                targets=[file_entry],
            )

            case_jobs = list(enumerate(suite_cases, start=1))
            file_jobs = 1 if requires_serial_case_execution(suite_cases) else jobs

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

    if not outcomes:
        return 0

    write_junit_xml(xml_report, group_name, yaml_file, outcomes)
    print_group_summary(group_name, outcomes, xml_report)

    return 0 if all(item.passed or item.skipped or item.warning for item in outcomes) else 1


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
    args = parser.parse_args()

    jobs = max(1, args.jobs)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_old_pytest_xml_reports()

    yaml_files = discover_yaml_files()

    if not yaml_files:
        reason = (
            f"No YAML files found in "
            f"{TEST_YAML_DIR.relative_to(PROJECT_ROOT).as_posix()}"
        )
        print(f"WARNING: {reason}")
        create_placeholder_xml(reason)
        return 0

    remove_placeholder_xml()

    if args.target:
        print(f"[INFO] Manual target override enabled: {args.target}")
        selected_runs, config_warnings = select_yaml_runs_for_target(
            yaml_files,
            args.target,
        )
    else:
        selected_runs, config_warnings = select_yaml_runs(yaml_files)

    for warning in config_warnings:
        print(f"[WARNING] {warning}")

    if not selected_runs:
        if args.target:
            if config_warnings:
                message = (
                    f"No valid YAML test groups found for manual target: {args.target}"
                )
                print(f"[ERROR] {message}")
                print(
                    f"[INFO] Reports written to: "
                    f"{REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}"
                )
                create_placeholder_xml(message)
                return 1
            message = f"No YAML test groups found for manual target: {args.target}"
        else:
            message = "No impacted YAML test groups found for changed files."

        print(f"[INFO] {message}")
        print(
            f"[INFO] Reports written to: "
            f"{REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}"
        )
        create_placeholder_xml(message)
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
            jobs=jobs,
        )
        if exit_code != 0:
            overall_exit_code = exit_code

    print("\n[INFO] Custom YAML test execution completed.")
    print(
        f"[INFO] Reports written to: "
        f"{REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}"
    )
    return overall_exit_code


if __name__ == "__main__":
    sys.exit(main())
