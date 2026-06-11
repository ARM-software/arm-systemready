from __future__ import annotations

import re
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess
from typing import Any
from unittest.mock import Mock


def noop(*args: Any, **kwargs: Any) -> None:
    """Simple no-op helper for replacing sleeps and signal handlers."""
    del args, kwargs


def basic_mock(**kwargs: Any) -> Mock:
    """
    Generic Mock factory.

    Example:
      factory: mock_helpers.basic_mock
      attrs:
        return_value: 123
    """
    return Mock(**kwargs)


def completed_process_mock(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> Mock:
    """
    Mock for subprocess.run returning a CompletedProcess-like object.
    """
    mock_obj = Mock()
    mock_obj.return_value = CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
    return mock_obj


def simple_check_output(output: str = "", as_bytes: bool = True):
    """
    Mock factory for subprocess.check_output with one fixed output.
    """
    def _mock_check_output(*args, **kwargs):
        del args, kwargs
        return output.encode() if as_bytes else output

    return _mock_check_output


def _pick_routed_value(value: Any, state: dict[str, int], key: str) -> Any:
    """Return a routed value, supporting sticky sequential lists."""
    if not isinstance(value, list):
        return value
    if not value:
        raise ValueError("Router response lists must not be empty")
    index = state.get(key, 0)
    state[key] = index + 1
    if index >= len(value):
        return value[-1]
    return value[index]


def check_output_router(
    responses: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    default_output: str = "",
    as_bytes: bool = True,
    use_contains: bool = True,
):
    """
    Route subprocess.check_output return values based on command text.

    responses:
      "ip link": "eth0\\neth1\\n"
      "ethtool eth0": "Link detected: yes\\n"

    errors:
      "ethtool eth9": "No such device"
    """
    responses = responses or {}
    errors = errors or {}
    call_state: dict[str, int] = {}

    def _match(pattern: str, cmd_text: str) -> bool:
        if pattern.startswith("regex:"):
            return re.search(pattern[6:], cmd_text) is not None
        if use_contains:
            return pattern in cmd_text
        return pattern == cmd_text

    def _mock_check_output(cmd, *args, **kwargs):
        del args, kwargs
        cmd_text = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)

        for pattern, output in responses.items():
            if _match(pattern, cmd_text):
                selected = _pick_routed_value(output, call_state, pattern)
                return selected.encode() if as_bytes else selected

        for pattern, error_text in errors.items():
            if _match(pattern, cmd_text):
                selected = _pick_routed_value(error_text, call_state, f"error:{pattern}")
                raise CalledProcessError(1, cmd, output=selected)

        return default_output.encode() if as_bytes else default_output

    return _mock_check_output


