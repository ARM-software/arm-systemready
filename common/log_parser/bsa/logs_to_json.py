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
import sys
from collections import defaultdict

# Keep these patterns in one place so the parser can read both clean ACS logs
# and raw simulator/terminal logs without a separate pre-cleaning step.
ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m')
BRACKET_TIMESTAMP_RE = re.compile(r'^\s*\[.*?\]\s?')
SIM_TUBE_PREFIX_RE = re.compile(r'^\s*#\s*\d+\s+ns\s+tube:\s+[^:]+:\s?')
SIM_CONTINUATION_PREFIX_RE = re.compile(r'^\s*#\s?')
SUITE_HEADER_RE = re.compile(r'\*\*\*\s+Running\s+(.+?)\s+tests\s+\*\*\*')
REFERENCED_RULES_MARKER_RE = re.compile(
    r'===\s+(Start|End)\s+tests\s+for\s+rules\s+referenced\s+by\s+([A-Za-z0-9_]+)\s+===',
    re.IGNORECASE
)
RULE_LINE_RE = re.compile(r'^([A-Za-z0-9_]+)\s*:\s*(-|\d+)\s*:\s*(.*)$')
RESULT_RE = re.compile(r'\bResult:\s*(.*)$', re.IGNORECASE)
INTERNAL_TEST_RE = re.compile(r'^Test\s+\d+\s*:\s*.*:\s*\S.*$', re.IGNORECASE)
DIAGNOSTIC_PREFIX_RE = re.compile(
    r'^(?:ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE|FATAL|TEST)\s*:',
    re.IGNORECASE
)
REASON_PREFIX_RE = re.compile(r'^(?:ERROR|WARN(?:ING)?|FATAL|TEST)\s*:\s*\S', re.IGNORECASE)
# INFO, fast-print and direct PAL messages can omit the severity label. Match
# their outcome explanations, not arbitrary UART payload, debug or progress text.
PLAIN_REASON_RE = re.compile(
    r'(?:(?:(?:Failed|Skipped|Passed) at )?checkpoint\s*-\s*(?:0x[\da-f]+|\d+).*'
    r'|(?:Failed|Skipped|Invalid|Unsupported|Mismatch|Timeout)\b.*'
    r'|pal_\w+ is not implemented\.?'
    r'|Please (?:implement|rerun)\b.*'
    r'|(?:or )?conduct (?:an offline|manual) review\b.*'
    r'|This test requires\b.*'
    r'|No .+\b(?:defined|discovered|detected|found|present|available|supported|shared|skipping|reported|implemented)\b.*'
    r'|No (?:Proximity domains in the system|translation support)\b.*'
    r'|And no system wake up timer\b.*'
    r'|ACS could not detect\b.*'
    r'|PCIe Subsystem not discovered\b.*'
    r'|(?:RAS|SRAT)\b.*\bnot found\b.*'
    r'|Pre-requisite rule\b.*\bdid not pass\b.*'
    r'|SMMU_02 not applicable\s*:\s*Stall model is not supported'
    r'|Endpoint to (?:Host|Endpoint) DMA test (?:PASSED|FAILED|SKIPPED)'
    r'|Counter frequency is \d+ (?:MHz|KHz)'
    r'|FEAT_\w+ (?:not supported\b.*|supported; manual verification required\b.*)'
    r'|(?:Received )?Failsafe interrupt\b.*'
    r'|MSC Storage value mismatch\b.*'
    r'|GET_CXL_COMPONENT_INFO\s*:\s*\S.*'
    r'|Rule is validated by\b.*'
    r'|If\b.*\bmanual(?:ly)? (?:validation|review|verify)\b.*'
    r'|For\b.*\bmanually verify\b.*'
    r'|The test must be considered fail\b.*'
    r'|(?:GIC Install Handler Failed|Did not receive UART interrupt)\b.*)',
    re.IGNORECASE
)
FIRMWARE_OUTPUT_RE = re.compile(r'ConvertPages\s*:', re.IGNORECASE)
# These diagnostics can begin before the legacy 49-character display boundary.
# Recognize the complete diagnostic instead of treating a truncated word as one.
HEADER_REASON_RE = re.compile(
    r'\b(?:No\s+ECAMs\s+discovered\b|GET_CXL_COMPONENT_INFO\s*:|Received\s+Failsafe\s+interrupt\b)',
    re.IGNORECASE
)
MAX_SUBTEST_DESCRIPTION_CHARS = 49

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
    if "PAL NOT SUPPORTED" in up:
        formatted_result = "PAL NOT SUPPORTED"
        summary_category = "PAL Not Supported"
        return formatted_result, summary_category

    # Test not implemented
    if "TEST NOT IMPLEMENTED" in up:
        formatted_result = "TEST NOT IMPLEMENTED"
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

    # Warnings
    if up.startswith("STATUS:") or up in ("WARNING", "WARN") or up.startswith("WARNING"):
        formatted_result = "WARNING" if "WARN" in up else "STATUS"
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

