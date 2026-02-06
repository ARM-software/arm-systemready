#!/bin/sh

# @file
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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

#run scmi-acs
cd /usr/bin
if [ -f /mnt/acs_results_template/acs_results/linux_acs/scmi_acs_app/arm_scmi_test_log.txt ]; then
    rm /mnt/acs_results_template/acs_results/linux_acs/scmi_acs_app/arm_scmi_test_log.txt
fi
mkdir -p /mnt/acs_results_template/acs_results/linux_acs/scmi_acs_app
#Run scmi tests
./scmi_test_agent
mv /usr/bin/arm_scmi_test_log.txt /mnt/acs_results_template/acs_results/linux_acs/scmi_acs_app/
echo "SCMI ACS Test Log:\n"
cat /mnt/acs_results_template/acs_results/linux_acs/scmi_acs_app/arm_scmi_test_log.txt
cd -

# ACS log parser run
echo "Running acs log parser tool "
RESULTS_DIR="/mnt/acs_results_template/acs_results"
if [ -d "$RESULTS_DIR" ]; then
  if [ -d "$RESULTS_DIR/acs_summary" ]; then
      rm -r $RESULTS_DIR/acs_summary
  fi
  /usr/bin/log_parser/main_log_parser.sh $RESULTS_DIR /mnt/acs_tests/config/acs_config.txt /mnt/acs_tests/config/system_config.txt /mnt/acs_tests/config/acs_waiver.json
  # Creating config directory in the results (secure flow)
  mkdir -p "$RESULTS_DIR/acs_summary/config"
  # Copy waiver and system config into results
  if [ -f /mnt/acs_tests/config/acs_waiver.json ]; then
    cp /mnt/acs_tests/config/acs_waiver.json "$RESULTS_DIR/acs_summary/config/"
  fi
  if [ -f /mnt/acs_tests/config/system_config.txt ]; then
    cp /mnt/acs_tests/config/system_config.txt "$RESULTS_DIR/acs_summary/config/"
  fi
  if [ -f /mnt/acs_tests/config/acs_run_config.ini ]; then
    cp /mnt/acs_tests/config/acs_run_config.ini "$RESULTS_DIR/acs_summary/config/"
  fi
  # Copying systemready-commit.log into result directory
  if [ -f /mnt/acs_tests/systemready-commit.log ]; then
    cp /mnt/acs_tests/systemready-commit.log "$RESULTS_DIR/acs_summary/config/"
  fi

  echo "Please wait acs results are syncing on storage medium."
  sync /mnt
  sleep 60
fi
