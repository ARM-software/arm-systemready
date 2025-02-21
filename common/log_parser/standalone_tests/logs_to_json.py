#!/usr/bin/env python3
# Copyright (c) 2024, Arm Limited or its affiliates. All rights reserved.
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
        key = f"total_{status}"
        suite_summary[key] += 1


def parse_dt_kselftest_log(log_data):
    test_suite_key = "dt_kselftest"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_SKIPPED": 0,
        "total_ABORTED": 0,
        "total_WARNINGS": 0
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
            # subtest_number = subtest_match.group(2)  # We can use our own subtest_number increment
            description_and_status = subtest_match.group(3)

            if '# SKIP' in description_and_status:
                status = 'SKIPPED'
                description = description_and_status.replace('# SKIP', '').strip()
            else:
                description = description_and_status.strip()
                status = 'PASSED' if status_str == 'ok' else 'FAILED'

            sub = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(sub)
            current_test["test_suite_summary"][f"total_{status}"] += 1
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary
    }

def parse_dt_validate_log(log_data):
    test_suite_key = "dt_validate"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_SKIPPED": 0,
        "total_ABORTED": 0,
        "total_WARNINGS": 0
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
            current_test["test_suite_summary"]["total_FAILED"] += 1
            suite_summary["total_FAILED"] += 1
            subtest_number += 1

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary
    }

def parse_ethtool_test_log(log_data):
    test_suite_key = "ethtool_test"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_SKIPPED": 0,
        "total_ABORTED": 0,
        "total_WARNINGS": 0
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
            suite_summary[f"total_{status}"] += 1
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
            suite_summary[f"total_{status}"] += 1
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
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Running ethtool command
        if f"INFO: Running \"ethtool {interface}\" :" in line:
            status = "PASSED"
            desc = f"Running ethtool on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Self-test detection
        if "INFO: Ethernet interface" in line and "supports ethtool self test" in line:
            if "doesn't support ethtool self test" in line:
                status = "SKIPPED"
                desc = f"Self-test on {interface} (Not supported)"
            else:
                result_line_idx = i + 2
                if result_line_idx < len(log_data) and "The test result is" in log_data[result_line_idx]:
                    if "PASS" in log_data[result_line_idx]:
                        status = "PASSED"
                    else:
                        status = "FAILED"
                    desc = f"Self-test on {interface}"
                else:
                    status = "FAILED"
                    desc = f"Self-test on {interface} (Result not found)"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
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
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # DHCP
        if "doesn't support DHCP" in line or "supports DHCP" in line:
            if "doesn't support DHCP" in line:
                status = "FAILED"
                desc = f"DHCP support on {interface}"
            else:
                status = "PASSED"
                desc = f"DHCP support on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Ping to router
        if "INFO: Ping to router/gateway" in line:
            if "is successful" in line:
                status = "PASSED"
                desc = f"Ping to router/gateway on {interface}"
            else:
                status = "FAILED"
                desc = f"Ping to router/gateway on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Ping to www.arm.com
        if "INFO: Ping to www.arm.com" in line:
            if "is successful" in line:
                status = "PASSED"
                desc = f"Ping to www.arm.com on {interface}"
            else:
                status = "FAILED"
                desc = f"Ping to www.arm.com on {interface}"
            sub = create_subtest(subtest_number, desc, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(sub)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        i += 1

    # If no ping tests found for the detected interfaces, add them as SKIPPED
    for intf in detected_interfaces:
        # Ping to router
        if not any(st["sub_Test_Description"] == f"Ping to router/gateway on {intf}" for st in current_test["subtests"]):
            sub = create_subtest(subtest_number, f"Ping to router/gateway on {intf}", "SKIPPED")
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], "SKIPPED")
            suite_summary["total_SKIPPED"] += 1
            subtest_number += 1

        # Ping to arm.com
        if not any(st["sub_Test_Description"] == f"Ping to www.arm.com on {intf}" for st in current_test["subtests"]):
            sub = create_subtest(subtest_number, f"Ping to www.arm.com on {intf}", "SKIPPED")
            current_test["subtests"].append(sub)
            update_suite_summary(current_test["test_suite_summary"], "SKIPPED")
            suite_summary["total_SKIPPED"] += 1
            subtest_number += 1

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary
    }

