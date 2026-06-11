from __future__ import annotations

import inspect
import importlib
import json
import types
from subprocess import CalledProcessError
from subprocess import CompletedProcess
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Mapping
from unittest.mock import Mock
from unittest.mock import patch

from case_data_builders import expand_template as base_expand_template
from mock_helpers import build_char16_payload
from mock_helpers import build_df_output
from mock_helpers import build_efi_var_bytes
from mock_helpers import build_ethtool_ip_address_output
from mock_helpers import build_ethtool_ip_link_line
from mock_helpers import build_ethtool_ip_link_show_line
from mock_helpers import build_fdisk_output
from mock_helpers import build_os_indications_var
from mock_helpers import build_run_result_from_outcome
from mock_helpers import build_sgdisk_partition_output
from mock_helpers import check_output_router
from mock_helpers import default_device_path
from mock_helpers import noop
from mock_helpers import normalize_ethtool_tool_path
from mock_helpers import passthrough_router
from mock_helpers import route_gateway
from mock_helpers import run_router
from mock_helpers import scenario_truthy
from mock_helpers import which_router


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


def build_ethtool_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build runtime files, args, and mocks for an ethtool scenario."""
    interfaces = scenario.get("interfaces", [])
    if interfaces is None:
        interfaces = []
    if not isinstance(interfaces, list):
        raise ConfigError("scenario.interfaces must be a list")

    tool_paths = {
        name: normalize_ethtool_tool_path(name, raw_value)
        for name, raw_value in (scenario.get("tools") or {}).items()
    }

    ip_link_lines = [
        build_ethtool_ip_link_line(index, iface)
        for index, iface in enumerate(interfaces, start=1)
    ]
    run_responses: dict[str, Any] = {
        "ip route show default": {"returncode": 0, "stdout": "", "stderr": ""},
        "ip -o route show table all default": {"returncode": 0, "stdout": "", "stderr": ""},
    }
    read_text_rules: list[dict[str, Any]] = []
    resolve_rules: list[dict[str, Any]] = []
    default_route_lines: list[str] = []
    route_get_output = scenario.get("route_get")

    for index, iface in enumerate(interfaces, start=1):
        name = iface["name"]
        kind = str(iface.get("kind", "physical"))

        run_responses[f"ip link show {name}"] = {
            "returncode": 0,
            "stdout": build_ethtool_ip_link_show_line(index, iface),
            "stderr": "",
        }
        run_responses[f"ip link set dev {name} down"] = {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }
        run_responses[f"ip link set dev {name} up"] = {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }
        run_responses[f"ip address show dev {name}"] = {
            "returncode": 0,
            "stdout": build_ethtool_ip_address_output(index, iface),
            "stderr": "",
        }

        if tool_paths.get("dhclient") is not None:
            run_responses[f"dhclient -r {name}"] = {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            }
            run_responses[f"dhclient -1 {name}"] = {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            }
        if tool_paths.get("udhcpc") is not None:
            run_responses[f"udhcpc -n -q -i {name}"] = {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            }

        if kind != "loopback":
            device_path = str(iface.get("device") or default_device_path(index, iface))
            resolve_rules.append(
                {
                    "when": {"args": {0: {"contains": f"/sys/class/net/{name}/device"}}},
                    "return": device_path,
                }
            )
            read_text_rules.append(
                {
                    "when": {"args": {0: {"contains": f"/sys/class/net/{name}/carrier"}}},
                    "return": str(iface.get("carrier", "1" if kind == "physical" else "0")),
                }
            )
            read_text_rules.append(
                {
                    "when": {"args": {0: {"contains": f"/sys/class/net/{name}/operstate"}}},
                    "return": str(iface.get("operstate", "up" if kind == "physical" else "down")),
                }
            )

        if tool_paths.get("ethtool") is not None and kind != "loopback":
            ethtool_cfg = iface.get("ethtool") or {}
            link_detected = scenario_truthy(
                ethtool_cfg.get("link_detected"),
                default=str(iface.get("carrier", "0")) == "1",
            )
            self_test_supported = scenario_truthy(
                ethtool_cfg.get("self_test_supported"),
                default=False,
            )
            run_responses[f"ethtool {name}"] = {
                "returncode": 0,
                "stdout": (
                    f"Settings for {name}\n"
                    f"\tLink detected: {'yes' if link_detected else 'no'}\n"
                ),
                "stderr": "",
            }
            run_responses[f"ethtool -i {name}"] = {
                "returncode": 0,
                "stdout": (
                    "driver: fake\n"
                    f"supports-test: {'yes' if self_test_supported else 'no'}\n"
                ),
                "stderr": "",
            }
            if self_test_supported or "self_test" in ethtool_cfg:
                self_test = ethtool_cfg.get("self_test", "pass")
                run_responses[f"ethtool -t {name}"] = build_run_result_from_outcome(
                    self_test,
                    success_stdout="The test result is PASS\n",
                    failure_stdout="self-test failed\n",
                )

        routes = iface.get("routes") or {}
        default_route = routes.get("default") or iface.get("default_route")
        if default_route:
            default_route_lines.append(str(default_route))
        if route_get_output is None:
            route_get_output = routes.get("route_get") or iface.get("route_get")

        connectivity = iface.get("connectivity") or {}
        gateway = route_gateway(str(default_route)) if default_route else None
        if gateway and "gateway_ping" in connectivity:
            run_responses[
                f"ping -c 3 -W 10 -I {name} {gateway}"
            ] = build_run_result_from_outcome(
                connectivity["gateway_ping"],
                success_stdout="3 packets transmitted, 3 received, 0% packet loss\n",
                failure_stdout="3 packets transmitted, 0 received, 100% packet loss\n",
            )
        if "arm_ping" in connectivity:
            run_responses[
                f"ping -c 3 -W 10 -I {name} www.arm.com"
            ] = build_run_result_from_outcome(
                connectivity["arm_ping"],
                success_stdout="3 packets transmitted, 3 received, 0% packet loss\n",
                failure_stdout="3 packets transmitted, 0 received, 100% packet loss\n",
            )
        if "ipv6_ping" in connectivity:
            ipv6_result = build_run_result_from_outcome(
                connectivity["ipv6_ping"],
                success_stdout="3 packets transmitted, 3 received, 0% packet loss\n",
                failure_stdout="3 packets transmitted, 0 received, 100% packet loss\n",
            )
            run_responses[f"ping -6 -c 3 -I {name} ipv6.google.com"] = ipv6_result
            run_responses[f"ping6 -c 3 -I {name} ipv6.google.com"] = ipv6_result
        if "wget" in connectivity:
            run_responses[
                "wget --spider --timeout=10 https://www.arm.com"
            ] = build_run_result_from_outcome(
                connectivity["wget"],
                success_stdout="",
                failure_stderr="network unreachable\n",
            )
        if "curl" in connectivity:
            run_responses[
                f"curl -Is --connect-timeout 20 --interface {name} https://www.arm.com"
            ] = build_run_result_from_outcome(
                connectivity["curl"],
                success_stdout="HTTP/2 200\n",
                failure_stderr="connect failed\n",
            )

    if default_route_lines:
        routes_stdout = "\n".join(default_route_lines) + "\n"
        run_responses["ip route show default"] = {
            "returncode": 0,
            "stdout": routes_stdout,
            "stderr": "",
        }
        run_responses["ip -o route show table all default"] = {
            "returncode": 0,
            "stdout": routes_stdout,
            "stderr": "",
        }

    if route_get_output:
        route_text = str(route_get_output)
        if not route_text.endswith("\n"):
            route_text += "\n"
        run_responses["ip route get 8.8.8.8"] = {
            "returncode": 0,
            "stdout": route_text,
            "stderr": "",
        }

    required = scenario.get("required_compliant_interfaces")
    if required is None:
        required = sum(
            1
            for iface in interfaces
            if str(iface.get("kind", "physical")) == "physical"
        )

    system_config_path = work_dir / "system_config.txt"
    return {
        "args": [str(system_config_path)],
        "text_files": {
            "system_config.txt": f"total_number_of_network_controllers: {required}\n",
        },
        "mocks": {
            "signal.signal": {"value": noop},
            "time.sleep": {"value": noop},
            "shutil.which": {
                "factory": which_router,
                "kwargs": {"responses": tool_paths, "default": None},
            },
            "subprocess.check_output": {
                "factory": check_output_router,
                "kwargs": {
                    "responses": {
                        "ip -o link": "\n".join(ip_link_lines) + ("\n" if ip_link_lines else "")
                    },
                    "use_contains": False,
                },
            },
            "subprocess.run": {
                "factory": run_router,
                "kwargs": {
                    "responses": run_responses,
                    "default_returncode": 1,
                    "use_contains": False,
                    "unmatched_stderr_template": "UNMOCKED COMMAND: {cmd}\n",
                },
            },
            "pathlib.Path.read_text": {
                "factory": passthrough_router,
                "inject_original_as": "real",
                "kwargs": {"rules": read_text_rules},
            },
            "pathlib.Path.resolve": {
                "factory": passthrough_router,
                "inject_original_as": "real",
                "kwargs": {"rules": resolve_rules},
            },
        },
    }


PRECIOUS_MBR_IDS = {"0xF8", "0xEF"}
PRECIOUS_GPT_GUIDS = {
    "C12A7328-F81F-11D2-BA4B-00A0C93EC93B",
    "21686148-6449-6E6F-744E-656564454649",
    "3DE21764-95BD-54BD-A5C3-4ABE786F38A8",
}


def _completed_process_spec(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, Any]:
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr}


def _join_stdout_lines(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(items) + "\n"


def _normalize_mbr_partition_id(value: Any) -> str:
    text = str(value).strip().upper()
    if not text:
        return ""
    if text.startswith("0X"):
        text = text[2:]
    return f"0x{text}"


def _normalize_prompt_response(value: Any, *, default: str = "no") -> str:
    """Normalize YAML prompt values into explicit yes/no/timeout responses."""
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "yes" if value else "no"
    else:
        text = str(value).strip().lower()

    if not text:
        return default

    normalized = {
        "timeout": "timeout",
        "1": "yes",
        "true": "yes",
        "yes": "yes",
        "y": "yes",
        "on": "yes",
        "0": "no",
        "false": "no",
        "no": "no",
        "n": "no",
        "off": "no",
    }
    return normalized.get(text, text)


def _platform_required(partition: dict[str, Any]) -> bool:
    if "attribute_flags" in partition:
        flags = str(partition["attribute_flags"]).strip()
        try:
            return (int(flags, 16) & 1) == 1
        except ValueError as exc:
            raise ConfigError(
                f"Invalid GPT attribute_flags value: {partition['attribute_flags']!r}"
            ) from exc
    return scenario_truthy(partition.get("platform_required"), default=False)


def _add_blk_write_check_run_responses(
    run_responses: dict[str, Any],
    target: str,
    write_cfg: dict[str, Any] | None,
) -> None:
    cfg = write_cfg or {}
    mounted = scenario_truthy(cfg.get("mounted"), default=False)
    run_responses[f"findmnt -n /dev/{target}"] = _completed_process_spec(
        returncode=0 if mounted else 1,
        stdout=f"/dev/{target} /mnt/{target} ext4 rw,relatime 0 0\n" if mounted else "",
    )

    if mounted:
        return

    if "used_blocks" not in cfg and "available_blocks" not in cfg:
        return

    used_blocks = int(cfg.get("used_blocks", 0))
    available_blocks = int(cfg.get("available_blocks", 0))
    run_responses[f"df -B 512 /dev/{target} --output=used,avail"] = _completed_process_spec(
        stdout=build_df_output(used_blocks, available_blocks)
    )


def _build_blk_write_check_stateful_rules(
    device: str,
    cfg: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    write_flow = cfg.get("write_flow")
    if write_flow is None:
        return {}, []
    if not isinstance(write_flow, dict):
        raise ConfigError("blk_write_check.write_flow must be a mapping when provided")

    initial_bytes = cfg.get("initial_device_bytes")
    if initial_bytes is None:
        initial_text = str(cfg.get("initial_device_text", "B" * 512))
        initial_bytes = initial_text.encode("utf-8")
    elif isinstance(initial_bytes, str):
        try:
            initial_bytes = bytes.fromhex(initial_bytes)
        except ValueError as exc:
            raise ConfigError(
                "blk_write_check.initial_device_bytes must be bytes or hex string"
            ) from exc
    elif not isinstance(initial_bytes, bytes):
        raise ConfigError("blk_write_check.initial_device_bytes must be bytes or hex string")

    mismatch_bytes = write_flow.get("mismatch_bytes")
    if mismatch_bytes is None:
        mismatch_bytes = b"X" * max(len(initial_bytes), 512)
    elif isinstance(mismatch_bytes, str):
        try:
            mismatch_bytes = bytes.fromhex(mismatch_bytes)
        except ValueError as exc:
            raise ConfigError(
                "blk_write_check.write_flow.mismatch_bytes must be bytes or hex string"
            ) from exc
    elif not isinstance(mismatch_bytes, bytes):
        raise ConfigError("blk_write_check.write_flow.mismatch_bytes must be bytes or hex string")

    used_blocks = int(cfg.get("used_blocks", 0))
    backup_name = f"{device}_backup.bin"
    device_state_key = f"{device}:device_bytes"
    mismatch_state_key = f"{device}:mismatch_bytes"
    state = {
        device_state_key: initial_bytes,
        mismatch_state_key: mismatch_bytes,
    }
    rules: list[dict[str, Any]] = []

    backup_command = (
        f"dd if=/dev/{device} of={backup_name} bs=512 count=1 skip={used_blocks}"
    )
    backup_mode = str(write_flow.get("backup", "success")).lower()
    if backup_mode in {"success", "pass", "ok"}:
        rules.append({
            "command": backup_command,
            "write_file": {
                "path": backup_name,
                "content": {"from_state": device_state_key},
            },
            "result": {"returncode": 0, "stdout": "", "stderr": ""},
        })
    elif backup_mode == "error":
        error_text = str(write_flow.get("backup_error", "mocked backup failure"))
        rules.append({
            "command": backup_command,
            "raise": {
                "type": CalledProcessError,
                "args": [1, backup_command],
                "kwargs": {"output": "", "stderr": error_text},
            },
        })
    elif backup_mode not in {"skip", "none"}:
        raise ConfigError(
            "blk_write_check.write_flow.backup must be success, error, skip, or none"
        )

    write_command = (
        f"dd if=hello.txt of=/dev/{device} bs=512 count=1 seek={used_blocks}"
    )
    write_mode = str(write_flow.get("write", "success")).lower()
    if write_mode in {"success", "pass", "ok"}:
        written_content = (
            {"from_state": mismatch_state_key}
            if str(write_flow.get("readback", "match")).lower() == "mismatch"
            else {"from_file": "hello.txt"}
        )
        rules.append({
            "command": write_command,
            "set_state": {device_state_key: written_content},
            "result": {"returncode": 0, "stdout": "", "stderr": ""},
        })
    elif write_mode == "error":
        error_text = str(write_flow.get("write_error", "mocked write failure"))
        rules.append({
            "command": write_command,
            "raise": {
                "type": CalledProcessError,
                "args": [1, write_command],
                "kwargs": {"output": "", "stderr": error_text},
            },
        })
    elif write_mode not in {"skip", "none"}:
        raise ConfigError(
            "blk_write_check.write_flow.write must be success, error, skip, or none"
        )

    read_command = (
        f"dd if=/dev/{device} of=read_hello.txt bs=512 count=1 skip={used_blocks}"
    )
    readback_mode = str(write_flow.get("readback", "match")).lower()
    if readback_mode in {"match", "mismatch"}:
        rules.append({
            "command": read_command,
            "write_file": {
                "path": "read_hello.txt",
                "content": {"from_state": device_state_key},
            },
            "result": {"returncode": 0, "stdout": "", "stderr": ""},
        })
    elif readback_mode == "error":
        error_text = str(write_flow.get("readback_error", "mocked readback failure"))
        rules.append({
            "command": read_command,
            "raise": {
                "type": CalledProcessError,
                "args": [1, read_command],
                "kwargs": {"output": "", "stderr": error_text},
            },
        })
    else:
        raise ConfigError("blk_write_check.write_flow.readback must be match, mismatch, or error")

    restore_command = (
        f"dd if={backup_name} of=/dev/{device} bs=512 count=1 seek={used_blocks}"
    )
    restore_mode = str(write_flow.get("restore", "success")).lower()
    if restore_mode in {"success", "pass", "ok"}:
        rules.append({
            "command": restore_command,
            "set_state": {device_state_key: {"from_file": backup_name}},
            "result": {"returncode": 0, "stdout": "", "stderr": ""},
        })
    elif restore_mode == "error":
        error_text = str(write_flow.get("restore_error", "mocked restore failure"))
        rules.append({
            "command": restore_command,
            "raise": {
                "type": CalledProcessError,
                "args": [1, restore_command],
                "kwargs": {"output": "", "stderr": error_text},
            },
        })
    elif restore_mode not in {"skip", "none"}:
        raise ConfigError(
            "blk_write_check.write_flow.restore must be success, error, skip, or none"
        )

    return state, rules


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


BLK_DEVICE_BANNER = "*" * 128


def _print_blk_devices_separator() -> None:
    print(f"\n{BLK_DEVICE_BANNER}\n")


def _run_blk_device_command(module: Any, command: str) -> Any:
    return module.subprocess.run(
        command,
        shell=True,
        text=True,
        check=False,
        capture_output=True,
    )


def _list_blk_devices(module: Any) -> list[str]:
    command = "lsblk -e 7 -d | grep disk | awk '{print $1}'"
    result = _run_blk_device_command(module, command)
    return result.stdout.split()


def _print_blk_devices_header(disks: list[str]) -> None:
    _print_blk_devices_separator()
    print("                                                    Read block devices tool\n")
    print(BLK_DEVICE_BANNER)
    print("INFO: Detected following block devices with lsblk command :")
    for num, disk in enumerate(disks):
        print(f"{num}: {disk}")
    _print_blk_devices_separator()


def _detect_blk_partition_table(module: Any, disk: str) -> str:
    command = f"timeout 10 gdisk -l /dev/{disk}"
    result = _run_blk_device_command(module, command)
    if "MBR: MBR only" in result.stdout:
        return "MBR"
    if "GPT: present" in result.stdout:
        return "GPT"
    print(f"INFO: No valid partition table found for {disk}, treating as raw device.")
    return "RAW"


def _count_blk_partitions(module: Any, disk: str) -> int:
    command = f"lsblk -rn -o NAME,TYPE /dev/{disk} | grep -c part"
    result = _run_blk_device_command(module, command)
    num_parts_str = result.stdout.strip()
    return int(num_parts_str) if num_parts_str else 0


def _run_blk_read(module: Any, partition_label: str, context: str = "") -> bool:
    context_suffix = f" {context}" if context else ""
    print(f"INFO: Performing block read on /dev/{partition_label}{context_suffix}")
    command = f"dd if=/dev/{partition_label} bs=1M count=1 > /dev/null"
    result = _run_blk_device_command(module, command)
    outcome = "successful" if result.returncode == 0 else "failed"
    print(f"INFO: Block read on /dev/{partition_label}{context_suffix} {outcome}")
    return result.returncode == 0


def _print_precious_partition(
    module: Any,
    partition_label: str,
    identifier: str,
    precious_parts: Mapping[str, str],
    *,
    suffix: str = "",
) -> None:
    for key, value in precious_parts.items():
        if value != identifier:
            continue
        print(f"INFO: {partition_label} partition is PRECIOUS{suffix}")
        used_blocks, _ = module.get_partition_space(f"/dev/{partition_label}")
        print(
            "INFO: Number of 512B blocks used on "
            f"/dev/{partition_label}: {used_blocks}"
        )
        print(f"      {key} : {value}")
        print("      Skipping block read/write...")
        break


def _parse_mbr_partition_ids(fdisk_stdout: str) -> list[str]:
    table_header_row = [
        "Device",
        "Boot",
        "Start",
        "End",
        "Sectors",
        "Size",
        "Id",
        "Type",
    ]
    lines = fdisk_stdout.strip().split("\n")
    collect_lines = False
    mbr_part_ids: list[str] = []

    for line in lines:
        if collect_lines:
            columns = line.split()
            if len(columns) < 6:
                continue
            if columns[1] == "*" and len(columns) >= 7:
                mbr_part_ids.append("0x" + columns[6].upper())
            else:
                mbr_part_ids.append("0x" + columns[5].upper())
            continue
        if all(substring in line for substring in table_header_row):
            collect_lines = True

    return mbr_part_ids


def _parse_gpt_partition_info(
    module: Any,
    sgdisk_stdout: str,
) -> tuple[str, int] | None:
    guid_regex = r"Partition GUID code: ([\w-]+) \("
    attr_flag_regex = r"Attribute flags: ([0-9A-Fa-f]+)"
    guid_code_match = module.re.search(guid_regex, sgdisk_stdout)
    attribute_flags_match = module.re.search(attr_flag_regex, sgdisk_stdout)
    if not guid_code_match or not attribute_flags_match:
        return None

    partition_guid_code = guid_code_match.group(1)
    attribute_flags_hex = attribute_flags_match.group(1)
    attribute_flags_int = int(attribute_flags_hex, 16)
    return partition_guid_code, attribute_flags_int & 1


def _handle_raw_blk_device(module: Any, disk: str) -> None:
    print(f"INFO: No partitions detected for {disk}, treating as raw device.")
    if _run_blk_read(module, disk):
        module.perform_write_check(disk, "", {})
    _print_blk_devices_separator()


def _handle_mbr_blk_device(
    module: Any,
    disk: str,
    part_labels: list[str],
    num_parts: int,
) -> None:
    command = f"fdisk -l /dev/{disk}"
    result = _run_blk_device_command(module, command)
    mbr_part_ids = _parse_mbr_partition_ids(result.stdout)

    if len(mbr_part_ids) < num_parts:
        print(
            "WARNING: Could not parse enough MBR partition IDs. "
            f"Found {len(mbr_part_ids)}, expected {num_parts}."
        )

    process_count = min(len(part_labels), len(mbr_part_ids), num_parts)
    for index in range(process_count):
        part_label = part_labels[index]
        partition_id = mbr_part_ids[index]
        print(f"\nINFO: Partition : /dev/{part_label} Partition type : {partition_id}")

        if partition_id in module.precious_parts_mbr.values():
            _print_precious_partition(
                module,
                part_label,
                partition_id,
                module.precious_parts_mbr,
            )
            continue

        if _run_blk_read(module, part_label, f"mbr_part_id = {partition_id}"):
            module.perform_write_check(
                part_label,
                partition_id,
                module.precious_parts_mbr,
            )

    _print_blk_devices_separator()


def _handle_gpt_blk_device(
    module: Any,
    disk: str,
    part_labels: list[str],
    num_parts: int,
) -> None:
    process_count = min(len(part_labels), num_parts)
    for index in range(process_count):
        part_label = part_labels[index]
        command = f"sgdisk -i={index + 1} /dev/{disk}"
        result = _run_blk_device_command(module, command)
        parsed = _parse_gpt_partition_info(module, result.stdout)

        if parsed is None:
            print(f"INFO: Unable to parse sgdisk info for {part_label}. Skipping.")
            continue

        partition_guid_code, lsb = parsed
        print(
            f"\nINFO: Partition : /dev/{part_label} "
            f"Partition type GUID : {partition_guid_code} "
            f"\"Platform required bit\" : {lsb}"
        )

        if lsb == 1:
            print(
                "INFO: Platform required attribute set for "
                f"{part_label} partition, skipping block read/write..."
            )
            continue

        if partition_guid_code in module.precious_parts_gpt.values():
            _print_precious_partition(
                module,
                part_label,
                partition_guid_code,
                module.precious_parts_gpt,
                suffix=".",
            )
            continue

        if _run_blk_read(module, part_label, f"part_guid = {partition_guid_code}"):
            module.perform_write_check(
                part_label,
                partition_guid_code,
                module.precious_parts_gpt,
            )

    _print_blk_devices_separator()


def _process_blk_device(module: Any, disk: str) -> None:
    print(f"INFO: Block device : /dev/{disk}")
    part_table = _detect_blk_partition_table(module, disk)
    print(f"INFO: Partition table type : {part_table}\n")

    num_parts = _count_blk_partitions(module, disk)
    if part_table == "RAW" or num_parts == 0:
        _handle_raw_blk_device(module, disk)
        return

    part_labels = module.get_partition_labels(disk)
    if len(part_labels) < num_parts:
        print(
            "WARNING: Mismatch in partition count. Found "
            f"{len(part_labels)} partition labels, but lsblk reported "
            f"{num_parts} partitions for {disk}. Proceeding with the ones we have..."
        )

    if part_table == "MBR":
        _handle_mbr_blk_device(module, disk, part_labels, num_parts)
        return
    if part_table == "GPT":
        _handle_gpt_blk_device(module, disk, part_labels, num_parts)
        return

    print(
        "INFO: Invalid partition table, expected MBR or GPT "
        f"reported type = {part_table}"
    )


def _run_blk_devices_module_main() -> int:
    """
    Synthetic main() for block-device scripts that only define a main guard.

    This mirrors the repository script flow closely enough for YAML scenario
    tests while still exercising the target module's own helper functions.
    """
    module = _resolve_runner_module_from_stack()

    try:
        disks = _list_blk_devices(module)
        _print_blk_devices_header(disks)

        for disk in disks:
            if module.is_mtd_block_device(disk):
                print(f"INFO: Skipping MTD block device /dev/{disk}")
                continue

            if module.is_ram_disk(disk):
                print(f"INFO: Skipping RAM disk /dev/{disk}")
                continue

            _process_blk_device(module, disk)

        return 0
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Error occurred: {exc}")
        return 1


def build_blk_devices_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build runtime mocks for the block-device script main flow."""
    disks = scenario.get("disks", [])
    if disks is None:
        disks = []
    if not isinstance(disks, list):
        raise ConfigError("scenario.disks must be a list")

    prompt = _normalize_prompt_response(scenario.get("prompt", "no"))
    prompt_response = "no" if prompt == "timeout" else prompt
    call_log_path = str(work_dir / "blk_commands.log")
    disk_listing_lines: list[str] = []
    run_responses: dict[str, Any] = {}
    stateful_state: dict[str, Any] = {}
    stateful_rules: list[dict[str, Any]] = []

    for disk_index, disk in enumerate(disks, start=1):
        if not isinstance(disk, dict):
            raise ConfigError(f"scenario.disks[{disk_index}] must be a mapping")
        if "name" not in disk:
            raise ConfigError(f"scenario.disks[{disk_index}] requires key 'name'")

        disk_name = str(disk["name"])
        disk_listing_lines.append(f"{disk_name} disk")

        disk_kind = str(disk.get("kind", "disk")).lower()
        if disk_name.startswith("mtdblock") or disk_kind in {"mtd", "mtdblock"}:
            continue
        if disk_name.startswith("ram") or disk_kind == "ram":
            continue

        table = str(disk.get("table", "raw")).lower()
        if table not in {"raw", "mbr", "gpt"}:
            raise ConfigError(
                f"scenario.disks[{disk_index}].table must be one of raw, mbr, gpt"
            )

        partitions = disk.get("partitions", [])
        if partitions is None:
            partitions = []
        if not isinstance(partitions, list):
            raise ConfigError(f"scenario.disks[{disk_index}].partitions must be a list")

        reported_partition_count = disk.get("reported_partition_count", len(partitions))
        if not isinstance(reported_partition_count, int):
            raise ConfigError(
                f"scenario.disks[{disk_index}].reported_partition_count must be an integer"
            )

        gdisk_stdout = str(
            disk.get(
                "gdisk_output",
                (
                    "MBR: MBR only\n"
                    if table == "mbr"
                    else "GPT: present\n" if table == "gpt" else "no partition table here\n"
                ),
            )
        )
        if gdisk_stdout and not gdisk_stdout.endswith("\n"):
            gdisk_stdout += "\n"

        run_responses[f"timeout 10 gdisk -l /dev/{disk_name}"] = _completed_process_spec(
            stdout=gdisk_stdout
        )

        if table == "raw" or reported_partition_count == 0:
            run_responses[f"lsblk -rn -o NAME,TYPE /dev/{disk_name}"] = _completed_process_spec(
                stdout=""
            )
            run_responses[f"dd if=/dev/{disk_name} of=/dev/null bs=1M count=1"] = (
                build_run_result_from_outcome(disk.get("block_read", "pass"))
            )
            disk_write_cfg = disk.get("write_check") or disk
            _add_blk_write_check_run_responses(
                run_responses,
                disk_name,
                disk_write_cfg,
            )
            state, rules = _build_blk_write_check_stateful_rules(
                disk_name,
                disk_write_cfg,
            )
            stateful_state.update(state)
            stateful_rules.extend(rules)
            continue

        partition_labels: list[str] = []
        for part_index, partition in enumerate(partitions, start=1):
            if not isinstance(partition, dict):
                raise ConfigError(
                    f"scenario.disks[{disk_index}].partitions[{part_index}] must be a mapping"
                )
            partition_labels.append(str(partition.get("name", f"{disk_name}{part_index}")))

        lsblk_partition_lines = [f"{label} part" for label in partition_labels]
        run_responses[f"lsblk -rn -o NAME,TYPE /dev/{disk_name}"] = _completed_process_spec(
            stdout=_join_stdout_lines(lsblk_partition_lines)
        )

        if table == "mbr":
            fdisk_stdout = disk.get("fdisk_output")
            if fdisk_stdout is None:
                fdisk_stdout = build_fdisk_output(disk_name, partitions)
            else:
                fdisk_stdout = str(fdisk_stdout)
                if fdisk_stdout and not fdisk_stdout.endswith("\n"):
                    fdisk_stdout += "\n"

            run_responses[f"fdisk -l /dev/{disk_name}"] = _completed_process_spec(
                stdout=fdisk_stdout
            )

            for part_index, partition in enumerate(partitions, start=1):
                partition_name = str(partition.get("name", f"{disk_name}{part_index}"))
                partition_id = _normalize_mbr_partition_id(partition.get("id", "83"))

                if (
                    partition_id in PRECIOUS_MBR_IDS
                    or "used_blocks" in partition
                    or "available_blocks" in partition
                ):
                    run_responses[
                        f"df -B 512 /dev/{partition_name} --output=used,avail"
                    ] = _completed_process_spec(
                        stdout=build_df_output(
                            int(partition.get("used_blocks", 0)),
                            int(partition.get("available_blocks", 0)),
                        )
                    )

                if partition_id in PRECIOUS_MBR_IDS:
                    continue

                run_responses[
                    f"dd if=/dev/{partition_name} of=/dev/null bs=1M count=1"
                ] = build_run_result_from_outcome(partition.get("block_read", "pass"))
                partition_write_cfg = partition.get("write_check") or partition
                _add_blk_write_check_run_responses(
                    run_responses,
                    partition_name,
                    partition_write_cfg,
                )
                state, rules = _build_blk_write_check_stateful_rules(
                    partition_name,
                    partition_write_cfg,
                )
                stateful_state.update(state)
                stateful_rules.extend(rules)

            continue

        for part_index, partition in enumerate(partitions, start=1):
            partition_name = str(partition.get("name", f"{disk_name}{part_index}"))
            partition_guid = str(
                partition.get("guid", "0FC63DAF-8483-4772-8E79-3D69D8477DE4")
            ).upper()
            required = _platform_required(partition)

            sgdisk_stdout = partition.get("sgdisk_output")
            if sgdisk_stdout is None:
                sgdisk_stdout = build_sgdisk_partition_output(partition)
            else:
                sgdisk_stdout = str(sgdisk_stdout)
                if sgdisk_stdout and not sgdisk_stdout.endswith("\n"):
                    sgdisk_stdout += "\n"

            run_responses[f"sgdisk -i={part_index} /dev/{disk_name}"] = _completed_process_spec(
                stdout=sgdisk_stdout
            )

            if (
                partition_guid in PRECIOUS_GPT_GUIDS
                or required
                or "used_blocks" in partition
                or "available_blocks" in partition
            ):
                run_responses[
                    f"df -B 512 /dev/{partition_name} --output=used,avail"
                ] = _completed_process_spec(
                    stdout=build_df_output(
                        int(partition.get("used_blocks", 0)),
                        int(partition.get("available_blocks", 0)),
                    )
                )

            if partition_guid in PRECIOUS_GPT_GUIDS or required:
                continue

            run_responses[
                f"dd if=/dev/{partition_name} of=/dev/null bs=1M count=1"
            ] = build_run_result_from_outcome(partition.get("block_read", "pass"))
            partition_write_cfg = partition.get("write_check") or partition
            _add_blk_write_check_run_responses(
                run_responses,
                partition_name,
                partition_write_cfg,
            )
            state, rules = _build_blk_write_check_stateful_rules(
                partition_name,
                partition_write_cfg,
            )
            stateful_state.update(state)
            stateful_rules.extend(rules)

    run_responses["lsblk -e 7 -d -n -o NAME,TYPE"] = _completed_process_spec(
        stdout=_join_stdout_lines(disk_listing_lines)
    )

    run_mock_spec: dict[str, Any] = {
        "factory": run_router,
        "kwargs": {
            "responses": run_responses,
            "default_returncode": 1,
            "use_contains": False,
            "unmatched_stderr_template": "UNMOCKED COMMAND: {cmd}\n",
            "call_log_path": call_log_path,
        },
    }
    if stateful_rules:
        run_mock_spec = {
            "factory": stateful_run_router,
            "kwargs": {
                "state": stateful_state,
                "rules": stateful_rules,
                "responses": run_responses,
                "default_returncode": 1,
                "use_contains": False,
                "unmatched_stderr_template": "UNMOCKED COMMAND: {cmd}\n",
                "call_log_path": call_log_path,
            },
        }

    return {
        "mocks": {
            "{module}.input_with_timeout": {"return_value": prompt_response},
            "subprocess.run": run_mock_spec,
        },
    }


