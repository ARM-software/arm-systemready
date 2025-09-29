#!/usr/bin/env python3
# Copyright (c) 2024-2025, Arm Limited or its affiliates. All rights reserved.
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

import sys
import re
import json
import os

ansi_escape = re.compile(r'\x1B\[[0-9;]*[A-Za-z]')

def create_subtest(subtest_number, description, status, reason=""):
    result = {
        "sub_Test_Number": str(subtest_number),
        "sub_Test_Description": description,
        "sub_test_result": {
            "PASSED": 1 if status == "PASSED" else 0,
            "FAILED": 1 if status == "FAILED" else 0,
            "ABORTED": 0,
            "SKIPPED": 1 if status == "SKIPPED" else 0,
            "WARNINGS": 0,
            "pass_reasons": [reason] if status == "PASSED" and reason else [],
            "fail_reasons": [reason] if status == "FAILED" and reason else [],
            "abort_reasons": [],
            "skip_reasons": [reason] if status == "SKIPPED" and reason else [],
            "warning_reasons": []
        }
    }
    return result

def update_suite_summary(suite_summary, status):
    s = status.strip().upper()
    if s in ("FAILED (WITH WAIVER)", "FAILED_WITH_WAIVER"):
        suite_summary["total_failed_with_waiver"] += 1
        return
    mapping = {
        "PASSED": "total_passed",
        "FAILED": "total_failed",
        "SKIPPED": "total_skipped",
        "ABORTED": "total_aborted",
        "WARNING": "total_warnings",
        "WARNINGS": "total_warnings",
    }
    if s in mapping:
        suite_summary[mapping[s]] += 1

