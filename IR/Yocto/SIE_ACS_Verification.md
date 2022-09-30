# Running SIE ACS on QEMU-Virt with TPM support

In this version, the SIE ACS is integrated into the IR ACS Prebuilt image.

See the Section 3.4 [Security Interface Extension ACS Users Guide](https://developer.arm.com/documentation/102872/latest) for instructions to enroll the secureboot keys.
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
GCC5_AARCH64_PREFIX=<set compiler prefix path for aarch64-linux-gnu->
build -n $NUM_CPUS -a AARCH64 -t GCC5 -p ArmVirtPkg/ArmVirtQemu.dsc -b RELEASE -D TTY_TERMINAL -D SECURE_BOOT_ENABLE -D TPM2_ENABLE -D TTY_TERMINAL all
```

3. Create the required flash images
```
#uefi firmware image
cp $PWD/edk2/Build/ArmVirtQemu-AARCH64/RELEASE_GCC5/FV/QEMU_EFI.fd flash0.img
truncate -s 64M flash0.img
#empty the flash for efi var store
truncate -s 64M flash1.img
```

## Running IR ACS prebuilt image on QEMU -Virt model
1. Create a script "run_qemu.sh" as below with variables configured as per your environment:

```
#! /bin/sh

QEMU=<path to QEMU model>
FLASH0=<path to flash0.img>
FLASH1=<path to flash1.img>
IMG=<path to ir-acs-live-image-generic-arm64.wic>

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


3. In the grub options, choose
```
SCT for Security Interface Extension (optional)                            |
and
Linux Boot for Security Interface Extension (optional)
```
to run the SIE ACS suites.

--------------
*Copyright (c) 2022, Arm Limited and Contributors. All rights reserved.*
