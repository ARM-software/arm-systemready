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
import os

################################################################################
# 1. Determine if we're in Device Tree (DT) mode or SR mode by checking yocto flag
################################################################################
YOCTO_FLAG_PATH = "/mnt/yocto_image.flag"
if os.path.isfile(YOCTO_FLAG_PATH):
    DT_OR_SR_MODE = "DT"
else:
    DT_OR_SR_MODE = "SR"

################################################################################
# 2. Define Mandatory Suites based on your table
#    (Recommended suites are simply "not in this list"; they won't affect compliance.)
################################################################################

# From your table for Device Tree (DT):
#   BSA (R), SCT (M), FWTS (M), Capsule Update (M), BBSR SCT (R), BBSR FWTS (R),
#   DT Validate (M), block device (M), Ethtool (M), DT kernel kselftest (R)
MANDATORY_SUITE_KEYS_DT = {
    "SCT",
    "FWTS",
    "Capsule Update",
    "DT_VALIDATE",
    "READ_WRITE_CHECK_BLK_DEVICES",
    "ETHTOOL_TEST",
}

# From your table for SR:
#   BSA (M), SBSA (M*) if present, SCT (M), FWTS (M), SCRT (M), BBSR SCT (R), BBSR FWTS (R)
MANDATORY_SUITE_KEYS_SR = {
    "BSA",
    "SBSA",
    "SCT",
    "FWTS",
    "SCRT",  # Only if your code actually uses "SCRT" as a key
    # SBSA => mandatory only if present
}

def reformat_json(json_file_path):
    """
    Re‐format (pretty‐print) the file to confirm it's valid JSON.
    """
    try:
        with open(json_file_path, 'r') as jf:
            data = json.load(jf)
        with open(json_file_path, 'w') as jf:
            json.dump(data, jf, indent=4)
    except FileNotFoundError:
        raise
    except json.JSONDecodeError:
        print(f"Warning: {json_file_path} is invalid JSON. Skipping.")

def count_fails_in_json(data):
    """
    Inspect JSON data and count how many tests are 'FAILED' vs 'FAILED_WITH_WAIVER'.
    Returns (failed, failed_with_waiver).

    Expects a structure with top-level 'test_results' => [ {subtests: [...]} ]
    or a top-level list for subtests. If not recognized, returns (0,0).
    """
    total_failed = 0
    total_failed_with_waiver = 0

    if isinstance(data, dict) and "test_results" in data:
        test_results = data["test_results"]
    elif isinstance(data, list):
        test_results = data
    else:
        return (0, 0)  # no recognized substructure

    if not isinstance(test_results, list):
        return (0, 0)

    for suite_entry in test_results:
        subtests = suite_entry.get("subtests", [])
        for sub in subtests:
            res = sub.get("sub_test_result")
            if isinstance(res, dict):
                # e.g. { "FAILED": 1, "FAILED_WITH_WAIVER": 1, ... }
                f = res.get("FAILED", 0)
                fw = res.get("FAILED_WITH_WAIVER", 0)
                total_failed += (f + fw)
                total_failed_with_waiver += fw
            elif isinstance(res, str):
                # e.g. "FAILED (WITH WAIVER)"
                if "FAILED" in res.upper() or "FAILURE" in res.upper():
                    total_failed += 1
                    if "(WITH WAIVER)" in res.upper():
                        total_failed_with_waiver += 1

    return (total_failed, total_failed_with_waiver)

################################################################################
# function for *single* suite compliance
################################################################################
def determine_suite_compliance_alone(fails, fails_waived):
    """
    Decide compliance for ONE suite, ignoring whether other mandatory suites exist.

    If no fails => "Compliant"
    If all fails are waived => "Compliant with Waivers"
    Otherwise => "Not compliant"
    """
    if (fails + fails_waived) == 0:
        return "Compliant"
    elif fails == fails_waived:
        return "Compliant with Waivers"
    else:
        return "Not compliant"

