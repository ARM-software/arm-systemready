#!/bin/sh

# @file
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
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


# Ensure logs are created by minimal image

RESULTS_DIR="/mnt/acs_results_template/acs_results/network_boot"
RESULTS_LOG="${RESULTS_DIR}/network_boot_results.log"

status="PASSED"

mkdir -p "${RESULTS_DIR}"

# Linux results log must exist
if [ ! -f "${RESULTS_LOG}" ]; then
    echo "network_boot_results.log: FAILED (not found under ${RESULTS_DIR})" | tee -a "${RESULTS_LOG}"
    echo "Network_Boot_Result: FAILED" | tee -a "${RESULTS_LOG}"
    exit 0
fi

cat "${RESULTS_LOG}"
echo
# Check LSBLK/BLKID/DMESG log presence
if [ "${status}" = "PASSED" ]; then
    if [ -f "${RESULTS_DIR}/lsblk.txt" ] && \
       [ -f "${RESULTS_DIR}/blkid.txt" ] && \
       [ -f "${RESULTS_DIR}/dmesg.txt" ]; then

        echo "Logs captured: PASSED (lsblk, blkid and dmesg logs exist)" | tee -a "${RESULTS_LOG}"

    else
        echo "Logs captured: FAILED (expected lsblk.txt, blkid.txt, dmesg.txt)" \
        | tee -a "${RESULTS_LOG}"

        status="FAILED"
    fi
fi

echo

# Final PASS/FAIL result
if [ "${status}" = "PASSED" ]; then
    echo "Network_Boot_Result: PASSED" | tee -a "${RESULTS_LOG}"
else
    echo "Network_Boot_Result: FAILED" | tee -a "${RESULTS_LOG}"
fi
