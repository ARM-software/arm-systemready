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

# Test Suite Mapping
test_suite_mapping = {
    "dt_kselftest": {
        "Test_suite_name": "DTValidation",
        "Test_suite_description": "Validation for device tree",
        "Test_case_description": "Device Tree kselftests"
    },
    "dt_validate": {
        "Test_suite_name": "DTValidation",
        "Test_suite_description": "Validation for device tree",
        "Test_case_description": "Device Tree Validation"
    },
    "ethtool_test": {
        "Test_suite_name": "Network",
        "Test_suite_description": "Network validation",
        "Test_case_description": "Ethernet Tool Tests"
    },
    "read_write_check_blk_devices": {
        "Test_suite_name": "Boot sources",
        "Test_suite_description": "Checks for boot sources",
        "Test_case_description": "Read/Write Check on Block Devices"
    },
    "capsule_update": {
        "Test_suite_name": "Capsule Update",
        "Test_suite_description": "Testing firmware capsule update mechanism",
        "Test_case_description": "Capsule Update Tests"
    },
    "psci_check": {
        "Test_suite_name": "PSCI",
        "Test_suite_description": "PSCI version check",
        "Test_case_description": "PSCI compliance"
    },
}

def create_subtest(subtest_number, description, status, reason=""):
    # Each subtest structure
    result = {
        "sub_Test_Number": str(subtest_number),
        "sub_Test_Description": description,
        "sub_test_result": {
            "PASSED": 1 if status == "PASSED" else 0,
            "FAILED": 1 if status == "FAILED" else 0,
            "FAILED_WITH_WAIVER": 0,  # We'll keep 0 by default unless set by external waiver logic
            "ABORTED": 0,
            "SKIPPED": 1 if status == "SKIPPED" else 0,
            "WARNINGS": 0,
            "pass_reasons": [reason] if (status == "PASSED" and reason) else [],
            "fail_reasons": [reason] if (status == "FAILED" and reason) else [],
            "abort_reasons": [],
            "skip_reasons": [reason] if (status == "SKIPPED" and reason) else [],
            "warning_reasons": [],
            "waiver_reason": ""  # Will be filled by waiver logic if needed
        }
    }
    return result

def update_suite_summary(suite_summary, status):
    if status in ["PASSED", "FAILED", "SKIPPED", "ABORTED", "WARNINGS"]:
        key = f"total_{status.lower()}"
        suite_summary[key] += 1

def parse_dt_kselftest_log(log_data):
    test_suite_key = "dt_kselftest"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waivers": 0
    }

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,
        "Test_case_description": mapping["Test_case_description"],
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    subtest_number = 1
    for line in log_data:
        line = line.strip()
        # Typical pattern: '# ok 1 description'
        subtest_match = re.match(r'# (ok|not ok) (\d+) (.+)', line)
        if subtest_match:
            status_str = subtest_match.group(1)
            description_and_status = subtest_match.group(3)

            if '# SKIP' in description_and_status:
                status = 'SKIPPED'
                description = description_and_status.replace('# SKIP', '').strip()
            else:
                description = description_and_status.strip()
                status = 'PASSED' if status_str == 'ok' else 'FAILED'

            sub = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(sub)
            current_test["test_suite_summary"][f"total_{status.lower()}"] += 1
            suite_summary[f"total_{status.lower()}"] += 1
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

def parse_dt_validate_log(log_data):
    test_suite_key = "dt_validate"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waiver": 0
    }

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,
        "Test_case_description": mapping["Test_case_description"],
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    subtest_number = 1
    for line in log_data:
        line = line.strip()
        # Often dt-validate will show lines like /path: error blah
        if re.match(r'^/.*: ', line):
            description = line
            status = 'FAILED'
            sub = create_subtest(subtest_number, description, status, reason=line)
            current_test["subtests"].append(sub)
            current_test["test_suite_summary"]["total_failed"] += 1
            suite_summary["total_failed"] += 1
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

def parse_ethtool_test_log(log_data):
    test_suite_key = "ethtool_test"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waivers": 0
    }

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],
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
    while i < len(log_data):
        line = log_data[i].strip()
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
        if f"INFO: Running \"ethtool {interface}\" :" in line:
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

