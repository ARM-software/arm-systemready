#!/bin/sh

# Copyright (c) 2022-2023, ARM Limited and Contributors. All rights reserved.
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
# AND ANY EXPRESS OR IMPLIED WARUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

echo "init.sh"

echo "Mounting efivarfs ..."
mount -t efivarfs efivarfs /sys/firmware/efi/efivars

sleep 5

#Skip running of ACS Tests if the grub option is added
ADDITIONAL_CMD_OPTION="";
ADDITIONAL_CMD_OPTION=`cat /proc/cmdline | awk '{ print $NF}'`

if [ $ADDITIONAL_CMD_OPTION != "noacs" ]; then
 echo "Attempting to mount the results partition ..."
 RESULT_DEVICE="";
 
 #mount result partition
 cat /proc/partitions | tail -n +3 > partition_table.lst
 while read -r line
 do
    # do something with $line here
    MAJOR=`echo $line | awk '{print $1}'`
    MINOR=`echo $line | awk '{print $2}'`
    DEVICE=`echo $line | awk '{print $4}'`
    echo "$MAJOR $MINOR $DEVICE"
    mknod /dev/$DEVICE b $MAJOR $MINOR
    mount /dev/$DEVICE /mnt
    if [ -d /mnt/acs_results ]; then
         #Partition is mounted. Break from loop
         RESULT_DEVICE="/dev/$DEVICE"
         echo "Setting RESULT_DEVICE to $RESULT_DEVICE"
         break;
         #Note: umount must be done from the calling function
    else
         #acs_results is not found, so move to next
         umount /mnt
    fi
 done < partition_table.lst
 
 rm partition_table.lst
 
 if [ ! -z "$RESULT_DEVICE" ]; then
  echo "Mounted the results partition on device $RESULT_DEVICE"
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
 #lsusb > /mnt/acs_results/linux_dump/lsusb.log
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
 echo $'SystemReady IR ACS v2.0.0 \nFWTS v23.01.00' > /mnt/acs_results/fwts/FWTSResults.log
 /usr/bin/fwts --ebbr `echo $test_list` -r /mnt/acs_results/fwts/FWTSResults.log
 echo -e -n "\n"
 
 #run linux bsa app
 mkdir -p /mnt/acs_results/linux_acs/bsa_acs_app
 echo "Loading BSA ACS Linux Driver"
 insmod /lib/modules/*/kernel/bsa_acs/bsa_acs.ko
 echo "Executing BSA ACS Application "
 echo $'SystemReady IR ACS v2.0.0 \nBSA v1.0.4' > /mnt/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
 bsa >> /mnt/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
 dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux_acs/bsa_acs_app/BsaResultsKernel.log
 
 #flush the contents to disk
 sync /mnt
 
 sleep 3
 
 mkdir -p /home/root/fdt
 mkdir -p /mnt/acs_results/linux_tools
 
 if [ -f /sys/firmware/fdt ]; then
  echo "copying fdt "
  cp /sys/firmware/fdt /home/root/fdt
 
  if [ -f /results/acs_results/linux_tools/dt-validate.log ]; then
   mv /results/acs_results/linux_tools/dt-validate.log /results/acs_results/linux_tools/dt-validate.log.old
  fi
 
  echo "Running dt-validate tool "
  dt-validate -s /usr/bin/processed_schema.json -m /home/root/fdt/fdt 2>> /mnt/acs_results/linux_tools/dt-validate.log
 
  sed -i '1s/^/DeviceTree bindings of Linux kernel version: 6.1.2 \ndtschema version: 2022.9 \n\n/' /mnt/acs_results/linux_tools/dt-validate.log
  if [ ! -s /mnt/acs_results/linux_tools/dt-validate.log ]; then
   echo $'The FDT is compliant according to schema ' >> /mnt/acs_results/linux_tools/dt-validate.log
  fi
 else
  echo  $'Error: The FDT devicetree file, fdt, does not exist at /sys/firmware/fdt. Cannot run dt-schema tool ' | tee /mnt/acs_results/linux_tools/dt-validate.log
 fi
else
 echo ""
 echo "Additional option set to not run ACS Tests. Skipping ACS tests on Linux"
 echo ""
fi
echo "ACS run is completed"
echo "Please press <Enter> to continue ..."
echo -e -n "\n"
exit 0
