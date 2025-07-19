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

def extract_hex_value(file_path):
    # Regular expression to match 'FwVersion - 0x<hex_value>'
    pattern = sys.argv[1]

    # Detect file encoding using chardet
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']

    try:
        # Read the file using the detected encoding
        with open(file_path, 'r', encoding=encoding) as file:
            lines = file.readlines()

        for line in lines:
            match = re.search(pattern, line)
            if match:
                return match.group(1)

    except UnicodeDecodeError:
        print(f"Error: Unable to decode the file {file_path} with detected encoding: {encoding}")
        return None

    return None

file_path = sys.argv[2]
hex_value = extract_hex_value(file_path)

# Print the result
if hex_value:
    print(hex_value)
else:
    print("No 'FwVersion' found in the file.")
