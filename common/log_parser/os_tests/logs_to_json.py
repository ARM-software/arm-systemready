#!/usr/bin/env python3
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import re
import json
import os
from pathlib import Path
import importlib.util

def _load_standalone_parser(standalone_path: Path):
    """
    Dynamically import the existing standalone logs_to_json.py so we can call
    its parse_ethtool_test_log() without duplicating code.
    """
    if not standalone_path.is_file():
        raise FileNotFoundError(f"Standalone parser not found at: {standalone_path}")

    spec = importlib.util.spec_from_file_location("standalone_parser", str(standalone_path))
    mod = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"Unable to load module from {standalone_path}")
    spec.loader.exec_module(mod)

    if not hasattr(mod, "parse_ethtool_test_log"):
        raise AttributeError("Standalone parser missing function: parse_ethtool_test_log(log_data)")
    return mod


def _ethtool_path() -> Path:
    env = os.getenv("STANDALONE_PARSER_PATH")
    if env:
        return Path(env).expanduser().resolve()

    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "standalone_tests" / "logs_to_json.py",
    ]
    self_path = Path(__file__).resolve()
    for c in candidates:
        try:
            c = c.resolve()
        except Exception:
            continue
        if c.is_file() and c != self_path:
            return c

    raise FileNotFoundError(
        "Could not find standalone logs_to_json.py. "
        "Set STANDALONE_PARSER_PATH to its absolute path."
    )


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 logs_to_json.py <path to ethtool_test.log> <output JSON file path> <os_name>")
        sys.exit(1)

    log_file_path = Path(sys.argv[1]).expanduser().resolve()
    output_file_path = Path(sys.argv[2]).expanduser().resolve()
    os_name = sys.argv[3]

    if not log_file_path.is_file():
        print(f"Error: log file not found: {log_file_path}")
        sys.exit(1)

    # Locate and load the existing standalone parser module
    standalone_path = _ethtool_path()
    standalone = _load_standalone_parser(standalone_path)

    # Read the log and parse using the single source of truth
    with open(log_file_path, "r") as f:
        log_lines = f.readlines()

    # --- Single source of truth for the parser ---
    parsed = standalone.parse_ethtool_test_log(log_lines)

    # Keep OS-test naming exactly as before:
    # "Test_case": f"ethtool_test_{os_name}"
    try:
        for test in parsed.get("test_results", []):
            if isinstance(test, dict) and "Test_case" in test:
                test["Test_case"] = f"ethtool_test_{os_name}"
    except Exception:
        # Non-fatal: if structure ever changes, we still output the parsed JSON.
        pass

    # Normalize suite_summary keys to match OS-test schema
    _OS_SCHEMA_KEYS = [
        "total_passed",
        "total_failed",
        "total_failed_with_waiver",
        "total_aborted",
        "total_skipped",
        "total_warnings",
        "total_ignored",
    ]

    def _normalize_suite_summary(obj):
        if not isinstance(obj, dict):
            return
        # plural -> singular
        if "total_failed_with_waivers" in obj and "total_failed_with_waiver" not in obj:
            obj["total_failed_with_waiver"] = obj.pop("total_failed_with_waivers")
        # drop anything not in schema
        for k in list(obj.keys()):
            if k not in _OS_SCHEMA_KEYS:
                obj.pop(k, None)
        # ensure all keys exist
        for k in _OS_SCHEMA_KEYS:
            obj.setdefault(k, 0)

    for test in parsed.get("test_results", []):
        _normalize_suite_summary(test.get("test_suite_summary", {}))
    _normalize_suite_summary(parsed.get("suite_summary", {}))

    with open(output_file_path, "w") as outfile:
        json.dump(parsed, outfile, indent=4)

if __name__ == "__main__":
    main()