################################################################################
# "determine_overall_compliance" that includes REASONS
################################################################################
def determine_overall_compliance(suite_fail_data):
    """
    Returns a string, possibly with reasons, e.g.:
       "Compliant"
       "Compliant with Waivers (waived fail(s) in suite(s): X, Y)"
       "Not compliant (missing suite(s): X, Y; non-waived fails in suite(s): A, B)"
    """

    # Decide mandatory set
    if DT_OR_SR_MODE == "DT":
        mandatory_suites = set(MANDATORY_SUITE_KEYS_DT)
    else:
        mandatory_suites = set(MANDATORY_SUITE_KEYS_SR)
        # If SBSA is present, treat it as mandatory
        if "SBSA" in suite_fail_data:
            mandatory_suites.add("SBSA")

    # We'll track missing mandatory suites, non-waived fails, etc.
    missing_suites = []
    non_waived_fail_suites = []
    waived_fail_suites = []

    # 1) Check for missing mandatory suites
    for m_suite in mandatory_suites:
        if m_suite not in suite_fail_data:
            missing_suites.append(m_suite)

    # 2) Summarize fails in mandatory suites only
    total_mandatory_fails = 0
    for suite_key, info in suite_fail_data.items():
        if suite_key not in mandatory_suites:
            continue
        f = info.get("Failed", 0)
        fw = info.get("Failed_with_Waiver", 0)
        total_mandatory_fails += (f + fw)

        if (f + fw) > 0:
            if f == fw:
                # all fails are waived
                waived_fail_suites.append(suite_key)
            else:
                # at least one fail is not waived
                non_waived_fail_suites.append(suite_key)

    ############################################################################
    # Build up a reason string
    ############################################################################
    # missing_suites => cause immediate "Not compliant"
    # non_waived_fail_suites => also "Not compliant"
    # if none missing, none non-waived => either "Compliant" or "Compliant with Waivers"

    # If we have missing mandatory suites
    if missing_suites:
        # Possibly also have some non-waived fails
        if non_waived_fail_suites:
            return (f"Not compliant (missing suite(s): {', '.join(missing_suites)}; "
                    f"non-waived fails in suite(s): {', '.join(non_waived_fail_suites)})")
        else:
            return (f"Not compliant (missing suite(s): {', '.join(missing_suites)})")

    # If no suites are missing, do we have any total fails?
    if total_mandatory_fails == 0:
        return "Compliant"

    # Are there unwaived fails?
    if non_waived_fail_suites:
        return (f"Not compliant (non-waived fails in suite(s): "
                f"{', '.join(non_waived_fail_suites)})")

    # If we get here => all fails in mandatory suites are waived
    # => "Compliant with Waivers" + note which suites
    if waived_fail_suites:
        return (f"Compliant with Waivers (waived fail(s) in suite(s): "
                f"{', '.join(waived_fail_suites)})")

    # Edge case fallback
    return "Compliant"

