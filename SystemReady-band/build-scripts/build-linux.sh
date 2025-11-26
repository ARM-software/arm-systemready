#!/usr/bin/env bash

# Copyright (c) 2021-2025, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# This script uses the following environment variables from the variant
#
# VARIANT - build variant name
# TOP_DIR - workspace root directory
# CROSS_COMPILE - PATH to GCC including CROSS-COMPILE prefix
# PARALLELISM - number of cores to build across
# LINUX_BUILD_ENABLED - Flag to enable building Linux
# LINUX_PATH - sub-directory containing Linux code
# LINUX_ARCH - Build architecture (arm64)
# LINUX_CONFIG_LIST - List of Linaro configs to use to build
# LINUX_CONFIG_DEFAULT - the default from the list (for tools)
# LINUX_{config} - array of linux config options, indexed by
#     path - the path to the linux source
#    defconfig - a defconfig to build
#    config - the list of config fragments
# TARGET_BINS_PLATS - the platforms to create binaries for
# TARGET_{plat} - array of platform parameters, indexed by
#    fdts - the fdt pattern used by the platform
# UBOOT_UIMAGE_ADDRS - address at which to link UBOOT image
# UBOOT_MKIMAGE - path to uboot mkimage
# LINUX_ARCH - the arch
# UBOOT_BUILD_ENABLED - flag to indicate the need for uimages.
#
# LINUX_IMAGE_TYPE - Image or zImage (Image is the default if not specified)

TOP_DIR=`pwd`
. $TOP_DIR/../common/config/systemready-band-source.cfg

LINUX_ARCH=arm64
LINUX_IMAGE_TYPE=Image
KEYS_DIR=$TOP_DIR/bbsr-keys
SRBAND_DEFCONFIG=$TOP_DIR/../common/config/srband_defconfig

do_build ()
{
    export ARCH=$LINUX_ARCH

    pushd $LINUX_PATH
    mkdir -p $LINUX_OUT_DIR
    echo "Building using defconfig..."
    cp arch/arm64/configs/defconfig $LINUX_OUT_DIR/.config
    arch=$(uname -m)
    if [[ $arch = "aarch64" ]]
    then
        echo "arm64"
        make ARCH=arm64 O=$LINUX_OUT_DIR olddefconfig
    else
        echo "x86 cross compile"
        CROSS_COMPILE=$TOP_DIR/$GCC
        make ARCH=arm64 CROSS_COMPILE=$TOP_DIR/$GCC O=$LINUX_OUT_DIR olddefconfig
    fi
    #Configurations needed for FWTS
    sed -i 's/# CONFIG_EFI_TEST is not set/CONFIG_EFI_TEST=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_DMI_SYSFS is not set/CONFIG_DMI_SYSFS=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_CGROUP_FREEZER is not set/CONFIG_CGROUP_FREEZER=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_COMMON_CLK_ZYNQMP is not set/CONFIG_COMMON_CLK_ZYNQMP=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_EFI_GENERIC_STUB_INITRD_CMDLINE_LOADER is not set/CONFIG_EFI_GENERIC_STUB_INITRD_CMDLINE_LOADER=y/g' $LINUX_OUT_DIR/.config
    #Configurations for SecureBoot and TCG for BBSR ACS
    sed -i 's/# CONFIG_TCG_TPM is not set/CONFIG_TCG_TPM=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_TIS_SYNQUACER is not set/CONFIG_TCG_TIS_SYNQUACER=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_CRB is not set/CONFIG_TCG_CRB=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_FTPM_TEE is not set/CONFIG_TCG_FTPM_TEE=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TEE is not set/CONFIG_TEE=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_OPTEE is not set/CONFIG_OPTEE=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_ARM_PSCI_CHECKER is not set/CONFIG_ARM_PSCI_CHECKER=y/g' $LINUX_OUT_DIR/.config
    #Configurations to enable rshim support
    echo "CONFIG_MLXBF_TMFIFO=y" >> $LINUX_OUT_DIR/.config
    #Configurations to increase serial ports
    echo "CONFIG_SERIAL_8250_NR_UARTS=32" >> $LINUX_OUT_DIR/.config
    echo "CONFIG_SERIAL_8250_RUNTIME_UARTS=32" >> $LINUX_OUT_DIR/.config
    cat $SRBAND_DEFCONFIG >> $LINUX_OUT_DIR/.config
    if [[ $arch = "aarch64" ]]
    then
        echo "arm64 machine"
        make ARCH=arm64 O=$LINUX_OUT_DIR -j$PARALLELISM
    else
        make ARCH=arm64 CROSS_COMPILE=$TOP_DIR/$GCC O=$LINUX_OUT_DIR -j$PARALLELISM
    fi
    popd
}

do_clean ()
{
    export ARCH=$LINUX_ARCH

    pushd $LINUX_PATH
    make O=$LINUX_OUT_DIR distclean
    popd

    rm -rf $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR
}

do_package ()
{
    echo "Packaging Linux... $VARIANT";
    # Copy binary to output folder
    pushd $TOP_DIR

    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/arch/$LINUX_ARCH/boot/$LINUX_IMAGE_TYPE \
    ${OUTDIR}/$LINUX_IMAGE_TYPE

    # Sign the kernel with DB key
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt ${OUTDIR}/$LINUX_IMAGE_TYPE --output ${OUTDIR}/$LINUX_IMAGE_TYPE

    #Copy drivers for packaging into Ramdisk
    mkdir -p $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/nvme/host/nvme.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/nvme/host/nvme-core.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/usb/host/xhci-pci-renesas.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/char/tpm/tpm_tis.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/char/tpm/tpm_tis_spi.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/char/tpm/tpm_tis_i2c_cr50.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/spi/spi-tegra210-quad.ko $TOP_DIR/ramdisk/drivers
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/cpufreq/cppc_cpufreq.ko $TOP_DIR/ramdisk/drivers

}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
