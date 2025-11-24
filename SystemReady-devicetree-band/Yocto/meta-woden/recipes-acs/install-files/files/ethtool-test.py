#!/usr/bin/env python3
# Copyright (c) 2023-2025, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
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

# This script parses for ethernet interfaces using ip tool and runs ethtool
# self-test if the interface supports. It also performs link detection,
# DHCP verification, IPv6 testing, and network connectivity checks via ping,
# wget, and curl.


import subprocess
import re
import time
import signal
import sys
import shutil
from pathlib import Path
from collections import OrderedDict
from fnmatch import fnmatch

# To print coloured output on the console
def print_color(text, level="INFO"):
    colors = {
        "INFO": "\033[92m",   # Green
        "DEBUG": "\033[94m",  # Blue
        "WARN": "\033[93m",   # Yellow
        "ERROR": "\033[91m",  # Red
        "CHECK": "\033[96m",  # Cyan
        "default": "\033[0m"
    }
    prefix = f"{level}: "
    print(colors.get(level, colors["default"]) + prefix + text + colors["default"])

# Tracking results
PASSED  = "PASSED"
FAILED  = "FAILED"
SKIPPED = "SKIPPED"
WARNING = "WARNING"

# Order and names of tests shown in the summary
TEST_ORDER = [
    "Detect interface",
    "Bring up",
    "ethtool present",
    "Self-test supported",
    "ethtool self tests",
    "Link detected",
    "IPv4 address present",
    "Gateway Address present",
    "Ping gateway (IPv4)",
    "Ping www.arm.com (IPv4)",
    "wget and curl",
    "IPv6 address present",
    "Ping ipv6.google.com (IPv6)"
]

# Parsing the summary 
results = {}

def init_iface_results(iface):
    od = OrderedDict()
    for t in TEST_ORDER:
        od[t] = {"status": SKIPPED, "detail": "Not run"}
    results[iface] = od

def set_result(iface, test_name, status, detail=""):
    if iface not in results:
        init_iface_results(iface)
    results[iface][test_name] = {"status": status, "detail": detail or ""}

def skip_many(iface, test_names, reason):
    for t in test_names:
        if results[iface][t]["status"] == SKIPPED or results[iface][t]["detail"] == "Not run":
            results[iface][t] = {"status": SKIPPED, "detail": reason}

