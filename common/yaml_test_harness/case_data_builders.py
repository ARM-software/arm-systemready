from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


class CaseBuildError(Exception):
    """Raised when case workspace data is invalid or cannot be materialized."""


def expand_template(value: str, work_dir: Path, file_path: Path) -> str:
    return (
        value.replace("{dir}", str(work_dir))
        .replace("{file}", str(file_path))
        .replace("{filename}", file_path.name)
    )


def replace_dir_tokens(value: Any, temp_dir: Path) -> Any:
    if isinstance(value, str):
        return value.replace("{dir}", str(temp_dir))
    if isinstance(value, list):
        return [replace_dir_tokens(item, temp_dir) for item in value]
    if isinstance(value, tuple):
        return tuple(replace_dir_tokens(item, temp_dir) for item in value)
    if isinstance(value, dict):
        return {
            key: replace_dir_tokens(item, temp_dir)
            for key, item in value.items()
        }
    return value


def build_runtime_case_for_tempdir(
    case_def: Mapping[str, Any],
    temp_dir: Path,
) -> dict[str, Any]:
    runtime_case = dict(case_def)
    runtime_case["scripts"] = replace_dir_tokens(
        runtime_case.get("scripts", {}),
        temp_dir,
    )
    runtime_case["bin_files"] = replace_dir_tokens(
        runtime_case.get("bin_files", {}),
        temp_dir,
    )
    runtime_case["text_files"] = replace_dir_tokens(
        runtime_case.get("text_files", {}),
        temp_dir,
    )
    runtime_case["dir_structure"] = replace_dir_tokens(
        runtime_case.get("dir_structure", []),
        temp_dir,
    )
    runtime_case["patch_constants"] = replace_dir_tokens(
        runtime_case.get("patch_constants", {}),
        temp_dir,
    )
    return runtime_case


def render_post_check_path(raw_path: str, work_dir: Path) -> Path:
    return Path(raw_path.format(dir=str(work_dir)))


def _write_text_if_changed(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                if executable:
                    path.chmod(0o755)
                return
        except Exception:
            pass

    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _write_bytes_if_changed(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            existing = path.read_bytes()
            if existing == content:
                return
        except Exception:
            pass

    path.write_bytes(content)


def prepare_case_files(work_dir: Path, case_def: Mapping[str, Any]) -> None:
    scripts = case_def.get("scripts", {})
    if scripts is not None:
        if not isinstance(scripts, dict):
            raise CaseBuildError("'scripts' must be a mapping")
        for name, content in scripts.items():
            if not isinstance(name, str) or not isinstance(content, str):
                raise CaseBuildError("'scripts' entries must be string -> string")
            script_path = work_dir / name
            _write_text_if_changed(script_path, content, executable=True)

    bin_files = case_def.get("bin_files", {})
    if bin_files is not None:
        if not isinstance(bin_files, dict):
            raise CaseBuildError("'bin_files' must be a mapping")
        for name, spec in bin_files.items():
            if not isinstance(name, str) or not isinstance(spec, dict):
                raise CaseBuildError("'bin_files' entries must be string -> mapping")

            target_file = work_dir / name
            hex_data = spec.get("hex")
            text_data = spec.get("text")

            if hex_data is not None:
                if not isinstance(hex_data, str):
                    raise CaseBuildError(
                        f"Invalid hex data type for bin_files entry '{name}'"
                    )
                try:
                    payload = bytes.fromhex(hex_data)
                except ValueError as exc:
                    raise CaseBuildError(
                        f"Invalid hex data for bin_files entry '{name}': {exc}"
                    ) from exc
                _write_bytes_if_changed(target_file, payload)
            elif text_data is not None:
                if not isinstance(text_data, str):
                    raise CaseBuildError(
                        f"Invalid text data type for bin_files entry '{name}'"
                    )
                _write_bytes_if_changed(target_file, text_data.encode("utf-8"))
            else:
                raise CaseBuildError(
                    "Each 'bin_files' entry requires string key 'hex' or 'text'"
                )

    text_files = case_def.get("text_files", {})
    if text_files is not None:
        if not isinstance(text_files, dict):
            raise CaseBuildError("'text_files' must be a mapping")
        for name, content in text_files.items():
            if not isinstance(name, str) or not isinstance(content, str):
                raise CaseBuildError("'text_files' entries must be string -> string")
            target_file = work_dir / name
            _write_text_if_changed(target_file, content)


def materialize_case_workspace(
    work_dir: Path,
    case_def: Mapping[str, Any],
) -> list[str]:
    details: list[str] = []

    dir_structure = case_def.get("dir_structure", [])
    if dir_structure is None:
        dir_structure = []
    if not isinstance(dir_structure, list):
        raise CaseBuildError("'dir_structure' must be a list")

    for index, entry in enumerate(dir_structure, start=1):
        if not isinstance(entry, dict):
            raise CaseBuildError(f"'dir_structure[{index}]' must be a mapping")
        rel_path = entry.get("path")
        if not isinstance(rel_path, str) or not rel_path.strip():
            raise CaseBuildError(
                f"'dir_structure[{index}].path' must be a non-empty string"
            )
        dir_path = work_dir / rel_path
        dir_path.mkdir(parents=True, exist_ok=True)
        details.append(f"Created directory: {dir_path}")

    prepare_case_files(work_dir, case_def)
    return details
