# Copyright (c) 2022-2023, ARM Limited and Contributors. All rights reserved.
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

#UpdateVars.efi is present only in the IR ACS image
#The below block for UpdateVars shall be executed only for IR
for %q in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%q:\EFI\BOOT\app\UpdateVars.efi then
        FS%q:
        cp -q FS%q:\security-interface-extension-keys\*.auth FS%q:\EFI\BOOT\app\
        cd FS%q:\EFI\BOOT\app
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
    if exist FS%i:\EFI\BOOT\bbr\sie_SctStartup.nsh then
        FS%i:\EFI\BOOT\bbr\sie_SctStartup.nsh
        for %k in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
            if  exist FS%k:\acs_results\SIE\sct_results\ then
                if  exist FS%i:\EFI\BOOT\bbr\SCT\Overall then
                    cp -r FS%i:\EFI\BOOT\bbr\SCT\Overall FS%k:\acs_results\SIE\sct_results\
                endif
                if  exist FS%i:\EFI\BOOT\bbr\SCT\Dependency\EfiCompliantBBTest then
                    cp -r FS%i:\EFI\BOOT\bbr\SCT\Dependency\EfiCompliantBBTest FS%k:\acs_results\SIE\sct_results\
                endif
                if  exist FS%i:\EFI\BOOT\bbr\SCT\Sequence then
                    cp -r FS%i:\EFI\BOOT\bbr\SCT\Sequence FS%k:\acs_results\SIE\sct_results\
                endif
            endif
        endfor
     echo "SIE SCT test suite execution is complete. Resetting the system"
     reset
     endif
endfor

