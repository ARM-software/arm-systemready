#!/usr/bin/env python3
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
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
import os

def read_file(file_path):
    _, file_extension = os.path.splitext(file_path)
    with open(file_path, "r") as file:
        return file_extension, file.read()

def merge_files(input_file_paths, merged_file_path):
    # Read the contents of the existing files
    file_contents = []
    for file_path in input_file_paths:
        file_extension, content = read_file(file_path)
        file_contents.append((file_extension, content))

    # Merge the contents into an HTML file
    with open(merged_file_path, "w") as merged_file:
        merged_file.write("<html>\n<head>\n<title>Summary</title>\n</head>\n<body>\n")
        for i, (file_extension, content) in enumerate(file_contents):
            merged_file.write(content + "\n")
        merged_file.write("</body>\n</html>")

if __name__ == "__main__":
    # Create a command-line argument parser
    parser = argparse.ArgumentParser(description="Merge multiple files into a single HTML file.")
    
    # Add the command-line arguments
    parser.add_argument("input_file_paths", nargs='+', help="Paths to the input files")
    parser.add_argument("merged_file_path", help="Path for the merged HTML file")
    
    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the function with the provided arguments
    merge_files(args.input_file_paths, args.merged_file_path)
