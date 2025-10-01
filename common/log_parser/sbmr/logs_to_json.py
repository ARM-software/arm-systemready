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

import json
import argparse
import re
import chardet
from collections import OrderedDict

# ---------- Regex & constants ----------

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

# Accept both IB and OOB
SUITE_HEADER_RE  = re.compile(r'^\s*SBMR-ACS\s+(?:IB|OOB)(?:\.(.*))?\s*$')
TEST_TITLE_RE    = re.compile(r'^\s*(?:Test|Check|Verify)\s+.*', re.IGNORECASE)
RESULT_LINE_RE   = re.compile(r'^\s*\|\s*(PASS|FAIL|SKIP|ABORT|WARNING)\s*\|\s*$')

# Generalize timezone prefix: "#(UTC)" / "#(IST)" / "#(XYZ)"
TZ_PREFIX_RE     = re.compile(r'^\s*#\([^)]+\)\s*\d{4}/\d{2}/\d{2}.*?-')
BRACKET_TS_RE    = re.compile(r'^\[.*?\]\s*')
TRAILING_PIPE_RE = re.compile(r'\s*\|\s*(PASS|FAIL|SKIP|ABORT|WARNING)\s*\|\s*$', re.IGNORECASE)

# Lines that contain both a title and a result on the same line:
# e.g. "Declaration ... | SKIP |"
INLINE_RESULT_RE = re.compile(r'^(?P<title>.+?)\s*\|\s*(?P<res>PASS|FAIL|SKIP|ABORT|WARNING)\s*\|\s*$', re.IGNORECASE)

# Trim noisy tails inside titles
INLINE_TS_SPLIT_MARKS = [" #(", " - Executing:", " - Issuing:"]


# ---------- Helpers ----------

