# UEFI Network Ping Test Utility

These scripts provide an automated mechanism for validating network connectivity in a UEFI shell environment. It includes:

- A discovery and execution script (`startup_dt.nsh`) that locates and runs the test.
- A log parser (`pingtest.nsh`) that analyzes the ping result and determines success/failure.

---

## System Requirements

- UEFI Shell environment (e.g., EDK2, U-Boot UEFI).
- Enabled NIC with DHCP or static IP configuration.
- Shell support for `ping`, `ifconfig`, `echo`, etc.

---

## Directory Structure

```
Script files path - FSx:\
 ├── acs_tests\
 │    └── debug\
 │         └── pingtest.nsh
 └── EFI\
     └── BOOT\
         └── startup_dt.nsh

Logs are stored at the following path:
  ├── acs_results_template\
      └── acs_results\
           └── network_logs\
             └── ping.log
             └── pintest.log
```

---

## Execution Flow

### 1. `startup_dt.nsh`

This script:

- Scans filesystems `FS0:` through `FSF:`.
- Looks for `pingtest.nsh` in `\acs_tests\debug\`.
- Switches to the results directory and ensures `network_logs` exists.
- Executes `ping 8.8.8.8` and saves output to `ping.log`.
- Parses `ping.log` by calling `pingtest.nsh` to determine pass/fail.

---

### 2. `pingtest.nsh`

A parser script that:

- Reads `ping.log` word by word.
- Detects whether any interface was configured.
- Validates ping summary (transmitted, received, % loss).
- Returns:
  - `0` if successful (e.g., packets received, <100% loss).
  - `1` if ping failed, malformed log, or network not configured.

---

## Expected Ping Log Format

```
Ping 8.8.8.8 16 data bytes.
16 bytes from 8.8.8.8 : icmp_seq=1 ttl=0 time0~9ms
...
10 packets transmitted, 10 received, 0% packet loss, time 9ms
Rtt min=0~9ms max=9~18ms avg=0~9ms
```
---

## Troubleshooting

| Issue                      | Possible Cause                     | Fix/Check                          |
|---------------------------|------------------------------------|------------------------------------|
| Log format error           | No output from `ping`, or no interfaces detected  | Check NIC/DHCP/network readiness, ensure system has at least one active and configured network interface |
| 100% packet loss           | Unreachable IP or no route         | Ensure network access              |
| Interface not configured   | DHCP failed                        | Verify `ifconfig -r` before ping   |

#### Note

- `echo "" > ping.log` command clears any existing data in `ping.log` by writing a **blank line**. If the `ping` command **fails to produce output**, the file remains effectively empty, containing `<null string>`. In such cases, `pingtest.nsh` will fail the test, printing: `Ping log is empty or not in a recognizable format. Please check the logs offline.`
- `ifconfig -r` reinitializes network interface setup, since initialization time can vary, consider increasing the stall delay if interfaces remain unconfigured
---
## Possible Outcomes of `pingtest.nsh`

| Log Message                                                  | Meaning                                                                 |
|------------------------------------------------------------------|-------------------------------------------------------------------------|
| `Ping successful. Received <N> packets.`                          | Ping test passed. N responses were received.                            |
| `Ping failed. 100% packet loss.`                                  | Ping command ran, but no replies were received.                         |
| `Unable to configure network using DHCP.`                         | No network interface was successfully configured.                       |
| `Log is not in a standard format, please check ping logs offline.` | The ping log format did not match the expected structure.              |
| `Ping log is empty or not in a recognizable format, please check logs offline.` | Log was empty or didn't contain recognizable ping output. |
---
### Note:  
- It is possible for network interfaces to be visible and functional in a Linux OS environment, but **absent in the UEFI shell**. This typically indicates that the necessary UEFI network drivers (e.g., UNDI or SNP drivers) are not available or not loaded in the UEFI environment.  
- Ensure the platform firmware includes support for the NIC hardware in the pre-boot (UEFI) phase for network diagnostics to succeed.
--------------
*Copyright (c) 2025, Arm Limited and Contributors. All rights reserved.*
