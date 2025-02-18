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
    }
}

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
    if status in ["PASSED", "FAILED", "SKIPPED", "ABORTED", "WARNINGS"]:
        key = f"total_{status}"
        suite_summary[key] += 1

def parse_dt_kselftest_log(log_data):
    results = []
    test_suite_key = "dt_kselftest"
    if test_suite_key not in test_suite_mapping:
        raise ValueError(f"No mapping found for test case '{test_suite_key}'")
    
    mapping = test_suite_mapping[test_suite_key]
    
    test_suite_summary = {
        "total_PASSED": 0,
        "total_FAILED": 0,
        "total_SKIPPED": 0,
        "total_ABORTED": 0,
        "total_WARNINGS": 0
    }
    suite_summary = test_suite_summary.copy()

    current_test = {
        "Test_suite_name": mapping["Test_suite_name"],
        "Test_suite_description": mapping["Test_suite_description"],
        "Test_case": test_suite_key,
        "Test_case_description": mapping["Test_case_description"],
        "subtests": [],
        "test_suite_summary": test_suite_summary.copy()
    }

    for line in log_data:
        line = line.strip()
        # Parse subtest results
        subtest_match = re.match(r'# (ok|not ok) (\d+) (.+)', line)
        if subtest_match:
            status_str = subtest_match.group(1)
            subtest_number = subtest_match.group(2)
            description_and_status = subtest_match.group(3)

            # Check for SKIP at the end
            if '# SKIP' in description_and_status:
                status = 'SKIPPED'
                description = description_and_status.replace('# SKIP', '').strip()
            else:
                description = description_and_status.strip()
                if status_str == 'ok':
                    status = 'PASSED'
                else:
                    status = 'FAILED'

            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            # Update counts
            current_test["test_suite_summary"][f"total_{status}"] += 1
            suite_summary[f"total_{status}"] += 1
        # Parse totals line
        totals_match = re.match(r'# # Totals: pass:(\d+) fail:(\d+) xfail:\d+ xpass:\d+ skip:(\d+) error:\d+', line)
        if totals_match:
            pass  # Counts already tracked

    results.append(current_test)
    return {
        "test_results": results,
        "suite_summary": suite_summary
    }

def parse_dt_validate_log(log_data):
    results = []
    test_suite_key = "dt_validate"
    if test_suite_key not in test_suite_mapping:
        raise ValueError(f"No mapping found for test case '{test_suite_key}'")
    
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
        if re.match(r'^/.*: ', line):
            # It's an error or warning
            description = line
            status = 'FAILED'
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            current_test["test_suite_summary"]["total_FAILED"] += 1
            suite_summary["total_FAILED"] += 1
            subtest_number += 1

    results.append(current_test)
    return {
        "test_results": results,
        "suite_summary": suite_summary
    }