def merge_json_files(json_files, output_file):
    merged_results = {}
    suite_fail_data = {}

    # We'll store the "acs_info" data in acs_info_data (if found)
    acs_info_path = None
    new_json_files = []
    for fpath in json_files:
        if "acs_info.json" in os.path.basename(fpath).lower():
            acs_info_path = fpath
        else:
            new_json_files.append(fpath)

    acs_info_data = None
    acs_results_summary = None

    if acs_info_path and os.path.isfile(acs_info_path):
        try:
            reformat_json(acs_info_path)
            with open(acs_info_path, 'r') as f:
                acs_info_data = json.load(f)
            merged_results["Suite_Name: acs_info"] = acs_info_data

            if isinstance(acs_info_data, dict):
                acs_results_summary = acs_info_data.get("ACS Results Summary")
                if not isinstance(acs_results_summary, dict):
                    acs_results_summary = {}
                    acs_info_data["ACS Results Summary"] = acs_results_summary
        except Exception as e:
            print(f"Warning: Could not load acs_info.json: {e}")

    if not acs_results_summary:
        acs_results_summary = {}
        merged_results["Suite_Name: acs_info"] = {
            "ACS Results Summary": acs_results_summary
        }

    # Step 2) Process each suite JSON
    for json_path in new_json_files:
        if not os.path.isfile(json_path):
            print(f"Warning: {json_path} not found. Skipping.")
            continue

        try:
            reformat_json(json_path)
        except json.JSONDecodeError:
            continue

        try:
            with open(json_path, 'r') as jf:
                data = json.load(jf)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Warning: {json_path} is invalid JSON. Skipping.")
            continue

        # Identify suite name from filename
        fn = os.path.basename(json_path).upper()
        if "BSA" in fn and "SBSA" not in fn:
            section_name = "Suite_Name: BSA"
            suite_key    = "BSA"
        elif "SBSA" in fn:
            section_name = "Suite_Name: SBSA"
            suite_key    = "SBSA"
        elif "BBSR" in fn and "FWTS" in fn:
            section_name = "Suite_Name: BBSR-FWTS"
            suite_key    = "BBSR-FWTS"
        elif "FWTS" in fn:
            section_name = "Suite_Name: FWTS"
            suite_key    = "FWTS"
        elif "BBSR" in fn and "SCT" in fn:
            section_name = "Suite_Name: BBSR-SCT"
            suite_key    = "BBSR-SCT"
        elif "SCT" in fn:
            section_name = "Suite_Name: SCT"
            suite_key    = "SCT"
        elif "CAPSULE_UPDATE" in fn:
            section_name = "Suite_Name: CAPSULE_UPDATE"
            suite_key    = "Capsule Update"
        elif "DT_KSELFTEST" in fn:
            section_name = "Suite_Name: DT Kselftest"
            suite_key    = "DT_KSELFTEST"
        elif "DT_VALIDATE" in fn:
            section_name = "Suite_Name: DT Validate"
            suite_key    = "DT_VALIDATE"
        elif os.path.basename(json_path).lower() == "ethtool_test.json":
            section_name = "Suite_Name: Ethtool Test"
            suite_key    = "ETHTOOL_TEST"
        elif "ethtool_test" in fn.lower():
            base_name_no_ext = os.path.splitext(os.path.basename(json_path))[0]
            section_name = f"Suite_Name: OS Tests - {base_name_no_ext}"
            suite_key    = f"OS_{base_name_no_ext}"
        elif "READ_WRITE_CHECK_BLK_DEVICES" in fn:
            section_name = "Suite_Name: Read Write Check Block Devices"
            suite_key    = "READ_WRITE_CHECK_BLK_DEVICES"
        elif "PSCI" in fn:
            section_name = "Suite_Name: PSCI"
            suite_key    = "PSCI"
        else:
            section_name = "Suite_Name: Unknown"
            suite_key    = "Unknown"

        merged_results[section_name] = data

        f, fw = count_fails_in_json(data)
        suite_fail_data[suite_key] = {
            "Failed": f,
            "Failed_with_Waiver": fw
        }

    # Step 3) Compute *per-suite* compliance ignoring other suites' presence
    for suite_key, fail_info in suite_fail_data.items():
        f = fail_info["Failed"]
        fw = fail_info["Failed_with_Waiver"]
        single_suite_comp = determine_suite_compliance_alone(f, fw)
        label = f"Suite_Name: {suite_key}_compliance"
        acs_results_summary[label] = single_suite_comp

    # Step 4) Overall compliance using mandatory logic
    overall_comp = determine_overall_compliance(suite_fail_data)
    acs_results_summary["Overall Compliance Result"] = overall_comp

    if "Overall Compliance Results" in acs_results_summary:
        del acs_results_summary["Overall Compliance Results"]

    with open(output_file, 'w') as outj:
        json.dump(merged_results, outj, indent=4)

def main():
    parser = argparse.ArgumentParser(
        description="Merge suite JSONs + acs_info.json, store compliance lines inside 'ACS Results Summary'"
    )
    parser.add_argument("output_file", help="Output merged JSON file")
    parser.add_argument("json_files", nargs='+',
                        help="List of JSON files to merge (including acs_info.json if present)")
    args = parser.parse_args()

    merge_json_files(args.json_files, args.output_file)

if __name__ == "__main__":
    main()
