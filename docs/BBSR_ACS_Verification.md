# Introduction to the SystemReady BBSR (BBSR)

The SystemReady BBSR provides a way to verify that Secure Boot and secure firmware update are implemented as prescribed by the Arm [Base Boot Security Specification](https://developer.arm.com/documentation/den0107/latest) (BBSR).  The BBSR is an extension to the bands of the SystemReady program and a pre-requisite for a BBSR certification in one of the SystemReady-devicetree or SystemReady bands.

The BBSR ACS tests the following security related interfaces:
* Authenticated variables
* Secure Boot variables
* Secure firmware update using update capsules
* For systems with Trusted Platform Modules(TPMs), TPM measured boot and the TCG2 protocol

Note:
1. The Prebuilt band images can be used to verify the requirements of BBSR.
2. See the Section 3.4 [BBSR ACS Users Guide](https://developer.arm.com/documentation/102872/latest) for instructions to enroll the SecureBoot keys.
This document also contains the background information on the BBSR related specification and ACS.

## Prerequisite for running BBSR ACS on QEMU

### Install swtpm package (TPM emulator)
Note: Install only if there is no past installation of swtpm present. Check by running "swtpm -v" in the terminal, which should output the version.

The following commands should fetch and install the swtpm package:

For latest Ubuntu
```
sudo apt install swtpm
```

For Ubuntu 20.04 LTS
```
# Steps to build and install SWTPM manually:

sudo apt-get install git g++ gcc automake autoconf libtool make gcc libc-dev libssl-dev pkg-config libtasn1-6-dev libjson-glib-dev expect gawk socat libseccomp-dev -y
cd ~
git clone https://github.com/stefanberger/swtpm.git
git clone https://github.com/stefanberger/libtpms.git
cd libtpms
./autogen.sh --prefix=/usr --with-tpm2 --with-openssl
make
sudo make install
cd ../swtpm
./autogen.sh --prefix=/usr
make
sudo make install
cd ..
rm -rf swtpm/ libtpms/
```

## Running BBSR ACS on QEMU with UEFI firmware

### Build QEMU model
Follow build instructions from https://www.qemu.org/download/#source

Note: During configure stage, enable slirp library build by appending ./configure with --enable-slirp <br>
slirp is a networking library, required by netdev in QEMU run command.
```
./configure --enable-slirp
```

### Build UEFI Firmware
To build the UEFI firmware images, follow these steps:
1. Fetch edk2 source
```
mkdir -p work_space
cd work_space
git clone --depth 1 --recurse-submodules https://github.com/tianocore/edk2.git
git clone --depth 1 --recurse-submodules https://github.com/tianocore/edk2-platforms.git
git clone --depth 1 --recurse-submodules https://github.com/tianocore/edk2-non-osi.git
```

2. Build the firmware image
```
export WORKSPACE=$PWD/edk2
export PACKAGES_PATH=$PWD/edk2:$PWD/edk2-platforms:$PWD/edk2-non-osi
. edk2/edksetup.sh
make -C edk2/BaseTools
NUM_CPUS=$((`getconf _NPROCESSORS_ONLN` + 2))
export GCC5_AARCH64_PREFIX=<set compiler prefix path for aarch64-linux-gnu->
build -n $NUM_CPUS -a AARCH64 -t GCC5 -p ArmVirtPkg/ArmVirtQemu.dsc -b RELEASE -D TTY_TERMINAL -D SECURE_BOOT_ENABLE -D TPM2_ENABLE -D TTY_TERMINAL all
```

NOTE: Download GCC-ARM 10.3 or later toolchain from [here](https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-a/downloads). <br />

3. Create the required flash images
```
#uefi firmware image
cp $PWD/edk2/Build/ArmVirtQemu-AARCH64/RELEASE_GCC5/FV/QEMU_EFI.fd flash0.img
truncate -s 64M flash0.img
#empty the flash for efi var store
truncate -s 64M flash1.img
```

### Running BBSR ACS with Prebuilt SystemReady band image on QEMU
1. Create a script "run_qemu.sh" as below with variables configured as per your environment:

```
#! /bin/sh

QEMU=<path to QEMU model>
FLASH0=<path to flash0.img>
FLASH1=<path to flash1.img>
IMG=<path to systemready band image>

WD=`pwd`
TPMSOCK=/tmp/swtpm-sock$$

echo "Creating TPM Emulator socket"
[ -e $WD/tpm ] || mkdir $WD/tpm
swtpm socket --tpm2 -t -d --tpmstate dir=$WD/tpm --ctrl type=unixio,path=$TPMSOCK
echo $TPMSOCK

echo "Running QEMU Virt model"
$QEMU -M virt -cpu cortex-a57 -smp 8 -m 2048 \
-device virtio-net-pci,netdev=net0,romfile="" \
-netdev type=user,id=net0 \
-drive if=pflash,format=raw,file=$FLASH0,readonly=on \
-drive if=pflash,format=raw,file=$FLASH1 \
-chardev socket,id=chrtpm,path=$TPMSOCK \
-tpmdev emulator,id=tpm0,chardev=chrtpm \
-device tpm-tis-device,tpmdev=tpm0 \
-device virtio-blk-pci,drive=drv1 \
-drive format=raw,file=$IMG,if=none,id=drv1 \
-nographic "$@"
```

2. To run the BBSR ACS, execute the "run_qemu.sh".
Once QEMU execution begins, immediately press Esc key to go into the UEFI settings. Follow the steps in Section 3.4 for "Enrolling keys in EDK2" in the [BBSR ACS Users Guide](https://developer.arm.com/documentation/102872/latest) for instructions to enroll the secureboot keys. <br>
Note: The SecureBoot keys are present in \<bootfs>\acs_tests/bbsr-keys


3. To run the BBSR ACS suites, choose following in grub options.
```
"BBSR Compliance (Automation)" for BBSR SCT tests, Secure Linux boot, BBSR FWTS and TPM2 logs.
```

Note: SystemReady-devicetree-band ACS image can also be run using the above steps, if the underlying firmware is UEFI.

## Running BBSR ACS on QEMU with uboot firmware

### Build u-boot firmware 
Follow the instructions provided in [Verification of the SystemReady-devicetree-band image on QEMU Arm machine](../../SystemReady-devicetree-band/README.md#software-stack-and-model) section of SystemReady-devicetree-band Yocto README.

### Running BBSR ACS with Prebuilt SystemReady-devicetree-band ACS image on QEMU
1. Create a script "run_qemu.sh" as below with variables configured as per your environment:

```
#! /bin/bash

IMG=<PATH to SystemReady-devicetree-band ACS image>
BUILD_PATH=<path to buildroot directory where QEMU and uboot firmware is built>
QEMU=$BUILD_PATH/output/host/bin/qemu-system-aarch64
FLASH_BIN=$BUILD_PATH/output/images/flash.bin
DISK_IMG=$BUILD_PATH/output/images/disk.img

WD=`pwd`
TPMSOCK=/tmp/swtpm-sock$$

echo "Creating TPM Emulator socket"
[ -e $WD/tpm ] || mkdir $WD/tpm
swtpm socket --tpm2 -t -d --tpmstate dir=$WD/tpm --ctrl type=unixio,path=$TPMSOCK
echo $TPMSOCK

echo "Running QEMU EBBR + TPM....."

$QEMU \
    -bios $FLASH_BIN \
    -cpu cortex-a53 \
    -d unimp \
    -device virtio-blk-device,drive=hd1 \
    -device virtio-blk-device,drive=hd0 \
    -device virtio-net-device,netdev=eth0 \
    -device virtio-rng-device,rng=rng0 \
    -drive file=$IMG,if=none,format=raw,id=hd0 \
    -drive file=$DISK_IMG,if=none,id=hd1 \
    -m 1024 \
    -machine virt,secure=on \
    -monitor null \
    -chardev socket,id=chrtpm,path=$TPMSOCK \
    -tpmdev emulator,id=tpm0,chardev=chrtpm \
    -device tpm-tis-device,tpmdev=tpm0 \
    -netdev user,id=eth0 \
    -no-acpi \
    -nodefaults \
    -nographic \
    -object rng-random,filename=/dev/urandom,id=rng0 \
    -rtc base=utc,clock=host \
    -serial stdio \
    -smp 2 | tee qemu_ebbr_bbsr_run.log

```

3. Execute the "run_qemu.sh", To run the BBSR ACS suites, choose following in grub options.
```
"BBSR Compliance (Automation)" for BBSR SCT tests, Secure Linux boot, BBSR FWTS and TPM2 logs.
```

**Note:**
 - SystemReady-devicetree-band Yocto ACS supports automatic enrollment of secure boot keys, still if the system fails to enter SecureBoot mode, Please refer to "Enrolling keys in U-boot" section of [BBSR ACS Users Guide](https://developer.arm.com/documentation/102872/latest) for instructions to enroll manually. <br>
 - The SecureBoot keys are present in \<bootfs>\acs_tests\bbsr-keys.

## Disabling Secure Boot and rolling back to Setup Mode
This section outlines the steps required to disable Secure Boot on systems utilizing either U-Boot or UEFI firmware by leveraging the SystemReady ACS test keys. It is intended for scenarios where the system was previously configured with Secure Boot enabled using these same ACS test keys by BBSR ACS.

### Disabling Secure Boot in systems with U-boot firmware
1. **Enter U-Boot Shell**
   - Reset the system.
   - Press `Esc` immediately during boot to enter the U-Boot shell.

2. **Initialize the Appropriate Storage Device**
   - Depending on where the SystemReady ACS keys are stored, you must initialize the correct storage subsystem.

   * Example: Initialize USB Subsystem

      ```bash
      => usb start
      ```

   * Example: Initialize MMC Device 1

      ```bash
      => mmc dev 1
      ```

   * **Note:** Refer to the U-Boot documentation for the correct commands related to your specific storage device.

3. **Clear Platform Key (PK) to Disable Secure Boot**
   - Use the following command to load and delete the Platform Key (PK) using a `NullPK.auth` file, which is a null update signed with the current PK.

   -  Example: Load and Delete PK from USB Device 0

      ```bash
      => load usb 0 ${loadaddr} acs_tests/bbsr-keys/NullPK.auth && setenv -e -nv -bs -rt -at -i ${loadaddr}:$filesize PK
      ```
   - After deleting the PK, reset the system to complete the process.

### Disabling Secure Boot in systems with UEFI firmware

1. **Reboot Your System**.

2. **Enter Firmware Setup Utility**
   - During the boot process, press the appropriate key to enter setup (usually `Esc`, `Del`, `F2`, or similar).

3. **Navigate to the Security or Boot Menu**
   - Use arrow keys to navigate.
   - Look for tabs such as `Boot`, `Security`, or `Advanced`.

4. **Find the Secure Boot Option**
   - Locate `Secure Boot` under the appropriate menu.
   - It may be under `Boot Configuration` or a dedicated `Secure Boot` tab.

5. **Disable Secure Boot**
   - Highlight the `Secure Boot` option.
   - Change its value from `Enabled` to `Disabled` using the `Enter` key or `+/-` keys.

6. **Clear Platform Key (PK)**
   - Navigate to the option to manage Secure Boot keys.
   - Select the option to clear the Platform Key (PK).
   - This action puts the system into `Setup Mode`.

7. **Save and Exit**
   - Press `F10` (or follow the on-screen instruction to save and exit).
   - Confirm changes if prompted.
   - Reboot the System

--------------
*Copyright (c) 2023-25, Arm Limited and Contributors. All rights reserved.*
