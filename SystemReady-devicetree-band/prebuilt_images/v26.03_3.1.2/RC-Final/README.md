## Changes

 -- On top of RC0

* BBSR SCT test "Secure Boot - ImageLoading Test" will be reported as KNOWN U-BOOT LIMITATION 
* BBSR SCT test "MemoryOverWriteRequestControl" will be reported as WARNING
* QCOM clock controller, interconect and pinctrl configs enabled in systemready.cfg
* New Standalone test -- runtime device mapping conflict test added as recommended test based on EBBR requirement
* capsule update ondisk variable check added as new subtest in capsule update test
* xBSA logs copy time improved by directly using uefi cp cmd in place of type


## Known Limitations / Issues

 - None
