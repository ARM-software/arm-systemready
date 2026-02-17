## Changes

* Component Upgrade
  * ACS Linux kernel updated to `v6.18` (prev v6.16)
  * FWTS updated to `2026.01` (prev 2025.09)
  * SCT updated to `Jan26 31st commit` (prev: edk2-test-stable202509)
  * DT-validate bindings source moved to v6.18 (prev: v6.16)

* Test Suites changes
  * SCMI test suite (**optional**) is new suite added, which can be run using seperate GRUB menu option
  * EfiConformanceTable for ebbr profiles added as part of SCT test
  * BSA and PFDI ACS test suite log refactored, no changes in JSON results
  * FWTS SMCCC tests (**recommended**) are enabled

## Known Limitations / Issues
