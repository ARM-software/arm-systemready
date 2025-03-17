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

# Define color codes
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[32m"
RESET = "\033[0m"

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

# DT SRS scope table
DT_SRS_SCOPE_TABLE = [
    ("SCT", "M"),
    ("FWTS", "M"),
    ("Capsule Update", "M"),
    ("DT_VALIDATE", "M"),
    ("READ_WRITE_CHECK_BLK_DEVICES", "M"),
    ("ETHTOOL_TEST", "M"),
    ("BSA", "R"),
    ("BBSR-SCT", "R"),
    ("BBSR-FWTS", "R"),
    ("DT_KSELFTEST", "R"),
    ("PSCI", "R"),
]

# SR SRS scope table
SR_SRS_SCOPE_TABLE = [
    ("SCT", "M"),
    ("FWTS", "M"),
    ("BSA", "M"),
    ("BBSR-SCT", "R"),
    ("BBSR-FWTS", "R"),
    ("SBSA", "R")
]

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
            global DT_SRS_SCOPE_TABLE
            DT_SRS_SCOPE_TABLE += [(f"OS_{base_name_no_ext}","M")]
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

    # Step 3) Compute *per-suite* and overall compliance
    # Decide mandatory set
    if DT_OR_SR_MODE == "DT":
        mandatory_suites = set(DT_SRS_SCOPE_TABLE)
    else:
        mandatory_suites = set(SR_SRS_SCOPE_TABLE)
        # If SBSA is present, treat it as mandatory
        if "SBSA" in suite_fail_data:
            mandatory_suites = {("SBSA", "M") if suite[0] == "SBSA" else suite for suite in mandatory_suites}

    overall_comp = "Compliant"
    # Keep track of missing_suites and non_waived_suites for parentheses
    missing_list = []
    non_waived_list = []

    for suite_name, requirement in mandatory_suites:
        if suite_name not in suite_fail_data:
            label = f"Suite_Name: {suite_name}_compliance"
            acs_results_summary[label] = "Not Compliant: not run"
            if requirement == "M":
                print(f"{RED}Suite: {suite_name}: {acs_results_summary[label]}{RESET}")
                overall_comp = "Not Compliant"
                missing_list.append(suite_name)
            else:
                print(f"Suite: {suite_name}: {acs_results_summary[label]}")
        else:
            fail_info = suite_fail_data.get(suite_name)
            f = fail_info.get("Failed", 0)
            fw = fail_info.get("Failed_with_Waiver", 0)
            label = f"Suite_Name: {suite_key}_compliance"
            if (f + fw) == 0:
                acs_results_summary[label] = "Compliant"
                print(f"Suite: {suite_name}: {acs_results_summary[label]}")
            elif f == fw:
                acs_results_summary[label] = "Compliant with waivers"
                print(f"Suite: {suite_name}: {acs_results_summary[label]}")
                if requirement == "M" and overall_comp != "Not Compliant":
                    overall_comp="Compliant with waivers"
            else:
                acs_results_summary[label] = f"Not Compliant: Failed {f}"
                if requirement == "M":
                    print(f"{RED}Suite: {suite_name}: {acs_results_summary[label]}{RESET}")
                    overall_comp="Not Compliant"
                    non_waived_list.append(suite_name)
                else:
                    print(f"Suite: {suite_name}: {acs_results_summary[label]}")

    #Ensure suite-wise compliance lines for *all* discovered suites (including recommended)
    for skey, info in suite_fail_data.items():
        # If no label set, default to "Compliant" if fails=0, else "Not compliant", etc.
        label = f"Suite_Name: {skey}_compliance"
        if label not in acs_results_summary:
            f = info["Failed"]
            fw = info["Failed_with_Waiver"]
            if (f + fw) == 0:
                acs_results_summary[label] = "Compliant"
            elif f == fw:
                acs_results_summary[label] = "Compliant with waivers"
            else:
                acs_results_summary[label] = "Not compliant"

    # Step 4) Overall compliance using mandatory logic
    #overall_comp = determine_overall_compliance(suite_fail_data)
    # Add reason in parentheses if we have missing or non-waived
    if overall_comp == "Not Compliant":
        reason_parts = []
        if missing_list:
            reason_parts.append(f"missing suite(s): {', '.join(missing_list)}")
        if non_waived_list:
            reason_parts.append(f"non-waived fails in suite(s): {', '.join(non_waived_list)}")
        if reason_parts:
            overall_comp += f" ({'; '.join(reason_parts)})"
    elif overall_comp == "Compliant with waivers":
        pass

    acs_results_summary["Overall Compliance Result"] = overall_comp
    if overall_comp.startswith("Not Compliant"):
        print(f"\n{RED}SRS 3.0 Compliance result: {overall_comp}{RESET}\n")
    elif overall_comp.startswith("Compliant with waivers"):
        print(f"\n{YELLOW}SRS 3.0 Compliance result: {overall_comp}{RESET}\n")
    else:
        print(f"\n{GREEN}SRS 3.0 Compliance result: {overall_comp}{RESET}\n")

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
