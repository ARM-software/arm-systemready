#!/usr/bin/env bash

# @file
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
# BUILDROOT_BUILD_ENABLED - Flag to enable building Buildroot
# BUILDROOT_PATH - sub-directory containing Buildroot code
# BUILDROOT_RAMDISK_BUILDROOT_PATH - path to the BB binary
# TARGET_BINS_PLATS - the platforms to create binaries for
# TARGET_{plat} - array of platform parameters, indexed by
#       ramdisk - the address of the ramdisk per platform
set -x
TOP_DIR=`pwd`
. $TOP_DIR/../common/config/systemready-band-source.cfg

LINUX_ARCH=arm64
BUILDROOT_PATH=buildroot
BUILDROOT_OUT_DIR=out/$LINUX_ARCH
BUILDROOT_RAMDISK_BUILDROOT_PATH=$BUILDROOT_PATH/$BUILDROOT_OUT_DIR/images
BUILDROOT_DEFCONFIG=$TOP_DIR/$BUILDROOT_PATH/configs/buildroot_defconfig
OUTDIR=$TOP_DIR/output
ARCH=arm64
CROSS_COMPILE=${TOP_DIR}/tools/arm-gnu-toolchain-13.2.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
KDIR="${TOP_DIR}/linux-6.16/out" 

do_build ()
{
    export ARCH=$LINUX_ARCH

    cp $TOP_DIR/../common/config/buildroot_defconfig  $TOP_DIR/$BUILDROOT_PATH/configs/
    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR

    mkdir -p root_fs_overlay
    mkdir -p root_fs_overlay/etc/init.d
    cp  $TOP_DIR/ramdisk/inittab root_fs_overlay/etc
    cp  $TOP_DIR/ramdisk/init.sh root_fs_overlay/etc/init.d/S99init.sh
    cp  $TOP_DIR/ramdisk/resolv.conf root_fs_overlay/etc/resolv.conf
    chmod +x root_fs_overlay/etc/init.d/S99init.sh

    mkdir -p root_fs_overlay/bin
    mkdir -p root_fs_overlay/lib/modules
    mkdir -p root_fs_overlay/usr/bin
    mkdir -p root_fs_overlay/usr/bin/sbmr-acs

    if [ ! -d root_fs_overlay/usr/bin/edk2-test-parser ]; then
        cp -r $TOP_DIR/edk2-test-parser root_fs_overlay/usr/bin/
    fi
    cp -r $TOP_DIR/../common/log_parser root_fs_overlay/usr/bin
    cp  $TOP_DIR/ramdisk/linux-bsa/bsa root_fs_overlay/bin/
    cp  $TOP_DIR/ramdisk/linux-bsa/bsa_acs.ko root_fs_overlay/lib/modules/
    cp  $TOP_DIR/ramdisk/drivers/* root_fs_overlay/lib/modules/

    cp  $TOP_DIR/ramdisk/secure_init.sh root_fs_overlay/usr/bin/
    chmod +x root_fs_overlay/usr/bin/secure_init.sh
    cp  $TOP_DIR/ramdisk/device_driver_sr.sh root_fs_overlay/usr/bin/
    chmod +x root_fs_overlay/usr/bin/device_driver_sr.sh
    cp  $TOP_DIR/ramdisk/bsa.sh root_fs_overlay/usr/bin/
    chmod +x root_fs_overlay/usr/bin/bsa.sh
    cp  $TOP_DIR/ramdisk/sbsa.sh root_fs_overlay/usr/bin/
    chmod +x root_fs_overlay/usr/bin/sbsa.sh
    cp  $TOP_DIR/ramdisk/fwts.sh root_fs_overlay/usr/bin/
    chmod +x root_fs_overlay/usr/bin/fwts.sh
    cp  $TOP_DIR/bbr-acs/bbsr/config/bbsr_fwts_tests.ini root_fs_overlay/bin/
    cp  $TOP_DIR/ramdisk/verify_tpm_measurements.py root_fs_overlay/bin/
    tar -xf $TOP_DIR/sbmr-acs/sbmr-acs.tar.gz -C root_fs_overlay/usr/bin/sbmr-acs

    touch root_fs_overlay/bin/sr_bsa.flag
    cp  $TOP_DIR/ramdisk/linux-sbsa/sbsa root_fs_overlay/bin/
    cp $TOP_DIR/ramdisk/linux-sbsa/mte_test root_fs_overlay/bin/
    cp  $TOP_DIR/ramdisk/linux-sbsa/sbsa_acs.ko root_fs_overlay/lib/modules/
    cp -r  $TOP_DIR/ramdisk/linux-sbsa/pmuval root_fs_overlay/bin/

    make O=$BUILDROOT_OUT_DIR buildroot_defconfig
    make O=$BUILDROOT_OUT_DIR -j $PARALLELISM
    rm $BUILDROOT_DEFCONFIG
    popd
    pushd $TOP_DIR/$BUILDROOT_PATH/out/arm64/build/fwts-25.09.00/smccc_test
    make -C "$KDIR" M="$PWD" CROSS_COMPILE="$CROSS_COMPILE" modules
    cp smccc_test.ko $TOP_DIR/$BUILDROOT_PATH/root_fs_overlay/lib/modules/
    popd
}

do_clean ()
{
    export ARCH=$LINUX_ARCH

    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR
    make O=$BUILDROOT_OUT_DIR clean
    popd

    rm -f ${OUTDIR}/ramdisk-buildroot.img
    rm -rf ${TOP_DIR}/buildroot/root_fs_overlay

}

do_package ()
{
    echo "Packaging BUILDROOT... $VARIANT";
    # Copy binary to output folder
    pushd $TOP_DIR
    cp $TOP_DIR/$BUILDROOT_RAMDISK_BUILDROOT_PATH/rootfs.cpio ${OUTDIR}/ramdisk-buildroot.img
    popd
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
