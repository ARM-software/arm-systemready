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

for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh then
        # create a file to mark BBSR SCT in progress
        echo "" > FS%i:\acs_tests\bbr\bbsr_sct_inprogress.flag
        FS%i:\acs_tests\bbr\bbsr_SctStartup.nsh
        # remove bbsr_sct_inprogress.flag file to mark BBSR SCT complete
        rm FS%i:\acs_tests\bbr\bbsr_sct_inprogress.flag
        for %k in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
            if  exist FS%k:\acs_results\BBSR\sct_results\ then
                if  exist FS%i:\acs_tests\bbr\SCT\Overall then
                    cp -r FS%i:\acs_tests\bbr\SCT\Overall FS%k:\acs_results\BBSR\sct_results\
                endif
                if  exist FS%i:\acs_tests\bbr\SCT\Dependency\EfiCompliantBBTest then
                    cp -r FS%i:\acs_tests\bbr\SCT\Dependency\EfiCompliantBBTest FS%k:\acs_results\BBSR\sct_results\
                endif
                if  exist FS%i:\acs_tests\bbr\SCT\Sequence then
                    cp -r FS%i:\acs_tests\bbr\SCT\Sequence FS%k:\acs_results\BBSR\sct_results\
                endif
            endif
        endfor
     echo "BBSR SCT test suite execution is complete. Resetting the system"
     reset
     endif
endfor

