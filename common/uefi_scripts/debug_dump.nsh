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
for %m in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%m:\acs_results then
        FS%m:
        cd FS%m:\acs_results
	goto DebugRun
    endif
endfor

:DebugRun
if exist uefi_dump then
    echo "UEFI debug logs already run"
    echo "Press any key to rerun UEFI debug logs"
    FS%m:\acs_tests\bbr\SCT\stallforkey.efi 10
    if %lasterror% == 0 then
        goto DEBUG_DUMP
    else
        goto Done
    endif
else
    mkdir uefi_dump
:DEBUG_DUMP
    cd uefi_dump
    echo "Starting UEFI Debug dump"
    connect -r
    pci > pci.log
    drivers > drivers.log
    devices > devices.log
    dh -d -v > dh.log
    dmpstore -all -s dmpstore.bin
    dmpstore -all > dmpstore.log
    memmap > memmap.log
    bcfg boot dump -v > bcfg.log
    devtree > devtree.log
    ver > uefi_version.log
    dmem > dmem.log
    sermode > sermode.log
    mode > mode.log
    timezone > timezone.log
    date > date.log
    time > time.log
    getmtc > getmtc.log
    ifconfig -l > ifconfig.log
    ifconfig -s eth0 dhcp
    ifconfig -s eth1 dhcp
    connect -r
    ifconfig -l > ifconfig_after_dhcp.log
    smbiosview > smbiosview.log
    for %n in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
        if not exist FS%n:\acs_tests\bsa\bsa_dt.flag then
            echo "" > map.log
            map -r >> map.log
            acpiview -l  > acpiview_l.log
            acpiview -r 2 > acpiview_r.log
            acpiview > acpiview.log
            acpiview -s DSDT -d
            acpiview -s SSDT -d
            goto Done
        endif
        goto Done
    endfor
endif
:Done
