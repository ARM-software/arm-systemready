# Copyright (c) 2023, Arm Limited or its affiliates. All rights reserved.
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

# This script will compare TPM logs i.e eventlog vs pcrlog

import sys
file_list = sys.argv

def get_line_number(word1):
    '''this method will return the line number of the string passed as argument '''
    line_number_list = []
    with open(file_list[1], 'r') as fp:
        # read all lines in a list 
        lines_eventlog = fp.readlines()
        for line in lines_eventlog:
            # check if string present on a current line
            if line.find(word1) != -1:
                line_number_list.append(lines_eventlog.index(line))
        global last_line_eventlog
        last_line_eventlog = len(lines_eventlog)

    with open(file_list[2], 'r') as fp1:
        # read all lines in a list
        lines_pcr = fp1.readlines()
        for line in lines_pcr:
            # check if string present on a current line
            if line.find(word1) != -1:
                line_number_list.append(lines_pcr.index(line))

        global last_line_pcr
        last_line_pcr = len(lines_pcr)
    return line_number_list



def get_number_of_entries():
    '''this method will return the number of entries in eventlog after sha256:'''
    sha256_n = get_line_number("sha256:")
    sha384_n = get_line_number("sha384:")
    sha256_to_sha384 = sha384_n[0] - sha256_n[0]  - 1
    return sha256_to_sha384



def compare():
    '''this method will compare sha256 of event and pcr log'''
    _256_line = get_line_number("sha256:")
    _384_line = get_line_number("sha384:")
    iterations = get_number_of_entries()
    with open(file_list[1], 'r') as fp ,open(file_list[2], 'r') as fp1:
        read_eventlog = fp.readlines()
        read_pcr = fp1.readlines()
        flag = 0    # Set flag on error.

        for x in range(iterations):
            ev = _256_line[0]  + x + 1
            event_data = read_eventlog[ev]
            pcr = _256_line[1]  + x + 1
            pcr_data = read_pcr[pcr]
            if remove(event_data.lower()) != remove(pcr_data.lower()):
                print("Following PCR register values are not agreeing with event log : ")
                print("PCR reg value: ")
                print(remove(event_data.lower()))
                print("Event log PCR value: ")
                print(remove(pcr_data.lower()))
                flag = 1

        if flag == 1 :
            print("FAILURE: TPM measurements not matching with event log.")
        else:
            print("SUCCESS: TPM measurements are matching with event log.")



def remove(string):
    return string.replace(" ", "") 

compare()
