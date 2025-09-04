# Windows Scripts

## device_driver_winpe.bat

### Overview
A batch script to capture **device driver** and **network configuration** information in **Windows Preinstallation Environment (WinPE)**, useful for system diagnostics.

### Commands used
```cmd
pnputil /enum-devices /connected
```
> Lists all currently connected devices with their associated driver details. Useful for confirming hardware recognition and driver loading inside WinPE.
---
```cmd
ipconfig /all
```
> Outputs detailed networking configuration, including IP address, gateway, DNS, MAC address, DHCP info, and more. Helpful for verifying network connectivity in pre-boot environments.
---

### Usage
To run and **save the output to a file**:
```cmd
device_driver_winpe.bat > output.log
```
> The log will be saved as `output.log` in the current directory.

**Note:** Use `type output.log | more` to view logs page by page in WinPE environment.

---------------------------------
*Copyright (c) 2025, Arm Limited and Contributors. All rights reserved.*
