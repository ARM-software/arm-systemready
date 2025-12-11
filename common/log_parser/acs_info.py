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
import subprocess
import os
import re
import json
from datetime import datetime

def get_system_info():
    """
    Gathers system info from dmidecode (Vendor, System Name, SoC Family, Firmware Version)
    plus a date/time stamp. If you have a UEFI version log, you can merge that in later.
    """
    system_info = {}

    # Firmware Version
    try:
        fw_version_output = subprocess.check_output(
            ["dmidecode", "-t", "bios"], universal_newlines=True, stderr=subprocess.DEVNULL
        )
        for line in fw_version_output.split('\n'):
            if 'Version:' in line:
                system_info['Firmware Version'] = line.split('Version:')[1].strip()
                break
    except Exception:
        system_info['Firmware Version'] = 'Unknown'

    # SoC Family
    try:
        soc_family_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL
        )
        # Iterate each line looking for "Family:"
        for line in soc_family_output.split('\n'):
            if 'Family:' in line:
                system_info['SoC Family'] = line.split('Family:', 1)[1].strip()
                break
        else:
            # If we didn't find 'Family:'
            system_info['SoC Family'] = 'Unknown'
    except Exception:
        system_info['SoC Family'] = 'Unknown'

    # System Name
    try:
        system_name_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL
        )
        for line in system_name_output.split('\n'):
            if 'Product Name:' in line:
                system_info['System Name'] = line.split('Product Name:')[1].strip()
                break
        else:
            # If we didn't find 'Product Name:'
            system_info['System Name'] = 'Unknown'
    except Exception:
        system_info['System Name'] = 'Unknown'

    # Vendor
    try:
        vendor_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL
        )
        for line in vendor_output.split('\n'):
            if 'Manufacturer:' in line:
                system_info['Vendor'] = line.split('Manufacturer:')[1].strip()
                break
    except Exception:
        system_info['Vendor'] = 'Unknown'

    # Timestamp
    system_info['Summary Generated On'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return system_info

def parse_config(config_path):
    """
    Reads a simple 'key: value' config file, merges them into a dict.
    """
    config_info = {}
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, 'r') as cf:
                for line in cf:
                    # Stop parsing at the user-defined configs section
                    if line.strip().startswith('# User-defined configs'):
                        break
                    if ':' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split(':', 1)
                        config_info[key.strip()] = value.strip()
        except Exception as e:
            print(f"Warning: Could not parse {config_path}: {e}")
    else:
        if config_path:
            print(f"Config file {config_path} not provided or does not exist.")
    return config_info

def get_uefi_version(uefi_version_log):
    """
    Reads 'UEFI v...' from a log file if present. Returns 'Unknown' otherwise.
    """
    if uefi_version_log and os.path.isfile(uefi_version_log):
        try:
            with open(uefi_version_log, 'r', encoding='utf-16') as file:
                for line in file:
                    if 'UEFI v' in line:
                        return line.strip()
        except Exception as e:
            print(f"Warning: reading UEFI version log {uefi_version_log}: {e}")
    return 'Unknown'

def main():
    parser = argparse.ArgumentParser(
        description="Collect ACS-like system info & summary data, then write to acs_info.txt & acs_info.json."
    )
    parser.add_argument("--acs_config_path", default="", help="Path to acs_config.txt (Band, version info, etc.)")
    parser.add_argument("--system_config_path", default="", help="Path to system_config.txt (extra system fields)")
    parser.add_argument("--uefi_version_log", default="", help="Path to uefi_version.log (UTF-16 or text)")
    parser.add_argument("--output_dir", default=".", help="Directory where acs_info.txt and acs_info.json will be created.")
    args = parser.parse_args()

    # 1) Gather system info from dmidecode
    system_info = get_system_info()

    # 2) Parse config files
    acs_conf = parse_config(args.acs_config_path)
    sys_conf = parse_config(args.system_config_path)

    # 3) Merge them into system_info
    #    For instance, you might have 'ACS version', 'SRS version', etc. in acs_config.txt
    for k, v in acs_conf.items():
        system_info[k] = v
    for k, v in sys_conf.items():
        system_info[k] = v

    # 4) get UEFI version from log
    uefi_ver = get_uefi_version(args.uefi_version_log)
    if uefi_ver != 'Unknown':
        system_info['UEFI Version'] = uefi_ver

    # 5) Build an "ACS Results Summary"
    band_val = acs_conf.get("Band", "Unknown")
    date_str = system_info.get('Summary Generated On', 'Unknown')

    acs_results_summary = {
        "Band": band_val,
        "Date": date_str,
    }

    # 6) Prepare final JSON
    final_json = {
        "System Info": system_info,
        "ACS Results Summary": acs_results_summary
    }

    # 7) Write to JSON
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "acs_info.json")
    with open(json_path, "w") as jf:
        json.dump(final_json, jf, indent=4)

    #print(f"acs_info.json created at: {json_path}")

if __name__ == "__main__":
    main()
