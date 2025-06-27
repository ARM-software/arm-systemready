#!/bin/sh

# @file
# Copyright (c) 2024-2025, Arm Limited or its affiliates. All rights reserved.
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

echo "Ping log is empty or not in a recognizable format, please check logs offline."
set returncode 1

:End
exit /b %returncode%
