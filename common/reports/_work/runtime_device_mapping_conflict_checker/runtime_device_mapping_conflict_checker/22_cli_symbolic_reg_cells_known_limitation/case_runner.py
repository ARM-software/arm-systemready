#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: case_runner.py <target_script>", file=sys.stderr)
        return 2

    work_dir = Path.cwd()
    target = Path(sys.argv[1]).resolve()

    spec = importlib.util.spec_from_file_location(
        "runtime_checker_under_test",
        target,
    )
    if spec is None or spec.loader is None:
        print(f"failed to load target: {{target}}", file=sys.stderr)
        return 2

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    module.DTS_PATH = work_dir / "device_tree.dts"
    module.MEMMAP_PATH = work_dir / "memmap.log"
    module.OUT_LOG_PATH = work_dir / "runtime_device_mapping_conflict_test.log"
    module._LOG_FH = None

    try:
        module.main()
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 1

    log_path = work_dir / "runtime_device_mapping_conflict_test.log"
    if log_path.exists():
        print(log_path.read_text(encoding="utf-8", errors="replace"), end="")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
