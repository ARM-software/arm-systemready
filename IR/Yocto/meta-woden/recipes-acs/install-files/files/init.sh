#!/bin/sh

# Copyright (c) 2023-2024, Arm Limited or its affiliates. All rights reserved.
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

echo "init.sh"

echo "Mounting efivarfs ..."
mount -t efivarfs efivarfs /sys/firmware/efi/efivars

sleep 5

#Skip running of ACS Tests if the grub option is added
ADDITIONAL_CMD_OPTION="";
ADDITIONAL_CMD_OPTION=`cat /proc/cmdline | awk '{ print $NF}'`

if [ $ADDITIONAL_CMD_OPTION != "noacs" ]; then
 echo "Attempting to mount the results partition ..." 
 #mount result partition
 BLOCK_DEVICE_NAME=$(blkid | grep "BOOT_ACS" | awk -F: '{print $1}')

 if [ ! -z "$BLOCK_DEVICE_NAME" ]; then
  mount $BLOCK_DEVICE_NAME /mnt
  echo "Mounted the results partition on device $BLOCK_DEVICE_NAME"
 else
  echo "Warning: the results partition could not be mounted. Logs may not be saved correctly"
 fi
 
 sleep 3
 
 SECURE_BOOT="";
 SECURE_BOOT=`cat /proc/cmdline | awk '{ print $NF}'`
 
 if [ $SECURE_BOOT = "secureboot" ]; then
  echo "Call SIE ACS in Linux"
  /usr/bin/secure_init.sh
  echo "SIE ACS run is completed\n"
  echo "Please press <Enter> to continue ..."
  echo -e -n "\n"
  exit 0
 fi
 
 #linux debug dump
 mkdir -p /mnt/acs_results/linux_dump
 lspci -vvv &> /mnt/acs_results/linux_dump/lspci.log
 lsusb > /mnt/acs_results/linux_dump/lsusb.log
 uname -a > /mnt/acs_results/linux_dump/uname.log
 cat /proc/interrupts > /mnt/acs_results/linux_dump/interrupts.log
 cat /proc/cpuinfo > /mnt/acs_results/linux_dump/cpuinfo.log
 cat /proc/meminfo > /mnt/acs_results/linux_dump/meminfo.log
 cat /proc/iomem > /mnt/acs_results/linux_dump/iomem.log
 ls -lR /sys/firmware > /mnt/acs_results/linux_dump/firmware.log
 cp -r /sys/firmware /mnt/acs_results/linux_dump/
 dmidecode > /mnt/acs_results/linux_dump/dmidecode.log
 efibootmgr > /mnt/acs_results/linux_dump/efibootmgr.log
 
 mkdir -p /mnt/acs_results/fwts
 echo "Executing FWTS for EBBR"
 test_list=`cat /usr/bin/ir_bbr_fwts_tests.ini | grep -v "^#" | awk '{print $1}' | xargs`
 echo "Test Executed are $test_list"
 echo $'SystemReady IR ACS v2.1.1 \nFWTS v24.01.00' > /mnt/acs_results/fwts/FWTSResults.log
 /usr/bin/fwts --ebbr `echo $test_list` -r /mnt/acs_results/fwts/FWTSResults.log
 echo -e -n "\n"
 
 #run linux bsa app
 mkdir -p /mnt/acs_results/linux_acs/bsa_acs_app
 echo "Loading BSA ACS Linux Driver"
 insmod /lib/modules/*/kernel/bsa_acs/bsa_acs.ko
 echo "Executing BSA ACS Application "
 echo $'SystemReady IR ACS v2.1.1 \nBSA v1.0.6' > /mnt/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
 bsa >> /mnt/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
 dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux_acs/bsa_acs_app/BsaResultsKernel.log
 
 #flush the contents to disk
 sync /mnt
 
 sleep 3
 
 mkdir -p /home/root/fdt
 mkdir -p /mnt/acs_results/linux_tools

 pushd /usr/bin
 echo "running device_driver_info.sh device and driver info created"
 ./device_driver_info.sh
 cp device_driver_info.log /mnt/acs_results/linux_tools
 popd

 # Generate the .dts file and move it to /mnt/acs_results/linux_tools
 dtc -I fs -O dts -o /mnt/acs_results/linux_tools/device_tree.dts /sys/firmware/devicetree/base 2>/dev/null

 # Generate tree format of sys hierarchy and saving it into logs.
 tree -d /sys > /mnt/acs_results/linux_dump/sys_hierarchy.log


 if [ -f /sys/firmware/fdt ]; then
  echo "copying fdt "
  cp /sys/firmware/fdt /home/root/fdt
 
  if [ -f /results/acs_results/linux_tools/dt-validate.log ]; then
   mv /results/acs_results/linux_tools/dt-validate.log /results/acs_results/linux_tools/dt-validate.log.old
  fi
 
  echo "Running dt-validate tool "
  dt-validate -s /usr/bin/processed_schema.json -m /home/root/fdt/fdt 2>> /mnt/acs_results/linux_tools/dt-validate.log
  sed -i '1s/^/DeviceTree bindings of Linux kernel version: 6.5 \ndtschema version: 2024.2 \n\n/' /mnt/acs_results/linux_tools/dt-validate.log
  if [ ! -s /mnt/acs_results/linux_tools/dt-validate.log ]; then
   echo $'The FDT is compliant according to schema ' >> /mnt/acs_results/linux_tools/dt-validate.log
  fi
 else
  echo  $'Error: The FDT devicetree file, fdt, does not exist at /sys/firmware/fdt. Cannot run dt-schema tool ' | tee /mnt/acs_results/linux_tools/dt-validate.log
 fi
 if [ -d "/mnt/acs_results/sct_results" ]; then
     echo "Running edk2-test-parser tool "
     mkdir -p /mnt/acs_results/edk2-test-parser
     cd /usr/bin/edk2-test-parser
     ./parser.py --md /mnt/acs_results/edk2-test-parser/edk2-test-parser.log /mnt/acs_results/sct_results/Overall/Summary.ekl /mnt/acs_results/sct_results/Sequence/EBBR.seq > /dev/null 2>&1
 else
     echo "SCT result does not exist, cannot run edk2-test-parser tool cannot run"
 fi
 mkdir -p /mnt/acs_results/linux_tools/psci
 mount -t debugfs none /sys/kernel/debug
 cat /sys/kernel/debug/psci > /mnt/acs_results/linux_tools/psci/psci.log
 dmesg | grep psci > /mnt/acs_results/linux_tools/psci/psci_kernel.log

 pushd /usr/kernel-selftest
 ./run_kselftest.sh -t dt:test_unprobed_devices.sh > /mnt/acs_results/linux_tools/dt_kselftest.log
 popd

 # update resolv.conf with 8.8.8.8 DNS server
 echo "nameserver 8.8.8.8" >> /etc/resolv.conf

 # run ethtool-test.py, dump ethernet information, run self-tests if supported, and ping
 python3 /bin/ethtool-test.py | tee ethtool-test.log
 # remove color characters from log and save
 awk '{gsub(/\x1B\[[0-9;]*[JKmsu]/, "")}1' ethtool-test.log > /mnt/acs_results/linux_tools/ethtool-test.log

 # run read_write_check_blk_devices.py, parse block devices, and perform read if partition doesn't belond
 # in precious partitions
 python3 /bin/read_write_check_blk_devices.py | tee /mnt/acs_results/linux_tools/read_write_check_blk_devices.log
 echo "ACS run is completed"
else
 echo ""
 echo "Additional option set to not run ACS Tests. Skipping ACS tests on Linux"
 echo ""
fi

sync /mnt
echo "Please press <Enter> to continue ..."
echo -e -n "\n"
exit 0
