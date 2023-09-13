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

# This script parses for ethernet interfaces using ip tool and runs ethtool
# self-test if the interface supports.

import subprocess

def print_color(text, color="default"):
    colors = {
        "default": "\033[0m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
    }

    color_code = colors.get(color, colors["default"])
    color_default = colors["default"]
    print(color_code + text + color_default)

if __name__ == "__main__":

    try:
        # Run ip link command to list all network interfaces
        ip_command = "ip -o link"
        output = subprocess.check_output(ip_command, shell=True).decode("utf-8").split('\n')

        ether_interfaces = []

        # Iterate through the reported interfaces
        for line in output:
            parts = line.split()
            if len(parts) < 2:
                continue

            interface_name = parts[1].rstrip(':')
            # Check if the line contains "ether"
            if "ether" in line:
                ether_interfaces.append(interface_name)

        print("\n****************************************************************\n")
        print_color("                         Running ethtool\n", "green")
        print("****************************************************************")

        # print the the ethernet interfaces if available.
        if len(ether_interfaces) == 0:
            print_color("INFO: No ethernet interfaces detected via ip linux command, Exiting ...", "yellow")
            exit(1)
        else:
            print_color("INFO: Detected following ethernet interfaces via ip command :", "green")
            for index, intrf in enumerate(ether_interfaces):
                print_color(f"{index}: {intrf}", "yellow")

        print("\n****************************************************************\n")
        for index, intrf in enumerate(ether_interfaces):
            # Dump ethtool prints for each ethernet interface reported
            print_color(f"INFO: Running \"ethtool {intrf} \" :", "green")
            command = f"ethtool {intrf}"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            print(result.stdout)
            print(result.stderr)

            # Run ethernet self-test if the drivers supports it
            command = f"ethtool -i {intrf}"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if "supports-test: yes" in result.stdout:
                print_color(f"INFO: Ethernet interface {intrf} supports ethtool self test.", "green")
                command = f"ethtool -t {intrf}"
                print_color(f"INFO: Running {command} :", "green")
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                print(result.stdout)
                print(result.stderr)
            else:
                print_color(f"INFO: Ethernet interface {intrf} doesn't supports ethtool self test", "green")
            print("\n****************************************************************\n")
            exit(0)
    except Exception as e:
        print_color(f"Error occurred: {e}", "red")
        exit(1)
