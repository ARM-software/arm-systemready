#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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

import json
import os
import sys

STANDALONE_PARSER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "standalone_tests")
)

if STANDALONE_PARSER_PATH not in sys.path:
    sys.path.insert(0, STANDALONE_PARSER_PATH)
from logs_to_json import parse_single_log
OS_RELEASE_FILE_NAME = "cat-etc-os-release.txt"
OS_TOOL_LOGS = (
    "ethtool-test.log",
    "read_write_check_blk_devices.log",
)

def create_subtest(subtest_number, description, status, reason=""):
    result = {
        "sub_Test_Number": str(subtest_number),
        "sub_Test_Description": description,
        "sub_test_result": {
            "PASSED": 1 if status == "PASSED" else 0,
            "FAILED": 1 if status == "FAILED" else 0,
            "FAILED_WITH_WAIVER": 0,
            "ABORTED": 0,
            "SKIPPED": 1 if status == "SKIPPED" else 0,
            "WARNINGS": 1 if status == "WARNINGS" else 0,
            "pass_reasons": [reason] if (status == "PASSED" and reason) else [],
            "fail_reasons": [reason] if (status == "FAILED" and reason) else [],
            "abort_reasons": [],
            "skip_reasons": [reason] if (status == "SKIPPED" and reason) else [],
            "warning_reasons": [reason] if (status == "WARNINGS" and reason) else [],
            "waiver_reason": ""
        }
    }
    return result

def update_suite_summary(suite_summary, status):
    key_map = {
        "PASSED": "total_passed",
        "FAILED": "total_failed",
        "SKIPPED": "total_skipped",
        "ABORTED": "total_aborted",
        "WARNINGS": "total_warnings"
    }
    if status in key_map:
        suite_summary[key_map[status]] += 1

def collect_os_release_files(os_logs_path):
    release_files = []
    if not os.path.isdir(os_logs_path):
        return release_files
    for root, _, files in os.walk(os_logs_path):
        if OS_RELEASE_FILE_NAME in files:
            release_files.append(os.path.join(root, OS_RELEASE_FILE_NAME))
    return release_files

def os_dir_from_release_path(os_logs_path, release_path):
    try:
        rel_path = os.path.relpath(release_path, os_logs_path)
    except ValueError:
        return None
    parts = rel_path.split(os.sep)
    return parts[0] if parts else None

