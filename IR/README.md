# SystemReady IR ACS

## Introduction to SystemReady IR
SystemReady IR - IoT, is a band of system certification in the Arm SystemReady program. This certification is for devices in the IoT edge sector that are built around SoCs based on the Arm A-profile architecture. It ensures interoperability with embedded Linux and other embedded operating systems.

SystemReady IR-certified platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Embedded Base Boot Requirements (EBBR)](https://developer.arm.com/architectures/platform-design/embedded-systems)
* EBBR recipe of the [Arm Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/latest)
* SystemReady IR certification and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

This section contains the build scripts and the live-images for the SystemReady IR Band.

## Release details
 - Code Quality: v0.8 BETA-0
 - **The latest pre-built release of IR ACS is available for download here: [v21.05_0.8_BETA-0](prebuilt_images/v21.05_0.8_BETA-0)**
 - The BSA tests are written for version 1.0 of the BSA specification.
 - The BBR tests are written for version 1.0 of the BBR specification.
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.


## Steps to build SystemReady IR ACS live image

## GitHub branch
- To pick up the release version of the code, checkout the release branch with the appropriate tag.
- To get the latest version of the code with bug fixes and new features, use the master branch.

## ACS build steps

### Prebuilt images
- Prebuilt images for each release are available in the prebuilt_images folder of the release branch. You can either choose to use these images or build your own image by following the steps below.
- To access the prebuilt_images, click this link : [prebuilt_images](prebuilt_images/)
- If you choose to use the prebuilt image, skip the build steps and jump to the test suite execution section below.

### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 18.04 LTS with at least 64GB of free disk space.
 - Must use Bash shell.
 - User should have **sudo** privilege to install tools required for build
 - Need to install `git` before  build using `sudo apt install git`
 - `git config --global user.name "Your Name"` and `git config --global user.email "Your Email"` must be configured before build.

### Steps to build SystemReady IR ACS live image
1. Clone the [Arm-SystemReady](https://github.com/ARM-software/arm-systemready) repo.

2. Navigate to the IR/scripts directory <br />
 `cd arm-systemready/IR/scripts`

3. Run get_source.sh to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the IR ACS live image, execute the below step <br />
 `./build-scripts/build-ir-live-image.sh`

5. If all of above steps are successful, the bootable image will be available at **/path-to-arm-systemready/IR/scripts/output/ir_acs_live_image.img**

## Build output
This image comprises of two FAT file system partitions recognized by UEFI: <br />
- 'acs-results' <br />
  Stores logs and is used to install UEFI-SCT. (Approximate size: 120 MB) <br/>
- 'boot' <br />
  Contains bootable applications and test suites. (Approximate size: 400 MB)

## Verification

Note: UEFI EDK2 setting for "Console Preference": The default is "Graphical". When that is selected, Linux output will go only to the graphical console (HDMI monitor). In order to force serial console output, you need to change the "Console Preference" to "Serial".

### Verification of the IR Image on Qemu
ACS is tested using Qemu 6.0 version. <br />
Command to boot with qemu :
   `qemu-system-aarch64 -bios <**Path to QEMU u-boot firmware**>/nor_flash.bin -cpu cortex-a57 -drive file=<**Path to IR live image**>/ir_acs_live_image.img,if=virtio,format=raw -m 2048 -machine virt,secure -monitor null -no-acpi -nodefaults -nographic -rtc base=utc,clock=host -serial stdio -smp 2 -accel tcg,thread=multi -d unimp,guest_errors`
   Note: qemu for aarch64 must be installed  before running above command  by `sudo apt-get install qemu-utils qemu-efi qemu-system-arm`

### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can be run in following order:

1. [UEFI Shell application](https://github.com/ARM-software/bsa-acs/blob/master/README.md) for BSA compliance.
2. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.
4. [OS tests](https://github.com/ARM-software/bsa-acs/blob/master/README.md) for BSA compliance.

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS) TAG: V21.03.00](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: 2495b85c20944013949cab8ec6e8fad54b874308  

- [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs) TAG: v21.05_0.5_ALPHA    

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: : v21.05_0.8_BETA-0 

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 421a6997ef362c6286c4ef87d21d5367a9d1fb58
 


## Security Implication
Arm SystemReady IR ACS test suite may run at higher privilege level. An attacker may utilize these tests as a means to elevate privilege which can potentially reveal the platform security assets. To prevent the leakage of secure information, it is strongly recommended that the ACS test suite is run only on development platforms. If it is run on production systems, the system should be scrubbed after running the test suite.

## License
System Ready ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, please send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2021, Arm Limited and Contributors. All rights reserved.*
