#!/bin/sh

# @file
# Copyright (c) 2025-, Arm Limited or its affiliates. All rights reserved.
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

echo -off

#The below capsule update block shall be supported only for SystemReady-devicetree-band
# check for capsule update
for %r in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%r:\acs_tests\app\capsule_update.nsh then
        if exist FS%r:\acs_tests\app\capsule_update_check.flag then
            echo "press any key to test capsule update"
            FS%r:\acs_tests\bbr\SCT\stallforkey.efi 10
            if %lasterror% == 0 then
                goto CapsuleUpdate
            else
                if exist FS%r:\acs_tests\app\capsule_update_check.flag then
                    echo "capsule update is pending, press any key to skip capsule update"
                    FS%r:\acs_tests\bbr\SCT\stallforkey.efi 10
                    if %lasterror% == 0 then
                        rm FS%r:\acs_tests\app\capsule_update_check.flag
                        echo "" > FS%r:\acs_tests\app\capsule_update_ignore.flag
                        echo "Capsule Update is ignored!!!"
                    else
                        goto CapsuleUpdate
                    endif
                endif
                goto Done
            endif
:CapsuleUpdate
            if exist FS%r:\acs_tests\app\signed_capsule.bin then
                if exist FS%r:\acs_results_template then
                    mkdir FS%r:\acs_results_template\fw
                else
                    echo " template directory not present"
                    goto Done
                endif
                smbiosview > FS%r:\acs_results_template\fw\smbiosview_before_update.log
                FS%r:\acs_tests\app\CapsuleApp.efi -E > FS%r:\acs_results_template\fw\CapsuleApp_ESRT_table_info_before_update.log
                FS%r:\acs_tests\app\CapsuleApp.efi -P > FS%r:\acs_results_template\fw\CapsuleApp_FMP_table_info_before_update.log
                rm FS%r:\acs_tests\app\capsule_update_check.flag
                echo "" > FS%r:\acs_tests\app\capsule_update_done.flag
                echo "UEFI capsule update is in progress, system will reboot after update ..."
                echo "Testing unauth.bin update" > FS%r:\acs_results_template\fw\capsule-update.log
                echo "Test_Info" >>  FS%r:\acs_results_template\fw\capsule-update.log
                if exist FS%r:\acs_tests\app\unauth.bin then
                    FS%r:\acs_tests\app\CapsuleApp.efi FS%r:\acs_tests\app\unauth.bin >> FS%r:\acs_results_template\fw\capsule-update.log
                else
                    echo "unauth.bin not present" >> FS%r:\acs_results_template\fw\capsule-update.log
                endif
                echo "Testing tampered.bin update" >> FS%r:\acs_results_template\fw\capsule-update.log
                echo "Test_Info" >>  FS%r:\acs_results_template\fw\capsule-update.log
                if exist FS%r:\acs_tests\app\tampered.bin then
                    FS%r:\acs_tests\app\CapsuleApp.efi FS%r:\acs_tests\app\tampered.bin >> FS%r:\acs_results_template\fw\capsule-update.log
                else
                    echo "tampered.bin not present" >> FS%r:\acs_results_template\fw\capsule-update.log
                endif
                echo "Testing signed_capsule.bin OD update" > FS%r:\acs_results_template\fw\capsule-on-disk.log
                echo "Test_Info" >> FS%r:\acs_results_template\fw\capsule-on-disk.log
                FS%r:\acs_tests\app\CapsuleApp.efi FS%r:\acs_tests\app\signed_capsule.bin -OD >> FS%r:\acs_results_template\fw\capsule-on-disk.log
                echo "UEFI capsule update has failed..." >> FS%r:\acs_results_template\fw\capsule-on-disk.log
                rm FS%r:\acs_tests\app\capsule_update_check.flag
                rm FS%r:\acs_tests\app\capsule_update_done.flag
                echo "" > FS%r:\acs_tests\app\capsule_update_unsupport.flag
                smbiosview > FS%r:\acs_results_template\fw\smbiosview_after_update.log
                FS%r:\acs_tests\app\CapsuleApp.efi -E > FS%r:\acs_results_template\fw\CapsuleApp_ESRT_table_info_after_update.log
                FS%r:\acs_tests\app\CapsuleApp.efi -P > FS%r:\acs_results_template\fw\CapsuleApp_FMP_table_info_after_update.log
            else
                rm FS%r:\acs_tests\app\capsule_update_check.flag
                mkdir FS%r:\acs_results_template\fw
                echo "" > FS%r:\acs_tests\app\capsule_update_unsupport.flag
                echo "Testing signed_capsule.bin OD update" > FS%r:\acs_results_template\fw\capsule-on-disk.log
                echo "Test_Info" >> FS%r:\acs_results_template\fw\capsule-on-disk.log
                echo "signed_capsule.bin not present" >>  FS%r:\acs_results_template\fw\capsule-on-disk.log
                echo "signed_capsule.bin file is not present, please copy the same file into acs_tests/app partition"
            endif
            goto Done
        else
            if exist FS%r:\acs_tests\app\capsule_update_done.flag then
                smbiosview > FS%r:\acs_results_template\fw\smbiosview_after_update.log
                FS%r:\acs_tests\app\CapsuleApp.efi -E > FS%r:\acs_results_template\fw\CapsuleApp_ESRT_table_info_after_update.log
                FS%r:\acs_tests\app\CapsuleApp.efi -P > FS%r:\acs_results_template\fw\CapsuleApp_FMP_table_info_after_update.log
                echo "Capsule Update done!!!"
            endif
            goto Done
        endif
    endif
endfor
:Done
