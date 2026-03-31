from __future__ import annotations

import ast
import os
import py_compile
import shlex
import subprocess
import sys
import traceback
import xml.etree.ElementTree as xml_et
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml


PROJECT_ROOT = Path.cwd().resolve()
TEST_YAML_DIR = PROJECT_ROOT / "test_yaml"
REPORTS_DIR = PROJECT_ROOT / "reports"
PLACEHOLDER_XML = REPORTS_DIR / "pytest-placeholder.xml"
SUPPORTED_SUFFIXES = {".yaml", ".yml"}
DEFAULT_CLI_TIMEOUT_SEC = 20


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
        }
    )

    @property
    def error(self) -> bool:
        return self.flags["error"]

    @property
    def skipped(self) -> bool:
        return self.flags["skipped"]


class ConfigError(Exception):
    """Raised when a YAML configuration is invalid."""


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


def build_report_path(group_name: str, yaml_file: Path) -> Path:
    safe_group = sanitize_name(group_name)
    safe_yaml = sanitize_name(yaml_file.stem)
    return REPORTS_DIR / f"{safe_group}__{safe_yaml}.xml"


def create_placeholder_xml(reason: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    testsuite = xml_et.Element("testsuite")
    testsuite.set("name", sanitize_xml_text("pytest"))
    testsuite.set("tests", "0")
    testsuite.set("failures", "0")
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    properties = xml_et.SubElement(testsuite, "properties")

    reason_prop = xml_et.SubElement(properties, "property")
    reason_prop.set("name", "reason")
    reason_prop.set("value", sanitize_xml_text(reason))

    placeholder_prop = xml_et.SubElement(properties, "property")
    placeholder_prop.set("name", "placeholder")
    placeholder_prop.set("value", "true")

    system_out = xml_et.SubElement(testsuite, "system-out")
    system_out.text = sanitize_xml_text(reason)

    xml_et.ElementTree(testsuite).write(
        PLACEHOLDER_XML,
        encoding="utf-8",
        xml_declaration=True,
    )


def remove_placeholder_xml() -> None:
    if PLACEHOLDER_XML.exists():
        PLACEHOLDER_XML.unlink()


def cleanup_old_pytest_xml_reports() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for xml_file in REPORTS_DIR.glob("*.xml"):
        if xml_file.name == "pylint-report.xml":
            continue
        xml_file.unlink(missing_ok=True)


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
    }:
        raise ConfigError(f"{field_name}.type unsupported: {case_type}")

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
            if not isinstance(hex_data, str):
                raise ConfigError(
                    f"{field_name}.bin_files['{key}'].hex must be a string"
                )

    validate_post_checks(case_def.get("post_checks"), f"{field_name}.post_checks")

    if case_type != "cli":
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
        if not isinstance(env, dict):
            raise ConfigError(f"{field_name}.env must be a mapping")
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ConfigError(f"{field_name}.env entries must be string -> string")

    expected_exit_code = case_def.get("expect_exit_code")
    if expected_exit_code is not None and not isinstance(expected_exit_code, int):
        raise ConfigError(f"{field_name}.expect_exit_code must be an integer")

    expect_exit_nonzero = case_def.get("expect_exit_nonzero", False)
    if not isinstance(expect_exit_nonzero, bool):
        raise ConfigError(f"{field_name}.expect_exit_nonzero must be a boolean")


def normalize_cases(value: Any, field_name: str) -> list[dict[str, Any]]:
    items = ensure_list(value, field_name)
    normalized: list[dict[str, Any]] = []

    for index, case_def in enumerate(items, start=1):
        if not isinstance(case_def, dict):
            raise ConfigError(f"{field_name}[{index}] must be a mapping")
        validate_case_schema(case_def, f"{field_name}[{index}]")
        normalized.append(case_def)

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

        files = normalize_suite_files(suite.get("files"), f"suites[{index}].files")
        cases = normalize_cases(suite.get("cases", []), f"suites[{index}].cases")

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
        },
    )


def expand_template(value: str, work_dir: Path, file_path: Path) -> str:
    return value.format(dir=str(work_dir), file=str(file_path), filename=file_path.name)