def parse_read_write_check_blk_devices_log(log_data):
    test_suite_key = "read_write_check_blk_devices"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waivers": 0
    }

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,
        "Test_case_description": mapping["Test_case_description"],
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    subtest_number = 1
    i = 0
    while i < len(log_data):
        line = log_data[i].strip()
        if "INFO: Detected following block devices with lsblk command :" in line:
            i += 1
            while i < len(log_data) and log_data[i].strip() and not log_data[i].startswith("INFO"):
                i += 1
            continue

        elif line.startswith("INFO: Block device :"):
            device_name = line.split(":")[-1].strip()
            i += 1

            # raw device check
            if i < len(log_data) and (
                "treating as raw device." in log_data[i]
                or "No valid partition table found for" in log_data[i]
            ):
                # Skip the "treating as raw device" line
                i += 1

                # Now parse lines related to the raw device until next "INFO: Block device :" or "********"
                while i < len(log_data):
                    raw_line = log_data[i].strip()
                    # Stop if we've hit another device or end-of-section
                    if raw_line.startswith("INFO: Block device :") or raw_line.startswith("****************************************************************"):
                        break

                    # Look for the read test lines: "Performing block read on /dev/XYZ"
                    if "Performing block read on" in raw_line:
                        # Next lines might say "Block read on /dev/XYZ successful" or "failed"
                        i += 1
                        read_status = "FAILED"
                        read_reason = "Block read result not found"
                        if i < len(log_data):
                            possible_result = log_data[i].strip()
                            if "Block read on" in possible_result:
                                if "successful" in possible_result:
                                    read_status = "PASSED"
                                else:
                                    read_status = "FAILED"
                                read_reason = possible_result
                                i += 1

                        # Create a subtest for the raw read
                        desc_read = f"Read check on Raw device {device_name}"
                        sub_read = create_subtest(subtest_number, desc_read, read_status, reason=read_reason)
                        current_test["subtests"].append(sub_read)
                        update_suite_summary(current_test["test_suite_summary"], read_status)
                        suite_summary[f"total_{read_status.lower()}"] += 1
                        subtest_number += 1

                        # Now see if we have a write check (passed/failed) or skip
                        # e.g. "INFO: /dev/sda is mounted, skipping write test."
                        # or "Do you want to perform a write check on /dev/sda? (yes/no): yes"
                        if i < len(log_data) and "is mounted, skipping write test" in log_data[i]:
                            write_reason = log_data[i].strip()
                            write_status = "SKIPPED"
                            i += 1
                            desc_write = f"Write check on Raw device {device_name}"
                            sub_write = create_subtest(subtest_number, desc_write, write_status, reason=write_reason)
                            current_test["subtests"].append(sub_write)
                            update_suite_summary(current_test["test_suite_summary"], write_status)
                            suite_summary[f"total_{write_status.lower()}"] += 1
                            subtest_number += 1

                        elif i < len(log_data) and "Do you want to perform a write check on" in log_data[i]:

                            # If user said yes/no
                            prompt_line = log_data[i].strip()
                            if "yes" in prompt_line.lower():
                                i += 1
                                ws = None
                                wr = "No explicit write-check result found"
                                while i < len(log_data):
                                    w_line = log_data[i].strip()
                                    if w_line.startswith("INFO: Block device :") or w_line.startswith("****************************************************************"):
                                        break
                                    if "INFO: write check passed on" in w_line:
                                        ws = "PASSED"
                                        wr = w_line
                                        i += 1
                                        break
                                    if "INFO: write check failed on" in w_line:
                                        ws = "FAILED"
                                        wr = w_line
                                        i += 1
                                        break
                                    i += 1

                                # no user input for yes/no for write check:
                                if not ws:
                                    ws = "SKIPPED"
                                    wr = "User did not choose the prompt"

                                desc_write = f"Write check on Raw device {device_name}"
                                sub_write = create_subtest(subtest_number, desc_write, ws, reason=wr)
                                current_test["subtests"].append(sub_write)
                                update_suite_summary(current_test["test_suite_summary"], ws)
                                suite_summary[f"total_{ws.lower()}"] += 1
                                subtest_number += 1
                            else:
                                # User said no or timed out
                                write_status = "SKIPPED"
                                write_reason = "Write check skipped due to user input or timeout"
                                while i < len(log_data):
                                    if (log_data[i].strip().startswith("INFO: Block device :")
                                        or log_data[i].strip().startswith("****************************************************************")):
                                        break
                                    i += 1
                                desc_write = f"Write check on Raw device {device_name}"
                                sub_write = create_subtest(subtest_number, desc_write, write_status, reason=write_reason)
                                current_test["subtests"].append(sub_write)
                                update_suite_summary(current_test["test_suite_summary"], write_status)
                                suite_summary[f"total_{write_status.lower()}"] += 1
                                subtest_number += 1

                    else:
                        i += 1

                # Done handling raw device lines; go to next device
                continue

            if i < len(log_data) and "Invalid partition table or not found for" in log_data[i]:
                status = "FAILED"
                reason = log_data[i].strip()
                desc = f"Partition table check on {device_name}"
                sub = create_subtest(subtest_number, desc, status, reason=reason)
                current_test["subtests"].append(sub)
                update_suite_summary(current_test["test_suite_summary"], status)
                suite_summary[f"total_{status.lower()}"] += 1
                subtest_number += 1
                i += 1
                continue

            while i < len(log_data):
                line = log_data[i].strip()
                if line.startswith("INFO: Partition :"):
                    partition_match = re.match(r'INFO: Partition :\s+(\S+)', line)
                    if partition_match:
                        partition_name = partition_match.group(1)
                    else:
                        partition_name = "Unknown"

                    i += 1
                    if i < len(log_data):
                        next_line = log_data[i].strip()
                        # 1) PRECIOUS => single SKIPPED subtest
                        if "is PRECIOUS" in next_line:
                            status = "SKIPPED"
                            reason = next_line
                            desc = f"Read/Write check on Partition {partition_name}"
                            sub = create_subtest(subtest_number, desc, status, reason=reason)
                            current_test["subtests"].append(sub)
                            update_suite_summary(current_test["test_suite_summary"], status)
                            suite_summary[f"total_{status.lower()}"] += 1
                            subtest_number += 1

                            while i < len(log_data):
                                if (log_data[i].strip().startswith("INFO: Partition :")
                                    or log_data[i].strip().startswith("INFO: Block device :")
                                    or log_data[i].strip().startswith("****************************************************************")):
                                    break
                                i += 1

                        # 2) "Performing block read on"
                        elif "Performing block read on" in next_line:
                            i += 1
                            read_status = "FAILED"
                            read_reason = "Block read result not found"
                            while i < len(log_data):
                                read_line = log_data[i].strip()
                                if (read_line.startswith("INFO: Partition :") or
                                    read_line.startswith("INFO: Block device :") or
                                    read_line.startswith("****************************************************************")):
                                    break
                                if "Block read on" in read_line:
                                    if "successful" in read_line:
                                        read_status = "PASSED"
                                    else:
                                        read_status = "FAILED"
                                    read_reason = read_line
                                    i += 1
                                    break
                                i += 1

                            # Create subtest for READ
                            read_desc = f"Read check on Partition {partition_name}"
                            read_sub = create_subtest(subtest_number, read_desc, read_status, reason=read_reason)
                            current_test["subtests"].append(read_sub)
                            update_suite_summary(current_test["test_suite_summary"], read_status)
                            suite_summary[f"total_{read_status.lower()}"] += 1
                            subtest_number += 1

                            # 3) check skip line or write prompt
                            write_status = None
                            write_reason = ""
                            if i < len(log_data) and "is mounted, skipping write test" in log_data[i]:
                                write_status = "SKIPPED"
                                write_reason = log_data[i].strip()
                                i += 1

                                write_desc = f"Write check on Partition {partition_name}"
                                write_sub = create_subtest(subtest_number, write_desc, write_status, reason=write_reason)
                                current_test["subtests"].append(write_sub)
                                update_suite_summary(current_test["test_suite_summary"], write_status)
                                suite_summary[f"total_{write_status.lower()}"] += 1
                                subtest_number += 1

                            elif i < len(log_data) and "Do you want to perform a write check on" in log_data[i]:
                                prompt_line = log_data[i].strip()
                                if "yes" in prompt_line.lower():
                                    i += 1
                                    ws = None
                                    wr = "No explicit write-check result found"
                                    while i < len(log_data):
                                        w_line = log_data[i].strip()
                                        if (w_line.startswith("INFO: Partition :")
                                            or w_line.startswith("INFO: Block device :")
                                            or w_line.startswith("****************************************************************")):
                                            break
                                        if "INFO: write check passed on" in w_line:
                                            ws = "PASSED"
                                            wr = w_line
                                            i += 1
                                            break
                                        if "INFO: write check failed on" in w_line:
                                            ws = "FAILED"
                                            wr = w_line
                                            i += 1
                                            break
                                        i += 1

                                    if not ws:
                                        ws = "SKIPPED"
                                        wr = "User did not choose the prompt"
                                    write_status = ws
                                    write_reason = wr
                                else:
                                    write_status = "SKIPPED"
                                    write_reason = "Write check skipped due to user input or timeout"
                                    while i < len(log_data):
                                        if (log_data[i].strip().startswith("INFO: Partition :")
                                            or log_data[i].strip().startswith("INFO: Block device :")
                                            or log_data[i].strip().startswith("****************************************************************")):
                                            break
                                        i += 1

                                if write_status:
                                    write_desc = f"Write check on Partition {partition_name}"
                                    write_sub = create_subtest(subtest_number, write_desc, write_status, reason=write_reason)
                                    current_test["subtests"].append(write_sub)
                                    update_suite_summary(current_test["test_suite_summary"], write_status)
                                    suite_summary[f"total_{write_status.lower()}"] += 1
                                    subtest_number += 1

                        else:
                            i += 1

                elif line.startswith("INFO: Block device :") or line.startswith("****************************************************************"):
                    break
                else:
                    i += 1
            continue
        else:
            i += 1

    # >>> REMOVE EMPTY REASON ARRAYS <<<
    for subtest in current_test["subtests"]:
        subres = subtest["sub_test_result"]
        if not subres.get("pass_reasons", []):
            del subres["pass_reasons"]
        if not subres.get("fail_reasons", []):
            del subres["fail_reasons"]
        if not subres.get("abort_reasons", []):
            del subres["abort_reasons"]
        if not subres.get("skip_reasons", []):
            del subres["skip_reasons"]
        if not subres.get("warning_reasons", []):
            del subres["warning_reasons"]

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary
    }