def normalize_log_line(raw_line):
    # Raw simulator logs can prefix every ACS line with timestamp/tube text.
    # Remove only that wrapper text and leave the ACS rule/result text intact.
    line = ANSI_ESCAPE_RE.sub('', raw_line)
    line = BRACKET_TIMESTAMP_RE.sub('', line)
    line = SIM_TUBE_PREFIX_RE.sub('', line)
    return SIM_CONTINUATION_PREFIX_RE.sub('', line)

def extract_status_text(status_text):
    # Some logs print a Result and the next marker/header on the same line.
    # Keep only the status part so markers do not leak into Test_result.
    status_text = (status_text or "").strip()
    status_text = re.split(r'\s+(?:===|\*\*\*)', status_text, maxsplit=1)[0]
    return status_text.strip()

def make_test_number(rule_id, test_index):
    return f"{rule_id} : {test_index or '-'}"

def limit_subtest_description(description):
    """Limit a description to 49 characters."""
    return (description or "").strip()[:MAX_SUBTEST_DESCRIPTION_CHARS].rstrip()

def extract_reason_line(line):
    """Select a diagnostic record, preserving its printed spacing and content."""
    firmware = FIRMWARE_OUTPUT_RE.search(line)
    if firmware:
        line = line[:firmware.start()].rstrip()
    # Normalize only for matching; stored reasons retain their internal spacing.
    normalized = " ".join(line.split())
    if (REASON_PREFIX_RE.match(normalized) or INTERNAL_TEST_RE.match(normalized) or
            PLAIN_REASON_RE.fullmatch(normalized)):
        return line
    return None

# A frame is one rule that has started but has not reached its Result/END line.
# Keeping these frames on a stack lets the parser attach each completed child
# rule to the nearest still-open parent rule.
def make_rule_frame(suite, rule_id, test_index, description, parent, current_source):
    test_number = make_test_number(rule_id, test_index)
    if parent:
        child_counts = parent.setdefault("_child_counts", defaultdict(int))
        child_counts[test_number] += 1
        occurrence = child_counts[test_number]
        # If the same rule appears twice under one parent, keep both paths unique
        # without changing the visible sub_Test_Number used by old waivers.
        display_number = test_number if occurrence == 1 else f"{test_number} [{occurrence}]"
        root = parent.get("root") or parent
        level = parent.get("level", 0) + 1
        path = parent.get("path", [parent.get("number", "")]) + [display_number]
    else:
        occurrence = 1
        root = None
        level = 0
        path = [test_number]

    frame = {
        "suite": suite,
        "rule_id": rule_id,
        "index": test_index or "-",
        "description": description,
        "number": test_number,
        "path": path,
        "level": level,
        "parent": parent,
        "root": root,
        "source": current_source,
        "subtests": [],
        "occurrence": occurrence
    }
    if parent is None:
        frame["root"] = frame
    elif len(description.strip()) > MAX_SUBTEST_DESCRIPTION_CHARS:
        header_match = HEADER_REASON_RE.search(description)
        header_text = (description[header_match.start():] if header_match else
                       description.strip()[len(limit_subtest_description(description)):].strip())
        header_reason = extract_reason_line(header_text)
        if header_reason:
            frame["reason_lines"] = [header_reason]
    return frame

def subtest_entry_from_frame(frame, formatted_result):
    # Completed child rules become recursive subtests. sub_Test_Path mirrors the
    # log branch so a partner can compare JSON/HTML directly with the log.
    entry = {
        "sub_Test_Number": frame.get("number", make_test_number(frame.get("rule_id"), frame.get("index"))),
        "sub_Test_Description": limit_subtest_description(
            frame.get("description", "")
        ),
        "sub_test_result": formatted_result,
        "sub_Test_Level": frame.get("level", 1),
        "sub_Test_Path": " / ".join(frame.get("path", [])),
        "reason": list(frame.get("reason_lines", []))
    }
    subtests = frame.get("subtests", [])
    if subtests:
        entry["subtests"] = subtests
    return entry

