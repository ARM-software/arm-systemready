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
  fwts_command="`python3 /mnt/acs_tests/parser/Parser.py -fwts`"
  fwts_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_fwts_run`"
fi

# FWTS (SBBR) Execution
echo "Executing FWTS for SBBR"
if [ "$automation_enabled" == "True" ] &&  [ "$fwts_enabled" == "False" ]; then
  echo "********* FWTS is disabled in config file**************"
else
  mkdir -p /mnt/acs_results/fwts
  echo "SystemReady band ACS v3.1.0" > /mnt/acs_results/fwts/FWTSResults.log
  if [ "$automation_enabled" == "False" ]; then
    fwts  -r stdout -q --uefi-set-var-multiple=1 --uefi-get-mn-count-multiple=1 --sbbr esrt uefibootpath aest cedt slit srat hmat pcct pdtt bgrt bert einj erst hest sdei nfit iort mpam ibft ras2 >> /mnt/acs_results/fwts/FWTSResults.log
  else
    $fwts_command >> /mnt/acs_results/fwts/FWTSResults.log
  fi
  sync /mnt
  sleep 5
  echo "FWTS Execution - Completed"
fi