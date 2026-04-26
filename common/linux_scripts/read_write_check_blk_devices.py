#!/usr/bin/env python3
# Copyright (c) 2025-2026, Arm Limited or its affiliates. All rights reserved.
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

"""Read block devices and optionally perform safe block write checks.

The script detects block devices, identifies MBR/GPT/raw devices, skips known
precious partitions, performs a block read test, and optionally performs a
single-block write/restore verification on non-precious partitions.
"""

import hashlib
import os
import re
import subprocess
import sys
import threading


# Precious partitions dictionary. This is a set of partition types that might
# contain firmware and should be skipped for read/write operations. The list is
# not exhaustive and may see additions in future.
PRECIOUS_PARTS_MBR = {
    "Protective partition": "0xF8",
    "EFI system partition": "0xEF",
}

PRECIOUS_PARTS_GPT = {
    "EFI System partition": "C12A7328-F81F-11D2-BA4B-00A0C93EC93B",
    "BIOS boot partition": "21686148-6449-6E6F-744E-656564454649",
    "U-Boot environment partition": "3DE21764-95BD-54BD-A5C3-4ABE786F38A8",
}

SEPARATOR = (
    "\n"
    "****************************************************************"
    "****************************************************************"
    "\n"
)


def run_command(command_args, check=False):
    """Run a command and return the completed process."""
    return subprocess.run(
        command_args,
        text=True,
        check=check,
        capture_output=True,
    )


def input_with_timeout(prompt, timeout=5):
    """Read user input with a timeout and return 'no' when no input is given."""
    print(prompt, end="", flush=True)
    input_queue = []

    def get_user_input():
        try:
            input_queue.append(sys.stdin.readline().strip())
        except EOFError:
            pass

    user_input_thread = threading.Thread(target=get_user_input)
    user_input_thread.daemon = True
    user_input_thread.start()
    user_input_thread.join(timeout)

    return input_queue[0] if input_queue else "no"


