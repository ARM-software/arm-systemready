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
from collections import OrderedDict
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
    ("BBSR-TPM", "R"),
    ("BBSR-FWTS", "R"),
    ("DT_KSELFTEST", "R"),
    ("PSCI", "R"),
    ("POST_SCRIPT", "R"),
    ("OS_TEST", "M")
]

# SR SRS scope table
SR_SRS_SCOPE_TABLE = [
    ("SCT", "M"),
    ("FWTS", "M"),
    ("BSA", "M"),
    ("BBSR-SCT", "R"),
    ("BBSR-FWTS", "R"),
    ("BBSR-TPM", "R"),
    ("SBSA", "R")
]

if DT_OR_SR_MODE == "DT":
    _REQUIREMENT_MAP = {name: req for name, req in DT_SRS_SCOPE_TABLE}
else:
    _REQUIREMENT_MAP = {name: req for name, req in SR_SRS_SCOPE_TABLE}

def compliance_label(suite_name: str) -> str:
    req = _REQUIREMENT_MAP.get(suite_name, "R")
    tag = "Mandatory" if req == "M" else "Recommended"
    # Match the console ordering: “Suite: <tag>  : <suite> …”
    return f"Suite_Name: {tag}  : {suite_name}_compliance"


def reformat_json(json_file_path):
    """
    Re-format (pretty-print) the file to confirm it's valid JSON.
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

    *** Added a check so that if no subtests are found at all, we treat it as 1 fail. ***
    """
    total_failed = 0
    total_failed_with_waiver = 0
    any_subtests_found = False

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
        if subtests:
            any_subtests_found = True
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
                if "FAILED" in res.upper() or "FAILURE" in res.upper() or "FAIL" in res.upper():
                    total_failed += 1
                    if "(WITH WAIVER)" in res.upper():
                        total_failed_with_waiver += 1

    # If we found zero subtests across the entire suite => treat that as a fail
    if not any_subtests_found:
        total_failed += 1
    return (total_failed, total_failed_with_waiver)

################################################################################
# We will load the test_categoryDT.json data here, so we can enrich the
#        merged JSON with "Waivable", "SRS scope", and
#        "Main Readiness Grouping" fields for each test suite.
################################################################################

TEST_CATEGORY_DT_PATH = "/usr/bin/log_parser/test_categoryDT.json"

try:
    with open(TEST_CATEGORY_DT_PATH, "r") as catf:
        test_category_dt_data = json.load(catf)
except Exception:
    test_category_dt_data = {}

def build_testcategory_dict(category_data):
    """
    Build a helper dictionary:
      result[suite_name_lower][test_suite_name_lower] -> row dictionary
    so we can easily retrieve waivable / scope / readiness grouping etc.
    """
    result = {}
    if not isinstance(category_data, dict):
        return result

    for cat_id, rows in category_data.items():
        if isinstance(rows, list):
            for row in rows:
                suite_str = row.get("Suite", "").strip()
                testsuite_str = row.get("Test Suite", "").strip()
                if not suite_str or not testsuite_str:
                    continue
                # Convert to lowercase for easy matching
                s_lower = suite_str.lower()
                ts_lower = testsuite_str.lower()
                if s_lower not in result:
                    result[s_lower] = {}
                result[s_lower][ts_lower] = row
    return result

