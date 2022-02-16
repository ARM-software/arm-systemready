# SystemReady IR ACS

## Introduction to SystemReady IR
SystemReady IoT Ready (IR) is a band of system certification in the Arm SystemReady program. This certification is for devices in the IoT edge sector that are built around SoCs based on the Arm A-profile architecture. It ensures interoperability with embedded Linux and other embedded operating systems.

SystemReady IR-certified platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Base System Architecture (BSA) specification](https://developer.arm.com/documentation/den0094/latest)
* [Embedded Base Boot Requirements (EBBR)](https://developer.arm.com/architectures/platform-design/embedded-systems)
* EBBR recipe of the [Arm Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/latest)
* SystemReady IR certification and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

This section of the repository contains the build scripts and the live-images for the SystemReady IR Band.

## Release details
 - Code Quality: v1.0
 - **The latest pre-built release of IR ACS is available for download here: [v21.09_1.0](prebuilt_images/v21.09_1.0)**
 - The BSA tests are written for version 1.0 of the BSA specification.
 - The BBR tests are written for version 1.0 of the BBR specification.
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.


## Steps to build SystemReady IR ACS live image

## Code download
- To build a release version of the code, checkout the main branch with the appropriate release tag.
- To build the latest version of the code with bug fixes and new features, use the main branch.

## ACS build steps

### Prebuilt images
- Prebuilt images for each release are available in the prebuilt_images folder. You can either choose to use these images or build your own image by following the build steps.
- To access the prebuilt_images, click : [prebuilt_images](prebuilt_images/)
- The prebuilt images are archived after compression to the .xz format. On Linux, use the xz utility to uncompress the image `xz -d es_acs_live_image.img.xz`. On Windows, use the 7zip or a similar utility.
- If you choose to use the prebuilt image, skip the build steps, and navigate to the "Verification" section below.

Note: The latest pre-built image contains Linux kernel version 5.13. To build a image with a different Linux kernel version, update the `LINUX_KERNEL_VERSION` in the configuration file `<path to arm-systemready>/common/config/common_config.cfg` before the build (after step 3 below). To see the list of kernel versions for which Linux BSA patches are available, see the [folder](https://gitlab.arm.com/linux-arm/linux-acs/-/tree/master/kernel/src)

### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 18.04 or 20.04 LTS with at least 32GB of free disk space.
 - Must use Bash shell.
 - You must have **sudo** privilege to install tools required for build.
 - Install `git` using `sudo apt install git`
 - `git config --global user.name "Your Name"` and `git config --global user.email "Your Email"` must be configured.

### Steps to build SystemReady IR ACS live image
1. Clone the arm-systemready repository <br />
 `git clone https://github.com/ARM-software/arm-systemready.git`

2. Navigate to the IR/scripts directory <br />
 `cd arm-systemready/IR/scripts`

3. Run get_source.sh to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the IR ACS live image, execute the below step <br />
 `./build-scripts/build-ir-live-image.sh`

5. If all the above steps are successful, the bootable image will be available at **/path-to-arm-systemready/IR/scripts/output/ir_acs_live_image.img.xz**

Note: The image is generated in a compressed (.xz) format. The image must be uncompressed before they are used.<br />

## Build output
This image comprises of two FAT file system partitions recognized by UEFI: <br />
- 'acs-results' <br />
  Stores logs of the automated execution of ACS. (Approximate size: 120 MB) <br/>
- 'boot' <br />
  Contains bootable applications and test suites. (Approximate size: 400 MB)

## Verification

Note: UEFI EDK2 setting for "Console Preference": The default is "Graphical". In this default setting, Linux output will go only to the graphical console (HDMI monitor). To force serial console output, you may change the "Console Preference" to "Serial".

### Verification of the IR image on Qemu arm machine

#### Follow the Build instructions mentioned in [qemu download page](https://www.qemu.org/download/#source) to build latest qemu model.

#### To build the firmware image, follow below steps

```
mkdir working_directory
cd working_directory
repo init -u https://github.com/glikely/u-boot-manifest
repo sync
export CROSS_COMPILE=<path to gcc-arm-10.2-2020.11-x86_64-aarch64-none-elf/bin/aarch64-none-elf->
make qemu_arm64_defconfig
make
```
nor_flash.bin will be generated once build is completed.

NOTE: If sync fails due repo version , please update repo using below steps.<br />
NOTE: Toolchain can be downloaded from [arm developer page](https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-a/downloads/10-2-2020-11)


```
mkdir -p ~/.bin
PATH="${HOME}/.bin:${PATH}"
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.bin/repo
chmod a+rx ~/.bin/repo
```
#### Verifying the ACS-IR pre-built image
Launch model with below command

```
<path to qemu-system-aarch64> -bios <path to nor_flash.bin>  -drive file=<path to ir_acs_live_image.img>,if=virtio,format=raw  -cpu cortex-a57 -smp 2 -m 2048 -M virt,secure=on -monitor null -no-acpi -nodefaults -nographic -rtc base=utc,clock=host -serial stdio -d unimp,guest_errors -machine virtualization=on
```
### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can be run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.
2. [UEFI Shell application](https://github.com/ARM-software/bsa-acs/blob/master/README.md) for BSA compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: V21.08.00 

- [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs) TAG: v21.09_1.0

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: : v21.09_1.0

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: edk2-test-stable202108



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

*Copyright (c) 2021-2022, Arm Limited and Contributors. All rights reserved.*

