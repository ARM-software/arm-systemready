#!/usr/bin/env bash

# Copyright (c) 2021, ARM Limited and Contributors. All rights reserved.
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
LINUX_ARCH=arm64
LINUX_IMAGE_TYPE=Image
GCC=tools/gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-
CROSS_COMPILE=$TOP_DIR/$GCC

do_build ()
{
    export ARCH=$LINUX_ARCH

    pushd $LINUX_PATH
    mkdir -p $LINUX_OUT_DIR
    echo "Building using defconfig..."
    cp arch/arm64/configs/defconfig $LINUX_OUT_DIR/.config
    make ARCH=arm64 CROSS_COMPILE=$TOP_DIR/$GCC O=$LINUX_OUT_DIR olddefconfig
    #Configurations needed for FWTS 
    sed -i 's/# CONFIG_EFI_TEST is not set/CONFIG_EFI_TEST=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_DMI_SYSFS is not set/CONFIG_DMI_SYSFS=y/g' $LINUX_OUT_DIR/.config
    sed -i 's/# CONFIG_CGROUP_FREEZER is not set/CONFIG_CGROUP_FREEZER=y/g' $LINUX_OUT_DIR/.config

    make ARCH=arm64 CROSS_COMPILE=$TOP_DIR/$GCC O=$LINUX_OUT_DIR -j$PARALLELISM
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

    mkdir -p ${OUTDIR}/${!outpath}

    cp $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/arch/$LINUX_ARCH/boot/$LINUX_IMAGE_TYPE \
    ${OUTDIR}/${!outpath}/$LINUX_IMAGE_TYPE

}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