test_cat_dict = build_testcategory_dict(test_category_dt_data)

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

    os_logs_found = 0
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
        elif "BBSR" in fn and "TPM" in fn:
            section_name = "Suite_Name: BBSR-TPM"
            suite_key    = "BBSR-TPM"    
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
            _REQUIREMENT_MAP[f"OS_{base_name_no_ext}"] = "M"
            os_logs_found += 1
            if os_logs_found == 3:
                DT_SRS_SCOPE_TABLE.remove(("OS_TEST","M"))
        elif "READ_WRITE_CHECK_BLK_DEVICES" in fn:
            section_name = "Suite_Name: Read Write Check Block Devices"
            suite_key    = "READ_WRITE_CHECK_BLK_DEVICES"
        elif "PSCI" in fn:
            section_name = "Suite_Name: PSCI"
            suite_key    = "PSCI"

        elif "POST_SCRIPT" in fn:
            section_name = "Suite_Name: POST_SCRIPT"
            suite_key    = "POST_SCRIPT"

        else:
            section_name = "Suite_Name: Unknown"
            suite_key    = "Unknown"

        merged_results[section_name] = data

        # If 'data' is a dict with 'test_results' list, unify it
        if (isinstance(data, dict)
            and "test_results" in data
            and isinstance(data["test_results"], list)
        ):
            data_list = data["test_results"]
        else:
            data_list = data


        ########################################################################
        # Enrich each test_suite dict with matching fields from test_cat_dict
        ########################################################################
        # suite_key is e.g. "BSA", so we'll look up suite_key.lower() in test_cat_dict
        # data might be a list of test_suite dicts (like BSA suite).
        # If there's a match on "Test_suite" => "Test Suite", copy fields.
        # Determine lookup suite key for Standalone-style sub-suites
        lookup_suite_key = suite_key.lower()
        standalone_aliases = {
            "dt_kselftest", "dt_validate", "ethtool_test",
            "read_write_check_blk_devices", "psci", "capsule update"
        }
        if lookup_suite_key in standalone_aliases or lookup_suite_key.startswith("os_"):
            lookup_suite_key = "standalone"

        if lookup_suite_key in test_cat_dict:
            # Now use 'data_list' instead of 'data'
            if isinstance(data_list, list):
                for ts_dict in data_list:
                    if not isinstance(ts_dict, dict):
                        continue

                    ts_name_merged = (ts_dict.get("Test_suite") or ts_dict.get("Test_suite_name") or "").strip().lower()
                    if ts_name_merged in test_cat_dict[lookup_suite_key]:
                        row_vals = test_cat_dict[lookup_suite_key][ts_name_merged]
                        if "Waivable" in row_vals:
                            ts_dict["Waivable"] = row_vals["Waivable"]
                        if "SRS scope" in row_vals:
                            ts_dict["SRS scope"] = row_vals["SRS scope"]
                        if "Main Readiness Grouping" in row_vals:
                            ts_dict["Main Readiness Grouping"] = row_vals["Main Readiness Grouping"]

                        desired_order = [
                            "Test_suite",
                            "Test_suite_name",
                            "Test_suite_Description",
                            "Test_suite_description",
                            "Waivable",
                            "SRS scope",
                            "Main Readiness Grouping",
                            "Sub_test_suite",
                            "Test_case",
                            "Test_case_description",
                            "Test Entry Point GUID",
                            "Returned Status Code",
                            "test_result",
                            "reason",
                            "subtests",
                            "test_case_summary"
                        ]
                        temp = {}
                        for key in desired_order:
                            if key in ts_dict:
                                temp[key] = ts_dict[key]
                        for key, val in ts_dict.items():
                            if key not in temp:
                                temp[key] = val
                        ts_dict.clear()
                        ts_dict.update(temp)

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

    if acs_info_data and isinstance(acs_info_data, dict):
        acs_results_summary = acs_info_data.get("ACS Results Summary", {})
    else:
        acs_results_summary = merged_results["Suite_Name: acs_info"].get("ACS Results Summary", {})

    for suite_name, requirement in mandatory_suites:
        if suite_name not in suite_fail_data:
            label = compliance_label(suite_name)
            acs_results_summary[label] = "Not Compliant: not run"
            if requirement == "M":
                print(f"{RED}Suite: Mandatory  : {suite_name}: {acs_results_summary[label]}{RESET}")
                overall_comp = "Not Compliant"
                missing_list.append(suite_name)
            else:
                print(f"Suite: Recommended: {suite_name}: {acs_results_summary[label]}")
        else:
            fail_info = suite_fail_data.get(suite_name)
            f = fail_info.get("Failed", 0)
            fw = fail_info.get("Failed_with_Waiver", 0)
            label = compliance_label(suite_name)
            if (f + fw) == 0:
                acs_results_summary[label] = "Compliant"
                if requirement == "M":
                    print(f"Suite: Mandatory  : {suite_name}: {acs_results_summary[label]}")
                else:
                    print(f"Suite: Recommended: {suite_name}: {acs_results_summary[label]}")
            elif f == fw:
                acs_results_summary[label] = "Compliant with waivers"
                if requirement == "M":
                    print(f"Suite: Mandatory  : {suite_name}: {acs_results_summary[label]}")
                else:
                    print(f"Suite: Recommended: {suite_name}: {acs_results_summary[label]}")
                if requirement == "M" and overall_comp != "Not Compliant":
                    overall_comp="Compliant with waivers"
            else:
                acs_results_summary[label] = f"Not Compliant: Failed {f}"
                if requirement == "M":
                    print(f"{RED}Suite: Mandatory  : {suite_name}: {acs_results_summary[label]}{RESET}")
                    overall_comp="Not Compliant"
                    non_waived_list.append(suite_name)
                else:
                    print(f"Suite: Recommended: {suite_name}: {acs_results_summary[label]}")

    #Ensure suite-wise compliance lines for *all* discovered suites (including recommended)
    for skey, info in suite_fail_data.items():
        # If no label set, default to "Compliant" if fails=0, else "Not compliant", etc.
        label = compliance_label(skey)
        if label not in acs_results_summary:
            f = info["Failed"]
            fw = info["Failed_with_Waiver"]
            if (f + fw) == 0:
                acs_results_summary[label] = "Compliant"
            elif f == fw:
                acs_results_summary[label] = "Compliant with waivers"
            else:
                acs_results_summary[label] = "Not compliant"

    # Step 4) Overall compliance
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

    bbsr_tpm  = acs_results_summary.get(compliance_label("BBSR-TPM"), "")
    bbsr_fwts = acs_results_summary.get(compliance_label("BBSR-FWTS"), "")
    bbsr_sct  = acs_results_summary.get(compliance_label("BBSR-SCT"), "")
    overall_str = acs_results_summary.get("Overall Compliance Result", "")

        # Determine if every BBSR sub-suite passed with no failures
    all_bbsr_compliant = (
        bbsr_tpm  == "Compliant"
        and bbsr_fwts == "Compliant"
        and bbsr_sct  == "Compliant"
    )

    # Check if any suite or the overall result used a waiver
    any_waiver = (
        "waiver" in bbsr_tpm.lower()
        or "waiver" in bbsr_fwts.lower()
        or "waiver" in bbsr_sct.lower()
        or "waiver" in overall_str.lower()
    )

    # Case A: All sub-suites passed cleanly
    if all_bbsr_compliant:
        # 1) If the *overall* compliance is a hard failure, override and mark BBSR as Not Compliant
        if overall_str.startswith("Not Compliant"):
            acs_results_summary["BBSR extension compliance results"] = "Not Compliant"

        # 2) If the overall result is “Compliant with waivers,” reflect that here
        elif overall_str.lower().startswith("compliant with waivers"):
            acs_results_summary["BBSR extension compliance results"] = "Compliant with waivers"

        # 3) Otherwise (overall is strictly Compliant), BBSR is Compliant
        else:
            acs_results_summary["BBSR extension compliance results"] = "Compliant"

    # Case B: At least one suite or the overall result involved a waiver
    elif any_waiver:
        # 1) Still respect a hard overall failure as Not Compliant
        if overall_str.startswith("Not Compliant"):
            acs_results_summary["BBSR extension compliance results"] = "Not Compliant"
        # 2) Otherwise, we have a waiver situation
        else:
            acs_results_summary["BBSR extension compliance results"] = "Compliant with waivers"

    # Case C: Some sub-suite(s) failed outright without waivers
    else:
        # Gather which suites didn’t run vs. which failed non-waived
        missing_list_bbsr = []
        non_waived_list_bbsr = []

        for label, comp_str in [
            ("BBSR-TPM", bbsr_tpm),
            ("BBSR-FWTS", bbsr_fwts),
            ("BBSR-SCT", bbsr_sct),
        ]:
            # “not run” indicates missing entirely
            if comp_str.lower().startswith("not compliant: not run"):
                missing_list_bbsr.append(label)
            # “failed” indicates an explicit non-waived failure
            elif comp_str.lower().startswith("not compliant: failed"):
                non_waived_list_bbsr.append(label)

        # If no specific details, at least flag as generic Not Compliant
        if not missing_list_bbsr and not non_waived_list_bbsr:
            acs_results_summary["BBSR extension compliance results"] = "Not Compliant"
        else:
            # Build a human-readable reason with missing vs. non-waived lists
            parts = []
            if missing_list_bbsr:
                parts.append(f"missing suite(s): {', '.join(missing_list_bbsr)}")
            if non_waived_list_bbsr:
                parts.append(f"non-waived fails in suite(s): {', '.join(non_waived_list_bbsr)}")
            acs_results_summary["BBSR extension compliance results"] = (
                f"Not Compliant ({'; '.join(parts)})"
            )

    # Finally, print out the BBSR extension result with color coding
    bbsr_comp_str = acs_results_summary["BBSR extension compliance results"]
    if bbsr_comp_str.lower().startswith("compliant with waivers"):
        print(f"{YELLOW}BBSR extension compliance results: {bbsr_comp_str}{RESET}\n")
    elif bbsr_comp_str.lower().startswith("compliant"):
        print(f"{GREEN}BBSR extension compliance results: {bbsr_comp_str}{RESET}\n")
    else:
        print(f"{RED}BBSR extension compliance results: {bbsr_comp_str}{RESET}\n")
    
    RENAME_SUITES_TO_STANDALONE = {
        "Suite_Name: DT Kselftest": "Suite_Name: Standalone",
        "Suite_Name: CAPSULE_UPDATE": "Suite_Name: Standalone",
        "Suite_Name: DT Validate": "Suite_Name: Standalone",
        "Suite_Name: Ethtool Test": "Suite_Name: Standalone",
        "Suite_Name: Read Write Check Block Devices": "Suite_Name: Standalone",
        "Suite_Name: PSCI": "Suite_Name: Standalone"
    }

    def _entry_to_list(entry):
        if isinstance(entry, list):
            return entry
        if (
            isinstance(entry, dict)
            and "test_results" in entry
            and isinstance(entry["test_results"], list)
        ):
            return entry["test_results"]
        return [entry]

    for old_key, new_key in RENAME_SUITES_TO_STANDALONE.items():
        if old_key in merged_results:
            old_data_list = _entry_to_list(merged_results.pop(old_key))
            merged_results.setdefault(new_key, [])
            merged_results[new_key].extend(old_data_list)

    # Ensure consistent order for ACS Results Summary if present
    if "Suite_Name: acs_info" in merged_results and "ACS Results Summary" in merged_results["Suite_Name: acs_info"]:
        preferred_order = [
            "Band",
            "Date",
            "Suite_Name: Mandatory  : Capsule Update_compliance",
            "Suite_Name: Mandatory  : DT_VALIDATE_compliance",
            "Suite_Name: Mandatory  : ETHTOOL_TEST_compliance",
            "Suite_Name: Mandatory  : FWTS_compliance",
            "Suite_Name: Mandatory  : OS_TEST_compliance",
            "Suite_Name: Mandatory  : READ_WRITE_CHECK_BLK_DEVICES_compliance",
            "Suite_Name: Mandatory  : SCT_compliance",
            "Suite_Name: Recommended  : BBSR-FWTS_compliance",
            "Suite_Name: Recommended  : BBSR-SCT_compliance",
            "Suite_Name: Recommended  : BBSR-TPM_compliance",
            "Suite_Name: Recommended  : BSA_compliance",
            "Suite_Name: Recommended  : DT_KSELFTEST_compliance",
            "Suite_Name: Recommended  : POST_SCRIPT_compliance",
            "Suite_Name: Recommended  : PSCI_compliance",
            "BBSR extension compliance results",
            "Overall Compliance Result",
        ]
        actual = merged_results["Suite_Name: acs_info"]["ACS Results Summary"]
        ordered = OrderedDict()
        for key in preferred_order:
            if key in actual:
                ordered[key] = actual[key]
        for key in actual:
            if key not in ordered:
                ordered[key] = actual[key]
        merged_results["Suite_Name: acs_info"]["ACS Results Summary"] = ordered

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
