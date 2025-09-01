#!/usr/bin/env python3
# Copyright (c) 2024-2025, Arm Limited or its affiliates. All rights reserved.
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

import chardet
import re
import sys

def extract_hex_values(file_path, pattern):
    # Detect file encoding using chardet
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']

    try:
        # Read the file using the detected encoding
        with open(file_path, 'r', encoding=encoding) as file:
            lines = file.readlines()

        matches = []
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    matches.append(match.group(1))
                except IndexError:
                    continue
        return matches

    except UnicodeDecodeError:
        print(f"Error: Unable to decode the file {file_path} with detected encoding: {encoding}")
        return []

if len(sys.argv) != 3:
    print("Usage: python3 extract_capsule_fw_version.py <pattern> <file_path>")
    sys.exit(1)

pattern = sys.argv[1]
file_path = sys.argv[2]

hex_values = extract_hex_values(file_path, pattern)
for val in hex_values:
    print(val)