def print_summary():
    print("\n================================================================")
    print("                         SUMMARY")
    print("================================================================")
    c = {"PASSED":"\033[92m", "FAILED":"\033[91m", "SKIPPED":"\033[93m", "WARNING":"\033[36m", "reset":"\033[0m"}

    # One-line detected interfaces summary
    detected_ifaces = [iface for iface in results if results[iface]["Detect interface"]["status"] == PASSED]
    if detected_ifaces:
        print(f"\nDetected Interfaces :  {c['PASSED']}PASSED{c['reset']} ({', '.join(detected_ifaces)})")

    printable_tests = [t for t in TEST_ORDER if t != "Detect interface"]
    max_name = max(len(t) for t in printable_tests)

    def st(oface, tname):
        return results.get(oface, {}).get(tname, {}).get("status", SKIPPED)

    def detail(oface, tname):
        return results.get(oface, {}).get(tname, {}).get("detail", "")
    yes_no_tests = {"ethtool present", "Self-test supported"}
    for iface in results:
        print(f"\nInterface {iface}")

        hidden = set()

        #Print limited info. for a interface based on previous pass/fails
        if st(iface, "Bring up") != PASSED:
            hidden.update([t for t in printable_tests if t != "Bring up"])

        else:
            if st(iface, "ethtool present") != PASSED:
                hidden.update(["Self-test supported", "ethtool self tests"])

            if st(iface, "Self-test supported") != PASSED:
                hidden.add("ethtool self tests")

            if st(iface, "Link detected") != PASSED:
                hidden.update([
                    "IPv4 address present",
                    "Gateway Address present",
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "IPv6 address present",
                    "Ping ipv6.google.com (IPv6)",
                    "wget and curl",
                ])

            if st(iface, "IPv4 address present") != PASSED:
                hidden.update([
                    "Gateway Address present",
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "wget and curl",
                ])

            if st(iface, "Gateway Address present") != PASSED:
                hidden.update([
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "wget and curl",
                ])

            if st(iface, "IPv6 address present") != PASSED:
                hidden.add("Ping ipv6.google.com (IPv6)")

        for t in printable_tests:
            if t in hidden:
                continue
            stv = st(iface, t)
            dv = detail(iface, t)
            if t in yes_no_tests:
                shown = "YES" if stv == "PASSED" else "NO"
                color = c.get(stv, "")
                reset = c["reset"]
                line = f"{t:{max_name}} :  {color}{shown}{reset}"
            else:
                color = c.get(stv, "")
                reset = c["reset"]
                line = f"{t:{max_name}} :  {color}{stv}{reset}"
            if dv:
                line += f"  ({dv})"
            print(line)
    
    def iface_has_failures(iface):
        return any(entry.get("status") == FAILED for entry in results.get(iface, {}).values())

    def is_virtual_bringup(iface):
        br = results.get(iface, {}).get("Bring up", {})
        return br.get("status") == SKIPPED and "Virtual interface" in br.get("detail", "")

    def link_detected_status(iface):
        return results.get(iface, {}).get("Link detected", {}).get("status", SKIPPED)

    # Compliance summary
    compliant_ifaces = []
    non_compliant_ifaces = []
    untestable_ifaces = []

    for iface in results:
        if is_virtual_bringup(iface):
            continue

        ld_status = link_detected_status(iface)

        if ld_status == WARNING:
            untestable_ifaces.append(iface)
            continue

        if ld_status != PASSED:
            non_compliant_ifaces.append(iface)
            continue

        if iface_has_failures(iface):
            non_compliant_ifaces.append(iface)
        else:
            compliant_ifaces.append(iface)

    green = "\033[92m"
    red   = "\033[91m"
    reset = "\033[0m"

    def join_names(names):
        return ", ".join(names) if names else "None"

    if non_compliant_ifaces:
        print(f"\nEthtool Compliance : {red}FAILED{reset} "
              f"(The interfaces {join_names(non_compliant_ifaces)} failed the tests)\n")
    else:
        if compliant_ifaces:
            print(f"\nEthtool Compliance : {green}PASSED{reset} "
                  f"(Passed interface(s) {join_names(compliant_ifaces)})\n")
        else:
            if untestable_ifaces:
                print(f"\nEthtool Compliance : {red}FAILED{reset} "
                      f"(Unable to test — Link detected was WARNING on {join_names(untestable_ifaces)})\n")
            else:
                print(f"\nEthtool Compliance : {red}FAILED{reset} (No testable interfaces)\n")

original_states = {}

#To check if a tool is from BusyBox 
def is_busybox_tool(tool_name):
    tool_path = shutil.which(tool_name)
    if not tool_path:
        return False
    try:
        r = subprocess.run(
            f"{tool_path} --help", shell=True,
            capture_output=True, text=True, timeout=2
        )
        return "BusyBox" in r.stdout or "BusyBox" in r.stderr
    except Exception:
        return False

def is_virtual_iface(iface):
    try:
        target_abs = str(Path(f"/sys/class/net/{iface}/device").resolve())
        if "/devices/virtual/" in target_abs:
            return True
    except Exception:
        pass

    virt_prefixes = (
        "docker", "veth", "virbr", "br", "tun", "tap",
        "wg", "tailscale", "zt", "cni", "flannel", "kube",
        "macvtap", "macvlan", "ipvlan", "bond"
    )
    if iface == "docker0":
        return True
    if any(iface.startswith(p) for p in virt_prefixes):
        return True

    virt_patterns = ("br-*", "cni-*", "flannel.*", "kube-*", "vnet*", "vif*")
    if any(fnmatch(iface, pat) for pat in virt_patterns):
        return True

    return False

