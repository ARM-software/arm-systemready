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

# Spin-table usage checker for SystemReady DeviceTree ACS.
#
# Usage:
#   ./spin_table_checker.sh /mnt/acs_results_template/acs_results/uefi_dump/ebbr_profile_table.log
#
# Return codes:
#   0 = PASS/SKIP/WARNING  No spin-table/cpu-release-addr found, test skipped,
#                          or warning for EBBR below 2.3.0/unknown EBBR version
#   1 = FAIL               spin-table or cpu-release-addr found for EBBR 2.3.0 or newer

set +e

LINUX_TOOLS="/mnt/acs_results_template/acs_results/linux_tools"
UEFI_DIR="/mnt/acs_results_template/acs_results/uefi"
DMESG_LOG="/mnt/acs_results_template/acs_results/linux_dump/dmesg.log"
OUT="$LINUX_TOOLS/spin_table_checker.log"

EBBR_LOG="$1"

# Use of Spin table protocol is strongly discouraged before EBBR 2.3.0.
# For EBBR 2.3.0 and newer, spin-table evidence causes FAIL.
FAIL_MAJOR=2
FAIL_MINOR=3
FAIL_PATCH=0

FOUND_SPIN_TABLE=0
FOUND_CPU_RELEASE_ADDR=0
FOUND_PSCI_INFO=0
CHECKED_DT_ARTIFACTS=0
FAIL_ON_SPIN_TABLE=0
EBBR_VERSION_KNOWN=0

mkdir -p "$LINUX_TOOLS"
: > "$OUT"

print_header()
{
    echo "" | tee -a "$OUT"
    echo "======================================================================" | tee -a "$OUT"
    echo "$1" | tee -a "$OUT"
    echo "======================================================================" | tee -a "$OUT"
}

version_ge()
{
    major="$1"
    minor="$2"
    patch="$3"

    if [ "$major" -gt "$FAIL_MAJOR" ]; then
        return 0
    fi

    if [ "$major" -lt "$FAIL_MAJOR" ]; then
        return 1
    fi

    if [ "$minor" -gt "$FAIL_MINOR" ]; then
        return 0
    fi

    if [ "$minor" -lt "$FAIL_MINOR" ]; then
        return 1
    fi

    if [ "$patch" -ge "$FAIL_PATCH" ]; then
        return 0
    fi

    return 1
}

detect_ebbr_version()
{
    if [ ! -f "$EBBR_LOG" ]; then
        echo "INFO: EBBR profile table log not found: $EBBR_LOG" | tee -a "$OUT"
        echo "INFO: Running spin-table checks, but spin-table evidence will be reported as WARNING only." | tee -a "$OUT"
        return 1
    fi

    echo "EBBR profile table log: $EBBR_LOG" | tee -a "$OUT"

    # Parse current EBBR profile table log format from uefi_dump.
    # Example:
    #   INFO: EBBR profile table GUID[0] : CCE33C35-74AC-4087-BCE7-8B29B02EEB27
    guid="$(grep -aEi 'EBBR profile table GUID\[[0-9]+\][[:space:]]*:' "$EBBR_LOG" 2>/dev/null | tail -n 1 | sed 's/.*:[[:space:]]*//' | tr 'A-F' 'a-f' | sed 's/[^0-9a-f]//g')"

    case "$guid" in
        cce33c3574ac4087bce78b29b02eeb27)
            EBBR_VERSION="2.1.0"
            return 0
            ;;
        9073eed4e50d11eeb8b08b68da62fc80)
            EBBR_VERSION="2.2.0"
            return 0
            ;;
        7721fc77a72411ef8eaaf7c9b194ba75)
            EBBR_VERSION="2.3.0"
            return 0
            ;;
        f2bb0422da8e11f0a67b1be220854098)
            EBBR_VERSION="2.4.0"
            return 0
            ;;
    esac

    echo "INFO: Could not identify EBBR version from $EBBR_LOG." | tee -a "$OUT"
    echo "INFO: Running spin-table checks, but spin-table evidence will be reported as WARNING only." | tee -a "$OUT"
    return 1
}

