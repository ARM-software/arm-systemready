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

def classify_status(status_text):
    if not status_text:
        return "UNKNOWN", None

    up = status_text.upper()

    # Failed with waiver
    if "FAILED" in up and "WAIVER" in up:
        formatted_result = "FAILED (WITH WAIVER)"
        summary_category = "Failed"
        return formatted_result, summary_category

    # Passed partial
    if "PASSED" in up and "PARTIAL" in up:
        formatted_result = "PASSED(*PARTIAL)"
        summary_category = "Passed (Partial)"
        return formatted_result, summary_category

    # PAL not supported
    if "NOT TESTED" in up and "PAL NOT SUPPORTED" in up:
        formatted_result = "NOT TESTED (PAL NOT SUPPORTED)"
        summary_category = "PAL Not Supported"
        return formatted_result, summary_category

    # Test not implemented
    if "NOT TESTED" in up and "TEST NOT IMPLEMENTED" in up:
        formatted_result = "NOT TESTED (TEST NOT IMPLEMENTED)"
        summary_category = "Test Not Implemented"
        return formatted_result, summary_category

    # Plain passed / failed / skipped
    if "PASSED" in up and "PARTIAL" not in up:
        formatted_result = "PASSED"
        summary_category = "Passed"
        return formatted_result, summary_category

    if "FAILED" in up and "WAIVER" not in up:
        formatted_result = "FAILED"
        summary_category = "Failed"
        return formatted_result, summary_category

    if "SKIPPED" in up:
        formatted_result = "SKIPPED"
        summary_category = "Skipped"
        return formatted_result, summary_category

    # STATUS → warnings
    if up.startswith("STATUS:"):
        formatted_result = "STATUS"
        summary_category = "Warnings"
        return formatted_result, summary_category

    # Fallback
    formatted_result = status_text
    summary_category = None
    return formatted_result, summary_category

def init_summary():
    return {
        "Total Rules Run": 0,
        "Passed": 0,
        "Passed (Partial)": 0,
        "Warnings": 0,
        "Skipped": 0,
        "Failed": 0,
        "PAL Not Supported": 0,
        "Not Implemented": 0,
        "Total_failed_with_waiver": 0
    }

def update_summary_counts(summary, summary_category, formatted_result):
    # Always increment total rules run
    summary["Total Rules Run"] += 1

    if summary_category is None:
        return

    if summary_category == "Passed":
        summary["Passed"] += 1
    elif summary_category == "Failed":
        summary["Failed"] += 1
        if "WAIVER" in formatted_result:
            summary["Total_failed_with_waiver"] += 1
    elif summary_category == "Skipped":
        summary["Skipped"] += 1
    elif summary_category == "Passed (Partial)":
        summary["Passed (Partial)"] += 1
    elif summary_category == "PAL Not Supported":
        summary["PAL Not Supported"] += 1
    elif summary_category == "Test Not Implemented":
        summary["Not Implemented"] += 1
    elif summary_category == "Warnings":
        summary["Warnings"] += 1

