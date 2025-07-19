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

#UpdateVars.efi is present only in the SystemReady-devicetree-band ACS image
#The below block for UpdateVars shall be executed only for SystemReady-devicetree-band
for %q in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%q:\acs_tests\app\UpdateVars.efi then
        FS%q:
        cp -q FS%q:\acs_tests\bbsr-keys\*.auth FS%q:\acs_tests\app\
        cd FS%q:\acs_tests\app
        echo "Printing SecureBoot state"
        setvar SecureBoot
        echo " "
        setvar SecureBoot > secure.state
        echo "00" >v secure_boot_on
        parse secure.state 01 1 -s 0  >v secure_boot_on
        if %secure_boot_on% == 01 then
            echo "System is already in secureboot mode"
            goto StartTest
        endif
        #The state is normal. Attempt to provision secureboot keys
        echo "The System is in normal mode"
        echo "Provisioning the SecureBoot keys..."
        echo " "
        UpdateVars db TestDB1.auth
        UpdateVars dbx TestDBX1.auth
        UpdateVars KEK TestKEK1.auth
        UpdateVars PK TestPK1.auth
        echo "Printing SecureBoot state"
        setvar SecureBoot
        echo " "
        setvar SecureBoot > new_secure.state
        echo "00" >v new_secure_boot_on
        parse new_secure.state 01 1 -s 0  >v new_secure_boot_on
        if %new_secure_boot_on% == 01 then
            echo "Automatic provision of secureboot keys is success."
            echo "The System is now in SecureBoot mode"
            echo " "
            goto StartTest
        else
            echo "Automatic provision of secureboot keys is failed."
            echo "Provision the secureboot keys manually and choose this option again in the grub menu"
            echo " "
            echo "The system will reset in 20 seconds"
            #Stall for 20 seconds
            stall 2000000
            reset
        endif
    endif
endfor

:StartTest
# Run the config parser
for %b in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%b:\acs_tests\parser\Parser.efi then
        if exist FS%b:\acs_tests\config\acs_run_config.ini then
            FS%b:
            echo "Config File content"
            echo " "
            echo " "
            type acs_tests\config\acs_run_config.ini
            echo " "
            echo " "
            echo "Press any key to modify the Config file"
            echo "If no key is pressed then default configurations"
            FS%b:\acs_tests\bbr\SCT\Stallforkey.efi 10
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
    endif
endfor
:DoneParser
for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh then
        # flag BBSR compliance testing is in progress
        echo "" > FS%i:\acs_tests\bbr\bbsr_inprogress.flag
        echo "Running SCT test"
        if exist FS%i:\yocto_image.flag then
            FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh
        else
            if "%config_enabled_for_automation_run%" == "" then
                echo "config_enabled_for_automation_run variable does not exist"
                FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh false
            else
                if "%config_enabled_for_automation_run%" == "true" then
                    FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh true
                else
                    FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh false
                endif
            endif
        endif
        # remove bbsr_inprogress.flag file to mark BBSR compliance testing,
        # as we secureboot to Linux in next step
        rm FS%i:\acs_tests\bbr\bbsr_inprogress.flag
    endif
endfor

# Boot Linux with SecureBoot enabled
echo "Booting Linux (SecureBoot)"
for %l in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    # Buildroot based build (SystemReady band)
    if exist FS%l:\Image and exist FS%l:\ramdisk-buildroot.img then
        FS%l:
        cd FS%l:\
        Image initrd=\ramdisk-buildroot.img rootwait verbose debug psci_checker=disable console=tty0 console=ttyS0  console=ttyAMA0 secureboot
    endif
    # Yocto based build (SystemReady-DT band)
    if exist FS%l:\Image and exist FS%l:\yocto_image.flag then
        FS%l:
        cd FS%l:\
        # Below command is placeholder that is populated with working parameters during SystemReady DT ACS build
        Image LABEL=BOOT secureboot
    endif
endfor
echo "Image not found"

