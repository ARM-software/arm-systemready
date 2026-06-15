from __future__ import annotations

import importlib.util
import io
import os
import py_compile
import re
import shlex
import shutil
import subprocess
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

try:  # Support package imports and direct harness module loading.
    from .case_data_builders import (
        CaseBuildError,
        expand_template,
        materialize_case_workspace,
        prepare_case_files,
    )
    from .mock_helpers import MockExpectationError
    from .mock_loader import ConfigError as MockLoaderConfigError
    from .mock_loader import apply_case_mocks, build_case_runtime_definition
    from .runner_checks import (
        DEFAULT_CLI_TIMEOUT_SEC,
        DESTRUCTIVE_TEST_ENV,
        REAL_SUBPROCESS_RUN,
        CommandRunResult,
        ConfigError,
        SkipCase,
        collect_function_names,
        create_runner_temp_dir,
        ensure_list,
        ensure_list_of_strings,
        ensure_string_or_list_of_strings,
        load_module_from_path,
        normalize_completed_stream,
        read_source,
        sanitize_xml_text,
    )
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from case_data_builders import (
        CaseBuildError,
        expand_template,
        materialize_case_workspace,
        prepare_case_files,
    )
    from mock_helpers import MockExpectationError
    from mock_loader import ConfigError as MockLoaderConfigError
    from mock_loader import apply_case_mocks, build_case_runtime_definition
    from runner_checks import (
        DEFAULT_CLI_TIMEOUT_SEC,
        DESTRUCTIVE_TEST_ENV,
        REAL_SUBPROCESS_RUN,
        CommandRunResult,
        ConfigError,
        SkipCase,
        collect_function_names,
        create_runner_temp_dir,
        ensure_list,
        ensure_list_of_strings,
        ensure_string_or_list_of_strings,
        load_module_from_path,
        normalize_completed_stream,
        read_source,
        sanitize_xml_text,
    )


def append_log_file_details(
    details_lines: list[str],
    runtime_case: dict[str, Any],
) -> None:
    try:  # Support package imports and direct harness module loading.
        from .runner_checks import append_log_file_details as shared_append_log_file_details
    except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
        from runner_checks import append_log_file_details as shared_append_log_file_details

    shared_append_log_file_details(details_lines, runtime_case)


def run_post_checks(work_dir: Path, post_checks: Any) -> tuple[bool, list[str]]:
    try:  # Support package imports and direct harness module loading.
        from .runner_checks import run_post_checks as shared_run_post_checks
    except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
        from runner_checks import run_post_checks as shared_run_post_checks

    return shared_run_post_checks(work_dir, post_checks)


def validate_output_expectations(
    case_def: dict[str, Any],
    stdout: str,
    stderr: str,
) -> tuple[bool, list[str]]:
    try:  # Support package imports and direct harness module loading.
        from .runner_checks import (
            validate_output_expectations as shared_validate_output_expectations,
        )
    except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
        from runner_checks import (
            validate_output_expectations as shared_validate_output_expectations,
        )

    return shared_validate_output_expectations(case_def, stdout, stderr)


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
                message = (
                    f"Expected return to contain {expected_fragment!r}, got {result!r}"
                )

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
    message = "Command succeeded" if passed else f"Expected exit code 0, got {result.exit_code}"
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
