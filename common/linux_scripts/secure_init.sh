#!/bin/sh

# @file
# Copyright (c) 2021-2024, Arm Limited or its affiliates. All rights reserved.
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


# securityfs does not get automounted
#Already mounted on Yocto Linux
/bin/mount -t securityfs securityfs /sys/kernel/security

# Following modules are built into Yocto image and shipped
# as loadable in buildroot build.
if ! grep -qi "yocto" /proc/version ; then
  echo "Loading TPM kernel modules..."
  insmod /lib/modules/tpm_tis.ko
  insmod /lib/modules/tpm_tis_spi.ko
  insmod /lib/modules/tpm_tis_i2c_cr50.ko
  insmod /lib/modules/spi-tegra210-quad.ko
fi

# give linux time to finish initializing disks
sleep 5

if [ "$(which mokutil)" != "" ]; then
  SB_STATE=`mokutil --sb-state`
  echo $SB_STATE
  if [ "$SB_STATE" = "SecureBoot enabled" ]; then
    echo "The system is in SecureBoot mode"
  else
    echo "WARNING: The System is not in SecureBoot mode"
  fi
fi

mkdir -p /mnt/acs_results/BBSR/fwts

# Add the YOCTO_FLAG variable
YOCTO_FLAG="/mnt/yocto_image.flag"

if [ -f  /bin/bbsr_fwts_tests.ini ]; then
  test_list=`cat /bin/bbsr_fwts_tests.ini | grep -v "^#" | awk '{print $1}' | xargs`
  echo "Test Executed are $test_list"
  if [ -f "$YOCTO_FLAG" ]; then
    echo "SystemReady devicetree band ACS v3.0.0" > /mnt/acs_results/BBSR/fwts/FWTSResults.log
  else
    echo "SystemReady band ACS v3.0.0" > /mnt/acs_results/BBSR/fwts/FWTSResults.log
  fi  
  fwts `echo $test_list` -f -r stdout >> /mnt/acs_results/BBSR/fwts/FWTSResults.log
fi

# run tpm2 tests
mkdir -p /mnt/acs_results/BBSR/tpm2
if [ -f /sys/kernel/security/tpm0/binary_bios_measurements ]; then
  echo "TPM2: dumping PCRs and event log"
  cp /sys/kernel/security/tpm0/binary_bios_measurements /tmp
  tpm2_eventlog /tmp/binary_bios_measurements > /mnt/acs_results/BBSR/tpm2/eventlog.log
  echo "  Event log: /mnt/acs_results/BBSR/tpm2/eventlog.log"
  tpm2_pcrread > /mnt/acs_results/BBSR/tpm2/pcr.log
  echo "  PCRs: /mnt/acs_results/BBSR/tpm2/pcr.log"
  rm /tmp/binary_bios_measurements
  if grep -q "pcrs:" "/mnt/acs_results/BBSR/tpm2/eventlog.log"; then
      echo "PCR reg entry found at the end of eventlog, comparing eventlog vs pcr "
      #TPM2 logs event log v/s tpm.log check
      python3 /bin/verify_tpm_measurements.py /mnt/acs_results/BBSR/tpm2/pcr.log /mnt/acs_results/BBSR/tpm2/eventlog.log | tee /mnt/acs_results/BBSR/tpm2/verify_tpm_measurements.log
  else
      echo "PCR reg entry not found at the end of event log, eventlog vs pcr comparision not possible "
  fi
else
   echo "TPM event log not found at /sys/kernel/security/tpm0/binary_bios_measurements"
fi

exit 0
