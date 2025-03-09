#!/bin/sh
# @file
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
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

#output for help command
if [ "$1" = "-h" ]; then
   echo ""
   echo "This tool updates the acs.cfg file at /acs_tests/config"
   echo "Usage:"
   echo "$0 <path to ACS prebuilt image> <path to acs.cfg> <path to copy acs_results or n to skip copying of the results>"
   echo "$0 -h"
   echo "Note:\n\t• If path to acs_results is not given, acs_image directory will be used as default\n\t• The script requires sudo privileges\n\t• The operation mode can be modified within the script if needed"
   echo ""
   exit 0
fi

#Checks for minimum number of arguments
if [ $# -lt 2 ] || [ $# -gt 3 ]; then
   echo ""
   echo "Usage:"
   echo "$0 <path to ACS prebuilt image> <path to acs.cfg> <path to copy acs_results or n to skip copying of the results>"
   echo "$0 -h"
   echo ""
   exit 1
fi

#sets various paths
acs_image_path="$1"
operation="put"
path_in_image="/acs_tests/config"
path_in_local="$2"
path_for_results=${3:-$(dirname "$acs_image_path")}  # Default to ACS image directory if $3 is empty
loop_variable="p1"

#checks for valid loop
loop=$(sudo kpartx -a -v "$acs_image_path" | grep "add map" | grep "p1" | head -n1 | awk '{print $3}')
if [ -z "$loop" ]; then
    echo "kpartx failed. Please check the arguments passed."
    exit 1
fi
echo "Loop is $loop"

echo "Mounting the partition $loop"
sudo mount "/dev/mapper/$loop" /mnt
if [ $? -ne 0 ]; then
    echo "mount failed"
    sudo kpartx -d -v "$acs_image_path" >/dev/null  # Cleanup before exiting
    exit 1
fi

# Copying the acs_results to the specified directory
echo "Copying the acs_results"
if [ "$3" != "n" ]; then
    if [ "$3" != "0" ]; then
        sudo cp -r /mnt/acs_results "$path_for_results"
    else
        sudo cp -r /mnt/acs_results "$(dirname "$acs_image_path")"
    fi
else
    echo "acs_results not copied"
fi

#performing the operation
if [ "$operation" = "get" ]; then
    sudo cp -r "/mnt/$path_in_image" "$(dirname "$path_in_local")"
    if [ $? -eq 0 ]; then
        echo "get success"
    else
        echo "get failed"
    fi
else
    echo "Operation is put"
    sudo cp -r "$path_in_local" "/mnt/$path_in_image"
    if [ $? -eq 0 ]; then
         echo "\"$path_in_local\" is successfully uploaded to the path \"$path_in_image\" of the image \"$acs_image_path\""
    else
         echo "put failed"
    fi
fi

#unmounting the loop
sudo umount /mnt
if [ $? -ne 0 ]; then
    echo "unmount failed. Please unmount manually"
    exit 1
fi
sudo kpartx -d -v "$acs_image_path"
if [ $? -ne 0 ]; then
    echo "kpartx delete failed. Please unmount manually"
    exit 1
fi

