from __future__ import annotations

import json
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any
from typing import Mapping

try:  # Support package imports and direct harness module loading.
    from .mock_loader import ConfigError
    from .mock_loader import _resolve_runner_module_from_stack
    from .mock_loader import stateful_run_router
    from .mock_helpers import build_char16_payload
    from .mock_helpers import build_df_output
    from .mock_helpers import build_efi_var_bytes
    from .mock_helpers import build_ethtool_ip_address_output
    from .mock_helpers import build_ethtool_ip_link_line
    from .mock_helpers import build_ethtool_ip_link_show_line
    from .mock_helpers import build_fdisk_output
    from .mock_helpers import build_os_indications_var
    from .mock_helpers import build_run_result_from_outcome
    from .mock_helpers import build_sgdisk_partition_output
    from .mock_helpers import check_output_router
    from .mock_helpers import default_device_path
    from .mock_helpers import noop
    from .mock_helpers import normalize_ethtool_tool_path
    from .mock_helpers import passthrough_router
    from .mock_helpers import route_gateway
    from .mock_helpers import run_router
    from .mock_helpers import scenario_truthy
    from .mock_helpers import which_router
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from mock_loader import ConfigError
    from mock_loader import _resolve_runner_module_from_stack
    from mock_loader import stateful_run_router
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