# To renew DHCP when doesn’t exist.
def renew_dhcp(intrf, busybox_env):
    if has_default_route(intrf):
        return False
    print_color(f"Default route via {intrf} is missing; attempting DHCP restore", "INFO")
    try:
        if busybox_env and shutil.which("udhcpc"):
            subprocess.run(f"udhcpc -n -q -i {intrf}", shell=True, timeout=30)
        elif shutil.which("dhclient"):
            subprocess.run(f"dhclient -r {intrf}", shell=True, timeout=20)
            subprocess.run(f"dhclient -1 {intrf}", shell=True, timeout=35)
        else:
            print_color("No DHCP client found (udhcpc/dhclient). Skipping restore.", "WARN")
    except subprocess.TimeoutExpired:
        print_color(f"DHCP action on {intrf} timed out", "WARN")
    for _ in range(10):
        if has_default_route(intrf):
            print_color(f"Default route restored on {intrf}", "CHECK")
            break
        time.sleep(1)
    return True

# To check if the default route already exist.
def has_default_route(dev):
    r = subprocess.run("ip route show default", shell=True, capture_output=True, text=True)
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if f" dev {dev} " in f" {line} ":
                return True
    r2 = subprocess.run("ip -o route show table all default", shell=True, capture_output=True, text=True)
    if r2.returncode == 0:
        for line in r2.stdout.splitlines():
            if f" dev {dev} " in f" {line} ":
                return True
    return False

#Restoring the interfaces to their original states on exit
def cleanup():
    print_color("Cleaning up... restoring interface states", "INFO")
    for iface, state in original_states.items():
        subprocess.run(f"ip link set dev {iface} {state}", shell=True)
    print_color("Cleanup complete.", "INFO")

signal.signal(signal.SIGINT, lambda sig, frame: (print_summary(), cleanup(), sys.exit(0)))
signal.signal(signal.SIGTERM, lambda sig, frame: (print_summary(), cleanup(), sys.exit(0)))

