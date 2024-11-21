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

import argparse
import json
import re

def main(input_file, output_file):
    tests = []
    test = {}
    with open(input_file, 'r') as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('TESTING:'):
                # Start a new test
                test_description = line[len('TESTING:'):].strip()
                test_info = ''
                test_result = ''
                i += 1
                # Read next lines for INFO and RESULTS
                while i < len(lines):
                    line = lines[i].strip()
                    if line.startswith('INFO :'):
                        test_info = line[len('INFO :'):].strip()
                    elif line.startswith('RESULTS :'):
                        test_result = line[len('RESULTS :'):].strip()
                        # Finished reading this test
                        break
                    i += 1
                # Add test to the list
                test = {
                    'Test_Description': test_description,
                    'Test_Info': test_info,
                    'Test_Result': test_result.upper()
                }
                tests.append(test)
            i += 1

    # Calculate summary
    summary = {
        'total_PASSED': sum(1 for t in tests if t['Test_Result'] == 'PASSED'),
        'total_FAILED': sum(1 for t in tests if t['Test_Result'] == 'FAILED'),
        'total_SKIPPED': sum(1 for t in tests if t['Test_Result'] == 'SKIPPED'),
    }

    # Prepare final JSON structure
    output_data = {
        'Test_Suite': 'Capsule Update Tests',
        'Tests': tests,
        'Summary': summary
    }

    # Write to JSON file
    with open(output_file, 'w') as json_file:
        json.dump(output_data, json_file, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse capsule update logs and save results to a JSON file.")
    parser.add_argument("input_file", help="Input capsule update log file")
    parser.add_argument("output_file", help="Output JSON file")

    args = parser.parse_args()
    main(args.input_file, args.output_file)
