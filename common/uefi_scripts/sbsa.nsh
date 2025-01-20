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
for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_results then
        FS%i:
        cd FS%i:\acs_results
        if not exist uefi then
            mkdir uefi
        endif
        cd uefi
        if not exist temp then
            mkdir temp
        endif
        if exist FS%i:\acs_tests\bsa\sbsa\Sbsa.efi then
	    if not exist FS%i:\acs_tests\parser\SbsaRunEnabled.flag then
	        goto Done
	    endif
            echo "Press any key to start SBSA in verbose mode."
            echo "If no key is pressed then SBSA will be run in normal mode"
            FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
            if %lasterror% == 0 then
                if exist FS%i:\acs_results\uefi\SbsaVerboseResults.log then
                    echo "SBSA ACS in verbose mode is already run."
                    echo "Press any key to start SBSA ACS execution from the beginning."
                    echo "WARNING: Ensure you have backed up the existing logs."
                    FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
                    if %lasterror% == 0 then
                        #Backup the existing logs
                        rm -q FS%i:\acs_results\uefi\SbsaVerboseResults_previous_run.log
                        cp -r FS%i:\acs_results\uefi\SbsaVerboseResults.log FS%i:\acs_results\uefi\SbsaVerboseResults_previous_run.log
                        rm -q FS%i:\acs_results\uefi\SbsaVerboseResults.log
                        goto SbsaVerboseRun
                    endif
                    goto SbsaNormalMode
                endif
:SbsaVerboseRun
                echo "Running SBSA in verbose mode"
                FS%i:\acs_tests\bsa\sbsa\Sbsa.efi -v 1 -skip 900 -f SbsaVerboseTempResults.log
                stall 200000
                if exist FS%i:\acs_results\uefi\SbsaVerboseTempResults.log then
                    echo " SystemReady band ACS v3.0.0-BETA0" > SbsaVerboseResults.log
                    stall 200000
                    type SbsaVerboseTempResults.log >> SbsaVerboseResults.log
                    cp SbsaVerboseTempResults.log temp/
                    rm SbsaVerboseTempResults.log
                    reset
                else
                    echo "There may be issues in writing of SBSA Verbose logs. Please save the console output"
                    reset
                endif
            endif
:SbsaNormalMode
            if exist FS%i:\acs_results\uefi\SbsaResults.log then
                echo "SBSA ACS is already run."
                echo "Press any key to start SBSA ACS execution from the beginning."
                echo "WARNING: Ensure you have backed up the existing logs."
                FS%i:\acs_tests\bbr\SCT\stallforkey.efi 10
                if %lasterror% == 0 then
                    #Backup the existing logs
                    rm -q FS%i:\acs_results\uefi\SbsaResults_previous_run.log
                    cp -r FS%i:\acs_results\uefi\SbsaResults.log FS%i:\acs_results\uefi\SbsaResults_previous_run.log
                    rm -q FS%i:\acs_results\uefi\SbsaResults.log
                    goto SbsaNormalRun
                endif
                goto Done
            endif
:SbsaNormalRun
            FS%i:\acs_tests\bsa\sbsa\Sbsa.efi -skip 900 -f SbsaTempResults.log
            stall 200000
            if exist FS%i:\acs_results\uefi\SbsaTempResults.log then
                echo " SystemReady band ACS v3.0.0-BETA0" > SbsaResults.log
                stall 200000
                type SbsaTempResults.log >> SbsaResults.log
                cp SbsaTempResults.log temp/
                rm SbsaTempResults.log
                reset
            else
                echo "There may be issues in writing of SBSA logs. Please save the console output"
                reset
            endif
        else
            echo "Sbsa.efi not present"
        endif
        goto Done
    endif
endfor
echo "acs_results not found"
:Done
if exist FS%i:\acs_tests\parser\SbsaRunEnabled.flag then
  rm FS%i:\acs_tests\parser\SbsaRunEnabled.flag
endif