def run_router(
    responses: dict[str, Any] | None = None,
    **options: Any,
):
    """
    Route subprocess.run behavior based on command text.

    responses format:
      "lsblk": {"stdout": "sda\\n", "stderr": "", "returncode": 0}
      "dd": {"stdout": "", "stderr": "write fail", "returncode": 1}
    """
    responses = responses or {}
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
        raise TypeError(f"Unsupported run_router option(s): {unsupported}")

    call_state: dict[str, int] = {}

    def _match(pattern: str, cmd_text: str) -> bool:
        if pattern.startswith("regex:"):
            return re.search(pattern[6:], cmd_text) is not None
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

        for pattern, result in responses.items():
            if _match(pattern, cmd_text):
                resolved = _pick_routed_value(result, call_state, pattern)
                if not isinstance(resolved, dict):
                    raise TypeError("run_router responses must resolve to mappings")
                return CompletedProcess(
                    args=cmd,
                    returncode=resolved.get("returncode", 0),
                    stdout=resolved.get("stdout", ""),
                    stderr=resolved.get("stderr", ""),
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


def path_read_text_router(
    responses: dict[str, str] | None = None,
    default_text: str = "",
    use_contains: bool = True,
):
    """
    Router for Path.read_text() based on path string.

    responses:
      "/sys/class/net/eth0/speed": "1000"
    """
    responses = responses or {}

    def _match(pattern: str, path_text: str) -> bool:
        if pattern.startswith("regex:"):
            return re.search(pattern[6:], path_text) is not None
        if use_contains:
            return pattern in path_text
        return pattern == path_text

    def _mock_read_text(self, *args, **kwargs):
        del args, kwargs
        path_text = str(self)

        for pattern, text in responses.items():
            if _match(pattern, path_text):
                return text

        return default_text

    return _mock_read_text


def which_return(value: str | None):
    """
    Mock shutil.which return value.
    """
    mock_obj = Mock()
    mock_obj.return_value = value
    return mock_obj


def which_router(
    responses: dict[str, str | None] | None = None,
    default: str | None = None,
):
    """Route shutil.which(...) results by tool name."""
    responses = responses or {}

    def _mock_which(name: str, *args, **kwargs):
        del args, kwargs
        return responses.get(name, default)

    return _mock_which


def scenario_truthy(value: Any, *, default: bool = False) -> bool:
    """Coerce common YAML-ish truthy values used in scenario definitions."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "present",
            "up",
            "pass",
            "passed",
            "on",
        }
    return bool(value)


def normalize_ethtool_tool_path(tool_name: str, raw_value: Any) -> str | None:
    """Normalize a scenario tool entry into a concrete which() return value."""
    if raw_value is None:
        return None

    default_path = "/usr/sbin/ethtool" if tool_name == "ethtool" else f"/usr/bin/{tool_name}"
    if isinstance(raw_value, bool):
        return default_path if raw_value else None
    if not isinstance(raw_value, str):
        raise TypeError(
            f"scenario.tools['{tool_name}'] must be a string or boolean, "
            f"got {type(raw_value).__name__}"
        )

    lowered = raw_value.strip().lower()
    if lowered in {"present", "yes", "true"}:
        return default_path
    if lowered in {"absent", "no", "false", ""}:
        return None
    return raw_value


def normalize_ip_entries(
    value: Any,
    *,
    default_dynamic: bool = False,
) -> list[dict[str, Any]]:
    """Normalize IPv4/IPv6 scenario entries into a list of address mappings."""
    if value is None:
        return []

    raw_items = [value] if isinstance(value, (str, dict)) else value
    if not isinstance(raw_items, list):
        raise TypeError("scenario ipv4/ipv6 entries must be a list, string, or mapping")

    entries: list[dict[str, Any]] = []
    for item in raw_items:
        if isinstance(item, str):
            entries.append({"address": item, "dynamic": default_dynamic})
            continue
        if not isinstance(item, dict):
            raise TypeError("scenario ipv4/ipv6 entries must be strings or mappings")
        address = item.get("address")
        if not isinstance(address, str):
            raise TypeError("scenario ip entries require a string 'address'")
        entries.append(
            {
                "address": address,
                "dynamic": scenario_truthy(item.get("dynamic"), default=default_dynamic),
            }
        )
    return entries


def build_ip_link_flags(kind: str, state: str) -> str:
    """Render the flags field used by `ip link` output."""
    flags = ["LOOPBACK"] if kind == "loopback" else ["BROADCAST", "MULTICAST"]
    if state.lower() == "up":
        flags.append("UP")
    return ",".join(flags)


def build_ethtool_ip_link_line(index: int, iface: dict[str, Any]) -> str:
    """Render one line from `ip -o link` for an ethtool scenario interface."""
    name = iface["name"]
    kind = iface.get("kind", "physical")
    state = str(iface.get("state", "down")).upper()
    mtu = int(iface.get("mtu", 65536 if kind == "loopback" else 1500))
    flags = build_ip_link_flags(kind, state)

    if kind == "loopback":
        return (
            f"{index}: {name}: <{flags}> mtu {mtu} qdisc noop "
            f"state {state} mode DEFAULT group default qlen 1000"
        )

    mac = iface.get("mac", f"02:00:00:00:00:{index:02x}")
    return (
        f"{index}: {name}: <{flags}> mtu {mtu} qdisc noop state {state} "
        f"mode DEFAULT group default qlen 1000 link/ether {mac}"
    )


def build_ethtool_ip_link_show_line(index: int, iface: dict[str, Any]) -> str:
    """Render one line from `ip link show <iface>`."""
    name = iface["name"]
    kind = iface.get("kind", "physical")
    state = str(iface.get("state", "down")).upper()
    mtu = int(iface.get("mtu", 65536 if kind == "loopback" else 1500))
    flags = build_ip_link_flags(kind, state)
    return f"{index}: {name}: <{flags}> mtu {mtu} state {state}\n"


def build_ethtool_ip_address_output(index: int, iface: dict[str, Any]) -> str:
    """Render `ip address show dev <iface>` output for a scenario interface."""
    name = iface["name"]
    kind = iface.get("kind", "physical")
    state = str(iface.get("state", "down")).upper()
    mtu = int(iface.get("mtu", 65536 if kind == "loopback" else 1500))
    flags = build_ip_link_flags(kind, state)

    lines = [f"{index}: {name}: <{flags}> mtu {mtu}"]
    ipv4_entries = normalize_ip_entries(
        iface.get("ipv4") or (iface.get("addresses") or {}).get("ipv4"),
        default_dynamic=False,
    )
    ipv6_entries = normalize_ip_entries(
        iface.get("ipv6") or (iface.get("addresses") or {}).get("ipv6"),
        default_dynamic=False,
    )

    for entry in ipv4_entries:
        dynamic_text = " dynamic" if entry["dynamic"] else ""
        lines.append(f"    inet {entry['address']} scope global{dynamic_text} {name}")
    for entry in ipv6_entries:
        lines.append(f"    inet6 {entry['address']} scope global")
    return "\n".join(lines) + "\n"


def default_device_path(index: int, iface: dict[str, Any]) -> str:
    """Build a default resolved sysfs device path for an interface."""
    kind = iface.get("kind", "physical")
    name = iface["name"]
    if kind == "virtual":
        return f"/sys/devices/virtual/net/{name}"
    return f"/sys/devices/pci0000:00/0000:00:{index:02x}.0/net/{name}"


def route_gateway(route_line: str | None) -> str | None:
    """Extract the IPv4 gateway address from a route output line."""
    if not route_line:
        return None
    match = re.search(r"\bvia\s+(\d{1,3}(?:\.\d{1,3}){3})", route_line)
    return match.group(1) if match else None


def build_run_result_from_outcome(
    outcome: Any,
    *,
    success_stdout: str = "",
    failure_stdout: str = "",
    failure_stderr: str = "",
) -> dict[str, Any]:
    """Convert a simple pass/fail scenario outcome into run_router response data."""
    if isinstance(outcome, dict):
        return {
            "returncode": outcome.get("returncode", 0),
            "stdout": outcome.get("stdout", ""),
            "stderr": outcome.get("stderr", ""),
        }

    outcome_text = str(outcome).strip().lower()
    if outcome_text in {"pass", "passed", "ok", "success"}:
        return {"returncode": 0, "stdout": success_stdout, "stderr": ""}
    if outcome_text in {"warn", "warning", "fail", "failed"}:
        return {
            "returncode": 1,
            "stdout": failure_stdout,
            "stderr": failure_stderr,
        }
    raise ValueError(f"Unsupported connectivity outcome: {outcome!r}")


def build_df_output(used_blocks: int, available_blocks: int) -> str:
    """Render `df -B 512 --output=used,avail` output."""
    return f"Used Avail\n{used_blocks} {available_blocks}\n"


def build_fdisk_output(disk: str, partitions: list[dict[str, Any]]) -> str:
    """Render minimal `fdisk -l` output that the parser can consume."""
    lines = [
        f"Disk /dev/{disk}: 16 GiB",
        "Device Boot Start End Sectors Size Id Type",
    ]

    for index, part in enumerate(partitions, start=1):
        name = part.get("name", f"{disk}{index}")
        boot_flag = "*" if scenario_truthy(part.get("boot"), default=False) else ""
        start = int(part.get("start", 2048))
        sectors = int(part.get("sectors", 204800))
        end = int(part.get("end", start + sectors - 1))
        size = str(part.get("size", "100M"))
        part_id = str(part.get("id", "83")).upper().removeprefix("0X")
        type_name = str(part.get("type_name", "Linux"))
        prefix = f"/dev/{name}"
        if boot_flag:
            lines.append(
                f"{prefix} {boot_flag} {start} {end} {sectors} {size} {part_id} {type_name}"
            )
        else:
            lines.append(f"{prefix} {start} {end} {sectors} {size} {part_id} {type_name}")

    return "\n".join(lines) + "\n"


def build_sgdisk_partition_output(partition: dict[str, Any]) -> str:
    """Render minimal `sgdisk -i=N` output for one GPT partition."""
    guid = str(
        partition.get(
            "guid",
            "0FC63DAF-8483-4772-8E79-3D69D8477DE4",
        )
    ).upper()
    guid_name = str(partition.get("guid_name", "Linux filesystem"))
    if "attribute_flags" in partition:
        flags = str(partition["attribute_flags"])
    else:
        flags = "0000000000000001" if scenario_truthy(
            partition.get("platform_required"),
            default=False,
        ) else "0000000000000000"

    return (
        f"Partition GUID code: {guid} ({guid_name})\n"
        f"Attribute flags: {flags}\n"
    )


def build_efi_var_bytes(attrs: int, payload: bytes = b"") -> bytes:
    """Build raw efivarfs contents: 4-byte LE attrs followed by payload bytes."""
    if attrs < 0:
        raise ValueError("EFI variable attributes must be non-negative")
    return int(attrs).to_bytes(4, byteorder="little", signed=False) + payload


def build_char16_payload(value: str, extra_utf16: str = "") -> bytes:
    """Encode a UEFI CHAR16 payload in UTF-16LE."""
    return (value + extra_utf16).encode("utf-16le")


def build_os_indications_var(
    value: int,
    *,
    attrs: int = 0x07,
) -> bytes:
    """Build the OsIndicationsSupported efivarfs payload."""
    if value < 0:
        raise ValueError("OsIndicationsSupported value must be non-negative")
    payload = int(value).to_bytes(8, byteorder="little", signed=False)
    return build_efi_var_bytes(attrs, payload)


def _match_rule_value(expected: Any, actual: Any) -> bool:
    """Match a rule value against the actual call argument."""
    if isinstance(expected, dict):
        if "equals" in expected:
            return actual == expected["equals"]
        if "contains" in expected:
            return str(expected["contains"]) in str(actual)
        if "regex" in expected:
            return re.search(str(expected["regex"]), str(actual)) is not None
        if "in" in expected:
            options = expected["in"]
            if not isinstance(options, list):
                raise TypeError("'in' matcher requires a list")
            return actual in options
        raise ValueError(f"Unsupported matcher spec: {expected!r}")

    return actual == expected


def _rule_matches(
    when: dict[str, Any] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> bool:
    """Return True when the rule selector matches the current call."""
    if when is None:
        return True
    if not isinstance(when, dict):
        raise TypeError("'when' must be a mapping")

    arg_rules = when.get("args", {})
    if arg_rules is None:
        arg_rules = {}
    if not isinstance(arg_rules, dict):
        raise TypeError("'when.args' must be a mapping")

    for index, expected in arg_rules.items():
        if not isinstance(index, int):
            raise TypeError("'when.args' keys must be integers")
        if index >= len(args) or not _match_rule_value(expected, args[index]):
            return False

    kwarg_rules = when.get("kwargs", {})
    if kwarg_rules is None:
        kwarg_rules = {}
    if not isinstance(kwarg_rules, dict):
        raise TypeError("'when.kwargs' must be a mapping")

    for key, expected in kwarg_rules.items():
        if key not in kwargs or not _match_rule_value(expected, kwargs[key]):
            return False

    return True


def _build_exception(spec: Any) -> BaseException:
    """Build an exception from a passthrough router rule."""
    if isinstance(spec, BaseException):
        return spec

    if isinstance(spec, type) and issubclass(spec, BaseException):
        return spec()

    if not isinstance(spec, dict):
        raise TypeError(
            "Exception rule must be an exception instance, exception class, "
            f"or mapping. Got: {type(spec).__name__}"
        )

    exc_type = spec.get("type")
    args = spec.get("args", [])
    kwargs = spec.get("kwargs", {})

    if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
        raise TypeError("'raise.type' must be an exception class")
    if not isinstance(args, list):
        raise TypeError("'raise.args' must be a list")
    if not isinstance(kwargs, dict):
        raise TypeError("'raise.kwargs' must be a dict")

    return exc_type(*args, **kwargs)


class MockExpectationError(AssertionError):
    """Raised when a declarative mock rule was expected to match but did not."""


def _rule_label(rule: dict[str, Any], index: int) -> str:
    """Return a stable human-readable label for a passthrough rule."""
    label = rule.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return f"rule[{index + 1}]"


def _validated_call_count(
    value: Any,
    *,
    field_name: str,
    rule_name: str,
) -> int | None:
    """Validate an optional per-rule call count constraint."""
    if value is None:
        return None
    if not isinstance(value, int) or value < 0:
        raise TypeError(
            f"'{field_name}' for {rule_name} must be a non-negative integer"
        )
    return value


def passthrough_router(
    real: Any,
    rules: list[dict[str, Any]] | None = None,
    *,
    label: str | None = None,
    require_any_rule_hit: bool = False,
):
    """
    Wrap a real callable and apply declarative YAML-friendly overrides.

    Example rule:
      - when:
          args:
            0: "/tmp/event.yaml"
            1:
              contains: "r"
        raise:
          type: OSError
          args: ["mocked open failure"]
    """
    rules = rules or []
    if not isinstance(rules, list):
        raise TypeError("'rules' must be a list")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise TypeError("'label' must be a non-empty string when provided")
    if not isinstance(require_any_rule_hit, bool):
        raise TypeError("'require_any_rule_hit' must be a boolean")

    normalized_rules: list[dict[str, Any]] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise TypeError("Each passthrough rule must be a mapping")

        rule_name = _rule_label(rule, index)
        required = rule.get("required", False)
        if not isinstance(required, bool):
            raise TypeError(f"'required' for {rule_name} must be a boolean")

        exact_calls = _validated_call_count(
            rule.get("exact_calls"),
            field_name="exact_calls",
            rule_name=rule_name,
        )
        min_calls = _validated_call_count(
            rule.get("min_calls"),
            field_name="min_calls",
            rule_name=rule_name,
        )
        max_calls = _validated_call_count(
            rule.get("max_calls"),
            field_name="max_calls",
            rule_name=rule_name,
        )
        if exact_calls is not None and (min_calls is not None or max_calls is not None):
            raise TypeError(
                f"{rule_name} cannot define 'exact_calls' together with "
                "'min_calls' or 'max_calls'"
            )
        if (
            min_calls is not None
            and max_calls is not None
            and min_calls > max_calls
        ):
            raise TypeError(
                f"{rule_name} has invalid call constraints: min_calls > max_calls"
            )

        normalized_rules.append(
            {
                "raw": rule,
                "name": rule_name,
                "required": required,
                "exact_calls": exact_calls,
                "min_calls": min_calls,
                "max_calls": max_calls,
                "hits": 0,
            }
        )

    router_label = label.strip() if isinstance(label, str) else None

    def _wrapped(*args, **kwargs):
        for rule_info in normalized_rules:
            rule = rule_info["raw"]
            if not _rule_matches(rule.get("when"), args, kwargs):
                continue
            rule_info["hits"] += 1

            if "raise" in rule:
                raise _build_exception(rule["raise"])
            if "return" in rule:
                return rule["return"]
            if rule.get("call_real", True):
                return real(*args, **kwargs)
            return None

        return real(*args, **kwargs)

    def _verify() -> None:
        failures: list[str] = []
        total_hits = sum(int(rule["hits"]) for rule in normalized_rules)

        if require_any_rule_hit and total_hits == 0:
            failures.append("expected at least one passthrough rule to match")

        for rule_info in normalized_rules:
            hits = int(rule_info["hits"])
            rule_name = str(rule_info["name"])
            exact_calls = rule_info["exact_calls"]
            min_calls = rule_info["min_calls"]
            max_calls = rule_info["max_calls"]

            if rule_info["required"] and hits == 0:
                failures.append(f"{rule_name} was never hit")
            if exact_calls is not None and hits != exact_calls:
                failures.append(
                    f"{rule_name} expected exactly {exact_calls} hit(s), got {hits}"
                )
            if min_calls is not None and hits < min_calls:
                failures.append(
                    f"{rule_name} expected at least {min_calls} hit(s), got {hits}"
                )
            if max_calls is not None and hits > max_calls:
                failures.append(
                    f"{rule_name} expected at most {max_calls} hit(s), got {hits}"
                )

        if failures:
            hit_summary = ", ".join(
                f"{rule_info['name']}={rule_info['hits']}"
                for rule_info in normalized_rules
            )
            prefix = f"{router_label}: " if router_label else ""
            if not hit_summary:
                hit_summary = "<no rules>"
            raise MockExpectationError(
                f"{prefix}{'; '.join(failures)}. Hit counts: {hit_summary}"
            )

    setattr(_wrapped, "_mock_verify", _verify)
    return _wrapped
