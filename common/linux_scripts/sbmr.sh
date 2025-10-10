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
    sbmr_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_sbmr_in_band_run`"
fi

run_sbmr_in_band(){
    echo "Call SBMR ACS in-band test"
    cd /usr/bin
    python redfish-finder
    cd sbmr-acs
    ./run-sbmr-acs.sh linux
    mkdir -p /mnt/acs_results/sbmr
    cp -r logs /mnt/acs_results/sbmr/sbmr_in_band_logs
    cd /
    echo "SBMR ACS in-band run is completed\n"
}

  # Run SBMR-ACS In-Band Tests if run with grub option
if [ "$automation_enabled" == "True" ] &&  [ "$sbmr_enabled" == "False" ]; then
    echo "********* SBMR in-band test is disabled in config file**************"
else
    run_sbmr_in_band
    sync /mnt
    sleep 3
    echo "NOTE: This ACS image runs SBMR IN-BAND tests ONLY." 1>&2
    echo "For SBMR OUT-OF-BAND tests, see: https://github.com/ARM-software/sbmr-acs.git" 1>&2
    echo "Please press <Enter> to continue ..."
    exec sh +m
fi