#!/bin/sh

# Copyright (c) 2023-2025, Arm Limited or its affiliates. All rights reserved.
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

if ! grep -q "ttySC0" /etc/securetty; then
  echo "ttySC0" >> /etc/securetty
  echo "added ttySC0"
fi

if ! grep -q "ttyAML0" /etc/securetty; then
  echo "ttyAML0" >> /etc/securetty
  echo "added ttyAML0"
fi

sleep 5

echo "Attempting to mount the results partition ..."
#mount result partition
BLOCK_DEVICE_NAME=$(blkid | grep "BOOT_ACS" | awk -F: '{print $1}' | head -n 1 )

if [ ! -z "$BLOCK_DEVICE_NAME" ]; then
  mount -o rw $BLOCK_DEVICE_NAME /mnt
  echo "Mounted the results partition on device $BLOCK_DEVICE_NAME"
else
  echo "Warning: the results partition could not be mounted. Logs may not be saved correctly"
fi
sleep 3

if [ -f /mnt/acs_tests/bbr/boot_tolinuxprompt.flag ]; then
  echo "Booted after Secure Boot clearance. Skipping ACS tests, Booting to Linux terminal..."
  rm /mnt/acs_tests/bbr/boot_tolinuxprompt.flag
 # echo "Please press <Enter> to continue ..."
  exit 0
fi

#Skip running of ACS Tests if the grub option is added
ADDITIONAL_CMD_OPTION="";
ADDITIONAL_CMD_OPTION=`cat /proc/cmdline | awk '{ print $NF}'`

