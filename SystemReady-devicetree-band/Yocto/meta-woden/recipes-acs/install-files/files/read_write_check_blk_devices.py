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

# This script parses for block devices and perform block read and write operation if the partition doesn't belong precious partitions set.

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

def is_mounted(device):
    command = f"findmnt -n {device}"
    result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
    return result.returncode == 0

def is_mtd_block_device(device):
    return device.startswith('mtdblock')

def is_ram_disk(device):
    return device.startswith('ram')

def perform_write_check(partition_label, partition_id, precious_parts):

    if is_mounted(f"/dev/{partition_label}"):
        print(f"INFO: /dev/{partition_label} is mounted, skipping write test.")
        return

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

def get_partition_labels(disk):
    """
    Return a list of partition labels from lsblk *without* relying on box/Unicode characters.
    """
    command = f"lsblk -rn -o NAME,TYPE /dev/{disk} | awk '/part/ {{print $1}}'"
    result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
    labels = result.stdout.strip().split()
    return labels

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
            # Skip MTD block devices
            if is_mtd_block_device(disk):
                print(f"INFO: Skipping MTD block device /dev/{disk}")
                continue

            # Skip RAM disks
            if is_ram_disk(disk):
                print(f"INFO: Skipping RAM disk /dev/{disk}")
                continue

            print(f"INFO: Block device : /dev/{disk}")

            # check whether disk uses MBR or GPT partition table
            command = f"timeout 10 gdisk -l /dev/{disk}"
            result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

            if "MBR: MBR only" in result.stdout:
                part_table = "MBR"
            elif "GPT: present" in result.stdout:
                part_table = "GPT"
            else:
                print(f"INFO: No valid partition table found for {disk}, treating as raw device.")
                part_table = "RAW"

            print(f"INFO: Partition table type : {part_table}\n")

            # get number of partitions available for given disk
            command = f"lsblk -rn -o NAME,TYPE /dev/{disk} | grep -c part"
            result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
            num_parts_str = result.stdout.strip()
            num_parts = int(num_parts_str) if num_parts_str else 0

            if part_table == "RAW" or num_parts == 0:
                print(f"INFO: No partitions detected for {disk}, treating as raw device.")
                part_lables = [disk]  # Treat the whole disk as a 'partition'

                # Process the raw disk
                for part_label in part_lables:
                    print(f"INFO: Performing block read on /dev/{part_label}")
                    command = f"dd if=/dev/{part_label} bs=1M count=1 > /dev/null"
                    result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
                    if result.returncode == 0:
                        print(f"INFO: Block read on /dev/{part_label} successful")
                        # Since we don't have partition IDs, pass empty string to perform_write_check
                        perform_write_check(part_label, '', {})
                    else:
                        print(f"INFO: Block read on /dev/{part_label} failed")

                print("\n********************************************************************************************************************************\n")
                continue  # Continue to next disk

            # get partition labels with the safer method
            part_lables = get_partition_labels(disk)

            # If there's a mismatch, just warn. We do not skip any existing partitions.
            if len(part_lables) < num_parts:
                print(f"WARNING: Mismatch in partition count. Found {len(part_lables)} partition labels, "
                      f"but lsblk reported {num_parts} partitions for {disk}. Proceeding with the ones we have...")

            # -----------------------------------
            # MBR scheme
            # -----------------------------------
            if part_table == "MBR":
                table_header_row = ["Device", "Boot", "Start", "End", "Sectors", "Size", "Id", "Type"]
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
                            # Because "Boot" might be an extra column, handle if columns[1] == '*'
                            if columns[1] == '*' and len(columns) >= 7:
                                # Then columns[6] is the "Id" (typical fdisk layout)
                                mbr_part_ids.append("0x" + columns[6].upper())
                            else:
                                # columns[5] is the "Id" in normal case
                                mbr_part_ids.append("0x" + columns[5].upper())
                    elif all(substring in line for substring in table_header_row):
                        collect_lines = True

                if len(mbr_part_ids) < num_parts:
                    print(f"WARNING: Could not parse enough MBR partition IDs. Found {len(mbr_part_ids)}, expected {num_parts}.")

                # Process up to min of (parsed labels, parsed IDs, num_parts)
                process_count = min(len(part_lables), len(mbr_part_ids), num_parts)

                for index in range(process_count):
                    print(f"\nINFO: Partition : /dev/{part_lables[index]} Partition type : {mbr_part_ids[index]}")

                    if mbr_part_ids[index] in precious_parts_mbr.values():
                        # skip read/write for precious
                        for key, value in precious_parts_mbr.items():
                            if value == mbr_part_ids[index]:
                                print(f"INFO: {part_lables[index]} partition is PRECIOUS")
                                used_blocks, _ = get_partition_space(f"/dev/{part_lables[index]}")
                                print(f"INFO: Number of 512B blocks used on /dev/{part_lables[index]}: {used_blocks}")
                                print(f"      {key} : {value}")
                                print("      Skipping block read/write...")
                                break
                    else:
                        command = f"dd if=/dev/{part_lables[index]} bs=1M count=1 > /dev/null"
                        print(f"INFO: Performing block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]}")
                        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)
                        if result.returncode == 0:
                            print(f"INFO: Block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]} successful")
                            perform_write_check(part_lables[index], mbr_part_ids[index], precious_parts_mbr)
                        else:
                            print(f"INFO: Block read on /dev/{part_lables[index]} mbr_part_id = {mbr_part_ids[index]} failed")
                print("\n********************************************************************************************************************************\n")

            # if disk follows GPT scheme
            elif part_table == "GPT":
                # We'll parse partition GUID code + attribute flags with sgdisk
                process_count = min(len(part_lables), num_parts)
                for index in range(process_count):
                    command = f"sgdisk -i={index+1} /dev/{disk}"
                    result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                    # regex to match part GUIDs and attribute flags
                    guid_regex = r"Partition GUID code: ([\w-]+) \("
                    attr_flag_regex = r"Attribute flags: ([0-9A-Fa-f]+)"
                    guid_code_match = re.search(guid_regex, result.stdout)
                    attribute_flags_match = re.search(attr_flag_regex, result.stdout)

                    if not guid_code_match or not attribute_flags_match:
                        print(f"INFO: Unable to parse sgdisk info for {part_lables[index]}. Skipping.")
                        continue

                    partition_guid_code = guid_code_match.group(1)
                    attribute_flags_hex = attribute_flags_match.group(1)
                    attribute_flags_int = int(attribute_flags_hex, 16)
                    lsb = attribute_flags_int & 1  # "Platform required" bit

                    print(f"\nINFO: Partition : /dev/{part_lables[index]} Partition type GUID : {partition_guid_code} \"Platform required bit\" : {lsb}")

                    # skip block read if "Platform required" bit is set
                    if lsb == 1:
                        print(f"INFO: Platform required attribute set for {part_lables[index]} partition, skipping block read/write...")
                        continue
                    # check if the partition is precious
                    if partition_guid_code in precious_parts_gpt.values():
                        used_blocks, _ = get_partition_space(f"/dev/{part_lables[index]}")
                        for key, value in precious_parts_gpt.items():
                            if value == partition_guid_code:
                                print(f"INFO: {part_lables[index]} partition is PRECIOUS.")
                                print(f"INFO: Number of 512B blocks used on /dev/{part_lables[index]}: {used_blocks}")
                                print(f"      {key} : {value}")
                                print("      Skipping block read/write...")
                                break
                    else:
                        command = f"dd if=/dev/{part_lables[index]} bs=1M count=1 > /dev/null"
                        print(f"INFO: Performing block read on /dev/{part_lables[index]} part_guid = {partition_guid_code}")
                        result = subprocess.run(command, shell=True, text=True, check=False, capture_output=True)

                        if result.returncode == 0:
                            print(f"INFO: Block read on /dev/{part_lables[index]} part_guid = {partition_guid_code} successful")
                            perform_write_check(part_lables[index], partition_guid_code, precious_parts_gpt)
                        else:
                            print(f"INFO: Block read on /dev/{part_lables[index]} part_guid = {partition_guid_code} failed")

                print("\n********************************************************************************************************************************\n")
            else:
                print(f"INFO: Invalid partition table, expected MBR or GPT reported type = {part_table}")

    except Exception as e:
        print(f"Error occurred: {e}")
        exit(1)