def parse_ethtool_test_log(log_data):
    results = []
    test_suite_key = "ethtool_test"
    if test_suite_key not in test_suite_mapping:
        raise ValueError(f"No mapping found for test case '{test_suite_key}'")
    
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

        # Detection of Ethernet Interfaces
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
                description = f"Detection of Ethernet Interfaces: {', '.join(interfaces)}"
            else:
                status = "FAILED"
                description = "No Ethernet Interfaces Detected"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1
            continue

        # Bringing Down Ethernet Interfaces
        if "INFO: Bringing down all ethernet interfaces using ifconfig" in line:
            # Assume success unless an error is found
            status = "PASSED"
            description = "Bringing down all Ethernet interfaces"
            for j in range(i + 1, len(log_data)):
                if "Unable to bring down ethernet interface" in log_data[j]:
                    status = "FAILED"
                    description = "Failed to bring down some Ethernet interfaces"
                    break
                if "****************************************************************" in log_data[j]:
                    break
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Bringing up interface
        if "INFO: Bringing up ethernet interface:" in line:
            interface = line.split(":")[-1].strip()
            # Check if the interface was brought up successfully
            if i + 1 < len(log_data) and "Unable to bring up ethernet interface" in log_data[i + 1]:
                status = "FAILED"
                description = f"Bring up interface {interface}"
            else:
                status = "PASSED"
                description = f"Bring up interface {interface}"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Running ethtool Command
        if f"INFO: Running \"ethtool {interface}\" :" in line:
            # Assume the command runs successfully
            status = "PASSED"
            description = f"Running ethtool on {interface}"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Ethernet interface self-test
        if "INFO: Ethernet interface" in line and "supports ethtool self test" in line:
            if "doesn't support ethtool self test" in line:
                status = "SKIPPED"
                description = f"Self-test on {interface} (Not supported)"
            else:
                # Check the test result
                result_index = i + 2  # Assuming result is two lines after
                if result_index < len(log_data) and "The test result is" in log_data[result_index]:
                    result_line = log_data[result_index].strip()
                    if "PASS" in result_line:
                        status = "PASSED"
                    else:
                        status = "FAILED"
                    description = f"Self-test on {interface}"
                else:
                    status = "FAILED"
                    description = f"Self-test on {interface} (Result not found)"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Link detection
        if "Link detected:" in line:
            if "yes" in line:
                status = "PASSED"
                description = f"Link detected on {interface}"
            else:
                status = "FAILED"
                description = f"Link not detected on {interface}"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # DHCP support
        if "doesn't support DHCP" in line or "supports DHCP" in line:
            if "doesn't support DHCP" in line:
                status = "FAILED"
                description = f"DHCP support on {interface}"
            else:
                status = "PASSED"
                description = f"DHCP support on {interface}"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Ping to router/gateway
        if "INFO: Ping to router/gateway" in line:
            if "is successful" in line:
                status = "PASSED"
                description = f"Ping to router/gateway on {interface}"
            else:
                status = "FAILED"
                description = f"Ping to router/gateway on {interface}"
            subtest = create_subtest(subtest_number, description, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(subtest)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        # Ping to www.arm.com
        if "INFO: Ping to www.arm.com" in line:
            if "is successful" in line:
                status = "PASSED"
                description = f"Ping to www.arm.com on {interface}"
            else:
                status = "FAILED"
                description = f"Ping to www.arm.com on {interface}"
            subtest = create_subtest(subtest_number, description, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(subtest)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

        i += 1

    # If ping tests were not found, add them as SKIPPED
    for intf in detected_interfaces:
        # Check if ping tests for this interface are present
        ping_to_router_present = any(
            subtest["sub_Test_Description"] == f"Ping to router/gateway on {intf}"
            for subtest in current_test["subtests"]
        )
        ping_to_arm_present = any(
            subtest["sub_Test_Description"] == f"Ping to www.arm.com on {intf}"
            for subtest in current_test["subtests"]
        )
        if not ping_to_router_present:
            # Ping to router/gateway
            description = f"Ping to router/gateway on {intf}"
            status = "SKIPPED"
            subtest = create_subtest(subtest_number, description, status)
            current_test["subtests"].append(subtest)
            update_suite_summary(current_test["test_suite_summary"], status)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1
        if not ping_to_arm_present:
            # Ping to www.arm.com
            description = f"Ping to www.arm.com on {intf}"
            status = "SKIPPED"
            subtest = create_subtest(subtest_number, description, status)
            update_suite_summary(current_test["test_suite_summary"], status)
            current_test["subtests"].append(subtest)
            suite_summary[f"total_{status}"] += 1
            subtest_number += 1

    results.append(current_test)
    return {
        "test_results": results,
        "suite_summary": suite_summary
    }

def parse_read_write_check_blk_devices_log(log_data):
    results = []
    test_suite_key = "read_write_check_blk_devices"
    if test_suite_key not in test_suite_mapping:
        raise ValueError(f"No mapping found for test case '{test_suite_key}'")
    
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
    devices_detected = []
    i = 0
    while i < len(log_data):
        line = log_data[i].strip()
        # Detection of block devices
        if "INFO: Detected following block devices with lsblk command :" in line:
            # Collect devices
            devices = []
            i += 1
            while i < len(log_data) and log_data[i].strip() and not log_data[i].startswith("INFO"):
                match = re.match(r'\d+:\s+(\S+)', log_data[i].strip())
                if match:
                    devices.append(match.group(1))
                i += 1
            if devices:
                devices_detected = devices
            continue
        # For each block device
        elif line.startswith("INFO: Block device :"):
            device_name = line.split(":")[-1].strip()
            i += 1
            # Check for invalid partition table
            if i < len(log_data) and "Invalid partition table or not found for" in log_data[i]:
                status = "FAILED"
                reason = log_data[i].strip()
                description = f"Partition table check on {device_name}"
                subtest = create_subtest(subtest_number, description, status, reason)
                current_test["subtests"].append(subtest)
                update_suite_summary(current_test["test_suite_summary"], status)
                suite_summary[f"total_{status}"] += 1
                subtest_number += 1
                # Skip to next device
                i += 1
                continue
            # Process partitions
            while i < len(log_data):
                line = log_data[i].strip()
                if line.startswith("INFO: Partition :"):
                    partition_line = line
                    # Extract partition name using regex
                    partition_match = re.match(r'INFO: Partition :\s+(\S+)', line)
                    if partition_match:
                        partition_name = partition_match.group(1)
                    else:
                        partition_name = "Unknown"
                    partition_status = None
                    partition_reason = ""
                    i += 1
                    if i < len(log_data):
                        next_line = log_data[i].strip()
                        if "is PRECIOUS" in next_line:
                            status = "SKIPPED"
                            reason = next_line
                            partition_status = status
                            partition_reason = reason
                            # Skip to next partition or device
                            while i < len(log_data):
                                if log_data[i].strip().startswith("INFO: Partition :") or \
                                   log_data[i].strip().startswith("INFO: Block device :") or \
                                   log_data[i].strip().startswith("****************************************************************"):
                                    break
                                i += 1
                        elif "Performing block read on" in next_line:
                            # Check for successful read
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
                            # Check for write check
                            write_status = None
                            write_reason = ""
                            if i < len(log_data) and "Do you want to perform a write check on" in log_data[i]:
                                # No write result indicates timeout/skipped
                                write_status = "SKIPPED"
                                write_reason = "Write check skipped due to timeout"
                                # Skip to next partition or device
                                while i < len(log_data):
                                    if log_data[i].strip().startswith("INFO: Partition :") or \
                                       log_data[i].strip().startswith("INFO: Block device :") or \
                                       log_data[i].strip().startswith("****************************************************************"):
                                        break
                                    i += 1
                            # Determine overall partition status
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
                            i += 1
                    # Create subtest for the partition
                    description = f"Read/Write check on Partition {partition_name}"
                    subtest = create_subtest(subtest_number, description, partition_status, partition_reason)
                    current_test["subtests"].append(subtest)
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

    results.append(current_test)
    return {
        "test_results": results,
        "suite_summary": suite_summary
    }

def parse_log(log_file_path):
    with open(log_file_path, 'r') as f:
        log_data = f.readlines()

    log_content = ''.join(log_data)

    # Adjusted detection logic with more flexible regex patterns
    if re.search(r'selftests: dt: test_unprobed_devices.sh', log_content):
        return parse_dt_kselftest_log(log_data)
    elif re.search(r'DeviceTree bindings of Linux kernel version', log_content):
        return parse_dt_validate_log(log_data)
    elif re.search(r'Running ethtool', log_content):
        return parse_ethtool_test_log(log_data)
    elif re.search(r'Read block devices tool', log_content):
        return parse_read_write_check_blk_devices_log(log_data)
    else:
        print("Detection failed. Log content:")
        print(log_content)
        raise ValueError("Unknown log type or unsupported log content.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 logs_to_json.py <path to log> <output JSON file path>")
        sys.exit(1)

    log_file_path = sys.argv[1]
    output_file_path = sys.argv[2]

    try:
        output_json = parse_log(log_file_path)
    except ValueError as ve:
        print(f"Error: {ve}")
        sys.exit(1)

    with open(output_file_path, 'w') as outfile:
        json.dump(output_json, outfile, indent=4)

   # print(f"Log parsed successfully. JSON output saved to {output_file_path}")
