# Copyright (c) 2021,2023, ARM Limited and Contributors. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# Neither the name of ARM nor the names of its contributors may be used
# to endorse or promote products derived from this software without specific
# prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
echo -off
for %m in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%m:\acs_results then
        FS%m:
        cd FS%m:\acs_results
        if exist uefi_dump then
            echo "UEFI debug logs already run"
            echo "press any key to rerun UEFI debug logs"
            FS%m:\EFI\BOOT\bbr\SCT\stallforkey.efi 10
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
            dmpstore -all > dmpstore.log
            dh -d > dh.log
            memmap > memmap.log
            bcfg boot dump > bcfg.log
            devtree > devtree.log
            ver > uefi_version.log
            ifconfig -l > ifconfig.log
            dmem > dmem.log
            for %n in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
                    if exist FS%n:\EFI\BOOT\bsa\ir_bsa.flag then
                        #IR Specific ->DT
                    else
                        echo "" > map.log
                        map -r >> map.log
                        smbiosview > smbiosview.log
                        acpiview -l  > acpiview_l.log
                        acpiview -r 2 > acpiview_r.log
                        acpiview > acpiview.log
                        goto Done
                    endif
                    goto Done
            endfor
        endif
    endif
endfor
:Done
