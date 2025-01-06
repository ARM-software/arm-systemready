# Modifying acs_run_config.ini to enable/disable various ACS test suites.

## Table of Contents

- [Modify before the build](#modify-before-the-build)

- [Modify before ACS run after build](#modify-before-acs-run-after-the-build)

- [Modify during the ACS run](#modify-during-the-acs-run)

---

## Modify before the build.

- To modify the acs_run_config.ini before building.

- Goto systemready repo /common/config.

- Edit acs_run_config.ini file to enable or disable the testsuits.

---

## Modify before ACS run after the build

- One can use kpartx to modify acs_run_config.ini before the acs run.

- Use the following commands

- "sudo kpartx -a -v <image-path>"
- "sudo mount /dev/mapper/<created-loop> /<mount-point>"
- "cd /<mount-point>/"   "sudo vi acs_run_config.ini"  (edit acs_run_config.ini).
- "sudo umount /<mount-point>"
- "sudo kpartx -d -v <image-path>"

---

## Modify during the ACS run

- Boot into ACS image go to UEFI shell (choose "SystemReady band ACS (Automation)"  in grub and press escape to enter uefi shell).

- Enter the path where ACS image is booted (eg: FS0://).

- In uefi shell one can use edit command to edit the text file("edit acs_run_config.ini") press CTRL+s to save and ctrl+q to quit the editor.

- To enable SBSA change the value of "SbsaRunEnabled = 1" save the file and rerun the ACS image.

---
