from __future__ import annotations

from typing import Any

try:  # Support package imports and direct harness module loading.
    from .runner_checks import (
        DEFAULT_CLI_TIMEOUT_SEC,
        ConfigError,
        ensure_list,
        ensure_list_of_strings,
        ensure_string_or_list_of_strings,
        merge_mappings,
    )
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from runner_checks import (
        DEFAULT_CLI_TIMEOUT_SEC,
        ConfigError,
        ensure_list,
        ensure_list_of_strings,
        ensure_string_or_list_of_strings,
        merge_mappings,
    )


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
                raise ConfigError(f"{field_name}.patch_constants keys must be strings")
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
                raise ConfigError(f"{field_name}.dir_structure[{index}] must be a mapping")
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
    if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
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
            return
        if not isinstance(expect_stdout_or_stderr_regex, list) or not all(
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
