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

import json
import os
import re

def parse_capsule_update_log(lines):
    tests = []
    i = 0
    total_lines = len(lines)
    while i < total_lines:
        line = lines[i].strip()
        # Flexible matching for "Testing unauth.bin update" or "Testing tampered.bin update"
        match = re.match(r"Testing\s+(unauth\.bin|tampered\.bin)\s+update", line, re.IGNORECASE)
        if match:
            test_description = line
            test_info = ''
            test_result = 'FAILED'  # Default to FAILED
            i += 1
            # Look for 'Test_Info'
            while i < total_lines:
                current_line = lines[i].strip()
                if re.match(r"Testing\s+", current_line, re.IGNORECASE):
                    # Next test starts
                    break
                elif re.match(r"Test[_\s]Info", current_line, re.IGNORECASE):
                    # Start collecting Test_Info
                    i += 1
                    info_lines = []
                    while i < total_lines:
                        info_line = lines[i].strip()
                        if re.match(r"Testing\s+", info_line, re.IGNORECASE):
                            # Next test starts
                            i -= 1
                            break
                        info_lines.append(info_line)
                        i += 1
                    test_info = '\n'.join(info_lines)
                    # Determine result based on user specification
                    if "failed to update capsule" in test_info.lower():
                        test_result = 'PASSED'  # According to user, this is a PASS case
                    elif "not present" in test_info.lower():
                        test_result = 'FAILED'
                    elif "succeed to write" in test_info.lower():
                        test_result = 'PASSED'
                    else:
                        test_result = 'FAILED'
                    break
                else:
                    i += 1
            tests.append({
                'Test_Description': test_description,
                'Test_Info': test_info,
                'Test_Result': test_result
            })
        else:
            i += 1
    return tests

def parse_capsule_on_disk_log(lines):
    tests = []
    i = 0
    total_lines = len(lines)
    while i < total_lines:
        line = lines[i].strip()
        # Flexible matching for "Testing signed_capsule.bin OD update"
        match = re.match(r"Testing\s+signed_capsule\.bin\s+OD\s+update", line, re.IGNORECASE)
        if match:
            test_description = line
            test_info = ''
            test_result = 'FAILED'  # Default to FAILED
            i += 1
            # Look for 'Test_Info'
            while i < total_lines:
                current_line = lines[i].strip()
                if re.match(r"Testing\s+", current_line, re.IGNORECASE):
                    # Next test starts
                    break
                elif re.match(r"Test[_\s]Info", current_line, re.IGNORECASE):
                    # Start collecting Test_Info
                    i += 1
                    info_lines = []
                    while i < total_lines:
                        info_line = lines[i].strip()
                        if re.match(r"Testing\s+", info_line, re.IGNORECASE):
                            # Next test starts
                            i -= 1
                            break
                        info_lines.append(info_line)
                        i += 1
                    test_info = '\n'.join(info_lines)
                    # Determine result based on user specification
                    if "signed_capsule.bin not present" in test_info.lower():
                        test_result = 'FAILED'
                    elif "succeed to write signed_capsule.bin" in test_info.lower():
                        if "uefi capsule update has failed" in test_info.lower():
                            test_result = 'FAILED'
                        else:
                            test_result = 'PASSED'
                    else:
                        test_result = 'FAILED'
                    break
                else:
                    i += 1
            tests.append({
                'Test_Description': test_description,
                'Test_Info': test_info,
                'Test_Result': test_result
            })
        else:
            i += 1
    return tests

