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

#Mount things needed by this script
/bin/busybox mount -t proc proc /proc

#softlink current console to /dev/tty for ssh/scp utility
rm /dev/tty
ln -s $(tty) /dev/tty

if ! mountpoint -q /sys; then
  echo "Mounting /sysfs..."
  /bin/busybox mount -t sysfs sysfs /sys
else
  echo "/sysfs is already mounted."
fi

mount -t efivarfs efivarfs /sys/firmware/efi/efivars
echo "init.sh"

#Create a link of S99init.sh to init.sh
if [ ! -f /init.sh ]; then
  ln -s  /etc/init.d/S99init.sh /init.sh
fi

#Create all the symlinks to /bin/busybox
/bin/busybox --install -s

#give linux time to finish initlazing disks
sleep 5
mdev -s

echo "Starting disk drivers"
insmod /lib/modules/xhci-pci-renesas.ko
insmod /lib/modules/nvme-core.ko
insmod /lib/modules/nvme.ko
insmod /lib/modules/cppc_cpufreq.ko

sleep 5

#Skip running of ACS Tests if the grub option is added
ADDITIONAL_CMD_OPTION="";
ADDITIONAL_CMD_OPTION=`cat /proc/cmdline | awk '{ print $NF}'`

#mount result partition
BLOCK_DEVICE_NAME=$(blkid | grep "BOOT_ACS" | awk -F: '{print $1}' | head -n 1)
if [ ! -z "$BLOCK_DEVICE_NAME" ]; then
  mount -o rw $BLOCK_DEVICE_NAME /mnt
  echo "Mounted the results partition on device $BLOCK_DEVICE_NAME"
else
  echo "Warning: the results partition could not be mounted. Logs may not be saved correctly"
fi

# Parse config file
automation_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation`"
if [ "$automation_enabled" == "True" ]; then
  fwts_command="`python3 /mnt/acs_tests/parser/Parser.py -fwts`"
  fwts_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_fwts_run`"

  bsa_command="`python3 /mnt/acs_tests/parser/Parser.py -bsa`"
  bsa_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_bsa_run`"

  sbsa_command="`python3 /mnt/acs_tests/parser/Parser.py -sbsa`"
  sbsa_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_sbsa_run`"

  sbmr_enabled="`python3 /mnt/acs_tests/parser/Parser.py -automation_sbmr_in_band_run`"
fi

