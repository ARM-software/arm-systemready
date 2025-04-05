#!/usr/bin/env python3i
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

import re
import json
import argparse
import os

def parse_tpm_log(lines):
    # Single test-entry approach:
    tpm_entry = {
        "Test_suite": "BBSR-TPM",
        "Sub_test_suite": "TPM",
        "Test_case": "TPM",
        "Test_case_description": "TPM event log verification results",
        "subtests": [],
        "test_case_summary": {
            "total_passed": 0,
            "total_failed": 0,
            "total_failed_with_waiver": 0,
            "total_aborted": 0,
            "total_skipped": 0,
            "total_warnings": 0,
            "total_ignored": 0
        }
    }

    pattern = re.compile(r'^Verify\s+.*:\s+(PASS|FAIL|ABORTED|SKIPPED|WARNING)', re.IGNORECASE)
    subtest_number = 0

    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')
        i += 1

        match = pattern.search(line)
        if match:
            # Extract the subtest description (everything before ": <RESULT>").
            # Example line:"Verify EV_POST_CODE events ... with recommended strings : FAIL"
            # We do a split by " : "
            parts = line.split(':')
            subtest_desc = parts[0].strip()  # e.g. "Verify EV_POST_CODE events ... recommended strings"
            result_str = parts[-1].strip().upper()  # e.g. "FAIL"

            # Grab any indented lines as "reason"
            reason_lines = []
            while i < len(lines):
                nxt = lines[i].rstrip('\n')
                # Break if the line is not indented
                if not nxt.strip() or re.match(r'^\S', nxt):
                    break
                reason_lines.append(nxt.strip())
                i += 1
            reason = reason_lines  # Store as a list of strings


            subtest_number += 1
            sub_test = {
                "sub_Test_Number": str(subtest_number),
                "sub_Test_Description": subtest_desc,
                "sub_test_result": result_str,
                "reason": reason
            }

            # Tally the results in test_case_summary
            summary = tpm_entry["test_case_summary"]
            upper_rs = result_str.upper()

            if "PASS" in upper_rs:
                summary["total_passed"] += 1
            elif "FAIL" in upper_rs:  # catches "FAIL", "FAILED", "FAILURE", etc.
                summary["total_failed"] += 1
                if "WITH WAIVER" in upper_rs:
                    summary["total_failed_with_waiver"] += 1
            elif "ABORTED" in upper_rs:
                summary["total_aborted"] += 1
            elif "SKIPPED" in upper_rs:
                summary["total_skipped"] += 1
            elif "WARNING" in upper_rs:
                summary["total_warnings"] += 1
            else:
                summary["total_ignored"] += 1


            tpm_entry["subtests"].append(sub_test)

    return tpm_entry

def main(input_file, output_file):
    if not os.path.isfile(input_file):
        print(f"ERROR: Input file '{input_file}' not found.")
        return

    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # Parse the TPM log
    tpm_entry = parse_tpm_log(lines)

    # If we found zero subtests, you can optionally handle that
    if len(tpm_entry["subtests"]) == 0:
        print(f"WARNING: No 'Verify ... : PASS|FAIL' patterns found in {input_file}.")

    # Build the suite_summary from the single test_entry
    summary = tpm_entry["test_case_summary"]
    suite_summary = {
        "total_passed": summary["total_passed"],
        "total_failed": summary["total_failed"],
        "total_failed_with_waiver": summary["total_failed_with_waiver"],
        "total_aborted": summary["total_aborted"],
        "total_skipped": summary["total_skipped"],
        "total_warnings": summary["total_warnings"],
        "total_ignored": summary["total_ignored"]
    }

    output_data = {
        "test_results": [tpm_entry],
        "suite_summary": suite_summary
    }

    # Write out JSON
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump(output_data, out_f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse TPM logs and convert to JSON (similar to SCT format).")
    parser.add_argument("input_file", help="Path to TPM log file")
    parser.add_argument("output_file", help="Path to output JSON file")
    args = parser.parse_args()
    main(args.input_file, args.output_file)
