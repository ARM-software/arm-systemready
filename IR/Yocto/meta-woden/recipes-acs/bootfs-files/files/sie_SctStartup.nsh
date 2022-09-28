# Copyright (c) 2022, ARM Limited and Contributors. All rights reserved.
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

for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F
  if exist FS%i:\EFI\BOOT\bbr\SCT then
    #
    # Found EFI SCT harness
    #
    FS%i:
    cd FS%i:\EFI\BOOT\bbr\SCT
    echo Press any key to stop the SIE SCT running
    stallforkey.efi 5
    if %lasterror% == 0 then
      goto Done
    endif
    for %j in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
        if exists FS%j:\acs_results\ then
            if exists FS%j:\acs_results\SIE\sct_results then

                #Check if SCT run has already completed
                if  exist FS%j:\acs_results\SIE\sct_results\Overall\Summary.log then
                    echo SIE SCT has completed run. Press any key to start SIE SCT execution from the begining. WARNING: Ensure you have backed up the existing logs.
                    stallforkey.efi 5
                    if %lasterror% == 0 then
                        #Backup the existing logs
                        rm -q FS%j:\acs_results\SIE\sct_results_previous_run
                        mkdir FS%j:\acs_results\SIE\sct_results_previous_run
                        cp -r FS%j:\acs_results\SIE\sct_results FS%j:\acs_results\sct_results_previous_run
                        rm -q FS%j:\acs_results\SIE\sct_results
                        goto StartSCT
                    else
                        goto Done
                    endif
                endif

                if exist FS%i:\EFI\BOOT\bbr\SCT\.passive.mode then
                    if exist FS%i:\EFI\BOOT\bbr\SCT\.verbose.mode then
                        Sct -c -p mnp -v
                    else
                        Sct -c -p mnp
                    endif
                    else
                    if exist FS%i:\EFI\BOOT\bbr\SCT\.verbose.mode then
                        Sct -c -v
                    else
                        Sct -c
                    endif

                    #SCT execution has finished. Copy the logs to acs_results
                    if  exist FS%j:\acs_results\sct_results\ then
                        if  exist FS%i:\EFI\BOOT\bbr\SCT\Overall then
                            cp -r FS%i:\EFI\BOOT\bbr\SCT\Overall FS%j:\acs_results\SIE\sct_results\
                        endif
                        if  exist FS%i:\EFI\BOOT\bbr\SCT\Sequence then
                            cp -r FS%i:\EFI\BOOT\bbr\SCT\Sequence\BBSR.seq FS%j:\acs_results\SIE\sct_results\
                        endif

                        #Restart to avoid an impact of running SCT tests on rest of the suites
                        echo Reset the system ...
                        reset
                    endif
                    #goto Done
                endif
            else
:StartSCT
            FS%j:
            cd FS%j:\acs_results
            mkdir SIE
            cd FS%j:\acs_results\SIE
            mkdir sct_results
            FS%i:
            cd FS%i:\EFI\BOOT\bbr\SCT
            Sct -s BBSR.seq
            goto Done
            endif
        endif
    endfor
  endif
endfor

:Done
