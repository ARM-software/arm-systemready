#!/bin/bash
# Copyright (c) 2023, ARM Limited and Contributors. All rights reserved.
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


#############Please RUN THIS FILE WITH SUDO PERMISSION################################
#############USE THE COMMAND GIVEN BELOW##############################################
########## sudo ./ethtool-test.sh | tee ethtool_test.log #############################


apt-get install net-tools ethtool
# Run ip link command to list all network interfaces
ip_command="ip -o link"
output=$(eval $ip_command)

ether_interfaces=()

# Iterate through the reported interfaces
while read -r line; do
    parts=($line)
    if [ "${#parts[@]}" -lt 2 ]; then
        continue
    fi

    interface_name=$(echo ${parts[1]} | sed 's/://')

    if [[ $line == *"ether"* ]]; then
        ether_interfaces+=($interface_name)
    fi
done <<< "$output"

echo "****************************************************************"
echo "                         Running ethtool"
echo "****************************************************************"

# Print the ethernet interfaces if available
if [ ${#ether_interfaces[@]} -eq 0 ]; then
    echo "INFO: No ethernet interfaces detected via ip linux command, Exiting ..."
    exit 1
else
    echo "INFO: Detected following ethernet interfaces via ip command :"
    for ((index=0; index<${#ether_interfaces[@]}; index++)); do
        echo "${index}: ${ether_interfaces[$index]}"
    done
fi

# Bring down all ethernet devices
echo "INFO: Bringing down all ethernet interfaces using ifconfig"
for intrf in "${ether_interfaces[@]}"; do
    command="ifconfig $intrf down"
    echo "$command"
    result_down=$(eval $command)

    if [ $? -ne 0 ]; then
        echo "INFO: Unable to bring down ethernet interface $intrf using ifconfig, Exiting ..."
        exit 1
    fi
done

echo "****************************************************************"
previous_eth_intrf=""

for intrf in "${ether_interfaces[@]}"; do
    if [ -n "$previous_eth_intrf" ]; then
        # Bring down the previous ethernet interface
        echo "INFO: Bringing down ethernet interface: $previous_eth_intrf"
        command="ifconfig $previous_eth_intrf down"
        result_down=$(eval $command)
        sleep 20
        if [ $? -ne 0 ]; then
            echo "INFO: Unable to bring down ethernet interface $previous_eth_intrf using ifconfig"
            echo "INFO: Exiting the tool..."
        fi
    fi

    previous_eth_intrf=$intrf

    # Bring up the current ethernet interface
    echo "INFO: Bringing up ethernet interface: $intrf"
    command="ifconfig $intrf up"
    result_up=$(eval $command)
    sleep 20
    if [ $? -ne 0 ]; then
        echo "INFO: Unable to bring up ethernet interface $intrf using ifconfig"
        echo "****************************************************************"
        continue
    fi

    # Dump ethtool prints for each ethernet interface reported
    echo "INFO: Running \"ethtool $intrf\" :"
    command="ethtool $intrf"
    result_ethdump=$(eval $command)
    echo "$result_ethdump"

    # Run ethernet self-test if the drivers support it
    command="ethtool -i $intrf"
    result_test=$(eval $command)

    if [[ $result_test == *"supports-test: yes"* ]]; then
        echo "INFO: Ethernet interface $intrf supports ethtool self test."
        command="ethtool -t $intrf"
        echo "INFO: Running $command :"
        result_test=$(eval $command)
        echo "$result_test"
    else
        echo "INFO: Ethernet interface $intrf doesn't support ethtool self test"
    fi

    # Don't continue testing if link is not detected using ethtool
    if [[ $result_ethdump != *"Link detected: yes"* ]]; then
        echo "INFO: Link not detected for $intrf"
        echo "****************************************************************"
        continue
    else
        echo "INFO: Link detected on $intrf"
    fi

    # Check if DHCP is enabled for the interface, else skip testing
    command="ip address show dev $intrf"
    result_dhcp=$(eval $command)
    echo "INFO: Running $command :"
    echo "$result_dhcp"

    if [[ $result_dhcp != *"dynamic"* ]]; then
        echo "INFO: $intrf doesn't support DHCP"
        echo "****************************************************************"
        continue
    else
        echo "INFO: $intrf supports DHCP"
    fi

    # Find router/gateway IP and ping it
    command="ip route show dev $intrf"
    result_router=$(eval $command)
    echo "INFO: Running $command :"
    echo "$result_router"

    ip_pattern='[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'
    router_ip=$(echo "$result_router" | grep -oE "$ip_pattern")
    router_ip=$(echo $router_ip | awk '{print $1}')

    if [ -n "$router_ip" ]; then
        echo "INFO: Router/Gateway IP for $intrf : $router_ip"
    else
        echo "INFO: Unable to find Router/Gateway IP for $intrf"
        echo "****************************************************************"
        continue
    fi

    # Make sure link is up before ping test
    command="ifconfig $intrf up"
    echo "INFO: Running $command :"
    result_ping=$(eval $command)
    sleep 20

    command="ping -w 10000 -c 3 -I $intrf $router_ip"
    echo "INFO: Running $command :"
    result_ping=$(eval $command)
    echo "$result_ping"

    # Skip other tests if ping doesn't work
    if [ $? -ne 0 ] && [[ $result_ping == *"100% packet loss"* ]]; then
        echo "INFO: Failed to ping router/gateway[$router_ip] for $intrf"
        echo "****************************************************************"
        continue
    else
        echo "INFO: Ping to router/gateway[$router_ip] for $intrf is successful"
    fi

    # Ping www.arm.com to check whether DNS is working
    command="ping -w 10000 -c 3 -I $intrf www.arm.com"
    echo "INFO: Running $command :"
    result_ping=$(eval $command)
    echo "$result_ping"

    if [[ $result_ping == *"bad address"* ]]; then
        echo "INFO: Unable to resolve www.arm.com, DNS not configured correctly for $intrf"
    fi

    if [ $? -ne 0 ] && [[ $result_ping == *"100% packet loss"* ]]; then
        echo "INFO: Failed to ping www.arm.com via $intrf"
    else
        echo "INFO: Ping to www.arm.com is successful"
    fi

    echo "****************************************************************"
done

exit 0