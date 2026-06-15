from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

try:  # Support package imports and direct harness module loading.
    from .case_data_builders import render_post_check_path
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from case_data_builders import render_post_check_path


SCRIPT_DIR = Path(__file__).resolve().parent


def detect_project_root(script_dir: Path) -> Path:
    if script_dir.parent.name == "common":
        return script_dir.parent.parent
    return script_dir.parent


PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
TEST_YAML_DIR = PROJECT_ROOT / "common" / "acs_test_framework_manifests"
REPORTS_DIR = PROJECT_ROOT / "common" / "reports"
RUNNER_WORK_DIR = REPORTS_DIR / "_runner_work"
SUPPORTED_SUFFIXES = {".yaml", ".yml"}
DEFAULT_CLI_TIMEOUT_SEC = 20
DESTRUCTIVE_TEST_ENV = "RUN_DESTRUCTIVE_HW_TESTS"
# Runner-managed process launches must not be affected by case-level
# subprocess.run mocks that target the global subprocess module.
REAL_SUBPROCESS_RUN = subprocess.run


@dataclass
class TestMeta:
    suite_name: str
    phase: str
    test_type: str


@dataclass
class TestOutcome:
    testcase_name: str
    file_path: str
    passed: bool
    message: str
    meta: TestMeta
    details: str = ""
    flags: dict[str, bool] = field(
        default_factory=lambda: {
            "error": False,
            "skipped": False,
            "warning": False,
        }
    )

    @property
    def error(self) -> bool:
        return self.flags["error"]

    @property
    def skipped(self) -> bool:
        return self.flags["skipped"]

    @property
    def warning(self) -> bool:
        return self.flags["warning"]


class ConfigError(Exception):
    """Raised when a YAML configuration is invalid."""


class SkipCase(Exception):
    """Raised when a case should be skipped due to environment gating."""


@dataclass
class CommandRunResult:
    command_text: str
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    timeout_sec: int
    shell_mode: bool


@dataclass(frozen=True)
class RunCaseOptions:
    suite_command: str | None = None


def create_runner_temp_dir(prefix: str = "runner_env_") -> Path:
    RUNNER_WORK_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        candidate = RUNNER_WORK_DIR / f"{prefix}{uuid4().hex[:8]}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise OSError(f"Could not create runner temp dir under {RUNNER_WORK_DIR}")


def load_yaml_config(yaml_file: Path) -> dict[str, Any]:
    try:
        with yaml_file.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Top-level YAML content must be a mapping")

    return data


def ensure_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"'{field_name}' must be a list")
    return value


def ensure_list_of_strings(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"'{field_name}' must be a list of strings")
    return value


