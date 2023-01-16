# SystemReady IR ACS

## Introduction to SystemReady IR
SystemReady IoT Ready (IR) is a band of system certification in the Arm SystemReady program. This certification is for devices in the IoT edge sector that are built around SoCs based on the Arm A-profile architecture. It ensures interoperability with embedded Linux and other embedded operating systems.

SystemReady IR-certified platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Base System Architecture (BSA) specification](https://developer.arm.com/documentation/den0094/latest)
* [Embedded Base Boot Requirements (EBBR)](https://developer.arm.com/architectures/platform-design/embedded-systems)
* EBBR recipe of the [Arm Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/latest)

This section of the repository contains the build scripts and the live-images for the SystemReady IR Band.

## Release details
 - Code Quality: IR ACS v2.0.0 Beta-1
 - The latest pre-built release of IR ACS is available for download here: [v22.10_2.0.0_BETA-1](https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v22.10_2.0.0_BETA-1)
 - The BSA tests are written for version 1.0 of the BSA specification.
 - The BBR tests are written for version 1.0 of the BBR specification.
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.



## Steps to build SystemReady IR ACS live image using the Yocto build system

## Code download
- To build a release version of the code, checkout the main branch with the appropriate release tag.
- To build the latest version of the code with bug fixes and new features, use the main branch.

## ACS build steps

### Prebuilt images
- Prebuilt images for each release are available in the prebuilt_images folder. You can either choose to use these images or build your own image by following the build steps.
- To access the prebuilt_images, click : [prebuilt_images](prebuilt_images/)
- The prebuilt images are archived after compression to the .xz format. On Linux, use the xz utility to uncompress the image `xz -d ir-acs-live-image-generic-arm64.wic.xz`. On Windows, use the 7zip or a similar utility.
- If you choose to use the prebuilt image, skip the build steps, and navigate to the "Verification" section below.


### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 18.04 or 20.04 LTS with at least 32GB of free disk space.
 - Availability of the Bash shell.
 - **sudo** privilege to install tools required for the build.
 - `git` installed using `sudo apt install git`.
 - Configuration of email using the commands `git config --global user.name "Your Name"` and `git config --global user.email "Your Email"`.

### Steps to build SystemReady IR ACS live image
1. Clone the arm-systemready repository <br />
 `git clone "https://github.com/ARM-software/arm-systemready.git"`

2. Navigate to the IR/Yocto directory <br />
 `cd arm-systemready/IR/Yocto`

3. Run get_source.sh to download all the related sources and tools for the build. Provide sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the IR ACS live image, execute the below step <br />
 `./build-scripts/build-ir-live-image.sh`

5. If the above steps are successful, the bootable image will be available at <br />
  **/path-to-arm-systemready/IR/Yocto/meta-woden/build/tmp/deploy/images/generic-arm64/ir-acs-live-image-generic-arm64.wic.xz**

Note: The image is generated in a compressed (.xz) format. The image must be uncompressed before using the same for verification.<br />

## Build output
This image comprises of two FAT file system partitions recognized by UEFI: <br />
- 'results' <br />
  Stores logs of the automated execution of ACS. (Approximate size: 50 MB) <br/>
- '/' <br />
  Root partition for Linux which contains test-suites to run in Linux environment. <br/>
- 'boot' <br />
  Contains bootable applications and test suites. (Approximate size: 100 MB)

## Verification

Note: The default UEFI EDK2 setting for "Console Preference" is "Graphical". In this default setting, the Linux output goes only to the graphical console (HDMI monitor). To force serial console output, you may change "Console Preference" to "Serial".

### Verification of the IR image on QEMU Arm machine

#### Follow the Build instructions mentioned in [qemu download page](https://www.qemu.org/download/#source) to build latest QEMU model.

NOTE: Download the toolchain from [arm developer page](https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-a/downloads/10-2-2020-11) <br />
NOTE: If repo sync fails due to incorrect repo version , please update repo using the below steps.<br />
```
mkdir -p ~/.bin
PATH="${HOME}/.bin:${PATH}"
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.bin/repo
chmod a+rx ~/.bin/repo
```

#### To build the firmware image, follow the below steps

```
mkdir working_directory
cd working_directory
repo init -u https://github.com/glikely/u-boot-manifest
repo sync
export CROSS_COMPILE=<path to gcc-arm-10.2-2020.11-x86_64-aarch64-none-elf/bin/aarch64-none-elf->
make qemu_arm64_defconfig
make
```
nor_flash.bin is generated once the build is completed.


#### Verifying the ACS-IR pre-built image
Launch the model with the below command

```
<path to qemu-system-aarch64> -bios <path to nor_flash.bin>  -drive file=<path to ir-acs-live-image-generic-arm64.wic>,if=virtio,format=raw  -cpu cortex-a57 -smp 2 -m 2048 -M virt,secure=on -monitor null -no-acpi -nodefaults -nographic -rtc base=utc,clock=host -serial stdio -d unimp,guest_errors -machine virtualization=on
```

### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can be run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.
2. [UEFI Shell application](https://github.com/ARM-software/bsa-acs/blob/main/README.md) for BSA compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.

### Running Security interface extension (SIE) ACS.

For the verification steps of SIE ACS on QEMU with TPM support, refer to the [SIE ACS Verification](../../common/docs/SIE_ACS_Verification.md).

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: v22.07.00

- [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs) TAG: v22.06_IR_2.0.0_BETA-1

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: v22.06_IR_2.0.0_BETA-1

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 4a25c3b3c79f63bd9f98b4fffcb21b5c66dd14bb



## Security Implication
Arm SystemReady IR ACS test suite may run at higher privilege level. An attacker may utilize these tests as a means to elevate privilege which can potentially reveal the platform security assets. To prevent the leakage of Secure information, it is strongly recommended that the ACS test suite is run only on development platforms. If it is run on production systems, the system should be scrubbed after running the test suite.

## License
System Ready ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2022-2023, Arm Limited and Contributors. All rights reserved.*

