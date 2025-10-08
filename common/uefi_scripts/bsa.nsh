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
for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\yocto_image.flag then
        if exist FS%i:\acs_results_template\acs_results then
            FS%i:
            cd FS%i:\acs_results_template\acs_results
            goto RunBsa
        endif
    else
        if exist FS%i:\acs_results then
            FS%i:
            cd FS%i:\acs_results
            goto RunBsa
        endif
    endif
endfor

:RunBsa
# We are here means bsa.nsh is invoked from SystemReady Automation
if "%1" == "true" then
    FS%i:
    acs_tests\parser\Parser.efi -bsa
    if "%automation_bsa_run%" ==  "" then
        echo "automation_bsa_run variable does not exist"
    else
        if "%automation_bsa_run%" == "false" then
            echo "************ BSA is disabled in config file(acs_run_config.ini) ************"
            goto Done
        endif
    endif
endif
if not exist uefi then
    mkdir uefi
endif
cd uefi
if not exist temp then
    mkdir temp
endif

if not exist FS%i:\yocto_image.flag then
    # We are here means bsa.nsh is invoked from UEFI EE
    if "%1" == "" then
        FS%i:
        acs_tests\parser\Parser.efi -bsa
        echo "UEFI EE BSA Command: %BsaCommand%"
        FS%i:\acs_tests\bsa\%BsaCommand% -f BsaTempResults.log
        goto BsaEE
    endif
endif

#BSA_VERSION_PRINT_PLACEHOLDER
if exist FS%i:\acs_tests\bsa\Bsa.efi then
    echo "Press any key to start BSA in verbose mode."
    echo "If no key is pressed then BSA will be run in normal mode"
    FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
    if %lasterror% == 0 then
        if exist BsaVerboseResults.log then
            echo "BSA ACS in verbose mode is already run."
            echo "Press any key to start BSA ACS in verbose mode execution from the beginning."
            echo "WARNING: Ensure you have backed up the existing logs."
            FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
            if %lasterror% == 0 then
                #Backup the existing logs
                rm -q BsaVerboseResults_previous_run.log
                cp -r BsaVerboseResults.log BsaVerboseResults_previous_run.log
                rm -q BsaVerboseResults.log
                goto BsaVerboseRun
            endif
            goto BsaNormalRun
        endif
:BsaVerboseRun
        echo "Running BSA in verbose mode"
        if exist FS%i:\acs_tests\bsa\bsa_dt.flag then
            #Executing for BSA SystemReady-devicetree-band. Execute only OS tests
            echo "BSA Command: Bsa.efi  -v 1 -os -skip 1500 -skip-dp-nic-ms -dtb BsaDevTree.dtb -f BsaVerboseTempResults.log"
            FS%i:\acs_tests\bsa\Bsa.efi -v 1 -os -skip 1500 -skip-dp-nic-ms -dtb BsaDevTree.dtb -f BsaVerboseTempResults.log
        else
            echo "BSA Command: Bsa.efi  -v 1 -skip 1500 -skip-dp-nic-ms -f BsaVerboseTempResults.log"
            FS%i:\acs_tests\bsa\Bsa.efi -v 1 -skip 1500 -skip-dp-nic-ms -f BsaVerboseTempResults.log
        endif
        stall 200000
        if exist BsaVerboseTempResults.log then
            if exist FS%i:\acs_tests\bsa\bsa_dt.flag then
                echo " SystemReady devicetree band ACS v3.1.0" > BsaVerboseResults.log
            else
                echo " SystemReady band ACS v3.1.0" > BsaVerboseResults.log
            endif
            stall 200000
            type BsaVerboseTempResults.log >> BsaVerboseResults.log
            cp BsaVerboseTempResults.log temp/
            rm BsaVerboseTempResults.log
            reset
        else
            echo "There may be issues in writing of BSA Verbose logs. Please save the console output"
        endif
    endif
:BsaNormalRun
    if exist BsaResults.log then
        echo "BSA ACS is already run."
        echo "Press any key to start BSA ACS execution from the beginning."
        echo "WARNING: Ensure you have backed up the existing logs."
        FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
        if %lasterror% == 0 then
            #Backup the existing logs
            rm -q BsaResults_previous_run.log
            cp -r BsaResults.log BsaResults_previous_run.log
            rm -q BsaResults.log
            goto BsaRun
        endif
        goto Done
    endif
:BsaRun
    if exist FS%i:\acs_tests\bsa\bsa_dt.flag then
       #Executing for BSA SystemReady-devicetree-band. Execute only OS tests
       echo "BSA Command: Bsa.efi  -os -skip 1500 -dtb BsaDevTree.dtb -skip-dp-nic-ms -f BsaTempResults.log"
       FS%i:\acs_tests\bsa\Bsa.efi -os -skip 1500 -dtb BsaDevTree.dtb -skip-dp-nic-ms -f BsaTempResults.log
    else
        if "%1" == "false" then
            echo  "BSA Command: Bsa.efi -skip 1500 -skip-dp-nic-ms -f BsaTempResults.log"
            FS%i:\acs_tests\bsa\Bsa.efi -skip 1500 -skip-dp-nic-ms -f BsaTempResults.log
        else
            if "%BsaCommand%" == "" then
                echo "BsaCommand variable does not exist, running default command Bsa.efi -skip 1500 -skip-dp-nic-ms -f BsaTempResults.log"
                FS%i:\acs_tests\bsa\Bsa.efi -skip 1500 -skip-dp-nic-ms -f BsaTempResults.log
            else
                echo  "BSA Command: %BsaCommand% -skip-dp-nic-ms -f BsaTempResults.log "
                FS%i:\acs_tests\bsa\%BsaCommand% -skip-dp-nic-ms -f BsaTempResults.log
            endif
        endif
    endif
    stall 200000
:BsaEE
    if exist BsaTempResults.log then
        if exist FS%i:\acs_tests\bsa\bsa_dt.flag then
            echo " SystemReady devicetree band ACS v3.1.0" > BsaResults.log
        else
            echo " SystemReady band ACS v3.1.0" > BsaResults.log
        endif
        stall 200000
        type BsaTempResults.log >> BsaResults.log
        cp BsaTempResults.log temp/
        rm BsaTempResults.log
        reset
    else
        echo "There may be issues in writing of BSA logs. Please save the console output"
    endif
else
    echo "Bsa.efi not present"
endif
:Done
