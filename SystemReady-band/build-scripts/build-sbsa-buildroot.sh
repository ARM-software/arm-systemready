#!/bin/sh

# @file
# Copyright (c) 2021-2024, Arm Limited or its affiliates. All rights reserved.
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
# BUILDROOT_BUILD_ENABLED - Flag to enable building Buildroot
# BUILDROOT_PATH - sub-directory containing Buildroot code
# TARGET_BINS_PLATS - the platforms to create binaries for
# TARGET_{plat} - array of platform parameters, indexed by
#       ramdisk - the address of the ramdisk per platform
set -x
TOP_DIR=`pwd`
. $TOP_DIR/../common/config/systemready-band-source.cfg

LINUX_ARCH=arm64
BUILDROOT_PATH=buildroot
BUILDROOT_OUT_DIR=out/$LINUX_ARCH
BUILDROOT_DEFCONFIG=$TOP_DIR/$BUILDROOT_PATH/configs/buildroot_sbsa_defconfig
KDIR="${TOP_DIR}/linux-${LINUX_KERNEL_VERSION}/out"

do_build ()
{
    export ARCH=$LINUX_ARCH

    cp $TOP_DIR/../common/config/buildroot_sbsa_defconfig  $TOP_DIR/$BUILDROOT_PATH/configs/
    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR
    make O=$BUILDROOT_OUT_DIR buildroot_sbsa_defconfig
    make O=$BUILDROOT_OUT_DIR -j $PARALLELISM
    rm $BUILDROOT_DEFCONFIG
    popd
    pushd $TOP_DIR/$BUILDROOT_PATH/out/arm64/build/fwts-${FWTS_VERSION}/smccc_test
    make -C "$KDIR" M="$PWD" CROSS_COMPILE="$CROSS_COMPILE" modules
    cp smccc_test.ko $TOP_DIR/ramdisk/drivers/
    popd

}

do_clean ()
{
    export ARCH=$LINUX_ARCH

    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR
    make O=$BUILDROOT_OUT_DIR clean
    popd

    rm -f ${PLATDIR}/ramdisk-buildroot.img

}

do_package ()
{
    echo "Packaging BUILDROOT";
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