def build_blk_write_check_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build runtime mocks for direct perform_write_check scenarios."""
    device = scenario.get("device") or scenario.get("partition_label")
    if not isinstance(device, str) or not device.strip():
        raise ConfigError("blk_write_check requires string key 'device'")

    partition_id = str(scenario.get("partition_id", ""))
    precious_parts = scenario.get("precious_parts", {})
    if not isinstance(precious_parts, dict):
        raise ConfigError("blk_write_check.precious_parts must be a mapping")

    prompt = _normalize_prompt_response(scenario.get("prompt", "no"))
    prompt_result = "no" if prompt == "timeout" else prompt
    call_log_path = str(work_dir / "blk_commands.log")
    run_responses: dict[str, Any] = {}
    _add_blk_write_check_run_responses(run_responses, device, scenario)
    state, rules = _build_blk_write_check_stateful_rules(device, scenario)
    if not rules:
        return {
            "args": [device, partition_id, precious_parts],
            "mocks": {
                "{module}.input_with_timeout": {"return_value": prompt_result},
                "subprocess.run": {
                    "factory": run_router,
                    "kwargs": {
                        "responses": run_responses,
                        "default_returncode": 1,
                        "use_contains": False,
                        "unmatched_stderr_template": "UNMOCKED COMMAND: {cmd}\n",
                        "call_log_path": call_log_path,
                    },
                },
            },
        }

    return {
        "args": [device, partition_id, precious_parts],
        "mocks": {
            "{module}.input_with_timeout": {"return_value": prompt_result},
            "subprocess.run": {
                "factory": stateful_run_router,
                "kwargs": {
                    "state": state,
                    "rules": rules,
                    "responses": run_responses,
                    "default_returncode": 1,
                    "use_contains": False,
                    "unmatched_stderr_template": "UNMOCKED COMMAND: {cmd}\n",
                    "call_log_path": call_log_path,
                },
            },
        },
    }



def _readable_text_block(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _normalize_simple_key_value_text(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value if value.endswith("\n") or not value else value + "\n"
    if not isinstance(value, dict):
        raise ConfigError(f"{field_name} must be a string or mapping")
    return _readable_text_block([f"{key}: {item}" for key, item in value.items()])


def _normalize_json_text(value: Any, field_name: str) -> str:
    if isinstance(value, str):
        return value if value.endswith("\n") or not value else value + "\n"
    try:
        return json.dumps(value, indent=4) + "\n"
    except TypeError as exc:
        raise ConfigError(
            f"{field_name} must be a string or JSON-serializable value"
        ) from exc


def _normalize_text_block(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{field_name} must be a string")
    return value if value.endswith("\n") or not value else value + "\n"


def _build_merge_jsons_acs_info_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"ACS Results Summary": {"Overall Compliance Result": value}}
    if not isinstance(value, dict):
        raise ConfigError("merge_jsons.acs_info must be a string or mapping")

    if "ACS Results Summary" in value:
        summary = value["ACS Results Summary"]
        if not isinstance(summary, dict):
            raise ConfigError(
                "merge_jsons.acs_info['ACS Results Summary'] must be a mapping"
            )
        return dict(value)

    return {"ACS Results Summary": dict(value)}


def _build_dmidecode_text(spec: Any) -> str:
    if isinstance(spec, str):
        return spec if spec.endswith("\n") or not spec else spec + "\n"
    if not isinstance(spec, dict):
        raise ConfigError("acs_info.dmidecode must be a string or mapping")
    firmware = str(spec.get("firmware", spec.get("firmware_version", "Unknown")))
    vendor = str(spec.get("vendor", spec.get("manufacturer", "Unknown")))
    product = str(spec.get("product", spec.get("system_name", "Unknown")))
    family = str(spec.get("family", spec.get("soc_family", "Unknown")))
    return _readable_text_block([
        "Handle 0x0000, DMI type 0, 24 bytes",
        "BIOS Information",
        f"    Version: {firmware}",
        "",
        "Handle 0x0001, DMI type 1, 27 bytes",
        "System Information",
        f"    Manufacturer: {vendor}",
        f"    Product Name: {product}",
        f"    Family: {family}",
    ])


def build_acs_info_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build fixture files and args for acs_info.py."""
    output_dir = str(scenario.get("output_dir", "out"))
    args = ["--dmidecode_log", str(work_dir / "dmidecode.log")]
    text_files: dict[str, str] = {
        "dmidecode.log": _build_dmidecode_text(scenario.get("dmidecode", {})),
    }
    bin_files: dict[str, dict[str, str]] = {}

    acs_config = scenario.get("acs_config")
    if acs_config is not None:
        text_files["acs_config.txt"] = _normalize_simple_key_value_text(
            acs_config,
            "acs_info.acs_config",
        )
        args.extend(["--acs_config_path", str(work_dir / "acs_config.txt")])

    system_config = scenario.get("system_config")
    if system_config is not None:
        text_files["system_config.txt"] = _normalize_simple_key_value_text(
            system_config,
            "acs_info.system_config",
        )
        args.extend(["--system_config_path", str(work_dir / "system_config.txt")])

    ipmitool = scenario.get("ipmitool")
    if ipmitool is not None:
        if isinstance(ipmitool, str):
            text_files["ipmitool.log"] = (
                ipmitool
                if ipmitool.endswith("\n") or not ipmitool
                else ipmitool + "\n"
            )
        elif isinstance(ipmitool, dict):
            fw_rev = ipmitool.get(
                "firmware_revision",
                ipmitool.get("Firmware Revision", "Unknown"),
            )
            text_files["ipmitool.log"] = _readable_text_block(
                [
                    "Device ID                 : 32",
                    f"Firmware Revision         : {fw_rev}",
                ]
            )
        else:
            raise ConfigError("acs_info.ipmitool must be a string or mapping")
        args.extend(["--ipmitool_log", str(work_dir / "ipmitool.log")])

    uefi_version = scenario.get("uefi_version")
    if uefi_version is not None:
        encoding = "utf-8"
        value = uefi_version
        if isinstance(uefi_version, dict):
            value = str(uefi_version.get("text", ""))
            encoding = str(uefi_version.get("encoding", "utf-8"))
        elif not isinstance(uefi_version, str):
            raise ConfigError("acs_info.uefi_version must be a string or mapping")
        payload = str(value)
        if payload and not payload.endswith("\n"):
            payload += "\n"
        bin_files["uefi_version.log"] = {"hex": payload.encode(encoding).hex()}
        args.extend(["--uefi_version_log", str(work_dir / "uefi_version.log")])

    args.extend(["--output_dir", str(work_dir / output_dir)])
    generated: dict[str, Any] = {"args": args, "text_files": text_files}
    if bin_files:
        generated["bin_files"] = bin_files
    return generated


