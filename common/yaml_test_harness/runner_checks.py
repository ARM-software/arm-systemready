from __future__ import annotations

import ast
import io
import importlib.util
import os
import py_compile
import re
import shlex
import shutil
import subprocess
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from uuid import uuid4
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from mock_helpers import MockExpectationError
from case_data_builders import (
    CaseBuildError,
    expand_template,
    materialize_case_workspace,
    prepare_case_files,
    render_post_check_path,
)

from mock_loader import apply_case_mocks
from mock_loader import build_case_runtime_definition
from mock_loader import ConfigError as MockLoaderConfigError


SCRIPT_DIR = Path(__file__).resolve().parent


def detect_project_root(script_dir: Path) -> Path:
    if script_dir.parent.name == "common":
        return script_dir.parent.parent
    return script_dir.parent


PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
TEST_YAML_DIR = PROJECT_ROOT / "common" / "test_yaml"
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


def normalize_suite_files(files_value: Any, field_name: str) -> list[str]:
    items = ensure_list(files_value, field_name)
    if not items:
        raise ConfigError(f"'{field_name}' must not be empty")

    normalized: list[str] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(item)
            continue
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            normalized.append(item["path"])
            continue
        raise ConfigError(
            f"Each entry in '{field_name}' must be either a string or {{path: ...}}"
        )
    return normalized


def validate_post_checks(post_checks: Any, field_name: str) -> None:
    if post_checks is None:
        return

    checks = ensure_list(post_checks, field_name)
    supported = {
        "exists",
        "not_exists",
        "file_contains",
        "file_not_contains",
        "file_not_empty",
        "regex",
        "ordered_contains",
    }

    for index, check in enumerate(checks, start=1):
        entry_name = f"{field_name}[{index}]"
        if not isinstance(check, dict):
            raise ConfigError(f"{entry_name} must be a mapping")

        check_type = check.get("type")
        if not isinstance(check_type, str):
            raise ConfigError(f"{entry_name}.type must be a string")

        if check_type not in supported:
            raise ConfigError(
                f"{entry_name}.type unsupported: {check_type}. "
                f"Supported types: {', '.join(sorted(supported))}"
            )

        raw_path = check.get("path")
        if not isinstance(raw_path, str):
            raise ConfigError(f"{entry_name}.path must be a string")

        if check_type in {"file_contains", "file_not_contains"}:
            text = check.get("text")
            if not isinstance(text, str):
                raise ConfigError(f"{entry_name}.text must be a string")

        if check_type == "regex":
            pattern = check.get("pattern")
            if not isinstance(pattern, str):
                raise ConfigError(f"{entry_name}.pattern must be a string")

        if check_type == "ordered_contains":
            texts = check.get("texts")
            if not isinstance(texts, list) or not all(
                isinstance(item, str) for item in texts
            ):
                raise ConfigError(f"{entry_name}.texts must be a list of strings")


def validate_env_mapping(
    value: Any,
    field_name: str,
    *,
    allow_bool_values: bool = False,
) -> None:
    if not isinstance(value, dict):
        raise ConfigError(f"{field_name} must be a mapping")

    valid_value_types = (str, bool) if allow_bool_values else (str,)
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigError(f"{field_name} keys must be strings")
        if not isinstance(item, valid_value_types):
            raise ConfigError(
                f"{field_name}['{key}'] must be "
                f"{'string/bool' if allow_bool_values else 'a string'}"
            )


def validate_command_probe_list(value: Any, field_name: str) -> None:
    probes = ensure_list(value, field_name)
    for index, probe in enumerate(probes, start=1):
        entry_name = f"{field_name}[{index}]"
        if isinstance(probe, str):
            continue
        if not isinstance(probe, dict):
            raise ConfigError(f"{entry_name} must be a string or mapping")

        command = probe.get("command")
        if not isinstance(command, str):
            raise ConfigError(f"{entry_name}.command must be a string")

        args = probe.get("args")
        if args is not None and (
            not isinstance(args, list) or not all(isinstance(item, str) for item in args)
        ):
            raise ConfigError(f"{entry_name}.args must be a list of strings")

        shell_value = probe.get("shell")
        if shell_value is not None and not isinstance(shell_value, bool):
            raise ConfigError(f"{entry_name}.shell must be a boolean")

        timeout_sec = probe.get("timeout_sec")
        if timeout_sec is not None and (
            not isinstance(timeout_sec, int) or timeout_sec <= 0
        ):
            raise ConfigError(f"{entry_name}.timeout_sec must be a positive integer")

        cwd = probe.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ConfigError(f"{entry_name}.cwd must be a string")

        env = probe.get("env")
        if env is not None:
            validate_env_mapping(env, f"{entry_name}.env")


def validate_common_case_controls(case_def: dict[str, Any], field_name: str) -> None:
    skip_unless_env = case_def.get("skip_unless_env")
    if skip_unless_env is not None:
        validate_env_mapping(
            skip_unless_env,
            f"{field_name}.skip_unless_env",
            allow_bool_values=True,
        )

    skip_unless_paths_exist = case_def.get("skip_unless_paths_exist")
    if skip_unless_paths_exist is not None:
        ensure_string_or_list_of_strings(
            skip_unless_paths_exist,
            f"{field_name}.skip_unless_paths_exist",
        )

    skip_unless_commands_succeed = case_def.get("skip_unless_commands_succeed")
    if skip_unless_commands_succeed is not None:
        validate_command_probe_list(
            skip_unless_commands_succeed,
            f"{field_name}.skip_unless_commands_succeed",
        )

    requires_destructive = case_def.get("requires_destructive")
    if requires_destructive is not None and not isinstance(requires_destructive, bool):
        raise ConfigError(f"{field_name}.requires_destructive must be a boolean")

    required_env = case_def.get("required_env")
    if required_env is not None:
        validate_env_mapping(required_env, f"{field_name}.required_env")

    warn_only = case_def.get("warn_only")
    if warn_only is not None and not isinstance(warn_only, bool):
        raise ConfigError(f"{field_name}.warn_only must be a boolean")


