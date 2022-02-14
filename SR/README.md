# SystemReady SR ACS


## Introduction to SystemReady SR
SystemReady SR is a band of system certification in the Arm SystemReady program that ensures interoperability of Arm based servers with standard operating systems and hypervisors.

SystemReady SR-certified platforms implement a minimum set of hardware and firmware features that an operating system can depend on to deploy the operating system image. Compliant systems must conform to the:
* [Server Base System Architecture (SBSA) specification](https://developer.arm.com/documentation/den0029/d/?lang=en)
* SBBR recipe of the [Base Boot Requirements (BBR) specification](https://developer.arm.com/documentation/den0044/latest)
* The SystemReady SR certification and testing requirements are specified in the [Arm SystemReady Requirements Specification (SRS)](https://developer.arm.com/documentation/den0109/latest)

This section contains the build scripts and the live-images for the SystemReady SR band.

**The collection of code and scripts under [arm-systemready/SR](https://github.com/ARM-software/arm-systemready/tree/main/SR) is an enhanced replacement of the [Arm Enterprise ACS](https://github.com/ARM-software/arm-enterprise-acs) repository**

## Release details
 - Code quality: v1.0
 - **The latest pre-built release of ACS is available for download here: [v22.02_1.0](prebuilt_images/v22.02_1.0)**
 - The SBSA tests are written for version 6.0 of the SBSA specification.
 - The BBR tests are written for the SBBR section in version 1.0 of the BBR specification.
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.


## Steps to build SystemReady SR ACS live image

## Code download
- To build a release version of the code, checkout the main branch with the appropriate release tag.
- To build the latest version of the code with bug fixes and new features, use the main branch.

## ACS build steps

### Prebuilt images
- Prebuilt images for each release are available in the prebuilt_images folder. You can either choose to use these images or build your own image by following the build steps.
- To access the prebuilt_images, click [prebuilt_images](prebuilt_images/)
- If you choose to use the prebuilt image, skip the build steps and navigate to the [Verification](#Verification) section below.

### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 18.04 or 20.04 LTS with at least 32GB of free disk space.
 - Use bash shell.
 - You must have **sudo** privilege to install tools required for build.
 - Install `git` using `sudo apt install git`
 - `git config --global user.name "Your Name"` and `git config --global user.email "Your Email"` must be configured.

### Steps to build SystemReady SR ACS live image
1. Clone the arm-systemready repository <br />
 `git clone https://github.com/ARM-software/arm-systemready.git`

2. Navigate to the SR/scripts directory <br />
 `cd arm-systemready/SR/scripts`

3. Run get_source.sh to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the SR ACS live image, execute the below step <br />
 `./build-scripts/build-sr-live-image.sh`

5. If all the above steps are successful, then the  bootable image will be available at **/path-to-arm-systemready/SR/scripts/output/sr_acs_live_image.img.xz**

Note: The image is generated in a compressed (.xz) format. The image must be uncompressed before it is used.<br />

## Build output
This image comprises two FAT file system partitions recognized by UEFI: <br />
- 'acs-results' <br />
  stores logs of the automated execution of ACS. (Approximate size: 120MB) <br/>
- 'boot' <br />
  contains bootable applications and test suites. (Approximate size: 400MB)


## Verification

Note: UEFI EDK2 setting for "Console Preference": The default is "Graphical". When that is selected, Linux output will goes to the graphical console (HDMI monitor). To force serial console output, you may change the "Console Preference" to "Serial".

### Verification of the SR image on the Arm Neoverse N2 reference design (RD-N2)

#### Prerequisites
sudo permission is required for  building RD-N2 software stack.

#### Follow the steps mentioned in [RD-N2 platform software user guide](https://gitlab.arm.com/arm-reference-solutions/arm-reference-solutions-docs/-/tree/master/docs/infra/rdn2) to obtain RD-N2 FVP.

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
./run_model.sh -v /path-to-sr-acs-live-image/sr_acs_live_image.img
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


### Automation
The test suite execution can be automated or manual. Automated execution is the default execution method when no key is pressed during boot. <br />
The live image boots to UEFI Shell. The different test applications can run in the following order:

1. [SCT tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.
2. [UEFI Shell application](https://github.com/ARM-software/sbsa-acs/blob/master/README.md) for SBSA compliance.
3. [FWTS tests](https://github.com/ARM-software/bbr-acs/blob/master/README.md) for BBR compliance.
4. [OS tests](https://github.com/ARM-software/sbsa-acs/blob/master/README.md) for Linux SBSA compliance.

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS)](http://kernel.ubuntu.com/git/hwe/fwts.git) TAG: 1228f0412a6c76b437cfa3078d5dc1fb5ca102c6

- [Base System Architecture (SBSA)](https://github.com/ARM-software/sbsa-acs) TAG: v22.02_SR_REL1.0

- [Base Boot Requirements (BBR)](https://github.com/ARM-software/bbr-acs) TAG: v22.02_SR_REL1.0

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 01d9d24efdedb30ff6b0e1f1c47c6c3b0c5a7093



## Security Implication
Arm SystemReady SR ACS test suite may run at higher privilege level. An attacker may utilize these tests as a means to elevate privilege which can potentially reveal the platform security assets. To prevent the leakage of Secure information, it is strongly recommended that the ACS test suite is run only on development platforms. If it is run on production systems, the system should be scrubbed after running the test suite.

## License
SystemReady ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to support-systemready-acs@arm.com with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2022, Arm Limited and Contributors. All rights reserved.*

