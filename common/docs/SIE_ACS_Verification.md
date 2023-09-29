# Introduction to the SystemReady Security Interface Extension (SIE)

The SystemReady Security Interface Extension provides a way to certify that Secure Boot and secure firmware update are implemented as prescribed by the Arm [Base Boot Security Specification](https://developer.arm.com/documentation/den0107/latest) (BBSR).  The Security Interface Extension is an extension to the bands of the SystemReady program and a pre-requisite for a Security Interface Extension certification in one of the IR, ES, or SR bands.

The Security Interface Extension ACS tests the following security related interfaces:
* Authenticated variables
* Secure Boot variables
* Secure firmware update using update capsules
* For systems with Trusted Platform Modules(TPMs), TPM measured boot and the TCG2 protocol

# Running SIE ACS

The Prebuilt SR/ES/IR band images can now be used to verify the requirements of SIE from this release, as they are integrated with the SIE ACS.

See the Section 3.4 [Security Interface Extension ACS Users Guide](https://developer.arm.com/documentation/102872/latest) for instructions to enroll the SecureBoot keys.
This document also contains the background information on the SIE related specification and ACS.

## Installing swtpm package (TPM emulator)
Note: Install only if there is no past installation of swtpm present. Check by running "swtpm -v" in the terminal, which should output the version.

The following commands should fetch and install the swtpm package:

For latest Ubuntu
```
sudo apt install swtpm
```

For Ubuntu 20.04 LTS
```
sudo add-apt-repository ppa:itrue/swtpm
sudo apt-get update
sudo apt-get install swtpm swtpm-tools
```

## Building UEFI Firmware
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

## Running SIE ACS with Prebuilt SystemReady band images on QEMU
1. Create a script "run_qemu.sh" as below with variables configured as per your environment:

```
#! /bin/sh

QEMU=<path to QEMU model>
FLASH0=<path to flash0.img>
FLASH1=<path to flash1.img>
IMG=<path to systemready IR/ES/SR image>

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

2. To run the SIE ACS, execute the "run_qemu.sh".

Once QEMU execution begins, immediately press Esc key to go into the UEFI settings. Follow the steps in Section 3.4 for "Enrolling keys in EDK2" in the [Security Interface Extension ACS Users Guide](https://developer.arm.com/documentation/102872/latest) for instructions to enroll the secureboot keys.

Note: The SecureBoot keys are present in \<bootfs>/security-interface-extension-keys


3. In the grub options, choose
```
SCT for Security Interface Extension (optional) for SIE SCT tests
and
Linux Boot for Security Interface Extension (optional) for Secure Linux boot, SIE FWTS and TPM2 logs.
```
to run the SIE ACS suites.

--------------
*Copyright (c) 2023, Arm Limited and Contributors. All rights reserved.*
