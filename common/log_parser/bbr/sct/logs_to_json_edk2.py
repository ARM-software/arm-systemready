#!/usr/bin/env python3

# @file
# Copyright (c) 2024-2025, Arm Limited or its affiliates. All rights reserved.
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


import argparse
import json
import re
import sys
import os
import chardet

def detect_file_encoding(file_path):
    """Detect file encoding using chardet."""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
    return result.get('encoding', 'utf-8')

def parse_edk2_log(input_file):
    """
    Parse an edk2-test-parser.log (Markdown table format) and extract exactly four fields:
      - "Test Entry Point GUID" (from the column "set guid")
      - "sub_Test_GUID"         (from the column "guid")
      - "result"                (from the column "result")
      - "reason"                (from the column "updated by")
    
    Returns a list of dictionaries.
    """
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    encoding = detect_file_encoding(input_file)
    results = []
    header_found = False
    col_index_map = {}

    # Define target columns (lowercase) with their output JSON key names.
    targets = {
        "set guid": "Test Entry Point GUID",
        "guid": "sub_Test_GUID",
        "result": "result",
        "updated by": "reason"
    }

    with open(input_file, 'r', encoding=encoding, errors='ignore') as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip("\n")
        # Process only lines that look like table rows (start and end with "|")
        if line.strip().startswith("|") and line.strip().endswith("|"):
            # Split the row by "|" and remove any empty first and last elements.
            cols = line.strip().split("|")
            if cols and cols[0] == "":
                cols = cols[1:]
            if cols and cols[-1] == "":
                cols = cols[:-1]

            # Check if this row is a header row by looking for our target column names.
            lower_cols = [col.strip().lower() for col in cols]
            if not header_found and any(t in lower_cols for t in targets):
                # Capture *all* column names, not just targets
                col_index_map = {col: idx for idx, col in enumerate(lower_cols)}
                header_found = True
                continue

            # If header is found, skip separator rows (rows that contain only dashes)
            if header_found:
                if all(re.fullmatch(r"[-:]+", cell.strip()) for cell in cols if cell.strip()):
                    continue

                # Build a record based on the header column positions.
                record = { output_key: "" for output_key in targets.values() }
                # Extract known columns
                for key, output_key in targets.items():
                    idx = col_index_map.get(key)
                    if idx is not None and idx < len(cols):
                        record[output_key] = cols[idx].strip()

                # Capture sub_Test_Description correctly

                # If there's a 'name' column (typical for grouped tables like RuntimeServicesTest, BootServicesTest, etc.)
                # then use that column as description.
                # Otherwise (like GenericTest), fall back to the first column.
                name_idx = col_index_map.get("name")

                if name_idx is not None and name_idx < len(cols):
                    # Extract from 'name' column
                    record["sub_Test_Description"] = cols[name_idx].strip()
                # Append record if any target field is non-empty
                if any(record.values()):
                    results.append(record)
        else:
            # Reset header_found if we leave a table section.
            header_found = False

    return results

def main():
    parser = argparse.ArgumentParser(
        description="Parse an edk2-test-parser.log Markdown file and output JSON with fixed fields."
    )
    parser.add_argument("input_file", help="Path to the edk2-test-parser.log file")
    parser.add_argument("output_file", help="Path to the output JSON file")
    args = parser.parse_args()

    parsed_results = parse_edk2_log(args.input_file)
    with open(args.output_file, 'w', encoding='utf-8') as out_f:
        json.dump(parsed_results, out_f, indent=4)

if __name__ == "__main__":
    main()
