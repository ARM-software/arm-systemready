# SystemReady IR ACS

## Introduction to SystemReady IR
SystemReady IoT Ready (IR) is a band of system certification in the Arm SystemReady program. This certification is for devices in the IoT edge sector that are built around SoCs based on the Arm A-profile architecture. It ensures interoperability with embedded Linux and other embedded operating systems.

SystemReady IR-certified platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Embedded Base Boot Requirements (EBBR)](https://developer.arm.com/architectures/platform-design/embedded-systems)
* EBBR recipe of the [Arm Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/latest)
* SystemReady IR certification and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

This section of the repository contains the build scripts and the live-images for the SystemReady IR Band.

## Release details
 - Code Quality: v0.9 BETA
 - **The latest pre-built release of IR ACS is available for download here: [v21.07_0.9_BETA](prebuilt_images/v21.07_0.9_BETA)**
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
- If you choose to use the prebuilt image, skip the build steps, and jump to the "Verification" section below.

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

### Verification of the IR Image on arm Base FVP Models

#### Base FVP Models can be obtained from [arm developer page](https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms)

#### Software stack for models can be built following steps mentioned in [linaro arm-reference-platforms user guide](https://git.linaro.org/landing-teams/working/arm/arm-reference-platforms.git/about/docs/user-guide.rst)
- To use Yocto for building  Board Support Package, refer [linaro basefvp user guide](https://git.linaro.org/landing-teams/working/arm/arm-reference-platforms.git/about/docs/basefvp/user-guide.rst)

- Following changes needs to be enabled in the u-boot.
```
--- a/arch/arm/Kconfig
+++ b/arch/arm/Kconfig
@@ -1188,6 +1188,7 @@ config TARGET_VEXPRESS64_BASE_FVP
        select ARM64
        select PL01X_SERIAL
        select SEMIHOSTING
+       select OF_CONTROL
```
```
--- a/arch/arm/dts/Makefile
+++ b/arch/arm/dts/Makefile
@@ -4,6 +4,7 @@ dtb-$(CONFIG_TARGET_SMARTWEB) += at91sam9260-smartweb.dtb
 dtb-$(CONFIG_TARGET_TAURUS) += at91sam9g20-taurus.dtb
 dtb-$(CONFIG_TARGET_CORVUS) += at91sam9g45-corvus.dtb
 dtb-$(CONFIG_TARGET_GURNARD) += at91sam9g45-gurnard.dtb
+dtb-y += fvp-base-aemv8a-aemv8a.dtb
```
NOTE: If using Base RevC FVP Model, use the device tree file for that model.

- Change the bootcmd to
```
+#define CONFIG_BOOTCOMMAND     "fdt addr ${fdtcontroladdr};" \
+                               "  virtio scan; " \
+                               "  virtio info; " \
+                               "  fatload virtio 0 ${kernel_addr} EFI/BOOT/bootaa64.efi; " \
+                               "  bootefi $kernel_addr  $fdtcontroladdr; "
```

- Enable below configs via menuconfig
```
Device Drivers → Support block devices
Device Drivers → VirtIO drivers → Platform bus driver for memory mapped virtio devices
Device Drivers → VirtIO drivers → Platform driver for virtio devices
Device Drivers → VirtIO drivers → Platform block driver
Device Tree Control → Default Device Tree for DT Control → fvp-base-aemv8a-aemv8a
```
If the Model supports PCIe, enable below configs also
```
Device Drivers → PCI support
Device Drivers → PCI support → Enable driver model for PCI
Device Drivers → PCI support → Generic ECAM-based PCI host controller support
```

#### Verifying the ACS-IR pre-built image
1. Set the enviroment variable 'MODEL'
```
export MODEL=<absolute path to the Base FVP bianry>
```
2. Set the enviroment variable 'BL1'
```
export BL1=<absolute path to the BL1 binary>
```
3. Set the enviroment variable 'FIP'
```
export FIP=<absolute path to the FIP binary>
```
4. Set the enviroment variable 'DISK'
```
export DISK=<absolute path to the ACS-IR image>
```
5. Launch model with below command
```
$MODEL \
-C pctl.startup=0.0.0.0 \
-C bp.secure_memory=0 \
-C cluster0.NUM_CORES=4 \
-C cluster1.NUM_CORES=4 \
-C cache_state_modelled=0 \
-C bp.pl011_uart0.untimed_fifos=1 \
-C bp.pl011_uart0.unbuffered_output=1 \
-C bp.pl011_uart0.out_file=uart0.log \
-C bp.pl011_uart1.out_file=uart1.log \
-C bp.secureflashloader.fname=${BL1} \
-C bp.flashloader0.fname=${FIP} \
-C bp.ve_sysregs.mmbSiteDefault=0 \
-C bp.ve_sysregs.exit_on_shutdown=1 \
-C bp.virtioblockdevice.image_path=${DISK} \
-C cluster0.has_fp16=2 \
-C cluster1.has_fp16=2 \
-C cluster0.has_arm_v8-1=1 \
-C cluster0.has_arm_v8-2=1 \
-C cluster0.has_arm_v8-3=1 \
-C cluster0.has_arm_v8-4=1 \
-C cluster0.has_arm_v8-5=1 \
-C cluster0.has_arm_v8-6=1 \
-C cluster1.has_arm_v8-1=1 \
-C cluster1.has_arm_v8-2=1 \
-C cluster1.has_arm_v8-3=1 \
-C cluster1.has_arm_v8-4=1 \
-C cluster1.has_arm_v8-5=1 \
-C cluster1.has_arm_v8-6=1 \
-C cluster0.restriction_on_speculative_execution=2 \
-C cluster1.restriction_on_speculative_execution=2 \
-C cluster0.pstate_ssbs_type=2 \
-C cluster1.pstate_ssbs_type=2 \
-C cluster0.cpu0.number-of-breakpoints=16 \
-C cluster0.cpu1.number-of-breakpoints=16 \
-C cluster0.cpu2.number-of-breakpoints=16 \
-C cluster0.cpu3.number-of-breakpoints=16 \
-C cluster0.cpu4.number-of-breakpoints=16 \
-C cluster0.cpu5.number-of-breakpoints=16 \
-C cluster0.cpu6.number-of-breakpoints=16 \
-C cluster0.cpu7.number-of-breakpoints=16 \
-C cluster1.cpu0.number-of-breakpoints=16 \
-C cluster1.cpu1.number-of-breakpoints=16 \
-C cluster1.cpu2.number-of-breakpoints=16 \
-C cluster1.cpu3.number-of-breakpoints=16 \
-C cluster1.cpu4.number-of-breakpoints=16 \
-C cluster1.cpu5.number-of-breakpoints=16 \
-C cluster1.cpu6.number-of-breakpoints=16 \
-C cluster1.cpu7.number-of-breakpoints=16 \
-C cluster0.cpu0.number-of-context-breakpoints=16 \
-C cluster0.cpu1.number-of-context-breakpoints=16 \
-C cluster0.cpu2.number-of-context-breakpoints=16 \
-C cluster0.cpu3.number-of-context-breakpoints=16 \
-C cluster0.cpu4.number-of-context-breakpoints=16 \
-C cluster0.cpu5.number-of-context-breakpoints=16 \
-C cluster0.cpu6.number-of-context-breakpoints=16 \
-C cluster0.cpu7.number-of-context-breakpoints=16 \
-C cluster1.cpu0.number-of-context-breakpoints=16 \
-C cluster1.cpu1.number-of-context-breakpoints=16 \
-C cluster1.cpu2.number-of-context-breakpoints=16 \
-C cluster1.cpu3.number-of-context-breakpoints=16 \
-C cluster1.cpu4.number-of-context-breakpoints=16 \
-C cluster1.cpu5.number-of-context-breakpoints=16 \
-C cluster1.cpu6.number-of-context-breakpoints=16 \
-C cluster1.cpu7.number-of-context-breakpoints=16 \
```
### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can be run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.
2. [UEFI Shell application](https://github.com/ARM-software/bsa-acs/blob/master/README.md) for BSA compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: 08378441d14c0c28b51f9843906582a81a9c1659

- [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs) TAG: v21.07_0.9_BETA

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: : v21.07_0.9_BETA

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 61dddf12db3d17cf19134089db45fbefb29ed004



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

*Copyright (c) 2021, Arm Limited and Contributors. All rights reserved.*