def ensure_string_or_list_of_strings(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return ensure_list_of_strings(value, field_name)


def merge_mappings(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Recursively merge mappings with override precedence."""
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_mappings(existing, value)
        else:
            merged[key] = value
    return merged


def sanitize_name(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in value
    )


def is_valid_xml_char(code: int) -> bool:
    return (
        code in {0x9, 0xA, 0xD}
        or 0x20 <= code <= 0xD7FF
        or 0xE000 <= code <= 0xFFFD
        or 0x10000 <= code <= 0x10FFFF
    )


def sanitize_xml_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)

    cleaned: list[str] = []
    for char in value:
        if is_valid_xml_char(ord(char)):
            cleaned.append(char)
    return "".join(cleaned)


def resolve_target_path(file_entry: str) -> Path:
    raw = Path(file_entry)
    if raw.is_absolute():
        return raw.resolve()
    return (PROJECT_ROOT / raw).resolve()


def read_source(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def parse_ast(file_path: Path) -> ast.AST:
    return ast.parse(read_source(file_path), filename=str(file_path))


def collect_function_names(file_path: Path) -> set[str]:
    tree = parse_ast(file_path)
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)

    return names


def format_outcome_message(prefix: str, text: str) -> str:
    text = text.strip()
    return prefix if not text else f"{prefix}: {text}"


def create_outcome(
    testcase_name: str,
    file_path: str,
    passed: bool,
    message: str,
    meta: TestMeta,
    **kwargs: Any,
) -> TestOutcome:
    return TestOutcome(
        testcase_name=testcase_name,
        file_path=file_path,
        passed=passed,
        message=message,
        meta=meta,
        details=kwargs.get("details", ""),
        flags={
            "error": kwargs.get("error", False),
            "skipped": kwargs.get("skipped", False),
            "warning": kwargs.get("warning", False),
        },
    )


def build_runner_module_name(file_path: Path) -> str:
    return f"runner_module_{sanitize_name(file_path.stem)}_{uuid4().hex}"


def load_module_from_path(file_path: Path) -> Any:
    module_name = build_runner_module_name(file_path)
    spec = importlib.util.spec_from_file_location(
        module_name,
        str(file_path),
    )
    if spec is None or spec.loader is None:
        raise ConfigError(f"Could not load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def normalize_completed_stream(stream: Any) -> str:
    if stream is None:
        return ""
    if isinstance(stream, str):
        return stream
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return str(stream)


try:  # Support package imports and direct harness module loading.
    from .runner_check_validation import (
        normalize_cases,
        normalize_suite_files,
        normalize_suites,
        validate_case_mocks,
        validate_case_schema,
        validate_command_probe_list,
        validate_common_case_controls,
        validate_env_mapping,
        validate_mock_spec,
        validate_post_checks,
    )
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from runner_check_validation import (
        normalize_cases,
        normalize_suite_files,
        normalize_suites,
        validate_case_mocks,
        validate_case_schema,
        validate_command_probe_list,
        validate_common_case_controls,
        validate_env_mapping,
        validate_mock_spec,
        validate_post_checks,
    )


def run_post_checks(work_dir: Path, post_checks: Any) -> tuple[bool, list[str]]:
    if post_checks is None:
        return True, []

    checks = ensure_list(post_checks, "post_checks")
    messages: list[str] = []
    all_passed = True

    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            raise ConfigError(f"post_checks[{index}] must be a mapping")

        check_type = check.get("type")
        raw_path = check.get("path")

        if not isinstance(check_type, str):
            raise ConfigError(f"post_checks[{index}] requires string key 'type'")
        if not isinstance(raw_path, str):
            raise ConfigError(f"post_checks[{index}] requires string key 'path'")

        resolved = render_post_check_path(raw_path, work_dir)

        if check_type == "exists":
            exists = resolved.exists()
            messages.append(
                f"post_check exists: {resolved} -> {'PASS' if exists else 'FAIL'}"
            )
            if not exists:
                all_passed = False
            continue

        if check_type == "not_exists":
            missing = not resolved.exists()
            messages.append(
                f"post_check not_exists: {resolved} -> {'PASS' if missing else 'FAIL'}"
            )
            if not missing:
                all_passed = False
            continue

        if check_type == "file_not_empty":
            passed = (
                resolved.exists()
                and resolved.is_file()
                and resolved.stat().st_size > 0
            )
            messages.append(
                f"post_check file_not_empty: {resolved} -> {'PASS' if passed else 'FAIL'}"
            )
            if not passed:
                all_passed = False
            continue

        if check_type in {"file_contains", "file_not_contains"}:
            text = check.get("text")
            if not isinstance(text, str):
                raise ConfigError(f"post_checks[{index}] requires string key 'text'")

            if not resolved.exists() or not resolved.is_file():
                messages.append(
                    f"post_check {check_type}: {resolved} contains {text!r} -> FAIL"
                )
                all_passed = False
                continue

            contents = resolved.read_text(encoding="utf-8", errors="replace")
            contains = text in contents
            passed = contains if check_type == "file_contains" else not contains

            messages.append(
                f"post_check {check_type}: {resolved} contains {text!r} -> "
                f"{'PASS' if passed else 'FAIL'}"
            )
            if not passed:
                all_passed = False
            continue

        if check_type == "regex":
            pattern = check.get("pattern")
            if not isinstance(pattern, str):
                raise ConfigError(
                    f"post_checks[{index}] requires string key 'pattern'"
                )

            if not resolved.exists() or not resolved.is_file():
                messages.append(
                    f"post_check regex: {resolved} matches {pattern!r} -> FAIL"
                )
                all_passed = False
                continue

            contents = resolved.read_text(encoding="utf-8", errors="replace")
            passed = re.search(pattern, contents, flags=re.MULTILINE) is not None
            messages.append(
                f"post_check regex: {resolved} matches {pattern!r} -> "
                f"{'PASS' if passed else 'FAIL'}"
            )
            if not passed:
                all_passed = False
            continue

        if check_type == "ordered_contains":
            texts = check.get("texts")
            if not isinstance(texts, list) or not all(
                isinstance(item, str) for item in texts
            ):
                raise ConfigError(
                    f"post_checks[{index}] requires key 'texts' as list[str]"
                )

            if not resolved.exists() or not resolved.is_file():
                messages.append(f"post_check ordered_contains: {resolved} -> FAIL")
                all_passed = False
                continue

            contents = resolved.read_text(encoding="utf-8", errors="replace")
            start = 0
            passed = True
            for text in texts:
                idx = contents.find(text, start)
                if idx == -1:
                    passed = False
                    messages.append(
                        f"post_check ordered_contains: {resolved} "
                        f"missing {text!r} in order -> FAIL"
                    )
                    all_passed = False
                    break
                start = idx + len(text)

            if passed:
                messages.append(f"post_check ordered_contains: {resolved} -> PASS")
            continue

        raise ConfigError(f"post_checks[{index}] unsupported type: {check_type}")

    return all_passed, messages


def format_output_block(title: str, text: str) -> str:
    cleaned = text.rstrip()
    if not cleaned:
        cleaned = "<empty>"
    return f"{title}\n{cleaned}"


def append_log_file_details(
    details_lines: list[str],
    runtime_case: dict[str, Any],
) -> None:
    patch_constants = runtime_case.get("patch_constants", {})
    if not isinstance(patch_constants, dict):
        return

    log_path_value = patch_constants.get("LOG_FILE")
    if not isinstance(log_path_value, str):
        return

    log_path = Path(log_path_value)
    details_lines.append("--- LOG FILE ---")

    if not log_path.exists() or not log_path.is_file():
        details_lines.append(f"<missing: {log_path}>")
        return

    log_text = log_path.read_text(encoding="utf-8", errors="replace").rstrip()
    details_lines.append(log_text if log_text else "<empty>")


def format_expectation_failure(
    check_type: str,
    expected: str,
    stdout: str,
    stderr: str,
    *,
    actual_label: str = "",
) -> str:
    lines = [
        "PHASE: expectation_check",
        f"CHECK TYPE: {check_type}",
        "",
        "EXPECTED:",
        f"  {expected}",
        "",
        format_output_block("ACTUAL STDOUT:", stdout),
        "",
        format_output_block("ACTUAL STDERR:", stderr),
    ]
    if actual_label:
        lines.extend(["", "ACTUAL:", f"  {actual_label}"])
    return "\n".join(lines)


def validate_output_expectations(
    case_def: dict[str, Any],
    stdout: str,
    stderr: str,
) -> tuple[bool, list[str]]:
    conditions: list[str] = []
    passed = True

    expected_exit_code = case_def.get("expect_exit_code")
    expect_exit_nonzero = bool(case_def.get("expect_exit_nonzero", False))

    if expected_exit_code is not None and not isinstance(expected_exit_code, int):
        raise ConfigError("'expect_exit_code' must be an integer")

    actual_exit_code = case_def.get("_actual_exit_code")

    if actual_exit_code is not None:
        if expected_exit_code is not None:
            if actual_exit_code != expected_exit_code:
                passed = False
                conditions.append(
                    "\n".join(
                        [
                            "PHASE: expectation_check",
                            "CHECK TYPE: expect_exit_code",
                            "",
                            "EXPECTED:",
                            f"  exit code = {expected_exit_code}",
                            "",
                            "ACTUAL:",
                            f"  exit code = {actual_exit_code}",
                        ]
                    )
                )
        elif expect_exit_nonzero and actual_exit_code == 0:
            passed = False
            conditions.append(
                "\n".join(
                    [
                        "PHASE: expectation_check",
                        "CHECK TYPE: expect_exit_nonzero",
                        "",
                        "EXPECTED:",
                        "  non-zero exit code",
                        "",
                        "ACTUAL:",
                        f"  exit code = {actual_exit_code}",
                    ]
                )
            )

    expect_output = case_def.get("expect_output")
    if expect_output is not None:
        candidates = (
            [expect_output]
            if isinstance(expect_output, str)
            else ensure_list_of_strings(expect_output, "expect_output")
        )
        merged = stdout + "\n" + stderr
        for candidate in candidates:
            if candidate not in merged:
                passed = False
                conditions.append(
                    format_expectation_failure(
                        check_type="expect_output",
                        expected=candidate,
                        stdout=stdout,
                        stderr=stderr,
                    )
                )

    stdout_contains = case_def.get("expect_stdout_contains")
    if stdout_contains is not None:
        if not isinstance(stdout_contains, str):
            raise ConfigError("'expect_stdout_contains' must be a string")
        if stdout_contains not in stdout:
            passed = False
            conditions.append(
                format_expectation_failure(
                    check_type="expect_stdout_contains",
                    expected=stdout_contains,
                    stdout=stdout,
                    stderr=stderr,
                )
            )

    stderr_contains = case_def.get("expect_stderr_contains")
    if stderr_contains is not None:
        if not isinstance(stderr_contains, str):
            raise ConfigError("'expect_stderr_contains' must be a string")
        if stderr_contains not in stderr:
            passed = False
            conditions.append(
                format_expectation_failure(
                    check_type="expect_stderr_contains",
                    expected=stderr_contains,
                    stdout=stdout,
                    stderr=stderr,
                )
            )

    either_contains = case_def.get("expect_stdout_or_stderr_contains")
    if either_contains is not None:
        candidates = (
            [either_contains]
            if isinstance(either_contains, str)
            else ensure_list_of_strings(
                either_contains,
                "expect_stdout_or_stderr_contains",
            )
        )
        for candidate in candidates:
            if candidate not in stdout and candidate not in stderr:
                passed = False
                conditions.append(
                    format_expectation_failure(
                        check_type="expect_stdout_or_stderr_contains",
                        expected=candidate,
                        stdout=stdout,
                        stderr=stderr,
                    )
                )

    expect_stdout_or_stderr_regex = case_def.get("expect_stdout_or_stderr_regex")
    if expect_stdout_or_stderr_regex is not None:
        candidates = (
            [expect_stdout_or_stderr_regex]
            if isinstance(expect_stdout_or_stderr_regex, str)
            else ensure_list_of_strings(
                expect_stdout_or_stderr_regex,
                "expect_stdout_or_stderr_regex",
            )
        )
        merged = stdout + "\n" + stderr
        for pattern in candidates:
            if re.search(pattern, merged, flags=re.MULTILINE) is None:
                passed = False
                conditions.append(
                    format_expectation_failure(
                        check_type="expect_stdout_or_stderr_regex",
                        expected=pattern,
                        stdout=stdout,
                        stderr=stderr,
                    )
                )

    expect_exit_code_in = case_def.get("expect_exit_code_in")
    if expect_exit_code_in is not None:
        if not isinstance(expect_exit_code_in, list) or not all(
            isinstance(item, int) for item in expect_exit_code_in
        ):
            raise ConfigError("'expect_exit_code_in' must be a list of integers")
        if actual_exit_code not in expect_exit_code_in:
            passed = False
            conditions.append(
                "\n".join(
                    [
                        "PHASE: expectation_check",
                        "CHECK TYPE: expect_exit_code_in",
                        "",
                        "EXPECTED:",
                        f"  exit code in {expect_exit_code_in}",
                        "",
                        "ACTUAL:",
                        f"  exit code = {actual_exit_code}",
                    ]
                )
            )

    return passed, conditions


try:  # Support package imports and direct harness module loading.
    from .runner_check_execution import (
        CHECK_HANDLERS,
        apply_skip_controls,
        build_cli_command,
        build_cli_env,
        build_command_from_spec,
        build_runtime_env,
        check_cli,
        check_command_exit_code,
        check_command_output_contains,
        check_command_output_regex,
        check_command_success,
        check_file_exists,
        check_function_exists,
        check_function_exists_any,
        check_main_guard,
        check_module_cli,
        check_module_main_with_env,
        check_path_exists,
        check_path_not_exists,
        check_py_compile,
        check_py_function,
        check_source_contains,
        check_source_contains_all,
        check_source_contains_any,
        execute_command_spec,
        normalize_probe_spec,
        run_command_assertion,
        run_single_check,
    )
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from runner_check_execution import (
        CHECK_HANDLERS,
        apply_skip_controls,
        build_cli_command,
        build_cli_env,
        build_command_from_spec,
        build_runtime_env,
        check_cli,
        check_command_exit_code,
        check_command_output_contains,
        check_command_output_regex,
        check_command_success,
        check_file_exists,
        check_function_exists,
        check_function_exists_any,
        check_main_guard,
        check_module_cli,
        check_module_main_with_env,
        check_path_exists,
        check_path_not_exists,
        check_py_compile,
        check_py_function,
        check_source_contains,
        check_source_contains_all,
        check_source_contains_any,
        execute_command_spec,
        normalize_probe_spec,
        run_command_assertion,
        run_single_check,
    )