# PARSER FOR CAPSULE UPDATE 
def parse_capsule_update_logs(capsule_update_log_path, capsule_test_results_log_path):
    test_suite_key = "capsule_update"
    mapping = {
        "Test_suite_name": "Capsule Update",
        "Test_suite_description": "Tests for automatic capsule update",
        "Test_case_description": "Capsule Update"
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
        "Test_suite_name": mapping["Test_suite_name"],
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,
        "Test_case_description": mapping["Test_case_description"],
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    def read_file_lines(path, encoding='utf-8'):
        try:
            with open(path, 'r', encoding=encoding, errors='ignore') as f:
                return f.readlines()
        except:
            return []

    update_lines = read_file_lines(capsule_update_log_path, encoding='utf-16')
    results_lines = read_file_lines(capsule_test_results_log_path, encoding='utf-8')

    subtest_number = 1

    def add_subtest(desc, status, reason=""):
        nonlocal subtest_number
        sub = create_subtest(subtest_number, desc, status, reason)
        current_test["subtests"].append(sub)
        update_suite_summary(current_test["test_suite_summary"], status)
        suite_summary[f"total_{status.lower()}"] += 1
        subtest_number += 1

    # PARSE capsule-update.log
    i = 0
    while i < len(update_lines):
        line = update_lines[i].strip()
        match = re.match(r"Testing\s+(unauth\.bin|tampered\.bin)\s+update", line, re.IGNORECASE)
        if match:
            test_desc = line
            test_info = ""
            result = "FAILED"
            i += 1
            while i < len(update_lines):
                cur = update_lines[i].strip()
                if re.match(r"Testing\s+", cur, re.IGNORECASE):
                    i -= 1
                    break
                elif re.match(r"Test[_\s]Info", cur, re.IGNORECASE):
                    i += 1
                    info_lines = []
                    while i < len(update_lines):
                        info_line = update_lines[i].strip()
                        if re.match(r"Testing\s+", info_line, re.IGNORECASE):
                            i -= 1
                            break
                        info_lines.append(info_line)
                        i += 1
                    test_info = "\n".join(info_lines)
                    if "failed to update capsule" in test_info.lower():
                        result = "PASSED"
                    elif "not present" in test_info.lower():
                        result = "FAILED"
                    elif "succeed to write" in test_info.lower():
                        result = "PASSED"
                    else:
                        result = "FAILED"
                    break
                else:
                    i += 1
            add_subtest(test_desc, result, reason=test_info.splitlines())
        i += 1

    # PARSE capsule_test_results.log
    i = 0
    while i < len(results_lines):
        line = results_lines[i].strip()
        sanity_match = re.match(r"Testing\s+signed_capsule\.bin\s+sanity", line, re.IGNORECASE)
        esrt_match = re.match(r"(Testing|Test:\s+Testing)\s+ESRT\s+FW\s+version\s+update", line, re.IGNORECASE)

        if sanity_match:
            test_desc = line
            test_info = ""
            result = "PASSED"
            i += 1
            while i < len(results_lines):
                cur = results_lines[i].strip()
                if re.match(r"Testing\s+", cur, re.IGNORECASE) or re.match(r"Test:\s+", cur, re.IGNORECASE):
                    i -= 1
                    break
                elif "error sanity_check_capsule" in cur.lower():
                    result = "FAILED"
                    test_info = cur
                    break
                elif "warning" in cur.lower():
                    result = "PASSED"
                    test_info = cur
                    break
                else:
                    i += 1
            add_subtest(test_desc, result, reason=test_info.splitlines())

        elif esrt_match:
            test_desc = "Testing ESRT FW version update"
            test_info_lines = []
            result = "FAILED"
            any_failed = False
            overall = None
            last_info_idx = -1
            i += 1
            while i < len(results_lines):
                cur = results_lines[i].strip()
                if re.match(r"Testing\s+", cur, re.IGNORECASE) or re.match(r"Test:\s+", cur, re.IGNORECASE):
                    i -= 1
                    break
                elif cur.lower().startswith("info:"):
                    info_text = cur[len("INFO:"):].strip()
                    test_info_lines.append(info_text)
                    last_info_idx = len(test_info_lines) - 1
                    i += 1
                elif cur.lower().startswith("results:"):
                    outcome_line = cur[len("RESULTS:"):].strip()
                    if re.search(r"overall\s+capsule\s+update\s+result", outcome_line, re.IGNORECASE):
                        overall = "PASSED" if "PASSED" in outcome_line.upper() else "FAILED"
                    else:
                        # tag the last INFO with this outcome
                        outcome = "FAILED" if "FAILED" in outcome_line.upper() else ("PASSED" if "PASSED" in outcome_line.upper() else None)
                        if outcome == "FAILED":
                            any_failed = True
                        if last_info_idx >= 0 and outcome:
                            test_info_lines[last_info_idx] = f"{test_info_lines[last_info_idx]} - {outcome}"
                    i += 1
                else:
                    i += 1
            if overall:
                result = overall
            else:
                result = "FAILED" if any_failed else "PASSED"
            add_subtest(test_desc, result, reason=test_info_lines)


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

###############################################################################
# PSCI Checker Parse
###############################################################################
def parse_psci_logs(psci_log_path):
    test_suite_key = "psci_check"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "total_aborted": 0,
        "total_warnings": 0,
        "total_failed_with_waivers": 0
    }

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],       # "PSCI"
        "Test_suite_description": mapping["Test_suite_description"],  # "PSCI version check"
        "Test_case": test_suite_key,                         # "psci_check"
        "Test_case_description": mapping["Test_case_description"],  # "PSCI compliance"
        "subtests": [],
        "test_suite_summary": suite_summary.copy()
    }

    # If file not found => Instead of failing, let's mark this as a WARNING
    if not os.path.isfile(psci_log_path):
        sub = create_subtest(
            subtest_number=1,
            description="PSCI version checker(1.0 or above)",
            status="WARNINGS",
            reason=f"PSCI log file not found at {psci_log_path}"
        )
        current_test["subtests"].append(sub)
        current_test["test_suite_summary"]["total_warnings"] += 1
        suite_summary["total_warnings"] += 1
        return {"test_results": [current_test], "suite_summary": suite_summary}

    # Read lines
    with open(psci_log_path, 'r') as f:
        lines = f.readlines()

    version_pattern = re.compile(r'psci:\s+PSCIv([\d\.]+)\s+detected in firmware\.', re.IGNORECASE)
    version_found = None
    for line in lines:
        match = version_pattern.search(line.strip())
        if match:
            version_found = match.group(1)
            break

    # Subtest description now is "PSCI version checker(1.0 or above)"
    subtest_desc = "PSCI version checker(1.0 or above)"

    if version_found:
        try:
            val = float(version_found)
            if val >= 1.0:
                status = "PASSED"
                reason = f"PSCI version {version_found} >= 1.0"
            else:
                # Below 1.0 => WARNING, not fail
                status = "WARNINGS"
                reason = f"PSCI version {version_found} < 1.0 => WARN"
        except ValueError:
            # Invalid format => WARNING, not fail
            status = "WARNINGS"
            reason = f"Invalid PSCI version format: {version_found}"
    else:
        # No PSCI line found => WARNING, not fail
        status = "WARNINGS"
        reason = "No 'PSCIvX.Y detected in firmware' line found"

    sub = create_subtest(1, subtest_desc, status, reason)
    current_test["subtests"].append(sub)
    current_test["test_suite_summary"][f"total_{status.lower()}"] += 1
    suite_summary[f"total_{status.lower()}"] += 1

    # Cleanup reason arrays
    for s in current_test["subtests"]:
        subres = s["sub_test_result"]
        for key_list in ["pass_reasons", "fail_reasons", "abort_reasons", "skip_reasons", "warning_reasons"]:
            if not subres[key_list]:
                del subres[key_list]

    return {"test_results": [current_test], "suite_summary": current_test["test_suite_summary"]}