def testcase_from_frame(frame, formatted_result):
    testcase = {
        "Test_case": frame.get("number", make_test_number(frame.get("rule_id"), frame.get("index"))),
        "Test_case_description": frame.get("description", ""),
        "Test_result": formatted_result,
        "_source": frame.get("source", "unknown"),
        "reason": list(frame.get("reason_lines", []))
    }
    subtests = frame.get("subtests", [])
    if subtests:
        testcase["subtests"] = subtests
    return testcase

def find_frame_from_top(rule_stack, rule_id):
    # END lines only carry the rule id. If the same id appears more than once
    # in nested logs, the nearest open frame is the one that should close.
    for idx in range(len(rule_stack) - 1, -1, -1):
        if rule_stack[idx].get("rule_id") == rule_id:
            return idx
    return None

def remove_marker_frame(marker_stack, frame):
    # If a rule closes before its End marker is seen, drop any stale marker
    # scope that points at that rule so later rules cannot attach to it.
    marker_stack[:] = [marker for marker in marker_stack if marker is not frame]

def complete_rule_frame(frame, formatted_result, summary_category,
                        testcases_per_suite, suite_summaries, total_summary):
    if frame.get("parent") is not None:
        # Nested rules are stored under their parent. Suite totals count only
        # completed top-level rules, matching the old BSA/SBSA behavior.
        parent = frame.get("parent")
        if parent is not None:
            parent.setdefault("subtests", []).append(
                subtest_entry_from_frame(frame, formatted_result)
            )
        return

    testcase = testcase_from_frame(frame, formatted_result)

    tcs = init_summary()
    update_summary_counts(tcs, summary_category, formatted_result)
    testcase["Test_case_summary"] = tcs

    suite = frame.get("suite", "")
    testcases_per_suite[suite].append(testcase)
    update_summary_counts(suite_summaries[suite], summary_category, formatted_result)
    update_summary_counts(total_summary, summary_category, formatted_result)

def iter_subtests(subtests):
    # Flatten a nested subtest tree for matching/merging, without changing the
    # recursive JSON structure that partners see in the final output.
    for subtest in subtests or []:
        yield subtest
        yield from iter_subtests(subtest.get("subtests", []))

def subtest_key(subtest):
    # Use the full nested path when available. The visible rule number is kept
    # as a fallback so old flat logs still merge as before.
    return subtest.get("sub_Test_Path") or subtest.get("sub_Test_Number")

def merge_matching_subtests(existing_subtests, override_subtests):
    # When UEFI and Linux logs contain the same testcase, keep the UEFI tree as
    # the base and overlay Linux results only on matching subtests. Prefer the
    # full path so repeated nested rule numbers do not overwrite each other.
    existing_by_key = {
        subtest_key(st): st
        for st in iter_subtests(existing_subtests)
        if subtest_key(st)
    }
    for override in iter_subtests(override_subtests):
        key = subtest_key(override)
        if key in existing_by_key:
            existing_by_key[key].clear()
            existing_by_key[key].update(override)

