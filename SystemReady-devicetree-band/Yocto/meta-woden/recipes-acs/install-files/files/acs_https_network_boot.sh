#!/bin/sh

# @file
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

# HTTPS/HTTP Network Boot preparation script for SystemReady-devicetree-band
# - Reads HTTPS_BOOT_IMAGE_URL from /mnt/acs_tests/config/system_config.txt
# - Ensures a system ESP exists
# - Checks URL reachability with wget --spider
# - Writes acs_https.conf.nsh for https_boot.nsh / ledge.efi
# - Sets https_boot_pending.flag and reboots (only on full success)

echo "============== Starting Network Boot Checks =============="

HTTPS_CONFIG_DIR="/mnt/acs_tests/config"
HTTPS_FLAG_DIR="/mnt/acs_tests/app"
SYSTEM_CONFIG_FILE="${HTTPS_CONFIG_DIR}/system_config.txt"
HTTPS_CONF_NSH="${HTTPS_CONFIG_DIR}/acs_https.conf.nsh"
HTTPS_PENDING_FLAG="${HTTPS_FLAG_DIR}/https_boot_pending.flag"

RESULTS_DIR="/mnt/acs_results_template/acs_results/network_boot"
RESULTS_LOG="${RESULTS_DIR}/network_boot_results.log"

detect_system_esp() {
    # GPT partition type GUID for EFI System Partition (ESP)
    ESP_GUID="c12a7328-f81f-11d2-ba4b-00a0c93ec93b"

    # Return 0 if at least one system ESP is detected
    if command -v lsblk >/dev/null 2>&1; then
        ESP_LINES="$(lsblk -rno NAME,PARTTYPE,PARTLABEL,MOUNTPOINT 2>/dev/null \
            | awk 'tolower($0) !~ /boot_acs/ && (tolower($2) ~ /'"$ESP_GUID"'/ || tolower($3) ~ /efi system partition/ || tolower($4) ~ /\/boot\/efi|\/efi/ )')"
        if [ -n "${ESP_LINES}" ]; then
            echo "Detected potential system ESP partition(s):"
            echo "${ESP_LINES}"
            return 0
        fi
    fi

    if command -v blkid >/dev/null 2>&1; then
        ESP_BLKID="$(blkid 2>/dev/null | grep -vi 'BOOT_ACS' | grep -Ei "EFI System Partition|PARTUUID=.*$ESP_GUID")"
        if [ -n "${ESP_BLKID}" ]; then
            echo "Detected potential system ESP via blkid:"
            echo "${ESP_BLKID}"
            return 0
        fi
    fi

    return 1
}

