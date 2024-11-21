#!/bin/sh

# @file
# Copyright (c) 2021-2024, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0

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

# This script will compare TPM logs i.e pcr.log vs event.log

import sys

def extract_sha_pcrs(filename):
    sha_pcrs = {}
    current_sha = None
    flag = False

    with open(filename, 'r') as file:
        for line in file:
            line = line.strip()

            if line.startswith("sha"):
                parts = line.split(":")
                sha_number = int(parts[0][3:])
                '''
                R200_BBSR : All measurements that are made into TPM PCRs must be made
                with a SHA-256 or stronger hashing algorithm.
                '''
                if sha_number >= 256:
                    # sha entry >= sha256 found
                    flag = True
                    current_sha = parts[0]
                    sha_pcrs[current_sha] = []
            elif current_sha and line:
                index, value = line.split(":")
                sha_pcrs[current_sha].append((index.strip(), value.strip()))

    if flag is False :
        print(f"FAILURE: Measurements not found with SHA256 or stronger hashing algorithm in {filename}")
        exit(1)

    return sha_pcrs

def compare_sha_pcrs(sha_pcrs_a, sha_pcrs_b):
    flag = False
    for sha, pcrs_a in sha_pcrs_a.items():
        # check for one hashing algorithm either SHA256 or stronger is sufficient.
        if flag is True :
            break
        if sha in sha_pcrs_b:
            pcrs_b = sha_pcrs_b[sha]
            # atleast one matching sha256 or stronger entries found
            flag = True

            # min() because eventlog only contains pcr 0-9
            for i in range(min(len(pcrs_a), len(pcrs_b))):
                index_a, value_a = pcrs_a[i]
                value_b = pcrs_b[i][1]

                # compare pcr values
                if value_a.lower() != value_b.lower():
                    print(f"Error: {sha}:pcr:{index_a} does not match.\n"
                          f"  pcr.log : {value_a.lower()}\n  eventlog: {value_b.lower()}\n")
                    exit(0)
    if flag is False:
        print("FAILURE: The PCR entries don't match.")
        exit(1)

    # this is only reached when pcr entries match
    print("TPM measurements in pcr.log and eventlog.log match.")

if __name__ == "__main__":
    # check if log files are passed to script
    if len(sys.argv) != 3:
        print("Usage: python3 verify_tpm_measurements.py"
              " <path to pcr.log> <path to eventlog.log>")
        exit(1)

    try:
        # parse commandline for filenames
        pcrlog_name = sys.argv[1]
        eventlog_name = sys.argv[2]

        # extract pcr values from pcr.log and eventlog.log
        sha_pcrs_a = extract_sha_pcrs(pcrlog_name)
        sha_pcrs_b = extract_sha_pcrs(eventlog_name)

        # compare pcr values
        compare_sha_pcrs(sha_pcrs_a, sha_pcrs_b)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

