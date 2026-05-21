# SystemReady Band OS Run Guide

## Overview

This document explains how to run the Linux OS-side diagnostics for SystemReady Band.

The OS run collects debug logs from the installed operating system and runs additional Linux diagnostics. The generated logs are packaged so they can be copied into the ACS results template and validated by the parser.

## Scripts Used

The OS run uses the following scripts:

| File | Purpose |
|------|---------|
| [`linux_init.sh`](../common/linux_scripts/linux_init.sh) | Initializes the OS run and triggers ACS or OS log collection flow |
| [`linux_dump.sh`](../common/linux_scripts/linux_dump.sh) | Collects Linux system dump logs |
| [`ethtool-test.py`](../common/linux_scripts/ethtool-test.py) | Perfoms Ethernet interface checks |
| [`read_write_check_blk_devices.py`](../common/linux_scripts/read_write_check_blk_devices.py) | Performs read/write checks on block devices |
| [`system_config.txt`](../common/config/system_config.txt) | System configuration input used by the scripts |

> **Note**: Please download the latest OS script files from the **[SystemReady-ACS Daily artifacts](https://github.com/ARM-software/arm-systemready/actions/workflows/systemready_daily.yml)**.

### Script Flow

```text
linux_init.sh
    ├── detects OS mode
    ├── installs required tools
    ├── calls linux_dump.sh
    ├── runs read_write_check_blk_devices.py to validate block devices using read checks and optional write checks.
    ├── runs ethtool-test.py to validate Ethernet interfaces using link, ethtool, IP, ping, wget, and curl checks.
    ├── creates systemready-band-compliance-logs.tar.gz
    └── prints where to copy the generated OS logs for ACS parser use

linux_dump.sh
    ├── collects Linux debug dump logs
    ├── captures firmware, ACPI, UEFI, RTC, PCI, CPU, memory, USB, and block-device information
    ├── performs system time and hardware clock set checks
    └── restores OS time synchronization using chronyd or systemd-timesyncd when available
```

## How to Run
From the directory containing the scripts, run the script with root privileges.
```sh
chmod +x linux_init.sh
```
```sh
sudo ./linux_init.sh --mode os
```

## Generated Log Directory

The OS logs are generated under the user’s home directory:
```text
$HOME/systemready-band-compliance-logs/
```

At the end of the run, the script creates:
```text
systemready-band-compliance-logs.tar.gz
```

## Logs Collected

The OS run collects the following Linux debug logs:
```text
dmesg.txt
lspci.txt
lspci-vvv.txt
cat-proc-interrupts.txt
cat-proc-cpuinfo.txt
cat-proc-meminfo.txt
cat-proc-iomem.txt
lscpu.txt
lsblk.txt
lsusb.txt
lshw.txt
dmidecode.txt
dmidecode.bin
uname-a.txt
cat-etc-os-release.txt
date.txt
timedatectl.txt
cat-proc-driver-rtc.txt
hwclock.txt
efibootmgr.txt
efibootmgr-t-20.txt
efibootmgr-t-5.txt
efibootmgr-c.txt
ifconfig.txt
ip-addr-show.txt
ping-c-5-www-arm-com.txt
cat-proc-cmdline.txt
df-h.txt
mount.txt
lsmod.txt
acpi.log
*.dat
*.dsl
acpixtract.txt
iasl.txt
date-set-202212150530.txt
date-after-set.txt
hw-clock-set-20230101091015.txt
hwclock-after-set.txt
firmware.txt
firmware/
time-sync-restore.txt
```

Additional diagnostic logs:

```text
read_write_check_blk_devices.log
ethtool-test.log
```


## Copying OS Logs for ACS Parser

After the OS run completes, copy the generated OS logs into the ACS results template.

Expected destination:

```text
acs_results_template/os-logs/<linux-os-name>/systemready-band-compliance-logs/
```

Directory structure:

```text
acs_results_template/
└── os-logs/
    └── linux-<os-name>/
        └── systemready-band-compliance-logs/
            ├── dmesg.txt
            ├── lspci.txt
            ├── cat-etc-os-release.txt
            ├── ethtool-test.log
            ├── read_write_check_blk_devices.log
            └── other OS logs
```
--------------
*Copyright (c) 2026, Arm Limited and Contributors. All rights reserved.*