if __name__ == "__main__":
    try:
        have_ethtool = shutil.which("ethtool") is not None
        busybox_env = shutil.which("udhcpc") is not None
        # Discovering ethernet interfaces
        output = subprocess.check_output("ip -o link", shell=True).decode("utf-8").split('\n')
        ether_interfaces = []
        for line in output:
            parts = line.split()
            if len(parts) < 2:
                continue
            interface_name = parts[1].rstrip(':')
            if "ether" in line:
                ether_interfaces.append(interface_name)
                init_iface_results(interface_name)

        print("\n****************************************************************\n")
        print("                      \033[92mRunning Networking Checks\033[0m\n")
        print("****************************************************************")

        if not ether_interfaces:
            print_color("No ethernet interfaces detected via ip linux command, Exiting ...", "WARN")
            sys.exit(1)
        else:
            print_color("Detected following ethernet interfaces via ip command :", "INFO")
            for index, intrf in enumerate(ether_interfaces):
                print(f"{index}: {intrf}")
                set_result(intrf, "Detect interface", PASSED)

        #Classify interfaces as virtual or physical
        virtual_ifaces  = [i for i in ether_interfaces if is_virtual_iface(i)]
        physical_ifaces = [i for i in ether_interfaces if i not in virtual_ifaces]
        for v in virtual_ifaces:
            set_result(v, "Bring up", SKIPPED, "Virtual interface — skipped all tests")

        # Recording initial states
        print_color("Capturing original interface states", "INFO")
        for intrf in ether_interfaces:
            result = subprocess.run(f"ip link show {intrf}", shell=True, capture_output=True, text=True)
            flags_match = re.search(r'<([^>]+)>', result.stdout)
            flags = flags_match.group(1).split(',') if flags_match else []
            state = "up" if "UP" in flags else "down"
            original_states[intrf] = state

        # Bringing down all the available interfaces
        print_color("Bringing down all ethernet interfaces using ip", "INFO")
        for intrf in physical_ifaces:
            cmd = f"ip link set dev {intrf} down"
            print(cmd)
            rc = subprocess.run(cmd, shell=True).returncode
            if rc != 0:
                print_color(f"Unable to bring down ethernet interface {intrf} using ip, Exiting ...", "WARN")

        print("\n****************************************************************\n")
        previous_eth_intrf = ""

        for intrf in physical_ifaces:
            if previous_eth_intrf:
                print_color(f"Bringing down ethernet interface: {previous_eth_intrf}", "INFO")
                subprocess.run(f"ip link set dev {previous_eth_intrf} down", shell=True)
                time.sleep(20)
            previous_eth_intrf = intrf

            # Bring up the current interface
            print_color(f"Bringing up ethernet interface: {intrf}", "INFO")
            result_up = subprocess.run(f"ip link set dev {intrf} up", shell=True)
            if result_up.returncode != 0:
                print_color(f"Unable to bring up ethernet interface {intrf} using ip", "WARN")
                set_result(intrf, "Bring up", FAILED, "ip link set up failed")
                # Skip everything else for this interface if unable to Bring up
                remaining = [t for t in TEST_ORDER if t not in ("Detect interface", "Bring up")]
                skip_many(intrf, remaining, "Interface could not be brought up")
                print("\n****************************************************************\n")
                continue
            else:
                set_result(intrf, "Bring up", PASSED)
            time.sleep(20)

            # Check for ethtool availability
            if have_ethtool:
                set_result(intrf, "ethtool present", PASSED)
                print_color(f"Running \"ethtool {intrf}\"", "INFO")
                result_ethdump = subprocess.run(f"ethtool {intrf}", shell=True, capture_output=True, text=True)
                print(result_ethdump.stdout)

                result_test = subprocess.run(f"ethtool -i {intrf}", shell=True, capture_output=True, text=True)
                print(result_test.stdout)
                if "supports-test: yes" in result_test.stdout:
                    print_color(f"Ethernet interface {intrf} supports ethtool self test.", "CHECK")
                    set_result(intrf, "Self-test supported", PASSED)
                    print_color(f"Running ethtool -t {intrf}", "INFO")
                    try:
                        t = subprocess.run(f"ethtool -t {intrf}",shell=True, capture_output=True, text=True, timeout=60)
                        print_color(t.stdout, "DEBUG")
                        if t.returncode == 0:
                            set_result(intrf, "ethtool self tests", PASSED)
                        else:
                            first_line = next((ln for ln in (t.stdout + "\n" + t.stderr).splitlines() if ln.strip()), "")
                            set_result(intrf, "ethtool self tests", WARNING, first_line or f"returncode={t.returncode}")
                    except subprocess.TimeoutExpired:
                        print_color("ethtool -t timed out (60s)", "WARN")
                        set_result(intrf, "ethtool self tests", WARNING, "timeout")

                    subprocess.run(["ip", "link", "set", "dev", intrf, "up"])
                    for _ in range(10):
                        try:
                            carrier = Path(f"/sys/class/net/{intrf}/carrier").read_text().strip()
                        except Exception:
                            carrier = "0"
                        if carrier == "1":
                            print_color(f"Link restored on {intrf}", "CHECK")
                            break
                        time.sleep(1)

                else:
                    print_color(f"Ethernet interface {intrf} does not support ethtool self test", "WARN")
                    set_result(intrf, "Self-test supported", SKIPPED, "supports-test: no")
                    set_result(intrf, "ethtool self tests", SKIPPED, "Self-test not supported")

                if "Link detected: yes" in result_ethdump.stdout:
                    print_color(f"Link detected on {intrf}", "CHECK")
                    set_result(intrf, "Link detected", PASSED)
                else:
                    print_color(f"Link not detected for {intrf}", "WARN")
                    set_result(intrf, "Link detected", WARNING, "No carrier")
                    # Skip everything else that needs a link
                    skip_many(intrf, [
                        "Gateway Address present",
                        "Ping gateway (IPv4)",
                        "Ping www.arm.com (IPv4)",
                        "IPv6 address present",
                        "Ping ipv6.google.com (IPv6)",
                        "wget and curl",
                    ], "Link not detected")
                    print("\n****************************************************************\n")
                    continue
            else:
                set_result(intrf, "ethtool present", FAILED, "ethtool not found; using sysfs")
                set_result(intrf, "Self-test supported", SKIPPED, "No ethtool")
                set_result(intrf, "ethtool self tests", SKIPPED, "No ethtool")
                print_color("ethtool not found; using sysfs for link detection", "WARN")
                try:
                    carrier = Path(f"/sys/class/net/{intrf}/carrier").read_text().strip()
                except Exception:
                    carrier = "0"
                if carrier != "1":
                    try:
                        oper = Path(f"/sys/class/net/{intrf}/operstate").read_text().strip()
                    except Exception:
                        oper = "down"
                    if oper != "up":
                        print_color(f"Link not detected for {intrf} (carrier={carrier}, operstate={oper})", "WARN")
                        set_result(intrf, "Link detected", WARNING, f"carrier={carrier}, operstate={oper}")
                        skip_many(intrf, [
                            "Gateway Address present",
                            "Ping gateway (IPv4)",
                            "Ping www.arm.com (IPv4)",
                            "IPv6 address present",
                            "Ping ipv6.google.com (IPv6)",
                            "wget and curl",
                        ], "Link not detected")
                        print("\n****************************************************************\n")
                        continue
                print_color(f"Link detected on {intrf} (sysfs)", "CHECK")
                set_result(intrf, "Link detected", PASSED)

            # Check IPv4 and IPv6 address configuration
            command = f"ip address show dev {intrf}"
            print_color(f"Running {command}", "INFO")
            result_addr = subprocess.run(command, shell=True, capture_output=True, text=True)
            print(result_addr.stdout)

            has_dhcp = "dynamic" in result_addr.stdout
            has_ipv6 = re.search(r'inet6 (?!fe80)', result_addr.stdout)

            # Detect any IPv4 (dynamic or static)
            ipv4_matches = re.findall(r'inet (\d+\.\d+\.\d+\.\d+)/\d+', result_addr.stdout)
            ipv4_list = [ip for ip in ipv4_matches if not ip.startswith("127.")]
            has_ipv4 = len(ipv4_list) > 0

            # Default route to evaluate whenever we have any IPv4
            if not has_default_route(intrf):
                renew_dhcp(intrf, busybox_env)
                command = f"ip address show dev {intrf}"
                result_addr = subprocess.run(command, shell=True, capture_output=True, text=True)
                print(result_addr.stdout)
                has_dhcp = "dynamic" in result_addr.stdout
                has_ipv6 = re.search(r'inet6 (?!fe80)', result_addr.stdout)
                ipv4_matches = re.findall(r'inet (\d+\.\d+\.\d+\.\d+)/\d+', result_addr.stdout)
                ipv4_list = [ip for ip in ipv4_matches if not ip.startswith("127.")]
                has_ipv4 = len(ipv4_list) > 0

            if has_ipv4 and has_default_route(intrf):
                set_result(intrf, "Gateway Address present", PASSED)
            elif has_ipv4:
                reason = "No default route" + (" after DHCP" if has_dhcp else " (static config)")
                set_result(intrf, "Gateway Address present", FAILED, reason)
            else:
                set_result(intrf, "Gateway Address present", SKIPPED, "No IPv4 address")

            # DHCP result
            #if has_dhcp:
            #    set_result(intrf, "IPv4 DHCP", PASSED)
            #else:
            #    print_color(f"{intrf} does not have a dynamic IPv4 address", "WARN")
            #    set_result(intrf, "IPv4 DHCP", FAILED, "No dynamic IPv4 assigned")

            # IPv4 address present (independent from DHCP)
            if has_ipv4:
                ip_type = "dynamic" if has_dhcp else "static"
                set_result(intrf, "IPv4 address present", PASSED, f"{ip_type} {', '.join(ipv4_list)}")
            else:
                set_result(intrf, "IPv4 address present", FAILED, "No IPv4 address")



            # Run ping6 if global IPv6 address is found
            if has_ipv6:
                set_result(intrf, "IPv6 address present", PASSED)
                ipv6_addresses = re.findall(r'inet6 ([\da-f:]+)/\d+ scope global', result_addr.stdout)
                for ip6 in ipv6_addresses:
                    print_color(f"Found global IPv6 address on {intrf} → {ip6}", "CHECK")
                ping6_bin = shutil.which("ping") or shutil.which("ping6")
                if "ping6" in (ping6_bin or ""):
                    ping6_command = f"ping6 -c 3 -I {intrf} ipv6.google.com"
                else:
                    ping6_command = f"ping -6 -c 3 -I {intrf} ipv6.google.com"
                print_color(f"Running {ping6_command}", "INFO")
                result_ping6 = subprocess.run(ping6_command, shell=True, capture_output=True, text=True)
                print(result_ping6.stdout)
                if result_ping6.returncode != 0 or "100% packet loss" in result_ping6.stdout:
                    print_color(f"Failed to ping ipv6.google.com via {intrf}", "WARN")
                    set_result(intrf, "Ping ipv6.google.com (IPv6)", WARNING, "Packet loss or ping failed")
                else:
                    print_color(f"Ping to ipv6.google.com via {intrf} is successful", "CHECK")
                    set_result(intrf, "Ping ipv6.google.com (IPv6)", PASSED)
            else:
                print_color(f"No IPv6 address found on {intrf}, skipping IPv6 test", "INFO")
                set_result(intrf, "IPv6 address present", SKIPPED, "No global IPv6")
                set_result(intrf, "Ping ipv6.google.com (IPv6)", SKIPPED, "No global IPv6")

            # If no IPv4 DHCP, skip IPv4-dependent tests
            if results[intrf]["IPv4 address present"]["status"] != PASSED or \
               results[intrf]["Gateway Address present"]["status"] != PASSED:
                skip_many(intrf, [
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "wget and curl",
                ], "No IPv4 and/or default route")
                print("\n****************************************************************\n")
                continue

            # Determine default router/gateway and verify the route path
            print_color("Running ip route get 8.8.8.8", "INFO")
            r = subprocess.run("ip route get 8.8.8.8", shell=True, capture_output=True, text=True)
            print(r.stdout)
            if r.returncode != 0:
                print_color(f"No default route available for {intrf} (route get failed), skipping further tests for this interface", "WARN")
                skip_many(intrf, [
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "wget and curl",
                ], "ip route get failed")
                print("\n****************************************************************\n")
                continue

            m = re.search(r'\bvia\s+(\d{1,3}(?:\.\d{1,3}){3}).*?\bdev\s+(\S+)', r.stdout)
            if not m:
                print_color(f"Unable to parse gateway/dev from route output, skipping further tests for {intrf}", "WARN")
                skip_many(intrf, [
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "wget and curl",
                ], "Cannot parse gateway")
                print("\n****************************************************************\n")
                continue

            gw, dev_on_path = m.group(1), m.group(2)
            if dev_on_path != intrf:
                print_color(f"Default route to 8.8.8.8 is via {dev_on_path}, not {intrf}; skipping further tests for {intrf}", "WARN")
                skip_many(intrf, [
                    "Ping gateway (IPv4)",
                    "Ping www.arm.com (IPv4)",
                    "wget and curl",
                ], f"Route uses {dev_on_path}")
                print("\n****************************************************************\n")
                continue

            ip_address = gw
            print_color(f"Router/Gateway IP for {intrf} : {ip_address}", "CHECK")

            set_result(intrf, "Gateway Address present", PASSED, f"gateway {gw}")

            subprocess.run(f"ip link set dev {intrf} up", shell=True)
            time.sleep(20)

            # Run IPv4 ping test to the router/gateway
            cmd = f"ping -c 3 -W 10 -I {intrf} {ip_address}"
            print_color(f"Running {cmd}", "INFO")
            rping = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            print(rping.stdout)
            if rping.returncode != 0 or "100% packet loss" in rping.stdout:
                print_color(f"Failed to ping router/gateway[{ip_address}] for {intrf}", "WARN")
                set_result(intrf, "Ping gateway (IPv4)", WARNING, "Packet loss or ping failed")
            else:
                print_color(f"Ping to router/gateway[{ip_address}] for {intrf} is successful", "CHECK")
                set_result(intrf, "Ping gateway (IPv4)", PASSED)

            # Ping www.arm.com to verify DNS resolution and external connectivity
            cmd = f"ping -c 3 -W 10 -I {intrf} www.arm.com"
            print_color(f"Running {cmd}", "INFO")
            rp2 = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            print(rp2.stdout)
            if "bad address" in rp2.stderr:
                print_color(f"Unable to resolve www.arm.com, DNS not configured correctly for {intrf}", "WARN")
            if rp2.returncode != 0 or "100% packet loss" in rp2.stdout:
                print_color(f"Failed to ping www.arm.com via {intrf}", "WARN")
                set_result(intrf, "Ping www.arm.com (IPv4)", WARNING, "Ping failed or DNS issue")
            else:
                print_color(f"Ping to www.arm.com is successful", "CHECK")
                set_result(intrf, "Ping www.arm.com (IPv4)", PASSED)

            # wget and curl connectivity check
            wget_available = shutil.which("wget") is not None
            curl_available = shutil.which("curl") is not None

            parts = []
            wget_ok = False
            curl_ok = False

            # wget check
            if wget_available:
                wget_command = f"wget --spider --timeout=10 https://www.arm.com"
                print_color(f"Running {wget_command}", "INFO")
                rwget = subprocess.run(wget_command, shell=True, capture_output=True, text=True)
                if rwget.stdout.strip():
                    print_color(rwget.stdout.strip(), "DEBUG")
                if rwget.stderr.strip():
                    print_color(rwget.stderr.strip(), "DEBUG")
                if rwget.returncode == 0:
                    wget_ok = True
                    parts.append("wget ok")
                    print_color("wget successfully accessed https://www.arm.com", "CHECK")
                else:
                    parts.append("wget failed")
                    print_color("wget failed to reach https://www.arm.com", "WARN")
            else:
                parts.append("wget not found")
                print_color("Skipping wget check: 'wget' not found.", "WARN")

            # curl check
            if curl_available:
                curl_command = f"curl -Is --connect-timeout 20 --interface {intrf} https://www.arm.com"
                print_color(f"Running {curl_command}", "INFO")
                rcurl = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
                lines = rcurl.stdout.strip().splitlines() if rcurl.stdout else []
                first_line = lines[0] if lines else ""
                if rcurl.stderr.strip():
                    print_color(f"Curl Error: {rcurl.stderr.strip()}", "DEBUG")
                if "HTTP/2 200" in first_line or "HTTP/1.1 200 OK" in first_line:
                    curl_ok = True
                    parts.append("curl ok")
                    print_color("curl successfully fetched https://www.arm.com", "CHECK")
                else:
                    parts.append("curl failed")
                    print_color("curl failed to fetch https://www.arm.com", "WARN")
            else:
                parts.append("curl not found")
                print_color("Skipping curl check: 'curl' not found.", "WARN")

            # wget and curl status
            if wget_ok and curl_ok:
                combined_status = PASSED
            elif wget_ok or curl_ok:
                combined_status = WARNING
            else:
                combined_status = FAILED

            set_result(intrf, "wget and curl", combined_status, ", ".join(parts))

            print("\n****************************************************************\n")

        # Restore all original interface states and print summary
        print_summary()
        cleanup()
        sys.exit(0)

    except Exception as e:
        print_color(f"Error occurred: {e}", "ERROR")
        print_summary()
        cleanup()
        sys.exit(1)