check_live_dt()
{
    LIVE_DT="/sys/firmware/devicetree/base"

    print_header "Checking live device tree"

    if [ ! -d "$LIVE_DT/cpus" ]; then
        echo "SKIP: $LIVE_DT/cpus not found" | tee -a "$OUT"
        return
    fi

    CHECKED_DT_ARTIFACTS=$((CHECKED_DT_ARTIFACTS + 1))
    echo "Path: $LIVE_DT" | tee -a "$OUT"

    for f in $(find "$LIVE_DT/cpus" -path '*/enable-method' -type f 2>/dev/null | sort -u); do
        val="$(tr '\000' ' ' < "$f" 2>/dev/null | sed 's/[[:space:]]*$//')"
        echo "$f = $val" | tee -a "$OUT"

        case "$val" in
            *spin-table*)
                FOUND_SPIN_TABLE=1
                echo "[FAIL-EVIDENCE] spin-table enable-method found: $f = $val" | tee -a "$OUT"
                ;;
            *psci*)
                FOUND_PSCI_INFO=1
                echo "[INFO] PSCI enable-method found: $f = $val" | tee -a "$OUT"
                ;;
        esac
    done

    for f in $(find "$LIVE_DT/cpus" -name cpu-release-addr -type f 2>/dev/null | sort -u); do
        FOUND_CPU_RELEASE_ADDR=1
        echo "[FAIL-EVIDENCE] cpu-release-addr found: $f" | tee -a "$OUT"
    done

    if [ -d "$LIVE_DT/psci" ]; then
        compat="$(tr '\000' ' ' < "$LIVE_DT/psci/compatible" 2>/dev/null | sed 's/[[:space:]]*$//')"
        method="$(tr '\000' ' ' < "$LIVE_DT/psci/method" 2>/dev/null | sed 's/[[:space:]]*$//')"

        FOUND_PSCI_INFO=1
        echo "$LIVE_DT/psci/compatible = $compat" | tee -a "$OUT"
        echo "$LIVE_DT/psci/method = $method" | tee -a "$OUT"
        echo "[INFO] PSCI node found" | tee -a "$OUT"
    fi
}

check_acs_dts()
{
    DTS_FILE="$LINUX_TOOLS/device_tree.dts"

    print_header "Checking ACS generated device_tree.dts"

    if [ ! -f "$DTS_FILE" ]; then
        echo "SKIP: $DTS_FILE not found" | tee -a "$OUT"
        return
    fi

    CHECKED_DT_ARTIFACTS=$((CHECKED_DT_ARTIFACTS + 1))
    echo "Path: $DTS_FILE" | tee -a "$OUT"

    grep -aEin 'enable-method|spin-table|cpu-release-addr|psci|arm,psci|method[[:space:]]*=' "$DTS_FILE" 2>/dev/null | tee -a "$OUT"

    if grep -aEiq 'enable-method[[:space:]]*=[[:space:]]*"spin-table"|enable-method.*spin-table|spin-table' "$DTS_FILE" 2>/dev/null; then
        FOUND_SPIN_TABLE=1
        echo "[FAIL-EVIDENCE] device_tree.dts contains spin-table evidence" | tee -a "$OUT"
    fi

    if grep -aEiq 'cpu-release-addr' "$DTS_FILE" 2>/dev/null; then
        FOUND_CPU_RELEASE_ADDR=1
        echo "[FAIL-EVIDENCE] device_tree.dts contains cpu-release-addr" | tee -a "$OUT"
    fi

    if grep -aEiq 'enable-method[[:space:]]*=[[:space:]]*"psci"|enable-method.*psci|arm,psci|psci[[:space:]]*\{|method[[:space:]]*=[[:space:]]*"(smc|hvc)"' "$DTS_FILE" 2>/dev/null; then
        FOUND_PSCI_INFO=1
        echo "[INFO] device_tree.dts contains PSCI evidence" | tee -a "$OUT"
    fi
}

