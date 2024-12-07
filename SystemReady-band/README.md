# SystemReady band ACS

## Table of Contents

- [Introduction](#introduction)
- [Latest Release details](#release-details)
- [Prebuilt Images](#prebuilt-images)
- [Steps to Manually Build an Image](#build-steps)
- [Verification on Arm Neoverse N2 reference design (RD-N2)](#verification)
- [Examples](#examples)
- [Understanding the Waiver Application Process](#understanding-the-waiver-application-process)
- [Important Notes](#important-notes)


## Introduction
SystemReady band is a band of system compliance in the Arm SystemReady program that ensures interoperability of Arm based servers with standard operating systems and hypervisors.

SystemReady band compliant platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. 

* The SystemReady band compliance and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

## Latest Release details
 - Code quality: v3.0.0-BET0
 - **The latest pre-built release of ACS is available for download here: [v24.11_3.0.0-BET0](prebuilt_images/v24.11_3.0.0-BET0)**
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.
 - SystemReady-band Image Test Suite details

| Test Suite                                                                                   | Test Suite Tag                                               | Specification Version |
|----------------------------------------------------------------------------------------------|--------------------------------------------------------------|-----------------------|
| [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs)                    | v24.11_REL1.0.9                                              | BSA v1.0 (c)          |
| [Server Base System Architecture (SBSA)](https://github.com/ARM-software/sbsa-acs)           | v24.11_REL7.2.1                                              | SBSA v7.1             |
| [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs)                      | v24.11_EBBR_REL2.2.0-BETA0_SBBR_REL2.1.0-BETA0_BBSR_REL1.3.0 | BBR v2.1              |
| [Base Boot Security Requirements (BBSR)](https://github.com/ARM-software/bbr-acs)            | v24.11_EBBR_REL2.2.0-BETA0_SBBR_REL2.1.0-BETA0_BBSR_REL1.3.0 | BBSR v1.3             |
| [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test)           | 0e2ced3befa431bb1aebff005c4c4f1a9edfe6b4                     |                       |
| [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git)                      | v24.09.00                                                    |                        |


## Prebuilt Images
- Prebuilt images for each release are available in the prebuilt_images folder. You can either choose to use these images or build your own image by following the build steps.
- To access the prebuilt_images, click [prebuilt_images](prebuilt_images/)
- The prebuilt images are archived after compression to the .xz format. On Linux, use the xz utility to uncompress the image `xz -d systemready_acs_live_image.img.xz`. On Windows, use the 7zip or a similar utility.
- If you choose to use the prebuilt image, skip the build steps and navigate to the [Verification](#Verification) section below.

## Steps to Manually Build an Image

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

### Steps to build SystemReady band ACS live image
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


## Verification on Arm Neoverse N2 reference design (RD-N2)

Note: UEFI EDK2 setting for "Console Preference": The default is "Graphical". When that is selected, Linux output will goes to the graphical console (HDMI monitor). To force serial console output, you may change the "Console Preference" to "Serial".

### Arm Neoverse N2 reference design (RD-N2) FVP

Follow the steps mentioned in [RD-N2 platform software user guide](https://neoverse-reference-design.docs.arm.com/en/latest/platforms/rdn2.html) to obtain RD-N2 FVP.

### Arm Neoverse N2 reference design (RD-N2) software stack

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


### Verifying the ACS-SR pre-built image

1. Set the environment variable 'MODEL' <br />
  `export MODEL=<absolute path to the RD-N2 FVP binary/FVP_RD_N2>`

3. Launch the RD-N2 FVP with the pre-built image with the following command <br />
  `cd /path to RD-N2_FVP platform software/model-scripts/rdinfra/platforms/rdn2` <br />
  `./run_model.sh -v /path-to-systemready-acs-live-image/systemready_acs_live_image.img`

This starts the ACS live image automation and run the test suites in sequence.

Known limitations:<br />
On FVP models, with versions previous to 11.15.23, during the execution of the UEFI-SCT suite, the following behavior is observed:

1. Execution of the 'UEFIRuntimeServices' tests may cause the test execution on FVP to stall and become non-responsive.
The message displayed prior to this stall would be either “System may reset after 1 second…” or a print associated with 'SetTime' tests.

The FVP execution must be terminated and restarted by running the run_model.sh script to continue with the execution of the tests.
The execution continues from the test that is next in sequence of the test prior to FVP stall.

2. It may appear that the test execution has stalled with the message “Waiting for few seconds for signal …” displayed on the console.
This is expected behavior and the progress of tests will continue after a 20-minute delay.

Note: When verifying ACS on hardware, ensure that ACS image is not in two different boot medias (USB, NVMe drives etc) attached to the device.

### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.
2. [BSA](https://github.com/ARM-software/bsa-acs/blob/main/README.md) for BSA compliance.
3. [SBSA](https://github.com/ARM-software/sbsa-acs/blob/master/README.md) for SBSA compliance.
4. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.
5. [OS tests](https://github.com/ARM-software/sbsa-acs/blob/master/README.md) for Linux SBSA compliance.<br />

Note: To skip FWTS and OS tests for debugging, append "noacs" to the Linux command by editing the "Linux Boot" option in the grub menu during image boot.<br />
To start an extended run of UEFI-SCT append "-nostartup startup.nsh sct_extd" to the shell.efi command by editing the "bbr/bsa" option in the grub menu during image boot.<br />

### Running BBSR (BBSR) ACS components.
Now BBSR ACS is integrated with SR ACS image, which can be accessed through GRUB options.

For the verification steps of BBSR ACS, refer to the [BBSR ACS Verification](../common/docs/BBSR_ACS_Verification.md).

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

*Copyright (c) 2022-2024, Arm Limited and Contributors. All rights reserved.*

