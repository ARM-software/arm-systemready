#!/usr/bin/env bash

# Copyright (c) 2015-2021, ARM Limited and Contributors. All rights reserved.
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
# BUILDROOT_PATH - sub-directory containing Buildroot code
# BUSYBOX_RAMDISK_PATH - path to where we build the ramdisk
# BUSYBOX_RAMDISK_BUSYBOX_PATH - path to the BB binary
# TARGET_BINS_PLATS - the platforms to create binaries for
# TARGET_{plat} - array of platform parameters, indexed by
#     ramdisk - the address of the ramdisk per platform
# LINUX_PATH - Path to Linux tree containing DT compiler and include files
# LINUX_OUT_DIR - output directory name
# LINUX_CONFIG_DEFAULT - the default linux build output

NUM_CPUS=$((`getconf _NPROCESSORS_ONLN` + 2))

TOP_DIR=`pwd`
. $TOP_DIR/../../common/config/common_config.cfg

BUILDROOT_PATH=buildroot
KEYS_DIR=$TOP_DIR/security-extension-acs-keys

do_build()
{
    echo "Building buildroot..."
    pushd $TOP_DIR/$BUILDROOT_PATH
    make arm_systemready_defconfig
    make -j $NUM_CPUS
    popd
}

do_clean ()
{
    echo "FIXME: NOT Cleaning buildroot..."
    pushd $TOP_DIR/$BUILDROOT_PATH
    make clean
    popd
    pushd $TOP_DIR/$BUILDROOT_RAMDISK_PATH
    rm -f $OUTDIR/ramdisk-busybox.img
    rm -f $OUTDIR/Image
    rm -f $OUTDIR/*.gpg
    popd
}

do_package ()
{
    echo "Packaging buildroot... $VARIANT";
    pushd $TOP_DIR
    mkdir -p $OUTDIR
    # Copy rootfs image to output folder
    cp $BUILDROOT_PATH/output/images/rootfs.cpio $OUTDIR/ramdisk-busybox.img
    # sign the rootfs image
    gpg --yes --default-key "TestDB1" --detach-sign $OUTDIR/ramdisk-busybox.img
    # Copy Linux kernel to output folder
    cp $BUILDROOT_PATH/output/images/Image $OUTDIR
    # Sign the kernel
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt $OUTDIR/Image --output $OUTDIR/Image
    gpg --yes --default-key "TestDB1" --detach-sign output/Image
    popd
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