check_uefi_dtb()
{
    UEFI_DTB="$UEFI_DIR/BsaDevTree.dtb"
    UEFI_DTS="/tmp/BsaDevTree_spin_table_check.dts"

    print_header "Checking UEFI BsaDevTree.dtb"

    if [ ! -f "$UEFI_DTB" ]; then
        echo "SKIP: $UEFI_DTB not found" | tee -a "$OUT"
        return
    fi

    CHECKED_DT_ARTIFACTS=$((CHECKED_DT_ARTIFACTS + 1))
    echo "Path: $UEFI_DTB" | tee -a "$OUT"

    if ! command -v dtc >/dev/null 2>&1; then
        echo "SKIP: dtc not found; cannot decompile $UEFI_DTB" | tee -a "$OUT"
        return
    fi

    dtc -I dtb -O dts -o "$UEFI_DTS" "$UEFI_DTB" 2>>"$OUT"

    if [ ! -s "$UEFI_DTS" ]; then
        echo "SKIP: failed to decompile $UEFI_DTB" | tee -a "$OUT"
        rm -f "$UEFI_DTS"
        return
    fi

    grep -aEin 'enable-method|spin-table|cpu-release-addr|psci|arm,psci|method[[:space:]]*=' "$UEFI_DTS" 2>/dev/null | tee -a "$OUT"

    if grep -aEiq 'enable-method[[:space:]]*=[[:space:]]*"spin-table"|enable-method.*spin-table|spin-table' "$UEFI_DTS" 2>/dev/null; then
        FOUND_SPIN_TABLE=1
        echo "[FAIL-EVIDENCE] BsaDevTree.dtb contains spin-table evidence" | tee -a "$OUT"
    fi

    if grep -aEiq 'cpu-release-addr' "$UEFI_DTS" 2>/dev/null; then
        FOUND_CPU_RELEASE_ADDR=1
        echo "[FAIL-EVIDENCE] BsaDevTree.dtb contains cpu-release-addr" | tee -a "$OUT"
    fi

    if grep -aEiq 'enable-method[[:space:]]*=[[:space:]]*"psci"|enable-method.*psci|arm,psci|psci[[:space:]]*\{|method[[:space:]]*=[[:space:]]*"(smc|hvc)"' "$UEFI_DTS" 2>/dev/null; then
        FOUND_PSCI_INFO=1
        echo "[INFO] BsaDevTree.dtb contains PSCI evidence" | tee -a "$OUT"
    fi

    rm -f "$UEFI_DTS"
}

check_dmesg_info()
{
    print_header "Checking dmesg summary for information only"

    if [ ! -f "$DMESG_LOG" ]; then
        echo "SKIP: $DMESG_LOG not found" | tee -a "$OUT"
        return
    fi

    echo "Path: $DMESG_LOG" | tee -a "$OUT"
    grep -aiE 'psci|spin-table|cpu-release|release-addr|smp: Bringing up|smp: Brought up' "$DMESG_LOG" 2>/dev/null | tee -a "$OUT"

    if grep -aiq 'psci' "$DMESG_LOG" 2>/dev/null; then
        FOUND_PSCI_INFO=1
        echo "[INFO] dmesg contains PSCI evidence" | tee -a "$OUT"
    fi

    if grep -aiEq 'spin-table|cpu-release|release-addr' "$DMESG_LOG" 2>/dev/null; then
        echo "[INFO] dmesg contains spin-table/cpu-release text, but dmesg is informational only and does not affect PASS/FAIL" | tee -a "$OUT"
    fi
}

echo "======================================================================" | tee -a "$OUT"
echo "Spin-table checker started" | tee -a "$OUT"
echo "======================================================================" | tee -a "$OUT"
echo "Date: $(date)" | tee -a "$OUT"
echo "Output log: $OUT" | tee -a "$OUT"

