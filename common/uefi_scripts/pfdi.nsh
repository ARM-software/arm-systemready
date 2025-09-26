#!/bin/sh

# @file
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
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
            goto RunPfdi
        endif
    endif
endfor

:RunPfdi

if not exist uefi then
    mkdir uefi
endif
cd uefi
if not exist temp then
    mkdir temp
endif


#Pfdi_VERSION_PRINT_PLACEHOLDER
if exist FS%i:\acs_tests\pfdi\pfdi.efi then
    echo "Press any key to start pfdi in verbose mode."
    echo "If no key is pressed then pfdi will be run in normal mode"
    FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
    if %lasterror% == 0 then
        if exist pfdiverboseresults.log then
            echo "pfdi ACS in verbose mode is already run."
            echo "Press any key to start pfdi ACS in verbose mode execution from the beginning."
            echo "WARNING: Ensure you have backed up the existing logs."
            FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
            if %lasterror% == 0 then
                #Backup the existing logs
                rm -q pfdiverboseresults_previous_run.log
                cp -r pfdiverboseresults.log pfdiverboseresults_previous_run.log
                rm -q pfdiverboseresults.log
                goto PfdiVerboseRun
            endif
            goto PfdiNormalRun
        endif
:PfdiVerboseRun
        echo "Running pfdi in verbose mode"
        #Executing for pfdi SystemReady-devicetree-band.
        FS%i:\acs_tests\pfdi\pfdi.efi -v 1 -f pfdiverbosetempresults.log
        stall 200000
        if exist pfdiverbosetempresults.log then
            if exist FS%i:\acs_tests\bsa\bsa_dt.flag then
                echo " SystemReady devicetree band ACS v3.1.0" > pfdiverboseresults.log
            else
                echo " SystemReady band ACS v3.1.0" > pfdiverboseresults.log
            endif
            stall 200000
            type pfdiverbosetempresults.log >> pfdiverboseresults.log
            cp pfdiverbosetempresults.log temp/
            rm pfdiverbosetempresults.log
            reset
        else
            echo "There may be issues in writing ofPfdi Verbose logs. Please save the console output"
        endif
    endif
:PfdiNormalRun
    if exist  pfdiresults.log then
        echo "pfdi ACS is already run."
        echo "Press any key to start pfdi ACS execution from the beginning."
        echo "WARNING: Ensure you have backed up the existing logs."
        FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
        if %lasterror% == 0 then
            #Backup the existing logs
            rm -q pfdiresults_previous_run.log
            cp -r pfdiresults.log pfdiresults_previous_run.log
            rm -q pfdiresults.log
            goto PfdiRun
        endif
        goto Done
    endif
:PfdiRun

    #Executing for pfdi SystemReady-devicetree-band.
    FS%i:\acs_tests\pfdi\pfdi.efi -f pfditempresults.log

    stall 200000
    if exist pfditempresults.log then
        if exist FS%i:\acs_tests\bsa\bsa_dt.flag then
            echo " SystemReady devicetree band ACS v3.1.0" > pfdiresults.log
        else
            echo " SystemReady band ACS v3.1.0" > pfdiresults.log
        endif
        stall 200000
        type pfditempresults.log >> pfdiresults.log
        cp pfditempresults.log temp/
        rm pfditempresults.log
        reset
    else
        echo "There may be issues in writing of pfdi logs. Please save the console output"
    endif
else
    echo "pfdi.efi not present"
endif
:Done