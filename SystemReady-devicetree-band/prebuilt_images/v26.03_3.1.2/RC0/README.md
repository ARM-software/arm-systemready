## Changes

* Component Upgrade
  * ACS Linux kernel updated to `v6.18` (prev v6.16)
  * FWTS updated to `2026.01` (prev 2025.09)
  * SCT updated to `Jan26 31st commit` (prev: edk2-test-stable202509)
  * DT-validate bindings source moved to v6.18 (prev: v6.16)

* Test Suites changes
  * SCMI test suite (**optional**) is new suite added, which can be run using seperate GRUB menu option
  * EfiConformanceTable test for ebbr profiles added as part of SCT test
  * BSA and PFDI ACS test suite log refactored, no changes in JSON results
  * FWTS SMCCC tests (**recommended**) are enabled
  * Network boot size reduced and now directly hosted on github
  * PFDI, BSA moved to latest sysarch-acs source
  * Checks related to CapsuleNNN, CapsuleMax, CapsuleLast variables added. ** Currenly the test parsing is not enabled, as acs plans to observe results of various platforms**
     * The logs are part of fw/capsule_test_results.log
  * Python based test added for EBBR RuntimeDeviceMappingConflict requirement. ** Currenly the test parsing is not enabled, as acs plans to observe results of various platforms**
     * The logs are part of acs_results/linux_tool/runtime_device_mapping_conflict_test

* Others
  * ACS results/test partition size increase to 512 MB to accomodate large size capsule update binaries

## Known Limitations / Issues
