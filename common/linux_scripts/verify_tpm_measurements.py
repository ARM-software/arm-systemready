#!/usr/bin/env python3
#
# Copyright (c) 2023-2025, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import yaml
import re

# TPM log review checklist
tpmlog_checklist = \
  ["Verify that the cumulative SHA256 measurements from the event log match the TPM PCRs 0-7",
   "Verify the first event is the EV_NO_ACTION for the Specification ID version",
   "Verify EV_POST_CODE events for measurements of firmware to PCR[0] with recommended strings",
   "Verify EV_POST_CODE events for measurements of signed critical data to PCR[0].",
   "Verify secure boot policy measurements are made into PCR[7] with "
   "EV_EFI_VARIABLE_DRIVER_CONFIG",
   "Verify BootOrder and Boot#### variables are measured in PCR[1] with"
   "EV_EFI_VARIABLE_BOOT/EV_EFI_VARIABLE_BOOT2",
   "Verify boot attempts measured in PCR[4] with EV_EFI_ACTION event type",
   "Verify security relevant configuration data are measured in into PCR[1] with "
   "EV_EFI_HANDOFF_TABLES",
   "Verify presence of EV_SEPARATOR event for each PCR",
   "Verify EV_TABLE_OF_DEVICES events for measurements of config data to PCR[1] with "
   "recommended strings",
   "Verify presence of “Exit Boot Services Invocation” event with EV_EFI_ACTION type"
   ]
max_width = max(len(item) for item in tpmlog_checklist)
print_buffer = []

def print_buffer_call():
    # print the buffer for debug/info prints
    if print_buffer:
        for message in print_buffer:
            print(4 * " " + message)
    print_buffer.clear()

def TestResult(test_idx, test_result):
    print(f"{tpmlog_checklist[test_idx - 1].ljust(max_width)} : {test_result}")
    print_buffer_call()

def compare_measurements(pcr_log_path, event_log_path):
    try:
        with open(pcr_log_path, 'r') as pcr_log, open(event_log_path, 'r') as event_log:
            pcr_data = yaml.safe_load(pcr_log)
            eventlog_data = yaml.safe_load(event_log)
    except Exception as e:
        print_buffer.append(f"ERROR: {e}")
        TestResult(1, "FAIL")
        exit(1)

    # check if event log and TPM PCR log as expected data
    if not 'pcrs' in eventlog_data:
        print_buffer.append("Event log doesn't contain PCR data.")
        TestResult(1, "FAIL")
        return
    if not pcr_data:
        print_buffer.append("TPM PCR log is empty.")
        TestResult(1, "FAIL")
        return

    # compare pcr values
    sha_algos = ['sha256', 'sha384', 'sha512']
    match_count = 0
    status = "FAIL"
    for sha in sha_algos:
        for i in range(8):
            if sha in eventlog_data['pcrs'] and \
               sha in pcr_data:
                if eventlog_data['pcrs'][sha][i] == \
                pcr_data[sha][i]:
                    match_count = match_count + 1
                else:
                    status = "FAIL"
                    print_buffer.append(f"PCR[{i}] measurements does not match for {sha}")
                    print_buffer.append(f"TPM      PCR[{i}] : {pcr_data[sha][i]}")
                    print_buffer.append(f"Eventlog PCR[{i}] : {eventlog_data['pcrs'][sha][i]}")

    # check if at least pcrs matched for one sha algorithm
    if match_count%8  == 0:
        status = "PASS"
    TestResult(1, status)

def parse_eventlog_data(event_log_path):
    try:
        with open(event_log_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
            events = []
            for event in yaml_data['events']:
                # parse common fields
                event_details = {
                    'event_num': event['EventNum'],
                    'pcr_index': event['PCRIndex'],
                    'event_type': event['EventType'],
                }
                # parse event specific data if available
                if 'Event' in event:
                    event_details['event_data'] = event['Event']
                elif 'SpecID' in event:
                    event_details['spec_id'] = str(event['SpecID'][0]['specVersionMajor']) \
                    + '.' + str(event['SpecID'][0]['specVersionMajor'])
                events.append(event_details)
            return events
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse YAML: {e}")
        exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)