main() {
    mkdir -p "${RESULTS_DIR}"
    : > "${RESULTS_LOG}"
    {
        echo "[INFO] network_boot_checks"
        date
    } >> "${RESULTS_LOG}"

    # Check BOOT_ACS mount
    if ! mountpoint -q /mnt ; then
        echo "/mnt is not a mountpoint; cannot access acs_tests/config, skipping Network boot setup."
        {
            echo "BOOT_ACS mount: FAILED (/mnt is not available; cannot access ACS configuration)"
            echo "Network_Boot_Result: FAILED"
        } >> "${RESULTS_LOG}"
        return 0
    fi

    # Check system_config.txt
    if [ ! -f "${SYSTEM_CONFIG_FILE}" ]; then
        echo "system_config.txt not found at ${SYSTEM_CONFIG_FILE}; skipping Network boot setup."
        {
            echo "system_config.txt: FAILED ( not found at ${SYSTEM_CONFIG_FILE})"
            echo "Network_Boot_Result: FAILED"
        } >> "${RESULTS_LOG}"
        return 0
    fi

    # Extract HTTPS_BOOT_IMAGE_URL
    IMAGE_URL="$(grep -E '^[[:space:]]*HTTPS_BOOT_IMAGE_URL=' "${SYSTEM_CONFIG_FILE}" \
                 | grep -v '^[[:space:]]*#' \
                 | head -n 1 \
                 | sed -e 's/^[[:space:]]*HTTPS_BOOT_IMAGE_URL=//' -e 's/^[[:space:]]*//')"

    if [ -z "${IMAGE_URL}" ]; then
        echo "HTTPS_BOOT_IMAGE_URL not set or commented in system_config.txt; skipping Network boot setup."
        {
            echo "Image URL: FAILED (not found or is commented out in system_config.txt)"
            echo "Network_Boot_Result: FAILED"
        } >> "${RESULTS_LOG}"
        return 0
    fi

    echo "Found HTTPS_BOOT_IMAGE_URL=${IMAGE_URL} in system_config.txt"
    echo "Image URL: PASSED (URL Found: ${IMAGE_URL})" >> "${RESULTS_LOG}"

    # Ensure system ESP exists
    if ! detect_system_esp; then
        echo "ERROR: No EFI System Partition (ESP) detected on the system."
        echo "Cannot proceed with network boot: ESP partition is a requirement."
        {
            echo "EFI System Partition (ESP): FAILED (not detected on the system; network boot requires a valid ESP)"
            echo "Network_Boot_Result: FAILED"
        } >> "${RESULTS_LOG}"
        return 0
    fi

    echo "EFI System Partition (ESP): PASSED (detected ESP on the system)" >> "${RESULTS_LOG}"

    # Parse scheme and hostpath
    case "${IMAGE_URL}" in
        http://* )
            HTTPS_IMAGE_SCHEME="http"
            HTTPS_IMAGE_HOSTPATH="${IMAGE_URL#http://}"
            ;;
        https://* )
            HTTPS_IMAGE_SCHEME="https"
            HTTPS_IMAGE_HOSTPATH="${IMAGE_URL#https://}"
            ;;
        * )
            echo "Unsupported URL scheme in ${IMAGE_URL}. Expected http:// or https://"
            {
                echo "URL scheme: FAILED ( Unsupported URL in HTTPS_BOOT_IMAGE_URL (${IMAGE_URL}), expected http:// or https://)"
                echo "Network_Boot_Result: FAILED"
            } >> "${RESULTS_LOG}"
            return 0
            ;;
    esac

    if [ -z "${HTTPS_IMAGE_HOSTPATH}" ]; then
        echo "Parsed HOSTPATH is empty, unable to configure Network boot."
        {
            echo "Image HOSTPATH: FAILED (Image URL is empty, cannot construct network boot URL)"
            echo "Network_Boot_Result: FAILED"
        } >> "${RESULTS_LOG}"
        return 0
    fi

    echo "Image HOSTPATH: PASSED (Image URL is Valid)" >> "${RESULTS_LOG}"

    # Wget reachability check
    if command -v wget >/dev/null 2>&1; then
        echo "Checking URL reachability with wget --spider: ${IMAGE_URL}"
        if wget --spider --timeout=20 -q "${IMAGE_URL}"; then
            echo "URL is accessible through wget."
            echo "Wget check on URL: PASSED (URL is reachable using wget --spider)" >> "${RESULTS_LOG}"
        else
            echo "WARNING: URL is NOT accessible through wget (wget --spider failed)."
            {
                echo "wget check on URL: FAILED (URL is not accessible using wget --spider)"
                echo "Network_Boot_Result: FAILED"
            } >> "${RESULTS_LOG}"
            return 0
        fi
    fi

    # Prepare https config and flag for UEFI https_boot.nsh
    mkdir -p "${HTTPS_CONFIG_DIR}" "${HTTPS_FLAG_DIR}"

    cat > "${HTTPS_CONF_NSH}" <<EOF
# Auto-generated by acs_https_network_boot.sh for HTTPS/HTTP network boot
set HTTPS_IMAGE_URL ${IMAGE_URL}
set HTTPS_IMAGE_HOSTPATH ${HTTPS_IMAGE_HOSTPATH}
set HTTPS_IMAGE_SCHEME ${HTTPS_IMAGE_SCHEME}
EOF

    sync
    sleep 5

    # Set flag for UEFI startup_dt.nsh to run https_boot.nsh on next boot
    : > "${HTTPS_PENDING_FLAG}"
    echo "Created flag ${HTTPS_PENDING_FLAG}"
    echo "Rebooting system for Network boot via UEFI shell"
    sync
    sleep 5
    umount /mnt
    sleep 5

    if command -v reboot >/dev/null 2>&1; then
        reboot
    elif command -v systemctl >/dev/null 2>&1; then
        systemctl reboot
    else
        echo b > /proc/sysrq-trigger
    fi
}

main "$@"
