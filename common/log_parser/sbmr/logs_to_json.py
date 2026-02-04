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

#Parse SBMR Robot Framework XML output into the SBMR JSON schema.

import json
import argparse
import xml.etree.ElementTree as ET
from collections import OrderedDict

# ---------- constants ----------

RESULT_MAP = {
    "PASS": "PASSED",
    "PASSED": "PASSED",
    "FAIL": "FAILED",
    "FAILED": "FAILED",
    "SKIP": "SKIPPED",
    "SKIPPED": "SKIPPED",
    "ABORT": "ABORTED",
    "ABORTED": "ABORTED",
    "WARN": "WARNING",
    "WARNING": "WARNING",
}


# ---------- Helpers ----------

def trim_inline_noise(s: str) -> str:
    # Return a cleaned description string.
    return (s or "").strip()


# ---------- Parser ----------

def _empty_summary():
    # Return zeroed counters for suite/case summaries.
    return {
        "total_passed": 0,
        "total_failed": 0,
        "total_failed_with_waiver": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0,
        "total_ignored": 0
    }

def _result_from_status(status_word: str) -> str:
    # Map Robot status strings to SBMR labels.
    mapped = RESULT_MAP.get((status_word or "").upper(), (status_word or "").upper())
    return mapped or "UNKNOWN"

def _case_name_from_suite_name(name: str) -> str:
    # Use the suite name as the case name when present.
    if not name:
        return None
    return name

def _extract_reason_from_test(test_elem):
    # Extract a failure reason from status text or the first FAIL/ERROR message.
    status_elem = test_elem.find("status")
    if status_elem is not None:
        reason = (status_elem.text or "").strip()
        if reason:
            return reason
    for msg in test_elem.iter("msg"):
        level = msg.get("level", "").upper()
        if level in ("FAIL", "ERROR"):
            msg_text = (msg.text or "").strip()
            if msg_text:
                return msg_text
    return None

def parse_robot_xml(input_file, output_file):
    # Parse Robot Framework output.xml into SBMR JSON.
    suites = OrderedDict()
    overall = _empty_summary()
    global_subtest_num = 0

    def ensure_suite(suite_name: str):
        # Create a suite entry when missing.
        if not suite_name:
            suite_name = "Unknown"
        if suite_name not in suites:
            # One suite groups multiple cases and their subtests.
            suites[suite_name] = {
                "Test_suite": suite_name,
                "Test_cases": [],
                "test_suite_summary": _empty_summary()
            }

    def ensure_case(suite_name: str, case_name: str):
        # Create a case entry under the suite when missing.
        if not case_name:
            return
        ensure_suite(suite_name)
        suite_obj = suites[suite_name]
        # Create a new case only when the name changes.
        if not suite_obj["Test_cases"] or suite_obj["Test_cases"][-1]["Test_case"] != case_name:
            suite_obj["Test_cases"].append({
                "Test_case": case_name,
                "subtests": [],
                "test_case_summary": _empty_summary()
            })

    def tally(result_mapped: str, suite_name: str, case_idx: int):
        # Increment suite and case counters for one subtest result.
        ssum = suites[suite_name]["test_suite_summary"]
        csum = suites[suite_name]["Test_cases"][case_idx]["test_case_summary"]
        def bump(bucket):
            ssum[bucket] += 1
            csum[bucket] += 1
            overall[bucket] += 1
        if result_mapped == "PASSED":
            bump("total_passed")
        elif result_mapped == "FAILED":
            bump("total_failed")
        elif result_mapped == "ABORTED":
            bump("total_aborted")
        elif result_mapped == "SKIPPED":
            bump("total_skipped")
        elif result_mapped == "WARNING":
            bump("total_warnings")

    def add_subtest(suite_name, case_name, description, result_word, reason):
        # Add one subtest entry and update counters.
        nonlocal global_subtest_num
        ensure_case(suite_name, case_name)
        suite_obj = suites[suite_name]
        case_idx = len(suite_obj["Test_cases"]) - 1
        global_subtest_num += 1
        mapped = _result_from_status(result_word)
        sub = {
            "sub_Test_Number": str(global_subtest_num),
            "sub_Test_Description": trim_inline_noise(description or ""),
            "sub_test_result": mapped
        }
        if reason:
            sub["reason"] = reason
        suite_obj["Test_cases"][case_idx]["subtests"].append(sub)
        tally(mapped, suite_name, case_idx)

    # Robot Framework output.xml
    tree = ET.parse(input_file)
    root = tree.getroot()

    def walk_suite(suite_elem, suite_path):
        name = (suite_elem.get("name") or "").strip()
        next_path = suite_path + ([name] if name else [])
        for test_elem in suite_elem.findall("test"):
            test_name = (test_elem.get("name") or "").strip()
            # Use the test-level <status> (keyword statuses are nested).
            status_elem = test_elem.find("status")
            status_word = status_elem.get("status") if status_elem is not None else ""
            reason = _extract_reason_from_test(test_elem) if status_word and status_word.upper() != "PASS" else None

            # Suite/case mapping: suite is level-2 name, case is level-3 name.
            suite_name = next_path[1] if len(next_path) >= 2 else "Unknown"
            case_name = None
            if len(next_path) >= 3:
                case_name = _case_name_from_suite_name(next_path[2])
            if not case_name:
                case_name = _case_name_from_suite_name(test_name) or "General"

            add_subtest(suite_name, case_name, test_name, status_word, reason)

        for child in suite_elem.findall("suite"):
            walk_suite(child, next_path)

    for top_suite in root.findall("suite"):
        walk_suite(top_suite, [])

    finalize_and_write(suites, output_file)

def finalize_and_write(suites, output_file):
    # Drop empty cases, recompute totals, and write the output JSON.
    for suite_name in list(suites.keys()):
        cases = suites[suite_name]["Test_cases"]
        filtered = [c for c in cases if c["subtests"]]
        suites[suite_name]["Test_cases"] = filtered

    def recompute_overall():
        # Aggregate totals from each suite summary.
        recomputed = _empty_summary()
        for s in suites.values():
            ss = s["test_suite_summary"]
            for k in recomputed:
                recomputed[k] += ss.get(k, 0)
        return recomputed

    output = {
        "test_results": list(suites.values()),
        "suite_summary": recompute_overall()
    }

    with open(output_file, "w") as jf:
        json.dump(output, jf, indent=4)

def main(input_file, output_file):
    # CLI entrypoint.
    parse_robot_xml(input_file, output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse SBMR log (IB or OOB) into grouped JSON (one Test_suite with multiple Test_case entries)."
    )
    parser.add_argument("input_file", help="SBMR console log file")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()
    main(args.input_file, args.output_file)
