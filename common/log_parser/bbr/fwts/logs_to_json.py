#!/usr/bin/env python3
# Copyright (c) 2024-2025, Arm Limited or its affiliates. All rights reserved.
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

def parse_fwts_log(log_path):
    with open(log_path, 'r') as f:
        log_data = f.readlines()

    results = []
    main_tests = []
    current_test = None
    current_subtest = None
    Test_suite_description = None

    # Summary variables
    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0
    }

    # First, identify all main tests from the "Running tests:" lines
    running_tests_started = False
    for line in log_data:
        if "Running tests:" in line:
            running_tests_started = True
            main_tests += re.findall(r'\b(\w+)\b', line.split(':', 1)[1].strip())
        elif running_tests_started and not re.match(r'^[=\-]+$', line.strip()):  # Continuation of Running tests line
            main_tests += re.findall(r'\b(\w+)\b', line.strip())
        elif running_tests_started and re.match(r'^[=\-]+$', line.strip()):  # Stop if separator line appears
            break

    # Process the log data
    for i, line in enumerate(log_data):
        # Detect the start of a new main test
        for main_test in main_tests:
            if line.startswith(main_test + ":"):
                if current_test:  # Save the previous test
                    if current_subtest:
                        current_test["subtests"].append(current_subtest)
                        current_subtest = None
                    # Update the test_suite_summary based on subtests
                    for sub in current_test["subtests"]:
                        for key in ["PASSED", "FAILED", "ABORTED", "SKIPPED", "WARNINGS"]:
                            current_test["test_suite_summary"][f"total_{key.lower()}"] += sub["sub_test_result"][key]
                    results.append(current_test)

                # Start a new main test
                Test_suite_description = line.split(':', 1)[1].strip() if ':' in line else "No description"
                current_test = {
                    "Test_suite": main_test,
                    "Test_suite_description": Test_suite_description,
                    "subtests": [],
                    "test_suite_summary": {
                        "total_passed": 0,
                        "total_failed": 0,
                        "total_aborted": 0,
                        "total_skipped": 0,
                        "total_warnings": 0
                    }
                }
                current_subtest = None  # Reset current_subtest
                break

        # Detect subtest start, subtest number, and subtest description
        subtest_match = re.match(r"Test (\d+) of (\d+): (.+)", line)
        if subtest_match:
            if current_subtest:  # Save the previous subtest
                current_test["subtests"].append(current_subtest)

            subtest_number = f'{subtest_match.group(1)} of {subtest_match.group(2)}'
            sub_Test_Description = subtest_match.group(3).strip()

            current_subtest = {
                "sub_Test_Number": subtest_number,
                "sub_Test_Description": sub_Test_Description,
                "sub_test_result": {
                    "PASSED": 0,
                    "FAILED": 0,
                    "ABORTED": 0,
                    "SKIPPED": 0,
                    "WARNINGS": 0,
                    "pass_reasons": [],
                    "fail_reasons": [],
                    "abort_reasons": [],
                    "skip_reasons": [],
                    "warning_reasons": []
                }
            }
            continue

        # Treat esrt abort test as failure
        if "Aborted" in line and "Cannot find ESRT table" in line:
            if not current_subtest:
                current_subtest = {
                    "sub_Test_Number": "Test 1 of 1",
                    "sub_Test_Description": " ",
                    "sub_test_result": {
                        "PASSED": 0,
                        "FAILED": 1,
                        "ABORTED": 0,
                        "SKIPPED": 0,
                        "WARNINGS": 0,
                        "pass_reasons": [],
                        "fail_reasons": [],
                        "abort_reasons": [],
                        "skip_reasons": [],
                        "warning_reasons": []
                    }
                }
            abort_reason = line.strip()
            current_subtest["sub_test_result"]["abort_reasons"].append(abort_reason)
            continue

        # Capture pass/fail/abort/skip/warning info
        if current_subtest:
            if "PASSED" in line:
                current_subtest["sub_test_result"]["PASSED"] += 1
                if "PASSED:" in line:
                    reason_text = line.split("PASSED:", 1)[1].strip()
                else:
                    reason_text = line.replace("PASSED", "").strip()
                j = i + 1
                while j < len(log_data):
                    next_line = log_data[j].strip()
                    # Break if next_line is empty or looks like the start of a new test/subtest entry
                    if not next_line or re.match(r"^(Test \d+ of \d+:|\w+:)", next_line):
                        break
                    reason_text += " " + next_line
                    j += 1
                current_subtest["sub_test_result"]["pass_reasons"].append(reason_text)
            elif "FAILED" in line:
                current_subtest["sub_test_result"]["FAILED"] += 1
                # Capture everything after the first colon if present, otherwise the rest of the line.
                if ":" in line:
                    reason_text = line.split(":", 1)[1].strip()
                else:
                    reason_text = line.replace("FAILED", "").strip()
                # Append subsequent lines that seem to be part of the reason.
                j = i + 1
                while j < len(log_data):
                    next_line = log_data[j].strip()
                    # Stop if next_line is empty or looks like the start of a new test/subtest
                    if not next_line or re.match(r"^(Test \d+ of \d+:|\w+:)", next_line):
                        break
                    reason_text += " " + next_line
                    j += 1
                current_subtest["sub_test_result"]["fail_reasons"].append(reason_text)
            elif "SKIPPED" in line:
                current_subtest["sub_test_result"]["SKIPPED"] += 1
                if "SKIPPED:" in line:
                    reason_text = line.split("SKIPPED:", 1)[1].strip()
                    j = i + 1
                    while j < len(log_data):
                        next_line = log_data[j].strip()
                        # Break if next_line is empty or looks like the start of a new test/subtest
                        if not next_line or re.match(r"^(Test \d+ of \d+:|\w+:)", next_line):
                            break
                        reason_text += " " + next_line
                        j += 1
                    current_subtest["sub_test_result"]["skip_reasons"].append(reason_text)
            elif "WARNING" in line:
                current_subtest["sub_test_result"]["WARNINGS"] += 1
                if "WARNING:" in line:
                    reason_text = line.split("WARNING:", 1)[1].strip()
                else:
                    reason_text = line.replace("WARNING", "").strip()
                j = i + 1
                while j < len(log_data):
                    next_line = log_data[j].strip()
                    # Break if next_line is empty or looks like the start of a new test/subtest entry
                    if not next_line or re.match(r"^(Test \d+ of \d+:|\w+:)", next_line):
                        break
                    reason_text += " " + next_line
                    j += 1
                current_subtest["sub_test_result"]["warning_reasons"].append(reason_text)
        else:
            # Handle SKIPPED when no current_subtest exists
            # detect lines like "ACPI XXX table does not exist, skipping test"
            skip_acpi_match = re.search(r"ACPI\s+(\S+)\s+table does not exist, skipping test", line)
            if skip_acpi_match and current_test:
                # Create a new subtest to record the skip
                sub_desc = current_test.get("Test_suite_description")

                skip_subtest = {
                    "sub_Test_Number": "Test 1 of 1",
                    "sub_Test_Description": sub_desc,
                    "sub_test_result": {
                        "PASSED": 0,
                        "FAILED": 0,
                        "ABORTED": 0,
                        "SKIPPED": 1,
                        "WARNINGS": 0,
                        "pass_reasons": [],
                        "fail_reasons": [],
                        "abort_reasons": [],
                        "skip_reasons": [line.strip()],
                        "warning_reasons": []
                    }
                }
                current_test["subtests"].append(skip_subtest)
                # do not continue here because we want to also catch normal "SKIPPED" if present

            if "SKIPPED" in line:
                current_subtest = {
                    "sub_Test_Number": "Test 1 of 1",
                    "sub_Test_Description": "Skipped test",
                    "sub_test_result": {
                        "PASSED": 0,
                        "FAILED": 0,
                        "ABORTED": 0,
                        "SKIPPED": 1,
                        "WARNINGS": 0,
                        "pass_reasons": [],
                        "fail_reasons": [],
                        "abort_reasons": [],
                        "skip_reasons": [],
                        "warning_reasons": []
                    }
                }
                if "SKIPPED:" in line:
                    reason_text = line.split("SKIPPED:")[1].strip()
                    current_subtest["sub_test_result"]["skip_reasons"].append(reason_text)
                current_test["subtests"].append(current_subtest)
                current_subtest = None
                continue

        # Parse per-test summary lines
        per_test_summary_match = re.match(
            r"^(\d+) passed,\s*(\d+) failed,\s*(\d+) warning,\s*(\d+) aborted,\s*(\d+) skipped,\s*(\d+) info only\.$",
            line.strip()
        )
        if per_test_summary_match:
            # Not updating counts here; we sum from subtests anyway
            continue

    # After processing all lines, save the last test + subtest
    if current_subtest:
        current_test["subtests"].append(current_subtest)
    if current_test:
        # Update the test_suite_summary from subtests
        for sub in current_test["subtests"]:
            for key in ["PASSED", "FAILED", "ABORTED", "SKIPPED", "WARNINGS"]:
                current_test["test_suite_summary"][f"total_{key.lower()}"] += sub["sub_test_result"][key]
        results.append(current_test)

    # After all tests, update the suite_summary from each test's summary
    for test in results:
        for key in ["PASSED", "FAILED", "ABORTED", "SKIPPED", "WARNINGS"]:
            suite_summary[f"total_{key.lower()}"] += test["test_suite_summary"][f"total_{key.lower()}"]

    # -----------------------------
    # POST-PROCESS THE RESULTS
    # 1) Rename summary keys, add total_failed_with_waiver
    # 2) Remove empty reason arrays from sub_test_result
    # -----------------------------

    # Rename the suite_summary keys & add total_failed_with_waiver
    final_suite_summary = {
        "total_passed": suite_summary.pop("total_passed"),
        "total_failed": suite_summary.pop("total_failed"),
        "total_failed_with_waiver": 0,  # Always 0 unless logic is added
        "total_aborted": suite_summary.pop("total_aborted"),
        "total_skipped": suite_summary.pop("total_skipped"),
        "total_warnings": suite_summary.pop("total_warnings")
    }

    # Process each test in results
    for test in results:
        # Rename that test's summary keys, add total_failed_with_waiver
        t = test["test_suite_summary"]
        test["test_suite_summary"] = {
            "total_passed": t.pop("total_passed"),
            "total_failed": t.pop("total_failed"),
            "total_failed_with_waiver": 0,  # same handling
            "total_aborted": t.pop("total_aborted"),
            "total_skipped": t.pop("total_skipped"),
            "total_warnings": t.pop("total_warnings")
        }

        # Remove empty reason arrays from each subtest
        for sub in test["subtests"]:
            sub_res = sub["sub_test_result"]
            # For each reason array, remove it if it's empty
            if not sub_res["pass_reasons"]:
                del sub_res["pass_reasons"]
            if not sub_res["fail_reasons"]:
                del sub_res["fail_reasons"]
            if not sub_res["abort_reasons"]:
                del sub_res["abort_reasons"]
            if not sub_res["skip_reasons"]:
                del sub_res["skip_reasons"]
            if not sub_res["warning_reasons"]:
                del sub_res["warning_reasons"]

    return {
        "test_results": results,
        "suite_summary": final_suite_summary
    }

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 fwts_parse_json.py <path to FWTS log> <output JSON file path>")
        sys.exit(1)

    log_file_path = sys.argv[1]  # Get the log file path from the command-line argument
    output_file_path = sys.argv[2]  # Get the output file path from the command-line argument
    output_json = parse_fwts_log(log_file_path)

    # Write to specified output file
    with open(output_file_path, 'w') as outfile:
        json.dump(output_json, outfile, indent=4)
