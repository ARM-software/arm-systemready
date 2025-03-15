## Table of Contents

- [Introduction](#introduction)
- [SystemReady Band](#systemready-band)
- [DeviceTree Band](#devicetree-band)
- [Important Notes](#important-notes)

---

## Introduction

This guide provides a comprehensive overview of the test suite components included in the Verification Image for DeviceTree and SystemReady band images. It details the various test tools that are part of the verification process, specifying whether they are executed automatically or require manual execution. Additionally, the guide captures the locations where the logs for each test tool are stored, ensuring easy access for review and debugging.
By following this guide, users can gain a clear understanding of the verification framework, enabling efficient test execution and result analysis to validate compliance with the required specifications.

---

## SystemReady Band


| Test Suites      | Run Enviroment  | Execution                    | Results Path              |
|------------------|-----------------|------------------------------|---------------------------|
| BSA              | UEFI and Linux# | Automatic                    | acs_results/uefi/BsaResults.log  acs_results/linux_acs/BsaResultsKernel.log     |
| SBSA             | UEFI and Linux# | Automatic (Conditional)*     | acs_results/uefi/SbsaResults.log  acs_results/linux_acs/SbsaResultsKernel.log        |
| SCT              | UEFI            | Automatic                    | acs_results/sct_results/Overall/Summary.log       |
| SCRT             | UEFI            | Automatic                    | `/path/to/results3`       |
| FWTS             | Linux           | Automatic                    | acs_results/fwts/FWTSResults.log       |
| BBSR-SCT         | UEFI            | Manual**                     | acs_results/BBSR/sct_results/Overall/Summary.log       |
| BBSR-FWTS        | Linux           | Manual**                     | acs_results/BBSR/fwts/FWTSResults.log       |

 - UEFI and Linux#: Complete coverage of BSA and SBSA test suite requires run of both the UEFI application of Linux application

 - Automatic (Conditional)*: SBSA run is optional for SR band and can be control using the acs run config file. Please refer this guide for more details.

 - Manual**: The BBSR extension complaince is optional, and the run is controlled using the **"BBSR Complaince (Automation)"** grub menu

---

## DeviceTree Band

| Test Suites      | Run Enviroment  | Execution                    | Results Path              |
|------------------|-----------------|------------------------------|---------------------------|
| BSA              | UEFI and Linux# | Automatic                    | acs_results_template/acs_results/uefi/BsaResults.log  acs_results_template/acs_results/linux_acs/bsa_acs_app/BsaResultsKernel.log     |
| SCT              | UEFI            | Automatic                    | acs_results_template/acs_results/sct_results/Overall/Summary.log       |
| SCRT             | UEFI            | Automatic                    | `/path/to/results3`       |
| FWTS             | Linux           | Automatic                    | acs_results_template/acs_results/fwts/FWTSResults.log       |
| BBSR-SCT         | UEFI            | Manual**                     | acs_results_template/acs_results/BBSR/sct_results/Overall/Summary.log       |
| BBSR-FWTS        | Linux           | Manual**                     | acs_results_template/acs_results/BBSR/fwts/FWTSResults.log       |
| Capsule Update   | UEFI            | Automatic                    | acs_results_template/fw/capsule-update.log acs_results_template/fw/capsule-on-disk.log acs_results_template/acs_results/app_output/capsule_test_results.log       |
| DT validate      | Linux           | Automatic                    | acs_results_template/acs_results/linux_tools/dt-validate.log      |
| Block Device test| Linux           | Automatic                    | acs_results_template/acs_results/linux_tools/read_write_check_blk_devices.log     |
| Ethtool          | Linux           | Automatic                    | acs_results_template/acs_results/linux_tools/ethtool-test.log     |
| DT Kernel kselftest  Linux         | Automatic                    | acs_results_template/acs_results/linux_tools/dt_kselftest.log     |

 - UEFI and Linux#: Complete coverage of BSA and SBSA test suite requires run of both the UEFI application of Linux application

 - Manual**: The BBSR extension complaince is optional, and the run is controlled using the **"BBSR Complaince (Automation)"** grub menu

---
