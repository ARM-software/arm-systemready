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

import argparse
import chardet
import json
import re
from collections import defaultdict

def detect_file_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def main(input_files, output_file):
    processing = False
    in_test = False
    suite_name = ""
    test_number = ""
    test_name = ""
    test_description = ""
    result = ""
    rules = ""
    result_mapping = {"PASS": "PASSED", "FAIL": "FAILED", "SKIPPED": "SKIPPED"}

    result_data = defaultdict(list)
    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0,
        "total_failed_with_waiver": 0,
        "total_ignored": 0
    }

    # Dictionary to keep track of test numbers per suite to avoid duplicates
    test_numbers_per_suite = defaultdict(set)

    for input_file in input_files:
        file_encoding = detect_file_encoding(input_file)

        with open(input_file, "r", encoding=file_encoding, errors="ignore") as file:
            lines = file.read().splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                # Remove leading timestamp and square brackets
                line = line.strip()
                line = re.sub(r'^\[.*?\]\s*', '', line)

                if "*** Starting" in line:
                    suite_name_match = re.search(r'\*\*\* Starting (.*) tests \*\*\*', line)
                    if suite_name_match:
                        suite_name = suite_name_match.group(1).strip()
                    else:
                        suite_name = line.strip().split("*** Starting")[1].split("tests")[0].strip()
                    if suite_name == "GICv2m":
                         suite_name = "GIC"
                    processing = True
                    in_test = False
                    i += 1
                    continue
                elif processing:
                    if not line.strip():
                        i +=1
                        continue
                    # Try to match test line with result on same line
                    result_line_match = re.match(r'^\s*(\d+)\s*:\s*(.*?)\s*: Result:\s*(\w+)$', line)
                    if result_line_match:
                        test_number = result_line_match.group(1).strip()
                        test_name = result_line_match.group(2).strip()
                        result = result_mapping.get(result_line_match.group(3).strip(), result_line_match.group(3).strip())
                        test_description = ""
                        rules = ""
                        # Check for duplicates
                        if test_number in test_numbers_per_suite[suite_name]:
                            i +=1
                            continue  # Skip adding duplicate test
                        # Create subtest_entry
                        subtest_entry = {
                            "sub_Test_Number": test_number,
                            "sub_Test_Description": test_name,
                            "sub_test_result": result
                        }
                        # Append subtest_entry to result_data
                        result_data[suite_name].append(subtest_entry)
                        test_numbers_per_suite[suite_name].add(test_number)
                        # Update suite_summary
                        if "FAILED" in result and "WAIVER" in result:
                            suite_summary["total_failed_with_waiver"] += 1
                        elif result == "PASSED":
                            suite_summary["total_passed"] += 1
                        elif result == "FAILED":
                            suite_summary["total_failed"] += 1
                        elif result == "ABORTED":
                            suite_summary["total_aborted"] += 1
                        elif result == "SKIPPED":
                            suite_summary["total_skipped"] += 1
                        elif result == "WARNING":
                            suite_summary["total_warnings"] += 1
                        # Reset variables
                        in_test = False
                        test_number = ""
                        test_name = ""
                        test_description = ""
                        result = ""
                        rules = ""
                        i +=1
                        continue
                    # Try to match test line without result
                    test_line_match = re.match(r'^\s*(\d+)\s*:\s*(.*)$', line)
                    if test_line_match:
                        test_number = test_line_match.group(1).strip()
                        test_name = test_line_match.group(2).strip()
                        in_test = True
                        test_description = ""
                        result = ""
                        rules = ""
                        i +=1
                        continue
                    elif in_test:
                        if ': Result:' in line:
                            result_match = re.search(r': Result:\s*(\w+)', line)
                            if result_match:
                                result = result_mapping.get(result_match.group(1).strip(), result_match.group(1).strip())
                            else:
                                result = "UNKNOWN"
                            # Check for duplicates
                            if test_number in test_numbers_per_suite[suite_name]:
                                i +=1
                                in_test = False  # Reset in_test flag
                                continue  # Skip adding duplicate test
                            # Create subtest_entry
                            subtest_entry = {
                                "sub_Test_Number": test_number,
                                "sub_Test_Description": test_name,
                                "sub_test_result": result
                            }
                            # Add rules if any
                            if result == "FAILED" and rules:
                                subtest_entry["RULES FAILED"] = rules.strip()
                            elif result == "SKIPPED" and rules:
                                subtest_entry["RULES SKIPPED"] = rules.strip()
                            # Append subtest_entry to result_data
                            result_data[suite_name].append(subtest_entry)
                            test_numbers_per_suite[suite_name].add(test_number)
                            # Update suite_summary
                            if "FAILED" in result and "WAIVER" in result:
                                suite_summary["total_failed_with_waiver"] += 1
                            elif result == "PASSED":
                                suite_summary["total_passed"] += 1
                            elif result == "FAILED":
                                suite_summary["total_failed"] += 1
                            elif result == "ABORTED":
                                suite_summary["total_aborted"] += 1
                            elif result == "SKIPPED":
                                suite_summary["total_skipped"] += 1
                            elif result == "WARNING":
                                suite_summary["total_warnings"] += 1
                            # Reset variables
                            in_test = False
                            test_number = ""
                            test_name = ""
                            test_description = ""
                            result = ""
                            rules = ""
                            i +=1
                            continue
                        else:
                            # Check if line is rules
                            if re.match(r'^[A-Z0-9_ ,]+$', line.strip()) or line.strip().startswith('Appendix'):
                                if rules:
                                    rules += ' ' + line.strip()
                                else:
                                    rules = line.strip()
                            else:
                                # Append to test_description
                                if test_description:
                                    test_description += ' ' + line.strip()
                                else:
                                    test_description = line.strip()
                            i +=1
                            continue
                    else:
                        i +=1
                        continue
                else:
                    i +=1
                    continue

    # Prepare the final output structure
    formatted_result = {
         "test_results": [],
         "suite_summary": suite_summary
    }

    for test_suite, subtests in result_data.items():
        # Initialize test suite summary
        test_suite_summary = {
            "total_passed": 0,
            "total_failed": 0,
            "total_aborted": 0,
            "total_skipped": 0,
            "total_warnings": 0,
            "total_failed_with_waiver": 0,
            "total_ignored": 0
        }

        # Count test results for the suite
        for subtest in subtests:
            result = subtest['sub_test_result']
            if "FAILED" in result and "WAIVER" in result:
                test_suite_summary["total_failed_with_waiver"] += 1
            elif result == "PASSED":
                test_suite_summary["total_passed"] += 1
            elif result == "FAILED":
                test_suite_summary["total_failed"] += 1
            elif result == "ABORTED":
                test_suite_summary["total_aborted"] += 1
            elif result == "SKIPPED":
                test_suite_summary["total_skipped"] += 1
            elif result == "WARNING":
                test_suite_summary["total_warnings"] += 1

        # Add the test suite and subtests to the result along with the test suite summary
        formatted_result["test_results"].append({
            "Test_suite": test_suite,
            "subtests": subtests,
            "test_suite_summary": test_suite_summary  # Nesting the summary within the test suite object
        })

    # Write the result to the JSON file
    with open(output_file, 'w') as json_file:
        json.dump(formatted_result, json_file, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse Log files and save results to a JSON file.")
    parser.add_argument("input_files", nargs='+', help="Input Log files")
    parser.add_argument("output_file", help="Output JSON file")

    args = parser.parse_args()
    main(args.input_files, args.output_file)
