#!/bin/bash 


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


echo
echo "Block Device Drivers Details"
echo "----------------------------"
echo ""
printf "%10s %10s \n" "Device" "Driver" 
for f in /sys/class/block/*; do
    dev=$(basename $f)
    driver=$(readlink $f/device/driver)
    if [ $driver ]; then
        driver=$(basename $driver)
        printf "%10s %10s \n" "$dev" "$driver"
    fi
done
echo ""
echo ""


echo "Graphics Driver Details"
echo "-----------------------"
echo ""

lspci -k | grep -EA3 'VGA|3D|Display'

echo ""
echo ""


echo "Network Drivers Details"
echo "-----------------------"
echo ""
printf "%10s %30s (%s)\n" "Device" "Driver" "Status"
for f in /sys/class/net/*; do
    dev=$(basename $f)
    driver=$(readlink $f/device/driver/module)
    if [ $driver ]; then
        driver=$(basename $driver)
    fi
    addr=$(cat $f/address)
    operstate=$(cat $f/operstate)
    printf "%10s [%s] %10s (%s)\n" "$dev" "$addr" "$driver" "$operstate"
done
echo ""
echo ""


echo "PCIe Driver Details"
echo "-------------------"
echo ""

lspci -vvv | awk 'BEGIN {flag=0; FS=":"} /^[0-9A-Fa-f]*[:]*[0-9A-Fa-f][0-9A-Fa-f]:[0-9A-Fa-f][0-9A-Fa-f]\.[0-7]/ { if(flag==1){print "        No driver found\n";} flag=1; print $0;} \
	{if (flag ==1) {if (index($0, "Kernel driver in use")>0) {print $0; flag=0; print "";} } } END{if (flag ==1) {print "        No driver found\n";}}'

echo ""
echo ""



# Function to process input files directly without intermediate files
process_file() {
    local input_file="$1"
    local type="$2"

    # Read the input file line by line and process it
    while IFS= read -r line; do
        # Skip header lines and unnecessary lines
        if [[ "$line" == "===="* ]] || [[ "$line" == *"Device Name"* ]] || [[ "$line" == *"Devices:"* ]] || [[ "$line" == V* || "$line" == ==* ]]; then
            continue
        fi

        # Split the line into an array based on whitespace
        read -ra parts <<< "$line"

        # Determine expected parts based on type
        local expected_parts
        if [[ "$type" == "devices" ]]; then
            expected_parts=8
        else
            expected_parts=9
        fi

        # Check if there are enough parts
        if [[ "${#parts[@]}" -lt $expected_parts ]]; then
            continue
        fi

        # Process devices
        if [[ "$type" == "devices" ]]; then
            device_id="${parts[0]}"
            device_type="${parts[1]}"
            control="${parts[2]}"
            enable="${parts[3]}"
            param1="${parts[4]}"
            param2="${parts[5]}"
            param3="${parts[6]}"
            device_name="${parts[@]:7}"  # Join the remaining parts for the device name

            # Replace '-' with 'N' for control and enable
            [[ "$control" == "-" ]] && control="N"
            [[ "$enable" == "-" ]] && enable="N"

            # Return the device info
            echo "DevicesInfo,\"$device_id\",\"$device_type\",\"$control\",\"$enable\",\"$param1\",\"$param2\",\"$param3\",\"$device_name\""

        # Process drivers
        elif [[ "$type" == "drivers" ]]; then
            driver_id="${parts[0]}"
            version="${parts[1]}"
            driver_type="${parts[2]}"
            control="${parts[3]}"
            enable="${parts[4]}"
            param1="${parts[5]}"
            param2="${parts[6]}"
            driver_name="${parts[@]:7:${#parts[@]}-8}"  # Join parts for the driver name
            image_name="${parts[-1]}"  # Last part is the image name

            # Replace '-' with 'N' for control, enable, param1, and param2
            [[ "$control" == "-" ]] && control="N"
            [[ "$enable" == "-" ]] && enable="N"
            [[ "$param1" == "-" ]] && param1="N"
            [[ "$param2" == "-" ]] && param2="N"

            # Return the driver info
            echo "DriversInfo,\"$driver_id\",\"$version\",\"$driver_type\",\"$control\",\"$enable\",\"$param1\",\"$param2\",\"$driver_name\",\"$image_name\""
        fi
    done < "$input_file"
}

# Process and capture device information from devices.log
devices_processed=$(process_file "/mnt/acs_results/uefi_dump/devices.log" "devices")

# Process and capture driver information from drivers.log
drivers_processed=$(process_file "/mnt/acs_results/uefi_dump/drivers.log" "drivers")

# Extract device list and search against dh.out.txt
device_ids=$(echo "$devices_processed" | awk -F, '{gsub(/"/, "", $2); print $2;}' | tr -d '\0' | tail -n +2)

echo "UEFI DEVICE DRIVER DETAILS"
echo "--------------------------"

# Initialize serial number
serial_num=1

# Print the header
echo "Serial No|Device ID|Device Name|Device Peg|Driver Name"

# Iterate through devices to match with dh.out.txt and drivers
echo "$devices_processed" | while read -r device_line; do
    device_id=$(echo "$device_line" | awk -F',' '{gsub(/"/, "", $2); print $2}')
    
    # Find the corresponding line in dh.log
    dh_line=$(awk '/Ctrl\['"$device_id"'\]/{print h} /^[a-zA-Z0-9]+:/{h=$0}' /mnt/acs_results/uefi_dump/dh.log)

    # Extract the device peg from the dh_line
    device_peg=$(echo "$dh_line" | awk -F':' '{print $1}')

    # Extract the device information
    DEVICE=$(echo "$device_line" | awk -F"\"" '{print $16}')

    # Extract the driver information from processed drivers
    DRIVER=$(echo "$drivers_processed" | grep "$device_peg" | awk -F"," '{gsub(/"/, "", $0); print $9}')

    # Check if device_peg is empty and print the appropriate message
    if [[ -z $device_peg ]]; then
        # Print serial number, device, and NA for driver not found
        echo "$serial_num|$device_id|$DEVICE|NA|Driver not found"
    else
        # Print serial number, device, and driver info
        echo "$serial_num|$device_id|$DEVICE|$device_peg|$DRIVER"
    fi

    # Increment the serial number
    ((serial_num++))
done