def validate_mock_spec(spec: Any, field_name: str) -> None:
    """Validate one mocks.<target> spec conservatively."""
    if isinstance(spec, str):
        return

    if not isinstance(spec, dict):
        raise ConfigError(
            f"{field_name} must be a string or mapping, got {type(spec).__name__}"
        )

    if "factory" in spec and spec["factory"] is not None and not isinstance(
        spec["factory"], str
    ):
        raise ConfigError(f"{field_name}.factory must be a string when provided")

    if "inject_original_as" in spec and not isinstance(
        spec["inject_original_as"], str
    ):
        raise ConfigError(f"{field_name}.inject_original_as must be a string")

    if "args" in spec and spec["args"] is not None and not isinstance(spec["args"], list):
        raise ConfigError(f"{field_name}.args must be a list")

    if "kwargs" in spec and spec["kwargs"] is not None and not isinstance(
        spec["kwargs"], dict
    ):
        raise ConfigError(f"{field_name}.kwargs must be a mapping")

    if "attrs" in spec and spec["attrs"] is not None and not isinstance(
        spec["attrs"], dict
    ):
        raise ConfigError(f"{field_name}.attrs must be a mapping")


def validate_case_mocks(case_def: dict[str, Any], field_name: str) -> None:
    """Validate optional mocks/scenario fields."""
    mocks = case_def.get("mocks")
    if mocks is not None:
        if not isinstance(mocks, dict):
            raise ConfigError(f"{field_name}.mocks must be a mapping")
        for target, spec in mocks.items():
            if not isinstance(target, str) or not target.strip():
                raise ConfigError(f"{field_name}.mocks keys must be non-empty strings")
            validate_mock_spec(spec, f"{field_name}.mocks[{target!r}]")

    scenario = case_def.get("scenario")
    if scenario is not None and not isinstance(scenario, dict):
        raise ConfigError(f"{field_name}.scenario must be a mapping")


