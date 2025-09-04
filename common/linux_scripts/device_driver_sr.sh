#!/bin/bash

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

#This script reports the drivers in use for block devices, graphics cards, network interfaces, and PCIe devices on a Linux system

echo
echo "Block Device Drivers Details"
echo "----------------------------"
echo ""
printf "%10s %10s \n" "Device" "Driver"

for f in /sys/class/block/*; do
    dev=$(basename "$f")
    if driver_link=$(readlink "$f/device/driver" 2>/dev/null); then
        driver=$(basename "$driver_link")
        printf "%10s %10s \n" "$dev" "$driver"
    fi
done
echo
echo


echo "Graphics Device Driver Details"
echo "------------------------------"
echo ""
lspci -k 2>/dev/null | grep -EA3 'VGA|3D|Display'
echo
echo


echo "Network Device Drivers Details"
echo "------------------------------"
echo ""
printf "%10s %30s (%s)\n" "Device" "Driver" "Status"

for f in /sys/class/net/*; do
    dev=$(basename "$f")
    addr=$(cat "$f/address" 2>/dev/null)
    operstate=$(cat "$f/operstate" 2>/dev/null)

    if driver_link=$(readlink "$f/device/driver/module" 2>/dev/null); then
        driver=$(basename "$driver_link")
    else
        driver="N/A"
    fi

    printf "%10s [%s] %10s (%s)\n" "$dev" "$addr" "$driver" "$operstate"
done
echo
echo


echo "PCIe Device Driver Details"
echo "--------------------------"
echo ""

lspci -vvv 2>/dev/null | awk '
BEGIN {
    flag = 0;
    FS = ":"
}
/^[0-9A-Fa-f]*[:]*[0-9A-Fa-f][0-9A-Fa-f]:[0-9A-Fa-f][0-9A-Fa-f]\.[0-7]/ {
    if (flag == 1) {
        print "        No driver found\n"
    }
    flag = 1
    print $0
}
{
    if (flag == 1 && index($0, "Kernel driver in use") > 0) {
        print $0
        flag = 0
        print ""
    }
}
END {
    if (flag == 1) {
        print "        No driver found\n"
    }
}'

echo
echo
