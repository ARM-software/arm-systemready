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

# check if BBSR SCT in progress, if yes resume the run.
for %b in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%b:\acs_tests\bbr\bbsr_inprogress.flag then
        echo "BBSR compliance testing in progress, Resuming ..."
        echo " "
        FS%b:\EFI\BOOT\bbsr_startup.nsh
    endif
endfor

# Run the config parser
for %y in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
        if exist FS%y:\acs_tests\parser\Parser.efi then
          if exist FS%y:\acs_tests\config\acs_run_config.ini then
            FS%y:
            echo "Config File content"
            echo " "
            echo " "
            type acs_tests\config\acs_run_config.ini
            echo " "
            echo " "
            echo "Press any key to modify the Config file"
            echo "If no key is pressed then default configurations"
            FS%y:acs_tests\bbr\SCT\Stallforkey.efi 10
            if %lasterror% == 0 then
                acs_tests\parser\parser.nsh
                acs_tests\parser\Parser.efi -automation
                goto DoneParser
            else
                acs_tests\parser\Parser.efi -automation
                goto DoneParser
            endif
          else
            echo "Config file not found at acs_tests/config/acs_run_config.ini"
          endif
        else
            echo "Parser.efi not present at acs_tests/parser/Parser.efi"
        endif
endfor
:DoneParser

# Run the SCT test
for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_tests\bbr\SctStartup.nsh then
        echo " "
        echo "Running SCT test"
        if "%config_enabled_for_automation_run%" == "" then
            echo "config_enabled_for_automation_run variable does not exist"
            FS%i:\acs_tests\bbr\SctStartup.nsh false
            goto DoneSCT
        endif

        if "%config_enabled_for_automation_run%" == "true" then
            FS%i:\acs_tests\bbr\SctStartup.nsh true
        else
            FS%i:\acs_tests\bbr\SctStartup.nsh false
        endif
        goto DoneSCT
    endif
endfor
:DoneSCT

# Run the SCRT test
for %k in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%k:\acs_tests\bbr\ScrtStartup.nsh then
        echo " "
        echo "Running SCRT test"
        if "%config_enabled_for_automation_run%" == "" then
            echo "config_enabled_for_automation_run variable does not exist"
            FS%i:\acs_tests\bbr\ScrtStartup.nsh false
            goto DoneScrt
        endif
        if "%config_enabled_for_automation_run%" == "true" then
            FS%k:\acs_tests\bbr\ScrtStartup.nsh true
        else
            FS%k:\acs_tests\bbr\ScrtStartup.nsh false
        endif
        goto DoneScrt
    endif
endfor
:DoneScrt

# Run the Capsule dump
for %e in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%e:\acs_results then
        FS%e:
        cd FS%e:\acs_results
        if not exist app_output then
            mkdir app_output
        endif
        cd app_output
        if exist CapsuleApp_FMP_protocol_info.log and exist CapsuleApp_ESRT_table_info.log then
            echo " "
            echo "CapsuleApp already run"
        else
            if exist FS%e:\acs_tests\app\CapsuleApp.efi then
                echo " "
                echo "Running capsule app dump"
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
        if "%config_enabled_for_automation_run%" == "" then
            echo "config_enabled_for_automation_run variable does not exist"
            FS%j:\acs_tests\bsa\bsa.nsh false
            goto Donebsa
        endif
        if "%config_enabled_for_automation_run%" == "true" then
            FS%j:\acs_tests\bsa\bsa.nsh true
        else
            FS%j:\acs_tests\bsa\bsa.nsh false
        endif
        goto Donebsa
    endif
endfor
:Donebsa

# Run the SBSA test
for %z in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%z:\acs_tests\bsa\sbsa\sbsa.nsh then
        echo " "
        echo "Running SBSA test"
        if "%config_enabled_for_automation_run%" == "" then
            echo "config_enabled_for_automation_run variable does not exist"
            FS%z:\acs_tests\bsa\sbsa\sbsa.nsh false
            goto Donesbsa
        endif
        if "%config_enabled_for_automation_run%" == "true" then
            FS%z:\acs_tests\bsa\sbsa\sbsa.nsh true
        else
            FS%z:\acs_tests\bsa\sbsa\sbsa.nsh false
        endif
        goto Donesbsa
    endif
endfor
:Donesbsa

# Boot Linux
for %l in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%l:\Image and exist FS%l:\ramdisk-buildroot.img then
        FS%l:
        cd FS%l:\
        echo " "
        echo "Booting Linux"
        Image initrd=\ramdisk-buildroot.img debug crashkernel=512M,high log_buf_len=1M print-fatal-signals=1 efi=debug acpi=on earlycon systemd.log_target=null plymouth.ignore-serial-consoles console=tty0 console=ttyS0  console=ttyAMA0
        goto DoneImage
    endif
endfor
:DoneImage