def main(input_files, output_file):
    # Per-suite list of testcases
    testcases_per_suite = defaultdict(list)
    # Per-suite summary
    suite_summaries = defaultdict(init_summary)
    # Global summary
    total_summary = init_summary()

    for input_file in input_files:
        # Parsing state is file-local. Completed testcases are accumulated
        # across files, but an unfinished rule/marker/suite must not leak into
        # the next log.
        rule_stack = []
        marker_stack = []
        current_suite = ""
        processing = False

        lower_path = input_file.lower()
        if "/linux" in lower_path or "bsaresultskernel" in lower_path or "/linux_acs" in lower_path:
            current_source = "linux"
        elif "/uefi" in lower_path:
            current_source = "uefi"
        else:
            current_source = "unknown"
        file_encoding = detect_file_encoding(input_file)

        with open(input_file, "r", encoding=file_encoding, errors="ignore") as f:
            lines = f.read().splitlines()

        i = 0
        while i < len(lines):
            raw_line = lines[i]
            i += 1

            line_no_timestamp = normalize_log_line(raw_line)

            # Strip leading spaces before matching. Nesting comes from explicit
            # referenced-rule markers, not indentation.
            line = line_no_timestamp.strip()

            if not line:
                continue

            # Start processing when we see Selected rules / Running tests / START (old format)
            # or "*** Running <suite> tests ***" (new format)
            if not processing and (
                "---------------------- Running tests ------------------------" in line
                or "Selected rules:" in line
                or re.search(r'\bSTART\s+', line)
                or "*** Running " in line
            ):
                processing = True

            if not processing:
                continue

            reason_line = extract_reason_line(line)
            # These are diagnostic records even when their text contains rule
            # or Result-like fields. The producer can emit them for any outcome.
            if INTERNAL_TEST_RE.match(line) or DIAGNOSTIC_PREFIX_RE.match(line):
                if rule_stack and reason_line:
                    rule_stack[-1].setdefault("reason_lines", []).append(reason_line)
                continue

            # ---------------- New log format support ----------------
            # Newer BSA/SBSA logs can nest rule groups:
            #   <PARENT_RULE> : <index> : <description>
            #     === Start tests for rules referenced by <PARENT_RULE> ===
            #     <CHILD_RULE> : <index> : <description>
            #       Result: <status text>
            #     === End tests for rules referenced by <PARENT_RULE> ===
            #   Result: <status text>
            suite_hdr = SUITE_HEADER_RE.search(line)
            if suite_hdr:
                current_suite = suite_hdr.group(1).strip().replace(" ", "_")

            referenced_rules_marker = REFERENCED_RULES_MARKER_RE.search(line)
            if referenced_rules_marker:
                marker_action = referenced_rules_marker.group(1).lower()
                marker_rule_id = referenced_rules_marker.group(2).strip()
                if marker_action == "start":
                    # The marker names the parent rule. Children that follow
                    # should be attached under this open parent frame.
                    frame_idx = find_frame_from_top(rule_stack, marker_rule_id)
                    if frame_idx is not None:
                        marker_stack.append(rule_stack[frame_idx])
                else:
                    # End marker closes the current parent scope, but does not
                    # complete the parent rule. The following Result line does.
                    for marker_idx in range(len(marker_stack) - 1, -1, -1):
                        if marker_stack[marker_idx].get("rule_id") == marker_rule_id:
                            marker_stack.pop(marker_idx)
                            break

            # RULE line. Start/End referenced-by markers provide explicit parent
            # scope for nested logs.
            rule_line = RULE_LINE_RE.search(line)
            if rule_line:
                rule_id = rule_line.group(1).strip()
                test_index = (rule_line.group(2) or "").strip() or "-"
                desc = (rule_line.group(3) or "").strip()
                suite = current_suite or ""
                inline_result = RESULT_RE.search(desc)
                status_text = ""
                if inline_result:
                    # Compact logs may print "RULE : idx : desc Result: PASS".
                    # Split it so Result is not stored as part of description.
                    status_text = extract_status_text(inline_result.group(1))
                    desc = desc[:inline_result.start()].strip()

                parent = marker_stack[-1] if marker_stack else None
                if parent is None and rule_stack:
                    # A new top-level rule should only appear after the previous
                    # top-level result. If a malformed log leaves frames open,
                    # clear them instead of guessing a parent from whitespace.
                    rule_stack.clear()
                    marker_stack.clear()

                frame = make_rule_frame(
                    suite, rule_id, test_index, desc, parent, current_source
                )
                if inline_result:
                    formatted_result, summary_category = classify_status(status_text)
                    complete_rule_frame(
                        frame,
                        formatted_result,
                        summary_category,
                        testcases_per_suite,
                        suite_summaries,
                        total_summary
                    )
                else:
                    rule_stack.append(frame)
                continue

            # In the new log format, Result closes the most recently opened rule.
            # That rule is either emitted as a testcase or attached to its parent.
            result_match = RESULT_RE.search(line)
            if result_match:
                status_text = extract_status_text(result_match.group(1))
                if not rule_stack:
                    continue

                frame = rule_stack.pop()
                # A diagnostic and its final Result can share a physical line.
                joined_reason = extract_reason_line(line[:result_match.start()].strip())
                if joined_reason:
                    frame.setdefault("reason_lines", []).append(joined_reason)
                remove_marker_frame(marker_stack, frame)
                formatted_result, summary_category = classify_status(status_text)
                complete_rule_frame(
                    frame,
                    formatted_result,
                    summary_category,
                    testcases_per_suite,
                    suite_summaries,
                    total_summary
                )
                continue
            # -------------- End new log format support --------------

            #   START <suite_or_dash> <RULE_ID> <index_or_dash> : <description...>
            # Old-format START/END logs use the same stack. Flat old logs stay
            # flat unless explicit referenced-rule markers provide parent scope.
            start_match = re.search(
                r'\bSTART\s+([^\s:]+)\s+([A-Za-z0-9_]+)\s+([^\s:]+)\s*:\s*(.*)$',
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

                parent = marker_stack[-1] if marker_stack else None
                if parent is None and rule_stack:
                    rule_stack.clear()
                    marker_stack.clear()

                rule_stack.append(
                    make_rule_frame(current_suite, rule_id, test_index, desc, parent, current_source)
                )
                continue

            # END line:
            #   END <RULE_ID> <status text...>
            end_match = re.search(r'\bEND\s+([A-Za-z0-9_]+)\s+(.*)$', line)
            if end_match:
                rule_id = end_match.group(1).strip()
                status_text = extract_status_text(end_match.group(2))

                formatted_result, summary_category = classify_status(status_text)

                # END names the rule being closed. Search from the top of the
                # stack so repeated rule IDs close the nearest matching instance.
                frame_idx = find_frame_from_top(rule_stack, rule_id)
                if frame_idx is None:
                    continue

                frame = rule_stack.pop(frame_idx)
                remove_marker_frame(marker_stack, frame)
                complete_rule_frame(
                    frame,
                    formatted_result,
                    summary_category,
                    testcases_per_suite,
                    suite_summaries,
                    total_summary
                )
                continue

            # Accept known plain diagnostic forms only inside their owning rule.
            # Result status does not determine whether a reason is retained.
            if rule_stack and reason_line and not suite_hdr and not referenced_rules_marker:
                rule_stack[-1].setdefault("reason_lines", []).append(reason_line)
            continue

    # Post-process UEFI/Linux duplicates per testcase
    processed_testcases = defaultdict(list)
    for suite_name, tcs in testcases_per_suite.items():
        seen = defaultdict(list)
        for tc in tcs:
            key = tc.get("Test_case")
            src = tc.pop("_source", "unknown")

            # Only merge duplicates when they are the known UEFI/Linux pair.
            # Other same-key entries are independent runs and must stay visible.
            existing = None
            for candidate in seen.get(key, []):
                if {candidate["source"], src} == {"uefi", "linux"}:
                    existing = candidate
                    break

            if existing is None:
                seen[key].append({"source": src, "index": len(processed_testcases[suite_name])})
                processed_testcases[suite_name].append(tc)
                continue

            # Keep UEFI as the base testcase; only override matching fields from Linux.
            existing_tc = processed_testcases[suite_name][existing["index"]]
            existing_src = existing["source"]

            # Ensure UEFI testcase is the base.
            if src == "uefi" and existing_src != "uefi":
                linux_tc = existing_tc
                existing_tc = tc
                processed_testcases[suite_name][existing["index"]] = existing_tc
                existing["source"] = src
            else:
                linux_tc = tc if src == "linux" else None

            if linux_tc:
                # For B_PER_08, keep UEFI testcase result. For other duplicate
                # testcases, Linux has the final testcase-level result.
                if key != "B_PER_08 : -":
                    existing_tc["Test_result"] = linux_tc.get("Test_result")
                    existing_tc["Test_case_summary"] = linux_tc.get("Test_case_summary")
                    # The reason must describe the same execution as the result,
                    # including when an older Linux log has no check details.
                    existing_tc["reason"] = linux_tc.get("reason", [])

                # Override only matching subtests. Linux-only subtests are not
                # appended because the UEFI tree is the report structure.
                merge_matching_subtests(
                    existing_tc.get("subtests", []),
                    linux_tc.get("subtests", []) or []
                )
            continue

    testcases_per_suite = processed_testcases

    # Recompute summaries from processed testcases
    suite_summaries = defaultdict(init_summary)
    total_summary = init_summary()
    for suite_name, tcs in testcases_per_suite.items():
        for tc in tcs:
            formatted_result, summary_category = classify_status(tc.get("Test_result"))
            update_summary_counts(suite_summaries[suite_name], summary_category, formatted_result)
            update_summary_counts(total_summary, summary_category, formatted_result)

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

    acs_run_true = total_summary.get("Total Rules Run", 0) > 0
    if not acs_run_true:
        sys.exit(1)

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