def parse_capsule_test_results_log(lines):
    tests = []
    i = 0
    total_lines = len(lines)
    while i < total_lines:
        line = lines[i].strip()
        # Flexible matching for different test descriptions
        sanity_match = re.match(r"Testing\s+signed_capsule\.bin\s+sanity", line, re.IGNORECASE)
        esrt_match = re.match(r"(Testing|Test:\s+Testing)\s+ESRT\s+FW\s+version\s+update", line, re.IGNORECASE)
        
        if sanity_match:
            test_description = line
            test_info = ''
            test_result = 'PASSED'  # Default to PASSED
            i += 1
            while i < total_lines:
                current_line = lines[i].strip()
                if re.match(r"Testing\s+", current_line, re.IGNORECASE) or re.match(r"Test:\s+", current_line, re.IGNORECASE):
                    # Next test starts
                    break
                elif "error sanity_check_capsule" in current_line.lower():
                    test_info = current_line
                    test_result = 'FAILED'
                    break
                elif "warning" in current_line.lower():
                    test_info = current_line
                    test_result = 'PASSED'
                    break
                else:
                    i += 1
            tests.append({
                'Test_Description': test_description,
                'Test_Info': test_info,
                'Test_Result': test_result
            })
        elif esrt_match:
            test_description = "Testing ESRT FW version update"
            test_info = ''
            test_result = 'FAILED'  # Default to FAILED
            i += 1
            while i < total_lines:
                current_line = lines[i].strip()
                if re.match(r"Testing\s+", current_line, re.IGNORECASE) or re.match(r"Test:\s+", current_line, re.IGNORECASE):
                    # Next test starts
                    break
                elif current_line.lower().startswith("info:"):
                    test_info = current_line[len("INFO:"):].strip()
                    i += 1
                elif current_line.lower().startswith("results:"):
                    result_line = current_line[len("RESULTS:"):].strip()
                    if result_line.upper() == "PASSED":
                        test_result = 'PASSED'
                    else:
                        test_result = 'FAILED'
                    break
                else:
                    i += 1
            tests.append({
                'Test_Description': test_description,
                'Test_Info': test_info,
                'Test_Result': test_result
            })
        else:
            i += 1
    return tests

def main():
    tests = []

    # Hardcoded paths to the log files
    capsule_update_log_path = '/mnt/acs_results_template/fw/capsule-update.log'
    capsule_on_disk_log_path = '/mnt/acs_results_template/fw/capsule-on-disk.log'
    capsule_test_results_log_path = '/mnt/acs_results/app_output/capsule_test_results.log'

    # Output JSON file path
    output_file = '/mnt/acs_results/acs_summary/acs_jsons/capsule_update.json'

    # Function to read log file with specified encoding and debugging
    def read_log_file(path, encoding='utf-8'):
        try:
            with open(path, 'r', encoding=encoding, errors='ignore') as file:
                lines = file.readlines()
            print(f"Successfully read {path} with encoding {encoding}. Total lines: {len(lines)}")
            return lines
        except Exception as e:
            print(f"Error reading {path} with encoding {encoding}: {e}")
            return []

    # Parse capsule-update.log (UTF-16 LE)
    if os.path.exists(capsule_update_log_path):
        lines = read_log_file(capsule_update_log_path, encoding='utf-16')  # Use 'utf-16' to handle BOM
        if lines:
            parsed_update_tests = parse_capsule_update_log(lines)
            tests.extend(parsed_update_tests)
            print(f"Parsed {len(parsed_update_tests)} tests from {capsule_update_log_path}")
        else:
            print(f"No content found or failed to read {capsule_update_log_path}")
    else:
        print(f"Error: {capsule_update_log_path} not found.")

    # Parse capsule-on-disk.log (UTF-8)
    if os.path.exists(capsule_on_disk_log_path):
        lines = read_log_file(capsule_on_disk_log_path, encoding='utf-8')  # Use 'UTF-8' to handle BOM
        if lines:
            parsed_on_disk_tests = parse_capsule_on_disk_log(lines)
            tests.extend(parsed_on_disk_tests)
            print(f"Parsed {len(parsed_on_disk_tests)} tests from {capsule_on_disk_log_path}")
        else:
            print(f"No content found or failed to read {capsule_on_disk_log_path}")
    else:
        print(f"Error: {capsule_on_disk_log_path} not found.")

    # Parse capsule_test_results.log (UTF-8)
    if os.path.exists(capsule_test_results_log_path):
        lines = read_log_file(capsule_test_results_log_path, encoding='utf-8')
        if lines:
            parsed_test_results = parse_capsule_test_results_log(lines)
            tests.extend(parsed_test_results)
            print(f"Parsed {len(parsed_test_results)} tests from {capsule_test_results_log_path}")
        else:
            print(f"No content found or failed to read {capsule_test_results_log_path}")
    else:
        print(f"Error: {capsule_test_results_log_path} not found.")

    # Calculate summary
    summary = {
        'total_PASSED': sum(1 for t in tests if t['Test_Result'] == 'PASSED'),
        'total_FAILED': sum(1 for t in tests if t['Test_Result'] == 'FAILED'),
        'total_SKIPPED': sum(1 for t in tests if t['Test_Result'] == 'SKIPPED'),
    }

    # Prepare final JSON structure
    output_data = {
        'Test_Suite': 'Capsule Update Tests',
        'Tests': tests,
        'Summary': summary
    }

    # Write to JSON file
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(output_data, json_file, indent=2)
        print(f"Parsing complete. Results saved to {output_file}")
    except Exception as e:
        print(f"Error writing to {output_file}: {e}")

if __name__ == "__main__":
        main()
