from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # Support package imports and direct harness module loading.
    from .mock_loader import ConfigError
    from .mock_loader import _resolve_runner_module_from_stack
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from mock_loader import ConfigError
    from mock_loader import _resolve_runner_module_from_stack


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
