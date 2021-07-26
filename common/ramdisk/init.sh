#!/bin/sh

# Copyright (c) 2021, ARM Limited and Contributors. All rights reserved.
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
/bin/busybox mount -t sysfs sysfs /sys
echo "init.sh"

#Create all the symlinks to /bin/busybox
/bin/busybox --install -s


#give linux time to finish initlazing disks
sleep 5
mdev -s

RESULT_DEVICE="";

#mount result partition

mount LABEL=RESULT /mnt
RESULT_DEVICE=`blkid |grep "LABEL=\"RESULT\"" |cut -f1 -d:`

if [ ! -z "$RESULT_DEVICE" ]; then
 echo "Mounted the results partition on device $RESULT_DEVICE"
else
 echo "Warning: the results partition could not be mounted. Logs may not be saved correctly"
fi


#linux debug dump
mkdir -p /mnt/acs_results/linux_dump
lspci -vvv &> /mnt/acs_results/linux_dump/lspci.log

mkdir -p /mnt/acs_results/fwts

#Check for the existense of fwts test configuration file in the package. EBBR Execution
if [ -f  /bin/ir_bbr_fwts_tests.ini ]; then
 test_list=`cat /bin/ir_bbr_fwts_tests.ini | grep -v "^#" | awk '{print $1}' | xargs`
 echo "Test Executed are $test_list"
 /bin/fwts `echo $test_list` -f -r /mnt/acs_results/fwts/FWTSResults.log
else
 #SBBR Execution
 /bin/fwts  -r stdout -q --sbbr > /mnt/acs_results/fwts/FWTSResults.log
fi

sleep 2

if [ ! -f  /bin/ir_bbr_fwts_tests.ini ]; then
 #Run Linux BSA tests for ES only
 sleep 3
 echo "Running Linux BSA tests"
 if [ -f  /lib/modules/bsa_acs.ko ]; then
  insmod /lib/modules/bsa_acs.ko
  mkdir -p /mnt/acs_results/linux
  /bin/bsa > /mnt/acs_results/linux/BsaResultsApp.log
 else
  echo "Error : BSA Kernel Driver is not found. Linux BSA Tests cannot be run."
 fi
 dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux/BsaResultsKernel.log
fi

sync /mnt
sleep 3

exec sh
