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

## License

Arm SystemReady ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2021-2024, Arm Limited and Contributors. All rights reserved.*