print_header "Checking EBBR profile version"

if detect_ebbr_version; then
    EBBR_VERSION_KNOWN=1

    echo "Detected EBBR version: $EBBR_VERSION" | tee -a "$OUT"
    echo "INFO: Spin-table evidence causes FAIL for EBBR 2.3.0 or newer." | tee -a "$OUT"
    echo "INFO: Spin-table evidence is reported as WARNING for EBBR below 2.3.0 or unknown EBBR version." | tee -a "$OUT"

    major="$(echo "$EBBR_VERSION" | cut -d. -f1)"
    minor="$(echo "$EBBR_VERSION" | cut -d. -f2)"
    patch="$(echo "$EBBR_VERSION" | cut -d. -f3)"

    if [ -z "$patch" ]; then
        patch=0
    fi

    if version_ge "$major" "$minor" "$patch"; then
        FAIL_ON_SPIN_TABLE=1
    fi
else
    EBBR_VERSION="unknown"
    EBBR_VERSION_KNOWN=0
    FAIL_ON_SPIN_TABLE=0
fi

check_live_dt
check_acs_dts
check_uefi_dtb
check_dmesg_info

print_header "Final result"

echo "checked_dt_artifacts=$CHECKED_DT_ARTIFACTS" | tee -a "$OUT"
echo "found_spin_table=$FOUND_SPIN_TABLE" | tee -a "$OUT"
echo "found_cpu_release_addr=$FOUND_CPU_RELEASE_ADDR" | tee -a "$OUT"
echo "found_psci_info=$FOUND_PSCI_INFO" | tee -a "$OUT"

if [ "$FOUND_SPIN_TABLE" -eq 1 ] || [ "$FOUND_CPU_RELEASE_ADDR" -eq 1 ]; then
    if [ "$FAIL_ON_SPIN_TABLE" -eq 1 ]; then
        echo "RESULT: FAIL" | tee -a "$OUT"
        echo "INFO: Deprecated spin-table usage/configuration found in checked DT artifacts." | tee -a "$OUT"
        echo "INFO: EBBR version $EBBR_VERSION is 2.3.0 or newer." | tee -a "$OUT"
        rc=1
    else
        echo "RESULT: WARNING" | tee -a "$OUT"
        echo "INFO: Spin-table usage/configuration found in checked DT artifacts." | tee -a "$OUT"
        echo "INFO: Use of Spin table protocol is strongly discouraged." | tee -a "$OUT"

        if [ "$EBBR_VERSION_KNOWN" -eq 1 ]; then
            echo "INFO: EBBR version $EBBR_VERSION is below 2.3.0, so this is reported as WARNING instead of FAIL." | tee -a "$OUT"
        else
            echo "INFO: EBBR version is unknown, so this is reported as WARNING instead of FAIL." | tee -a "$OUT"
        fi

        rc=0
    fi
elif [ "$CHECKED_DT_ARTIFACTS" -gt 0 ]; then
    echo "RESULT: PASS" | tee -a "$OUT"
    echo "INFO: No spin-table or cpu-release-addr evidence found in checked DT artifacts." | tee -a "$OUT"
    rc=0
else
    echo "RESULT: SKIP" | tee -a "$OUT"
    echo "INFO: No DT artifact could be checked." | tee -a "$OUT"
    rc=0
fi

if [ "$FOUND_PSCI_INFO" -eq 1 ]; then
    echo "INFO: PSCI evidence was also found, but PSCI is informational only for this check." | tee -a "$OUT"
fi

echo "NOTE: dmesg is parsed for information only and does not affect PASS/FAIL." | tee -a "$OUT"
echo "NOTE: This script checks whether spin-table is exposed in OS-visible/captured DT artifacts. It cannot prove whether unused spin-table code exists in firmware source." | tee -a "$OUT"

exit "$rc"
