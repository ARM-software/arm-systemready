## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Automatic Capsule update flow](#flow)


## Introduction

Capsule update is the standard interface to update the firmware. The SystemReady devicetree ACS image provides automatic capsule update testing as part of ACS automation run.

## Prerequisites
1. Copy the platform’s three capsule files (unauth.bin, tampered.bin and signed_capsule.bin) which were generated using Generate capsule steps
  mentioned in the IR guide into the BOOT partition /acs_tests/app/ path of the ACS image on a storage drive.

2. Boot the ACS image on the platform with the new.dtb file which was generated in Generate
  capsule files.

## Automatic Capsule update flow
1. Select bbr/bsa from the GRUB boot menu and press Enter. This is the default selection and will run automatically if no other option is chosen.

2. First, the UEFI-based tests, including SCT, BSA, and the Ethernet port test, will run. After these tests complete, ACS will automatically boot to Linux.

3. In Linux, the FWTS, BSA, and MVP tests will be executed. The image will automatically detect if a capsule update test is required and will reboot to perform the testing.

4. After rebooting to the UEFI shell, SCT and BSA tests will be skipped, as they were already completed in the first run.

5. User input will be requested to proceed with the capsule update, with a 10-second timeout.

6. If the user presses any key within 10 seconds, `capsule.efi` will perform the on-disk capsule update test. If the user does not press any key and ACS determines that capsule testing is needed,
    it will proceed with the test. However, a prompt will be provided, allowing the user to skip the capsule update test if desired.

7. Before firmware update, script captures ESRT and SMBIOS tables for firmware update versions into \acs_results\app_output path.

8. As part of firmware update, first the update with unauth.bin and tampered.bin will be done, then update with signed_capsule.bin will be performed.
    > FS0:\acs_tests\app\CapsuleApp.efi   FS0:\acs_tests\app\unauth.bin
    
    > FS0:\acs_tests\app\CapsuleApp.efi   FS0:\acs_tests\app\tampered.bin
    
    > FS0:\acs_tests\app\CapsuleApp.efi   FS0:\acs_tests\app\ signed_capsule.bin -OD

9. If the update with `signed_capsule.bin` is successful, the system will automatically reset for the firmware update. In case of failure, ACS will boot to Linux with a failure acknowledgment.

10. On reboot after firmware update, script captures ESRT and SMBIOS tables for firmware update versions into \acs_results\app_output path and then it boots to Linux with success acknowledgement.

11. In Linux, a message will be logged indicating whether the capsule update was successful or not, based on the uefi capsule update status.
