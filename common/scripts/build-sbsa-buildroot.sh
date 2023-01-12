#!/usr/bin/env bash

# Copyright (c) 2015-2023, ARM Limited and Contributors. All rights reserved.
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
# BUILDROOT_BUILD_ENABLED - Flag to enable building Buildroot
# BUILDROOT_PATH - sub-directory containing Buildroot code
# BUILDROOT_ARCH - Build architecture (arm)
# BUILDROOT_RAMDISK_BUILDROOT_PATH - path to the BB binary
# TARGET_BINS_PLATS - the platforms to create binaries for
# TARGET_{plat} - array of platform parameters, indexed by
#       ramdisk - the address of the ramdisk per platform
set -x
TOP_DIR=`pwd`
BAND=$1
if [ $BAND == "SR" ] || [ $BAND == "ES" ]; then
    . $TOP_DIR/../../common/config/sr_es_common_config.cfg
else
    . $TOP_DIR/../../common/config/common_config.cfg
fi

LINUX_ARCH=arm64
BUILDROOT_PATH=buildroot
BUILDROOT_ARCH=$LINUX_ARCH
BUILDROOT_RAMDISK_PATH=$BUILDROOT_PATH/ramdisk
BUILDROOT_OUT_DIR=out/$LINUX_ARCH
BUILDROOT_RAMDISK_BUILDROOT_PATH=$BUILDROOT_PATH/$BUILDROOT_OUT_DIR/images
BUILDROOT_DEFCONFIG=$TOP_DIR/$BUILDROOT_PATH/configs/buildroot_sbsa_defconfig

LINUX_CONFIG_LIST="$LINUX_CONFIG_LIST $BUILDROOT_LINUX_CONFIG_LIST"
LINUX_CONFIG_DEFAULT=$BUILDROOT_LINUX_CONFIG_LIST

do_build ()
{
    export ARCH=$BUILDROOT_ARCH

    cp $TOP_DIR/../../common/config/buildroot_sbsa_defconfig  $TOP_DIR/$BUILDROOT_PATH/configs/
    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR
    make O=$BUILDROOT_OUT_DIR buildroot_sbsa_defconfig
    make O=$BUILDROOT_OUT_DIR -j $PARALLELISM
    rm $BUILDROOT_DEFCONFIG
    popd
}

do_clean ()
{
    export ARCH=$BUILDROOT_ARCH

    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR
    make O=$BUILDROOT_OUT_DIR clean
    popd

    rm -f ${PLATDIR}/ramdisk-buildroot.img

}

do_package ()
{
    echo "Packaging BUILDROOT SR";
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
