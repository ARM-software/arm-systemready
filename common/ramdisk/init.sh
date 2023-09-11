#!/bin/sh

# Copyright (c) 2021-2023, ARM Limited and Contributors. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# Neither the name of ARM nor the names of its contributors may be used
# to endorse or promote products derived from this software without specific
# prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

#Mount things needed by this script
/bin/busybox mount -t proc proc /proc


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
insmod /lib/modules/xhci-pci.ko
insmod /lib/modules/nvme-core.ko
insmod /lib/modules/nvme.ko

sleep 5

#Skip running of ACS Tests if the grub option is added
ADDITIONAL_CMD_OPTION="";
ADDITIONAL_CMD_OPTION=`cat /proc/cmdline | awk '{ print $NF}'`

if [ $ADDITIONAL_CMD_OPTION != "noacs" ]; then
 #mount result partition
 BLOCK_DEVICE_NAME=$(blkid | grep "BOOT" | awk -F: '{print $1}')

 if [ ! -z "$BLOCK_DEVICE_NAME" ]; then
  mount $BLOCK_DEVICE_NAME /mnt
  echo "Mounted the results partition on device $BLOCK_DEVICE_NAME"
 else
  echo "Warning: the results partition could not be mounted. Logs may not be saved correctly"
 fi

 if [ $ADDITIONAL_CMD_OPTION == "secureboot" ]; then
  echo "Call SIE ACS"
  /usr/bin/secure_init.sh
  echo "SIE ACS run is completed\n"
  echo "Please press <Enter> to continue ..."
  sync /mnt
  sleep 3
  exec sh +m
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

 #Check for the existense of fwts test configuration file in the package. EBBR Execution
 if [ -f  /bin/ir_bbr_fwts_tests.ini ]; then
  test_list=`cat /bin/ir_bbr_fwts_tests.ini | grep -v "^#" | awk '{print $1}' | xargs`
  echo "Test Executed are $test_list"
  fwts `echo $test_list` -f -r /mnt/acs_results/fwts/FWTSResults.log
 else
  #SBBR Execution
  echo "Executing FWTS for SBBR"
  fwts  -r stdout -q --uefi-set-var-multiple=1 --uefi-get-mn-count-multiple=1 --sbbr esrt uefibootpath > /mnt/acs_results/fwts/FWTSResults.log
 fi

 sleep 2

 if [ ! -f  /bin/ir_bbr_fwts_tests.ini ]; then
  #Run Linux BSA tests for ES and SR only
  mkdir -p /mnt/acs_results/linux
  sleep 3
  echo "Running Linux BSA tests"
  if [ -f  /lib/modules/bsa_acs.ko ]; then
   #Case of ES
   insmod /lib/modules/bsa_acs.ko
   if [ -f /bin/sr_bsa.flag ]; then
    echo $'SystemReady SR ACS v2.0.0_BETA-0\n' > /mnt/acs_results/linux/BsaResultsApp.log
   else
    echo $'SystemReady ES ACS v1.2.0\n' > /mnt/acs_results/linux/BsaResultsApp.log
   fi
   /bin/bsa >> /mnt/acs_results/linux/BsaResultsApp.log
   dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux/BsaResultsKernel.log
  else
   echo "Error: BSA kernel Driver is not found. Linux BSA tests cannot be run."
  fi

  if [ -f /bin/sr_bsa.flag ]; then
   echo "Running Linux SBSA tests"
   if [ -f  /lib/modules/sbsa_acs.ko ]; then
    #Case of SR
    insmod /lib/modules/sbsa_acs.ko
    echo $'SystemReady SR ACS v2.0.0_BETA-0\n' > /mnt/acs_results/linux/SbsaResultsApp.log
    /bin/sbsa >> /mnt/acs_results/linux/SbsaResultsApp.log
    dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux/SbsaResultsKernel.log
   else
    echo "Error: SBSA kernel Driver is not found. Linux SBSA tests cannot be run."
   fi
  fi
 fi
 if [ -d "/mnt/acs_results/sct_results" ]; then
     echo "Running edk2-test-parser tool "
     mkdir -p /mnt/acs_results/edk2-test-parser
     cd /usr/bin/edk2-test-parser
     ./parser.py --md /mnt/acs_results/edk2-test-parser/edk2-test-parser.log /mnt/acs_results/sct_results/Overall/Summary.ekl /mnt/acs_results/sct_results/Sequence/BBSR.seq
 else
     echo "SCT result does not exist, cannot run edk2-test-parser tool cannot run"
 fi
else
 echo ""
 echo "Additional option set to not run ACS Tests. Skipping ACS tests on Linux"
 echo ""
fi

sync /mnt
sleep 3

exec sh +m
