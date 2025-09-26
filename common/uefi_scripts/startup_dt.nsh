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

echo -off
connect -r

for %x in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
  if exist FS%x:\acs_tests\bbr\boot_tolinuxprompt.flag then
      echo "Secure Boot just cleared. Skipping ACS tests and booting Linux..."
      goto BootLinux
  endif
endfor

# Clearing Secure Boot Key
for %d in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%d:\acs_tests\bbr\clear_secureboot.flag then
        FS%d:
        cd \acs_tests\app
        # Get SecureBoot value
        setvar SecureBoot > secure.state
        # Fallback to default value (assume disabled unless parsed as '01')
        echo "00" >v secure_boot_on
        # parse the value
        parse secure.state 01 1 -s 0 >v secure_boot_on
        echo "Detected SecureBoot value:"
        setvar SecureBoot
        # Proceed only if Secure Boot is enabled (01)
        if %secure_boot_on% == 01 then
            echo "Secure Boot is ENABLED. Clearing PK..."
            if exist UpdateVars.efi and exist NullPK.auth then
                UpdateVars PK NullPK.auth
                if %lasterror% == 0 then
                    echo "PK cleared successfully."
                    echo "Secure Boot value:"
                    setvar SecureBoot
                else
                    echo "UpdateVars.efi failed. Please verify NullPK.auth and platform state."
                endif
            else
                echo "ERROR: UpdateVars.efi or NullPK.auth not found in acs_tests\app"
            endif
        else
            echo "Secure Boot is already DISABLED (Setup Mode)... skipping PK clearance."
        endif
        # cleanup and reboot
        rm \acs_tests\bbr\clear_secureboot.flag
        echo > \acs_tests\bbr\boot_tolinuxprompt.flag
        echo "System will reboot in 5 seconds..."
        stall 500000
        reset
    endif
endfor

# check if BBSR SCT in progress, if yes resume the run.
for %b in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%b:\acs_tests\bbr\bbsr_inprogress.flag then
        echo "BBSR compliance testing in progress, Resuming ..."
        echo " "
        FS%b:\EFI\BOOT\bbsr_startup.nsh
    endif
endfor

# Run the SCT test
for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_tests\bbr\SctStartup.nsh then
        echo " "
        echo "Running SCT test"
        FS%i:\acs_tests\bbr\SctStartup.nsh %1
        goto DoneSCT
    endif
endfor
:DoneSCT

# Run the Capsule dump
for %e in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%e:\acs_results_template\acs_results then
        FS%e:
        cd FS%e:\acs_results_template\acs_results
        if not exist app_output then
            mkdir app_output
        endif
        cd app_output
        if exist CapsuleApp_FMP_protocol_info.log and exist CapsuleApp_ESRT_table_info.log then
            echo "CapsuleApp already run"
        else
            if exist FS%e:\acs_tests\app\CapsuleApp.efi then
                echo "Running capsule app dump "
                FS%e:\acs_tests\app\CapsuleApp.efi -P > CapsuleApp_FMP_protocol_info.log
                FS%e:\acs_tests\app\CapsuleApp.efi -E > CapsuleApp_ESRT_table_info.log
                goto DoneApp
            endif
        endif
    endif
endfor
:DoneApp

# Run the DebugDump 
for %p in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%p:\acs_tests\debug\debug_dump.nsh then
        echo " "
        echo "Running debug dump"
        FS%p:\acs_tests\debug\debug_dump.nsh
        goto DoneDebug
    endif
endfor
:DoneDebug

# Run the BSA test
for %j in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%j:\acs_tests\bsa\bsa.nsh then
        echo " "
        echo "Running BSA test"
        FS%j:\acs_tests\bsa\bsa.nsh
        goto Donebsa
    endif
endfor
:Donebsa

# Run the PFDI test
for %k in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%k:\acs_tests\pfdi\pfdi.nsh then
        echo " "
        echo "Running pfdi test"
        FS%k:\acs_tests\pfdi\pfdi.nsh
        goto Donepfdi
    endif
endfor
:Donepfdi

# Run the pingtest
for %m in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%m:\acs_tests\debug\pingtest.nsh then
        FS%m:
        cd FS%m:\acs_results_template\acs_results
        if not exist network_logs then
            mkdir network_logs
        endif
        cd network_logs
        echo "Running ping test..."
        ifconfig -r
        echo "Waiting for network to come up..."
        stall 2000000
        echo "" > ping.log
        ping 8.8.8.8 >> ping.log
        type ping.log
        FS%m:\acs_tests\debug\pingtest.nsh ping.log > pingtest.log
        set pingreturn %lasterror%
        type pingtest.log
        if %pingreturn% == 0x0 then
            echo "Ping test passed."
        else
            echo "Ping test failed."
        endif
        goto DonePing
    endif
endfor
:DonePing

# Run the capsule update test
for %r in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%r:\acs_tests\app\capsule_update.nsh then
        echo " "
        echo "Running capsule update test"
        FS%r:\acs_tests\app\capsule_update.nsh
        goto DoneCapsuleUpdate
    endif
endfor
:DoneCapsuleUpdate

goto BootLinux

:BootLinux
for %l in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%l:\Image and exist FS%l:\yocto_image.flag then
        FS%l:
        cd FS%l:\
        echo " "
        echo "Booting Linux"
        Image LABEL=BOOT root=partuid
        goto DoneImage
    endif
endfor

:DoneImage
