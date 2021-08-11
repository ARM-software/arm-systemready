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
# PLATDIR - Platform Output directory
# GRUB_PATH - path to GRUB source
# CROSS_COMPILE - PATH to GCC including CROSS-COMPILE prefix
# PARALLELISM - number of cores to build across
# GRUB_BUILD_ENABLED - Flag to enable building Linux
# BUSYBOX_BUILD_ENABLED - Building Busybox
#


TOP_DIR=`pwd`
. $TOP_DIR/../../common/config/common_config.cfg

GRUB_PATH=grub
GCC=tools/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-
CROSS_COMPILE=$TOP_DIR/$GCC
KEYS_DIR=$TOP_DIR/security-extension-acs-keys
GRUB_CONFIG_FILE=${TOP_DIR}/build-scripts/config/grub.cfg
GRUB_INITIAL_CONFIG_FILE=${TOP_DIR}/build-scripts/config/grub-initial.cfg

do_build ()
{
    arch=$(uname -m)
    if [[ $arch = "aarch64" ]]
    then
        CROSS_COMPILE_DIR=''
    else
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
                ./bootstrap
            fi
        fi

        ./autogen.sh
        ./configure STRIP=$CROSS_COMPILE_DIR/aarch64-linux-gnu-strip \
        --target=aarch64-linux-gnu --with-platform=efi \
        --prefix=$TOP_DIR/$GRUB_PATH/output/ \
        TARGET_CC=$CROSS_COMPILE_DIR/aarch64-linux-gnu-gcc --disable-werror

        make -j8 install
        output/bin/grub-mkstandalone -v \
        -o output/grubaa64.efi -O arm64-efi --pubkey $KEYS_DIR/TestDB1.pubgpg --disable-shim-lock \
        --modules "pgp gcry_sha512 gcry_rsa part_gpt part_msdos ntfs ntfscomp hfsplus fat ext2 normal chain \
        boot configfile linux help part_msdos terminal terminfo configfile tpm \
        lsefi search normal gettext loadenv read search_fs_file search_fs_uuid search_label" \
        "boot/grub/grub.cfg=$GRUB_INITIAL_CONFIG_FILE"

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

    # delete the gpg generated sig file
    rm -f $GRUB_CONFIG_FILE.sig
:
}
do_package ()
{
    pushd $TOP_DIR/$GRUB_PATH

    # sign grub with db key
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt output/grubaa64.efi --output output/grubaa64.efi

    # sign grub.cfg with gpg key
    gpg --default-key "TestDB1" --detach-sign $GRUB_CONFIG_FILE

    popd
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@

