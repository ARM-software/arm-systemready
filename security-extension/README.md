# SystemReady Security Extension ACS

## Introduction to the SystemReady Security Extension

The SystemReady Security Extension provides a way to certify that Secure Boot and secure firmware update are implemented as prescribed by the Arm [Base Boot Security Specification](https://developer.arm.com/documentation/den0107/latest) (BBSR).  The Security Extension is an extension to the bands of the SystemReady program and a pre-requisite for a Security Extension certification in one of the IR, ES, or LS bands.

The Security Extension ACS tests the following security related interfaces:
* Authenticated variables
* Secure Boot variables
* Secure firmware update using update capsules
* For systems with TPMs, TPM measured boot and the TCG2 protocol

This section describes the steps to build the ACS or obtain the pre-built live image.

## Release details
 - Code Quality: v1.0
 - **The latest pre-built release of the Security Extension ACS is available for download here: [v21.09_SE_REL1.0](./prebuilt_images/v21.09_SE_REL1.0)**
 - The Security Extension tests are written for version 1.1 of the BBSR specification.
 - The compliance suite is not a substitute for design verification.
 - To review the ACS logs, Arm licensees can contact Arm directly through their partner managers.
 - New Features
     - New features in this release include tests for the UEFI Image Information Execution table and TPM-based measured boot.
 - Limitations
     - This release is limited to the security extension ACS tests only.  It is not supported to use this release for SystemReady ES and IR band testing.  See the SystemReady ACS page for links to the latest SystemReady IR and ES tests.


## Steps to build SystemReady Security Extension ACS live image

## GitHub branch
- To pick up the release version of the code, checkout the branch "security-extension-acs".  The release tag is: v21.08_SE_REL1.0_BETA-1

## ACS build steps

### Pre-built images
- Pre-built images for each release are available in the prebuilt_images folder of the release branch. You can either choose to use these images or build your own image by following the steps below.
- To access the prebuilt_images, click this link : [prebuilt_images](./prebuilt_images/v21.09_SE_REL1.0)
- If you choose to use the pre-built image, skip the build steps and jump to the test suite execution section below.

### Prerequisites
Before starting the ACS build, ensure that the following requirements are met:
 - Ubuntu 18.04 LTS with at least 64GB of free disk space.
 - Must use Bash shell.
 - User should have **sudo** privilege to install tools required for build
 - git must be installed in order to clone the ACS repo

### Steps to build SystemReady Security Extension ACS live image
1. Clone the security-extension-acs branch of  [Arm-SystemReady](https://github.com/ARM-software/arm-systemready) repo. <br />
 `git clone -b security-extension-acs https://github.com/ARM-software/arm-systemready`

2. Navigate to the security-extension/scripts directory <br />
 `cd arm-systemready/security-extension/scripts`

3. Run get_source.sh to download all related sources and tools for the build. Provide the sudo permission when prompted <br />
 `./build-scripts/get_source.sh` <br />

4. To start the build of the Security Extension ACS live image, execute the below step <br />
 `./build-scripts/build-security-extension-live-image.sh`

5. If all of above steps are successful, the bootable image will be available at: <br />
 `/[path-to-arm-systemready]/security-extension/scripts/output/se_acs_live_image.img`

## Build output
This image comprises of two FAT file system partitions recognized by UEFI: <br />
- 'acs-results' <br />
  Stores logs and is used to install UEFI-SCT. (Approximate size: 120 MB) <br/>
- 'boot' <br />
  Contains bootable applications and test suites. (Approximate size: 400 MB)

## Running the Security Extension ACS
The test suite consists of both automated and manual tests.  See the [Security Extension ACS Users Guide](./security_extension_users_guide.md) for addition information.

## Baselines for Open Source Software in this release:

- [Firmware Test Suite (FWTS) TAG: V21.02.00](http://kernel.ubuntu.com/git/hwe/fwts.git)

- [UEFI Self Certification Tests (UEFI-SCT)](https://github.com/tianocore/edk2-test) TAG: 421a6997ef362c6286c4ef87d21d5367a9d1fb58


## Security Implications
Arm SystemReady Security Extension ACS test suite may run at a higher privilege level. An attacker may utilize these tests as a means to elevate privilege which can potentially reveal the platform security assets. To prevent the leakage of secure information, it is strongly recommended that the ACS test suite is run only on development platforms. If it is run on production systems, the system should be scrubbed after running the test suite.

## License
System Ready ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, please send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2021, Arm Limited and Contributors. All rights reserved.*