def detect_file_encoding(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    enc = chardet.detect(raw).get("encoding") or "utf-8"
    return enc

def clean_line(s: str) -> str:
    s = s.rstrip("\n")
    s = BRACKET_TS_RE.sub("", s)
    s = TZ_PREFIX_RE.sub("", s).strip()
    return s

def trim_inline_noise(s: str) -> str:
    out = s
    for mark in INLINE_TS_SPLIT_MARKS:
        if mark in out:
            out = out.split(mark, 1)[0]
    return out.strip()

def extract_suite_and_case(fragment: str):
    """
    Map SBMR headers to (suite, case).
      Redfish                                  -> (Redfish, None)
      Redfish.Host Interface                   -> (Redfish, Host Interface)
      Redfish.Host Interface.Test ... :: ...   -> (Redfish, Host Interface)
      Ipmi.Test Ipmi ... :: ...                -> (Ipmi, Ipmi ...)
    """
    if not fragment:
        return (None, None)
    fragment = TRAILING_PIPE_RE.sub("", fragment)  # drop "| PASS |" suffixes
    tokens = [t.strip() for t in fragment.split(".") if t.strip()]
    if not tokens:
        return (None, None)

    suite = tokens[0]
    case = None

    if len(tokens) >= 2:
        t1 = tokens[1]
        if t1.lower().startswith("test "):
            # No explicit "<suite>.<case>" — case comes from the 'Test ...' banner
            t1_core = re.sub(r'^Test\s+', '', t1).split('::', 1)[0].strip()
            case = t1_core or None
        else:
            # "<suite>.<case>"
            case = t1

    return (suite or None, case or None)


# ---------- Parser ----------

def main(input_file, output_file):
    encoding = detect_file_encoding(input_file)

    # Structure:
    # suites["Ipmi"] = {
    #   "Test_suite": "Ipmi",
    #   "Test_cases": [
    #       {"Test_case": "Ipmi ...", "subtests":[...], "test_case_summary": {...}},
    #       ...
    #   ],
    #   "test_suite_summary": {...}
    # }
    suites = OrderedDict()

    # Track per-suite current case for appending
    current_suite = None
    current_case  = None
    pending_title = None
    global_subtest_num = 0

    # reason capture after failures/aborts/skips
    need_reason_for_last = False
    waiting_reason_line  = False
    last_subtest_ref     = None

    # overall summary
    overall = {
        "total_passed": 0,
        "total_failed": 0,
        "total_failed_with_waiver": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0,
        "total_ignored": 0
    }

    def ensure_suite(suite_name: str):
        if not suite_name:
            suite_name = "Unknown"
        if suite_name not in suites:
            suites[suite_name] = {
                "Test_suite": suite_name,
                "Test_cases": [],
                "test_suite_summary": {
                    "total_passed": 0,
                    "total_failed": 0,
                    "total_failed_with_waiver": 0,
                    "total_aborted": 0,
                    "total_skipped": 0,
                    "total_warnings": 0,
                    "total_ignored": 0
                }
            }

    def ensure_case(suite_name: str, case_name: str):
        if not case_name:
            case_name = "General"
        ensure_suite(suite_name)
        suite_obj = suites[suite_name]
        # check last case to avoid duplicates (we only advance when a new case appears)
        if not suite_obj["Test_cases"] or suite_obj["Test_cases"][-1]["Test_case"] != case_name:
            suite_obj["Test_cases"].append({
                "Test_case": case_name,
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
            })

    def tally(result_mapped: str, suite_name: str, case_idx: int):
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

    def add_result(result_word: str):
        nonlocal pending_title, last_subtest_ref, global_subtest_num
        if not pending_title or not current_suite:
            return
        ensure_case(current_suite, current_case)
        suite_obj = suites[current_suite]
        case_idx = len(suite_obj["Test_cases"]) - 1

        global_subtest_num += 1
        mapped = RESULT_MAP.get(result_word.upper(), result_word.upper())

        sub = {
            "sub_Test_Number": str(global_subtest_num),
            "sub_Test_Description": trim_inline_noise(pending_title),
            "sub_test_result": mapped
        }
        suite_obj["Test_cases"][case_idx]["subtests"].append(sub)
        last_subtest_ref = sub
        tally(mapped, current_suite, case_idx)
        pending_title = None

    def add_direct_result(title: str, result_word: str):
        """Handle inline 'title | RESULT |' rows."""
        nonlocal last_subtest_ref, global_subtest_num
        if not title or not current_suite:
            return
        ensure_case(current_suite, current_case)
        suite_obj = suites[current_suite]
        case_idx = len(suite_obj["Test_cases"]) - 1

        global_subtest_num += 1
        mapped = RESULT_MAP.get(result_word.upper(), result_word.upper())
        sub = {
            "sub_Test_Number": str(global_subtest_num),
            "sub_Test_Description": trim_inline_noise(title),
            "sub_test_result": mapped
        }
        suite_obj["Test_cases"][case_idx]["subtests"].append(sub)
        last_subtest_ref = sub
        tally(mapped, current_suite, case_idx)

    with open(input_file, "r", encoding=encoding, errors="ignore") as fh:
        for raw in fh:
            line = clean_line(raw)
            if not line:
                continue

            # -------- reason capture window (banner + fallback) --------
            if need_reason_for_last:
                ll = line.strip()
                low = ll.lower()

                # Prefer the "Original failure:" banner when present
                if not waiting_reason_line and "original failure:" in low:
                    waiting_reason_line = True
                    continue

                if waiting_reason_line:
                    if ll:
                        if last_subtest_ref is not None:
                            last_subtest_ref["reason"] = ll.strip().strip("'\"")
                        need_reason_for_last = False
                        waiting_reason_line = False
                        last_subtest_ref = None
                        continue
                    # empty: keep waiting
                    continue

                # Fallback: take first meaningful non-structural line as reason
                if ll and not (SUITE_HEADER_RE.match(line) or TEST_TITLE_RE.match(line) or RESULT_LINE_RE.match(line) or line.startswith("---") or line.startswith("command_line:")):
                    if last_subtest_ref is not None:
                        last_subtest_ref["reason"] = ll.strip().strip("'\"")
                    need_reason_for_last = False
                    waiting_reason_line = False
                    last_subtest_ref = None
                    continue

                # Structural line arrived: close reason window
                if SUITE_HEADER_RE.match(line) or TEST_TITLE_RE.match(line) or RESULT_LINE_RE.match(line):
                    need_reason_for_last = False
                    waiting_reason_line = False
                    last_subtest_ref = None
                # fall through

            # -------- suite / case headers --------
            m = SUITE_HEADER_RE.match(line)
            if m:
                frag = m.group(1) or ""
                suite, case = extract_suite_and_case(frag)
                if suite:
                    current_suite = suite
                    ensure_suite(current_suite)
                if case:
                    current_case = case
                    ensure_case(current_suite, current_case)
                continue

            # -------- inline "title | RESULT |" rows (common in OOB) --------
            m_inline = INLINE_RESULT_RE.match(line)
            if m_inline:
                # Skip if it's an SBMR banner accidentally matching
                if not line.strip().startswith("SBMR-ACS"):
                    add_direct_result(m_inline.group("title"), m_inline.group("res"))
                    # reason window for non-pass
                    if m_inline.group("res").upper() in ("FAIL", "ABORT", "WARNING", "SKIP"):
                        need_reason_for_last = True
                        waiting_reason_line = False
                    else:
                        need_reason_for_last = False
                        waiting_reason_line = False
                        last_subtest_ref = None
                    continue

            # -------- test title lines (IB/OOB when printed on own line) --------
            if TEST_TITLE_RE.match(line):
                pending_title = line.strip()
                continue

            # -------- result-only lines like "| PASS |" (IB pattern) --------
            r = RESULT_LINE_RE.match(line)
            if r:
                add_result(r.group(1))
                # open a short reason window for non-pass outcomes
                if r.group(1).upper() in ("FAIL", "ABORT", "WARNING", "SKIP"):
                    need_reason_for_last = True
                    waiting_reason_line = False
                else:
                    need_reason_for_last = False
                    waiting_reason_line = False
                    last_subtest_ref = None
                continue

            # ignore other lines

    # prune empty cases (no subtests)
    for suite_name in list(suites.keys()):
        cases = suites[suite_name]["Test_cases"]
        filtered = [c for c in cases if c["subtests"]]
        suites[suite_name]["Test_cases"] = filtered

    # rebuild top-level summary from kept suites (already tallied, but ensure consistency)
    def recompute_overall():
        recomputed = {
            "total_passed": 0,
            "total_failed": 0,
            "total_failed_with_waiver": 0,
            "total_aborted": 0,
            "total_skipped": 0,
            "total_warnings": 0,
            "total_ignored": 0
        }
        for s in suites.values():
            ss = s["test_suite_summary"]
            for k in recomputed:
                recomputed[k] += ss.get(k, 0)
        return recomputed

    overall = recompute_overall()

    # final JSON shape
    output = {
        "test_results": list(suites.values()),
        "suite_summary": overall
    }

    with open(output_file, "w") as jf:
        json.dump(output, jf, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse SBMR log (IB or OOB) into grouped JSON (one Test_suite with multiple Test_case entries)."
    )
    parser.add_argument("input_file", help="SBMR console log file")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()
    main(args.input_file, args.output_file)