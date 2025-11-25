## Changes

* ACS Linux kernel updated to `v6.16` (prev v6.12)
* FWTS updated to `2025.09` (prev 2025.02)
* SCT updated to `edk2-test-stable202509` (prev: July-end)
* DT-validate bindings source moved to v6.16 (prev: v6.12)
* ethtool test enhancements
  * `curl` and `wget` checks relaxed to **PASS** if either command is available and succeeds
  * If `ethtool` is not available, fallback to `/sys/class/net/{iface}/carrier` to detect an active link
  * Ping check relaxed to **WARNING**
* `systemready-commit.log` added to `acs_results_template/acs_results/acs_summary/config/`, which captures individual ACS build source details
* DT-validate parser logic updated to account for empty dt-validate logs (handles no-warnings/no-errors case)
* SystemReady script invocation updated to work with pre-existing kernel bindings, saving download time and working offline (no network)
* `merged_results.json` keys sorted in alphabetical order
* New standalone **recommended** test: SMBIOS check added to verify presence of the SMBIOS3 table
* v6.18 kernel fix patch applied for `ethtool` crash

## Known Limitations / Issues

- SCT compliance can fail if the SCT SMBIOS test fails
  - This will be addressed in the next RC image.

- With the FWTS upgrade, new tests related to SMCCC are added, which also include some PCI tests.
  - PCI test reporting is under discussion and will be fixed in the next RC image.

- With the SCT upgrade, RT Properties Table tests are added. The test *“UEFI Compliant - EFI Runtime Properties Table RuntimeServicesSupported field matches the expected value”* failure is suspected to be a test issue.
  - Investigation is ongoing.
