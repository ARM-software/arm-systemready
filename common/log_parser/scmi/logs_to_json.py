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

import argparse
import chardet
import json
import re
from collections import OrderedDict

STATUS_MAP = {
    "CONFORMANT": "PASSED",
    "NON CONFORMANT": "FAILED",
    "SKIPPED": "SKIPPED",
}

# Matches suite header lines like "*** Starting BASE tests ***".
SUITE_HDR_RE = re.compile(r"\*{3}\s*Starting\s+(.*?)\s+tests\s*\*{3}", re.I)
TEST_LINE_RE = re.compile(
    r"^\s*(\d+)\s*:\s*(.*?)(?:\s*:\s*(CONFORMANT|NON CONFORMANT|SKIPPED))?\s*$",
    re.I,
)
STATUS_LINE_RE = re.compile(r"^(.*?)\s*:\s*(CONFORMANT|NON CONFORMANT|SKIPPED)\s*$", re.I)
# If this appears, treat SCMI as not runnable (no JSON/HTML).
FATAL_SCMI_RE = re.compile(r"Failed to open SCMI raw transport base path", re.I)


def detect_file_encoding(file_path):
    """Detect log encoding so we can read bytes safely."""
    with open(file_path, "rb") as file:
        raw_data = file.read()
    result = chardet.detect(raw_data)
    return result["encoding"] or "utf-8"


def init_summary():
    """Create a fresh summary counter dict."""
    return {
        "total_passed": 0,
        "total_failed": 0,
        "total_failed_with_waiver": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0,
    }


def update_summary(summary, result):
    """Increment counters based on a single testcase result."""
    result_upper = (result or "").upper()
    if "FAILED" in result_upper and "WITH WAIVER" in result_upper:
        summary["total_failed_with_waiver"] += 1
    elif result == "PASSED":
        summary["total_passed"] += 1
    elif result == "FAILED":
        summary["total_failed"] += 1
    elif result == "ABORTED":
        summary["total_aborted"] += 1
    elif result == "SKIPPED":
        summary["total_skipped"] += 1
    elif result == "WARNING":
        summary["total_warnings"] += 1


def parse_scmi_logs(input_files):
    """Parse SCMI log files into the common JSON structure."""
    suites = OrderedDict()
    overall_summary = init_summary()
    current_suite = ""
    current_test = None
    current_details = []
    # Only parse after SCMI banner appears.
    run_started = False

    def ensure_suite(suite_name):
        """Ensure suite entry exists before appending testcases."""
        suite_name = (suite_name or "unknown").lower()
        if suite_name not in suites:
            suites[suite_name] = {
                "Test_suite": suite_name,
                "testcases": [],
                "test_suite_summary": init_summary(),
            }

    def add_testcase(suite_name, number, description, result, reason=None):
        """Append a testcase and update per-suite and overall summaries."""
        if not suite_name:
            suite_name = "unknown"
        suite_name = suite_name.lower()
        ensure_suite(suite_name)
        testcase = {
            "Test_case": str(number),
            "Test_case_description": description,
            "Test_result": result,
        }
        if reason:
            testcase["reason"] = reason
        suites[suite_name]["testcases"].append(testcase)
        update_summary(suites[suite_name]["test_suite_summary"], result)
        update_summary(overall_summary, result)
        return

    def start_new_run():
        """Reset state when a new SCMI run banner appears."""
        nonlocal suites, overall_summary, current_suite, current_test, current_details, run_started
        suites = OrderedDict()
        overall_summary = init_summary()
        current_suite = ""
        current_test = None
        current_details = []
        run_started = True

    for input_file in input_files:
        file_encoding = detect_file_encoding(input_file)
        with open(input_file, "r", encoding=file_encoding, errors="ignore") as f:
            lines = f.read().splitlines()

        for raw_line in lines:
            line = raw_line.rstrip()

            if "**** SCMI Compliance Suite ****" in line:
                start_new_run()
                continue

            if run_started and FATAL_SCMI_RE.search(line):
                # Signal caller to skip SCMI entirely.
                return None

            if not run_started:
                continue

            suite_hdr = SUITE_HDR_RE.search(line)
            if suite_hdr:
                current_suite = suite_hdr.group(1).strip()
                current_test = None
                current_details = []
                continue

            test_match = TEST_LINE_RE.match(line)
            if test_match:
                number = test_match.group(1).strip()
                description = test_match.group(2).strip()
                status_raw = test_match.group(3)
                if status_raw:
                    status = STATUS_MAP.get(status_raw.upper(), status_raw.upper())
                    reason = None
                    if status in ("FAILED", "SKIPPED") and current_details:
                        reason = "; ".join(current_details)
                    add_testcase(current_suite, number, description, status, reason)
                    current_test = None
                    current_details = []
                else:
                    current_test = (number, description)
                    current_details = []
                continue

            if current_test:
                status_match = STATUS_LINE_RE.match(line.strip())
                if status_match:
                    reason_text = status_match.group(1).strip()
                    status_raw = status_match.group(2)
                    status = STATUS_MAP.get(status_raw.upper(), status_raw.upper())
                    number, description = current_test
                    reason = None
                    if status in ("FAILED", "SKIPPED"):
                        reason_upper = reason_text.upper()
                        if status == "FAILED":
                            # Prefer CHECK/EXPECTED/RECEIVED lines as failure reason.
                            reason_parts = list(current_details)
                            if "EXPECTED" in reason_upper or "RECEIVED" in reason_upper:
                                reason_parts.append(reason_text)
                            if reason_parts:
                                reason = "; ".join(reason_parts)
                        elif reason_text and "0X" not in reason_upper and reason_upper not in (
                            "VERSION",
                            "CHECK STATUS",
                            "CHECK HEADER",
                            "CHECK RSVD BITS",
                            "CHECK STATUS   ",
                            "CHECK HEADER   ",
                            "PROTOCOL LIST",
                        ):
                            # Keep short, human-readable skip reason.
                            reason = reason_text
                        elif current_details:
                            reason = "; ".join(current_details)
                    add_testcase(current_suite, number, description, status, reason)
                    current_test = None
                    current_details = []
                else:
                    detail = line.strip()
                    upper_detail = detail.upper()
                    # Collect useful detail lines for failure reasons.
                    if "EXPECTED" in upper_detail or "RECEIVED" in upper_detail or ("CHECK" in upper_detail and "FAILED" in upper_detail):
                        current_details.append(detail)
                continue

    if not suites:
        return {}

    return {
        "test_results": list(suites.values()),
        "suite_summary": overall_summary,
    }


def main(input_files, output_file):
    """CLI entry point: parse logs and write JSON."""
    data = parse_scmi_logs(input_files)
    if data is None:
        raise SystemExit(2)
    if not data:
        raise SystemExit(1)
    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse SCMI logs and save results to JSON.")
    parser.add_argument("input_files", nargs="+", help="One or more SCMI log files")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()
    main(args.input_files, args.output_file)