def parse_ethtool_test_log(log_data, os_name):
    test_suite_key = f"ethtool_test_{os_name}"  # e.g., ethtool_test_linux-opensuse-leap-15.5-version

    mapping = {
        "Test_suite": "Network",
        "Test_suite_description": "Network validation",
        "Test_case_description": "Ethernet Tool Tests"
    }

    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waivers": 0
    }

    current_test = {
        "Test_suite": mapping["Test_suite"],
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,
        "Test_case_description": mapping["Test_case_description"],
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    subtest_number = 1
    interface = None
    detected_interfaces = []
    i = 0
    # strip ANSI codes from the entire log once
    log_data = [re.sub(ansi_escape, '', s) for s in log_data]
    while i < len(log_data):
        line = re.sub(ansi_escape, '', log_data[i]).strip()
        # Detecting interfaces
        if line.startswith("INFO: No ethernet interfaces detected via ip linux command"):
            status = "FAILED"
            desc = "No Ethernet Interfaces Detected"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1
            i += 1
            continue

        # Detecting interfaces
        if line.startswith("INFO: Detected following ethernet interfaces via ip command :"):
            interfaces = []
            i += 1
            while i < len(log_data) and log_data[i].strip() and not log_data[i].startswith("INFO"):
                match = re.match(r'\d+:\s+(\S+)', log_data[i].strip())
                if match:
                    interfaces.append(match.group(1))
                i += 1
            if interfaces:
                detected_interfaces = interfaces
                status = "PASSED"
                desc = f"Detection of Ethernet Interfaces: {', '.join(interfaces)}"
            else:
                status = "FAILED"
                desc = "No Ethernet Interfaces Detected"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1
            continue

        # Bringing down all interfaces
        if "INFO: Bringing down all ethernet interfaces using ifconfig" in line:
            status = "PASSED"
            desc = "Bringing down all Ethernet interfaces"
            for j in range(i + 1, len(log_data)):
                if "Unable to bring down ethernet interface" in log_data[j]:
                    status = "FAILED"
                    desc = "Failed to bring down some Ethernet interfaces"
                    break
                if "****************************************************************" in log_data[j]:
                    break
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # Bringing up specific interface
        if "INFO: Bringing up ethernet interface:" in line:
            interface = line.split(":")[-1].strip()
            if i + 1 < len(log_data) and "Unable to bring up ethernet interface" in log_data[i + 1]:
                status = "FAILED"
                desc = f"Bring up interface {interface}"
            else:
                status = "PASSED"
                desc = f"Bring up interface {interface}"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # Running ethtool command
        if f'INFO: Running "ethtool {interface}' in line:
            status = "PASSED"
            desc = f"Running ethtool on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # Self-test detection
        if "INFO: Ethernet interface" in line and "ethtool self test" in line:
            if "doesn't supports ethtool self test" in line:
                status = "SKIPPED"
                desc   = f"Self-test on {interface} (Not supported)"
            else:
                # Look ahead up to 20 lines to find "The test result is ..."
                result_status = None
                for k in range(i + 1, min(i + 21, len(log_data))):
                    if "The test result is" in log_data[k]:
                        result_status = "PASSED" if "PASS" in log_data[k] else "FAILED"
                        break

                if result_status:
                    status = result_status
                    desc   = f"Self-test on {interface}"
                else:
                    status = "FAILED"
                    desc   = f"Self-test on {interface} (Result not found)"

            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # Link detection
        if "Link detected:" in line:
            if "yes" in line:
                status = "PASSED"
                desc = f"Link detected on {interface}"
            else:
                status = "FAILED"
                desc = f"Link not detected on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # DHCP
        if "doesn't support DHCP" in line or "support DHCP" in line:
            if "doesn't support DHCP" in line:
                status = "FAILED"
                desc = f"DHCP support on {interface}"
            else:
                status = "PASSED"
                desc = f"DHCP support on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # Ping to router
        if "INFO: Ping to router/gateway" in line and "is successful" in line:
                status = "PASSED"
                desc = f"Ping to router/gateway on {interface}"
                sub = create_subtest(subtest_number, desc, status)
                update_suite_summary(current_test["test_suite_summary"], status)
                current_test["subtests"].append(sub)
                suite_summary[f"total_{status.lower()}"] += 1
                subtest_number += 1
        if "Failed to ping router/gateway" in line:
            intf = line.split("for")[-1].strip()
            status = "FAILED"
            desc = f"Ping to router/gateway on {intf}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # Ping to www.arm.com
        if "INFO: Ping to www.arm.com" in line and "is successful" in line:
                status = "PASSED"
                desc = f"Ping to www.arm.com on {interface}"
                sub = create_subtest(subtest_number, desc, status)
                update_suite_summary(current_test["test_suite_summary"], status)
                current_test["subtests"].append(sub)
                suite_summary[f"total_{status.lower()}"] += 1
                subtest_number += 1
        if "Failed to ping www.arm.com via" in line:
            intf = line.split("via")[-1].strip()
            status = "FAILED"
            desc = f"Ping to www.arm.com on {intf}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # >>> Wget checks <<<
        if "INFO: wget failed to reach https://www.arm.com via" in line:
            intf = line.split("via")[-1].strip()
            status = "FAILED"
            desc = f"Wget connectivity to https://www.arm.com on {intf}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        if "INFO: wget successfully accessed https://www.arm.com via" in line:
            intf = line.split("via")[-1].strip()
            status = "PASSED"
            desc = f"Wget connectivity to https://www.arm.com on {intf}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        # >>> Curl checks <<<
        if "INFO: curl failed to fetch https://www.arm.com via" in line:
            intf = line.split("via")[-1].strip()
            status = "FAILED"
            desc = f"Curl connectivity to https://www.arm.com on {intf}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        if "INFO: curl successfully fetched https://www.arm.com via" in line:
            intf = line.split("via")[-1].strip()
            status = "PASSED"
            desc = f"Curl connectivity to https://www.arm.com on {intf}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status.lower()}"] += 1
            subtest_number += 1

        i += 1

    # If no ping tests found for the detected interfaces, add them as SKIPPED
    for intf in detected_interfaces:
        # Ping to router
        if not any(st["sub_Test_Description"] == f"Ping to router/gateway on {intf}" for st in current_test["subtests"]):
            sub = create_subtest(subtest_number, f"Ping to router/gateway on {intf}", "SKIPPED")
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], "SKIPPED")
            suite_summary["total_skipped"] += 1
            subtest_number += 1

        # Ping to arm.com
        if not any(st["sub_Test_Description"] == f"Ping to www.arm.com on {intf}" for st in current_test["subtests"]):
            sub = create_subtest(subtest_number, f"Ping to www.arm.com on {intf}", "SKIPPED")
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], "SKIPPED")
            suite_summary["total_skipped"] += 1
            subtest_number += 1

    # >>> REMOVE EMPTY REASON ARRAYS <<<
    for subtest in current_test["subtests"]:
        subres = subtest["sub_test_result"]
        if not subres["pass_reasons"]:
            del subres["pass_reasons"]
        if not subres["fail_reasons"]:
            del subres["fail_reasons"]
        if not subres["abort_reasons"]:
            del subres["abort_reasons"]
        if not subres["skip_reasons"]:
            del subres["skip_reasons"]
        if not subres["warning_reasons"]:
            del subres["warning_reasons"]

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary


    }

def parse_log(log_file_path, os_name):
    with open(log_file_path, 'r') as f:
        log_data = f.readlines()
    return parse_ethtool_test_log(log_data, os_name)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 logs_to_json.py <path to ethtool_test.log> <output JSON file path> <os_name>")
        sys.exit(1)

    log_file_path = sys.argv[1]
    output_file_path = sys.argv[2]
    os_name = sys.argv[3]

    try:
        output_json = parse_log(log_file_path, os_name)
    except ValueError as ve:
        print(f"Error: {ve}")
        sys.exit(1)

    with open(output_file_path, 'w') as outfile:
        json.dump(output_json, outfile, indent=4)