def calculate_sha256(file_path):
    """Calculate and return the SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as file_obj:
        for byte_block in iter(lambda: file_obj.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def get_partition_space(partition_path):
    """Return used and available 512-byte blocks for a partition."""
    command_result = run_command(
        ["df", "-B", "512", partition_path, "--output=used,avail"],
        check=True,
    )
    output_lines = command_result.stdout.strip().split("\n")

    if len(output_lines) > 1:
        fields = output_lines[1].split()
        used_block_count = int(fields[0])
        available_block_count = int(fields[1])
        return used_block_count, available_block_count

    print(f"WARNING: Unable to parse partition space for {partition_path}.")
    return 0, 0


def is_mounted(device):
    """Return True if the given device is mounted."""
    command_result = run_command(["findmnt", "-n", device])
    return command_result.returncode == 0


def is_mtd_block_device(device):
    """Return True if the device is an MTD block device."""
    return device.startswith("mtdblock")


def is_ram_disk(device):
    """Return True if the device is a RAM disk."""
    return device.startswith("ram")


def create_hello_file(file_path):
    """Create a 512-byte test file and return its SHA256 checksum."""
    hello_content = "Hello!".ljust(512, "\x00")

    with open(file_path, "wb") as file_obj:
        file_obj.write(hello_content.encode("utf-8"))

    return calculate_sha256(file_path)


def cleanup_files(file_paths):
    """Remove temporary files if they exist."""
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)


def restore_backup(partition_label, backup_filename, used_blocks):
    """Restore the backed-up block to the target partition."""
    print("INFO: Restoring the backup to the device after write check...")
    run_command(["dd", f"if={backup_filename}", f"of=/dev/{partition_label}",
                 "bs=512", "count=1", f"seek={used_blocks}"], check=True)
    print(f"INFO: Backup restored for /dev/{partition_label}.")


def perform_write_check(partition_label, partition_id, precious_parts):
    """Optionally perform a single-block write/read/restore check."""
    device_path = f"/dev/{partition_label}"

    if is_mounted(device_path):
        print(f"INFO: {device_path} is mounted, skipping write test.")
        return

    user_input = "no"
    if partition_id not in precious_parts.values():
        user_input = input_with_timeout(
            f"Do you want to perform a write check on {device_path}? (yes/no): ",
            5,
        ).lower()

    if user_input != "yes" or partition_id in precious_parts.values():
        return

    used_blocks, available_blocks = get_partition_space(device_path)
    if available_blocks <= 0:
        print(
            f"WARNING: No available space for write check on {device_path}. "
            "Skipping write check."
        )
        return

    hello_file = "hello.txt"
    read_back_file = "read_hello.txt"
    backup_filename = f"{partition_label}_backup.bin"

    original_sha256 = create_hello_file(hello_file)

    print("INFO: Creating backup of the current block before write check...")
    run_command(["dd", f"if={device_path}", f"of={backup_filename}",
                 "bs=512", "count=1", f"skip={used_blocks}"], check=True)

    print("INFO: Writing test data to the device for write check...")
    run_command(["dd", f"if={hello_file}", f"of={device_path}",
                 "bs=512", "count=1", f"seek={used_blocks}"], check=True)

    print("INFO: Reading back the test data for verification...")
    run_command(["dd", f"if={device_path}", f"of={read_back_file}",
                 "bs=512", "count=1", f"skip={used_blocks}"], check=True)

    read_back_sha256 = calculate_sha256(read_back_file)

    print(f"Original SHA256: {original_sha256}")
    print(f"Read-back SHA256: {read_back_sha256}")

    if original_sha256 == read_back_sha256:
        print(f"INFO: write check passed on {device_path}.")
    else:
        print(f"INFO: write check failed on {device_path}.")
        print(
            f"WARNING: Data integrity check failed for {device_path}. "
            "Possible data corruption."
        )

    restore_backup(partition_label, backup_filename, used_blocks)
    cleanup_files([hello_file, read_back_file, backup_filename])


def get_partition_labels(disk):
    """Return partition labels from lsblk without relying on Unicode output."""
    command_result = run_command(
        ["lsblk", "-rn", "-o", "NAME,TYPE", f"/dev/{disk}"]
    )
    labels = []

    for line in command_result.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 2 and columns[1] == "part":
            labels.append(columns[0])

    return labels


def get_disks():
    """Return detected disk block devices."""
    command_result = run_command(
        ["lsblk", "-e", "7", "-d", "-n", "-o", "NAME,TYPE"]
    )
    disks = []

    for line in command_result.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 2 and columns[1] == "disk":
            disks.append(columns[0])

    return disks


def get_partition_table_type(disk):
    """Return MBR, GPT, or RAW for the given disk."""
    command_result = run_command(
        ["timeout", "10", "gdisk", "-l", f"/dev/{disk}"]
    )

    if "MBR: MBR only" in command_result.stdout:
        return "MBR"

    if "GPT: present" in command_result.stdout:
        return "GPT"

    print(f"INFO: No valid partition table found for {disk}, treating as raw device.")
    return "RAW"


def get_partition_count(disk):
    """Return the number of partitions detected on the disk."""
    return len(get_partition_labels(disk))


def read_block(partition_label):
    """Perform a block read test for the given partition label."""
    command_result = run_command(["dd", f"if=/dev/{partition_label}",
                                  "of=/dev/null", "bs=1M", "count=1"])
    return command_result.returncode == 0


def process_raw_device(disk):
    """Process a raw block device with no partition table."""
    print(f"INFO: No partitions detected for {disk}, treating as raw device.")

    print(f"INFO: Performing block read on /dev/{disk}")
    if read_block(disk):
        print(f"INFO: Block read on /dev/{disk} successful")
        perform_write_check(disk, "", {})
    else:
        print(f"INFO: Block read on /dev/{disk} failed")

    print(SEPARATOR)


def parse_mbr_partition_ids(disk):
    """Parse MBR partition IDs from fdisk output."""
    table_header_row = [
        "Device", "Boot", "Start", "End", "Sectors", "Size", "Id", "Type",
    ]
    command_result = run_command(["fdisk", "-l", f"/dev/{disk}"])
    output_lines = command_result.stdout.strip().split("\n")
    should_collect_lines = False
    mbr_part_ids = []

    for line in output_lines:
        if should_collect_lines:
            columns = line.split()
            if len(columns) >= 6:
                if columns[1] == "*" and len(columns) >= 7:
                    mbr_part_ids.append("0x" + columns[6].upper())
                else:
                    mbr_part_ids.append("0x" + columns[5].upper())
        elif all(substring in line for substring in table_header_row):
            should_collect_lines = True

    return mbr_part_ids


def print_precious_partition_info(partition_label, partition_id, precious_parts):
    """Print details for a precious partition."""
    used_blocks, _ = get_partition_space(f"/dev/{partition_label}")

    for key, value in precious_parts.items():
        if value == partition_id:
            print(f"INFO: {partition_label} partition is PRECIOUS")
            print(
                f"INFO: Number of 512B blocks used on /dev/{partition_label}: "
                f"{used_blocks}"
            )
            print(f"      {key} : {value}")
            print("      Skipping block read/write...")
            break


def process_mbr_disk(disk, partition_labels, num_parts):
    """Process all MBR partitions on a disk."""
    mbr_part_ids = parse_mbr_partition_ids(disk)

    if len(mbr_part_ids) < num_parts:
        print(
            "WARNING: Could not parse enough MBR partition IDs. "
            f"Found {len(mbr_part_ids)}, expected {num_parts}."
        )

    process_count = min(len(partition_labels), len(mbr_part_ids), num_parts)

    for index in range(process_count):
        partition_label = partition_labels[index]
        partition_id = mbr_part_ids[index]

        print(f"\nINFO: Partition : /dev/{partition_label} Partition type : {partition_id}")

        if partition_id in PRECIOUS_PARTS_MBR.values():
            print_precious_partition_info(
                partition_label,
                partition_id,
                PRECIOUS_PARTS_MBR,
            )
            continue

        print(
            f"INFO: Performing block read on /dev/{partition_label} "
            f"mbr_part_id = {partition_id}"
        )

        if read_block(partition_label):
            print(
                f"INFO: Block read on /dev/{partition_label} "
                f"mbr_part_id = {partition_id} successful"
            )
            perform_write_check(partition_label, partition_id, PRECIOUS_PARTS_MBR)
        else:
            print(
                f"INFO: Block read on /dev/{partition_label} "
                f"mbr_part_id = {partition_id} failed"
            )

    print(SEPARATOR)


def parse_gpt_partition_info(disk, partition_index):
    """Return GPT partition GUID and platform-required bit."""
    command_result = run_command(
        ["sgdisk", f"-i={partition_index + 1}", f"/dev/{disk}"]
    )

    guid_regex = r"Partition GUID code: ([\w-]+) \("
    attr_flag_regex = r"Attribute flags: ([0-9A-Fa-f]+)"

    guid_code_match = re.search(guid_regex, command_result.stdout)
    attribute_flags_match = re.search(attr_flag_regex, command_result.stdout)

    if not guid_code_match or not attribute_flags_match:
        return None, None

    partition_guid_code = guid_code_match.group(1)
    attribute_flags_hex = attribute_flags_match.group(1)
    attribute_flags_int = int(attribute_flags_hex, 16)
    platform_required_bit = attribute_flags_int & 1

    return partition_guid_code, platform_required_bit


def process_gpt_disk(disk, partition_labels, num_parts):
    """Process all GPT partitions on a disk."""
    process_count = min(len(partition_labels), num_parts)

    for index in range(process_count):
        partition_label = partition_labels[index]
        partition_guid_code, platform_required_bit = parse_gpt_partition_info(
            disk, index
        )

        if not partition_guid_code:
            print(f"INFO: Unable to parse sgdisk info for {partition_label}. Skipping.")
            continue

        print(
            f"\nINFO: Partition : /dev/{partition_label} "
            f"Partition type GUID : {partition_guid_code} "
            f'"Platform required bit" : {platform_required_bit}'
        )

        if platform_required_bit == 1:
            print(
                f"INFO: Platform required attribute set for {partition_label} "
                "partition, skipping block read/write..."
            )
            continue

        if partition_guid_code in PRECIOUS_PARTS_GPT.values():
            print_precious_partition_info(
                partition_label,
                partition_guid_code,
                PRECIOUS_PARTS_GPT,
            )
            continue

        print(
            f"INFO: Performing block read on /dev/{partition_label} "
            f"part_guid = {partition_guid_code}"
        )

        if read_block(partition_label):
            print(
                f"INFO: Block read on /dev/{partition_label} "
                f"part_guid = {partition_guid_code} successful"
            )
            perform_write_check(
                partition_label,
                partition_guid_code,
                PRECIOUS_PARTS_GPT,
            )
        else:
            print(
                f"INFO: Block read on /dev/{partition_label} "
                f"part_guid = {partition_guid_code} failed"
            )

    print(SEPARATOR)


def print_detected_disks(disks):
    """Print detected block devices."""
    print(SEPARATOR)
    print("                                                    Read block devices tool")
    print(SEPARATOR)

    print("INFO: Detected following block devices with lsblk command :")
    for num, disk in enumerate(disks):
        print(f"{num}: {disk}")

    print(SEPARATOR)


def process_disk(disk):
    """Process a single disk block device."""
    if is_mtd_block_device(disk):
        print(f"INFO: Skipping MTD block device /dev/{disk}")
        return

    if is_ram_disk(disk):
        print(f"INFO: Skipping RAM disk /dev/{disk}")
        return

    print(f"INFO: Block device : /dev/{disk}")

    partition_table = get_partition_table_type(disk)
    print(f"INFO: Partition table type : {partition_table}\n")

    num_parts = get_partition_count(disk)

    if partition_table == "RAW" or num_parts == 0:
        process_raw_device(disk)
        return

    partition_labels = get_partition_labels(disk)

    if len(partition_labels) < num_parts:
        print(
            "WARNING: Mismatch in partition count. "
            f"Found {len(partition_labels)} partition labels, "
            f"but lsblk reported {num_parts} partitions for {disk}. "
            "Proceeding with the ones we have..."
        )

    if partition_table == "MBR":
        process_mbr_disk(disk, partition_labels, num_parts)
    elif partition_table == "GPT":
        process_gpt_disk(disk, partition_labels, num_parts)
    else:
        print(
            "INFO: Invalid partition table, expected MBR or GPT "
            f"reported type = {partition_table}"
        )


def main():
    """Main entry point."""
    disks = get_disks()
    print_detected_disks(disks)

    for disk in disks:
        process_disk(disk)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Error occurred: {error}")
        sys.exit(1)
