#!/usr/bin/env python3
# Copyright (c) 2023, Arm Limited or its affiliates. All rights reserved.
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

# This script parses for block devices and perform block read operation if the partition
# doesn't belong precious partitions set.

import subprocess
import re

# Note: Precious partitions dictionary, this is a set of partition types which might have firmware
# and to be refrained from read/write operations. The list is not exhaustive might see additions in future.
precious_parts_mbr = {
    "Protective partition":"0xF8",
    "EFI system partition":"0xEF"

}

precious_parts_gpt = {
    "EFI System partition":"C12A7328-F81F-11D2-BA4B-00A0C93EC93B",
    "BIOS boot partition":"21686148-6449-6E6F-744E-656564454649",
    "U-Boot environment partition":"3DE21764-95BD-54BD-A5C3-4ABE786F38A8"
}

if __name__ == "__main__":
    try:
        # find all disk block devices
        command = "lsblk -e 7 -d | grep disk | awk '{print $1}'"
        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
        disks = result.stdout.split()

        print("\n********************************************************************************************************************************\n")
        print("                                                    Read block devices tool\n")
        print("********************************************************************************************************************************")

        print("INFO: Detected following block devices with lsblk command :")
        for num, disk in enumerate(disks):
            print(f"{num}: {disk}")

        print("\n********************************************************************************************************************************\n")

        for disk in disks:
            print(f"INFO: Block device : /dev/{disk}")

            # check whether disk uses MBR or GPT partition table
            command = f"timeout 5 gdisk -l /dev/{disk}"
            result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

            if "MBR: MBR only" in result.stdout:
                part_table = "MBR"
            elif "GPT: present" in result.stdout:
                part_table = "GPT"
            else:
                print(f"INFO: Invalid partition table or not found for {disk}")
                continue

            print(f"INFO: Partition table type : {part_table}\n")

            # get number of partitions available for given disk
            command = f"lsblk /dev/{disk} | grep -c part"
            result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
            num_parts = 0
            num_parts = int(result.stdout)

            # skip if no partitions
            if num_parts == 0:
                print(f"INFO: No partitions detected for {disk}, skipping block read...")
                continue

            # get partition labels
            command = f"lsblk /dev/{disk}  | grep part"
            result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
            part_lables = re.findall(r'[├└]─(\S+)', result.stdout)


            # if disk follows MBR
            if part_table == "MBR":
                table_header_row = ["Device", "Boot Start", "End Sectors", "Size", "Id", "Type"]
                command = f"fdisk -l /dev/{disk}"
                result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                # get MBR partition type Ids
                lines = (result.stdout).strip().split('\n')
                collect_lines = False
                mbr_part_ids = []

                # Iterate through the lines and collect lines after the header line
                for line in lines:
                    if collect_lines:
                        # Split the line into columns using spaces and extract the 6th column
                        columns = line.split()
                        if len(columns) >= 6:
                            mbr_part_ids.append("0x" + (columns[5]).upper())
                    elif all(substring in line for substring in table_header_row):
                        collect_lines = True

                # check if parsing went well for MBR
                if not(len(part_lables) == len(mbr_part_ids) == num_parts):
                    print(f"INFO: Error parsing MBR partition Ids/partition labels/number of partition(s) for {disk} ")

                # iterate partitions
                for index in range(0, num_parts):
                    print(f"\nINFO: Partition : /dev/{part_lables[index]} Partition type : {mbr_part_ids[index]}")
                    # check if the partition is precious
                    if mbr_part_ids[index] in precious_parts_mbr.values():
                        for key, value in precious_parts_mbr.items():
                            if value == mbr_part_ids[index]:
                                print(f"INFO: {part_lables[index]} partition is PRECIOUS")
                                print(f"      {key} : {value}")
                                print("      Skipping block read...")
                                continue
                    # perform block read of 1 block (1MB)
                    else:
                        command = f"dd if=/dev/{part_lables[index]} bs=1M count=1"
                        print(f"INFO: Performing block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]}")
                        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                        if result.returncode == 0:
                            print(f"INFO: Block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]} successful")
                        else:
                            print(f"INFO: Block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]} failed")
                print("\n********************************************************************************************************************************\n")

            # if disk follows GPT scheme
            elif part_table == "GPT":
                gpt_part_guids = []
                platform_required_bit = []

                # check if parsing went well for GPT
                if not(len(part_lables) == num_parts):
                    print(f"INFO: Error parsing GPT partition Ids/partition labels/number of partition(s) for {disk} ")

                for index in range(0, num_parts):
                    command = f"sgdisk -i={index+1} /dev/{disk}"
                    result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                    # regex to match part GUIDs and Attribute flags
                    guid_regex = r"Partition GUID code: ([\w-]+) \(.*\)"
                    attr_flag_regex = r"Attribute flags: ([0-9A-Fa-f]+)"
                    guid_code_match = re.search(guid_regex, result.stdout)
                    attribute_flags_match = re.search(attr_flag_regex, result.stdout)

                    # Extract Attribute flags
                    if attribute_flags_match:
                        attribute_flags_hex = attribute_flags_match.group(1)
                        attribute_flags_int = int(attribute_flags_hex, 16)  # convert hexadecimal to integer
                        lsb = attribute_flags_int & 1  # mask and get LSB (bit 0)
                    else:
                        print(f"INFO: Unable to parse Attribute flags for {part_lables[index]} partition")
                        continue

                    # Extract and print the matched values
                    if guid_code_match:
                        partition_guid_code = guid_code_match.group(1)
                    else:
                        print(f"INFO: Unable to parse Partition GUID code for {part_lables[index]} partition")
                        continue

                    print(f"\nINFO: Partition : /dev/{part_lables[index]} Partition type GUID : {partition_guid_code} \"Platform required bit\" : {lsb}")

                    # skip block read if "Platform required" bit is set
                    if lsb == 1:
                        print(f"INFO: Platform required attribute set for {part_lables[index]} partition, skipping block read...")
                        continue
                    # check if the partition is precious
                    if partition_guid_code in precious_parts_gpt.values():
                        for key, value in precious_parts_gpt.items():
                            if value == partition_guid_code:
                                print(f"INFO: {part_lables[index]} partition is PRECIOUS.")
                                print(f"      {key} : {value}")
                                print("      Skipping block read...")
                                continue
                    # perform block read of 1 block (1MB)
                    else:
                        command = f"dd if=/dev/{part_lables[index]} bs=1M count=1 > /dev/null"
                        print(f"INFO: Performing block read on /dev/{part_lables[index]} part_guid = {partition_guid_code}")
                        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                        if result.returncode == 0:
                            print(f"INFO: Block read on /dev/{part_lables[index]} part_guid = {partition_guid_code} successful")
                        else:
                            print(f"INFO: Block read on /dev/{part_lables[index]} part_guid = {partition_guid_code} failed")
                print("\n********************************************************************************************************************************\n")
            else:
                print(f"INFO: Invalid partition table, expected MBR or GPT reported type = {part_table}")

    except Exception as e:
        print(f"Error occurred: {e}")
        exit(1)