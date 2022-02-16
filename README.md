# Arm SystemReady ACS

## Introduction to Arm SystemReady
Systems that are designed to just work for the end user with the ability to install and run generic, off-the-shelf operating systems out of the box, must follow a set of minimum hardware and firmware requirements.

For the Arm ecosystem, this requirement first surfaced in the server segment. The Arm ServerReady compliance certification program provides this 'just works' solution for servers, allowing you to deploy Arm servers with confidence. The program is based on industry standards and is accompanied by a compliance test suite, and a process for certification.

The Arm SystemReady program is a natural extension of the Arm ServerReady program. Different market segments may target different sets of operating systems and hypervisors with different hardware and firmware requirements. We use the term band to identify these differences, with a shorthand notation for each band. The bands are:
* [SystemReady SR](https://developer.arm.com/architectures/system-architectures/arm-systemready/sr)
* [SystemReady LS](https://developer.arm.com/architectures/system-architectures/arm-systemready/ls)
* [SystemReady ES](https://developer.arm.com/architectures/system-architectures/arm-systemready/es)
* [SystemReady IR](https://developer.arm.com/architectures/system-architectures/arm-systemready/ir)

For more information, visit: [Arm SystemReady](https://developer.arm.com/architectures/system-architectures/arm-systemready)

This repository contains the infrastructure to build the Architecture Compliance Suite (ACS) and the bootable prebuilt images to be used for the certifications of various bands of SystemReady.<br />
Note:  Currently SystemReady ES, IR and SR  bands are supported in this repository

For the legacy SystemReady SR ACS, refer to the [Arm Enterprise ACS repository](https://github.com/ARM-software/arm-enterprise-acs)

## SystemReady bands:
Navigate to the ES, IR, or SR band for further details on specific scripts and prebuilt images through the directories below:
* [ES](./ES)
* [IR](./IR)
* [SR](./SR)

## SystemReady Security Interface Extension:
The SystemReady Security Interface Extension certifies that firmware meets the requirements specified by the Arm [Base Boot Security Requirements specification](https://developer.arm.com/documentation/den0107/latest) (BBSR). The Security Interface Extension is optionally applicable to SystemReady SR, ES and IR bands, but not the LS band.
Further details on Security Interface Extension, including pre-built images, are here:
* [Security Interface Extension](https://github.com/ARM-software/arm-systemready/tree/security-interface-extension-acs/security-interface-extension)

## Limitations

### BSA
Validating the compliance of certain PCIe rules defined in the BSA specification require the PCIe end-point generate specific stimulus during the runtime of the test. Examples of such stimulus are  P2P, PASID, ATC, etc. The tests that requires these stimuli are grouped together in the exerciser module. The exerciser layer is an abstraction layer that enables the integration of hardware capable of generating such stimuli to the test framework.
The details of the hardware or Verification IP which enable these exerciser tests platform specific and are beyond the scope of this document.

The Live image does not allow customizations, hence, the exerciser module is not included in the Live image. To enable exerciser tests for greater coverage of PCIe rules, please refer to [BSA](https://github.com/ARM-software/bsa-acs) Or contact your Arm representative for details.

### SBSA
Validating the compliance of certain PCIe rules defined in the SBSA specification requires the PCIe end-point to generate specific stimulus during the runtime of the test. Examples of such stimulus are  P2P, PASID, ATC, etc. The tests that requires these stimuli are grouped together in the exerciser module. The exerciser layer is an abstraction layer that enables the integration of hardware capable of generating such stimuli to the test framework.
The details of the hardware or Verification IP which enable these exerciser tests are platform specific and are beyond the scope of this document.

 - Some PCIe and Exerciser test are dependent on PCIe features supported by the test system.
   Please fill the required API's with test system information.

|APIs                         |Description                                                                   |Affected tests          |
|-----------------------------|------------------------------------------------------------------------------|------------------------|
|pal_pcie_p2p_support         |Return 0 if the test system PCIe supports peer to peer transaction, else 1    |453, 454, 456, 812, 813 |
|pal_pcie_is_cache_present    |Return 1 if the test system supports PCIe address translation cache, else 0   |452                     |
|pal_pcie_get_legacy_irq_map  |Return 0 if system legacy irq map is filled, else 1                           |412, 450, 806           |

   Below exerciser capabilities are required by exerciser test.
   - MSI-X interrupt generation.
   - Incoming Transaction Monitoring(order, type).
   - Initiating transacions from and to the exerciser.
   - Ability to check on BDF and register address seen for each configuration address along with access type.

 - SBSA Test 403 (Check ECAM Memory accessibility) execution time depends on the system PCIe hierarchy. For systems with multiple ECAMs the time taken to complete can be long which is normal. Please wait until the test completes.

## License

Arm SystemReady ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2021-2022, Arm Limited and Contributors. All rights reserved.*