def _build_merge_jsons_module_main(
    *,
    work_dir: Path,
    input_files: list[str],
    output_files: list[str],
    dt_or_sr_mode: str | None = None,
    yocto_flag_path: str | None = None,
) -> Any:
    def _run_merge_jsons_module_main() -> int:
        module = _resolve_runner_module_from_stack()

        if yocto_flag_path is not None:
            setattr(
                module,
                "YOCTO_FLAG_PATH",
                str((work_dir / yocto_flag_path).resolve()),
            )
        if dt_or_sr_mode is not None:
            setattr(module, "DT_OR_SR_MODE", dt_or_sr_mode)

        resolved_inputs = [
            str((work_dir / input_name).resolve()) for input_name in input_files
        ]
        for output_name in output_files:
            module.merge_json_files(
                resolved_inputs,
                str((work_dir / output_name).resolve()),
            )
        return 0

    return _run_merge_jsons_module_main


def build_merge_jsons_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    text_files: dict[str, str] = {}
    input_names: list[str] = []

    def _append_input(
        name: Any,
        *,
        field_name: str,
        content: str | None = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{field_name} must be a non-empty string")
        if content is not None:
            if name in text_files:
                raise ConfigError(f"Duplicate merge_jsons input file: {name}")
            text_files[name] = content
        input_names.append(name)

    acs_info = scenario.get("acs_info")
    if acs_info is not None:
        acs_info_name = scenario.get("acs_info_name", "acs_info.json")
        _append_input(
            acs_info_name,
            field_name="merge_jsons.acs_info_name",
            content=_normalize_json_text(
                _build_merge_jsons_acs_info_payload(acs_info),
                "merge_jsons.acs_info",
            ),
        )

    input_files = scenario.get("input_files")
    if input_files is not None:
        if not isinstance(input_files, dict):
            raise ConfigError("merge_jsons.input_files must be a mapping")
        for name, content in input_files.items():
            _append_input(
                name,
                field_name=f"merge_jsons.input_files[{name!r}]",
                content=_normalize_json_text(
                    content,
                    f"merge_jsons.input_files[{name!r}]",
                ),
            )

    invalid_files = scenario.get("invalid_files")
    if invalid_files is not None:
        if not isinstance(invalid_files, dict):
            raise ConfigError("merge_jsons.invalid_files must be a mapping")
        for name, content in invalid_files.items():
            _append_input(
                name,
                field_name=f"merge_jsons.invalid_files[{name!r}]",
                content=_normalize_text_block(
                    content,
                    f"merge_jsons.invalid_files[{name!r}]",
                ),
            )

    missing_input_files = scenario.get("missing_input_files", [])
    if missing_input_files is not None:
        if not isinstance(missing_input_files, list) or not all(
            isinstance(item, str) and item.strip() for item in missing_input_files
        ):
            raise ConfigError(
                "merge_jsons.missing_input_files must be a list of strings"
            )
        for name in missing_input_files:
            _append_input(
                name,
                field_name="merge_jsons.missing_input_files[]",
            )

    if not input_names:
        raise ConfigError(
            "merge_jsons scenario requires at least one input via "
            "acs_info, input_files, invalid_files, or missing_input_files"
        )

    raw_output_files = scenario.get("output_files", scenario.get("output_file", "merged.json"))
    if isinstance(raw_output_files, str):
        output_files = [raw_output_files]
    elif isinstance(raw_output_files, list) and all(
        isinstance(item, str) and item.strip() for item in raw_output_files
    ):
        output_files = list(raw_output_files)
    else:
        raise ConfigError(
            "merge_jsons.output_files must be a string or a list of strings"
        )

    dt_or_sr_mode = scenario.get("dt_or_sr_mode")
    if dt_or_sr_mode is not None:
        if not isinstance(dt_or_sr_mode, str) or dt_or_sr_mode not in {"DT", "SR"}:
            raise ConfigError("merge_jsons.dt_or_sr_mode must be 'DT' or 'SR'")

    yocto_flag_path = scenario.get("yocto_flag_path")
    if yocto_flag_path is not None:
        if not isinstance(yocto_flag_path, str) or not yocto_flag_path.strip():
            raise ConfigError(
                "merge_jsons.yocto_flag_path must be a non-empty string"
            )
        text_files.setdefault(yocto_flag_path, "")

    generated_case = {
        "args": [
            str((work_dir / output_files[0]).resolve()),
            *[str((work_dir / input_name).resolve()) for input_name in input_names],
        ]
        if len(output_files) == 1
        else [],
        "patch_constants": {
            "main": _build_merge_jsons_module_main(
                work_dir=work_dir,
                input_files=input_names,
                output_files=output_files,
                dt_or_sr_mode=dt_or_sr_mode,
                yocto_flag_path=yocto_flag_path,
            ),
        },
        "text_files": text_files,
    }
    return generated_case


def build_extract_capsule_fw_version_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build fixture files and args for extract_capsule_fw_version.py."""
    pattern = scenario.get("pattern")
    if not isinstance(pattern, str) or not pattern.strip():
        raise ConfigError("extract_capsule_fw_version.pattern must be a non-empty string")

    input_name = str(scenario.get("input_name", "input.log"))
    raw_input = scenario.get("input_text")
    if raw_input is None:
        lines = scenario.get("input_lines", [])
        if not isinstance(lines, list) or not all(isinstance(item, str) for item in lines):
            raise ConfigError("extract_capsule_fw_version.input_lines must be a list of strings")
        raw_input = _readable_text_block(lines)
    elif not isinstance(raw_input, str):
        raise ConfigError("extract_capsule_fw_version.input_text must be a string")
    if raw_input and not raw_input.endswith("\n"):
        raw_input += "\n"

    return {
        "args": [pattern, str(work_dir / input_name)],
        "text_files": {input_name: raw_input},
    }

def _ensure_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{field_name} must be a list of strings")
    return list(value)


def _normalize_verify_tpm_banks(value: Any, field_name: str) -> dict[str, list[str]]:
    if not isinstance(value, dict) or not value:
        raise ConfigError(f"{field_name} must be a non-empty mapping")

    normalized: dict[str, list[str]] = {}
    for algo, entries in value.items():
        if not isinstance(algo, str):
            raise ConfigError(f"{field_name} keys must be strings")
        if not isinstance(entries, list) or not all(isinstance(item, str) for item in entries):
            raise ConfigError(f"{field_name}.{algo} must be a list of strings")
        normalized[algo] = list(entries)
    return normalized


def _verify_tpm_event(
    event_num: int,
    pcr_index: int,
    event_type: str,
    *,
    event: Any = None,
    spec_version_major: int | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "EventNum": event_num,
        "PCRIndex": pcr_index,
        "EventType": event_type,
    }
    if spec_version_major is not None:
        entry["SpecID"] = [{"specVersionMajor": spec_version_major}]
    elif event is not None:
        entry["Event"] = event
    return entry


def build_verify_tpm_events(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the default event list for verify_tpm_measurements.py."""
    if "events" in scenario:
        explicit_events = scenario["events"]
        if not isinstance(explicit_events, list):
            raise ConfigError("verify_tpm.events must be a list when provided")
        return list(explicit_events)

    spec_version_major = int(scenario.get("spec_version_major", 2))
    post_code_events = _ensure_string_list(
        scenario.get("post_code_events", ["BL_31", "SECURE_RT_EL3"]),
        "verify_tpm.post_code_events",
    )
    secure_boot_vars = _ensure_string_list(
        scenario.get("secure_boot_vars", ["SecureBoot", "PK", "KEK", "db", "dbx"]),
        "verify_tpm.secure_boot_vars",
    )
    boot_variables = _ensure_string_list(
        scenario.get("boot_variables", ["BootOrder", "Boot0001"]),
        "verify_tpm.boot_variables",
    )
    handoff_events = _ensure_string_list(
        scenario.get("handoff_events", ["SMBIOS"]),
        "verify_tpm.handoff_events",
    )
    table_of_devices = _ensure_string_list(
        scenario.get("table_of_devices", ["SYS_CONFIG_UART0"]),
        "verify_tpm.table_of_devices",
    )

    separator_pcrs = scenario.get("separator_pcrs", list(range(8)))
    if not isinstance(separator_pcrs, list) or not all(
        isinstance(item, int) for item in separator_pcrs
    ):
        raise ConfigError("verify_tpm.separator_pcrs must be a list of integers")

    boot_attempt = scenario.get("boot_attempt", "Calling EFI Application from Boot Option")
    if boot_attempt is not None and not isinstance(boot_attempt, str):
        raise ConfigError("verify_tpm.boot_attempt must be a string or null")

    exit_boot_services = scenario_truthy(
        scenario.get("exit_boot_services"),
        default=True,
    )

    events: list[dict[str, Any]] = []
    next_event_num = 1

    events.append(
        _verify_tpm_event(
            next_event_num,
            0,
            "EV_NO_ACTION",
            spec_version_major=spec_version_major,
        )
    )
    next_event_num += 1

    for item in post_code_events:
        events.append(_verify_tpm_event(next_event_num, 0, "EV_POST_CODE", event=item))
        next_event_num += 1

    for var_name in secure_boot_vars:
        events.append(
            _verify_tpm_event(
                next_event_num,
                7,
                "EV_EFI_VARIABLE_DRIVER_CONFIG",
                event={"UnicodeName": var_name},
            )
        )
        next_event_num += 1

    for var_name in boot_variables:
        event_type = "EV_EFI_VARIABLE_BOOT" if var_name == "BootOrder" else "EV_EFI_VARIABLE_BOOT2"
        events.append(
            _verify_tpm_event(
                next_event_num,
                1,
                event_type,
                event={"UnicodeName": var_name},
            )
        )
        next_event_num += 1

    if boot_attempt is not None:
        events.append(
            _verify_tpm_event(
                next_event_num,
                4,
                "EV_EFI_ACTION",
                event=boot_attempt,
            )
        )
        next_event_num += 1

    for item in handoff_events:
        events.append(
            _verify_tpm_event(next_event_num, 1, "EV_EFI_HANDOFF_TABLES", event=item)
        )
        next_event_num += 1

    for pcr_index in separator_pcrs:
        events.append(
            _verify_tpm_event(
                next_event_num,
                pcr_index,
                "EV_SEPARATOR",
                event=f"sep{pcr_index}",
            )
        )
        next_event_num += 1

    for item in table_of_devices:
        events.append(
            _verify_tpm_event(next_event_num, 1, "EV_TABLE_OF_DEVICES", event=item)
        )
        next_event_num += 1

    if exit_boot_services:
        events.append(
            _verify_tpm_event(
                next_event_num,
                5,
                "EV_EFI_ACTION",
                event="Exit Boot Services Invocation",
            )
        )

    return events


def build_verify_tpm_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build runtime files and args for verify_tpm_measurements.py scenarios."""
    pcr_banks = _normalize_verify_tpm_banks(scenario.get("pcrs"), "verify_tpm.pcrs")
    event_pcrs = _normalize_verify_tpm_banks(
        scenario.get("event_pcrs", pcr_banks),
        "verify_tpm.event_pcrs",
    )

    event_log_raw = scenario.get("event_log_raw")
    if event_log_raw is not None:
        if not isinstance(event_log_raw, str):
            raise ConfigError("verify_tpm.event_log_raw must be a string")
        event_contents = event_log_raw
        if event_contents and not event_contents.endswith("\n"):
            event_contents += "\n"
    else:
        event_doc = {
            "pcrs": event_pcrs,
            "events": build_verify_tpm_events(scenario),
        }
        event_contents = json.dumps(event_doc, indent=2) + "\n"

    pcr_contents = json.dumps(pcr_banks, indent=2) + "\n"
    pcr_path = work_dir / "pcr.yaml"
    event_path = work_dir / "event.yaml"

    generated: dict[str, Any] = {
        "args": [str(pcr_path), str(event_path)],
        "text_files": {
            "pcr.yaml": pcr_contents,
            "event.yaml": event_contents,
        },
    }

    mocks: dict[str, Any] = {}

    event_log_open_error = scenario.get("event_log_open_error")
    if event_log_open_error is not None:
        if not isinstance(event_log_open_error, str) or not event_log_open_error.strip():
            raise ConfigError(
                "verify_tpm.event_log_open_error must be a non-empty string"
            )
        mocks["builtins.open"] = {
            "factory": "mock_helpers.passthrough_router",
            "inject_original_as": "real",
            "kwargs": {
                "label": "verify-tpm-open-router",
                "rules": [
                    {
                        "label": "event-log-open-error",
                        "required": True,
                        "when": {
                            "args": {
                                0: {"equals": str(event_path)},
                                1: {"contains": "r"},
                            }
                        },
                        "raise": {
                            "type": "py:builtins.OSError",
                            "args": [event_log_open_error],
                        },
                    }
                ],
            },
        }

    event_log_yaml_error = scenario.get("event_log_yaml_error")
    if event_log_yaml_error is not None:
        if not isinstance(event_log_yaml_error, str) or not event_log_yaml_error.strip():
            raise ConfigError(
                "verify_tpm.event_log_yaml_error must be a non-empty string"
            )
        mocks["yaml.safe_load"] = {
            "factory": "mock_helpers.passthrough_router",
            "inject_original_as": "real",
            "kwargs": {
                "label": "verify-tpm-yaml-router",
                "rules": [
                    {
                        "label": "event-log-yaml-error",
                        "required": True,
                        "when": {
                            "args": {
                                0: {"contains": str(event_path)},
                            }
                        },
                        "raise": {
                            "type": "py:yaml.YAMLError",
                            "args": [event_log_yaml_error],
                        },
                    }
                ],
            },
        }

    if mocks:
        generated["mocks"] = mocks

    return generated


CAPSULE_REPORT_GUID = "39b68c46-f7fb-441b-b6ec-16b0f69821f3"
GLOBAL_VARIABLE_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
DEFAULT_ATTR_CAPSULE_MAX = 0x06
DEFAULT_ATTR_CAPSULE_LAST = 0x07
DEFAULT_ATTR_CAPSULE_NNNN = 0x07
DEFAULT_ATTR_OS_INDICATIONS = 0x07
FILE_CAPSULE_DELIVERY_SUPPORTED = 0x4


def _parse_int_like(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ConfigError(f"{field_name} must not be empty")
        try:
            return int(text, 0)
        except ValueError as exc:
            raise ConfigError(
                f"{field_name} must be an integer or int-like string"
            ) from exc
    raise ConfigError(f"{field_name} must be an integer or int-like string")


def _decode_hex_bytes(hex_text: str, field_name: str) -> bytes:
    try:
        return bytes.fromhex(hex_text)
    except ValueError as exc:
        raise ConfigError(f"{field_name} contains invalid hex data") from exc


def _resolve_case_relative_path(work_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else work_dir / candidate


def _build_capsule_named_var_bytes(
    spec: Any,
    *,
    default_attrs: int,
    field_name: str,
) -> bytes:
    if isinstance(spec, str):
        return build_efi_var_bytes(default_attrs, build_char16_payload(spec))

    if not isinstance(spec, dict):
        raise ConfigError(f"{field_name} must be a string or mapping")

    if "hex" in spec:
        return _decode_hex_bytes(str(spec["hex"]), f"{field_name}.hex")

    attrs = _parse_int_like(spec.get("attrs", default_attrs), f"{field_name}.attrs")

    if "payload_hex" in spec:
        payload = _decode_hex_bytes(
            str(spec["payload_hex"]),
            f"{field_name}.payload_hex",
        )
    else:
        name = spec.get("name", spec.get("value", ""))
        if not isinstance(name, str):
            raise ConfigError(f"{field_name}.name must be a string")
        extra_utf16 = spec.get("extra_utf16", "")
        if not isinstance(extra_utf16, str):
            raise ConfigError(f"{field_name}.extra_utf16 must be a string")
        payload = build_char16_payload(name, extra_utf16)

    return build_efi_var_bytes(attrs, payload)


def _build_capsule_entry_bytes(
    spec: Any,
    *,
    field_name: str,
) -> tuple[str, bytes]:
    if isinstance(spec, str):
        return spec, build_efi_var_bytes(
            DEFAULT_ATTR_CAPSULE_NNNN,
            _decode_hex_bytes("AA", f"{field_name}.payload_hex"),
        )

    if not isinstance(spec, dict):
        raise ConfigError(f"{field_name} entries must be strings or mappings")

    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"{field_name}.name must be a non-empty string")

    if "hex" in spec:
        payload_bytes = _decode_hex_bytes(str(spec["hex"]), f"{field_name}.hex")
        return name, payload_bytes

    attrs = _parse_int_like(
        spec.get("attrs", DEFAULT_ATTR_CAPSULE_NNNN),
        f"{field_name}.attrs",
    )
    payload_hex = str(spec.get("payload_hex", "AA"))
    payload = _decode_hex_bytes(payload_hex, f"{field_name}.payload_hex")
    return name, build_efi_var_bytes(attrs, payload)


def _build_os_indications_bytes(spec: Any) -> bytes:
    if isinstance(spec, bool):
        value = FILE_CAPSULE_DELIVERY_SUPPORTED if spec else 0
        return build_os_indications_var(value, attrs=DEFAULT_ATTR_OS_INDICATIONS)

    if isinstance(spec, (int, str)):
        value = _parse_int_like(spec, "capsule_vars.os_indications")
        return build_os_indications_var(value, attrs=DEFAULT_ATTR_OS_INDICATIONS)

    if not isinstance(spec, dict):
        raise ConfigError(
            "capsule_vars.os_indications must be a bool, int-like, or mapping"
        )

    if "hex" in spec:
        return _decode_hex_bytes(
            str(spec["hex"]),
            "capsule_vars.os_indications.hex",
        )

    attrs = _parse_int_like(
        spec.get("attrs", DEFAULT_ATTR_OS_INDICATIONS),
        "capsule_vars.os_indications.attrs",
    )
    if "value" in spec:
        value = _parse_int_like(
            spec["value"],
            "capsule_vars.os_indications.value",
        )
    else:
        supported = scenario_truthy(spec.get("supported"), default=False)
        value = FILE_CAPSULE_DELIVERY_SUPPORTED if supported else 0
    return build_os_indications_var(value, attrs=attrs)


def build_capsule_vars_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build efivarfs fixtures and default module patches for capsule variable checks."""
    efivar_dir_raw = scenario.get("efivar_dir", "efivars")
    if not isinstance(efivar_dir_raw, str) or not efivar_dir_raw.strip():
        raise ConfigError("capsule_vars.efivar_dir must be a non-empty string")
    log_file_raw = scenario.get("log_file", "capsule.log")
    if not isinstance(log_file_raw, str) or not log_file_raw.strip():
        raise ConfigError("capsule_vars.log_file must be a non-empty string")

    efivar_path = _resolve_case_relative_path(work_dir, efivar_dir_raw)
    log_file_path = _resolve_case_relative_path(work_dir, log_file_raw)
    efivarfs_present = scenario_truthy(
        scenario.get("efivarfs_present"),
        default=True,
    )

    generated: dict[str, Any] = {
        "patch_constants": {
            "EFIVAR_PATH": str(efivar_path),
            "LOG_FILE": str(log_file_path),
        }
    }

    if not efivarfs_present:
        return generated

    generated["dir_structure"] = [{"path": str(efivar_path.relative_to(work_dir))}]
    bin_files: dict[str, dict[str, str]] = {}

    def add_var(filename: str, payload: bytes) -> None:
        rel_path = str((efivar_path.relative_to(work_dir) / filename).as_posix())
        bin_files[rel_path] = {"hex": payload.hex()}

    os_indications = scenario.get("os_indications")
    if os_indications is not None:
        add_var(
            f"OsIndicationsSupported-{GLOBAL_VARIABLE_GUID}",
            _build_os_indications_bytes(os_indications),
        )

    capsule_max = scenario.get("capsule_max")
    if capsule_max is not None:
        add_var(
            f"CapsuleMax-{CAPSULE_REPORT_GUID}",
            _build_capsule_named_var_bytes(
                capsule_max,
                default_attrs=DEFAULT_ATTR_CAPSULE_MAX,
                field_name="capsule_vars.capsule_max",
            ),
        )

    capsule_last = scenario.get("capsule_last")
    if capsule_last is not None:
        add_var(
            f"CapsuleLast-{CAPSULE_REPORT_GUID}",
            _build_capsule_named_var_bytes(
                capsule_last,
                default_attrs=DEFAULT_ATTR_CAPSULE_LAST,
                field_name="capsule_vars.capsule_last",
            ),
        )

    capsule_entries = scenario.get("capsule_entries", [])
    if capsule_entries is None:
        capsule_entries = []
    if not isinstance(capsule_entries, list):
        raise ConfigError("capsule_vars.capsule_entries must be a list")

    for index, entry in enumerate(capsule_entries, start=1):
        name, payload = _build_capsule_entry_bytes(
            entry,
            field_name=f"capsule_vars.capsule_entries[{index}]",
        )
        add_var(f"{name}-{CAPSULE_REPORT_GUID}", payload)

    if bin_files:
        generated["bin_files"] = bin_files

    return generated


def build_runtime_device_mapping_scenario_case(
    scenario: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Build DTS and memmap fixtures for runtime_device_mapping_conflict_checker.py."""
    text_files: dict[str, str] = {}
    bin_files: dict[str, dict[str, str]] = {}
    mocks: dict[str, Any] = {}

    dts_path = work_dir / "device_tree.dts"
    memmap_path = work_dir / "memmap.log"
    log_path = work_dir / "runtime_device_mapping_conflict_test.log"

    dts = scenario.get("dts")
    memmap = scenario.get("memmap")
    memmap_hex = scenario.get("memmap_hex")
    missing_dts = scenario_truthy(scenario.get("missing_dts"), default=False)
    missing_memmap = scenario_truthy(scenario.get("missing_memmap"), default=False)
    log_open_error = scenario.get("log_open_error")

    if missing_dts and dts is not None:
        raise ConfigError(
            "runtime_device_mapping cannot define both dts and missing_dts"
        )
    if missing_memmap and (memmap is not None or memmap_hex is not None):
        raise ConfigError(
            "runtime_device_mapping cannot define memmap/memmap_hex together with "
            "missing_memmap"
        )
    if log_open_error is not None and (
        not isinstance(log_open_error, str) or not log_open_error.strip()
    ):
        raise ConfigError(
            "runtime_device_mapping.log_open_error must be a non-empty string"
        )

    if dts is not None:
        if not isinstance(dts, str):
            raise ConfigError("runtime_device_mapping.dts must be a string")
        text_files["device_tree.dts"] = dts

    if memmap is not None and memmap_hex is not None:
        raise ConfigError(
            "runtime_device_mapping cannot define both memmap and memmap_hex"
        )

    if memmap is not None:
        if not isinstance(memmap, str):
            raise ConfigError("runtime_device_mapping.memmap must be a string")
        text_files["memmap.log"] = memmap

    if memmap_hex is not None:
        if not isinstance(memmap_hex, str):
            raise ConfigError("runtime_device_mapping.memmap_hex must be a string")
        bin_files["memmap.log"] = {"hex": memmap_hex}

    if log_open_error is not None:
        mocks["pathlib.Path.open"] = {
            "factory": "mock_helpers.passthrough_router",
            "inject_original_as": "real",
            "kwargs": {
                "label": "runtime-device-mapping-open-router",
                "rules": [
                    {
                        "label": "runtime-log-open-error",
                        "required": True,
                        "when": {
                            "args": {
                                0: {"equals": log_path},
                            }
                        },
                        "raise": {
                            "type": "py:builtins.OSError",
                            "args": [log_open_error],
                        },
                    }
                ],
            },
        }

    generated: dict[str, Any] = {
        "patch_constants": {
            "DTS_PATH": dts_path,
            "MEMMAP_PATH": memmap_path,
            "OUT_LOG_PATH": log_path,
        }
    }

    if text_files:
        generated["text_files"] = text_files

    if bin_files:
        generated["bin_files"] = bin_files

    if mocks:
        generated["mocks"] = mocks

    return generated


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