def prepare_case_files(work_dir: Path, case_def: dict[str, Any]) -> None:
    scripts = case_def.get("scripts", {})
    if scripts is not None:
        if not isinstance(scripts, dict):
            raise ConfigError("'scripts' must be a mapping")
        for name, content in scripts.items():
            if not isinstance(name, str) or not isinstance(content, str):
                raise ConfigError("'scripts' entries must be string -> string")
            script_path = work_dir / name
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(content, encoding="utf-8")
            script_path.chmod(0o755)

    bin_files = case_def.get("bin_files", {})
    if bin_files is not None:
        if not isinstance(bin_files, dict):
            raise ConfigError("'bin_files' must be a mapping")
        for name, spec in bin_files.items():
            if not isinstance(name, str) or not isinstance(spec, dict):
                raise ConfigError("'bin_files' entries must be string -> mapping")
            hex_data = spec.get("hex")
            if not isinstance(hex_data, str):
                raise ConfigError("Each 'bin_files' entry requires string key 'hex'")
            target_file = work_dir / name
            target_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                target_file.write_bytes(bytes.fromhex(hex_data))
            except ValueError as exc:
                raise ConfigError(
                    f"Invalid hex data for bin_files entry '{name}': {exc}"
                ) from exc


def render_post_check_path(raw_path: str, work_dir: Path) -> Path:
    return Path(raw_path.format(dir=str(work_dir)))


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

        raise ConfigError(f"post_checks[{index}] unsupported type: {check_type}")

    return all_passed, messages


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

    if case_def.get("_actual_exit_code") is not None:
        actual_exit_code = case_def["_actual_exit_code"]
        if expected_exit_code is not None:
            if actual_exit_code != expected_exit_code:
                passed = False
                conditions.append(
                    f"Expected exit code {expected_exit_code}, got {actual_exit_code}"
                )
        elif expect_exit_nonzero and actual_exit_code == 0:
            passed = False
            conditions.append("Expected a non-zero exit code")

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
                conditions.append(f"output missing text: {candidate}")

    stdout_contains = case_def.get("expect_stdout_contains")
    if stdout_contains is not None:
        if not isinstance(stdout_contains, str):
            raise ConfigError("'expect_stdout_contains' must be a string")
        if stdout_contains not in stdout:
            passed = False
            conditions.append(f"stdout missing text: {stdout_contains}")

    stderr_contains = case_def.get("expect_stderr_contains")
    if stderr_contains is not None:
        if not isinstance(stderr_contains, str):
            raise ConfigError("'expect_stderr_contains' must be a string")
        if stderr_contains not in stderr:
            passed = False
            conditions.append(f"stderr missing text: {stderr_contains}")

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
                conditions.append(f"stdout/stderr missing text: {candidate}")

    return passed, conditions


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


def normalize_completed_stream(stream: Any) -> str:
    if stream is None:
        return ""
    if isinstance(stream, str):
        return stream
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return str(stream)


