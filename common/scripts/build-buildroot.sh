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
. $TOP_DIR/../../common/config/sr_es_common_config.cfg

LINUX_ARCH=arm64
BUILDROOT_PATH=buildroot
BUILDROOT_ARCH=$LINUX_ARCH
BUILDROOT_OUT_DIR=out/$LINUX_ARCH
BUILDROOT_RAMDISK_BUILDROOT_PATH=$BUILDROOT_PATH/$BUILDROOT_OUT_DIR/images
BUILDROOT_DEFCONFIG=$TOP_DIR/$BUILDROOT_PATH/configs/buildroot_defconfig
OUTDIR=$TOP_DIR/output
LINUX_CONFIG_LIST="$LINUX_CONFIG_LIST $BUILDROOT_LINUX_CONFIG_LIST"
LINUX_CONFIG_DEFAULT=$BUILDROOT_LINUX_CONFIG_LIST

do_build ()
{
    export ARCH=$BUILDROOT_ARCH

    cp $TOP_DIR/../../common/config/buildroot_defconfig  $TOP_DIR/$BUILDROOT_PATH/configs/
    pushd $TOP_DIR/$BUILDROOT_PATH
    mkdir -p $BUILDROOT_OUT_DIR
    mkdir -p root_fs_overlay
    mkdir -p root_fs_overlay/etc/init.d
    cp  $TOP_DIR/../../common/ramdisk/inittab root_fs_overlay/etc
    cp  $TOP_DIR/../../common/ramdisk/init.sh root_fs_overlay/etc/init.d/S99init.sh
    cp  $TOP_DIR/../../common/ramdisk/resolv.conf root_fs_overlay/etc/resolv.conf
    chmod +x root_fs_overlay/etc/init.d/S99init.sh
    mkdir -p root_fs_overlay/bin
    mkdir -p root_fs_overlay/lib/modules
    mkdir -p root_fs_overlay/usr/bin
    mkdir -p root_fs_overlay/usr/bin/sbmr-acs

    cp -r $TOP_DIR/edk2-test-parser root_fs_overlay/usr/bin/ 
    cp  $TOP_DIR/ramdisk/linux-bsa/bsa root_fs_overlay/bin/
    cp  $TOP_DIR/ramdisk/linux-bsa/bsa_acs.ko root_fs_overlay/lib/modules/
    cp  $TOP_DIR/ramdisk/drivers/* root_fs_overlay/lib/modules/
    cp  $TOP_DIR/ramdisk/secure_init.sh root_fs_overlay/usr/bin/
    chmod +x root_fs_overlay/usr/bin/secure_init.sh
    cp  $TOP_DIR/bbr-acs/bbsr/config/bbsr_fwts_tests.ini root_fs_overlay/bin/
    cp  $TOP_DIR/../../common/config/verify_tpm_measurements.py root_fs_overlay/bin/
    tar -xf $TOP_DIR/sbmr-acs/sbmr-acs_master.tar.gz -C root_fs_overlay/usr/bin/sbmr-acs

    if [ $BAND == "IR" ]; then
        cp  $TOP_DIR/bbr-acs/ebbr/config/ir_bbr_fwts_tests.ini root_fs_overlay/bin/
    fi

    if [ $BAND == "SR" ]; then
        touch root_fs_overlay/bin/sr_bsa.flag
        cp  $TOP_DIR/ramdisk/linux-sbsa/sbsa root_fs_overlay/bin/
        cp $TOP_DIR/ramdisk/linux-sbsa/mte_test root_fs_overlay/bin/
        cp  $TOP_DIR/ramdisk/linux-sbsa/sbsa_acs.ko root_fs_overlay/lib/modules/
        cp -r  $TOP_DIR/ramdisk/linux-sbsa/pmuval root_fs_overlay/bin/
    fi

    make O=$BUILDROOT_OUT_DIR buildroot_defconfig
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