if [ $ADDITIONAL_CMD_OPTION != "noacs" ]; then
    SECURE_BOOT="";
    SECURE_BOOT=`cat /proc/cmdline | awk '{ print $NF}'`

    if [ $SECURE_BOOT = "secureboot" ]; then
      echo "Call BBSR ACS in Linux"
      /usr/bin/secure_init.sh
      echo "BBSR ACS run is completed\n"
      secureboot_state=$(hexdump -v -e '1/1 "%02x"' /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c 2>/dev/null | tail -c 2)
      if [ "$secureboot_state" = "01" ]; then
        echo -e "\033[1;31m*** Secure Boot is ENABLED. Disabling Secure Boot.....     ***\033[0m"
        touch /mnt/acs_tests/bbr/clear_secureboot.flag
        sync
        umount /mnt
        echo "Rebooting system to enter UEFI shell"
        sleep 1
        reboot
        sleep 3
      else
        echo "Secure Boot is not enabled. Skipping secureboot PK clearance"
        echo "Please press <Enter> to continue ..."
        echo -e -n "\n"
        exit 0
      fi
    fi

    check_flag=0
    if [ -f /mnt/acs_tests/app/capsule_update_done.flag ] || [ -f /mnt/acs_tests/app/capsule_update_ignore.flag ] || [ -f /mnt/acs_tests/app/capsule_update_unsupport.flag ] || [ -f /mnt/acs_tests/app/linux_run_complete.flag ]; then
      check_flag=1
    fi

    if [ $check_flag -eq 0 ]; then
      capsule_update_check=0
      touch /mnt/acs_tests/app/capsule_update_check.flag
      if [ $? -eq 0 ]; then
        echo "Successfully created capsule update check flag"
        capsule_update_check=1
      else
        echo "Failed to create capsule update check flag"
      fi
      touch /mnt/acs_tests/app/linux_run_complete.flag


      #LINUX DEBUG DUMP
      echo "Collecting Linux debug logs"
      LINUX_DUMP_DIR="/mnt/acs_results_template/acs_results/linux_dump"
      mkdir -p $LINUX_DUMP_DIR
      echo 1 > /proc/sys/kernel/printk
      timedatectl set-ntp true &> $LINUX_DUMP_DIR/set_ntp_time.log
      timedatectl &> $LINUX_DUMP_DIR/timedatectl.log
      echo 7 > /proc/sys/kernel/printk
      lspci -vvv &> $LINUX_DUMP_DIR/lspci.log
      lsusb    > $LINUX_DUMP_DIR/lsusb.log
      uname -a > $LINUX_DUMP_DIR/uname.log
      dmesg > $LINUX_DUMP_DIR/dmesg.log
      journalctl > $LINUX_DUMP_DIR/journalctl.log
      cat /proc/interrupts > $LINUX_DUMP_DIR/interrupts.log
      cat /proc/cpuinfo    > $LINUX_DUMP_DIR/cpuinfo.log
      cat /proc/meminfo    > $LINUX_DUMP_DIR/meminfo.log
      cat /proc/iomem      > $LINUX_DUMP_DIR/iomem.log
      ls -lR /sys/firmware > $LINUX_DUMP_DIR/firmware.log
      cp -r /sys/firmware $LINUX_DUMP_DIR/
      dmidecode  > $LINUX_DUMP_DIR/dmidecode.log
      efibootmgr > $LINUX_DUMP_DIR/efibootmgr.log
      fwupdmgr get-devices          &> $LINUX_DUMP_DIR/fwupd_getdevices.log
      echo "0" | fwupdtool esp-list &> $LINUX_DUMP_DIR/fwupd_esplist.log
      fwupdmgr get-bios-settings    &> $LINUX_DUMP_DIR/fwupd_bios_setting.log
      fwupdmgr get-history          &> $LINUX_DUMP_DIR/fwupd_get_history.log
      sync /mnt
      sleep 5
      echo "Linux debug logs run - Completed"


      # FWTS EBBR run
      mkdir -p /mnt/acs_results_template/acs_results/fwts
      echo "Executing FWTS for EBBR"
      test_list=`cat /usr/bin/ir_bbr_fwts_tests.ini | grep -v "^#" | awk '{print $1}' | xargs`
      echo "Test Executed are $test_list"
      echo "SystemReady devicetree band ACS v3.1.0" > /mnt/acs_results_template/acs_results/fwts/FWTSResults.log
      /usr/bin/fwts --ebbr `echo $test_list` -r stdout >> /mnt/acs_results_template/acs_results/fwts/FWTSResults.log
      echo -e -n "\n"
      sync /mnt
      sleep 5
      echo "FWTS test execution - Completed"


      #LINUX BSA RUN
      mkdir -p /mnt/acs_results_template/acs_results/linux_acs/bsa_acs_app
      if [ -f /lib/modules/*/kernel/bsa_acs/bsa_acs.ko ]; then
        echo "Running Linux BSA tests"
        insmod /lib/modules/*/kernel/bsa_acs/bsa_acs.ko
        echo "SystemReady devicetree band ACS v3.1.0" > /mnt/acs_results_template/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
        bsa --skip-dp-nic-ms >> /mnt/acs_results_template/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
        dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results_template/acs_results/linux_acs/bsa_acs_app/BsaResultsKernel.log
        sync /mnt
        sleep 5
        echo "Linux BSA test execution - Completed"
      else
        echo "Error: BSA kernel Driver is not found. Linux BSA tests cannot be run"
      fi


      # Device Driver Info script
      mkdir -p /home/root/fdt
      mkdir -p /mnt/acs_results_template/acs_results/linux_tools
      pushd /usr/bin
      echo "running device_driver_info.sh device and driver info created"
      ./device_driver_info.sh
      cp device_driver_info.log /mnt/acs_results_template/acs_results/linux_tools
      echo "device driver script run completed"
      popd
      sync /mnt
      sleep 5


      # DT VALIDATE RUN
      # Generate the .dts file and move it to /mnt/acs_results_template/acs_results/linux_tools
      dtc -I fs -O dts -o /mnt/acs_results_template/acs_results/linux_tools/device_tree.dts /sys/firmware/devicetree/base 2>/dev/null
      # Generate tree format of sys hierarchy and saving it into logs.
      tree -d /sys > /mnt/acs_results_template/acs_results/linux_dump/sys_hierarchy.log
      if [ -f /sys/firmware/fdt ]; then
        echo "copying fdt "
        cp /sys/firmware/fdt /home/root/fdt
        sync /mnt

        # Device Tree Validate script
        if [ -f /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log ]; then
          mv /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log.old
        fi
        echo "Running dt-validate tool "
        dt-validate -s /usr/bin/processed_schema.json -m /home/root/fdt/fdt 2>> /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log
        sed -i '1s/^/DeviceTree bindings of Linux kernel version: 6.16 \ndtschema version: 2025.02 \n\n/' /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log
        if [ ! -s /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log ]; then
          echo "The FDT is compliant according to schema " >> /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log
        fi
        # Run dt parser on dt-validate log to categorize failures
        /usr/bin/systemready-scripts/dt-parser.py /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log --print 2>&1 | tee /mnt/acs_results_template/acs_results/linux_tools/dt-validate-parser.log
      else
        echo  "Error: The FDT devicetree file, fdt, does not exist at /sys/firmware/fdt. Cannot run dt-schema tool" | tee /mnt/acs_results_template/acs_results/linux_tools/dt-validate.log
      fi
      sync /mnt
      sleep 5


      # Capturing System PSCI command output
      echo "Collecting psci command output"
      mkdir -p /mnt/acs_results_template/acs_results/linux_tools/psci
      mount -t debugfs none /sys/kernel/debug
      cat /sys/kernel/debug/psci > /mnt/acs_results_template/acs_results/linux_tools/psci/psci.log
      dmesg | grep psci > /mnt/acs_results_template/acs_results/linux_tools/psci/psci_kernel.log
      sync /mnt
      sleep 5
      echo "PSCI command output - Completed"


      # DT Kernel Self test run
      echo "Running DT Kernel Self Test"
      pushd /usr/kernel-selftest
      chmod +x dt/test_unprobed_devices.sh
      chmod +x kselftest/ktap_helpers.sh
      ./run_kselftest.sh -t dt:test_unprobed_devices.sh > /mnt/acs_results_template/acs_results/linux_tools/dt_kselftest.log
      popd
      sync /mnt
      sleep 5
      echo "DT Kernel Self test run - Completed"


      # ETHTOOL test run
      echo "Running Ethtool test"
      # update resolv.conf with 8.8.8.8 DNS server
      echo "nameserver 8.8.8.8" >> /etc/resolv.conf
      # run ethtool-test.py, dump ethernet information, run self-tests if supported, and ping
      python3 /bin/ethtool-test.py | tee ethtool-test.log
      # remove color characters from log and save
      awk '{gsub(/\x1B\[[0-9;]*[JKmsu]/, "")}1' ethtool-test.log > /mnt/acs_results_template/acs_results/linux_tools/ethtool-test.log
      sync /mnt
      sleep 5
      echo "Ethtool test run - Completed"


      # READ_WRITE_BLOCK_DEVICE run
      # RUN read_write_check_blk_devices.py, parse block devices, and perform read if partition doesn't belond in precious partitions
      echo "Running BLK devices read and write check"
      python3 /bin/read_write_check_blk_devices.py | tee /mnt/acs_results_template/acs_results/linux_tools/read_write_check_blk_devices.log
      sync /mnt
      sleep 5
      echo "BLK devices read and write check - Completed"

      if [ $capsule_update_check -eq 1 ]; then
        umount /mnt
        sleep 5
        echo "System is rebooting for Capsule update"
        reboot
      fi
    else
      if [ -f /mnt/acs_tests/app/capsule_update_done.flag ]; then
        fw_pattern="^ *FwVersion\s*-\s*(0x[0-9A-Fa-f]+)"
        fw_status_pattern="^ *LastAttemptStatus\s*-\s*(0x[0-9A-Fa-f]+)"
        fw_class_pattern="^ *FwClass\s*-\s*([A-Fa-f0-9\-]+)"
        fw_status="0x0"
        extract_script_path="/usr/bin/extract_capsule_fw_version.py"
        before_update_log="/mnt/acs_results_template/fw/CapsuleApp_ESRT_table_info_before_update.log"
        after_update_log="/mnt/acs_results_template/fw/CapsuleApp_ESRT_table_info_after_update.log"

        i=0
        for val in $(python3 "$extract_script_path" "$fw_class_pattern" "$before_update_log" | tr '\n' ' '); do
          eval "fw_class_$i='$val'"
          i=$((i+1))
        done

        i=0
        for val in $(python3 "$extract_script_path" "$fw_guid" "$before_update_log" | tr '\n' ' '); do
          eval "fw_guid_$i='$val'"
          i=$((i+1))
        done

        i=0
        for val in $(python3 "$extract_script_path" "$fw_pattern" "$before_update_log" | tr '\n' ' '); do
          eval "prev_fw_$i='$val'"
          i=$((i+1))
        done
        entry_count=$i

        i=0
        for val in $(python3 "$extract_script_path" "$fw_pattern" "$after_update_log" | tr '\n' ' '); do
          eval "cur_fw_$i='$val'"
          i=$((i+1))
        done

        i=0
        for val in $(python3 "$extract_script_path" "$fw_status_pattern" "$after_update_log" | tr '\n' ' '); do
          eval "status_fw_$i='$val'"
          i=$((i+1))
        done

        echo "Testing ESRT FW version update" > /mnt/acs_results_template/fw/capsule_test_results.log
        overall_result="PASSED"
        i=0
        while [ $i -lt $entry_count ]; do
          eval prev_val=\$prev_fw_$i
          eval cur_val=\$cur_fw_$i
          eval status_val=\$status_fw_$i
          eval guid_val=\$fw_class_$i

          [ -z "$status_val" ] && status_val="0xFFFFFFFF"

          echo "INFO: Fmp Payload GUID:$guid_val, prev version: $prev_val, current version: $cur_val, last attempted status: $status_val" >> /mnt/acs_results_template/fw/capsule_test_results.log

          prev_ver=$(printf "%d" "$prev_val")
          cur_ver=$(printf "%d" "$cur_val")
          prev_status=$(printf "%d" "$status_val")
          expected_status=$(printf "%d" "$fw_status")
          if [ "$cur_ver" -gt "$prev_ver" ] && [ "$prev_status" -eq "$expected_status" ]; then
            echo "RESULTS: Fmp Payload  with GUID $guid_val was successfully update -- PASSED" >> /mnt/acs_results_template/fw/capsule_test_results.log
          else
            echo "RESULTS: Fmp Payload  with GUID $guid_val failed to update -- FAILED" >> /mnt/acs_results_template/fw/capsule_test_results.log
            overall_result="FAILED"
          fi
          i=$((i+1))
        done
        echo "RESULTS: Overall Capsule Update Result: $overall_result" >> /mnt/acs_results_template/fw/capsule_test_results.log
        rm /mnt/acs_tests/app/capsule_update_done.flag
      elif [ -f /mnt/acs_tests/app/capsule_update_unsupport.flag ]; then
        echo "Capsule update has failed"
        echo "Capsule update has failed ..." >> /mnt/acs_results_template/fw/capsule_test_results.log
        rm /mnt/acs_tests/app/capsule_update_unsupport.flag
      else
        echo "Capsule update has ignored..."
        rm /mnt/acs_tests/app/capsule_update_ignore.flag
      fi


      # EDK2 Parser Tool run
      if [ -d "/mnt/acs_results_template/acs_results/sct_results" ]; then
        echo "Running edk2-test-parser tool "
        mkdir -p /mnt/acs_results_template/acs_results/edk2-test-parser
        cd /usr/bin/edk2-test-parser
        ./parser.py --md /mnt/acs_results_template/acs_results/edk2-test-parser/edk2-test-parser.log /mnt/acs_results_template/acs_results/sct_results/Overall/Summary.ekl /mnt/acs_results_template/acs_results/sct_results/Sequence/EBBR.seq > /dev/null 2>&1
        echo "edk2-test-parser run completed"
      else
        echo "SCT result does not exist, cannot run edk2-test-parser tool cannot run"
      fi
      sync /mnt
      sleep 5


      # systemready-scripts running
      if [ -d "/mnt/acs_results_template" ]; then
        echo "Running post scripts "
        cd /mnt/acs_results_template
        mkdir -p /mnt/acs_results_template/acs_results/post-script
        #/usr/bin/systemready-scripts/check-sr-results.py --dir /mnt/acs_results_template > /mnt/acs_results_template/acs_results/post-script/post-script.log 2>&1
        /usr/bin/systemready-scripts/check-sr-results.py --dir /mnt/acs_results_template 2>&1 | tee /mnt/acs_results_template/acs_results/post-script/post-script.log
		cd -
      fi
      sync /mnt
      sleep 5


      # ACS Log Parser run
      echo "Running acs log parser tool "
      if [ -d "/mnt/acs_results_template" ]; then
        if [ -d "/mnt/acs_results_template/acs_results/acs_summary" ]; then
          rm -r /mnt/acs_results_template/acs_results/acs_summary
        fi
      /usr/bin/log_parser/main_log_parser.sh /mnt/acs_results_template/acs_results /mnt/acs_tests/config/acs_config.txt /mnt/acs_tests/config/system_config.txt /mnt/acs_tests/config/acs_waiver.json
      fi
      # Copying acs_waiver.json into result directory.
      if [ -f /mnt/acs_tests/config/acs_waiver.json ]; then
        mkdir -p /mnt/acs_results_template/acs_results/acs_summary/config
        cp /mnt/acs_tests/config/acs_waiver.json /mnt/acs_results_template/acs_results/acs_summary/config
      fi
      echo "Please wait acs results are syncing on storage medium."
      sync /mnt
      sleep 60

      echo "ACS automated test suites run is completed."
      echo "Please reboot to run BBSR tests if not done"
    fi
else
  echo ""
  echo "Additional option set to not run ACS Tests. Skipping ACS tests on Linux"
  echo ""
fi

echo "Please press <Enter> to continue ..."
echo -e -n "\n"
exit 0
