from __future__ import annotations

import importlib
import inspect
import types
from contextlib import ExitStack
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
from typing import Callable
from typing import Mapping
from unittest.mock import Mock
from unittest.mock import patch

try:  # Support package imports and direct harness module loading.
    from .case_data_builders import expand_template as base_expand_template
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from case_data_builders import expand_template as base_expand_template



def _stateful_read_content(spec: Any, state: dict[str, Any], work_dir: Path) -> bytes:
    if isinstance(spec, bytes):
        return spec
    if isinstance(spec, str):
        return spec.encode("utf-8")
    if not isinstance(spec, dict):
        raise TypeError("Stateful content spec must be bytes, string, or mapping")
    if "from_state" in spec:
        value = state.get(str(spec["from_state"]), b"")
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        raise TypeError("State value for content must be bytes or string")
    if "from_file" in spec:
        file_path = work_dir / str(spec["from_file"])
        return file_path.read_bytes()
    if "hex" in spec:
        return bytes.fromhex(str(spec["hex"]))
    raise ValueError(f"Unsupported stateful content spec: {spec!r}")


def _stateful_resolve_value(spec: Any, state: dict[str, Any], work_dir: Path) -> Any:
    if isinstance(spec, dict):
        if "from_state" in spec:
            return state.get(str(spec["from_state"]))
        if "from_file" in spec or "hex" in spec:
            return _stateful_read_content(spec, state, work_dir)
    return spec


