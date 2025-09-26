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
from pathlib import Path
import sys

RESULT_MAP = {
    "PASS": "PASSED",
    "PASSED": "PASSED",
    "FAIL": "FAILED",
    "FAILED": "FAILED",
    "ABORT": "ABORTED",
    "ABORTED": "ABORTED",
    "SKIP": "SKIPPED",
    "SKIPPED": "SKIPPED",
    "WARN": "WARNING",
    "WARNING": "WARNING",
}

def detect_file_encoding(path: Path) -> str:
    raw = path.read_bytes()
    return chardet.detect(raw)["encoding"] or "utf‑8"

def parse_files(input_files, output_file):
    processing = False
    in_test = False
    suite_name = ""
    test_number = ""
    test_name = ""
    reason_lines = []

    result_data = defaultdict(list)
    test_numbers_per_suite = defaultdict(set)

    suite_summary = dict.fromkeys(
        ["total_passed", "total_failed", "total_aborted", "total_skipped", "total_warnings"],
        0,
    )

    for file_name in input_files:
        path = Path(file_name)
        enc = detect_file_encoding(path)

        with path.open("r", encoding=enc, errors="ignore") as fh:
            lines = fh.read().splitlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            banner = re.match(r"\*{3}\s*Starting\s+(.*?)\s+tests\s*\*{3}", line, re.I)
            if banner:
                suite_name = banner.group(1).strip()
                processing = True
                in_test = False
                i += 1
                continue

            if not processing:
                i += 1
                continue

            if not line:
                i += 1
                continue

            header = re.match(r"^\s*(\d+)\s*:\s*(.+?)(?:\s*:\s*Result\s*:\s*([A-Z]+))?$", line, re.I)
            if header:
                test_number = header.group(1).strip()
                test_name = header.group(2).rstrip()
                inline_verdict = header.group(3)
                reason_lines = []
                if inline_verdict:
                    verdict_raw = inline_verdict.upper()
                    verdict = RESULT_MAP.get(verdict_raw, verdict_raw)

                    if test_number not in test_numbers_per_suite[suite_name]:
                        sub = {
                            "sub_Test_Number": test_number,
                            "sub_Test_Description": test_name,
                            "sub_test_result": verdict,
                        }

                        result_data[suite_name].append(sub)
                        test_numbers_per_suite[suite_name].add(test_number)

                        if verdict == "PASSED":
                            suite_summary["total_passed"] += 1
                        elif verdict == "FAILED":
                            suite_summary["total_failed"] += 1
                        elif verdict == "ABORTED":
                            suite_summary["total_aborted"] += 1
                        elif verdict == "SKIPPED":
                            suite_summary["total_skipped"] += 1
                        elif verdict == "WARNING":
                            suite_summary["total_warnings"] += 1

                    in_test = False
                else:
                    in_test = True
                i += 1
                continue

            if in_test:
                verdict_line = re.search(r"Result\s*:\s*([A-Z]+)", line, re.I)
                if verdict_line:
                    verdict_raw = verdict_line.group(1).upper()
                    verdict = RESULT_MAP.get(verdict_raw, verdict_raw)

                    if test_number not in test_numbers_per_suite[suite_name]:
                        sub = {
                            "sub_Test_Number": test_number,
                            "sub_Test_Description": test_name,
                            "sub_test_result": verdict,
                        }
                        if verdict == "FAILED" and reason_lines:
                            sub["reason"] = ", ".join(reason_lines)

                        result_data[suite_name].append(sub)
                        test_numbers_per_suite[suite_name].add(test_number)

                        if verdict == "PASSED":
                            suite_summary["total_passed"] += 1
                        elif verdict == "FAILED":
                            suite_summary["total_failed"] += 1
                        elif verdict == "ABORTED":
                            suite_summary["total_aborted"] += 1
                        elif verdict == "SKIPPED":
                            suite_summary["total_skipped"] += 1
                        elif verdict == "WARNING":
                            suite_summary["total_warnings"] += 1

                    in_test = False
                    test_number = test_name = ""
                    reason_lines = []
                    continue

                # ---- grab first two “failed …” line as reason ----
                if re.search(r"failed", line, re.I) and len(reason_lines) < 2:
                    reason_lines.append(line.strip())

                i += 1
                continue

            i += 1  # default advance




    # ---------- build JSON ----------
    formatted = []
    pfdi_run_true = False
    for suite, subtests in result_data.items():
        local_summary = dict.fromkeys(
            ["total_passed", "total_failed", "total_aborted", "total_skipped", "total_warnings"],
            0,
        )
        for s in subtests:
            res = s["sub_test_result"]
            if res == "PASSED":
                local_summary["total_passed"] += 1
                pfdi_run_true = True
            elif res == "FAILED":
                local_summary["total_failed"] += 1
                pfdi_run_true = True
            elif res == "ABORTED":
                local_summary["total_aborted"] += 1
                pfdi_run_true = True
            elif res == "SKIPPED":
                local_summary["total_skipped"] += 1
                pfdi_run_true = True
            elif res == "WARNING":
                local_summary["total_warnings"] += 1
                pfdi_run_true = True

        formatted.append(
            {
                "Test_suite": suite,
                "subtests": subtests,
                "test_suite_summary": local_summary,
            }
        )

    formatted.append({"Suite_summary": suite_summary})

    #PFDI complaince is conditional requirement, if not implemented no need for json and html
    if not pfdi_run_true:
        sys.exit(1)

    with open(output_file, "w", encoding="utf‑8") as out:
        json.dump(formatted, out, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse PFDI log files and save results to JSON."
    )
    parser.add_argument("input_files", nargs="+", help="One or more PFDI log files")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()
    parse_files(args.input_files, args.output_file)
