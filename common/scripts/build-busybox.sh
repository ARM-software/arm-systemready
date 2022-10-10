#!/usr/bin/env bash

# Copyright (c) 2015-2022, ARM Limited and Contributors. All rights reserved.
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
# LINUX_COMPILER - PATH to GCC including CROSS-COMPILE prefix
# BUSYBOX_BUILD_ENABLED - Flag to enable building BusyBox
# BUSYBOX_PATH - sub-directory containing BusyBox code
# BUSYBOX_ARCH - Build architecture (arm)
# BUSYBOX_RAMDISK_PATH - path to where we build the ramdisk
# BUSYBOX_RAMDISK_BUSYBOX_PATH - path to the BB binary
# TARGET_BINS_PLATS - the platforms to create binaries for
# TARGET_{plat} - array of platform parameters, indexed by
#     ramdisk - the address of the ramdisk per platform
# LINUX_PATH - Path to Linux tree containing DT compiler and include files
# LINUX_OUT_DIR - output directory name
# LINUX_CONFIG_DEFAULT - the default linux build output


TOP_DIR=`pwd`
BAND=$1

if [ $BAND == "SR" ]; then
    . $TOP_DIR/../../common/config/sr_common_config.cfg
else
    . $TOP_DIR/../../common/config/common_config.cfg
fi

BUSYBOX_ARCH=arm64
BUSYBOX_PATH=busybox
BUSYBOX_OUT_DIR=output
BUSYBOX_RAMDISK_PATH=ramdisk

BUSYBOX_RAMDISK_BUSYBOX_PATH=$BUSYBOX_PATH/$BUSYBOX_OUT_DIR/_install/bin

do_build()
{
    echo "Building busybox..."
    export ARCH=$BUSYBOX_ARCH
    pushd $TOP_DIR/$BUSYBOX_PATH
    mkdir -p $BUSYBOX_OUT_DIR
    make O=$BUSYBOX_OUT_DIR defconfig
    sed -i 's/# CONFIG_STATIC is not set/CONFIG_STATIC=y/g' $BUSYBOX_OUT_DIR/.config
    arch=$(uname -m)
    if [[ $arch = "aarch64" ]]
    then
        echo "arm64 native compile"
        make O=$BUSYBOX_OUT_DIR -j $PARALLELISM  ARCH=arm64
        make O=$BUSYBOX_OUT_DIR ARCH=arm64 install
    else
        GCC=tools/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-
        CROSS_COMPILE=$TOP_DIR/$GCC
        make O=$BUSYBOX_OUT_DIR -j $PARALLELISM  ARCH=arm64 CROSS_COMPILE=$TOP_DIR/$GCC
        make O=$BUSYBOX_OUT_DIR ARCH=arm64 CROSS_COMPILE=$TOP_DIR/$GCC install
    fi
    popd

}

do_clean ()
{
    export ARCH=$BUSYBOX_ARCH

    pushd $TOP_DIR/$BUSYBOX_PATH
    mkdir -p $BUSYBOX_OUT_DIR
    make O=$BUSYBOX_OUT_DIR clean
    popd
    pushd $TOP_DIR/$BUSYBOX_RAMDISK_PATH
    rm -f ramdisk.img busybox
    popd
}

do_package ()
{
    echo "Packaging BUSYBOX... $VARIANT";
    # create the ramdisk
    pushd $TOP_DIR/$BUSYBOX_RAMDISK_PATH
    pwd
    if [ $BAND == "SR" ]; then
        touch $TOP_DIR/$BUSYBOX_RAMDISK_PATH/sr_bsa.flag
    fi
    if [ $BAND == "SR" ]; then
           echo "file /bin/sr_bsa.flag                   ./sr_bsa.flag                                         755 0 0"  >> files.txt
           echo "file /bin/sbsa                          ./linux-sbsa/sbsa                                         755 0 0"  >> files.txt
           echo "file /lib/modules/sbsa_acs.ko           ./linux-sbsa/sbsa_acs.ko                                  755 0 0"  >> files.txt
           echo "file /lib/modules/nvme.ko               ./drivers/nvme.ko                                         755 0 0"  >> files.txt
           echo "file /lib/modules/nvme-core.ko          ./drivers/nvme-core.ko                                    755 0 0"  >> files.txt
           echo "file /lib/modules/xhci-pci.ko           ./drivers/xhci-pci.ko                                     755 0 0"  >> files.txt
           echo "file /lib/modules/xhci-pci-renesas.ko   ./drivers/xhci-pci-renesas.ko                             755 0 0"  >> files.txt
    fi
    cp $TOP_DIR/$BUSYBOX_RAMDISK_BUSYBOX_PATH/busybox .
    $TOP_DIR/$LINUX_PATH/$LINUX_OUT_DIR/$LINUX_CONFIG_DEFAULT/usr/gen_init_cpio files.txt \
    > ramdisk.img
    popd
    # Copy binary to output folder
    pushd $TOP_DIR
    mkdir -p ${OUTDIR}
    cp $BUSYBOX_RAMDISK_PATH/ramdisk.img  ${PLATDIR}/ramdisk-busybox.img
    popd
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