def parse_single_log(log_file_path):
    with open(log_file_path, 'r') as f:
        log_data = f.readlines()

    log_content = ''.join(log_data)

    if re.search(r'selftests: dt: test_unprobed_devices.sh', log_content):
        return parse_dt_kselftest_log(log_data)
    elif re.search(r'DeviceTree bindings of Linux kernel version', log_content):
        return parse_dt_validate_log(log_data)
    elif re.search(r'Running ethtool', log_content):
        return parse_ethtool_test_log(log_data)
    elif re.search(r'Read block devices tool', log_content):
        return parse_read_write_check_blk_devices_log(log_data)
    else:
        # No known pattern => unknown
        raise ValueError("Unknown or unsupported standalone log format.")

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        # Single log usage
        log_file, output_json = args
        try:
            result = parse_single_log(log_file)
        except ValueError as ve:
            print(f"Error: {ve}")
            sys.exit(1)
        with open(output_json, 'w') as out:
            json.dump(result, out, indent=4)
        sys.exit(0)

    elif len(args) == 4 and args[0].lower() == "capsule_update":
        # Capsule update usage
        _, update_log, test_results_log, output_json = args
        result = parse_capsule_update_logs(update_log, test_results_log)
        with open(output_json, 'w') as out:
            json.dump(result, out, indent=4)
        sys.exit(0)

    # PSCI check usage
    elif len(args) == 3 and args[0].lower() == "psci_check":
        # logs_to_json.py psci_check <psci_log> <output_json>
        _, psci_log, output_json = args
        result = parse_psci_logs(psci_log)
        with open(output_json, 'w') as out:
            json.dump(result, out, indent=4)
        sys.exit(0)
    else:
        print("Usage:")
        print("  1) Single log:      python3 logs_to_json.py <path_to_log> <output_JSON>")
        print("  2) Capsule update:  python3 logs_to_json.py capsule_update <update_log> <test_results_log> <output_JSON>")
        print("  3) PSCI check:      python3 logs_to_json.py psci_check <psci_kernel.log> <output_JSON>")
        sys.exit(1)
