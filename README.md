# Arm SystemReady ACS
  
## Arm SystemReady Introduction
Systems that are designed to just work for the end user – with the ability to install and run generic, off-the-shelf operating systems out of the box – must follow a set of minimum hardware and firmware requirements.

For the Arm ecosystem, this requirement first surfaced in the server segment. The Arm ServerReady compliance certification program provides this “just works” solution for servers, allowing partners to deploy Arm servers with confidence. The program is based on industry standards and is accompanied by a compliance test suite, and a process for certification.

The Arm SystemReady program is a natural extension of the Arm ServerReady program. Different market segments may target different sets of operating systems and hypervisors with different hardware and firmware requirements. We use the term band to identify these differences, with a shorthand notation for each band. The bands are:
* [SystemReady SR](https://developer.arm.com/architectures/system-architectures/arm-systemready/sr)
* [SystemReady LS](https://developer.arm.com/architectures/system-architectures/arm-systemready/ls)
* [SystemReady ES](https://developer.arm.com/architectures/system-architectures/arm-systemready/es)
* [SystemReady IR](https://developer.arm.com/architectures/system-architectures/arm-systemready/es)

For more informaton, please visit: [Arm SystemReady](https://developer.arm.com/architectures/system-architectures/arm-systemready)

This repository contains the infrastructure to build the Architecture Compliance Suite and the bootable prebuilt images to be used for the certifications of various bands of SystemReady.
Note:  Currently SystemReady ES and IR bands are supported in this repository

For SystemReady SR, please refer to the [Arm Enterprise ACS repository](https://github.com/ARM-software/arm-enterprise-acs)

## ACS Infrastructure and Prebuilt Images
Please navigate to the ES or IR band, specific scripts and prebuilt images, through the directories below:
* [ES](https://github.com/ARM-software/arm-systemready/tree/main/ES)
* [IR](https://github.com/ARM-software/arm-systemready/tree/main/IR)

## License

Arm SystemReady ACS is distributed under Apache v2.0 License.

