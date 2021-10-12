# Arm SystemReady ACS

## Introduction to Arm SystemReady
Systems that are designed to just work for the end user with the ability to install and run generic, off-the-shelf operating systems out of the box, must follow a set of minimum hardware and firmware requirements.

For the Arm ecosystem, this requirement first surfaced in the server segment. The Arm ServerReady compliance certification program provides this “just works” solution for servers, allowing you to deploy Arm servers with confidence. The program is based on industry standards and is accompanied by a compliance test suite, and a process for certification.

The Arm SystemReady program is a natural extension of the Arm ServerReady program. Different market segments may target different sets of operating systems and hypervisors with different hardware and firmware requirements. We use the term band to identify these differences, with a shorthand notation for each band. The bands are:
* [SystemReady SR](https://developer.arm.com/architectures/system-architectures/arm-systemready/sr)
* [SystemReady LS](https://developer.arm.com/architectures/system-architectures/arm-systemready/ls)
* [SystemReady ES](https://developer.arm.com/architectures/system-architectures/arm-systemready/es)
* [SystemReady IR](https://developer.arm.com/architectures/system-architectures/arm-systemready/ir)

For more information, visit: [Arm SystemReady](https://developer.arm.com/architectures/system-architectures/arm-systemready)

This repository contains the infrastructure to build the Architecture Compliance Suite and the bootable prebuilt images to be used for the certifications of various bands of SystemReady.
Note:  Currently SystemReady ES and IR bands are supported in this repository

For SystemReady SR, refer to the [Arm Enterprise ACS repository](https://github.com/ARM-software/arm-enterprise-acs)

## System Ready bands:
Navigate to the ES or IR band for further details on specific scripts and prebuilt images, through the directories below:
* [ES](./ES)
* [IR](./IR)

## System Ready Security Interface Extension:
The SystemReady Security Interface Extension provides a way to certify that secure boot and secure firmware update are implemented as prescribed by the Arm [Base Boot Security Specification](https://developer.arm.com/documentation/den0107/latest) (BBSR). The Security Interface Extension can be followed with the SystemReady SR, ES, and IR bands.
Please navigate to the Security Interface Extension link below for further details on specific scripts and prebuilt images:
* [security-interface-extension](./security-interface-extension)

## License

Arm SystemReady ACS is distributed under Apache v2.0 License.

## Feedback, contributions, and support

 - For feedback, use the GitHub Issue Tracker that is associated with this repository.
 - For support, send an email to "support-systemready-acs@arm.com" with details.
 - Arm licensees can contact Arm directly through their partner managers.
 - Arm welcomes code contributions through GitHub pull requests.

--------------

*Copyright (c) 2021, Arm Limited and Contributors. All rights reserved.*

