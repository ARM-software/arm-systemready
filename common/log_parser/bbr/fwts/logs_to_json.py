#!/usr/bin/env python3
# Copyright (c) 2024, Arm Limited or its affiliates. All rights reserved.
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
    Test_suite_Description = None

    # Summary variables
    total_PASSED = 0
    total_FAILED = 0
    total_ABORTED = 0
    total_SKIPPED = 0
    total_WARNINGS = 0

    suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_ABORTED": 0,
        "total_SKIPPED": 0,
        "total_WARNINGS": 0
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
    for line in log_data:
        # Detect the start of a new main test
        for main_test in main_tests:
            if line.startswith(main_test + ":"):
                if current_test:  # Save the previous test
                    if current_subtest:
                        current_test["subtests"].append(current_subtest)
                        current_subtest = None
                    # Add test_suite_summary for the completed test suite
                    current_test["test_suite_summary"] = {
                        "total_PASSED": current_test["test_suite_summary"]["total_PASSED"],
                        "total_FAILED": current_test["test_suite_summary"]["total_FAILED"],
                        "total_ABORTED": current_test["test_suite_summary"]["total_ABORTED"],
                        "total_SKIPPED": current_test["test_suite_summary"]["total_SKIPPED"],
                        "total_WARNINGS": current_test["test_suite_summary"]["total_WARNINGS"]
                    }
                    results.append(current_test)

                # Start a new main test
                Test_suite_Description = line.split(':', 1)[1].strip() if ':' in line else "No description"
                current_test = {
                    "Test_suite": main_test,  # Changed field name from main_test to Test_suite
                    "Test_suite_Description": Test_suite_Description,
                    "subtests": [],
                    "test_suite_summary": {
                        "total_PASSED": 0,
                        "total_FAILED": 0,
                        "total_ABORTED": 0,
                        "total_SKIPPED": 0,
                        "total_WARNINGS": 0
                    }
                }
                break

        # Detect subtest start, subtest number, and subtest description
        subtest_match = re.match(r"Test (\d+) of (\d+): (.+)", line)
        if subtest_match:
            if current_subtest:  # Save the previous subtest
                current_test["subtests"].append(current_subtest)

            subtest_number = f'{subtest_match.group(1)} of {subtest_match.group(2)}'
            sub_Test_Description = subtest_match.group(3).strip()

            current_subtest = {
                "sub_Test_Number": subtest_number,  # Changed field name from subtest_number to sub_Test_Number
                "sub_Test_Description": sub_Test_Description,
                "sub_test_result": {  # Changed field name from results to sub_test_result
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

        # Check for test abortion and properly append the whole reason
        if "Aborted" in line or "ABORTED" in line:  # Detect all forms of abortion messages
            if not current_subtest:
                current_subtest = {
                    "sub_Test_Number": "Test 1 of 1",  # Changed field name
                    "sub_Test_Description": "Aborted test",
                    "sub_test_result": {  # Changed field name from results to sub_test_result
                        "PASSED": 0,
                        "FAILED": 0,
                        "ABORTED": 1,
                        "SKIPPED": 0,
                        "WARNINGS": 0,
                        "pass_reasons": [],
                        "fail_reasons": [],
                        "abort_reasons": [],
                        "skip_reasons": [],
                        "warning_reasons": []
                    }
                }
            abort_reason = line.strip()  # Take the entire line as the abort reason
            current_subtest["sub_test_result"]["abort_reasons"].append(abort_reason)
            current_test["test_suite_summary"]["total_ABORTED"] += 1  # Increment ABORTED count for the suite
            suite_summary["total_ABORTED"] += 1  # Increment ABORTED count for overall suite summary
            continue

        # Capture pass/fail/abort/skip/warning info
        if current_subtest:
            if "PASSED" in line:
                current_subtest["sub_test_result"]["PASSED"] += 1
                reason_text = line.split("PASSED:")[1].strip() if "PASSED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["pass_reasons"].append(reason_text)
                current_test["test_suite_summary"]["total_PASSED"] += 1
                suite_summary["total_PASSED"] += 1
            elif "FAILED" in line:
                current_subtest["sub_test_result"]["FAILED"] += 1
                reason_text = line.split("FAILED:")[1].strip() if "FAILED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["fail_reasons"].append(reason_text)
                current_test["test_suite_summary"]["total_FAILED"] += 1
                suite_summary["total_FAILED"] += 1
            elif "SKIPPED" in line:
                current_subtest["sub_test_result"]["SKIPPED"] += 1
                reason_text = line.split("SKIPPED:")[1].strip() if "SKIPPED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["skip_reasons"].append(reason_text)
                current_test["test_suite_summary"]["total_SKIPPED"] += 1
                suite_summary["total_SKIPPED"] += 1
            elif "WARNING" in line:
                current_subtest["sub_test_result"]["WARNINGS"] += 1
                reason_text = line.split("WARNING:")[1].strip() if "WARNING:" in line else "No specific reason"
                current_subtest["sub_test_result"]["warning_reasons"].append(reason_text)
                current_test["test_suite_summary"]["total_WARNINGS"] += 1
                suite_summary["total_WARNINGS"] += 1

    # Capture the total summary line before "Test Failure Summary"
    for line in log_data:
        if "Total:" in line:
            summary_match = re.search(r"Total:\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*\d+", line)
            if summary_match:
                total_PASSED = int(summary_match.group(1))
                total_FAILED = int(summary_match.group(2))
                total_ABORTED = int(summary_match.group(3))
                total_WARNINGS = int(summary_match.group(4))
                total_SKIPPED = int(summary_match.group(5))
            break

    # Save the last test and subtest
    if current_subtest:
        current_test["subtests"].append(current_subtest)
    if current_test:
        current_test["test_suite_summary"] = {
            "total_PASSED": current_test["test_suite_summary"]["total_PASSED"],
            "total_FAILED": current_test["test_suite_summary"]["total_FAILED"],
            "total_ABORTED": current_test["test_suite_summary"]["total_ABORTED"],
            "total_SKIPPED": current_test["test_suite_summary"]["total_SKIPPED"],
            "total_WARNINGS": current_test["test_suite_summary"]["total_WARNINGS"]
        }
        results.append(current_test)

    # Return the parsed results with a suite summary
    return {
        "test_results": results,
        "suite_summary": suite_summary
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
