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

import json
import argparse
import re
import chardet
import os

def normalize_result(r):
    r = r.strip().upper()
    # Map single-word states to full past tense
    if r == "PASS":
        return "PASSED"
    if r == "FAIL":
        return "FAILED"
    # Normalize SKIP to SKIPPED while preserving SKIPPED
    if r == "SKIP":
        return "SKIPPED"
    return r

# JSON mapping of Test Suites, Sub Test Suites, and Test Cases
test_mapping = {
    "GenericTest": {
        "EFICompliantTest": [
            "PlatformSpecificElements",
            "RequiredElements"
        ],
        "SbbrEfiSpecVerLvl": [
            "TestEfiSpecVerLvl"
        ],
        "SbbrSysEnvConfig": [
            "BootExcLevel"
        ]
    },
    "BootServicesTest": {
        "EventTimerandPriorityServicesTest": [
            "CheckEvent_Conf",
            "CheckEvent_Func",
            "CloseEvent_Func",
            "CreateEventEx_Conf",
            "CreateEventEx_Func",
            "CreateEvent_Conf",
            "CreateEvent_Func",
            "RaiseTPL_Func",
            "RestoreTPL_Func",
            "SetTimer_Conf",
            "SetTimer_Func",
            "SignalEvent_Func",
            "WaitForEvent_Conf",
            "WaitForEvent_Func"
        ],
        "MemoryAllocationServicesTest": [
            "AllocatePages_Conf",
            "AllocatePages_Func",
            "AllocatePool_Conf",
            "AllocatePool_Func",
            "FreePages_Conf",
            "FreePages_Func",
            "GetMemoryMap_Conf",
            "GetMemoryMap_Func"
        ],
        "ProtocolHandlerServicesTest": [
            "CloseProtocol_Conf",
            "CloseProtocol_Func",
            "ConnectController_Conf",
            "ConnectController_Func",
            "DisconnectController_Conf",
            "DisconnectController_Func",
            "HandleProtocol_Conf",
            "HandleProtocol_Func",
            "InstallMultipleProtocolInterfaces_Conf",
            "InstallMultipleProtocolInterfaces_Func",
            "InstallProtocolInterface_Conf",
            "InstallProtocolInterface_Func",
            "LocateDevicePath_Conf",
            "LocateDevicePath_Func",
            "LocateHandleBuffer_Conf",
            "LocateHandleBuffer_Func",
            "LocateHandle_Conf",
            "LocateHandle_Func",
            "LocateProtocol_Conf",
            "LocateProtocol_Func",
            "OpenProtocolInformation_Conf",
            "OpenProtocolInformation_Func",
            "OpenProtocol_Conf",
            "OpenProtocol_Func_1",
            "OpenProtocol_Func_2",
            "OpenProtocol_Func_3",
            "ProtocolsPerHandle_Conf",
            "ProtocolsPerHandle_Func",
            "RegisterProtocolNotify_Conf",
            "RegisterProtocolNotify_Func",
            "ReinstallProtocolInterface_Conf",
            "ReinstallProtocolInterface_Func",
            "UninstallMultipleProtocolInterfaces_Conf",
            "UninstallMultipleProtocolInterfaces_Func",
            "UninstallProtocolInterface_Conf",
            "UninstallProtocolInterface_Func"
        ],
        "ImageServicesTest": [
            "ExitBootServices_Conf",
            "Exit_Conf",
            "Exit_Func",
            "LoadImage_Conf",
            "LoadImage_Func",
            "StartImage_Conf",
            "StartImage_Func",
            "UnloadImage_Conf",
            "UnloadImage_Func"
        ],
        "MiscBootServicesTest": [
            "CalculateCrc32_Conf",
            "CalculateCrc32_Func",
            "CopyMem_Func",
            "GetNextMonotonicCount_Conf",
            "GetNextMonotonicCount_Func",
            "InstallConfigurationTable_Conf",
            "InstallConfigurationTable_Func",
            "SetMem_Func",
            "SetWatchdogTimer_Conf",
            "SetWatchdogTimer_Func",
            "Stall_Func"
        ]
    },
    "RuntimeServicesTest": {
        "VariableServicesTest": [
            "GetNextVariableName_Conf",
            "GetNextVariableName_Func",
            "GetVariable_Conf",
            "GetVariable_Func",
            "HardwareErrorRecord_Conf",
            "HardwareErrorRecord_Func",
            "QueryVariableInfo_Conf",
            "QueryVariableInfo_Func",
            "SetVariable_Conf",
            "SetVariable_Func",
            "AuthVar_Conf",
            "AuthVar_Func"
        ],
        "TimeServicesTest": [
            "GetTime_Conf",
            "GetTime_Func",
            "GetWakeupTime_Conf",
            "GetWakeupTime_Func",
            "SetTime_Conf",
            "SetTime_Func",
            "SetWakeupTime_Conf",
            "SetWakeupTime_Func"
        ],
        "MiscRuntimeServicesTest": [
            "QueryCapsuleCapabilities_Conf",
            "QueryCapsuleCapabilities_Func",
            "UpdateCapsule_Conf"
        ],
        "SBBRRuntimeServicesTest": [
            "Non-volatile Variable Reset Test",
            "Runtime Services Test"
        ],
        "SecureBootTest": [
            "ImageLoading",
            "VariableAttributes",
            "VariableUpdates"
        ],
        "BBSRVariableSizeTest": [
            "BBSRVariableSizeTest_func"
        ],
        "TCGMemoryOverwriteRequestTest": [
            "Test MOR and MORLOCK"
        ]
    },
    "TCG2ProtocolTest": {
        "GetActivePcrBanks_Conf": [
            "GetActivePcrBanks_Conf"
        ],
        "GetCapability_Conf": [
            "GetCapability_Conf"
        ],
        "HashLogExtendEvent_Conf": [
            "HashLogExtendEvent_Conf"
        ],
        "SubmitCommand_Conf": [
            "SubmitCommand_Conf"
        ]
    },
    "PlatformResetAttackMitigationPsciTest": {
        "PlatformResetAttackMitigationPsciTest_func": [
            "PlatformResetAttackMitigationPsciTest_func"
        ]
    },
    "LoadedImageProtocolTest": {
        "LoadedImageProtocolTest1": [
            "LoadedImageProtocolTest1"
        ],
        "LoadedImageProtocolTest2": [
            "LoadedImageProtocolTest2"
        ]
    },
    "DevicePathProcotols": {
        "DevicePathProcotolTest": [
            "PathNode_Conf"
        ],
        "DevicePathUtilitiesProcotolTest": [
            "AppendDeviceNode_Conformance",
            "AppendDeviceNode_Functionality",
            "AppendDevicePathInstance_Conformance",
            "AppendDevicePathInstance_Functionality",
            "AppendDevicePath_Conformance",
            "AppendDevicePath_Functionality",
            "CreatDeviceNode_Functionality",
            "CreateDeviceNode_Conformance",
            "DuplicateDevicePath_Conformance",
            "DuplicateDevicePath_Functionality",
            "GetDevicePathSize_Conformance",
            "GetDevicePathSize_Functionality",
            "GetNextDevicePathInstance_Conformance",
            "GetNextDevicePathInstance_Functionality",
            "IsDevicePathMultiInstance_Functionality"
        ]
    },
    "HIITest": {
        "HIIDatabaseProtocolTest": [
            "ExportPackageListsConformance",
            "ExportPackageListsFunction",
            "FindKeyboardLayoutsConformance",
            "FindKeyboardLayoutsFunction",
            "GetKeyboardLayoutConformance",
            "GetKeyboardLayoutFunction",
            "GetPackageListHandleConformance",
            "GetPackageListHandleFunction",
            "ListPackageListsConformance",
            "ListPackageListsFunction",
            "NewPackageListConformance",
            "NewPackageListFunction",
            "RegisterPackageNotifyConformance",
            "RemovePackageListConformance",
            "RemovePackageListFunction",
            "SetKeyboardLayoutConformance",
            "SetKeyboardLayoutFunction",
            "UnregisterPackageNotifyConformance",
            "UpdatePackageListConformance",
            "UpdatePackageListFunction"
        ]
    },
    "NetworkSupportTest": {
        "SimpleNetworkProtocolTest": [
            "GetStatus_Conf",
            "GetStatus_Func",
            "Initialize_Conf",
            "Initialize_Func",
            "MCastIpToMac_Conf",
            "MCastIpToMac_Func",
            "Receive_Conf",
            "Reset_Conf",
            "Reset_Func",
            "Shutdown_Conf",
            "Shutdown_Func",
            "Start_Conf",
            "Start_Func",
            "Stop_Conf",
            "Stop_Func",
            "Transmit_Conf"
        ]
    },
    "SecureTechTest": {
        "RNGProtocolTest": [
            "GetInfo_Conf",
            "GetInfo_Func",
            "GetRNG_Conf",
            "GetRNG_Func"
        ]
    },
    "ConsoleSupportTest": {
        "SimpleTextInputExProtocolTest": [
            "ReadKeyStrokeExConformance",
            "ReadKeyStrokeExFunctionAuto",
            "RegisterKeyNotifyConformance",
            "ResetFunctionAuto",
            "SetStateConformance",
            "UnregisterKeyNotifyConformance"
        ],
        "SimpleInputProtocolTest": [
            "Reset_Func"
        ],
        "SimpleOutputProtocolTest": [
            "ClearScreen_Func",
            "EnableCursor_Func",
            "OutputString_Func",
            "QueryMode_Conf",
            "QueryMode_Func",
            "Reset_Func",
            "SetAttribute_Func",
            "SetCursorPosition_Conf",
            "SetCursorPosition_Func",
            "SetMode_Conf",
            "SetMode_Func",
            "TestString_Func"
        ]
    }
}

