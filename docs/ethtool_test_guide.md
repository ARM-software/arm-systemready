# Ethernet Interface Diagnostics and Connectivity Validation Script

## Overview

This script automates testing and diagnostics of Ethernet interfaces on Linux-based systems. It evaluates the status, configuration, and connectivity of each interface using standard tools such as `ip`, `ethtool`, `ping`, `wget`, and `curl`.

When executed with a **SystemReady DT image**, the script runs automatically as part of the ACS (Architecture Compliance Suite) test framework with all dependencies. Output logs are generated at `linux_tools/ethtool-test.log` within the `acs_results` directory.

---

## Requirements

- Python 3.x
- Linux tools:
  - `ip`
  - `ifconfig`
  - `ethtool`
  - `ping`
  - `wget`
  - `curl`

### For standalone use on other systems:

1. Install the tools if missing:
```bash
sudo apt install net-tools iproute2 ethtool wget curl python3
```

2. Make the script executable (if needed):

```bash
chmod +x ethtool-test.py
```

3. Run the script as root:

```bash
sudo ./ethtool-test.py
```

Root privileges are required to manipulate interface state and run diagnostics.

---

## Execution Flow

The script performs diagnostics in a staged manner for each detected Ethernet interface, ensuring that tests only proceed when earlier conditions are met. The flow is designed to be conditional and isolated per interface.

1. **Interface detection**  
   The script uses `ip -o link` to list all network interfaces and selects only those marked as Ethernet (`ether` in the output). These are added to a test list.

2. **Pre-test setup**  
   All Ethernet interfaces are brought down using `ifconfig`. This is a preparatory step to ensure clean initialization before tests begin.

3. **Interface-by-Interface testing**  
   Interfaces are brought up and tested one at a time. The previous interface is brought down before the next is activated, maintaining test isolation.

4. **NIC information logging**  
   `ethtool <interface>` is executed to display NIC capabilities such as supported speeds, duplex modes, and link detection.

5. **Self-Test execution**  
   If the interface driver supports it (`supports-test: yes` from `ethtool -i`), the script runs `ethtool -t` to perform a self-test. Results are logged for review.

6. **Link status verification**  
   The script checks for `Link detected: yes` in the `ethtool` output. If no link is detected, the interface is skipped from further testing.

7. **DHCP address check**  
   Using `ip address show`, the script verifies that a dynamic (DHCP-assigned) IPv4 address is present. If not, it skips gateway and external connectivity checks.

8. **Gateway IP discovery and ping**  
   The script extracts the default gateway from `ip route` and attempts to ping it. If the gateway cannot be reached, external connectivity tests are skipped.

9. **External connectivity tests**  
   If the gateway ping is successful, the script pings `www.arm.com` to confirm DNS resolution and routing. `wget` and `curl` are used to verify HTTPS connectivity to `https://www.arm.com`.

10. **Iteration and completion**  
   After testing an interface, it is brought down, and the script proceeds to the next one. Once all interfaces are tested, the script exits.

---

## Test Execution Flow

Before processing each Ethernet interface through the flowchart, the script:

1. Detects all Ethernet interfaces using the `ip` command.
2. Bring down all interfaces to ensure a controlled and isolated testing environment.
   
Then, for each interface, it proceeds through the validation and connectivity checks shown below.

```mermaid
flowchart TD
    Start([Start]) --> C[Bring up the interface]
    C --> D[ethtool &lt;iface&gt; NIC info dump]
    D --> E{supports-test: yes?}
    E -->|yes| F[ethtool -t self-test]
    E -->|no| G[Link detection check]
    F --> G
    G --> H{Link detected?}
    H -->|yes| I[DHCP check]
    H -->|no| End([End])
    I --> J{DHCP configured?}
    J -->|yes| K[Gateway IP discovery]
    J -->|no| End
    K --> L{Gateway IP found?}
    L -->|yes| M[Ping to gateway]
    L -->|no| End
    M --> N{Ping successful?}
    N -->|yes| O[Ping to external website]
    N -->|yes| P[wget connectivity test]
    N -->|yes| Q[curl connectivity test]
    N -->|no| End
```

---

## Script Exit and Skip Conditions

The script may exit early or skip processing specific interfaces under certain conditions. Below are the key log messages indicating such exits or skips:

### Script exit conditions

The following messages indicate that the entire script will terminate:

- `INFO: No ethernet interfaces detected via ip linux command, Exiting ...`
- `INFO: Unable to bring down ethernet interface <iface> using ifconfig, Exiting ...`
- `Error occurred: <exception message>`

### Per-Interface skip (script continues with next interface)

These messages indicate that the current interface failed validation and is being skipped:

- `INFO: Unable to bring down ethernet interface <iface> using ifconfig`
- `INFO: Unable to bring up ethernet interface <iface> using ifconfig`
- `INFO: Link not detected for <iface>`
- `INFO: <iface> doesn't support DHCP`
- `INFO: Unable to find Router/Gateway IP for <iface>`
- `INFO: Failed to ping router/gateway[<gateway_ip>] for <iface>`

--------------
*Copyright (c) 2025, Arm Limited and Contributors. All rights reserved.*
