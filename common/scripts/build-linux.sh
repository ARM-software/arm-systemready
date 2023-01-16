#!/usr/bin/env bash

# Copyright (c) 2021-2023, ARM Limited and Contributors. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# Neither the name of ARM nor the names of its contributors may be used
# to endorse or promote products derived from this software without specific
# prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

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
BAND=$1
if [ $BAND == "SR" ] || [ $BAND == "ES" ]; then
    . $TOP_DIR/../../common/config/sr_es_common_config.cfg
else
    . $TOP_DIR/../../common/config/common_config.cfg
fi

LINUX_ARCH=arm64
LINUX_IMAGE_TYPE=Image
KEYS_DIR=$TOP_DIR/security-interface-extension-keys

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
    #Configurations for SecureBoot and TCG for SIE ACS
    sed -i 's/# CONFIG_TCG_TPM is not set/CONFIG_TCG_TPM=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_TIS is not set/CONFIG_TCG_TIS=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_TIS_SPI is not set/CONFIG_TCG_TIS_SPI=y/g' $LINUX_OUT_DIR/.config
    echo "CONFIG_TCG_TIS_SPI_CR50=y" >> $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_TIS_SYNQUACER is not set/CONFIG_TCG_TIS_SYNQUACER=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_TIS_I2C_CR50 is not set/CONFIG_TCG_TIS_I2C_CR50=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_CRB is not set/CONFIG_TCG_CRB=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TCG_FTPM_TEE is not set/CONFIG_TCG_FTPM_TEE=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_TEE is not set/CONFIG_TEE=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_OPTEE is not set/CONFIG_OPTEE=y/g' $LINUX_OUT_DIR/.config

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
    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/drivers/usb/host/xhci-pci.ko $TOP_DIR/ramdisk/drivers

}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
