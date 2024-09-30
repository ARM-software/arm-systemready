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
        #BSA_VERSION_PRINT_PLACEHOLDER
        if exist FS%i:\EFI\BOOT\bsa\Bsa.efi then
            echo "Press any key to start BSA in verbose mode."
            echo "If no key is pressed then BSA will be run in normal mode"
            FS%i:\EFI\BOOT\bbr\SCT\stallforkey.efi 10
            if %lasterror% == 0 then
                if exist FS%i:\acs_results\uefi\BsaVerboseResults.log then
                    echo "BSA ACS in verbose mode is already run."
                    echo "Press any key to start BSA ACS in verbose mode execution from the beginning."
                    echo "WARNING: Ensure you have backed up the existing logs."
                    FS%i:\EFI\BOOT\bbr\SCT\stallforkey.efi 10
                    if %lasterror% == 0 then
                        #Backup the existing logs
                        rm -q FS%i:\acs_results\uefi\BsaVerboseResults_previous_run.log
                        cp -r FS%i:\acs_results\uefi\BsaVerboseResults.log FS%i:\acs_results\uefi\BsaVerboseResults_previous_run.log
                        rm -q FS%i:\acs_results\uefi\BsaVerboseResults.log
                        goto BsaVerboseRun
                    endif
                    goto BsaNormalRun
                endif
:BsaVerboseRun
                echo "Running BSA in verbose mode"
                if exist FS%i:\EFI\BOOT\bsa\ir_bsa.flag then
                    #Executing for BSA IR. Execute only OS tests
                    FS%i:\EFI\BOOT\bsa\Bsa.efi -v 1 -os -skip 900 -dtb BsaDevTree.dtb -f BsaVerboseTempResults.log
                else
                   FS%i:\EFI\BOOT\bsa\Bsa.efi -v 1 -skip 900 -f BsaVerboseTempResults.log
                endif
                stall 200000
                if exist FS%i:\acs_results\uefi\BsaVerboseTempResults.log then
                    if exist FS%i:\EFI\BOOT\bsa\ir_bsa.flag then
                        echo " SystemReady IR ACS v2.1.1" > BsaVerboseResults.log
                    else
                        echo " SystemReady ES ACS v1.4.0" > BsaVerboseResults.log
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
            if exist FS%i:\acs_results\uefi\BsaResults.log then
                echo "BSA ACS is already run."
                echo "Press any key to start BSA ACS execution from the beginning."
                echo "WARNING: Ensure you have backed up the existing logs."
                FS%i:\EFI\BOOT\bbr\SCT\stallforkey.efi 10
                if %lasterror% == 0 then
                    #Backup the existing logs
                    rm -q FS%i:\acs_results\uefi\BsaResults_previous_run.log
                    cp -r FS%i:\acs_results\uefi\BsaResults.log FS%i:\acs_results\uefi\BsaResults_previous_run.log
                    rm -q FS%i:\acs_results\uefi\BsaResults.log
                    goto BsaRun
                endif
                goto Done
            endif
:BsaRun
            if exist FS%i:\EFI\BOOT\bsa\ir_bsa.flag then
               #Executing for BSA IR. Execute only OS tests
               FS%i:\EFI\BOOT\bsa\Bsa.efi -os -skip 900 -dtb BsaDevTree.dtb -f BsaTempResults.log
            else
               FS%i:\EFI\BOOT\bsa\Bsa.efi -skip 900 -f BsaTempResults.log
            endif
            stall 200000
            if exist FS%i:\acs_results\uefi\BsaTempResults.log then
                if exist FS%i:\EFI\BOOT\bsa\ir_bsa.flag then
                    echo " SystemReady IR ACS v2.1.1" > BsaResults.log
                else
                    echo " SystemReady ES ACS v1.4.0" > BsaResults.log
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
        goto Done
    endif
endfor
echo "acs_results not found"
:Done
