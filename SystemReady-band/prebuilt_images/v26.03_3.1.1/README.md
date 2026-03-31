# SystemReady Band v3.1.1 Pre-built Image

The **SystemReady Band v3.1.1** release pre-built image is available for download at:

🔗 [Download systemready_acs_live_image.img.xz.zip](https://github.com/ARM-software/arm-systemready/releases/download/v26.03_SR_3.1.1/systemready_acs_live_image.img.xz.zip)

Follow the steps below to decompress the pre-built image:

```bash
unzip systemready_acs_live_image.img.xz.zip
xz -d systemready_acs_live_image.img.xz
```

After decompression, you will get the .img file, which can be used directly with your target environment.

---

## Prerequisites

### OS Installation and Boot Logs

Arm SystemReady band v3.1.1 requires that OS installation and boot logs are used to check for overall compliance:

- Installation and boot logs from RHEL and SLES LTS releases are required.

To get the logs run the [linux-distro-cmds.sh](https://gitlab.arm.com/systemready/systemready-band-template/-/blob/main/os-logs/linux-distro-cmds.sh?ref_type=heads) script and copy RHEL and SLES logs into acs image root folder. Within acs image root folder, create os-logs then copy those RHEL and SLES logs into that folder

The ACS image root folder structure is as follows:

```
├── EFI
├── acs_tests
├── acs_results
├── os-logs
├── Image
└── ramdisk-buildroot.img
```

### SBMR Execution Mode

SBMR in-band tests are run as part of SystemReady ACS automation. The out-of-band SBMR tests need to be executed from outside the DUT, using an external host machine, to exercise the server system's out-of-band capabilities.

Please refer to the [SBMR ACS README.md](https://github.com/ARM-software/sbmr-acs/blob/main/README.md) for steps to run the tests.

After a successful run, the suite generates a `logs` folder containing run metadata and results in an XML file. This folder must be renamed to `sbmr_out_of_band_logs` and copied to the `acs_results\sbmr\` path in the ACS image, so that the log parser scripts can collate the results and provide an overall SBMR compliance report for the DUT.