if [ $ADDITIONAL_CMD_OPTION != "noacs" ]; then
  if [ $ADDITIONAL_CMD_OPTION == "secureboot" ]; then
    echo "Call BBSR ACS"
    /usr/bin/secure_init.sh
    echo "BBSR ACS run is completed\n"
    echo "Please press <Enter> to continue ..."
    sync /mnt
    sleep 3
    exec sh +m
  fi

  if [ $ADDITIONAL_CMD_OPTION == "acsforcevamap" ]; then
    echo "Linux Boot with SetVirtualMap enabled"
    mkdir -p /mnt/acs_results/SetVAMapMode/fwts
    echo "Executing FWTS"
    echo "SystemReady band ACS v3.1.0" > /mnt/acs_results/SetVAMapMode/fwts/FWTSResults.log
    fwts  -r stdout -q --uefi-set-var-multiple=1 --uefi-get-mn-count-multiple=1 --sbbr esrt uefibootpath aest cedt slit srat hmat pcct pdtt bgrt bert einj erst hest sdei nfit iort mpam ibft ras2 >> /mnt/acs_results/SetVAMapMode/fwts/FWTSResults.log
    sync /mnt
    sleep 3
    echo "The ACS test suites are completed."
    exec sh +m
  fi


  #Linux debug dump
  echo "Collecting Linux Debug Dump"
  mkdir -p /mnt/acs_results/linux_dump
  dmesg > /mnt/acs_results/linux_dump/dmesg.log
  lspci > /mnt/acs_results/linux_dump/lspci.log
  lspci -vvv &> /mnt/acs_results/linux_dump/lspci-vvv.log
  cat /proc/interrupts > /mnt/acs_results/linux_dump/interrupts.log
  cat /proc/cpuinfo > /mnt/acs_results/linux_dump/cpuinfo.log
  cat /proc/meminfo > /mnt/acs_results/linux_dump/meminfo.log
  cat /proc/iomem > /mnt/acs_results/linux_dump/iomem.log
  lscpu > /mnt/acs_results/linux_dump/lscpu.log
  lsblk > /mnt/acs_results/linux_dump/lsblk.log
  lsusb > /mnt/acs_results/linux_dump/lsusb.log
  lshw > /mnt/acs_results/linux_dump/lshw.log
  dmidecode > /mnt/acs_results/linux_dump/dmidecode.log
  dmidecode --dump-bin /mnt/acs_results/linux_dump/dmidecode.bin >> /mnt/acs_results/linux_dump/dmidecode.log 2>&1
  uname -a > /mnt/acs_results/linux_dump/uname.log
  cat /etc/os-release > /mnt/acs_results/linux_dump/cat-etc-os-release.log
  date > /mnt/acs_results/linux_dump/date.log
  cat /proc/driver/rtc > /mnt/acs_results/linux_dump/rtc.log
  hwclock > /mnt/acs_results/linux_dump/hwclock.log
  efibootmgr > /mnt/acs_results/linux_dump/efibootmgr.log
  efibootmgr -t 20 > /mnt/acs_results/linux_dump/efibootmgr-t-20.log
  efibootmgr -t 5 > /mnt/acs_results/linux_dump/efibootmgr-t-5.log
  efibootmgr -c > /mnt/acs_results/linux_dump/efibootmgr-c.txt 2>&1
  ifconfig > /mnt/acs_results/linux_dump/ifconfig.log
  ip addr show > /mnt/acs_results/linux_dump/ip-addr-show.log
  ping -c 5 www.arm.com > /mnt/acs_results/linux_dump/ping-c-5-www-arm-com.log
  acpidump > /mnt/acs_results/linux_dump/acpi.log
  acpidump > /mnt/acs_results/linux_dump/acpi.dat
  cd /mnt/acs_results/linux_dump
  acpixtract -a acpi.dat > acpixtract.log 2>&1
  iasl -d *.dat > iasl.log 2>&1
  cd -
  date --set="20221215 05:30" > /mnt/acs_results/linux_dump/date-set-202212150530.log
  date > /mnt/acs_results/linux_dump/date-after-set.log
  hwclock --set --date "2023-01-01 09:10:15" > /mnt/acs_results/linux_dump/hw-clock-set-20230101091015.log
  hwclock > /mnt/acs_results/linux_dump/hwclock-after-set.log
  ls -lR /sys/firmware > /mnt/acs_results/linux_dump/firmware.log
  cp -r /sys/firmware /mnt/acs_results/linux_dump/ >> firmware.log 2>&1
  # Capturing System PSCI command output
  mkdir -p /mnt/acs_results/linux_tools/psci
  mount -t debugfs none /sys/kernel/debug
  cat /sys/kernel/debug/psci > /mnt/acs_results/linux_tools/psci/psci.log
  dmesg | grep psci > /mnt/acs_results/linux_tools/psci/psci_kernel.log
  sync /mnt
  sleep 5
  echo "Linux Debug Dump - Completed"

  # Linux Device Driver script run
  echo "Running Device Driver Matching Script"
  cd /usr/bin/
  ./device_driver_sr.sh > /mnt/acs_results/linux_dump/device_driver.log
  cd -
  echo "Device Driver script run completed"
  sync /mnt
  sleep 5

  # FWTS (SBBR) Execution
  echo "Executing FWTS for SBBR"
  if [ "$automation_enabled" == "True" ] &&  [ "$fwts_enabled" == "False" ]; then
    echo "********* FWTS is disabled in config file**************"
  else
    mkdir -p /mnt/acs_results/fwts
    if [ -f /lib/modules/smccc_test.ko ]; then
      echo "Loading FWTS SMCCC module"
      insmod /lib/modules/smccc_test.ko
    else
      echo "Error: FWTS SMCCC kernel Driver is not found."
    fi
    echo "SystemReady band ACS v3.1.0" > /mnt/acs_results/fwts/FWTSResults.log
    if [ "$automation_enabled" == "False" ]; then
      fwts  -r stdout -q --uefi-set-var-multiple=1 --uefi-get-mn-count-multiple=1 --sbbr aest cedt slit srat hmat pcct pdtt bgrt bert einj erst hest sdei nfit iort mpam ibft ras2 smccc >> /mnt/acs_results/fwts/FWTSResults.log
    else
      $fwts_command -r stdout -q >> /mnt/acs_results/fwts/FWTSResults.log
    fi
    sync /mnt
    sleep 5
    echo "FWTS Execution - Completed"
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

  # Run SBMR-ACS In-Band Tests 
  if [ "$automation_enabled" == "True" ]; then
    if [ "$sbmr_enabled" == "False" ]; then
      echo "********* SBMR In-Band is disabled in config file**************"
    else
      run_sbmr_in_band
      sync /mnt
      sleep 3
      echo "NOTE: This ACS image runs SBMR IN-BAND tests ONLY." 1>&2
      echo "For SBMR OUT-OF-BAND tests, see: https://github.com/ARM-software/sbmr-acs.git" 1>&2
    fi
  else
    echo "SBMR-ACS In-Band test is disabled by default, please enable in config file to run SBMR-ACS In-Band test"
  fi

  # Linux BSA Execution
  echo "Running Linux BSA tests"
  if [ "$automation_enabled" == "True" ] &&  [ "$bsa_enabled" == "False" ]; then
    echo "********* BSA is disabled in config file**************"
  else
    mkdir -p /mnt/acs_results/linux
    if [ -f  /lib/modules/bsa_acs.ko ]; then
      insmod /lib/modules/bsa_acs.ko
      echo "SystemReady band ACS v3.1.0" > /mnt/acs_results/linux/BsaResultsApp.log
      if [ "$automation_enabled" == "False" ]; then
        # based on previous certification/complaince inputs, side effects are seen
        # when bsa/sbsa test changes config of PCIe devices whose class code are
        # display port, mass storage, network controller...SKIP them
        /bin/bsa --skip-dp-nic-ms >> /mnt/acs_results/linux/BsaResultsApp.log
      else
        echo "Running command $bsa_command --skip-dp-nic-ms"
        $bsa_command --skip-dp-nic-ms  >> /mnt/acs_results/linux/BsaResultsApp.log
      fi
      dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux/BsaResultsKernel.log
      sync /mnt
      sleep 5
      echo "Linux BSA test Execution - Completed"
    else
      echo "Error: BSA kernel Driver is not found. Linux BSA tests cannot be run."
    fi
  fi


  # Linux SBSA Execution
  echo "Running Linux SBSA tests"
  if [ "$automation_enabled" == "True" ]; then
    if [ "$sbsa_enabled" == "False" ]; then
      echo "********* SBSA is disabled in config file**************"
    else
      mkdir -p /mnt/acs_results/linux
      if [ -f  /lib/modules/sbsa_acs.ko ]; then
        insmod /lib/modules/sbsa_acs.ko
        echo "SystemReady band ACS v3.1.0" > /mnt/acs_results/linux/SbsaResultsApp.log
        echo "Running command $sbsa_command --skip-dp-nic-ms"
        $sbsa_command --skip-dp-nic-ms >> /mnt/acs_results/linux/SbsaResultsApp.log
        dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux/SbsaResultsKernel.log
        sync /mnt
        sleep 5
        echo "Linux SBSA test Execution - Completed"
      else
        echo "Error: SBSA kernel Driver is not found. Linux SBSA tests cannot be run."
      fi
    fi
  else
    echo "SBSA test is disabled by default, please enable in config file to run Sbsa"
  fi

  # EDK2 test parser
  if [ -d "/mnt/acs_results/sct_results" ]; then
    echo "Running edk2-test-parser tool "
    mkdir -p /mnt/acs_results/edk2-test-parser
    cd /usr/bin/edk2-test-parser
    ./parser.py --md /mnt/acs_results/edk2-test-parser/edk2-test-parser.log /mnt/acs_results/sct_results/Overall/Summary.ekl /mnt/acs_results/sct_results/Sequence/SBBR.seq > /dev/null 2>&1
    cd -
    echo "edk2-test-parser run completed"
    sync /mnt
    sleep 5
  else
    echo "SCT result does not exist, cannot run edk2-test-parser tool cannot run"
  fi

  # ACS log parser run
  echo "Running acs log parser tool "
  if [ -d "/mnt/acs_results" ]; then
    if [ -d "/mnt/acs_results/acs_summary" ]; then
        rm -r /mnt/acs_results/acs_summary
    fi
    /usr/bin/log_parser/main_log_parser.sh /mnt/acs_results /mnt/acs_tests/config/acs_config.txt /mnt/acs_tests/config/system_config.txt /mnt/acs_tests/config/acs_waiver.json
    sync /mnt
    sleep 5
  fi

  echo "Please wait acs results are syncing on storage medium."
  sync /mnt
  sleep 60
  #copying acs_run_config.ini into results directory.
  mkdir -p /mnt/acs_results/acs_summary/config
  cp /mnt/acs_tests/config/acs_run_config.ini /mnt/acs_results/acs_summary/config/
  # Copying acs_waiver.json into result directory.
  if [ -f /mnt/acs_tests/config/acs_waiver.json ]; then
    cp /mnt/acs_tests/config/acs_waiver.json /mnt/acs_results/acs_summary/config/
  fi
  # Copying system_config.txt into result directory
  if [ -f /mnt/acs_tests/config/system_config.txt ]; then
    cp /mnt/acs_tests/config/system_config.txt /mnt/acs_results/acs_summary/config/
  fi
  sync /mnt

  echo "ACS automated test suites run is completed."
  echo "Please reboot to run BBSR tests if not done"
  echo "Please press <Enter> to continue ..."
else
  echo ""
  echo "Linux Execution Enviroment can be used to run an acs test suite manually with desired options"
  echo "The supported test suites for Linux enviroment are"
  echo "  BSA"
  echo "  SBSA"
  echo "  FWTS"
  echo " "
  echo " To view or modify the supported command line parameters for a test suite"
  echo " Edit the /mnt/acs_tests/config/acs_run_config.ini"
  echo " "
  echo " To run BSA test suite, execute /usr/bin/bsa.sh"
  echo " To run SBSA test suite, execute /usr/bin/sbsa.sh"
  echo " To run SCT test suite, execute /usr/bin/fwts.sh"
  echo " To run SBMR test suite, execute /usr/bin/sbmr.sh"
  echo ""
fi

sync /mnt
sleep 5

exec sh +m
