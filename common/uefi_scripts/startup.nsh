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

echo -off
connect -r

# Run the config parser
for %a in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%a:\acs_tests\parser\Parser.efi  then
        FS%a:\acs_tests\parser\Parser.efi
    endif
endfor

# check if BBSR SCT in progress, if yes resume the run.
for %b in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%b:\acs_tests\bbr\bbsr_sct_inprogress.flag then
        echo "BBSR SCT in progress, Resuming ..."
        FS%b:\EFI\BOOT\bbsr_startup.nsh
    endif
endfor

for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_tests\bbr\SctStartup.nsh then
        FS%i:\acs_tests\bbr\SctStartup.nsh %1
        goto DoneSCT
    endif
endfor
:DoneSCT

for %k in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%k:\acs_tests\bbr\ScrtStartup.nsh then
        FS%k:\acs_tests\bbr\ScrtStartup.nsh
        goto Donebbr
    endif
endfor
:Donebbr

for %e in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%e:\acs_results then
        FS%e:
        cd FS%e:\acs_results
        if not exist app_output then
            mkdir app_output
        endif
        cd app_output
        for %q in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
            if exist FS%q:\acs_tests\app\CapsuleApp.efi then
                echo "Running CapsuleApp "
                FS%q:\acs_tests\app\CapsuleApp.efi -P > CapsuleApp_FMP_protocol_info.log
                FS%q:\acs_tests\app\CapsuleApp.efi -E > CapsuleApp_ESRT_table_info.log
                goto DoneApp
            endif
        endfor
    endif
endfor
:DoneApp

for %p in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%p:\acs_tests\debug\debug_dump.nsh then
        FS%p:\acs_tests\debug\debug_dump.nsh
        goto DoneDebug
    endif
endfor
:DoneDebug

for %j in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%j:\acs_tests\bsa\bsa.nsh then
        FS%j:\acs_tests\bsa\bsa.nsh
        goto Donebsa
    endif
endfor
:Donebsa

for %z in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%z:\acs_tests\bsa\sbsa\sbsa.nsh then
        FS%z:\acs_tests\bsa\sbsa\sbsa.nsh
        goto Donesbsa
    endif
endfor
:Donesbsa

for %m in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%m:\acs_tests\debug\pingtest.nsh and exist FS%m:\yocto_image.flag then
        FS%m:
        cd FS%m:\acs_results
        if not exist network_logs then
            mkdir network_logs
        endif
        cd network_logs
        echo Running ping test...
        ifconfig -r
        echo Waiting for network to come up...
        stall 200000
        echo "" > ping.log
        ping 8.8.8.8 >> ping.log
        type ping.log
        FS%m:\acs_tests\debug\pingtest.nsh ping.log > pingtest.log
        set pingreturn %lasterror%
        type pingtest.log
        if %pingreturn% == 0x0 then
            echo Ping test passed.
        else
            echo Ping test failed.
        endif
        goto DonePing
    endif
endfor
:DonePing

# check for capsule update
for %r in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%r:\yocto_image.flag and exist FS%r:\acs_tests\app\capsule_update_check.flag then
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
            goto BootLinux
        endif
:CapsuleUpdate
        if exist FS%r:\acs_tests\app\signed_capsule.bin then
	    if exist FS%r:\acs_results_template then
	        mkdir FS%r:\acs_results_template\fw
	    else
	       echo " template directory not present"
	       goto BootLinux
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
	      echo "unauth.bin not present"
	    endif
            echo "Testing tampered.bin update" >> FS%r:\acs_results_template\fw\capsule-update.log
	    echo "Test_Info" >>  FS%r:\acs_results_template\fw\capsule-update.log
	    if exist FS%r:\acs_tests\app\tampered.bin then
              FS%r:\acs_tests\app\CapsuleApp.efi FS%r:\acs_tests\app\tampered.bin >> FS%r:\acs_results_template\fw\capsule-update.log
	    else
	      echo "tampered.bin not present"
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
	    echo "signed_capsule.bin not present" >  FS%r:\acs_results_template\fw\capsule-on-disk.log
            echo "signed_capsule.bin file is not present, please copy the same file into acs_tests/app partition"
        endif
        goto BootLinux
    else
        if exist FS%r:\yocto_image.flag and exist FS%r:\acs_tests\app\capsule_update_done.flag then
            smbiosview > FS%r:\acs_results_template\fw\smbiosview_after_update.log
            FS%r:\acs_tests\app\CapsuleApp.efi -E > FS%r:\acs_results_template\fw\CapsuleApp_ESRT_table_info_after_update.log
            FS%r:\acs_tests\app\CapsuleApp.efi -P > FS%r:\acs_results_template\fw\CapsuleApp_FMP_table_info_after_update.log
	    echo "Capsule Update done!!!"
        endif
        goto BootLinux
    endif
endfor

:BootLinux
echo "Booting Linux"
for %l in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%l:\Image and exist FS%l:\ramdisk-buildroot.img then
        FS%l:
        cd FS%l:\
        Image initrd=\ramdisk-buildroot.img debug crashkernel=512M,high log_buf_len=1M print-fatal-signals=1 efi=debug acpi=on earlycon systemd.log_target=null plymouth.ignore-serial-consoles console=tty0 console=ttyS0  console=ttyAMA0
    endif
    if exist FS%l:\Image and exist FS%l:\ramdisk-busybox.img then
        FS%l:
        cd FS%l:\
        Image initrd=\ramdisk-busybox.img debug crashkernel=512M,high log_buf_len=1M print-fatal-signals=1 efi=debug acpi=on earlycon systemd.log_target=null plymouth.ignore-serial-consoles
    endif
    if exist FS%l:\Image and exist FS%l:\yocto_image.flag then
        FS%l:
        cd FS%l:\
        Image LABEL=BOOT root=partuid rootfstype=ext4
    endif
endfor
echo "Image not found"
