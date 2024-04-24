# Copyright (c) 2024, ARM Limited and Contributors. All rights reserved.
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

# Usage pingtest.nsh <ping output log>
# This script checks whether ping test was successful or not.
# This script expects the ping log to be in following format,
#
# Shell> ping 8.8.8.8
# Ping 8.8.8.8 16 data bytes.
# 16 bytes from 8.8.8.8 : icmp_seq=1 ttl=0 time9~18ms
# 16 bytes from 8.8.8.8 : icmp_seq=2 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=3 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=4 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=5 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=6 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=7 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=8 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=9 ttl=0 time0~9ms
# 16 bytes from 8.8.8.8 : icmp_seq=10 ttl=0 time0~9ms
#
# 10 packets transmitted, 10 received, 0% packet loss, time 9ms
#
# Rtt(round trip time) min=0~9ms max=9~18ms avg=0~9ms

echo -off

# set a variable with words separated by space in inputted log
type %1 >v x

# set variables
set state start
set returncode 1
set num_of_packets_recv 0


for %i in %x%
    #check if no configured interfaces were found.
    if %state% == start then
        if %i == No then
            set state noconfigure
        endif
    endif

    if %state% == noconfigure then
        if %i == configured then
            # fail the test "no configured interfaces were found"
            set returncode 1
            echo "Unable to configure network using DHCP."
            goto End
        endif
    else
    if %state% == start then
        if %i == transmitted, then
            set state num_packet
        endif
    else
    if %state% == num_packet then
        set state check_recv
        set num_of_packets_recv %i
    else
    if %state% == check_recv then
        if %i == received, then
            set state pkts_loss
        else
            echo  "Log is not in a standard format, please check ping logs offline."
            set returncode 1
            goto End
        endif
    else
    if %state% == pkts_loss then
        if %i == 100% then
            echo "Ping failed. 100% packet loss."
            set returncode 1
            goto End
        else
            echo "Ping successful. Received %num_of_packets_recv% packets."
            set returncode 0
            goto End
        endif
    endif
    endif
    endif
    endif
    endif
endfor

echo "Ping log is empty or not in standard format, please check logs offline."
set returncode 1

:End
exit /b %returncode%