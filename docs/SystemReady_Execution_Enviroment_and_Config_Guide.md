# SystemReady Band Execution Enviroment and Configuration User Guide

## Overview

This guide provides details on the SR band Execution Enviroment and configuration-based feature integrated into the SystemReady-band image.

Execution Enviroment is used to run manually only a desired selected test suites, and with a configuration file the test suite run can be customized with required parameter.
The configuration file can also be used to selectively enable/disable individual test suites in automation run. This allows for flexible and targeted testing.

---

## Configuration File

The configuration file is an INI-style file located at a predefined path in the image, typically:

- **Linux**: `/mnt/acs_tests/config/acs_run_config.ini`
- **UEFI**: `fsx:\acs_tests\config\acs_run_config.ini`

### Sample Configuration File

```ini
[AUTOMATION]
config_enabled_for_automation_run = false

[SCT]
automation_sct_run = true
sct_sequence_file = SBBR.seq

[SCRT]
automation_scrt_run = true

[BSA]
automation_bsa_run = true
bsa_modules = 
bsa_tests = 
bsa_skip = 1500
bsa_verbose = 3

[SBSA]
automation_sbsa_run = false
sbsa_modules = 
sbsa_level = 4
sbsa_tests = 
sbsa_skip = 1500
sbsa_verbose = 3

[FWTS]
automation_fwts_run = true
fwts_modules = --uefi-set-var-multiple=1 --uefi-get-mn-count-multiple=1 --sbbr esrt uefibootpath aest cedt slit srat hmat pcct pdtt bgrt bert einj erst hest sdei nfit iort mpam ibft ras2

[BBSR_SCT]
automation_bbsr_sct_run = true
bbsr_sct_sequence_file = BBSR.seq

[BBSR_FWTS]
automation_bbsr_fwts_run = true

[BBSR_TPM]
automation_bbsr_tpm_run = true
```
---

### Behavior Details for Config-Based Automation

This section explains how the automation run behaves based on the `config_enabled_for_automation_run` flag in the configuration file.

---

### Configuration variable: `config_enabled_for_automation_run`

This flag controls whether the automation run should follow the instructions in the configuration file or use the default behavior.

```ini
[AUTOMATION]
config_enabled_for_automation_run = true
or
config_enabled_for_automation_run = false
```

### Behavior Matrix

| config_enabled_for_automation_run |         Behavior        |
|----------------------------------|----------|
| `true` | - ✅ Configuration file is **read and parsed**. <br> - ✅ **Only test suites explicitly enabled** in the config will be run. <br> - ✅ Command-line parameters (like sequence files, modules, skip lists) are constructed from config values. <br> - ❌ Test suites with `false` skipped. |
| `false` | - ⚠️ Configuration file is **ignored**. <br> - ✅ All test suites run using the **default full-flow** logic. <br> - ✅ Suitable for exhaustive platform testing. <br> - ❌ No selective filtering based on config. |


### Flow Diagram (Conceptual)

```text
+-------------------------------------+
|         START AUTOMATION           |
+-------------------------------------+
              |
              v
+-------------------------------+
| Read config file (if exists) |
+-------------------------------+
              |
              v
+-----------------------------------------------+
| Is config_enabled_for_automation_run = true ? |
+----------------------+------------------------+
       YES              |           NO
        |               |           |
        v               |           v
+--------------------------+   +----------------------------+
| Parse individual test    |   | Ignore config file         |
| suite flags and options  |   | Run all test suites        |
+--------------------------+   +----------------------------+
        |                                   |
        v                                   v
+------------------------------+   +------------------------------+
|  run enabled tests and       |   |Execute default test commands |
|  generated commands          |   |                              |
+------------------------------+   +-------------------------------+
```


---

## SR Execution Enviroment

The grub menu is updated to provide two more options for execution enviroment.
On boot, users are presented with the following GRUB menu:

```
Linux Boot
SystemReady band ACS (Automation)
BBSR Compliance (Automation)
UEFI Execution Enviroment
Linux Execution Enviroment
Set Virtual Address Map
```
---

- Linux Boot - Boots into the default Linux environment.
- SystemReady band ACS (Automation) - Initiates the automation flow.
- BBSR Compliance (Automation) -  - Launches the BBSR-specific testing environment.
- UEFI Execution Enviroment - Allows manual execution of UEFI-based test suites using the config file.
- Linux Execution Enviroment - Allows manual execution of Linux-based test suites using the config file. 
- Set Virtual Address Map - Technical option for configuring memory map behavior in UEFI.

## SystemReady band ACS (Automation) Flow

When selecting **SystemReady band ACS (Automation)**, the following behavior occurs:

1. A **timer** is initiated. **if no key pressed**  The system **ignores the config file** and runs **all test suites** in the legacy manner.
2. During this timer period, if the user **presses any key**, the system will:
   - Launch the `Parser.efi` application.
   - Allow the user to **view, edit, and update** the configuration file.
3. On exiting `Parser.efi`:
   - The system checks the flag `config_enabled_for_automation_run`.
   - If `true`: The automation runs only **enabled test suites** based on config parameters (commands are generated from config).
   - If `false`: The system **ignores the config file** and runs **all test suites** in the legacy manner.

---

## Behavior of Linux Execution Enviroment and UEFI Execution Enviroment

- **UEFI Execution Enviroment**
  - Enters UEFI Shell with similar behavior to Linux Execution Enviroment.
  - Users can run UEFI test suites (like SCT, SCRT) manually.
  - Help/guidance is displayed in the shell to inform how to execute commands using config.

- **Linux Execution Enviroment**
  - Boots into Linux shell where users can manually execute test suites.
  - The system reads the config file and allows manual control over which test suites to run based on the enabled sections and their parameters.
  - A help or run-guide is displayed to assist users in running the appropriate commands.

---

## Manual Execution Instructions (Linux Execution Enviroment / UEFI Execution Enviroment)

- Users can manually view/edit the config file using:
  - `acs_tets/parser/Parser.efi` (UEFI shell)
  - `vi acs_tests/config/acs_run_config.ini` or any text editor in Linux
- Once configured:
  - **Run test suites manually** using the generated command structure as per config parameters.

---