def main(input_files, output_file):
    # Per-suite list of testcases
    testcases_per_suite = defaultdict(list)
    # Per-suite summary
    suite_summaries = defaultdict(init_summary)
    # Global summary
    total_summary = init_summary()

    # Active main testcases (B_* rules etc.)
    # key: rule_id -> metadata
    active_main = {}
    # Active subtests
    # key: rule_id -> metadata
    active_sub = {}
    # Stack of currently open main test IDs (for nesting)
    parent_stack = []

    current_suite = ""

    processing = False

    for input_file in input_files:
        file_encoding = detect_file_encoding(input_file)

        with open(input_file, "r", encoding=file_encoding, errors="ignore") as f:
            lines = f.read().splitlines()

        i = 0
        while i < len(lines):
            raw_line = lines[i]
            i += 1

            # Strip timestamp [....] if present (keep spaces after timestamp for indentation detection)
            line_no_timestamp = re.sub(r'^\s*\[.*?\]\s?', '', raw_line)

            # NOW detect indentation level (count leading spaces AFTER timestamp removal)
            indent_match = re.match(r'^(\s*)', line_no_timestamp)
            indent_spaces = len(indent_match.group(1)) if indent_match else 0
            is_indented = indent_spaces > 0

            # Strip the leading spaces to get clean line
            line = line_no_timestamp.strip()

            if not line:
                continue

            # Start processing when we see Selected rules or Running tests or START
            if not processing and (
                "---------------------- Running tests ------------------------" in line
                or line.startswith("Selected rules:")
                or line.startswith("START ")
            ):
                processing = True

            if not processing:
                continue

            #   START <suite_or_dash> <RULE_ID> <index_or_dash> : <description...>
            start_match = re.match(
                r'^START\s+([^\s:]+)\s+([A-Za-z0-9_]+)\s+([^\s:]+)\s*:\s*(.*)$',
                line
            )
            if start_match:
                suite_tok = start_match.group(1).strip()
                rule_id = start_match.group(2).strip()
                index_tok = start_match.group(3).strip()
                desc = (start_match.group(4) or "").strip()

                # Update current suite unless '-'
                if suite_tok != "-":
                    current_suite = suite_tok

                if not current_suite:
                    # Leave empty if genuinely unknown, but usually logs set it.
                    current_suite = ""

                # Normalize index
                test_index = index_tok if index_tok != "" else "-"

                # Decide if this is a main testcase or a subtest based on indentation:
                # - Non-indented lines = main testcases (B_*, S_*, GPU_*, PCI_ER_*, etc.)
                # - Indented lines = subtests (nested under current parent)
                is_main = not is_indented

                if is_main:
                    # Main rule
                    meta = {
                        "suite": current_suite,
                        "rule_id": rule_id,
                        "index": test_index,
                        "description": desc,
                        "subtests": []
                    }
                    active_main[rule_id] = meta
                    parent_stack.append(rule_id)
                else:
                    # Subrule / subtest under current parent (if indented or non-B_ rule)
                    parent_id = parent_stack[-1] if parent_stack else None
                    meta = {
                        "suite": current_suite,
                        "rule_id": rule_id,
                        "index": test_index,
                        "description": desc,
                        "parent": parent_id,
                        "is_indented": is_indented
                    }
                    active_sub[rule_id] = meta

                continue

            # END line:
            #   END <RULE_ID> <status text...>
            end_match = re.match(r'^END\s+([A-Za-z0-9_]+)\s+(.*)$', line)
            if end_match:
                rule_id = end_match.group(1).strip()
                status_text = (end_match.group(2) or "").strip()

                formatted_result, summary_category = classify_status(status_text)

                # Check if this is a subtest (in active_sub)
                if rule_id in active_sub:
                    sub_meta = active_sub.pop(rule_id)
                    parent_id = sub_meta.get("parent")
                    if parent_id and parent_id in active_main:
                        parent_meta = active_main[parent_id]
                        sub_entry = {
                            "sub_Test_Number": f"{rule_id} : {sub_meta.get('index', '-')}",
                            "sub_Rule_ID": rule_id,
                            "sub_Test_Description": sub_meta.get("description", ""),
                            "sub_test_result": formatted_result
                        }
                        parent_meta["subtests"].append(sub_entry)
                    # No summary update for subtests
                    continue

                # Check if this is a main testcase (in active_main)
                if rule_id in active_main:
                    meta = active_main.pop(rule_id)

                    # Pop from parent stack if this was the last main opened
                    if parent_stack and parent_stack[-1] == rule_id:
                        parent_stack.pop()

                    suite = meta.get("suite", "")
                    desc = meta.get("description", "")
                    index = meta.get("index", "-")
                    subtests = meta.get("subtests", [])

                    # Build testcase object
                    testcase = {
                        "Test_case": f"{rule_id} : {index}",
                        "Test_case_description": desc,
                        "Test_result": formatted_result
                    }
                    if subtests:
                        testcase["subtests"] = subtests

                    # Per-testcase summary (one-hot)
                    tcs = init_summary()
                    update_summary_counts(tcs, summary_category, formatted_result)
                    testcase["Test_case_summary"] = tcs

                    # Append to suite
                    testcases_per_suite[suite].append(testcase)

                    # Update per-suite summary
                    update_summary_counts(suite_summaries[suite], summary_category, formatted_result)
                    # Update global summary
                    update_summary_counts(total_summary, summary_category, formatted_result)

                    continue

                # Ignore END lines for unknown rule IDs (not in active_sub or active_main)
                continue

            # Ignore all other lines (debug, informational, etc.)
            continue

    # Build final JSON structure
    output = {
        "test_results": [],
        "suite_summary": total_summary
    }

    # Deterministic ordering by suite name
    for suite_name in sorted(testcases_per_suite.keys()):
        suite_obj = {
            "Test_suite": suite_name,
            "testcases": testcases_per_suite[suite_name],
            "test_suite_summary": suite_summaries[suite_name]
        }
        output["test_results"].append(suite_obj)

    with open(output_file, "w") as jf:
        json.dump(output, jf, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse BSA ACS log files and save results to a JSON file."
    )
    parser.add_argument("input_files", nargs="+", help="Input log files")
    parser.add_argument("output_file", help="Output JSON file")

    args = parser.parse_args()
    main(args.input_files, args.output_file)
