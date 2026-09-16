# Windows Scripts

## device_driver_winpe.bat

### Overview
A batch script to capture **device driver** and **network configuration** information in **Windows Preinstallation Environment (WinPE)**, useful for system diagnostics.

---
### Setup
Boot the system into the **Windows Preinstallation Environment (WinPE)**.

Download the `device_driver_winpe.bat` script from the `common/windows_scripts/` directory of the `arm-systemready` repository and save it to a writable disk or partition accessible from WinPE.

To identify the available disks and volumes in WinPE:
```cmd
diskpart
list volume
exit
```
Switch to the drive where the script was downloaded. For example:
```cmd
D:
cd <path-to-script>
```
---
### Commands used in the script
```cmd
pnputil /enum-devices /connected
```
> Lists all currently connected devices with their associated driver details. Useful for confirming hardware recognition and driver loading inside WinPE.

```cmd
ipconfig /all
```
> Outputs detailed networking configuration — including IP address, gateway, DNS, MAC address, DHCP info, and more. Helpful for verifying network connectivity in pre-boot environments.

---
### Usage
To run and save the output to a file:
```cmd
device_driver_winpe.bat > device_driver_winpe.log
```
> The log will be saved as `device_driver_winpe.log` in the current directory.

**Note:** Use `type device_driver_winpe.log | more` to view logs page by page in the WinPE environment.

---
### Saving Logs to ACS Results
Identify the drive containing the ACS results and copy the generated log to the corresponding WinPE OS logs directory in the ACS results:

```cmd
copy device_driver_winpe.log D:\acs_results_template\os-logs\winpe\
```
The resulting log should be available at:
```text
acs_results_template/os-logs/winpe/device_driver_winpe.log
```
Alternatively, the generated `device_driver_winpe.log` can be downloaded or copied from the WinPE environment to the local system and then manually copied to `acs_results_template/os-logs/winpe/`

---------------------------------
*Copyright (c) 2025-2026, Arm Limited and Contributors. All rights reserved.*