def check_events(event_list):
    try:
        # Verify the EV_NO_ACTION event for Specification ID version.
        # the first event in the log must be the Specification ID version.
        if(event_list[0]['event_type'] == 'EV_NO_ACTION') and \
        'spec_id' in event_list[0]:
            TestResult(2, "PASS")
        else:
            TestResult(2, "FAIL")


        # Verify EV_POST_CODE events for measurements of firmware to PCR[0] with recommended string
        # in event data as per BBSR.

        # Recommended strings for the event data that are used for
        # Secure world firmware components
        sec_wd_patterns = [
            r"SYS_CTRL_[0-9]+",
            r"BL_[0-9]+",
            r"SECURE_RT_EL0_[a-zA-Z0-9]+",
            "SECURE_RT_EL1",
            "SECURE_RT_EL2",
            "SECURE_RT_EL3"
        ]
        match_found = False
        # will be set to FAIL if non-compliance
        status = "PASS"
        count = 0
        for event in event_list:
            if event['event_type'] == "EV_POST_CODE" \
                and event['pcr_index'] == 0:
                count = count + 1
                # check if event data matches recommended string
                for pattern in sec_wd_patterns:
                    if isinstance(event['event_data'], (str, bytes)) and \
                                                           re.match(pattern, event['event_data']):
                       match_found = True
                       break
                if not match_found :
                    print_buffer.append(f"Event {event['event_num']:2} data doesn't comply " + \
                                        "with recommended string")
                    status = "WARN"
                # reset flag for next iteration
                match_found = False
        if count == 0:
            print_buffer.append(f"Event of type EV_POST_CODE measured into PCR[0] not found")
            TestResult(3, "FAIL")
        elif status == "WARN":
            # all events of type EV_POST_CODE has event string as recommended.
            TestResult(3, "WARN")
        else:
            TestResult(3, "PASS")

        # Verify EV_POST_CODE events for measurements of signed critical to data PCR[0].
        match_found = False
        status = "FAIL"
        for event in event_list:
            if event['event_type'] == "EV_POST_CODE":
                if event['pcr_index'] == 0:
                    status = "PASS"
                    match_found = True
                else:
                    print_buffer.append(f"Event {event['event_num']:2} has type EV_POST_CODE but" + \
                                        " not measured into PCR[0]")
                    status = "FAIL"
        if not match_found:
            print_buffer.append("Event of type EV_POST_CODE not found")
        TestResult(4, status)

        # Verify Secure Boot policy measurements (SecureBoot, PK, KEK, db and dbX) are measured
        # into PCR[7] using EV_EFI_VARIABLE_DRIVER_CONFIG event type
        secure_boot_varlist = ['SecureBoot', 'PK', 'KEK', 'db', 'dbx']
        for event in event_list:
            if(event['event_type'] == "EV_EFI_VARIABLE_DRIVER_CONFIG"):
                if 'UnicodeName' in event['event_data'] :
                    if event['event_data']['UnicodeName'] in secure_boot_varlist:
                        secure_boot_varlist.remove(event['event_data']['UnicodeName'])
                        if event['pcr_index'] != 7:
                            status = "FAIL"
        if secure_boot_varlist:
            print_buffer.append(f"Following secure boot policy measurements not found" + \
                                f": {secure_boot_varlist}")
            status = "FAIL"
        else:
            status = "PASS"
        TestResult(5, status)

        # Verify BootOrder and Boot#### variables are measured in PCR[1]
        # with EV_EFI_VARIABLE_BOOT/EV_EFI_VARIABLE_BOOT2
        match_found = False
        status = "FAIL"
        for event in event_list:
            if event['event_type'] in ("EV_EFI_VARIABLE_BOOT", "EV_EFI_VARIABLE_BOOT2"):
                if 'UnicodeName' in event['event_data'] :
                    if event['event_data']['UnicodeName'] == \
                    "BootOrder" or re.match(r"Boot\d{4}$", event['event_data']['UnicodeName']):
                        if event['pcr_index'] != 1:
                            print_buffer.append(f"{event['event_data']['UnicodeName']}" + \
                                                f"is measured into PCR[{event['pcr_index']}]," + \
                                                f" expected PCR[1]")
                            status = "FAIL"
                        if event['pcr_index'] == 1:
                            match_found = True
                            status = "PASS"

        if not match_found:
            print_buffer.append("BootOrder/Boot#### variable measurements not found")
            status = "FAIL"
        TestResult(6, status)

        # Verify boot attempt measurements into PCR[4] with event type EV_EFI_ACTION
        # and action string "Calling EFI Application from Boot Option"
        status = "FAIL"
        match_found = False
        for event in event_list:
            if event['event_type'] == "EV_EFI_ACTION" and \
            event['event_data'] == "Calling EFI Application from Boot Option":
                match_found = True
                if event['pcr_index'] != 4:
                    print_buffer.append("Boot attempt not measured into PCR[4]" + \
                                        f" instead into PCR[{event['pcr_index']}]")
                    status = "FAIL"
                else:
                    status = "PASS"
        if not match_found:
            print_buffer.append("Boot attempt measurements not found")
            status = "FAIL"
        TestResult(7, status)

        # Verify PCR[1] measurements of security relevant configuration data go into PCR[1].
        # data such as the security lifecycle state of a system, security relevant SMBIOS
        # structures must be measured into PCR[1] using event type EV_EFI_HANDOFF_TABLES,
        # this should include structures that identify the platform hardware for example
        # manufacturer, model number, version, and so on.
        match_found = False
        status = "FAIL"
        for event in event_list:
            if event['event_type'] == "EV_EFI_HANDOFF_TABLES":
                match_found = True
                if event['pcr_index'] == 1:
                    status = "PASS"
                else:
                    print_buffer.append(f"Event {event['event_num']:2} has type " + \
                                        "EV_EFI_HANDOFF_TABLES but not measured into PCR[1]")
                    status = "FAIL"
        if not match_found:
            print_buffer.append("Event of type EV_EFI_HANDOFF_TABLES not found")
        TestResult(8, status)

        # Verify EV_SEPARATOR measurements the EV_SEPARATOR event delineates the point in
        # platform boot where the platform firmware relinquishes control of making measurements
        # into the TPM. There must be an EV_SEPARATOR measurement for each PCR[0] through PCR[7].
        pcrs = list(range(8))
        for event in event_list:
            if event['event_type'] == "EV_SEPARATOR" and \
            event['pcr_index'] in pcrs:
                pcrs.remove(event['pcr_index'])
        if pcrs:
            print_buffer(f"EV_SEPARATOR event not found for pcrs {pcrs}")
            status = "FAIL"
        else:
            status = "PASS"

        TestResult(9, status)

        # For measurements of configuration data made by auxiliary controllers or Secure world
        # firmware to PCR[1], the event type used should be EV_TABLE_OF_DEVICES. with recommended
        # string in event data

        # Recommended strings for the event data measurements made by auxiliary controllers
        # or Secure world firmware
        sec_wd_aux_patterns = [
            r"SYS_CONFIG_[a-zA-Z0-9]+",
            r"BL_[0-9]+_CONFIG_[a-zA-Z0-9]+",
            r"SECURE_CONFIG_EL0_[a-zA-Z0-9]+",
            r"SECURE_CONFIG_EL1_[a-zA-Z0-9]+",
            r"SECURE_CONFIG_EL2_[a-zA-Z0-9]+",
            r"SECURE_CONFIG_EL3_[a-zA-Z0-9]+"
        ]
        match_found = False
        # will be set to FAIL if non-compliance
        status = "PASS"
        count = 0
        for event in event_list:
            if event['event_type'] == "EV_TABLE_OF_DEVICES":
                if not event['pcr_index'] == 1:
                    print_buffer.append(f"Event {event['event_num']:2} of type " + \
                                         "EV_TABLE_OF_DEVICES not measured into PCR[1]")
                    status = "FAIL"
                else:
                    count = count + 1
                    # check if event data matches recommended string
                    for pattern in sec_wd_aux_patterns:
                        if re.match(pattern, event['event_data']):
                            match_found = True
                            break
                    if not match_found :
                        print_buffer.append(f"Event {event['event_num']:2} data doesn't " + \
                                             "comply with recommended string")
                        status = "WARN"
                    # reset flag for next iteration
                    match_found = False
        if count == 0:
            print_buffer.append("Event of type EV_TABLE_OF_DEVICES measured into PCR[1] not found")
            TestResult(10, "FAIL")
        elif status == "WARN":
            # all events of type EV_TABLE_OF_DEVICES has event string as recommended.
            TestResult(10, "WARN")
        else:
            TestResult(10, "PASS")

        # If ExitBootServices() is invoked, then an EV_EFI_ACTION event
        # “Exit Boot Services Invocation” must be measured.
        status = "FAIL"
        for event in event_list:
            if event['event_type'] == "EV_EFI_ACTION" and \
            event['event_data'] == "Exit Boot Services Invocation":
                match_found = True
                status = "PASS"
        if status == "FAIL":
            print_buffer.append("“Exit Boot Services Invocation” event with type EV_EFI_ACTION" + \
                                " not found")
        TestResult(11, status)


    except Exception as e:
        print_buffer.append(f"ERROR: {e}")
        print_buffer_call()
        exit(1)

if __name__ == "__main__":
    # check if log files are passed to script
    if len(sys.argv) != 3:
        print("Usage: python3 verify_tpm_measurements.py"
              " <path to pcr.log> <path to eventlog.log>")
        exit(1)

    try:
        # parse command line for file
        pcr_log_path  = sys.argv[1]
        eventlog_path = sys.argv[2]

        # Verify that the cumulative SHA256 measurements from the event log match the TPM PCRs 0-7.
        # The events logged in the TPM event log must match the actual measurements extended
        # in the TPM PCRs.
        compare_measurements(pcr_log_path, eventlog_path)

        # parse eventlog and store for further processing
        events = parse_eventlog_data(eventlog_path)
        check_events(events)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
