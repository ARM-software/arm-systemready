#!/usr/bin/env bash

# Copyright (c) 2022, ARM Limited and Contributors. All rights reserved.
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
set -x
TOP_DIR=`pwd`

#Get the band run from automatically
pushd ../..
BAND_PATH=`pwd`
BAND=`basename $BAND_PATH`
popd

echo "Getting the sources for $BAND "

. $TOP_DIR/../../common/config/common_config.cfg

#The shell variables use in this file are defined in common_config.cfg

export GIT_SSL_NO_VERIFY=1


sudo apt install git curl mtools gdisk gcc liblz4-tool zstd \
 openssl automake autotools-dev libtool bison flex \
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint \
 make gcc g++ python gnu-efi libfile-slurp-perl help2man 

sudo pip3 install kas

pushd $TOP_DIR/meta-woden
git init
kas checkout kas/woden.yml
popd

customise_image()
{
    #Remove the root login prompt after the startup
    sed -i 's/ExecStart=.*/ExecStart=\-\/sbin\/agetty \-a root \-8 \-L \%I \@BAUDRATE\@ \$TERM/' $TOP_DIR/meta-woden/poky/meta/recipes-core/systemd/systemd-serialgetty/serial-getty@.service

}


copy_recipes()
{

    #woden.conf will be changed
    #sed -i 's/PREFERRED_VERSION_linux-yocto ?= \"[0-9]\.[0-9][0-9]\%\"/PREFERRED_VERSION_linux-yocto ?= \"'${YOCTO_LINUX_KERNEL_VERSION}'\%\"/' $TOP_DIR/meta-woden/poky/meta-poky/conf/distro/poky.conf

    #Adding build option to grub that is required for SecureBoot
    sed -i 's/\/grub\-core\//\/grub\-core\/\ --disable-shim-lock/g' $TOP_DIR/meta-woden/poky/meta/recipes-bsp/grub/grub-efi_2.06.bb

    #Remove the existing recipe
    rm $TOP_DIR/meta-woden/poky/meta/recipes-kernel/linux/linux-yocto_5.15.bb 

    #copy linux_yocto.bbappend with empty defconfig
    cp $TOP_DIR/config/linux-yocto_%.bbappend $TOP_DIR/meta-woden/meta-arm/meta-arm/recipes-kernel/linux/linux-yocto_%.bbappend

    cp $TOP_DIR/meta-woden/recipes-acs/edk2-firmware/files/allow_capsule_on_disk.patch $TOP_DIR/meta-woden/meta-arm/meta-arm/recipes-bsp/uefi/files

    # check whether common_config.cfg specifies tag for related source(s) and update
    # recipes accordingly
    if [ ! -z "$ARM_BSA_TAG" ]; then
        sed -i -E 's/SRCREV_bsa-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_bsa-acs = \"'${ARM_BSA_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs.bb
        sed -i -E 's/SRCREV_bsa-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_bsa-acs = \"'${ARM_BSA_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-app/bsa-acs-app.bb
        sed -i -E 's/SRCREV_bsa-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_bsa-acs = \"'${ARM_BSA_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-drv/bsa-acs-drv.bb
    fi

    if [ ! -z "$EDK2_SRC_TAG" ]; then
        sed -i -E 's/SRCREV_edk2\s+=\s+"\$\{AUTOREV\}"/SRCREV_edk2 = \"'${EDK2_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/ebbr-sct/ebbr-sct.bb
        sed -i -E 's/SRCREV_edk2\s+\?=\s+"\$\{AUTOREV\}"/SRCREV_edk2 = \"'${EDK2_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/edk2-firmware/edk2-firmware-rev.bb
    fi

    if [ ! -z "$ARM_BBR_TAG" ]; then
        sed -i -E 's/SRCREV_bbr-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_bbr-acs = \"'${ARM_BBR_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/ebbr-sct/ebbr-sct.bb
    fi

    if [ ! -z "$EDK2_LIBC_SRC_TAG" ]; then
        sed -i -E 's/SRCREV_edk2-libc\s+=\s+"\$\{AUTOREV\}"/SRCREV_edk2-libc = \"'${EDK2_LIBC_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs.bb
    fi

    if [ ! -z "$SCT_SRC_TAG" ]; then
        sed -i -E 's/SRCREV_edk2-test\s+=\s+"\$\{AUTOREV\}"/SRCREV_edk2-test = \"'${SCT_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/ebbr-sct/ebbr-sct.bb
    fi

    if [ ! -z "$ARM_LINUX_ACS_TAG" ]; then
        sed -i -E 's/SRCREV_linux-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_linux-acs = \"'${ARM_LINUX_ACS_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-drv/bsa-acs-drv.bb
    fi

    # create a bsa-acs patches directory in meta-woden/recipes-acs/bsa-acs-uefi and copy requires BSA patches
    mkdir $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs
    cp $TOP_DIR/../patches/* $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs/.

    # copy .nsh files to meta-woden/recipes-acs/bootfs-files/files
    COMMON_DIR_PATH=`git rev-parse --show-toplevel`"/common"
    mkdir $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files
    cp $COMMON_DIR_PATH/config/*.nsh $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files/.

    #update run-time scripts with ACS version
    pushd $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files
    if [ ! -z "$ACS_VERSION" ] && [ ! -z "$ARM_BSA_VERSION" ]; then
        sed -i 's/#BSA_VERSION_PRINT_PLACEHOLDER/echo '"${ACS_VERSION}"'\necho BSA '"${ARM_BSA_VERSION}"' /g' bsa.nsh
    fi

    # remove connect -r from startup.nsh, since it is not required for IR systems
    sed -i 's/connect -r//g' startup.nsh

    popd

}

copy_recipes
customise_image

