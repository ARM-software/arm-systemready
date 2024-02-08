# SystemReady IR ACS

## Introduction to SystemReady IR
SystemReady IoT Ready (IR) is a band of system certification in the Arm SystemReady program. This certification is for devices in the IoT edge sector that are built around SoCs based on the Arm A-profile architecture. It ensures interoperability with embedded Linux and other embedded operating systems.

SystemReady IR-certified platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Base System Architecture (BSA) specification](https://developer.arm.com/documentation/den0094/latest)
* [Embedded Base Boot Requirements (EBBR)](https://developer.arm.com/architectures/platform-design/embedded-systems)
* EBBR recipe of the [Arm Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/latest)

This section of the repository contains the build scripts and the live-images for the SystemReady IR Band.

## Release details
 - Code Quality: IR ACS v2.1.0
 - The latest pre-built release of IR ACS is available for download here: [v23.09_2.1.0](https://github.com/ARM-software/arm-systemready/tree/main/IR/prebuilt_images/v23.09_2.1.0)
 - The BSA tests are written for version 1.0 of the BSA specification.
 - The BBR tests are written for EBBR section of version 2.0 of the BBR specification.
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
 - Ubuntu 18.04 or later LTS with at least 32GB of free disk space.
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
This image comprises of 2 FAT file system partition recognized by UEFI: <br />
- '/' <br />
  Root partition for Linux which contains test-suites to run in Linux environment. <br/>
- 'BOOT_ACS' <br />
  Approximate size: 150 MB <br />
  contains bootable applications and test suites. <br />
  contains a 'acs_results' directory which stores logs of the automated execution of ACS.

## Verification

Note: The default UEFI EDK2 setting for "Console Preference" is "Graphical". In this default setting, the Linux output goes only to the graphical console (HDMI monitor). To force serial console output, you may change "Console Preference" to "Serial".

### Verification of the IR image on QEMU Arm machine

#### Building the firmware and QEMU

The U-Boot firmware and QEMU can be built with
[Buildroot](https://buildroot.org/).

To download and build the firmware code, do the following:

```
git clone https://git.buildroot.net/buildroot -b 2023.05.x
cd buildroot
make qemu_aarch64_ebbr_defconfig
make
```

When the build completes, it generates the firmware file
`output/images/flash.bin`, comprising TF-A, OP-TEE and the U-Boot bootloader. A
QEMU executable is also generated at `output/host/bin/qemu-system-aarch64`.

Specific information for this Buildroot configuration is available in the file
`board/qemu/aarch64-ebbr/readme.txt`.

More information on Buildroot is available in [The Buildroot user
manual](https://buildroot.org/downloads/manual/manual.html).

#### Verifying the ACS-IR pre-built image

Launch the model using the following command:

```
./output/host/bin/qemu-system-aarch64 \
    -bios output/images/flash.bin \
    -cpu cortex-a53 \
    -d unimp \
    -device virtio-blk-device,drive=hd1 \
    -device virtio-blk-device,drive=hd0 \
    -device virtio-net-device,netdev=eth0 \
    -device virtio-rng-device,rng=rng0 \
    -drive file=<path-to/ir-acs-live-image-generic-arm64.wic>,if=none,format=raw,id=hd0 \
    -drive file=output/images/disk.img,if=none,id=hd1 \
    -m 1024 \
    -machine virt,secure=on \
    -monitor null \
    -netdev user,id=eth0 \
    -no-acpi \
    -nodefaults \
    -nographic \
    -object rng-random,filename=/dev/urandom,id=rng0 \
    -rtc base=utc,clock=host \
    -serial stdio \
    -smp 2
```

Note:
When verifiying ACS on hardware, ensure that ACS image is not in two different boot medias (USB, NVMe drives etc) attached to the device.

### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can be run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.
2. [UEFI Shell application](https://github.com/ARM-software/bsa-acs/blob/main/README.md) for BSA compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/main/README.md) for BBR compliance.

### Running Security interface extension (SIE) ACS.

For the verification steps of SIE ACS, refer to the [SIE ACS Verification](../../common/docs/SIE_ACS_Verification.md).

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: v23.07.00

- [Base System Architecture (BSA)](https://github.com/ARM-software/bsa-acs) TAG: v23.09_REL1.0.6

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: v23.09_SR_REL2.0.0_ES_REL1.3.0_IR_REL2.1.0

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 315e3a56a6d9261d4fad4c1950f2d01a052eeba4



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

