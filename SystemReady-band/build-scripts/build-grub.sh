#!/usr/bin/env bash

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
# PLATDIR - Platform Output directory
# GRUB_PATH - path to GRUB source
# CROSS_COMPILE - PATH to GCC including CROSS-COMPILE prefix
# PARALLELISM - number of cores to build across
# GRUB_BUILD_ENABLED - Flag to enable building Linux
# BUSYBOX_BUILD_ENABLED - Building Busybox
#


TOP_DIR=`pwd`
arch=$(uname -m)
. $TOP_DIR/../common/config/systemready-band-source.cfg

GRUB_TARGET=aarch64-none-linux-gnu
GRUB_PATH=grub
GRUB_PLAT_CONFIG_FILE=${TOP_DIR}/build-scripts/config/grub_prefix.cfg
KEYS_DIR=$TOP_DIR/bbsr-keys

do_build ()
{
    if [[ $arch = "aarch64" ]]; then
        CROSS_COMPILE_DIR=''
    else
        CROSS_COMPILE=$TOP_DIR/$GCC
        CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
        PATH="$PATH:$CROSS_COMPILE_DIR"
    fi

    if [ -d $TOP_DIR/$GRUB_PATH ]; then
        pushd $TOP_DIR/$GRUB_PATH
        echo $CROSS_COMPILE_DIR
        echo $CROSS_COMPILE
        mkdir -p $TOP_DIR/$GRUB_PATH/output
        # On the master branch of grub, commit '35b90906'
        #("gnulib: Upgrade Gnulib and switch to bootstrap tool")
        # required the bootstrap tool to be executed before the configure step.
        if [ -e bootstrap ]; then
            if [ ! -e grub-core/lib/gnulib/stdlib.in.h ]; then
                GNULIB_URL="https://github.com/coreutils/gnulib.git" \
                ./bootstrap
            fi
        fi

        ./autogen.sh

        if [[ $arch = "aarch64" ]]; then
            ./configure \
            --target=aarch64-linux-gnu --with-platform=efi \
            --prefix=$TOP_DIR/$GRUB_PATH/output/ \
            --disable-werror
        else
            ./configure STRIP=${CROSS_COMPILE}strip \
            --target=$GRUB_TARGET --with-platform=efi \
            --prefix=$TOP_DIR/$GRUB_PATH/output/ \
            TARGET_CC=${CROSS_COMPILE}gcc --disable-werror
        fi

        make -j $PARALLELISM install
        output/bin/grub-mkimage -v -c ${GRUB_PLAT_CONFIG_FILE} \
        -o output/grubaa64.efi -O arm64-efi --disable-shim-lock -p "" \
        part_gpt part_msdos ntfs ntfscomp hfsplus fat ext2 normal chain \
        boot configfile linux help  terminal terminfo configfile \
        lsefi search normal gettext loadenv read search_fs_file search_fs_uuid search_label \
        pgp gcry_sha512 gcry_rsa tpm

        popd
    fi

}

do_clean ()
{
    if [ -d $TOP_DIR/$GRUB_PATH ]; then
        pushd $TOP_DIR/$GRUB_PATH
        rm -rf output
        git clean -fdX
        popd
    fi
}

do_package ()
{
    # sign grub with db key
    pushd $TOP_DIR/$GRUB_PATH
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt output/grubaa64.efi --output output/grubaa64.efi
    popd
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@

