#!/bin/sh

# @file
# Copyright (c) 2021-2025, Arm Limited or its affiliates. All rights reserved.
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

# Parse config file
automation_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation`"
if [ "$automation_enabled" == "True" ]; then
    sbsa_command="`python3 /mnt/acs_tests/parser/Parser.py -sbsa`"
    sbsa_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_sbsa_run`"
fi

# Linux SBSA Execution
echo "Running Linux SBSA tests"
if [ "$automation_enabled" == "True" ] &&  [ "$sbsa_enabled" == "False" ]; then
  echo "********* SBSA is disabled in config file**************"
else
  if [ -f  /lib/modules/sbsa_acs.ko ]; then
    insmod /lib/modules/sbsa_acs.ko
    echo "SystemReady band ACS v3.1.0" > /mnt/acs_results/linux/SbsaResultsApp.log
    if [ "$automation_enabled" == "False" ]; then
      /bin/sbsa >> /mnt/acs_results/linux/SbsaResultsApp.log
    else
      $sbsa_command >> /mnt/acs_results/linux/SbsaResultsApp.log
    fi
    dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux/SbsaResultsKernel.log
    sync /mnt
    sleep 5
    echo "Linux SBSA test Execution - Completed"
  else
    echo "Error: SBSA kernel Driver is not found. Linux SBSA tests cannot be run."
  fi
fi