def parse_read_write_check_blk_devices_log(log_data):
    test_suite_key = "read_write_check_blk_devices"
    mapping = test_suite_mapping[test_suite_key]

    suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_SKIPPED": 0,
        "total_ABORTED": 0,
        "total_WARNINGS": 0
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
            # We only store them if needed, not mandatory
            i += 1
            while i < len(log_data) and log_data[i].strip() and not log_data[i].startswith("INFO"):
                i += 1
            continue
        elif line.startswith("INFO: Block device :"):
            device_name = line.split(":")[-1].strip()
            i += 1
            if i < len(log_data) and "Invalid partition table or not found for" in log_data[i]:
                # Partition table is invalid
                status = "FAILED"
                reason = log_data[i].strip()
                desc = f"Partition table check on {device_name}"
                sub = create_subtest(subtest_number, desc, status, reason=reason)
                current_test["subtests"].append(sub)
                update_suite_summary(current_test["test_suite_summary"], status)
                suite_summary[f"total_{status}"] += 1
                subtest_number += 1
                i += 1
                continue
            # Process partitions
            while i < len(log_data):
                line = log_data[i].strip()
                if line.startswith("INFO: Partition :"):
                    partition_match = re.match(r'INFO: Partition :\s+(\S+)', line)
                    if partition_match:
                        partition_name = partition_match.group(1)
                    else:
                        partition_name = "Unknown"

                    i += 1
                    partition_status = None
                    partition_reason = ""

                    if i < len(log_data):
                        next_line = log_data[i].strip()
                        if "is PRECIOUS" in next_line:
                            partition_status = "SKIPPED"
                            partition_reason = next_line
                            while i < len(log_data):
                                if (log_data[i].strip().startswith("INFO: Partition :") or 
                                   log_data[i].strip().startswith("INFO: Block device :") or 
                                   log_data[i].strip().startswith("****************************************************************")):
                                    break
                                i += 1
                        elif "Performing block read on" in next_line:
                            i += 1
                            if i < len(log_data):
                                read_result_line = log_data[i].strip()
                                if "Block read on" in read_result_line and "successful" in read_result_line:
                                    read_status = "PASSED"
                                    read_reason = read_result_line
                                else:
                                    read_status = "FAILED"
                                    read_reason = read_result_line
                                i += 1
                            else:
                                read_status = "FAILED"
                                read_reason = "Block read result not found"

                            write_status = None
                            write_reason = ""

                            if i < len(log_data) and "Do you want to perform a write check on" in log_data[i]:
                                # We consider it SKIPPED
                                write_status = "SKIPPED"
                                write_reason = "Write check skipped due to user input or timeout"
                                while i < len(log_data):
                                    if (log_data[i].strip().startswith("INFO: Partition :") or 
                                       log_data[i].strip().startswith("INFO: Block device :") or 
                                       log_data[i].strip().startswith("****************************************************************")):
                                        break
                                    i += 1

                            if read_status == "PASSED":
                                partition_status = "PASSED"
                                if write_status == "SKIPPED":
                                    partition_reason = f"{read_reason}. {write_reason}"
                                else:
                                    partition_reason = read_reason
                            else:
                                partition_status = "FAILED"
                                partition_reason = read_reason
                        else:
                            # Move on if unknown line
                            i += 1

                    if partition_status:
                        desc = f"Read/Write check on Partition {partition_name}"
                        sub = create_subtest(subtest_number, desc, partition_status, partition_reason)
                        current_test["subtests"].append(sub)
                        update_suite_summary(current_test["test_suite_summary"], partition_status)
                        suite_summary[f"total_{partition_status}"] += 1
                        subtest_number += 1

                elif line.startswith("INFO: Block device :") or line.startswith("****************************************************************"):
                    break
                else:
                    i += 1
            continue
        else:
            i += 1

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary
    }