def detect_file_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def clean_test_description(description):
    if description.startswith("/"):
        cleaned_desc = re.split(r"[,.]", description)[-1].strip()
        return cleaned_desc
    return description

def find_test_suite_and_subsuite(test_case_name):
    for test_suite, sub_suites in test_mapping.items():
        for sub_suite, test_cases in sub_suites.items():
            if test_case_name in test_cases:
                return test_suite, sub_suite
    return None, None

def main(input_file, output_file):
    file_encoding = detect_file_encoding(input_file)
    results = []
    test_entry = None
    sub_test_number = 0
    capture_description = False

    # We'll fill "suite_summary" after final classification
    suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_failed_with_waiver": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0,
        # NEW - Not used until final classification,
        # but we show how to handle if we want total_ignored here
        # We won't add it unless specifically needed
    }

    with open(input_file, "r", encoding=file_encoding, errors="ignore") as file:
        lines = file.readlines()

        for i, line in enumerate(lines):
            line = line.strip()

            if re.match(r'^\s*Device\s*Path\s*:', line, re.IGNORECASE):
                dp_value = line.split(':', 1)[1].strip()
                if test_entry is not None:
                    test_entry["Device Path"] = dp_value
                continue

            # Start of a new test entry
            if "BBR ACS" in line:
                if test_entry:
                    results.append(test_entry)
                test_entry = {
                    "Test_suite": "",
                    "Sub_test_suite": "",
                    "Test_case": "",
                    "Test_case_description": "",
                    "Test Entry Point GUID": "",
                    "Returned Status Code": "",
                    "subtests": [],
                    "test_case_summary": {
                        "total_passed": 0,
                        "total_failed": 0,
                        "total_failed_with_waiver": 0,
                        "total_aborted": 0,
                        "total_skipped": 0,
                        "total_warnings": 0,
                        "total_ignored": 0  # <--- NEW field in each test
                    }
                }
                # Next line is the test name
                if i + 1 < len(lines):
                    test_entry["Test_case"] = lines[i+1].strip()

                sub_test_number = 0
                # Attempt to find the test suite/subsuite
                test_suite, sub_test_suite = find_test_suite_and_subsuite(test_entry["Test_case"])
                test_entry["Test_suite"] = test_suite if test_suite else "Unknown"
                test_entry["Sub_test_suite"] = sub_test_suite if sub_test_suite else "Unknown"

            if "Test Configuration #0" in line:
                capture_description = True
                continue

            if capture_description and line and not re.match(r'-+', line):
                test_entry["Test_case_description"] = line
                capture_description = False

            if "Test Entry Point GUID" in line:
                test_entry["Test Entry Point GUID"] = line.split(':', 1)[1].strip()

            if "Returned Status Code" in line:
                test_entry["Returned Status Code"] = line.split(':', 1)[1].strip()
                # Attempt to parse next lines for "XYZ: [RESULT]"
                j = i + 1
                while j < len(lines):
                    candidate = lines[j].strip()
                    j += 1
                    if not candidate:
                        continue
                    m = re.search(r'^([^:]+):\s*\[(.*?)\]', candidate)
                    if m:
                        test_entry["test_result"] = normalize_result(m.group(2))
                        test_entry["reason"] = ""
                    break

            # Sub-test detection from lines like "FooTest -- PASS"
            if re.search(r'--\s*(PASS|FAIL|FAILURE|WARNING|NOT SUPPORTED)', line, re.IGNORECASE):
                parts = line.rsplit(' -- ', 1)
                test_desc = clean_test_description(parts[0])
                result_str = normalize_result(parts[1])

                # Tally in test_case_summary *before* overrides
                if "PASS" in result_str:
                    test_entry["test_case_summary"]["total_passed"] += 1
                elif "FAIL" in result_str:
                    test_entry["test_case_summary"]["total_failed"] += 1
                elif "ABORTED" in result_str:
                    test_entry["test_case_summary"]["total_aborted"] += 1
                elif "SKIPPED" in result_str:
                    test_entry["test_case_summary"]["total_skipped"] += 1
                elif "WARNING" in result_str:
                    test_entry["test_case_summary"]["total_warnings"] += 1
                # "NOT SUPPORTED" etc. is not specially counted, you can add if needed.

                test_guid = lines[i+1].strip() if i+1 < len(lines) else ""
                file_path = lines[i+2].strip() if i+2 < len(lines) else ""

                sub_test_number += 1

                reason = ""
                if ":" in file_path:
                    reason_split = file_path.rsplit(":", 1)
                    if len(reason_split) > 1:
                        reason = reason_split[1].strip()

                sub_test = {
                    "sub_Test_Number": str(sub_test_number),
                    "sub_Test_Description": test_desc,
                    "sub_Test_GUID": test_guid,
                    "sub_test_result": result_str,
                    "sub_Test_Path": file_path,
                    "reason": reason
                }
                test_entry["subtests"].append(sub_test)

        # End of loop: add last test entry
        if test_entry:
            results.append(test_entry)

    # Merge with edk2_test_parser.json if present
    edk2_file = os.path.join(os.path.dirname(output_file), "edk2_test_parser.json")
    if os.path.exists(edk2_file):
        with open(edk2_file, "r", encoding="utf-8") as f:
            edk2_data = json.load(f)

        subtest_dict = {}
        test_guid_dict = {}
        for item in edk2_data:
            ep_guid = item.get("Test Entry Point GUID", "").strip()
            sub_guid = item.get("sub_Test_GUID", "").strip()
            result_val = item.get("result", "")
            reason_val = item.get("reason", "")

            if ep_guid and sub_guid:
                subtest_dict[(ep_guid.upper(), sub_guid.upper())] = {
                    "result": result_val,
                    "reason": reason_val
                }
            elif ep_guid and not sub_guid:
                test_guid_dict[ep_guid.upper()] = {
                    "result": result_val,
                    "reason": reason_val
                }

        # Apply overrides
        for test_obj in results:
            ep_guid_current = test_obj["Test Entry Point GUID"].upper()
            if ep_guid_current in test_guid_dict:
                test_obj["test_result"] = normalize_result(test_guid_dict[ep_guid_current]["result"])
                test_obj["reason"] = test_guid_dict[ep_guid_current]["reason"]

            for subtest in test_obj["subtests"]:
                st_guid = subtest["sub_Test_GUID"].upper()
                if (ep_guid_current, st_guid) in subtest_dict:
                    match_record = subtest_dict[(ep_guid_current, st_guid)]
                    subtest["sub_test_result"] = normalize_result(match_record["result"])
                    subtest["reason"] = match_record["reason"]

    # Reorder final dictionary so "test_result" & "reason" appear after "Returned Status Code"
    for i, test_obj in enumerate(results):
        reordered = {
            "Test_suite": test_obj["Test_suite"],
            "Sub_test_suite": test_obj["Sub_test_suite"],
            "Test_case": test_obj["Test_case"],
            "Test_case_description": test_obj["Test_case_description"],
            "Test Entry Point GUID": test_obj["Test Entry Point GUID"],
            "Returned Status Code": test_obj["Returned Status Code"]
        }
        if "Device Path" in test_obj:
            reordered["Device Path"] = test_obj["Device Path"]

        if "test_result" in test_obj:
            reordered["test_result"] = test_obj["test_result"]
        if "reason" in test_obj:
            reordered["reason"] = test_obj["reason"]

        reordered["subtests"] = test_obj["subtests"]
        reordered["test_case_summary"] = test_obj["test_case_summary"]
        results[i] = reordered

    # Final step: re-tally subtests so the final results reflect overrides
    for test_obj in results:
        tcsum = test_obj["test_case_summary"]
        # Reset them all to 0, including new "total_ignored"
        tcsum["total_passed"] = 0
        tcsum["total_failed"] = 0
        tcsum["total_failed_with_waiver"] = 0
        tcsum["total_aborted"] = 0
        tcsum["total_skipped"] = 0
        tcsum["total_warnings"] = 0
        tcsum["total_ignored"] = 0  # <--- NEW category for all overrides

        for subtest in test_obj["subtests"]:
            final_result = subtest["sub_test_result"].upper()
            # Classify final_result
            if "PASS" in final_result:
                tcsum["total_passed"] += 1
            elif "FAIL" in final_result:
                tcsum["total_failed"] += 1
            elif "ABORTED" in final_result:
                tcsum["total_aborted"] += 1
            elif "SKIPPED" in final_result:
                tcsum["total_skipped"] += 1
            elif "WARNING" in final_result:
                tcsum["total_warnings"] += 1
            else:
                # ANY other override (IGNORED, KNOWN U-BOOT LIMITATION, etc)
                tcsum["total_ignored"] += 1

    # Sum them all into suite_summary
    final_suite_summary = {
        "total_passed": 0,
        "total_failed": 0,
        "total_failed_with_waiver": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0,
        "total_ignored": 0  # <--- match the new field
    }
    for test_obj in results:
        tcsum = test_obj["test_case_summary"]
        final_suite_summary["total_passed"] += tcsum["total_passed"]
        final_suite_summary["total_failed"] += tcsum["total_failed"]
        final_suite_summary["total_failed_with_waiver"] += tcsum["total_failed_with_waiver"]
        final_suite_summary["total_aborted"] += tcsum["total_aborted"]
        final_suite_summary["total_skipped"] += tcsum["total_skipped"]
        final_suite_summary["total_warnings"] += tcsum["total_warnings"]
        final_suite_summary["total_ignored"] += tcsum["total_ignored"]

    output_data = {
        "test_results": results,
        "suite_summary": final_suite_summary
    }

    with open(output_file, 'w') as json_file:
        json.dump(output_data, json_file, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse an SCT Log file and save results to a JSON file.")
    parser.add_argument("input_file", help="Input Log file")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()
    main(args.input_file, args.output_file)
