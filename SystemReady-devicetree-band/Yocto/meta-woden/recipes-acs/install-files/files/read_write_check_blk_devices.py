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

# This script parses for block devices and perform block read operation if the partition
# doesn't belong precious partitions set.

import subprocess
import re
import hashlib
import threading
import os

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

def input_with_timeout(prompt, timeout=5):
    print(prompt, end='', flush=True)
    input_queue = []
    def get_user_input():
        try:
            input_queue.append(input())
        except EOFError:
            pass
    user_input_thread = threading.Thread(target=get_user_input)
    user_input_thread.daemon = True
    user_input_thread.start()
    user_input_thread.join(timeout)
    return input_queue[0] if input_queue else "no"

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_partition_space(partition_path): #to calculate used blocks and available blocks
    command = f"df -B 512 {partition_path} --output=used,avail"
    result = subprocess.run(command, shell=True, text=True, check=True, capture_output=True)
    lines = result.stdout.strip().split('\n')
    if len(lines) > 1:
        parts = lines[1].split()
        used_blocks = int(parts[0])
        available_blocks = int(parts[1])
        return used_blocks, available_blocks
    else:
        print(f"WARNING: Unable to parse partition space for {partition_path}.")
        return 0, 0  # Default to 0 if parsing fails

def perform_write_check(partition_label, partition_id, precious_parts):

    # Check if partition is precious
    user_input = 'no' if partition_id in precious_parts.values() else input_with_timeout(
        f"Do you want to perform a write check on /dev/{partition_label}? (yes/no): ", 5).lower()

    if user_input == 'yes' and partition_id not in precious_parts.values():
        used_blocks, available_blocks = get_partition_space(f"/dev/{partition_label}")
        if available_blocks > 0:

            # Prepare hello.txt content with padding to 512 bytes
            hello_content = "Hello!".ljust(512, '\x00')  # Pad the content to 512 bytes
            with open("hello.txt", "wb") as f:
                f.write(hello_content.encode('utf-8'))
            original_sha256 = calculate_sha256("hello.txt")

            # Backup filename specific to partition
            backup_filename = f"{partition_label}_backup.bin"
            # backup command
            print("INFO: Creating backup of the current block before write check...")
            backup_command = f"dd if=/dev/{partition_label} of={backup_filename} bs=512 count=1 skip={used_blocks}"
            subprocess.run(backup_command, shell=True, check=True)

            # Write padded hello.txt to the device
            print("INFO: Writing test data to the device for write check...") 
            write_command = f"dd if=hello.txt of=/dev/{partition_label} bs=512 count=1 seek={used_blocks}"
            subprocess.run(write_command, shell=True, check=True)

            # Read back the 512-byte block
            read_back_file = "read_hello.txt"
            print("INFO: Reading back the test data for verification...")
            read_command = f"dd if=/dev/{partition_label} of={read_back_file} bs=512 count=1 skip={used_blocks}"
            subprocess.run(read_command, shell=True, check=True)

            # Calculate SHA256 for the padded content to ensure a fair comparison
            read_back_sha256 = calculate_sha256(read_back_file)

            # Verify checksums
            print(f"Original SHA256: {original_sha256}")
            print(f"Read-back SHA256: {read_back_sha256}")
            if original_sha256 == read_back_sha256:
                print(f"INFO: write check passed on /dev/{partition_label}.")

                # Restore the backup
                print("INFO: Restoring the backup to the device after write check...")
                restore_command = f"dd if={backup_filename} of=/dev/{partition_label} bs=512 count=1 seek={used_blocks}"
                subprocess.run(restore_command, shell=True, check=True)
                print(f"INFO: Backup restored for /dev/{partition_label}.")
            else:
                print(f"WARNING: Data integrity check failed for /dev/{partition_label}. Possible data corruption.")

            # Clean up
            os.remove("hello.txt")
            os.remove(read_back_file)
            os.remove(backup_filename)

        else:
            print(f"WARNING: No available space for write check on /dev/{partition_label}. Skipping write check.")


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
            command = f"timeout 10 gdisk -l /dev/{disk}"
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
                print(f"INFO: No partitions detected for {disk}, skipping block read/write...")
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
                lines = result.stdout.strip().split('\n')
                collect_lines = False
                mbr_part_ids = []

                for line in lines:
                    if collect_lines:
                        columns = line.split()
                        if len(columns) >= 6:
                            mbr_part_ids.append("0x" + columns[5].upper())
                    elif all(substring in line for substring in table_header_row):
                        collect_lines = True

                if not(len(part_lables) == len(mbr_part_ids) == num_parts):
                    print(f"INFO: Error parsing MBR partition Ids/partition labels/number of partition(s) for {disk} ")

                for index in range(0, num_parts):
                    print(f"\nINFO: Partition : /dev/{part_lables[index]} Partition type : {mbr_part_ids[index]}")

                    if mbr_part_ids[index] in precious_parts_mbr.values():
                        for key, value in precious_parts_mbr.items():
                            if value == mbr_part_ids[index]:
                                print(f"INFO: {part_lables[index]} partition is PRECIOUS")
                                used_blocks = get_partition_space(f"/dev/{part_lables[index]}")
                                print(f"INFO: Number of 512B blocks used on /dev/{part_lables[index]}: {used_blocks}")
                                print(f"      {key} : {value}")
                                print("      Skipping block read/write...")
                                continue
                    else:
                        command = f"dd if=/dev/{part_lables[index]} bs=1M count=1 > /dev/null"
                        print(f"INFO: Performing block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]}")
                        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
                        if result.returncode == 0:
                            print(f"INFO: Block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]} successful")
                            # Call the perform_write_check function for the partition
                            perform_write_check(part_lables[index], partition_guid_code, precious_parts_gpt)
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
                        print(f"INFO: Platform required attribute set for {part_lables[index]} partition, skipping block read/write...")
                        continue
                    # check if the partition is precious
                    if partition_guid_code in precious_parts_gpt.values():

                        used_blocks = get_partition_space(f"/dev/{part_lables[index]}")

                        for key, value in precious_parts_gpt.items():
                            if value == partition_guid_code:
                                print(f"INFO: {part_lables[index]} partition is PRECIOUS.")
                                print(f"INFO: Number of 512B blocks used on /dev/{part_lables[index]}: {used_blocks}")
                                print(f"      {key} : {value}")
                                print("      Skipping block read/write...")
                                continue
                    # perform block read of 1 block (1MB)
                    else:
                        command = f"dd if=/dev/{part_lables[index]} bs=1M count=1 > /dev/null"
                        print(f"INFO: Performing block read on /dev/{part_lables[index]} part_guid = {partition_guid_code}")
                        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                        if result.returncode == 0:
                            print(f"INFO: Block read on /dev/{part_lables[index]} part_guid = {partition_guid_code} successful")
                            # Call the perform_write_check function for the partition
                            perform_write_check(part_lables[index], partition_guid_code, precious_parts_gpt)
                        else:
                            print(f"INFO: Block read on /dev/{part_lables[index]} part_guid = {partition_guid_code} failed")

                print("\n********************************************************************************************************************************\n")
            else:
                print(f"INFO: Invalid partition table, expected MBR or GPT reported type = {part_table}")

    except Exception as e:
        print(f"Error occurred: {e}")
        exit(1)
