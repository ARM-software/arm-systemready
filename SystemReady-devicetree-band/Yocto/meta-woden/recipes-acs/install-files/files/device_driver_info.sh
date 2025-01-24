#!/bin/sh

# @file
# Copyright (c) 2024, Arm Limited or its affiliates. All rights reserved.
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

output_file="device_driver_info.log"

# Search within /sys for directories with non-empty drivers subdirectory
find /sys -type d -name drivers -exec bash -c '
    driver_dir=$(dirname "$0")  # Path to the driver subdirectory
    if [ -n "$(ls -A "$0")" ]; then
        parent_name=$(basename "$driver_dir")  # Extract the parent directory name
        for driver_name in $(ls "$0"); do
            echo "$parent_name : $driver_name" >> "$1"
        done
    fi
' {} "$output_file" \;
echo "$1"
echo "Device and Driver information saved to $output_file"
