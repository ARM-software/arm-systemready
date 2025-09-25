# Arm SystemReady ACS

## Introduction to Arm SystemReady
Systems that are designed to just work for the end user with the ability to install and run generic, off-the-shelf operating systems out of the box, must follow a set of minimum hardware and firmware requirements.


For the Arm ecosystem, this requirement first surfaced in the server segment. The Arm ServerReady compliance program provides this 'just works' solution for servers, allowing you to deploy Arm servers with confidence. The program is based on industry standards and is accompanied by a compliance test suite, and a process for compliance.

The Arm SystemReady program is a natural extension of the Arm ServerReady program. Different market segments may target different sets of operating systems and hypervisors with different hardware and firmware requirements. We use the term band to identify these differences. The bands are:
* [SystemReady-band](https://www.arm.com/architecture/system-architectures/systemready-compliance-program/systemready-band)
* [SystemReady-devicetree-band](https://www.arm.com/architecture/system-architectures/systemready-compliance-program/systemready-devicetree-band)

For more information on the Arm SystemReady Compliance Program, visit: [Arm SystemReady](https://www.arm.com/architecture/system-architectures/systemready-compliance-program)

This repository contains the infrastructure to build the Arm SystemReady Architecture Compliance Suite (ACS) and the bootable prebuilt images to be used for the compliance of various bands of SystemReady.<br />


## SystemReady bands:
Navigate to the SystemReady-devicetree band, or SystemReady band for further details on specific scripts and prebuilt images through the directories below:
* [SystemReady-devicetree-band](./SystemReady-devicetree-band/)
* [SystemReady-band](./SystemReady-band)

## Legacy Repository

> ⚠️ **Note:** This project has a legacy version that is no longer actively maintained but may still be useful for historical reference or backward compatibility.

You can find the legacy repository here:  
🔗 [**Legacy_systemready**](https://github.com/ARM-software/arm-systemready/tree/legacy_systemready)

## SystemReady BBSR:
The SystemReady BBSR tests if the firmware meets the requirements specified by the Arm [Base Boot Security Requirements specification](https://developer.arm.com/documentation/den0107/latest) (BBSR). BBSR ACS is integrated in SystemReady band and SystemReady-devicetree band ACS prebuilt images.

For further details on BBSR ACS, please refer to [BBSR ACS Verification Guide](./docs/BBSR_ACS_Verification.md).

## Limitations

### BSA
Validating the compliance of certain PCIe rules defined in the BSA specification require the PCIe end-point generate specific stimulus during the runtime of the test. Examples of such stimulus are  P2P, PASID, ATC, etc. The tests that requires these stimuli are grouped together in the exerciser module. The exerciser layer is an abstraction layer that enables the integration of hardware capable of generating such stimuli to the test framework.
The details of the hardware or Verification IP which enable these exerciser tests platform specific and are beyond the scope of this document.

The ACS image does not allow customizations, hence, the exerciser module is not included in the ACS image. To enable exerciser tests for greater coverage of PCIe rules, please refer to [BSA](https://github.com/ARM-software/bsa-acs) Or contact your Arm representative for details.

### SBSA
Validating the compliance of certain PCIe rules defined in the SBSA specification requires the PCIe end-point to generate specific stimulus during the runtime of the test. Examples of such stimulus are  P2P, PASID, ATC, etc. The tests that requires these stimuli are grouped together in the exerciser module. The exerciser layer is an abstraction layer that enables the integration of hardware capable of generating such stimuli to the test framework.
The details of the hardware or Verification IP which enable these exerciser tests are platform specific and are beyond the scope of this document.

 - Some PCIe and Exerciser test are dependent on PCIe features supported by the test system.
   Please fill the required API's with test system information.

|APIs                         |Description                                                                   |Affected tests          |
|-----------------------------|------------------------------------------------------------------------------|------------------------|
|pal_pcie_dev_p2p_support     |Return 0 if the test system PCIe supports peer to peer transaction, else 1    |856, 857                |
|pal_pcie_is_cache_present    |Return 1 if the test system supports PCIe address translation cache, else 0   |852                     |
|pal_pcie_get_legacy_irq_map  |Return 0 if system legacy irq map is filled, else 1                           |850                     |

   Below exerciser capabilities are required by exerciser test.
   - MSI-X interrupt generation.
   - Incoming Transaction Monitoring(order, type).
   - Initiating transactions from and to the exerciser.
   - Ability to check on BDF and register address seen for each configuration address along with access type.

 - SBSA Test 803 (Check ECAM Memory accessibility) execution time depends on the system PCIe hierarchy. For systems with multiple ECAMs the time taken to complete can be long which is normal. Please wait until the test completes.

## License

Arm SystemReady ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2021-2024, Arm Limited and Contributors. All rights reserved.*