#
# PARSER FOR CAPSULE UPDATE 
#
def parse_capsule_update_logs(capsule_update_log_path, capsule_on_disk_log_path, capsule_test_results_log_path):
    test_suite_key = "capsule_update"
    mapping = {
        "Test_suite_name": "Capsule Update",  # same as the other standalone logs
        "Test_suite_description": "Tests for automatic capsule update",
        "Test_case_description": "Capsule Update"
    }

    suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_SKIPPED": 0,
        "total_ABORTED": 0,
        "total_WARNINGS": 0
    }

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],       # <--- 'Standalone tests'
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,                         # 'capsule_update'
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

    # The original capsule script assumed certain encodings:
    #   capsule_update.log => utf-16
    #   capsule_on_disk.log => utf-16
    #   capsule_test_results.log => utf-8
    update_lines = read_file_lines(capsule_update_log_path, encoding='utf-16')
    on_disk_lines = read_file_lines(capsule_on_disk_log_path, encoding='utf-16')
    results_lines = read_file_lines(capsule_test_results_log_path, encoding='utf-8')

    subtest_number = 1

    # Helper to add subtest
    def add_subtest(desc, status, reason=""):
        nonlocal subtest_number
        sub = create_subtest(subtest_number, desc, status, reason)
        current_test["subtests"].append(sub)
        update_suite_summary(current_test["test_suite_summary"], status)
        suite_summary[f"total_{status}"] += 1
        subtest_number += 1

    # PARSE capsule-update.log
    i = 0
    while i < len(update_lines):
        line = update_lines[i].strip()
        # e.g. "Testing unauth.bin update"
        match = re.match(r"Testing\s+(unauth\.bin|tampered\.bin)\s+update", line, re.IGNORECASE)
        if match:
            test_desc = line
            test_info = ""
            result = "FAILED"  # default
            i += 1
            while i < len(update_lines):
                cur = update_lines[i].strip()
                if re.match(r"Testing\s+", cur, re.IGNORECASE):
                    # next test
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

                    # Determine pass/fail from text
                    if "failed to update capsule" in test_info.lower():
                        # For unauth/tampered, failing to update is a PASS
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
            add_subtest(test_desc, result, reason=test_info)
        i += 1

    # PARSE capsule-on-disk.log
    i = 0
    while i < len(on_disk_lines):
        line = on_disk_lines[i].strip()
        # e.g. "Testing signed_capsule.bin OD update"
        match = re.match(r"Testing\s+signed_capsule\.bin\s+OD\s+update", line, re.IGNORECASE)
        if match:
            test_desc = line
            test_info = ""
            result = "FAILED"
            i += 1
            while i < len(on_disk_lines):
                cur = on_disk_lines[i].strip()
                if re.match(r"Testing\s+", cur, re.IGNORECASE):
                    i -= 1
                    break
                elif re.match(r"Test[_\s]Info", cur, re.IGNORECASE):
                    i += 1
                    info_lines = []
                    while i < len(on_disk_lines):
                        info_line = on_disk_lines[i].strip()
                        if re.match(r"Testing\s+", info_line, re.IGNORECASE):
                            i -= 1
                            break
                        info_lines.append(info_line)
                        i += 1
                    test_info = "\n".join(info_lines)
                    if "signed_capsule.bin not present" in test_info.lower():
                        result = "FAILED"
                    elif "succeed to write signed_capsule.bin" in test_info.lower():
                        if "uefi capsule update has failed" in test_info.lower():
                            result = "FAILED"
                        else:
                            result = "PASSED"
                    else:
                        result = "FAILED"
                    break
                else:
                    i += 1
            add_subtest(test_desc, result, reason=test_info)
        i += 1

    # PARSE capsule_test_results.log
    i = 0
    while i < len(results_lines):
        line = results_lines[i].strip()
        # e.g. "Testing signed_capsule.bin sanity" or "Testing ESRT FW version update"
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
                    # the original code interpreted warnings as PASSED
                    result = "PASSED"
                    test_info = cur
                    break
                else:
                    i += 1
            add_subtest(test_desc, result, reason=test_info)

        elif esrt_match:
            test_desc = "Testing ESRT FW version update"
            test_info = ""
            result = "FAILED"
            i += 1
            while i < len(results_lines):
                cur = results_lines[i].strip()
                if re.match(r"Testing\s+", cur, re.IGNORECASE) or re.match(r"Test:\s+", cur, re.IGNORECASE):
                    i -= 1
                    break
                elif cur.lower().startswith("info:"):
                    test_info = cur[len("INFO:"):].strip()
                    i += 1
                elif cur.lower().startswith("results:"):
                    outcome = cur[len("RESULTS:"):].strip()
                    if outcome.upper() == "PASSED":
                        result = "PASSED"
                    else:
                        result = "FAILED"
                    break
                else:
                    i += 1
            add_subtest(test_desc, result, reason=test_info)
        else:
            i += 1

    return {
        "test_results": [current_test],
        "suite_summary": suite_summary
    }

#
# DETECTION LOGIC FOR SINGLE-LOG STANDALONE vs. CAPSULE_UPDATE MODE
#
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
    # Two modes:
    # 1) Single-Log parse:   logs_to_json.py <log> <output_json>
    # 2) Capsule update:     logs_to_json.py capsule_update <capsule_update_log> <capsule_on_disk_log> <capsule_test_results_log> <output_json>
    #
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

    elif len(args) == 5 and args[0].lower() == "capsule_update":
        # Capsule update usage
        # logs_to_json.py capsule_update <update_log> <on_disk_log> <test_results_log> <output_json>
        _, update_log, on_disk_log, test_results_log, output_json = args
        result = parse_capsule_update_logs(update_log, on_disk_log, test_results_log)
        with open(output_json, 'w') as out:
            json.dump(result, out, indent=4)
        sys.exit(0)
    else:
        print("Usage:")
        print("  1) Single log:      python3 logs_to_json.py <path_to_log> <output_JSON>")
        print("  2) Capsule update:  python3 logs_to_json.py capsule_update <update_log> <on_disk_log> <test_results_log> <output_JSON>")
        sys.exit(1)
