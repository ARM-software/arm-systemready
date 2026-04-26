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

MODE="${1:-os}"
LOG_DIR="${2:-}"

if [ -z "$LOG_DIR" ]; then
    echo "ERROR: LOG_DIR argument missing"
    exit 1
fi

mkdir -p "$LOG_DIR"
cd "$LOG_DIR" || exit 1

echo "Collecting Linux Debug Dump"

if [ "$MODE" = "acs" ]; then
    ORIG_SYS_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
fi

dmesg > dmesg.txt 2>&1
lspci > lspci.txt 2>&1
lspci -vvv > lspci-vvv.txt 2>&1
cat /proc/interrupts > cat-proc-interrupts.txt 2>&1
cat /proc/cpuinfo > cat-proc-cpuinfo.txt 2>&1
cat /proc/meminfo > cat-proc-meminfo.txt 2>&1
cat /proc/iomem > cat-proc-iomem.txt 2>&1
lscpu > lscpu.txt 2>&1
lsblk > lsblk.txt 2>&1
lsusb > lsusb.txt 2>&1
lshw > lshw.txt 2>&1

dmidecode > dmidecode.txt 2>&1
dmidecode --dump-bin dmidecode.bin >> dmidecode.txt 2>&1

uname -a > uname-a.txt 2>&1
cat /etc/os-release > cat-etc-os-release.txt 2>&1
date > date.txt 2>&1

if [ "$MODE" = "os" ]; then
    timedatectl > timedatectl.txt 2>&1
fi

cat /proc/driver/rtc > cat-proc-driver-rtc.txt 2>&1
hwclock > hwclock.txt 2>&1

efibootmgr > efibootmgr.txt 2>&1
efibootmgr -t 20 > efibootmgr-t-20.txt 2>&1
efibootmgr -t 5 > efibootmgr-t-5.txt 2>&1
efibootmgr -c > efibootmgr-c.txt 2>&1

ifconfig > ifconfig.txt 2>&1
ip addr show > ip-addr-show.txt 2>&1
ping -c 5 www.arm.com > ping-c-5-www-arm-com.txt 2>&1

cat /proc/cmdline > cat-proc-cmdline.txt 2>&1
df -h > df-h.txt 2>&1
mount > mount.txt 2>&1
lsmod > lsmod.txt 2>&1

acpidump > acpi.log 2>&1
acpixtract -a acpi.log > acpixtract.txt 2>&1
iasl -d *.dat > iasl.txt 2>&1

date --set="20221215 05:30" > date-set-202212150530.txt 2>&1
date > date-after-set.txt 2>&1

hwclock --set --date "2023-01-01 09:10:15" > hw-clock-set-20230101091015.txt 2>&1
hwclock > hwclock-after-set.txt 2>&1

ls -lR /sys/firmware > firmware.txt 2>&1
cp -r /sys/firmware . >> firmware.txt 2>&1

if [ "$MODE" = "acs" ]; then
    ipmitool -C 17 -N 3 -p 623 mc info > ipmitool.txt 2>&1

    mount -t debugfs none /sys/kernel/debug > debugfs-mount.txt 2>&1 || true
    cat /sys/kernel/debug/psci > psci.txt 2>&1
    dmesg | grep -i psci > psci-kernel.txt 2>&1

    date --set="$ORIG_SYS_TIME" > date-restore-original.txt 2>&1 || true
    hwclock --systohc > hwclock-systohc.txt 2>&1 || true
fi

if [ "$MODE" = "os" ]; then
    echo "Restoring time sync..." > time-sync-restore.txt

    if systemctl list-unit-files 2>/dev/null | grep -q chronyd; then
        systemctl restart chronyd >> time-sync-restore.txt 2>&1
        chronyc -a makestep >> time-sync-restore.txt 2>&1
    elif systemctl list-unit-files 2>/dev/null | grep -q systemd-timesyncd; then
        systemctl restart systemd-timesyncd >> time-sync-restore.txt 2>&1
    else
        echo "No known time sync service found" >> time-sync-restore.txt
    fi

    sleep 10
fi

echo "Linux Debug Dump - Completed"