def validate_case_schema(case_def: dict[str, Any], field_name: str) -> None:
    case_name = case_def.get("name")
    if not isinstance(case_name, str) or not case_name.strip():
        raise ConfigError(f"{field_name}.name must be a non-empty string")

    case_type = case_def.get("type", "cli")
    if not isinstance(case_type, str):
        raise ConfigError(f"{field_name}.type must be a string")

    if case_type not in {
        "file_exists",
        "py_compile",
        "source_contains",
        "source_contains_any",
        "source_contains_all",
        "function_exists",
        "function_exists_any",
        "main_guard",
        "cli",
        "module_cli",
        "py_function",
        "module_main_with_env",
        "path_exists",
        "path_not_exists",
        "command_success",
        "command_exit_code",
        "command_output_contains",
        "command_output_regex",
    }:
        raise ConfigError(f"{field_name}.type unsupported: {case_type}")

    validate_common_case_controls(case_def, field_name)
    validate_case_mocks(case_def, field_name)

    if "scripts" in case_def and case_def["scripts"] is not None:
        scripts = case_def["scripts"]
        if not isinstance(scripts, dict):
            raise ConfigError(f"{field_name}.scripts must be a mapping")
        for key, value in scripts.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ConfigError(
                    f"{field_name}.scripts entries must be string -> string"
                )

    if "bin_files" in case_def and case_def["bin_files"] is not None:
        bin_files = case_def["bin_files"]
        if not isinstance(bin_files, dict):
            raise ConfigError(f"{field_name}.bin_files must be a mapping")
        for key, spec in bin_files.items():
            if not isinstance(key, str) or not isinstance(spec, dict):
                raise ConfigError(
                    f"{field_name}.bin_files entries must be string -> mapping"
                )
            hex_data = spec.get("hex")
            text_data = spec.get("text")
            if hex_data is None and text_data is None:
                raise ConfigError(
                    f"{field_name}.bin_files['{key}'] requires 'hex' or 'text'"
                )
            if hex_data is not None and not isinstance(hex_data, str):
                raise ConfigError(
                    f"{field_name}.bin_files['{key}'].hex must be a string"
                )
            if text_data is not None and not isinstance(text_data, str):
                raise ConfigError(
                    f"{field_name}.bin_files['{key}'].text must be a string"
                )

    if "text_files" in case_def and case_def["text_files"] is not None:
        text_files = case_def["text_files"]
        if not isinstance(text_files, dict):
            raise ConfigError(f"{field_name}.text_files must be a mapping")
        for key, value in text_files.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ConfigError(
                    f"{field_name}.text_files entries must be string -> string"
                )

    if "patch_constants" in case_def and case_def["patch_constants"] is not None:
        patch_constants = case_def["patch_constants"]
        if not isinstance(patch_constants, dict):
            raise ConfigError(f"{field_name}.patch_constants must be a mapping")
        for key, value in patch_constants.items():
            if not isinstance(key, str):
                raise ConfigError(
                    f"{field_name}.patch_constants keys must be strings"
                )
            if not isinstance(value, (str, int, float, bool)):
                raise ConfigError(
                    f"{field_name}.patch_constants['{key}'] "
                    "must be a scalar string/int/float/bool"
                )

    if "dir_structure" in case_def and case_def["dir_structure"] is not None:
        dir_structure = case_def["dir_structure"]
        if not isinstance(dir_structure, list):
            raise ConfigError(f"{field_name}.dir_structure must be a list")
        for index, entry in enumerate(dir_structure, start=1):
            if not isinstance(entry, dict):
                raise ConfigError(
                    f"{field_name}.dir_structure[{index}] must be a mapping"
                )
            if not isinstance(entry.get("path"), str):
                raise ConfigError(
                    f"{field_name}.dir_structure[{index}].path must be a string"
                )

    validate_post_checks(case_def.get("post_checks"), f"{field_name}.post_checks")

    if case_type == "py_function":
        function_name = case_def.get("function")
        if not isinstance(function_name, str) or not function_name.strip():
            raise ConfigError(f"{field_name}.function must be a non-empty string")

        args = case_def.get("args", [])
        if not isinstance(args, list):
            raise ConfigError(f"{field_name}.args must be a list")

        kwargs = case_def.get("kwargs")
        if kwargs is not None and not isinstance(kwargs, dict):
            raise ConfigError(f"{field_name}.kwargs must be a mapping")

        if "expect_exception" in case_def and not isinstance(
            case_def["expect_exception"], str
        ):
            raise ConfigError(f"{field_name}.expect_exception must be a string")

        if "expect_return_contains" in case_def and not isinstance(
            case_def["expect_return_contains"], str
        ):
            raise ConfigError(f"{field_name}.expect_return_contains must be a string")

        return

    if case_type == "module_main_with_env":
        expected_exit_code = case_def.get("expect_exit_code")
        if expected_exit_code is not None and not isinstance(expected_exit_code, int):
            raise ConfigError(f"{field_name}.expect_exit_code must be an integer")
        return

    if case_type in {"path_exists", "path_not_exists"}:
        path_value = case_def.get("path")
        if not isinstance(path_value, str):
            raise ConfigError(f"{field_name}.path must be a string")
        return

    if case_type in {
        "command_success",
        "command_exit_code",
        "command_output_contains",
        "command_output_regex",
    }:
        command = case_def.get("command")
        if not isinstance(command, str):
            raise ConfigError(f"{field_name}.command must be a string")

        args = case_def.get("args", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ConfigError(f"{field_name}.args must be a list of strings")

        shell_value = case_def.get("shell", False)
        if not isinstance(shell_value, bool):
            raise ConfigError(f"{field_name}.shell must be a boolean")

        timeout_sec = case_def.get("timeout_sec", DEFAULT_CLI_TIMEOUT_SEC)
        if not isinstance(timeout_sec, int) or timeout_sec <= 0:
            raise ConfigError(f"{field_name}.timeout_sec must be a positive integer")

        cwd = case_def.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ConfigError(f"{field_name}.cwd must be a string")

        env = case_def.get("env")
        if env is not None:
            validate_env_mapping(env, f"{field_name}.env")

        if case_type == "command_exit_code":
            expected_exit_code = case_def.get("expect_exit_code")
            if not isinstance(expected_exit_code, int):
                raise ConfigError(f"{field_name}.expect_exit_code must be an integer")

        if case_type == "command_output_contains":
            expect_text = case_def.get("expect_text")
            if not isinstance(expect_text, str):
                raise ConfigError(f"{field_name}.expect_text must be a string")

        if case_type == "command_output_regex":
            expect_pattern = case_def.get("expect_pattern")
            if not isinstance(expect_pattern, str):
                raise ConfigError(f"{field_name}.expect_pattern must be a string")
        return

    if case_type not in {"cli", "module_cli"}:
        return

    raw_args = case_def.get("args", [])
    if not isinstance(raw_args, list) or not all(
        isinstance(arg, str) for arg in raw_args
    ):
        raise ConfigError(f"{field_name}.args must be a list of strings")

    command = case_def.get("command")
    if command is not None and not isinstance(command, str):
        raise ConfigError(f"{field_name}.command must be a string")

    stdin_text = case_def.get("stdin")
    if stdin_text is not None and not isinstance(stdin_text, str):
        raise ConfigError(f"{field_name}.stdin must be a string")

    timeout_sec = case_def.get("timeout_sec", DEFAULT_CLI_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or timeout_sec <= 0:
        raise ConfigError(f"{field_name}.timeout_sec must be a positive integer")

    shell_value = case_def.get("shell", False)
    if not isinstance(shell_value, bool):
        raise ConfigError(f"{field_name}.shell must be a boolean")

    expect_timeout = case_def.get("expect_timeout", False)
    if not isinstance(expect_timeout, bool):
        raise ConfigError(f"{field_name}.expect_timeout must be a boolean")

    env = case_def.get("env")
    if env is not None:
        validate_env_mapping(env, f"{field_name}.env")

    expected_exit_code = case_def.get("expect_exit_code")
    if expected_exit_code is not None and not isinstance(expected_exit_code, int):
        raise ConfigError(f"{field_name}.expect_exit_code must be an integer")

    expect_exit_nonzero = case_def.get("expect_exit_nonzero", False)
    if not isinstance(expect_exit_nonzero, bool):
        raise ConfigError(f"{field_name}.expect_exit_nonzero must be a boolean")

    expect_exit_code_in = case_def.get("expect_exit_code_in")
    if expect_exit_code_in is not None:
        if not isinstance(expect_exit_code_in, list) or not all(
            isinstance(item, int) for item in expect_exit_code_in
        ):
            raise ConfigError(
                f"{field_name}.expect_exit_code_in must be a list of integers"
            )

    expect_stdout_or_stderr_regex = case_def.get("expect_stdout_or_stderr_regex")
    if expect_stdout_or_stderr_regex is not None:
        if isinstance(expect_stdout_or_stderr_regex, str):
            pass
        elif not isinstance(expect_stdout_or_stderr_regex, list) or not all(
            isinstance(item, str) for item in expect_stdout_or_stderr_regex
        ):
            raise ConfigError(
                f"{field_name}.expect_stdout_or_stderr_regex must be a string or list of strings"
            )


def normalize_cases(
    value: Any,
    field_name: str,
    defaults: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    items = ensure_list(value, field_name)
    normalized: list[dict[str, Any]] = []
    suite_defaults = defaults or {}

    for index, case_def in enumerate(items, start=1):
        if not isinstance(case_def, dict):
            raise ConfigError(f"{field_name}[{index}] must be a mapping")
        merged_case = merge_mappings(suite_defaults, case_def)
        # Let an explicit case-level non-zero/exit-code-set expectation override a
        # suite default like expect_exit_code: 0 that would otherwise leak in.
        if case_def.get("expect_exit_nonzero") and "expect_exit_code" not in case_def:
            merged_case.pop("expect_exit_code", None)
        if "expect_exit_code_in" in case_def and "expect_exit_code" not in case_def:
            merged_case.pop("expect_exit_code", None)
        validate_case_schema(merged_case, f"{field_name}[{index}]")
        normalized.append(merged_case)

    return normalized


def normalize_suites(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_suites = config.get("suites")
    if raw_suites is None:
        raise ConfigError("Top-level key 'suites' is required")

    suites = ensure_list(raw_suites, "suites")
    if not suites:
        raise ConfigError("'suites' must not be empty")

    normalized: list[dict[str, Any]] = []
    for index, suite in enumerate(suites, start=1):
        if not isinstance(suite, dict):
            raise ConfigError(f"suites[{index}] must be a mapping")

        name = suite.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"suites[{index}] requires a non-empty string 'name'")

        suite_command = suite.get("command")
        if suite_command is not None and not isinstance(suite_command, str):
            raise ConfigError(f"suites[{index}].command must be a string")

        defaults = suite.get("defaults") or {}
        if not isinstance(defaults, dict):
            raise ConfigError(f"suites[{index}].defaults must be a mapping")

        files = normalize_suite_files(suite.get("files"), f"suites[{index}].files")
        cases = normalize_cases(
            suite.get("cases", []),
            f"suites[{index}].cases",
            defaults=defaults,
        )

        normalized.append(
            {
                "name": name.strip(),
                "command": suite_command,
                "files": files,
                "cases": cases,
            }
        )

    return normalized


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
                f"post_check not_exists: {resolved} -> "
                f"{'PASS' if missing else 'FAIL'}"
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
                f"post_check file_not_empty: {resolved} -> "
                f"{'PASS' if passed else 'FAIL'}"
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


def build_command_from_spec(
    file_path: Path,
    spec: dict[str, Any],
    work_dir: Path,
) -> tuple[list[str] | str, bool]:
    raw_args = spec.get("args", [])
    if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
        raise ConfigError("'args' must be a list of strings")

    command_value = spec.get("command")
    if not isinstance(command_value, str):
        raise ConfigError("'command' must be a string")

    shell_mode = bool(spec.get("shell", False))
    expanded_command = expand_template(command_value, work_dir, file_path)
    expanded_args = [expand_template(arg, work_dir, file_path) for arg in raw_args]

    if shell_mode:
        parts = [expanded_command, *[shlex.quote(arg) for arg in expanded_args]]
        return " ".join(parts), True

    return [expanded_command, *expanded_args], False


def build_runtime_env(
    file_path: Path,
    env_spec: Any,
    work_dir: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    if env_spec is None:
        return env

    if not isinstance(env_spec, dict):
        raise ConfigError("'env' must be a mapping")

    for key, value in env_spec.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ConfigError("'env' entries must be string -> string")
        env[key] = expand_template(value, work_dir, file_path)

    return env


def execute_command_spec(
    file_path: Path,
    spec: dict[str, Any],
    work_dir: Path,
    stdin_text: str | None = None,
) -> CommandRunResult:
    timeout_sec = spec.get("timeout_sec", DEFAULT_CLI_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or timeout_sec <= 0:
        raise ConfigError("'timeout_sec' must be a positive integer")

    cmd, shell_mode = build_command_from_spec(file_path, spec, work_dir)
    run_env = build_runtime_env(file_path, spec.get("env"), work_dir)

    cwd_value = spec.get("cwd")
    if cwd_value is None:
        cwd = work_dir
    else:
        if not isinstance(cwd_value, str):
            raise ConfigError("'cwd' must be a string")
        cwd = Path(expand_template(cwd_value, work_dir, file_path))

    timed_out = False
    stdout = ""
    stderr = ""
    exit_code: int | None = None

    try:
        completed = REAL_SUBPROCESS_RUN(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            input=stdin_text,
            check=False,
            env=run_env,
            timeout=timeout_sec,
            shell=shell_mode,
        )
        stdout = normalize_completed_stream(completed.stdout)
        stderr = normalize_completed_stream(completed.stderr)
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = normalize_completed_stream(exc.stdout)
        stderr = normalize_completed_stream(exc.stderr)

    command_text = cmd if isinstance(cmd, str) else " ".join(cmd)
    return CommandRunResult(
        command_text=command_text,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        timeout_sec=timeout_sec,
        shell_mode=shell_mode,
    )


def normalize_probe_spec(probe: Any) -> dict[str, Any]:
    if isinstance(probe, str):
        return {
            "command": probe,
            "args": [],
            "shell": True,
            "timeout_sec": DEFAULT_CLI_TIMEOUT_SEC,
        }
    if isinstance(probe, dict):
        return dict(probe)
    raise ConfigError("Command probe must be a string or mapping")


def apply_skip_controls(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> None:
    skip_unless_env = case_def.get("skip_unless_env", {})
    if skip_unless_env:
        if not isinstance(skip_unless_env, dict):
            raise ConfigError("'skip_unless_env' must be a mapping")
        for key, expected in skip_unless_env.items():
            current = os.environ.get(key)
            if isinstance(expected, bool):
                present = bool(current)
                if present != expected:
                    raise SkipCase(
                        f"[HW WARNING] Env presence mismatch for {key!r}: "
                        f"got {present}, expected {expected}"
                    )
                continue
            if current != expected:
                raise SkipCase(
                    f"[HW WARNING] Env mismatch for {key!r}: "
                    f"got {current!r}, expected {expected!r}"
                )

    skip_unless_paths_exist = case_def.get("skip_unless_paths_exist", [])
    for raw_path in ensure_string_or_list_of_strings(
        skip_unless_paths_exist,
        "skip_unless_paths_exist",
    ):
        resolved = Path(expand_template(raw_path, work_dir, file_path))
        if not resolved.exists():
            raise SkipCase(f"[HW WARNING] Missing required path: {resolved}")

    skip_unless_commands_succeed = case_def.get("skip_unless_commands_succeed", [])
    probes = ensure_list(skip_unless_commands_succeed, "skip_unless_commands_succeed")
    for probe in probes:
        probe_spec = normalize_probe_spec(probe)
        result = execute_command_spec(file_path, probe_spec, work_dir)
        if result.timed_out:
            raise SkipCase(
                f"[HW WARNING] Probe command timed out after {result.timeout_sec}s: "
                f"{result.command_text}"
            )
        if result.exit_code != 0:
            raise SkipCase(
                f"[HW WARNING] Probe command failed with exit code "
                f"{result.exit_code}: {result.command_text}"
            )

    if case_def.get("requires_destructive", False):
        if os.environ.get(DESTRUCTIVE_TEST_ENV) != "1":
            raise SkipCase(
                f"[HW WARNING] Destructive test skipped. Set "
                f"{DESTRUCTIVE_TEST_ENV}=1 to enable."
            )

    required_env = case_def.get("required_env", {})
    if required_env:
        if not isinstance(required_env, dict):
            raise ConfigError("'required_env' must be a mapping")
        for key, expected in required_env.items():
            current = os.environ.get(key)
            if current != expected:
                raise ConfigError(
                    f"required_env mismatch for {key!r}: "
                    f"got {current!r}, expected {expected!r}"
                )


def check_file_exists(
    file_path: Path,
    _case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    exists = file_path.exists()
    message = "File exists" if exists else "File does not exist"
    return exists, message, "", False


def check_py_compile(
    file_path: Path,
    _case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True, "Python compilation succeeded", "", False
    except py_compile.PyCompileError as exc:
        return False, "Python compilation failed", str(exc), False


def check_source_contains(
    file_path: Path,
    case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    pattern = case_def.get("pattern")
    if not isinstance(pattern, str):
        raise ConfigError("'source_contains' requires a string 'pattern'")

    source = read_source(file_path)
    passed = pattern in source
    message = f"Found pattern: {pattern}" if passed else f"Pattern not found: {pattern}"
    return passed, message, "", False


def check_source_contains_any(
    file_path: Path,
    case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    patterns = ensure_list_of_strings(case_def.get("patterns"), "patterns")
    source = read_source(file_path)
    matched = [pattern for pattern in patterns if pattern in source]
    passed = bool(matched)
    details = "Matched patterns: " + ", ".join(matched) if matched else ""
    message = "At least one pattern matched" if passed else "No patterns matched"
    return passed, message, details, False


def check_source_contains_all(
    file_path: Path,
    case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    patterns = ensure_list_of_strings(case_def.get("patterns"), "patterns")
    source = read_source(file_path)
    missing = [pattern for pattern in patterns if pattern not in source]
    passed = not missing
    details = "Missing patterns: " + ", ".join(missing) if missing else ""
    message = "All patterns matched" if passed else "Some patterns were not found"
    return passed, message, details, False


def check_function_exists(
    file_path: Path,
    case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    function_name = case_def.get("function")
    if not isinstance(function_name, str):
        raise ConfigError("'function_exists' requires a string 'function'")

    names = collect_function_names(file_path)
    passed = function_name in names
    message = (
        f"Function found: {function_name}"
        if passed
        else f"Function not found: {function_name}"
    )
    return passed, message, "", False


def check_function_exists_any(
    file_path: Path,
    case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    functions = ensure_list_of_strings(case_def.get("functions"), "functions")
    names = collect_function_names(file_path)
    matched = [name for name in functions if name in names]
    passed = bool(matched)
    details = "Matched functions: " + ", ".join(matched) if matched else ""
    message = "At least one function matched" if passed else "No functions matched"
    return passed, message, details, False


def check_main_guard(
    file_path: Path,
    _case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    source = read_source(file_path)
    patterns = [
        'if __name__ == "__main__":',
        "if __name__ == '__main__':",
    ]
    passed = any(pattern in source for pattern in patterns)
    message = "Main guard found" if passed else "Main guard not found"
    return passed, message, "", False


def check_py_function(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    module = load_module_from_path(file_path)
    module_name = module.__name__
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    original_cwd = Path.cwd()
    original_env = os.environ.copy()

    try:
        details_lines: list[str] = [f"Work dir: {work_dir}"]
        function_name = case_def.get("function")
        if not isinstance(function_name, str):
            raise ConfigError("'py_function' requires a string 'function'")

        if not hasattr(module, function_name):
            return False, f"Function not found: {function_name}", "", False

        try:
            runtime_case = build_case_runtime_definition(
                case_def,
                work_dir,
                file_path,
                extra_tokens={"module": module.__name__},
            )
            details_lines.extend(materialize_case_workspace(work_dir, runtime_case))
        except (MockLoaderConfigError, ValueError, TypeError) as exc:
            raise ConfigError(str(exc)) from exc
        except CaseBuildError as exc:
            raise ConfigError(str(exc)) from exc

        func = getattr(module, function_name)
        args = runtime_case.get("args", [])
        kwargs = runtime_case.get("kwargs", {})
        run_env = build_cli_env(file_path, runtime_case, work_dir)

        if not isinstance(args, list):
            raise ConfigError("'py_function.args' must be a list")
        if not isinstance(kwargs, dict):
            raise ConfigError("'py_function.kwargs' must be a mapping")

        patch_constants = runtime_case.get("patch_constants", {})
        if patch_constants is not None:
            if not isinstance(patch_constants, dict):
                raise ConfigError("'py_function.patch_constants' must be a mapping")
            for attr_name, attr_value in patch_constants.items():
                setattr(module, attr_name, attr_value)

        expected_exception = runtime_case.get("expect_exception")

        passed = True
        message = ""
        is_error = False
        result: Any = None
        raised_exc: Exception | None = None

        try:
            os.chdir(work_dir)
            os.environ.clear()
            os.environ.update(run_env)
            with apply_case_mocks(
                runtime_case.get("mocks"),
                target_context={"module": module.__name__},
            ):
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    result = func(*args, **kwargs)
        except MockExpectationError as exc:
            raised_exc = exc
            details_lines.append(f"Mock verification failed: {exc}")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raised_exc = exc
            details_lines.append(traceback.format_exc())
        finally:
            os.chdir(original_cwd)
            os.environ.clear()
            os.environ.update(original_env)

        stdout = normalize_completed_stream(stdout_buffer.getvalue())
        stderr = normalize_completed_stream(stderr_buffer.getvalue())
        details_lines.extend(
            [
                "--- STDOUT ---",
                stdout.rstrip(),
                "--- STDERR ---",
                stderr.rstrip(),
            ]
        )

        if raised_exc is not None:
            if isinstance(raised_exc, MockExpectationError):
                passed = False
                message = f"Mock verification failed: {raised_exc}"
                is_error = True
            elif expected_exception:
                passed = raised_exc.__class__.__name__ == expected_exception
                message = (
                    f"Raised expected exception: {expected_exception}"
                    if passed
                    else (
                        f"Expected {expected_exception}, got "
                        f"{raised_exc.__class__.__name__}: {raised_exc}"
                    )
                )
                is_error = not passed
            else:
                passed = False
                message = f"Unexpected exception: {raised_exc}"
                is_error = True
        elif expected_exception:
            passed = False
            message = f"Expected exception {expected_exception}, but function returned"
            details_lines.append(repr(result))
        else:
            expected_return = runtime_case.get("expect_return")
            if "expect_return" in runtime_case and result != expected_return:
                passed = False
                message = f"Expected return {expected_return!r}, got {result!r}"

            expected_fragment = runtime_case.get("expect_return_contains")
            if expected_fragment is not None and expected_fragment not in str(result):
                passed = False
                message = f"Expected return to contain {expected_fragment!r}, got {result!r}"

            if passed:
                message = f"Function returned {result!r}"

        output_passed, output_conditions = validate_output_expectations(
            runtime_case,
            stdout,
            stderr,
        )
        post_passed, post_messages = run_post_checks(
            work_dir,
            runtime_case.get("post_checks"),
        )
        if post_messages:
            details_lines.extend(["--- POST CHECKS ---", *post_messages])

        conditions: list[str] = []
        if not passed and message:
            conditions.append(message)
        conditions.extend(output_conditions)
        conditions.extend(message for message in post_messages if "FAIL" in message)

        final_passed = passed and output_passed and post_passed
        final_message = (
            message
            if final_passed
            else "\n\n" + ("\n" + ("-" * 80) + "\n").join(conditions)
            if conditions
            else "Function check failed"
        )

        details = sanitize_xml_text("\n".join(details_lines).strip())
        return final_passed, sanitize_xml_text(final_message), details, is_error
    finally:
        sys.modules.pop(module_name, None)


def check_module_main_with_env(
    file_path: Path,
    case_def: dict[str, Any],
    _work_dir: Path,
) -> tuple[bool, str, str, bool]:
    temp_dir = create_runner_temp_dir()
    details_lines: list[str] = [f"Temp dir: {temp_dir}"]
    module: Any | None = None
    exit_code: int | None = None
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    original_cwd = Path.cwd()
    original_env = os.environ.copy()

    try:
        try:
            runtime_case = build_case_runtime_definition(
                case_def,
                temp_dir,
                file_path,
            )
            details_lines.extend(materialize_case_workspace(temp_dir, runtime_case))
        except (CaseBuildError, MockLoaderConfigError, ValueError, TypeError) as exc:
            return False, f"Configuration error: {exc}", "\n".join(details_lines), True

        run_env = build_cli_env(file_path, runtime_case, temp_dir)
        module = load_module_from_path(file_path)

        patch_constants = runtime_case.get("patch_constants", {})
        for attr_name, attr_value in patch_constants.items():
            setattr(module, attr_name, attr_value)
            details_lines.append(f"Patched constant: {attr_name}={attr_value!r}")

        try:
            os.chdir(temp_dir)
            os.environ.clear()
            os.environ.update(run_env)
            with apply_case_mocks(
                runtime_case.get("mocks"),
                target_context={"module": module.__name__},
            ):
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    main_result = module.main()
                    exit_code = main_result if isinstance(main_result, int) else 0
        except MockExpectationError as exc:
            stdout = normalize_completed_stream(stdout_buffer.getvalue())
            stderr = normalize_completed_stream(stderr_buffer.getvalue())
            details_lines.extend(
                [
                    f"Exit code: {exit_code}",
                    "--- STDOUT ---",
                    stdout.rstrip(),
                    "--- STDERR ---",
                    stderr.rstrip(),
                    f"Mock verification failed: {exc}",
                ]
            )
            append_log_file_details(details_lines, runtime_case)
            return (
                False,
                f"Mock verification failed: {exc}",
                sanitize_xml_text("\n".join(details_lines).strip()),
                False,
            )
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 0
        finally:
            os.chdir(original_cwd)
            os.environ.clear()
            os.environ.update(original_env)

        stdout = normalize_completed_stream(stdout_buffer.getvalue())
        stderr = normalize_completed_stream(stderr_buffer.getvalue())
        runtime_case["_actual_exit_code"] = exit_code
        details_lines.append(f"Exit code: {exit_code}")
        details_lines.extend(
            [
                "--- STDOUT ---",
                stdout.rstrip(),
                "--- STDERR ---",
                stderr.rstrip(),
            ]
        )

        output_passed, output_conditions = validate_output_expectations(
            runtime_case,
            stdout,
            stderr,
        )

        post_passed, post_messages = run_post_checks(
            temp_dir,
            runtime_case.get("post_checks"),
        )
        details_lines.extend(["--- POST CHECKS ---", *post_messages])

        conditions = [
            *output_conditions,
            *[message for message in post_messages if "FAIL" in message],
        ]
        if not output_passed or not post_passed:
            append_log_file_details(details_lines, runtime_case)
            return (
                False,
                "\n\n" + ("\n" + ("-" * 80) + "\n").join(conditions),
                sanitize_xml_text("\n".join(details_lines).strip()),
                False,
            )

        return (
            True,
            "Module main() check passed",
            sanitize_xml_text("\n".join(details_lines).strip()),
            False,
        )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        details_lines.append(traceback.format_exc())
        return (
            False,
            f"Unhandled exception: {exc}",
            sanitize_xml_text("\n".join(details_lines).strip()),
            not bool(case_def.get("warn_only", False)),
        )

    finally:
        if module is not None:
            sys.modules.pop(module.__name__, None)
        shutil.rmtree(temp_dir, ignore_errors=True)


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


def check_path_exists(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    raw_path = case_def.get("path")
    if not isinstance(raw_path, str):
        raise ConfigError("'path_exists' requires a string 'path'")
    resolved = Path(expand_template(raw_path, work_dir, file_path))
    passed = resolved.exists()
    message = f"Path exists: {resolved}" if passed else f"Path not found: {resolved}"
    return passed, message, "", False


def check_path_not_exists(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    raw_path = case_def.get("path")
    if not isinstance(raw_path, str):
        raise ConfigError("'path_not_exists' requires a string 'path'")
    resolved = Path(expand_template(raw_path, work_dir, file_path))
    passed = not resolved.exists()
    message = (
        f"Path correctly absent: {resolved}"
        if passed
        else f"Path unexpectedly exists: {resolved}"
    )
    return passed, message, "", False


def run_command_assertion(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[CommandRunResult, list[str], bool]:
    spec = {
        "command": case_def.get("command"),
        "args": case_def.get("args", []),
        "shell": case_def.get("shell", False),
        "timeout_sec": case_def.get("timeout_sec", DEFAULT_CLI_TIMEOUT_SEC),
        "cwd": case_def.get("cwd"),
        "env": case_def.get("env"),
    }
    result = execute_command_spec(file_path, spec, work_dir)
    details = [
        f"Command: {result.command_text}",
        f"Shell mode: {'yes' if result.shell_mode else 'no'}",
        f"Timeout seconds: {result.timeout_sec}",
        f"Timed out: {'yes' if result.timed_out else 'no'}",
        f"Exit code: {result.exit_code}",
        "--- STDOUT ---",
        result.stdout.rstrip(),
        "--- STDERR ---",
        result.stderr.rstrip(),
    ]
    return result, details, result.timed_out


def check_command_success(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    result, details, timed_out = run_command_assertion(file_path, case_def, work_dir)
    if timed_out:
        return (
            False,
            f"Command timed out after {result.timeout_sec}s",
            "\n".join(details),
            True,
        )
    passed = result.exit_code == 0
    message = (
        "Command succeeded"
        if passed
        else f"Expected exit code 0, got {result.exit_code}"
    )
    return passed, message, "\n".join(details), False


def check_command_exit_code(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    expected_exit_code = case_def.get("expect_exit_code")
    if not isinstance(expected_exit_code, int):
        raise ConfigError("'command_exit_code' requires integer 'expect_exit_code'")
    result, details, timed_out = run_command_assertion(file_path, case_def, work_dir)
    if timed_out:
        return (
            False,
            f"Command timed out after {result.timeout_sec}s",
            "\n".join(details),
            True,
        )
    passed = result.exit_code == expected_exit_code
    message = (
        f"Command exited with expected code {expected_exit_code}"
        if passed
        else f"Expected exit code {expected_exit_code}, got {result.exit_code}"
    )
    return passed, message, "\n".join(details), False


def check_command_output_contains(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    expect_text = case_def.get("expect_text")
    if not isinstance(expect_text, str):
        raise ConfigError("'command_output_contains' requires string 'expect_text'")
    result, details, timed_out = run_command_assertion(file_path, case_def, work_dir)
    if timed_out:
        return (
            False,
            f"Command timed out after {result.timeout_sec}s",
            "\n".join(details),
            True,
        )
    merged = result.stdout + "\n" + result.stderr
    passed = expect_text in merged
    message = (
        f"Command output contains {expect_text!r}"
        if passed
        else f"Command output missing {expect_text!r}"
    )
    return passed, message, "\n".join(details), False


def check_command_output_regex(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    expect_pattern = case_def.get("expect_pattern")
    if not isinstance(expect_pattern, str):
        raise ConfigError("'command_output_regex' requires string 'expect_pattern'")
    result, details, timed_out = run_command_assertion(file_path, case_def, work_dir)
    if timed_out:
        return (
            False,
            f"Command timed out after {result.timeout_sec}s",
            "\n".join(details),
            True,
        )
    merged = result.stdout + "\n" + result.stderr
    passed = re.search(expect_pattern, merged, flags=re.MULTILINE) is not None
    message = (
        f"Command output matches regex {expect_pattern!r}"
        if passed
        else f"Command output does not match regex {expect_pattern!r}"
    )
    return passed, message, "\n".join(details), False


def build_cli_command(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[list[str] | str, bool]:
    raw_args = case_def.get("args", [])
    command_override = case_def.get("command")
    shell_mode = bool(case_def.get("shell", False))

    expanded_args = [expand_template(arg, work_dir, file_path) for arg in raw_args]

    if command_override:
        command_value = expand_template(command_override, work_dir, file_path)
        if shell_mode:
            parts = [command_value, *[shlex.quote(arg) for arg in expanded_args]]
            return " ".join(parts), True
        return [command_value, *expanded_args], False

    base_cmd = [sys.executable, str(file_path), *expanded_args]
    if shell_mode:
        return " ".join(shlex.quote(part) for part in base_cmd), True
    return base_cmd, False


def build_cli_env(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    raw_env = case_def.get("env")
    if raw_env is None:
        return env

    if not isinstance(raw_env, dict):
        raise ConfigError("'env' must be a mapping")

    for key, value in raw_env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ConfigError("'env' entries must be string -> string")
        env[key] = expand_template(value, work_dir, file_path)

    return env


def check_cli(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    try:
        runtime_case = build_case_runtime_definition(
            case_def,
            work_dir,
            file_path,
        )
        prepare_case_files(work_dir, runtime_case)
    except (CaseBuildError, MockLoaderConfigError, ValueError, TypeError) as exc:
        raise ConfigError(str(exc)) from exc

    stdin_text = runtime_case.get("stdin")
    if stdin_text is not None and not isinstance(stdin_text, str):
        raise ConfigError("'stdin' must be a string")

    timeout_sec = runtime_case.get("timeout_sec", DEFAULT_CLI_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or timeout_sec <= 0:
        raise ConfigError("'timeout_sec' must be a positive integer")

    expect_timeout = bool(runtime_case.get("expect_timeout", False))
    cmd, shell_mode = build_cli_command(file_path, runtime_case, work_dir)
    run_env = build_cli_env(file_path, runtime_case, work_dir)

    timed_out = False
    stdout = ""
    stderr = ""
    exit_code: int | None = None

    try:
        completed = REAL_SUBPROCESS_RUN(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            input=stdin_text,
            check=False,
            env=run_env,
            timeout=timeout_sec,
            shell=shell_mode,
        )
        stdout = normalize_completed_stream(completed.stdout)
        stderr = normalize_completed_stream(completed.stderr)
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = normalize_completed_stream(exc.stdout)
        stderr = normalize_completed_stream(exc.stderr)

    runtime_case["_actual_exit_code"] = exit_code

    conditions: list[str] = []
    output_passed = True

    if timed_out:
        if expect_timeout:
            output_passed = True
        else:
            output_passed = False
            conditions.append(f"CLI command timed out after {timeout_sec}s")
    else:
        if expect_timeout:
            output_passed = False
            conditions.append("Expected command to time out, but it completed")
        else:
            output_passed, output_conditions = validate_output_expectations(
                runtime_case,
                stdout,
                stderr,
            )
            conditions.extend(output_conditions)

    post_passed, post_messages = run_post_checks(
        work_dir,
        runtime_case.get("post_checks"),
    )
    conditions.extend(message for message in post_messages if "FAIL" in message)

    passed = output_passed and post_passed and not conditions

    command_text = cmd if isinstance(cmd, str) else " ".join(cmd)
    details_lines = [
        f"Command: {command_text}",
        f"Shell mode: {'yes' if shell_mode else 'no'}",
        f"Timeout seconds: {timeout_sec}",
        f"Timed out: {'yes' if timed_out else 'no'}",
        f"Exit code: {exit_code}",
        "--- STDOUT ---",
        stdout.rstrip(),
        "--- STDERR ---",
        stderr.rstrip(),
    ]

    if post_messages:
        details_lines.extend(["--- POST CHECKS ---", *post_messages])

    message = (
        "CLI check passed"
        if passed
        else "\n\n" + ("\n" + ("-" * 80) + "\n").join(conditions)
    )
    message = sanitize_xml_text(message)
    details = sanitize_xml_text("\n".join(details_lines).strip())

    is_error = timed_out and not expect_timeout
    return passed, message, details, is_error


def check_module_cli(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    details_lines: list[str] = [f"Work dir: {work_dir}"]

    try:
        runtime_case = build_case_runtime_definition(
            case_def,
            work_dir,
            file_path,
        )
        details_lines.extend(materialize_case_workspace(work_dir, runtime_case))
    except (CaseBuildError, MockLoaderConfigError, ValueError, TypeError) as exc:
        raise ConfigError(str(exc)) from exc

    stdin_text = runtime_case.get("stdin")
    if stdin_text is not None and not isinstance(stdin_text, str):
        raise ConfigError("'stdin' must be a string")

    raw_args = runtime_case.get("args", [])
    if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
        raise ConfigError("'args' must be a list of strings")

    run_env = build_cli_env(file_path, runtime_case, work_dir)
    patch_constants = runtime_case.get("patch_constants", {})
    if not isinstance(patch_constants, dict):
        raise ConfigError("'patch_constants' must be a mapping")

    command_text = " ".join(
        [shlex.quote(str(file_path)), *(shlex.quote(arg) for arg in raw_args)]
    )
    details_lines.append(f"Command: python {command_text}")

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    original_argv = sys.argv[:]
    original_stdin = sys.stdin
    original_cwd = Path.cwd()
    original_main = sys.modules.get("__main__")
    original_env = os.environ.copy()
    exit_code = 0
    spec = importlib.util.spec_from_file_location("__main__", str(file_path))
    if spec is None or spec.loader is None:
        raise ConfigError(f"Could not load module from {file_path}")
    script_module = importlib.util.module_from_spec(spec)

    for attr_name, attr_value in patch_constants.items():
        setattr(script_module, attr_name, attr_value)
        details_lines.append(f"Patched constant: {attr_name}={attr_value!r}")

    try:
        sys.argv = [str(file_path), *raw_args]
        if stdin_text is not None:
            sys.stdin = io.StringIO(stdin_text)
        os.chdir(work_dir)
        os.environ.clear()
        os.environ.update(run_env)
        sys.modules["__main__"] = script_module

        try:
            with apply_case_mocks(
                runtime_case.get("mocks"),
                target_context={"module": "__main__"},
            ):
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    spec.loader.exec_module(script_module)
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 0
        except MockExpectationError as exc:
            stdout = normalize_completed_stream(stdout_buffer.getvalue())
            stderr = normalize_completed_stream(stderr_buffer.getvalue())
            details_lines.extend(
                [
                    f"Exit code: {exit_code}",
                    "--- STDOUT ---",
                    stdout.rstrip(),
                    "--- STDERR ---",
                    stderr.rstrip(),
                ]
            )
            return (
                False,
                f"Mock verification failed: {exc}",
                "\n".join(details_lines),
                False,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            stdout = normalize_completed_stream(stdout_buffer.getvalue())
            stderr = normalize_completed_stream(stderr_buffer.getvalue())
            details_lines.extend(
                [
                    f"Exit code: {exit_code}",
                    "--- STDOUT ---",
                    stdout.rstrip(),
                    "--- STDERR ---",
                    stderr.rstrip(),
                    traceback.format_exc(),
                ]
            )
            return (
                False,
                f"Unhandled exception: {exc}",
                "\n".join(details_lines),
                not bool(case_def.get("warn_only", False)),
            )
    finally:
        sys.argv = original_argv
        sys.stdin = original_stdin
        os.chdir(original_cwd)
        os.environ.clear()
        os.environ.update(original_env)
        if original_main is None:
            sys.modules.pop("__main__", None)
        else:
            sys.modules["__main__"] = original_main

    stdout = normalize_completed_stream(stdout_buffer.getvalue())
    stderr = normalize_completed_stream(stderr_buffer.getvalue())
    runtime_case["_actual_exit_code"] = exit_code

    output_passed, output_conditions = validate_output_expectations(
        runtime_case,
        stdout,
        stderr,
    )
    post_passed, post_messages = run_post_checks(
        work_dir,
        runtime_case.get("post_checks"),
    )
    conditions = [*output_conditions, *[msg for msg in post_messages if "FAIL" in msg]]

    passed = output_passed and post_passed and not conditions
    details_lines.extend(
        [
            f"Exit code: {exit_code}",
            "--- STDOUT ---",
            stdout.rstrip(),
            "--- STDERR ---",
            stderr.rstrip(),
        ]
    )
    if post_messages:
        details_lines.extend(["--- POST CHECKS ---", *post_messages])

    message = (
        "Module CLI check passed"
        if passed
        else "\n\n" + ("\n" + ("-" * 80) + "\n").join(conditions)
    )
    message = sanitize_xml_text(message)
    details = sanitize_xml_text("\n".join(details_lines).strip())
    return passed, message, details, False

CHECK_HANDLERS: dict[
    str,
    Callable[[Path, dict[str, Any], Path], tuple[bool, str, str, bool]],
] = {
    "file_exists": check_file_exists,
    "py_compile": check_py_compile,
    "source_contains": check_source_contains,
    "source_contains_any": check_source_contains_any,
    "source_contains_all": check_source_contains_all,
    "function_exists": check_function_exists,
    "function_exists_any": check_function_exists_any,
    "main_guard": check_main_guard,
    "cli": check_cli,
    "module_cli": check_module_cli,
    "py_function": check_py_function,
    "module_main_with_env": check_module_main_with_env,
    "path_exists": check_path_exists,
    "path_not_exists": check_path_not_exists,
    "command_success": check_command_success,
    "command_exit_code": check_command_exit_code,
    "command_output_contains": check_command_output_contains,
    "command_output_regex": check_command_output_regex,
}


def run_single_check(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    case_type = case_def.get("type", "cli")
    if not isinstance(case_type, str):
        raise ConfigError("Case 'type' must be a string")

    apply_skip_controls(file_path, case_def, work_dir)

    handler = CHECK_HANDLERS.get(case_type)
    if handler is None:
        raise ConfigError(f"Unsupported test type: {case_type}")

    return handler(file_path, case_def, work_dir)
