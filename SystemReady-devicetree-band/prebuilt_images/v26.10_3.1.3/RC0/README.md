## Changes

* Component Upgrade
  * Upgraded DT Yocto/Linux stack and DT bindings, including Linux 7.2.x support and Linux 7.2 BSA driver API compatibility.
  * Updated DT BSA and PFDI version patches for latest upstream sysarch changes.
  * Updated FWTS 26.01.00 recipe download source to GitHub FWTS repo.

* Test Suites changes
  * Added Devicetree reserved-memory memory-map compliance checker.
  * Added DTB 8-byte alignment compliance test.
  * Added deprecated spin-table CPU enable-method detection.
  * Added DT kselftest ignore list and additional platform driver coverage.
  * Restored SBBR runtime services tests in the DT EBBR SCT flow.
  * Applied EBBR 2.3 SCT patch and switched to EfiEbbrProfileTableTest.
  * Added UefiDump recipe and integrated EBBR profile dumping/validation.
  * Added PSCI version reporting in DT system information.
  * Collected dmidecode earlier for DT BBSR/SCMI parsing.
  * Enforced stricter ESP detection in DT HTTPS/network boot flow.

* Platform Support
  * Enabled Qualcomm platform support updates, including SM8750 basics and QCS615 clock/interconnect/pinctrl drivers.
  * Included linux-firmware in the Woden image and added X1E80100 firmware support.

* Others
  * Added dosfstools to the Woden image.
  * Enabled additional GRUB console commands for DT.
  * Fixed ledge-efi DT build reliability by forcing serial build.
  * Refreshed DT Yocto ACS recipe metadata against current upstream sources.

## Known Limitations / Issues
- None
