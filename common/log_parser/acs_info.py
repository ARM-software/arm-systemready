#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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

# Collects system information from various sources and generates acs_info.json

import argparse
import subprocess
import os
import re
import json
from datetime import datetime

def get_system_info(dmidecode_log_path):
    """
    Parse a saved dmidecode output file and return:
      - Vendor
      - System Name
      - SoC Family
      - Firmware Version
      - Summary Generated On
    """
    system_info = {
        "Firmware Version": "Unknown",
        "SoC Family": "Unknown",
        "System Name": "Unknown",
        "Vendor": "Unknown",
    }

    in_bios_info = False
    in_system_info = False

    # Regex to match key-value pairs in dmidecode output
    kv_re = re.compile(r"^\s*([A-Za-z0-9 /()._-]+)\s*:\s*(.*)\s*$")

    with open(dmidecode_log_path, "r", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")

            # Track which section we're in
            if line.strip() == "BIOS Information":
                in_bios_info = True
                in_system_info = False
                continue

            if line.strip() == "System Information":
                in_system_info = True
                in_bios_info = False
                continue

            # Reset section flags on new DMI handle
            if line.startswith("Handle 0x"):
                in_bios_info = False
                in_system_info = False
                continue

            m = kv_re.match(line)
            if not m:
                continue

            key, val = m.group(1).strip(), m.group(2).strip()

            # Extract BIOS Version
            if in_bios_info and key == "Version" and system_info["Firmware Version"] == "Unknown":
                system_info["Firmware Version"] = val
                continue

            # Extract System Information fields
            if in_system_info:
                if key == "Family" and system_info["SoC Family"] == "Unknown":
                    system_info["SoC Family"] = val
                elif key == "Product Name" and system_info["System Name"] == "Unknown":
                    system_info["System Name"] = val
                elif key == "Manufacturer" and system_info["Vendor"] == "Unknown":
                    system_info["Vendor"] = val

    system_info["Summary Generated On"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return system_info

def parse_config(config_path):
    """
    Reads a 'key: value' config file into a dictionary.
    Stops parsing at '# User-defined configs' marker.
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
    Reads 'UEFI v...' from UTF-16 encoded log file. Returns 'Unknown' if not found.
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

def extract_bmc_firmware_from_ipmitool_log(log_path):
    """Extract firmware revision from ipmitool mc info log output."""
    if not log_path or not os.path.isfile(log_path):
        warn_prefix = "\033[1;93mWARNING:"
        warn_suffix = "\033[0m"
        if not log_path:
            print(f"{warn_prefix} ipmitool log path not provided for BMC firmware extraction.{warn_suffix}")
        else:
            print(f"{warn_prefix} ipmitool log not found at {log_path}{warn_suffix}")
        return None
    fw_re = re.compile(r"^\s*Firmware\s+Revision\s*:\s*(.+)\s*$", re.IGNORECASE)
    with open(log_path, "r", errors="replace") as f:
        for raw in f:
            m = fw_re.match(raw)
            if m:
                return m.group(1).strip()
    return None

def get_bmc_firmware_version(ipmitool_log_path):
    """Return BMC firmware revision from ipmitool log or Unknown if missing."""
    value = extract_bmc_firmware_from_ipmitool_log(ipmitool_log_path)
    return value if value else "Unknown"

def is_systemready_band(acs_conf):
    # Return True only for SystemReady (not DeviceTree) band.
    band_val = (acs_conf or {}).get("Band", "").strip().lower()
    return band_val == "systemready band"



def main():
    """Entry point for acs_info.json generation."""
    parser = argparse.ArgumentParser(
        description="Collect ACS-like system info & summary data, then write to acs_info.txt & acs_info.json."
    )
    parser.add_argument("--acs_config_path", default="", help="Path to acs_config.txt (Band, version info, etc.)")
    parser.add_argument("--system_config_path", default="", help="Path to system_config.txt (extra system fields)")
    parser.add_argument("--uefi_version_log", default="", help="Path to uefi_version.log (UTF-16 or text)")
    parser.add_argument("--dmidecode_log", default=".", help="Path to dmidecode log")
    parser.add_argument("--output_dir", default=".", help="Directory where acs_info.txt and acs_info.json will be created.")
    parser.add_argument("--ipmitool_log", default="", help="Path to ipmitool mc info log for BMC firmware extraction")
    args = parser.parse_args()

    # Gather system info from dmidecode
    system_info = get_system_info(args.dmidecode_log)

    # Parse and merge config files
    acs_conf = parse_config(args.acs_config_path)
    sys_conf = parse_config(args.system_config_path)

    # 3) Merge them into system_info
    #    For instance, you might have 'ACS version', 'SRS version', etc. in acs_config.txt
    for k, v in acs_conf.items():
        system_info[k] = v
    for k, v in sys_conf.items():
        system_info[k] = v

    # Add UEFI and BMC firmware versions
    uefi_ver = get_uefi_version(args.uefi_version_log)
    if uefi_ver != 'Unknown':
        system_info['UEFI Version'] = uefi_ver
    if is_systemready_band(acs_conf):
        system_info['BMC Firmware Version'] = get_bmc_firmware_version(args.ipmitool_log)

    # Build ACS Results Summary
    band_val = acs_conf.get("Band", "Unknown")
    date_str = system_info.get('Summary Generated On', 'Unknown')

    acs_results_summary = {
        "Band": band_val,
        "Date": date_str,
    }

    # Assemble and write final JSON
    final_json = {
        "System Info": system_info,
        "ACS Results Summary": acs_results_summary
    }

    # Write to JSON
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "acs_info.json")
    with open(json_path, "w") as jf:
        json.dump(final_json, jf, indent=4)

    #print(f"acs_info.json created at: {json_path}")

if __name__ == "__main__":
    main()
