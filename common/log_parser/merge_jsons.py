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

import json
import argparse
import os

def reformat_json(json_file_path):
    """Ensure consistent formatting and indentation for the input JSON file."""
    try:
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        # Reformat the JSON file with consistent indentation
        with open(json_file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)
    except FileNotFoundError:
        raise
    except json.JSONDecodeError:
        print(f"Warning: {json_file_path} is not a valid JSON file. Skipping.")

def merge_json_files(json_files, output_file):
    merged_results = {}

    for json_file_path in json_files:
        if not os.path.isfile(json_file_path):
            print(f"Warning: {json_file_path} not found. Skipping this file.")
            continue

        try:
            reformat_json(json_file_path)
        except json.JSONDecodeError:
            # Already handled in reformat_json()
            continue

        try:
            with open(json_file_path, 'r') as json_file:
                data = json.load(json_file)

            # Determine the section name based on the file name
            file_name = os.path.basename(json_file_path).upper()

            if "BSA" in file_name and not "SBSA" in file_name:
                section_name = "Suite_Name: BSA"
            elif "SBSA" in file_name:
                section_name = "Suite_Name: SBSA"
            elif "FWTS" in file_name:
                section_name = "Suite_Name: FWTS"
            elif "SCT" in file_name:
                section_name = "Suite_Name: SCT"
            elif "DT_KSELFTEST" in file_name:
                section_name = "Suite_Name: DT Kselftest"
            elif "DT_VALIDATE" in file_name:
                section_name = "Suite_Name: DT Validate"
            elif "ETHTOOL_TEST" in file_name:
                section_name = "Suite_Name: Ethtool Test"
            elif "READ_WRITE_CHECK_BLK_DEVICES" in file_name:
                section_name = "Suite_Name: Read Write Check Block Devices"
            else:
                section_name = "Suite_Name: Unknown"

            # Add this section to the merged_results under its header
            merged_results[section_name] = data

        except FileNotFoundError:           
            print(f"Warning: {json_file_path} not found during merging. Skipping this file.")
        except json.JSONDecodeError:
            print(f"Warning: {json_file_path} is not a valid JSON file after reformatting. Skipping.")

    # Write the merged results to the output JSON file with consistent indentation
    with open(output_file, 'w') as output_json_file:
        json.dump(merged_results, output_json_file, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple JSON files into a single JSON file with consistent formatting.")
    parser.add_argument("output_file", help="Output JSON file for merged results")
    parser.add_argument("json_files", nargs='+', help="List of input JSON files to merge")

    args = parser.parse_args()
    merge_json_files(args.json_files, args.output_file)