def check_cli(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    prepare_case_files(work_dir, case_def)

    stdin_text = case_def.get("stdin")
    if stdin_text is not None and not isinstance(stdin_text, str):
        raise ConfigError("'stdin' must be a string")

    timeout_sec = case_def.get("timeout_sec", DEFAULT_CLI_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or timeout_sec <= 0:
        raise ConfigError("'timeout_sec' must be a positive integer")

    expect_timeout = bool(case_def.get("expect_timeout", False))
    cmd, shell_mode = build_cli_command(file_path, case_def, work_dir)
    run_env = build_cli_env(file_path, case_def, work_dir)

    timed_out = False
    stdout = ""
    stderr = ""
    exit_code: int | None = None

    try:
        completed = subprocess.run(
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

    case_def["_actual_exit_code"] = exit_code

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
                case_def, stdout, stderr
            )
            conditions.extend(output_conditions)

    post_passed, post_messages = run_post_checks(work_dir, case_def.get("post_checks"))
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

    message = "CLI check passed" if passed else "; ".join(conditions)
    message = sanitize_xml_text(message)
    details = sanitize_xml_text("\n".join(details_lines).strip())

    is_error = timed_out and not expect_timeout
    return passed, message, details, is_error


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
}


def run_single_check(
    file_path: Path,
    case_def: dict[str, Any],
    work_dir: Path,
) -> tuple[bool, str, str, bool]:
    case_type = case_def.get("type", "cli")
    if not isinstance(case_type, str):
        raise ConfigError("Case 'type' must be a string")

    handler = CHECK_HANDLERS.get(case_type)
    if handler is None:
        raise ConfigError(f"Unsupported test type: {case_type}")

    return handler(file_path, case_def, work_dir)


def run_case(
    suite_name: str,
    file_entry: str,
    case_index: int,
    case_def: dict[str, Any],
    suite_command: str | None = None,
) -> TestOutcome:
    file_path = resolve_target_path(file_entry)
    case_name = case_def["name"].strip()
    testcase_name = f"{suite_name}::{Path(file_entry).name}::{case_name}"
    case_type = str(case_def.get("type", "cli"))

    work_dir = (
        REPORTS_DIR
        / "_work"
        / sanitize_name(suite_name)
        / sanitize_name(Path(file_entry).stem)
        / sanitize_name(f"{case_index}_{case_name}")
    )
    work_dir.mkdir(parents=True, exist_ok=True)

    effective_case = dict(case_def)
    if suite_command is not None and "command" not in effective_case:
        effective_case["command"] = suite_command

    meta = TestMeta(
        suite_name=suite_name,
        phase="case",
        test_type=case_type,
    )

    try:
        passed, message, details, is_error = run_single_check(
            file_path, effective_case, work_dir
        )
        return create_outcome(
            testcase_name=testcase_name,
            file_path=file_entry,
            passed=passed,
            message=sanitize_xml_text(message),
            meta=meta,
            details=sanitize_xml_text(details),
            error=is_error,
        )
    except ConfigError as exc:
        return create_outcome(
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
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return create_outcome(
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


def write_junit_xml(
    xml_report: Path,
    suite_name: str,
    yaml_file: Path,
    outcomes: list[TestOutcome],
) -> None:
    tests = len(outcomes)
    failures = sum(
        1 for item in outcomes if not item.passed and not item.error and not item.skipped
    )
    errors = sum(1 for item in outcomes if item.error)
    skipped = sum(1 for item in outcomes if item.skipped)
    passed = sum(1 for item in outcomes if item.passed)

    testsuite = xml_et.Element("testsuite")
    testsuite.set("name", sanitize_xml_text(suite_name))
    testsuite.set("tests", str(tests))
    testsuite.set("failures", str(failures))
    testsuite.set("errors", str(errors))
    testsuite.set("skipped", str(skipped))

    properties = xml_et.SubElement(testsuite, "properties")

    yaml_prop = xml_et.SubElement(properties, "property")
    yaml_prop.set("name", "yaml_file")
    yaml_prop.set(
        "value",
        sanitize_xml_text(yaml_file.relative_to(PROJECT_ROOT).as_posix()),
    )

    passed_prop = xml_et.SubElement(properties, "property")
    passed_prop.set("name", "passed")
    passed_prop.set("value", sanitize_xml_text(str(passed)))

    for outcome in outcomes:
        testcase = xml_et.SubElement(testsuite, "testcase")
        testcase.set(
            "classname",
            sanitize_xml_text(sanitize_name(outcome.file_path or suite_name)),
        )
        testcase.set("name", sanitize_xml_text(outcome.testcase_name))
        testcase.set("file", sanitize_xml_text(outcome.file_path))

        if outcome.skipped:
            skipped_node = xml_et.SubElement(testcase, "skipped")
            skipped_node.set("message", sanitize_xml_text(outcome.message))
            skipped_node.text = sanitize_xml_text(outcome.details)
        elif not outcome.passed and outcome.error:
            error_node = xml_et.SubElement(testcase, "error")
            error_node.set("message", sanitize_xml_text(outcome.message))
            error_node.text = sanitize_xml_text(outcome.details)
        elif not outcome.passed:
            failure_node = xml_et.SubElement(testcase, "failure")
            failure_node.set("message", sanitize_xml_text(outcome.message))
            failure_node.text = sanitize_xml_text(outcome.details)

        system_out = xml_et.SubElement(testcase, "system-out")
        body = [
            f"file={outcome.file_path}",
            f"suite={outcome.meta.suite_name}",
            f"phase={outcome.meta.phase}",
            f"type={outcome.meta.test_type}",
            f"message={outcome.message}",
        ]
        if outcome.details:
            body.extend(["details:", outcome.details])

        system_out.text = sanitize_xml_text("\n".join(body))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    xml_et.ElementTree(testsuite).write(
        xml_report,
        encoding="utf-8",
        xml_declaration=True,
    )


def print_group_summary(
    suite_name: str,
    outcomes: list[TestOutcome],
    xml_report: Path,
) -> None:
    total = len(outcomes)
    passed = sum(1 for item in outcomes if item.passed)
    failures = sum(
        1 for item in outcomes if not item.passed and not item.error and not item.skipped
    )
    errors = sum(1 for item in outcomes if item.error)
    skipped = sum(1 for item in outcomes if item.skipped)

    print(f"\n[INFO] Finished group    : {suite_name}")
    print(
        f"[INFO] XML report        : "
        f"{xml_report.relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(f"[INFO] Total             : {total}")
    print(f"[INFO] Passed            : {passed}")
    print(f"[INFO] Failed            : {failures}")
    print(f"[INFO] Errors            : {errors}")
    print(f"[INFO] Skipped           : {skipped}")

    failed_items = [item for item in outcomes if not item.passed]
    if failed_items:
        print("[INFO] Failed checks:")
        for item in failed_items:
            kind = "ERROR" if item.error else "FAIL"
            print(
                f"  - [{kind}] {item.file_path} :: "
                f"{item.testcase_name} :: {item.message}"
            )


def build_config_error_outcome(
    yaml_file: Path,
    message: str,
    details: str,
) -> TestOutcome:
    return create_outcome(
        testcase_name="config::load_yaml",
        file_path=yaml_file.relative_to(PROJECT_ROOT).as_posix(),
        passed=False,
        message=sanitize_xml_text(message),
        meta=TestMeta(
            suite_name="config",
            phase="config",
            test_type="config",
        ),
        details=sanitize_xml_text(details),
        error=True,
    )


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


def get_yaml_target_entries(yaml_file: Path) -> set[str]:
    try:
        config = load_yaml_config(yaml_file)
        suites = normalize_suites(config)
    except ConfigError:
        return set()

    targets: set[str] = set()
    for suite in suites:
        for file_entry in suite["files"]:
            targets.add(Path(file_entry).as_posix())
    return targets


def yaml_targets_changed_files(yaml_file: Path, changed_paths: set[Path]) -> set[str]:
    try:
        config = load_yaml_config(yaml_file)
        suites = normalize_suites(config)
    except ConfigError:
        return set()

    matched: set[str] = set()
    for suite in suites:
        for file_entry in suite["files"]:
            target_path = normalize_target_for_matching(file_entry)
            if target_path in changed_paths:
                matched.add(Path(file_entry).as_posix())
    return matched


def select_yaml_runs(yaml_files: list[Path]) -> list[tuple[Path, set[str]]]:
    changed_paths = get_recently_changed_paths()

    if not changed_paths:
        return []

    selected_map: dict[Path, set[str]] = {}

    for yaml_file in yaml_files:
        yaml_abs = yaml_file.resolve()
        matched_targets = yaml_targets_changed_files(yaml_file, changed_paths)

        if yaml_abs in changed_paths:
            matched_targets.update(get_yaml_target_entries(yaml_file))

        if matched_targets:
            selected_map[yaml_file] = matched_targets

    return list(selected_map.items())


def run_yaml(yaml_file: Path, selected_targets: set[str]) -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    group_name = get_group_name(yaml_file)
    xml_report = build_report_path(group_name, yaml_file)

    print(f"\n[INFO] Running group      : {group_name}")
    print(
        f"[INFO] YAML file         : "
        f"{yaml_file.relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(
        f"[INFO] XML report        : "
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
        suite_command = suite.get("command")
        suite_files = suite["files"]
        suite_cases = suite["cases"]

        filtered_files = []
        for file_entry in suite_files:
            normalized_file_entry = Path(file_entry).as_posix()
            if normalized_file_entry in selected_targets:
                filtered_files.append(file_entry)

        if not filtered_files:
            continue

        print(f"[INFO] Suite             : {suite_name}")

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
            print(f"[INFO] Target file       : {file_entry}")
            for case_index, case_def in enumerate(suite_cases, start=1):
                outcomes.append(
                    run_case(
                        suite_name=suite_name,
                        file_entry=file_entry,
                        case_index=case_index,
                        case_def=case_def,
                        suite_command=suite_command,
                    )
                )

    if not outcomes:
        return 0

    write_junit_xml(xml_report, group_name, yaml_file, outcomes)
    print_group_summary(group_name, outcomes, xml_report)
    return 0 if all(item.passed for item in outcomes) else 1


def main() -> int:
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

    selected_runs = select_yaml_runs(yaml_files)

    if not selected_runs:
        print("[INFO] No impacted YAML test groups found for changed files.")
        print(
            f"[INFO] Reports written to: "
            f"{REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}"
        )
        create_placeholder_xml("No impacted YAML test groups found for changed files")
        return 0

    print("[INFO] Running only impacted YAML test groups:")
    for yaml_file, selected_targets in selected_runs:
        print(f"  - {yaml_file.relative_to(PROJECT_ROOT).as_posix()}")
        for target in sorted(selected_targets):
            print(f"      * target: {target}")

    overall_exit_code = 0
    for yaml_file, selected_targets in selected_runs:
        exit_code = run_yaml(yaml_file, selected_targets=selected_targets)
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
