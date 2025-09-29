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
from pathlib import Path
import json

# Put repo root (parent of "common") on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from common.log_parser.standalone_tests.logs_to_json import parse_ethtool_test_log
except ImportError as e:
    raise ImportError(
        "Could not import parse_ethtool_test_log from common.log_parser.standalone_tests.logs_to_json "
        "even after adding the repo root to sys.path. Verify the path exists."
    ) from e

def _normalize_suite_summary(obj):
    if not isinstance(obj, dict):
        return
    _OS_SCHEMA_KEYS = [
        "total_passed",
        "total_failed",
        "total_failed_with_waiver",
        "total_aborted",
        "total_skipped",
        "total_warnings",
        "total_ignored",
    ]
    if "total_failed_with_waivers" in obj and "total_failed_with_waiver" not in obj:
        obj["total_failed_with_waiver"] = obj.pop("total_failed_with_waivers")
    for k in list(obj.keys()):
        if k not in _OS_SCHEMA_KEYS:
            obj.pop(k, None)
    for k in _OS_SCHEMA_KEYS:
        obj.setdefault(k, 0)

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

    with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
        log_lines = f.readlines()

    parsed = parse_ethtool_test_log(log_lines)

    # Override test case name for OS schema
    for test in parsed.get("test_results", []):
        if isinstance(test, dict) and "Test_case" in test:
            test["Test_case"] = f"ethtool_test_{os_name}"

    # Normalize suite_summary to OS schema
    for test in parsed.get("test_results", []):
        _normalize_suite_summary(test.get("test_suite_summary", {}))
    _normalize_suite_summary(parsed.get("suite_summary", {}))

    with open(output_file_path, "w", encoding="utf-8") as outfile:
        json.dump(parsed, outfile, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
