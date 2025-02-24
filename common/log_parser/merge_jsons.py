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

    # data might be a dict with "test_results" or a list
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

def determine_overall_compliance(suite_fail_data):
    """
    suite_fail_data: { "BSA": {"Failed": x, "Failed_with_Waiver": y}, ... }
    Returns: "Compliant", "Compliant with Waivers", or "Not compliant".
    """
    all_failed_zero = True
    compliant_with_waivers = True

    for suite_key, info in suite_fail_data.items():
        f = info.get("Failed", 0)
        fw = info.get("Failed_with_Waiver", 0)
        if f != fw:
            compliant_with_waivers = False
        if (f + fw) != 0:
            all_failed_zero = False

    if all_failed_zero:
        return "Compliant"
    elif compliant_with_waivers:
        # check if there's at least 1 waived test
        any_waivers = any(v.get("Failed_with_Waiver", 0) > 0 for v in suite_fail_data.values())
        if any_waivers:
            return "Compliant with Waivers"
        else:
            return "Compliant"
    else:
        return "Not compliant"


def merge_json_files(json_files, output_file):
    """
    Behavior:
      1) If acs_info.json is in the list, load it first => store as "Suite_Name: acs_info".
         We'll also retrieve its "ACS Results Summary" dict so we can put the final suite
         compliance lines in there, and replace "Overall Compliance Results" with the actual
         overall compliance.
      2) Merge each other suite => store as "Suite_Name: BSA", "Suite_Name: FWTS", etc.
      3) For each suite => compute "Suite_Name: BSA_compliance" etc.
      4) Insert those compliance lines into the "ACS Results Summary" dict (instead of top-level).
      5) Also set "Overall Compliance Result" in that "ACS Results Summary" dict.
      6) Write final merged JSON to 'output_file'.
    """

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

    # Step 1) If we have acs_info.json, load it & store under "Suite_Name: acs_info".
    # Also keep a handle to acs_results_summary dict if present
    acs_info_data = None
    acs_results_summary = None

    if acs_info_path and os.path.isfile(acs_info_path):
        try:
            reformat_json(acs_info_path)
            with open(acs_info_path, 'r') as f:
                acs_info_data = json.load(f)

            # Put it directly in merged_results
            merged_results["Suite_Name: acs_info"] = acs_info_data

            # Attempt to find "ACS Results Summary" dict inside
            if isinstance(acs_info_data, dict):
                acs_results_summary = acs_info_data.get("ACS Results Summary")
                # if it's not a dict, or missing, we'll create a new one
                if not isinstance(acs_results_summary, dict):
                    acs_results_summary = {}
                    acs_info_data["ACS Results Summary"] = acs_results_summary
        except Exception as e:
            print(f"Warning: Could not load acs_info.json: {e}")

    # If we STILL don't have a dict for acs_results_summary, create one anyway
    if not acs_results_summary:
        acs_results_summary = {}
        # We might store it top-level if no acs_info_data at all
        # but let's just do "Suite_Name: acs_info" => { "ACS Results Summary": {} }
        merged_results["Suite_Name: acs_info"] = {
            "ACS Results Summary": acs_results_summary
        }

    # Step 2) Process each suite
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
        elif "BBSR-FWTS" in fn:
            section_name = "Suite_Name: BBSR-FWTS"
            suite_key    = "BBSR-FWTS"
        elif "BBSR-SCT" in fn:
            section_name = "Suite_Name: BBSR-SCT"
            suite_key    = "BBSR-SCT"
        elif "FWTS" in fn:
            section_name = "Suite_Name: FWTS"
            suite_key    = "FWTS"
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
        elif "ETHTOOL_TEST" in fn:
            section_name = "Suite_Name: Ethtool Test"
            suite_key    = "ETHTOOL_TEST"
        elif "READ_WRITE_CHECK_BLK_DEVICES" in fn:
            section_name = "Suite_Name: Read Write Check Block Devices"
            suite_key    = "READ_WRITE_CHECK_BLK_DEVICES"
        else:
            section_name = "Suite_Name: Unknown"
            suite_key    = "Unknown"

        # Merge data
        merged_results[section_name] = data

        # Count fails => store suite-level fail data
        f, fw = count_fails_in_json(data)
        suite_fail_data[suite_key] = {
            "Failed": f,
            "Failed_with_Waiver": fw
        }

    # Step 3) Compute per-suite compliance & store in acs_results_summary
    # Instead of separate "Suite_Name: BSA_compliance" keys, we'll store them inside "ACS Results Summary"
    # as requested. e.g. "Suite_Name: BSA_compliance": "Compliant with Waivers"
    for suite_key, fail_info in suite_fail_data.items():
        single_dict = {suite_key: fail_info}
        compliance_val = determine_overall_compliance(single_dict)
        label = f"Suite_Name: {suite_key}_compliance"
        acs_results_summary[label] = compliance_val

    # Step 4) Overall compliance across all suites
    overall_comp = determine_overall_compliance(suite_fail_data)

    # Now we REPLACE any existing "Overall Compliance Results" in the acs_results_summary
    # with our new final "Overall Compliance Result"
    # Also, user wants the field name "Overall Compliance Result".
    acs_results_summary["Overall Compliance Result"] = overall_comp

    # If original had "Overall Compliance Results" with "Unknown", we can remove it or rename:
    if "Overall Compliance Results" in acs_results_summary:
        del acs_results_summary["Overall Compliance Results"]

    # Write final
    with open(output_file, 'w') as outj:
        json.dump(merged_results, outj, indent=4)


def main():
    parser = argparse.ArgumentParser(
        description="Merge suite JSONs + acs_info.json, store compliance lines inside 'ACS Results Summary' of acs_info.json"
    )
    parser.add_argument("output_file", help="Output merged JSON file")
    parser.add_argument("json_files", nargs='+', help="List of JSON files to merge (including acs_info.json if present)")
    args = parser.parse_args()

    merge_json_files(args.json_files, args.output_file)

if __name__ == "__main__":
    main()
