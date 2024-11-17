# SystemReadyband ACS


## Introduction to SystemReady band
SystemReady band is a band of system complaince in the Arm SystemReady program that ensures interoperability of Arm based servers with standard operating systems and hypervisors.

SystemReady band complaint platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Server Base System Architecture (SBSA) specification](https://developer.arm.com/documentation/den0029/h/?lang=en)
* SBBR recipe of the [Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/f/?lang=en)
* The SystemReady band complaince and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

This section contains the build scripts and the live-images for the SystemReady band.

## Release details
 - Code quality: v3.0.0
 - **The latest pre-built release of ACS is available for download here: [v23.09_2.0.0](prebuilt_images/v23.09_2.0.0)**
 - The SBSA tests are written for version 7.1 of the SBSA specification.
 - The BSA tests are written for version 1.0 (c) of the BSA specification.
 - The BBR tests are written for the SBBR section in version 1.0 of the BBR specification.
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.


## Steps to build SystemReady band ACS live image

## Code download
- To build a release version of the code, checkout the main branch with the appropriate release tag.
- To build the latest version of the code with bug fixes and new features, use the main branch.

## ACS build steps

### Prebuilt images
- Prebuilt images for each release are available in the prebuilt_images folder. You can either choose to use these images or build your own image by following the build steps.
- To access the prebuilt_images, click [prebuilt_images](prebuilt_images/)
- The prebuilt images are archived after compression to the .xz format. On Linux, use the xz utility to uncompress the image `xz -d systemready_acs_live_image.img.xz`. On Windows, use the 7zip or a similar utility.
- If you choose to use the prebuilt image, skip the build steps and navigate to the [Verification](#Verification) section below.

### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 20.04 or later LTS with at least 32GB of free disk space.
 - Use bash shell.
 - You must have **sudo** privilege to install tools required for build.
 - Install `git` using `sudo apt install git`
 - `git config --global user.name "Your Name"` and `git config --global user.email "Your Email"` must be configured.

### Steps to build SystemReady band ACS live image
1. Clone the arm-systemready repository <br />
 `git clone "ssh://$USER@ap-gerrit-1.ap01.arm.com:29418/avk/syscomp_systemready" arm-systemready`

2. Navigate to the SystemReady band directory <br />
 `cd arm-systemready/SystemReady-band`

3. Run get_source.sh to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the ACS live image, execute the below step <br />
 `./build-scripts/build-systemready-live-image.sh`

5. If all the above steps are successful, then the  bootable image will be available at **/path-to-arm-systemready/SystemReady-band/output/systemready_acs_live_image.img.xz**

Note: The image is generated in a compressed (.xz) format. The image must be uncompressed before it is used.<br />

## Build output
This image comprise of single FAT file system partition recognized by UEFI: <br />
- 'BOOT_ACS' <br />
  Approximate size: 640 MB <br />
  contains bootable applications and test suites. <br />
  contains a 'acs_results' directory which stores logs of the automated execution of ACS.


## Verification

Note: UEFI EDK2 setting for "Console Preference": The default is "Graphical". When that is selected, Linux output will goes to the graphical console (HDMI monitor). To force serial console output, you may change the "Console Preference" to "Serial".

### Verification of the SystemReady band image on the Arm Neoverse N2 reference design (RD-N2)

#### Prerequisites
sudo permission is required for  building RD-N2 software stack.

#### Follow the steps mentioned in [RD-N2 platform software user guide](https://neoverse-reference-design.docs.arm.com/en/latest/platforms/rdn2/readme.html#rd-n2-readme-label) to obtain RD-N2 FVP.

### For software stack build instructions, follow BusyBox Boot link under Supported Features by RD-N2 platform software stack section in the same guide.

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


#### Verifying the ACS-SR pre-built image

1. Set the environment variable 'MODEL'
```
export MODEL=<absolute path to the RD-N2 FVP binary/FVP_RD_N2>
```
2. Launch the RD-N2 FVP with the pre-built image with the following command
```
cd /path to RD-N2_FVP platform software/model-scripts/rdinfra/platforms/rdn2
./run_model.sh -v /path-to-systemready-acs-live-image/systemready_acs_live_image.img
```
This starts the ACS live image automation and run the test suites in sequence.

Known limitations:<br />
On FVP models, with versions previous to 11.15.23, during the execution of the UEFI-SCT suite, the following behavior is observed:

1. Execution of the 'UEFIRuntimeServices' tests may cause the test execution on FVP to stall and become non-responsive.
The message displayed prior to this stall would be either “System may reset after 1 second…” or a print associated with 'SetTime' tests.

The FVP execution must be terminated and restarted by running the run_model.sh script to continue with the execution of the tests.
The execution continues from the test that is next in sequence of the test prior to FVP stall.

2. It may appear that the test execution has stalled with the message “Waiting for few seconds for signal …” displayed on the console.
This is expected behavior and the progress of tests will continue after a 20-minute delay.

Note:
When verifiying ACS on hardware, ensure that ACS image is not in two different boot medias (USB, NVMe drives etc) attached to the device.

### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.
2. [UEFI Shell application](https://github.com/ARM-software/sbsa-acs/blob/master/README.md) for SBSA compliance.
                           (https://github.com/ARM-software/bsa-acs/blob/main/README.md)    for BSA compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.
4. [OS tests](https://github.com/ARM-software/sbsa-acs/blob/master/README.md) for Linux SBSA compliance.<br />
Note: To skip FWTS and OS tests for debugging, append "noacs" to the Linux command by editing the "Linux Boot" option in the grub menu during image boot.<br />
To start an extended run of UEFI-SCT append "-nostartup startup.nsh sct_extd" to the shell.efi command by editing the "bbr/bsa" option in the grub menu during image boot.<br />

### Running BBSR (BBSR) ACS components.
Now BBSR ACS is integrated with SR ACS image, which can be accessed through GRUB options.

For the verification steps of BBSR ACS, refer to the [BBSR ACS Verification](../common/docs/BBSR_ACS_Verification.md).

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: v23.07.00

- [Server Base System Architecture (SBSA)](https://github.com/ARM-software/sbsa-acs) TAG: v23.09_REL7.1.3

- [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs) TAG: v23.09_REL1.0.6

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: v23.09_SR_REL2.0.0_ES_REL1.3.0_IR_REL2.1.0

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 032822757792c5d4d0bfed1fd8524e69ef4f2d17



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