def stateful_run_router(
    responses: dict[str, Any] | None = None,
    **options: Any,
):
    """Stateful subprocess.run router for scenario-specific command flows."""
    state = dict(options.pop("state", {}) or {})
    rules = list(options.pop("rules", []) or [])
    responses = dict(responses or {})
    default_stdout = str(options.pop("default_stdout", ""))
    default_stderr = str(options.pop("default_stderr", ""))
    default_returncode = int(options.pop("default_returncode", 0))
    unmatched_stderr_template = options.pop("unmatched_stderr_template", None)
    if unmatched_stderr_template is not None and not isinstance(
        unmatched_stderr_template,
        str,
    ):
        raise TypeError("'unmatched_stderr_template' must be a string")
    use_contains = bool(options.pop("use_contains", True))
    call_log_path = options.pop("call_log_path", None)
    if call_log_path is not None and not isinstance(call_log_path, str):
        raise TypeError("'call_log_path' must be a string")
    if options:
        unsupported = ", ".join(sorted(options))
        raise TypeError(f"Unsupported stateful_run_router option(s): {unsupported}")

    response_state: dict[str, int] = {}

    def _match(pattern: str, cmd_text: str) -> bool:
        if use_contains:
            return pattern in cmd_text
        return pattern == cmd_text

    def _mock_run(cmd, *args, **kwargs):
        del args, kwargs
        cmd_text = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)

        if call_log_path is not None:
            log_path = Path(call_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{cmd_text}\n")

        for rule in rules:
            if not isinstance(rule, dict):
                raise TypeError("Each stateful_run_router rule must be a mapping")
            pattern = rule.get("command")
            if not isinstance(pattern, str):
                raise TypeError("stateful_run_router rule requires string 'command'")
            if not _match(pattern, cmd_text):
                continue

            for key, value_spec in (rule.get("set_state") or {}).items():
                state[str(key)] = _stateful_resolve_value(value_spec, state, Path.cwd())

            write_file = rule.get("write_file")
            if write_file is not None:
                if (
                    not isinstance(write_file, dict)
                    or "path" not in write_file
                    or "content" not in write_file
                ):
                    raise TypeError("write_file must be a mapping with 'path' and 'content'")
                target = Path.cwd() / str(write_file["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(
                    _stateful_read_content(
                        write_file["content"],
                        state,
                        Path.cwd(),
                    )
                )

            if "raise" in rule:
                raise build_exception_from_spec(rule["raise"])

            result = rule.get("result", {})
            if not isinstance(result, dict):
                raise TypeError("stateful_run_router rule 'result' must be a mapping")
            return CompletedProcess(
                args=cmd,
                returncode=int(result.get("returncode", 0)),
                stdout=str(result.get("stdout", "")),
                stderr=str(result.get("stderr", "")),
            )

        for pattern, result in responses.items():
            if not _match(pattern, cmd_text):
                continue
            resolved = result
            if isinstance(result, list):
                if not result:
                    raise TypeError("stateful_run_router response lists must not be empty")
                index = response_state.get(pattern, 0)
                response_state[pattern] = index + 1
                resolved = result[index] if index < len(result) else result[-1]
            if not isinstance(resolved, dict):
                raise TypeError("stateful_run_router responses must resolve to mappings")
            return CompletedProcess(
                args=cmd,
                returncode=int(resolved.get("returncode", 0)),
                stdout=str(resolved.get("stdout", "")),
                stderr=str(resolved.get("stderr", "")),
            )

        stderr_text = default_stderr
        if unmatched_stderr_template is not None:
            stderr_text = unmatched_stderr_template.format(cmd=cmd_text)

        return CompletedProcess(
            args=cmd,
            returncode=default_returncode,
            stdout=default_stdout,
            stderr=stderr_text,
        )

    return _mock_run


class ConfigError(Exception):
    """Raised when a YAML configuration is invalid."""


def load_dotted_object(dotted_path: str) -> Any:
    """Load object from dotted path like 'pkg.mod.func' or 'pkg.mod.obj.attr'."""
    if not isinstance(dotted_path, str) or "." not in dotted_path:
        raise ValueError(f"Invalid dotted path: {dotted_path!r}")

    parts = dotted_path.split(".")
    last_error: Exception | None = None

    for index in range(len(parts) - 1, 0, -1):
        module_name = ".".join(parts[:index])
        attr_parts = parts[index:]

        try:
            obj = importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc
            continue

        try:
            for attr_name in attr_parts:
                obj = getattr(obj, attr_name)
            return obj
        except AttributeError as exc:
            raise AttributeError(f"Invalid dotted path: {dotted_path!r}") from exc

    raise ValueError(f"Invalid dotted path: {dotted_path!r}") from last_error


def resolve_special_value(value: Any) -> Any:
    """
    Resolve special YAML values.

    Supported:
      - 'py:package.module.object' -> imported Python object
    """
    if isinstance(value, str) and value.startswith("py:"):
        return load_dotted_object(value[3:])
    if isinstance(value, list):
        return [resolve_special_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_special_value(item) for item in value)
    if isinstance(value, dict):
        return {
            key: resolve_special_value(item)
            for key, item in value.items()
        }
    return value


def build_exception_from_spec(spec: Any) -> BaseException:
    """
    Build an exception instance from YAML spec.

    Supported forms:
      - py:builtins.OSError
      - {type: py:builtins.OSError, args: ["message"]}
      - an already-created exception instance
    """
    resolved = resolve_special_value(spec)

    if isinstance(resolved, BaseException):
        return resolved

    if isinstance(resolved, type) and issubclass(resolved, BaseException):
        return resolved()

    if not isinstance(resolved, dict):
        raise TypeError(
            "Exception spec must resolve to an exception instance, exception "
            f"class, or mapping. Got: {type(resolved).__name__}"
        )

    exc_type = resolved.get("type")
    if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
        raise TypeError(
            "Exception spec 'type' must resolve to an exception class, "
            f"got: {exc_type!r}"
        )

    args = resolved.get("args", [])
    kwargs = resolved.get("kwargs", {})

    if not isinstance(args, list):
        raise TypeError(
            f"Exception spec 'args' must be a list, got: {type(args).__name__}"
        )
    if not isinstance(kwargs, dict):
        raise TypeError(
            f"Exception spec 'kwargs' must be a dict, got: {type(kwargs).__name__}"
        )

    return exc_type(*args, **kwargs)


def resolve_side_effect_value(value: Any) -> Any:
    """Resolve side-effect values, including exception descriptors."""
    if isinstance(value, list):
        return [resolve_side_effect_value(item) for item in value]

    if isinstance(value, dict) and set(value.keys()) == {"exception"}:
        return build_exception_from_spec(value["exception"])

    return resolve_special_value(value)


def set_nested_attr(obj: Any, attr_path: str, value: Any) -> None:
    """
    Set nested attribute path like:
      return_value.stdout
      return_value.returncode
    """
    parts = attr_path.split(".")
    current = obj

    for part in parts[:-1]:
        current = getattr(current, part)

    setattr(current, parts[-1], value)


def build_mock_from_spec(target: str, spec: Any) -> Any:
    """
    Build replacement object from YAML spec.

    Supported forms:

    1) String shorthand:
       mocks:
         shutil.which: unittest.mock.Mock

    2) Dict form:
       mocks:
         subprocess.run:
           factory: unittest.mock.Mock
           kwargs:
             name: run_mock
           attrs:
             return_value.stdout: "hello"
             return_value.returncode: 0

    3) Implicit Mock with direct behavior:
       mocks:
         yaml.safe_load:
           side_effect:
             - {"sha256": ["a0", "a1"]}
             - exception:
                 type: py:yaml.YAMLError
                 args: ["mocked parse failure"]

    4) Factory that needs the original callable:
       mocks:
         builtins.open:
           factory: mock_helpers.passthrough_router
           inject_original_as: real
           kwargs:
             rules: [...]

    5) Direct callable factory (used by generated scenarios):
       mocks:
         time.sleep:
           value: <function noop>
    """
    if isinstance(spec, str):
        factory = load_dotted_object(spec)
        return factory()

    if not isinstance(spec, dict):
        raise TypeError(f"Unsupported mock spec type: {type(spec).__name__}")

    factory_ref = spec.get("factory")
    if (
        factory_ref is not None
        and not isinstance(factory_ref, str)
        and not callable(factory_ref)
    ):
        raise TypeError(
            "'factory' must be a string or callable when provided, "
            f"got: {type(factory_ref).__name__}"
        )

    if "value" in spec:
        return resolve_special_value(spec["value"])

    original = load_dotted_object(target)

    raw_args = spec.get("args", [])
    if raw_args is None:
        raw_args = []
    if not isinstance(raw_args, list):
        raise TypeError(f"'args' must be a list, got: {type(raw_args).__name__}")

    raw_kwargs = spec.get("kwargs", {})
    if raw_kwargs is None:
        raw_kwargs = {}
    if not isinstance(raw_kwargs, dict):
        raise TypeError(f"'kwargs' must be a dict, got: {type(raw_kwargs).__name__}")

    args = [resolve_special_value(value) for value in raw_args]
    kwargs = {key: resolve_special_value(value) for key, value in raw_kwargs.items()}

    inject_original_as = spec.get("inject_original_as")
    if inject_original_as is not None:
        if not isinstance(inject_original_as, str) or not inject_original_as.strip():
            raise TypeError("'inject_original_as' must be a non-empty string")
        kwargs[inject_original_as] = original

    if spec.get("wraps_original", False):
        kwargs["wraps"] = original

    if factory_ref:
        if isinstance(factory_ref, str):
            factory = load_dotted_object(factory_ref)
        else:
            factory = factory_ref
    else:
        factory = Mock

    obj = factory(*args, **kwargs)

    raw_attrs = spec.get("attrs", {})
    if raw_attrs is None:
        raw_attrs = {}

    if not isinstance(raw_attrs, dict):
        raise TypeError(f"'attrs' must be a dict, got: {type(raw_attrs).__name__}")

    if "return_value" in spec:
        obj.return_value = resolve_special_value(spec["return_value"])

    if "side_effect" in spec:
        obj.side_effect = resolve_side_effect_value(spec["side_effect"])

    for attr_name, raw_value in raw_attrs.items():
        value = resolve_special_value(raw_value)
        set_nested_attr(obj, attr_name, value)

    return obj


def expand_patch_target(
    target: str,
    target_context: Mapping[str, str] | None = None,
) -> str:
    """Expand supported placeholders such as '{module}' in patch targets."""
    expanded = target
    if not target_context:
        return expanded

    for key, value in target_context.items():
        expanded = expanded.replace(f"{{{key}}}", str(value))
    return expanded


def apply_case_mocks(
    mock_map: dict[str, Any] | None,
    *,
    target_context: Mapping[str, str] | None = None,
) -> ExitStack:
    """
    Apply case mocks and return an ExitStack.

    Caller should use:
        with apply_case_mocks(case.get("mocks")):
            ...
    """
    stack = ExitStack()

    if not mock_map:
        return stack

    if not isinstance(mock_map, dict):
        raise TypeError(f"'mocks' must be a dict, got: {type(mock_map).__name__}")

    for target, spec in mock_map.items():
        if not isinstance(target, str):
            raise TypeError(
                f"Mock target must be a string, got: {type(target).__name__}"
            )
        expanded_target = expand_patch_target(target, target_context)
        replacement = build_mock_from_spec(expanded_target, spec)
        verifier = getattr(replacement, "_mock_verify", None)
        if callable(verifier):
            stack.callback(verifier)
        stack.enter_context(patch(expanded_target, replacement))

    return stack


def expand_template(
    value: str,
    work_dir: Path,
    file_path: Path,
    extra_tokens: dict[str, str] | None = None,
) -> str:
    """Expand common runtime tokens such as {dir}, {file}, and optional extras."""
    expanded = base_expand_template(value, work_dir, file_path)
    if not extra_tokens:
        return expanded

    for key, item in extra_tokens.items():
        expanded = expanded.replace(f"{{{key}}}", str(item))
    return expanded


def expand_case_value(
    value: Any,
    work_dir: Path,
    file_path: Path,
    extra_tokens: dict[str, str] | None = None,
) -> Any:
    """Recursively expand runtime tokens inside case values."""
    if isinstance(value, str):
        return expand_template(value, work_dir, file_path, extra_tokens)
    if isinstance(value, list):
        return [expand_case_value(item, work_dir, file_path, extra_tokens) for item in value]
    if isinstance(value, tuple):
        return tuple(
            expand_case_value(item, work_dir, file_path, extra_tokens)
            for item in value
        )
    if isinstance(value, dict):
        return {
            key: expand_case_value(item, work_dir, file_path, extra_tokens)
            for key, item in value.items()
        }
    return value


def expand_case_mapping(
    mapping: dict[str, Any] | None,
    work_dir: Path,
    file_path: Path,
    extra_tokens: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Expand tokens across a case mapping, including its keys."""
    if not mapping:
        return {}

    expanded: dict[str, Any] = {}
    for key, value in mapping.items():
        expanded_key = (
            expand_template(key, work_dir, file_path, extra_tokens)
            if isinstance(key, str)
            else key
        )
        expanded[expanded_key] = expand_case_value(
            value,
            work_dir,
            file_path,
            extra_tokens,
        )
    return expanded


def merge_case_definitions(
    generated_case: dict[str, Any],
    case_def: dict[str, Any],
) -> dict[str, Any]:
    """Merge generated scenario data with explicit user-specified case fields."""
    merged = dict(generated_case)
    merged.update(case_def)

    for field_name in (
        "scripts",
        "bin_files",
        "text_files",
        "patch_constants",
        "mocks",
        "kwargs",
    ):
        generated = generated_case.get(field_name) or {}
        explicit = case_def.get(field_name) or {}
        if generated or explicit:
            merged[field_name] = {**generated, **explicit}

    generated_dirs = list(generated_case.get("dir_structure") or [])
    explicit_dirs = list(case_def.get("dir_structure") or [])
    if generated_dirs or explicit_dirs:
        merged["dir_structure"] = [*generated_dirs, *explicit_dirs]

    if "args" not in case_def and "args" in generated_case:
        merged["args"] = list(generated_case["args"])

    return merged


def _resolve_runner_module_from_stack() -> types.ModuleType:
    """
    Resolve the target module from the runner call stack.

    module_main_with_env currently calls ``module.main()`` directly. For scripts
    that only expose a main guard, scenario builders can inject a synthetic
    ``main`` callable via patch_constants, and that callable recovers the target
    module from the runner frame.
    """
    frame = inspect.currentframe()
    current = frame.f_back if frame is not None else None
    try:
        while current is not None:
            candidate = current.f_locals.get("module")
            if isinstance(candidate, types.ModuleType):
                return candidate
            current = current.f_back
    finally:
        del frame
        del current

    raise RuntimeError("Unable to resolve target module from runner stack")


# Keep scenario imports below the shared helpers so the split builder modules can
# import shared functionality from this file without circular-import breakage.
try:  # Support package imports and direct harness module loading.
    from .mock_loader_hardware_scenarios import build_blk_devices_scenario_case
    from .mock_loader_hardware_scenarios import build_blk_write_check_scenario_case
    from .mock_loader_hardware_scenarios import build_capsule_vars_scenario_case
    from .mock_loader_hardware_scenarios import build_ethtool_scenario_case
    from .mock_loader_hardware_scenarios import build_runtime_device_mapping_scenario_case
    from .mock_loader_hardware_scenarios import build_verify_tpm_events
    from .mock_loader_hardware_scenarios import build_verify_tpm_scenario_case
    from .mock_loader_parser_scenarios import build_acs_info_scenario_case
    from .mock_loader_parser_scenarios import build_extract_capsule_fw_version_scenario_case
    from .mock_loader_parser_scenarios import build_merge_jsons_scenario_case
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from mock_loader_hardware_scenarios import build_blk_devices_scenario_case
    from mock_loader_hardware_scenarios import build_blk_write_check_scenario_case
    from mock_loader_hardware_scenarios import build_capsule_vars_scenario_case
    from mock_loader_hardware_scenarios import build_ethtool_scenario_case
    from mock_loader_hardware_scenarios import build_runtime_device_mapping_scenario_case
    from mock_loader_hardware_scenarios import build_verify_tpm_events
    from mock_loader_hardware_scenarios import build_verify_tpm_scenario_case
    from mock_loader_parser_scenarios import build_acs_info_scenario_case
    from mock_loader_parser_scenarios import build_extract_capsule_fw_version_scenario_case
    from mock_loader_parser_scenarios import build_merge_jsons_scenario_case


SCENARIO_CASE_BUILDERS: dict[
    str,
    Callable[[dict[str, Any], Path], dict[str, Any]],
] = {
    "ethtool": build_ethtool_scenario_case,
    "capsule_vars": build_capsule_vars_scenario_case,
    "verify_tpm": build_verify_tpm_scenario_case,
    "acs_info": build_acs_info_scenario_case,
    "merge_jsons": build_merge_jsons_scenario_case,
    "blk_devices": build_blk_devices_scenario_case,
    "blk_write_check": build_blk_write_check_scenario_case,
    "runtime_device_mapping": build_runtime_device_mapping_scenario_case,
}


def build_generated_case_definition(
    case_def: dict[str, Any],
    work_dir: Path,
    file_path: Path,
    extra_tokens: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an implicit/generated case definition from scenario input."""
    scenario = expand_case_value(
        case_def.get("scenario"),
        work_dir,
        file_path,
        extra_tokens,
    )
    if not scenario:
        return {}
    if not isinstance(scenario, dict):
        raise ConfigError("'scenario' must resolve to a mapping")

    kind = scenario.get("kind")
    if kind is None and file_path.name == "ethtool-test.py":
        kind = "ethtool"
    builder = SCENARIO_CASE_BUILDERS.get(str(kind))
    if builder is None:
        raise ConfigError(f"Unsupported scenario kind: {kind!r}")
    return builder(scenario, work_dir)


def build_case_runtime_definition(
    case_def: dict[str, Any],
    work_dir: Path,
    file_path: Path,
    extra_tokens: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the final runtime case after scenario generation and token expansion."""
    generated_case = build_generated_case_definition(
        case_def,
        work_dir,
        file_path,
        extra_tokens,
    )
    merged_case = merge_case_definitions(generated_case, case_def)

    runtime_case = dict(merged_case)
    runtime_case["scripts"] = expand_case_mapping(
        merged_case.get("scripts", {}),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["bin_files"] = expand_case_mapping(
        merged_case.get("bin_files", {}),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["text_files"] = expand_case_mapping(
        merged_case.get("text_files", {}),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["dir_structure"] = expand_case_value(
        merged_case.get("dir_structure", []),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["patch_constants"] = expand_case_value(
        merged_case.get("patch_constants", {}),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["mocks"] = expand_case_mapping(
        merged_case.get("mocks", {}),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["args"] = expand_case_value(
        merged_case.get("args", []),
        work_dir,
        file_path,
        extra_tokens,
    )
    runtime_case["kwargs"] = expand_case_value(
        merged_case.get("kwargs", {}),
        work_dir,
        file_path,
        extra_tokens,
    )
    return runtime_case


__all__ = [
    "ConfigError",
    "SCENARIO_CASE_BUILDERS",
    "_resolve_runner_module_from_stack",
    "apply_case_mocks",
    "build_acs_info_scenario_case",
    "build_blk_devices_scenario_case",
    "build_blk_write_check_scenario_case",
    "build_capsule_vars_scenario_case",
    "build_case_runtime_definition",
    "build_ethtool_scenario_case",
    "build_exception_from_spec",
    "build_extract_capsule_fw_version_scenario_case",
    "build_generated_case_definition",
    "build_merge_jsons_scenario_case",
    "build_mock_from_spec",
    "build_runtime_device_mapping_scenario_case",
    "build_verify_tpm_events",
    "build_verify_tpm_scenario_case",
    "expand_case_mapping",
    "expand_case_value",
    "expand_patch_target",
    "expand_template",
    "load_dotted_object",
    "merge_case_definitions",
    "resolve_side_effect_value",
    "resolve_special_value",
    "set_nested_attr",
    "stateful_run_router",
]