def parse_os_release(os_release_path):
    name = None
    version_id = None
    try:
        with open(os_release_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("NAME=") and name is None:
                    name = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("VERSION_ID=") and version_id is None:
                    version_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                if name and version_id:
                    break
    except OSError:
        return None, None
    return name, version_id

def parse_post_script_errors(log_path, tokens):
    errors = []
    if not os.path.isfile(log_path):
        return errors
    tokens_lower = [t.lower() for t in tokens if t]
    with open(log_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("ERROR"):
                continue
            lower_line = line.lower()
            if any(token in lower_line for token in tokens_lower):
                errors.append(line.strip())
    return errors

def add_summary(dst, src):
    dst["total_passed"] += src.get("total_passed", 0)
    dst["total_failed"] += src.get("total_failed", 0)
    dst["total_skipped"] += src.get("total_skipped", 0)
    dst["total_aborted"] += src.get("total_aborted", 0)
    dst["total_warnings"] += src.get("total_warnings", 0)
    dst["total_failed_with_waivers"] += src.get("total_failed_with_waivers", 0)
    dst["total_failed_with_waivers"] += src.get("total_failed_with_waiver", 0)

def make_test_case_unique(parsed_json, suffix):
    for test in parsed_json.get("test_results", []):
        test_case = test.get("Test_case")
        if test_case:
            test["Test_case"] = f"{test_case}_{suffix}"
        desc = test.get("Test_case_description", "")
        test["Test_case_description"] = f"{desc} ({suffix})" if desc else suffix

def mark_recommended_test_case(parsed_json):
    for test in parsed_json.get("test_results", []):
        test["SRS scope"] = "Recommended"

def append_parsed_log(test_results, suite_summary, log_path, suffix):
    if not os.path.isfile(log_path):
        return
    try:
        parsed_json = parse_single_log(log_path)
    except Exception as exc:
        print(f"WARNING: Failed to parse OS test log {log_path}: {exc}")
        return
    make_test_case_unique(parsed_json, suffix)
    mark_recommended_test_case(parsed_json)
    test_results.extend(parsed_json.get("test_results", []))
    add_summary(suite_summary, parsed_json.get("suite_summary", {}))

def os_log_dirs(os_logs_path):
    if not os.path.isdir(os_logs_path):
        return []
    dirs = []
    for entry in sorted(os.listdir(os_logs_path)):
        os_dir = os.path.join(os_logs_path, entry)
        if os.path.isdir(os_dir) and entry.startswith("linux"):
            dirs.append((entry, os_dir))
    return dirs

def append_os_tool_logs(test_results, suite_summary, os_logs_path):
    for os_name, os_dir in os_log_dirs(os_logs_path):
        log_base = os.path.join(os_dir, "systemready-band-compliance-logs")
        if not os.path.isdir(log_base):
            log_base = os_dir
        suffix = os_name.replace("/", "_")
        for log_file in OS_TOOL_LOGS:
            append_parsed_log(
                test_results,
                suite_summary,
                os.path.join(log_base, log_file),
                suffix
            )

def build_results(os_logs_path, post_script_log):
    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waivers": 0
    }

    test_suite = {
        "Test_suite": "os_test",
        "Test_suite_description": "os test checks",
        "Test_case": "os_testing",
        "Test_case_description": "OS logs validation and post script checks",
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    subtest_number = 1

    rhel_info = None
    sle_info = None
    all_os_dirs = set()

    for release_path in collect_os_release_files(os_logs_path):
        name, version_id = parse_os_release(release_path)
        if not name or not version_id:
            continue
        os_dir = os_dir_from_release_path(os_logs_path, release_path)
        if os_dir:
            all_os_dirs.add(os_dir)
        name_lower = name.lower()
        if rhel_info is None and ("red hat" in name_lower or "redhat" in name_lower):
            rhel_info = (name, version_id, release_path, os_dir)
        if sle_info is None and ("sles" in name_lower or "suse" in name_lower):
            sle_info = (name, version_id, release_path, os_dir)
        if rhel_info and sle_info:
            break

    def add_presence_subtest(label, os_info):
        nonlocal subtest_number
        desc = f"Is {label.lower()} logs present or not"
        if not os_info:
            sub = create_subtest(subtest_number, desc, "FAILED", "OS logs missing")
        else:
            name, version_id, _, _ = os_info
            reason = f"{name} {version_id}"
            sub = create_subtest(subtest_number, desc, "PASSED", reason)
        test_suite["subtests"].append(sub)
        update_suite_summary(test_suite["test_suite_summary"], "FAILED" if sub["sub_test_result"]["FAILED"] else "PASSED")
        subtest_number += 1

    add_presence_subtest("RHEL", rhel_info)
    add_presence_subtest("SLE", sle_info)

    errors = parse_post_script_errors(post_script_log, ["os-logs"])
    if not os.path.isfile(post_script_log):
        desc = f"post-script.log not found at {post_script_log}"
        sub = create_subtest(subtest_number, desc, "FAILED", "post-script.log missing")
        test_suite["subtests"].append(sub)
        update_suite_summary(test_suite["test_suite_summary"], "FAILED")
        subtest_number += 1
    elif errors:
        rhel_dir = rhel_info[3] if rhel_info else None
        sle_dir = sle_info[3] if sle_info else None
        other_dirs = {d for d in all_os_dirs if d and d not in {rhel_dir, sle_dir}}
        for error_line in errors:
            cleaned = error_line.strip()
            if cleaned.startswith("ERROR"):
                cleaned = cleaned[len("ERROR"):].strip()
            reason = "post-script error"
            if ":" in cleaned:
                desc_part, reason_part = cleaned.rsplit(":", 1)
                desc = f"post-script checks:{desc_part.strip()}"
                reason = reason_part.strip()
            else:
                desc = f"post-script checks:{cleaned}"
            lower_line = error_line.lower()
            if (rhel_dir and rhel_dir.lower() in lower_line) or (sle_dir and sle_dir.lower() in lower_line):
                status = "FAILED"
            elif any(d.lower() in lower_line for d in other_dirs):
                status = "WARNINGS"
            else:
                status = "WARNINGS"
            sub = create_subtest(subtest_number, desc, status, reason)
            test_suite["subtests"].append(sub)
            update_suite_summary(test_suite["test_suite_summary"], status)
            subtest_number += 1

    test_results = [test_suite]
    suite_summary = test_suite["test_suite_summary"].copy()
    append_os_tool_logs(test_results, suite_summary, os_logs_path)

    return {
        "test_results": test_results,
        "suite_summary": suite_summary
    }

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <os-logs-path> <post-script.log> <output JSON file path>")
        sys.exit(1)

    os_logs_path = sys.argv[1]
    post_script_log = sys.argv[2]
    output_file_path = sys.argv[3]

    output_json = build_results(os_logs_path, post_script_log)
    with open(output_file_path, "w", encoding="utf-8") as outfile:
        json.dump(output_json, outfile, indent=4)

if __name__ == "__main__":
    main()
