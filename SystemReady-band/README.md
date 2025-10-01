# SystemReady band ACS

## Table of Contents

- [Introduction](#introduction)
- [Latest Release details](#latest-release-details)
- [Prebuilt Images](#prebuilt-images)
- [Steps to Manually Build Image](#steps-to-manually-build-image)
- [Image Directory Structure](#image-directory-structure)
- [Details and Functionalities of the Image](#details-and-functionalities-of-the-image)
  - [Grub Menu & Compliance Run](#grub-menu--compliance-run)
  - [ACS configs file](#acs-configs-file)
  - [Log Parser scripts](#log-parser-scripts)
    - [Standard Formatted Result](#standard-formatted-result)
    - [Waiver application process](#waiver-application-process)
- [Verification on Arm Neoverse N2 reference design](#verification-on-arm-neoverse-n2-reference-design)
  - [Software stack and Model](#software-stack-and-model)
  - [Model run command](#model-run-command)
- [Security Implication](#security-implication)
- [License](#license)
- [Feedback, contributions, and support](#feedback-contributions-and-support)

## Introduction
SystemReady band is a band of system compliance in the Arm SystemReady program that ensures interoperability of Arm based servers with standard operating systems and hypervisors.

SystemReady band compliant platforms must implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. 

The SystemReady band compliance and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

## Latest Release details
 - Release version: v3.1.0
 - Quality: EAC
 - **The latest pre-built release of ACS is available for download here: [v25.10_3.1.0](prebuilt_images/v25.10_3.1.0)**
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.
 - SystemReady-band Image Test Suite details

| Test Suite                                                                                   | Test Suite Tag                                               | Specification Version |
|----------------------------------------------------------------------------------------------|--------------------------------------------------------------|-----------------------|
| [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs)                    | v25.04_SR_3.0.1                                              | BSA v1.1              |
| [Server Base System Architecture (SBSA)](https://github.com/ARM-software/sbsa-acs)           | v25.04_SR_3.0.1                                              | SBSA v7.2             |
| [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs)                      | v25.04_SR_3.0.1                                              | BBR v2.1              |
| [Base Boot Security Requirements (BBSR)](https://github.com/ARM-software/bbr-acs)            | v25.04_SR_3.0.1                                              | BBSR v1.3             |
| [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test)           | 0e2ced3befa431bb1aebff005c4c4f1a9edfe6b4                     |                       |
| [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git)                      | v25.01.00                                                    |                       |

## Prebuilt Images
- Prebuilt images for each release are available in the prebuilt_images folder.To access the prebuilt_images, click [prebuilt_images](prebuilt_images/).
- The prebuilt images are archived after compression to the .xz format. On Linux, use the xz utility to uncompress the image <br />
  `xz -d  systemready_acs_live_image.img.xz` <br />
   On Windows, use the 7zip or a similar utility.
- If you choose to use the prebuilt image, skip the build steps and navigate to the [Verification on Arm Neoverse N2 reference design](#verification-on-arm-neoverse-n2-reference-design).

## Steps to Manually Build Image

### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 20.04 or later LTS with at least 32GB of free disk space.
 - Use bash shell.
 - You must have **sudo** privilege to install tools required for build.
 - Install `git` using `sudo apt install git`
 - `git config --global user.name "Your Name"` and `git config --global user.email "Your Email"` must be configured.

### Code download
- To build a release version of the code, checkout the main branch with the appropriate release [tag](https://github.com/ARM-software/arm-systemready/tags).
- To build the latest version of the code with bug fixes and new features, use the main branch.

### Build Steps
1. Clone the arm-systemready repository <br />
 `git clone https://github.com/ARM-software/arm-systemready.git`

2. Navigate to the SystemReady band directory <br />
 `cd arm-systemready/SystemReady-band`

3. Run get_source.sh to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the ACS live image, execute the below step <br />
 `./build-scripts/build-systemready-band-live-image.sh`

5. If all the above steps are successful, then the  bootable image will be available at <br />
   `/path-to-arm-systemready/SystemReady-band/output/systemready_acs_live_image.img.xz`

Note: The image is generated in a compressed (.xz) format. The image must be uncompressed before it is used.<br />

### Build output
This image comprise of single FAT file system partition recognized by UEFI: <br />
- 'BOOT_ACS' <br />
  Approximate size: 640 MB <br />
  contains bootable applications and test suites. <br />
  contains a 'acs_results' directory which stores logs of the automated execution of ACS.


## Image Directory Structure
```
├── EFI
│   └── BOOT
│       ├── Shell.efi
│       ├── bbsr_startup.nsh
│       ├── bootaa64.efi
│       ├── grub.cfg
│       ├── startup_ee.nsh
│       └── startup.nsh
|
├── acs_tests
│   ├── app
│   │   └── CapsuleApp.efi
│   ├── bbr
│   │   ├── SCT
│   │   ├── ScrtStartup.nsh
│   │   ├── SctStartup.nsh
│   │   └── bbsr_SctStartup.nsh
│   ├── bbsr-keys
│   │   ├── NullPK.auth
│   │   ├── TestDB1.auth
│   │   ├── TestDB1.der
│   │   ├── TestDBX1.auth
│   │   ├── TestDBX1.der
│   │   ├── TestKEK1.auth
│   │   ├── TestKEK1.der
│   │   ├── TestPK1.auth
│   │   └── TestPK1.der
│   ├── bsa
│   │   ├── Bsa.efi
│   │   ├── bsa.nsh
│   │   └── sbsa
│   |       |── Sbsa.efi
│   │       └── sbsa.nsh
│   ├── config
│   │   ├── acs_config.txt
│   │   ├── acs_run_config.ini
│   │   └── system_config.txt
│   ├── debug
│   │   └── debug_dump.nsh
│   └── parser
│      ├── parser.nsh
│      ├── Parser.py
│      └── Parser.efi
├── acs_results
├── Image
└── ramdisk-buildroot.img
```
- EFI/BOOT contains the uefi automation startup scripts and grub related files
  - Shell.efi - uefi shell executable
  - bbsr_startup.nsh - bbsr uefi test startup file
  - bootaa64.efi - grub executable
  - grub.cfg - grub config file
  - startup.nsh - uefi automation run startup file
  - startup_ee.nsh - uefi execution enviroment startup file
- acs_tests contains executable files and configs related for test suites
  - app directory contains CapsuleApp.efi
  - bbr directory contains SCT related bianries and sequence files
  - bbsr-keys contains cryptographic keys for secure boot and testing secure firmware updates
  - bsa directory contains bsa uefi executable for bsa compliance
  - bsa/sbsa directory contains sbsa uefi executable for bsa compliance
  - config directory contains system, acs related config files
  - debug directory contains script to gather debug information
  - parser directory contains uefi parser executable and python parser script to parse acs_config file
- acs_results will contain result logs of various test suite run
- Image - Linux kernel image file, also contains linux test suites and processing scripts
  - /init.sh - linux automation script
  - /usr/bin/secure_init.sh - linux automation script for bbsr
  - /usr/bin/fwts - fwts executable
  - /lib/modules/bsa_acs.ko  - BSA Linux test kernel module
  - /bin/bsa  - BSA Linux app
  - /lib/modules/sbsa_acs.ko  - SBSA Linux test kernel module
  - /bin/sbsa  - SBSA Linux app
  - /usr/bin/edk2-test-parser - SCT results parser
  - /usr/bin/device_driver_sr.sh - device driver script
  - /usr/bin/log_parser - directory containing results post processing script
- ramdisk-buildroot.img - ram disk file

## Details and Functionalities of the Image

### Grub Menu & Compliance Run
```
 │ Linux Boot                                    │
 │*SystemReady band ACS (Automation)             │
 │ BBSR Compliance (Automation)                  │
 │ UEFI Execution Enviroment                     │
 │ Linux Execution Enviroment                    │
 │ Linux Boot with SetVirtualAddressMap enabled  |
```
 - **Linux Boot** : This option will boot the ACS Linux kernel and run the default Linux tool (linux debug dump, fwts, linux bsa, linux sbsa (if selected))
   - noacs command line parameter: Edit the Linux Boot grub menu option and add **noacs** at the end of Linux Boot grub menu option, to boot into ACS Linux kernel without running the default Linux test suites.
   - initcall_blacklist=psci_checker command line parameter: Edit the Linux Boot grub menu option and add **initcall_blacklist=psci_checker** to skip default linux psci_checker tool.
 - **SystemReady band ACS (Automation)** : This is **default** option and will run the automated compliance
   - UEFI compliance run - SCT, BSA UEFI, SBSA UEFI (if selected)
   - Boots to Linux and run Linux compliance run - FWTS, BSA Linux, SBSA Linux (if selected)
 - **UEFI Execution Enviroment** : This option is introduced to manually run the selective UEFI test suites like SCT, BSA and SBSA with desired configuration.
 - **Linux Execution Enviroment** : This option is introduced to manually run the selective Linux test suites like FWTS, BSA and SBSA with desired configuration
     For more details on the Execution Enviroment and acs run config, refer to the [SystemReady_Execution_Enviroment_and_Config_Guide](../docs/SystemReady_Execution_Enviroment_and_Config_Guide.md)
   - UEFI compliance run - SCT, BSA UEFI, SBSA UEFI (if selected)
   - Boots to Linux and run Linux compliance run - FWTS, BSA Linux, SBSA Linux (if selected)
 - **BBSR Compliance (Automation)** : This option will run the SCT and FWTS tests required for BBSR compliance, perform a Linux secure boot, and, if a TPM is present, evaluate the measured boot log. For the verification steps of BBSR ACS, refer to the [BBSR ACS Verification](../docs/BBSR_ACS_Verification.md).
 - **Linux Boot with SetVirtualAddressMap enabled** : This option is for debug purpose, to boot ACS Linux with SetVAMap on.

### ACS configs file
- **acs_config.txt**: The file specifies the ARM specification version that the ACS tool suite complies with, and this information is included in the **System_Information** table of the **ACS_Summary.html** report.

- **acs_run_config.ini**: This file is used to manage the execution of various ACS test suites and supports passing parameters to them. <br />

  Please refer to [SystemReady_Execution_Enviroment_and_Config_Guide](../docs/SystemReady_Execution_Enviroment_and_Config_Guide.md) on details of modifying the config file.
 
- **system_config.txt**: The file is used to collect below system information which is required for **ACS_Summary.html** report, It is recommned to fill this information before running the ACS image for complaince.
   - FW source code: Unknown
   - Flashing instructions: Unknown
   - product website: Unknown
   - Tested operated Systems: Unknown
   - Testlab assistance: Unknown

### Log Parser scripts
- The scripts will parse the results generated by various test suite tools and consolidate them into JSON files. These JSON files will adhere to a standard format, maintaining a consistent structure for all test suites
- Also for easier intrepretation, results will also be captured in HTML format.

#### Standard Formatted Result
- The JSON and HTML formatted results are present in /acs_results/**acs_summary**  folder.

#### Waiver application process
- Please follow the [waiver application guide](https://github.com/ARM-software/arm-systemready/blob/main/docs/waiver_guide.md) on details of waiver application to acs results
- Template of waiver.json can be found [here](https://github.com/ARM-software/arm-systemready/blob/main/docs/example_waiver.json)

## Verification on Arm Neoverse N2 reference design

Note: UEFI EDK2 setting for "Console Preference": The default is "Graphical". When that is selected, Linux output will goes to the graphical console (HDMI monitor). To force serial console output, you may change the "Console Preference" to "Serial".

### Software stack and Model

Follow the steps mentioned in [RD-N2 platform software user guide](https://neoverse-reference-design.docs.arm.com/en/latest/platforms/rdn2.html) to obtain RD-N2 FVP.

#### Prerequisites
sudo permission is required for  building RD-N2 software stack.

#### For software stack build instructions, follow BusyBox Boot link under Supported Features by RD-N2 platform software stack section in the same guide.

Note: After the download of software stack code, please do the below changes before starting the build steps.<br />
RD-N2 should be built with the GIC changes as mentioned below as applicable.<br />
- If the system supports LPIs (Interrupt ID > 8192) then firmware should support installation of handler for LPI interrupts.
    - If you are using edk2, change the ArmGic driver in the ArmPkg to support installation of handler for LPIs.
    - Add the following in \<path to RDN2 software stack\>/uefi/edk2/ArmPkg/Drivers/ArmGic/GicV3/ArmGicV3Dxe.c
>        - After [#define ARM_GIC_DEFAULT_PRIORITY  0x80]
>          +#define ARM_GIC_MAX_NUM_INTERRUPT 16384
>        - Change this in GicV3DxeInitialize function.
>          -mGicNumInterrupts      = ArmGicGetMaxNumInterrupts (mGicDistributorBase);
>          +mGicNumInterrupts      = ARM_GIC_MAX_NUM_INTERRUPT;


### Model run command

1. Set the environment variable 'MODEL' <br />
  `export MODEL=<absolute path to the RD-N2 FVP binary/FVP_RD_N2>`

3. Launch the RD-N2 FVP with the pre-built image with the following command <br />
  `cd /path to RD-N2_FVP platform software/model-scripts/rdinfra/platforms/rdn2` <br />
  `./run_model.sh -v /path-to-systemready-acs-live-image/systemready_acs_live_image.img`

**Note: When verifying ACS on hardware, ensure that ACS image is not in two different boot medias (USB, NVMe drives etc) attached to the device.**


Known limitations:<br />
On FVP models, with versions previous to 11.15.23, during the execution of the UEFI-SCT suite, the following behavior is observed:

1. Execution of the 'UEFIRuntimeServices' tests may cause the test execution on FVP to stall and become non-responsive.
The message displayed prior to this stall would be either “System may reset after 1 second…” or a print associated with 'SetTime' tests.

The FVP execution must be terminated and restarted by running the run_model.sh script to continue with the execution of the tests.
The execution continues from the test that is next in sequence of the test prior to FVP stall.

2. It may appear that the test execution has stalled with the message “Waiting for few seconds for signal …” displayed on the console.
This is expected behavior and the progress of tests will continue after a 20-minute delay.


## Security Implication
Arm SystemReady band ACS test suite may run at higher privilege level. An attacker may utilize these tests as a means to elevate privilege which can potentially reveal the platform security assets. To prevent the leakage of Secure information, it is strongly recommended that the ACS test suite is run only on development platforms. If it is run on production systems, the system should be scrubbed after running the test suite.

## License
SystemReady ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to support-systemready-acs@arm.com with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2022-2025, Arm Limited and Contributors. All rights reserved.*
