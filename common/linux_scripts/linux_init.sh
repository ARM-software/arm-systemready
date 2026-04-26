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

MODE="auto"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LINUX_DUMP_SH="$SCRIPT_DIR/linux_dump.sh"

usage() {
    cat <<EOF
Usage:
  $0 [--mode os|acs|auto]

Examples:
  ACS:
    /usr/bin/linux_init.sh --mode acs

  Normal OS:
    sudo ./linux_init.sh --mode os

Options:
  --mode os|acs|auto
      os    Run on installed OS.
      acs   Run inside ACS image.
      auto  Detect automatically.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --mode)
            MODE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Root privileges required. Re-running with sudo..."
    exec sudo "$0" --mode "$MODE"
fi

if [ "$MODE" = "auto" ]; then
    if [ -d /mnt/acs_tests ] || [ -d /mnt/acs_results ]; then
        MODE="acs"
    else
        MODE="os"
    fi
fi

case "$MODE" in
    os|acs)
        ;;
    *)
        echo "Invalid mode: $MODE"
        echo "Use: os, acs, or auto"
        exit 1
        ;;
esac

if [ "$MODE" = "os" ]; then
    set -x
fi

if [ "$MODE" = "acs" ]; then
    LOG_DIR="/mnt/acs_results/linux_dump"
else
    REAL_USER="${SUDO_USER:-${USER:-root}}"
    REAL_HOME=$(eval echo ~"$REAL_USER")
    LOG_DIR="$REAL_HOME/systemready-band-compliance-logs"
fi

mkdir -p "$LOG_DIR"

install_os_tools() {
    echo "Installing required tools on OS, if package manager is available"

    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        apt-get install -y acpica-tools pciutils usbutils dmidecode lshw efibootmgr net-tools iproute2 iputils-ping util-linux ethtool python3 gdisk wget curl
    elif command -v dnf >/dev/null 2>&1; then
        dnf check-update || true
        dnf install -y acpica-tools pciutils usbutils dmidecode lshw efibootmgr net-tools iproute iputils util-linux ethtool python3 gdisk wget curl
    elif command -v yum >/dev/null 2>&1; then
        yum check-update || true
        yum install -y acpica-tools pciutils usbutils dmidecode lshw efibootmgr net-tools iproute iputils util-linux ethtool python3 gdisk wget curl --nogpgcheck
    elif command -v zypper >/dev/null 2>&1; then
        zypper modifyrepo --all -e
        zypper refresh
        zypper install -y acpica pciutils usbutils dmidecode lshw efibootmgr net-tools iproute2 iputils util-linux ethtool python3 gdisk wget curl
    else
        echo "Unknown package manager. Continuing without installing packages."
    fi
}

run_linux_dump() {
    if [ ! -f "$LINUX_DUMP_SH" ]; then
        if [ -f /usr/bin/linux_dump.sh ]; then
            LINUX_DUMP_SH="/usr/bin/linux_dump.sh"
        else
            echo "linux_dump.sh not found"
            exit 1
        fi
    fi

    sh "$LINUX_DUMP_SH" "$MODE" "$LOG_DIR"
}

run_block_device_check() {
    echo "Running BLK devices read and write check"

    if [ "$MODE" = "acs" ]; then
        python3 /usr/bin/read_write_check_blk_devices.py </dev/null | tee "$LOG_DIR/read_write_check_blk_devices.log"
    else
        python3 "$SCRIPT_DIR/read_write_check_blk_devices.py" </dev/null | tee "$LOG_DIR/read_write_check_blk_devices.log"
    fi

    echo "BLK devices read and write check - Completed"
}

run_ethtool_check() {
    echo "Running Ethtool test Script"

    if [ "$MODE" = "acs" ]; then
        python3 /usr/bin/ethtool-test.py /mnt/acs_tests/config/system_config.txt | tee "$LOG_DIR/ethtool-test-temp.log"
    else
        python3 "$SCRIPT_DIR/ethtool-test.py" "$SCRIPT_DIR/system_config.txt" | tee "$LOG_DIR/ethtool-test-temp.log"
    fi

    awk '{gsub(/\x1B\[[0-9;]*[JKmsu]/, "")}1' "$LOG_DIR/ethtool-test-temp.log" > "$LOG_DIR/ethtool-test.log"
    rm -f "$LOG_DIR/ethtool-test-temp.log"

    echo "Ethtool script run - Completed"
}

create_os_archive() {
    if [ "$MODE" = "os" ]; then
        OLD_PWD=$(pwd)
        cd "$SCRIPT_DIR" || exit 1

        tar -czvf systemready-band-compliance-logs.tar.gz \
            -C "$REAL_HOME" systemready-band-compliance-logs

        cd "$OLD_PWD" || true
        echo "Created $SCRIPT_DIR/systemready-band-compliance-logs.tar.gz"
    fi
}

print_os_copy_instructions() {
    if [ "$MODE" = "os" ]; then
        echo ""
        echo "============================================================"
        echo "OS run completed."
        echo ""
        echo "Generated OS logs directory:"
        echo "  $LOG_DIR"
        echo ""
        echo "Generated archive:"
        echo "  $SCRIPT_DIR/systemready-band-compliance-logs.tar.gz"
        echo ""
        echo "Copy the generated OS logs into the ACS results template at:"
        echo "  acs_results_template/os-logs/<linux-os-name>/systemready-band-compliance-logs/"
        echo ""
        echo "Examples:"
        echo "  acs_results_template/os-logs/linux-redhat/systemready-band-compliance-logs/"
        echo "  acs_results_template/os-logs/linux-opensuse/systemready-band-compliance-logs/"
        echo ""
        echo "The ACS parser expects OS logs under:"
        echo "  os-logs/linux-*/systemready-band-compliance-logs/"
        echo "============================================================"
        echo ""
    fi
}

sync_results() {
    if [ "$MODE" = "acs" ]; then
        sync /mnt 2>/dev/null || sync
        sleep 5
    else
        sync
    fi
}

echo "linux_init.sh run started"
echo "Mode: $MODE"
echo "Log directory: $LOG_DIR"

if [ "$MODE" = "os" ]; then
    install_os_tools
fi

run_linux_dump
sync_results

run_block_device_check
sync_results

run_ethtool_check
sync_results

create_os_archive
print_os_copy_instructions

echo "linux_init.sh run completed"
