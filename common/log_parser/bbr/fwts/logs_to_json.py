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
                    # Update the test_suite_summary based on subtests
                    for sub in current_test["subtests"]:
                        for key in ["PASSED", "FAILED", "ABORTED", "SKIPPED", "WARNINGS"]:
                            current_test["test_suite_summary"][f"total_{key}"] += sub["sub_test_result"][key]
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
                current_subtest = None  # Reset current_subtest when a new test suite starts
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
            continue  # Do not increment counts here; will do it later based on subtests

        # Capture pass/fail/abort/skip/warning info
        if current_subtest:
            if "PASSED" in line:
                current_subtest["sub_test_result"]["PASSED"] += 1
                reason_text = line.split("PASSED:")[1].strip() if "PASSED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["pass_reasons"].append(reason_text)
            elif "FAILED" in line:
                current_subtest["sub_test_result"]["FAILED"] += 1
                reason_text = line.split("FAILED:")[1].strip() if "FAILED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["fail_reasons"].append(reason_text)
            elif "SKIPPED" in line:
                current_subtest["sub_test_result"]["SKIPPED"] += 1
                reason_text = line.split("SKIPPED:")[1].strip() if "SKIPPED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["skip_reasons"].append(reason_text)
            elif "WARNING" in line:
                current_subtest["sub_test_result"]["WARNINGS"] += 1
                reason_text = line.split("WARNING:")[1].strip() if "WARNING:" in line else "No specific reason"
                current_subtest["sub_test_result"]["warning_reasons"].append(reason_text)
        else:
            # Handle SKIPPED when no current_subtest exists
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
                reason_text = line.split("SKIPPED:")[1].strip() if "SKIPPED:" in line else "No specific reason"
                current_subtest["sub_test_result"]["skip_reasons"].append(reason_text)
                current_test["subtests"].append(current_subtest)
                current_subtest = None  # Reset current_subtest after adding to subtests
                continue

        # Parse per-test summary lines
        per_test_summary_match = re.match(r"^(\d+) passed,\s*(\d+) failed,\s*(\d+) warning,\s*(\d+) aborted,\s*(\d+) skipped,\s*(\d+) info only\.$", line.strip())
        if per_test_summary_match:
            # We will not update counts here; instead, we will sum up counts from subtests
            continue  # Move to the next line

    # After processing all lines, save the last test and subtest
    if current_subtest:
        current_test["subtests"].append(current_subtest)
    if current_test:
        # Update the test_suite_summary based on subtests
        for sub in current_test["subtests"]:
            for key in ["PASSED", "FAILED", "ABORTED", "SKIPPED", "WARNINGS"]:
                current_test["test_suite_summary"][f"total_{key}"] += sub["sub_test_result"][key]
        results.append(current_test)

    # After all tests, update the suite_summary based on test_suite_summary of all tests
    for test in results:
        for key in ["PASSED", "FAILED", "ABORTED", "SKIPPED", "WARNINGS"]:
            suite_summary[f"total_{key}"] += test["test_suite_summary"][f"total_{key}"]

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
