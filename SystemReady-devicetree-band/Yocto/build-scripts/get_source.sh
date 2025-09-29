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

set -x
TOP_DIR=`pwd`

#Get the band run from automatically
pushd ../..
BAND_PATH=`pwd`
BAND=`basename $BAND_PATH`
popd

echo "Getting the sources for $BAND "

. $TOP_DIR/../../common/config/systemready-dt-band-source.cfg


export GIT_SSL_NO_VERIFY=1
source /etc/lsb-release

REL="${DISTRIB_RELEASE//[!0-9]/}"
MAJORREL=${REL:0:2}
if [ $MAJORREL -gt 18 ]; then
    sudo apt install python-is-python3 -y
else
    sudo apt install python -y
fi

sudo apt install git curl mtools gdisk gcc liblz4-tool zstd \
 openssl automake autotools-dev libtool bison flex \
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint \
 make gcc g++ gnu-efi libfile-slurp-perl help2man \
 python3-pip chrpath diffstat lz4 cpio gawk wget efitools -y

sudo pip3 install kas

pushd $TOP_DIR/meta-woden
git init
kas checkout kas/woden.yml
popd

customise_image()
{
    #Remove the root login prompt after the startup
    sed -i 's/ExecStart=.*/ExecStart=\-\/sbin\/agetty \-a root \-8 \-L \--keep-baud \%I \@BAUDRATE\@ \$TERM/' $TOP_DIR/meta-woden/poky/meta/recipes-core/systemd/systemd-serialgetty/serial-getty@.service

}


copy_recipes()
{

    #grub-2.06 config to workaround secureboot issue seen with 2.12
    pushd $TOP_DIR/meta-woden/poky/meta/recipes-bsp
    git checkout 0a010ac1b46651aaaf57008fb9e6db656822b2e4 -- grub
    popd

    #Adding build option to grub that is required for SecureBoot
    sed -i 's/\/grub\-core\//\/grub\-core\/\ --disable-shim-lock/g' $TOP_DIR/meta-woden/poky/meta/recipes-bsp/grub/grub-efi_2.06.bb

    #Remove the existing recipe
    rm $TOP_DIR/meta-woden/poky/meta/recipes-kernel/linux/linux-yocto_6.6.bb

    #Increase the initramfs size to hold more storage drivers in ACS image
    sed -i 's/INITRAMFS_MAXSIZE ??= "131072"/INITRAMFS_MAXSIZE ??= "180000"/' $TOP_DIR/meta-woden/poky/meta/conf/bitbake.conf


    #copy linux_yocto.bbappend with empty defconfig
    cp $TOP_DIR/config/linux-yocto_%.bbappend $TOP_DIR/meta-woden/meta-arm/meta-arm/recipes-kernel/linux/linux-yocto_%.bbappend

    cp $TOP_DIR/meta-woden/recipes-acs/edk2-firmware/files/allow_capsule_on_disk.patch $TOP_DIR/meta-woden/meta-arm/meta-arm/recipes-bsp/uefi/files


    # recipes accordingly
    if [ ! -z "$SYS_ARCH_ACS_TAG" ]; then
        sed -i -E 's/SRCREV_sysarch-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_sysarch-acs = \"'${SYS_ARCH_ACS_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs.bb
        sed -i -E 's/SRCREV_sysarch-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_sysarch-acs = \"'${SYS_ARCH_ACS_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-app/bsa-acs-app.bb
        sed -i -E 's/SRCREV_sysarch-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_sysarch-acs = \"'${SYS_ARCH_ACS_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-drv/bsa-acs-drv.bb
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
        sed -i -E 's/SRCREV_edk2-libc\s+=\s+"\$\{AUTOREV\}"/SRCREV_edk2-libc = \"'${EDK2_LIBC_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/pfdi/pfdi.bb
    fi

    if [ ! -z "$SCT_SRC_TAG" ]; then
        sed -i -E 's/SRCREV_edk2-test\s+=\s+"\$\{AUTOREV\}"/SRCREV_edk2-test = \"'${SCT_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/ebbr-sct/ebbr-sct.bb
    fi

    if [ ! -z "$ARM_LINUX_ACS_TAG" ]; then
        sed -i -E 's/SRCREV_linux-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_linux-acs = \"'${ARM_LINUX_ACS_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/bsa-acs-drv/bsa-acs-drv.bb
    fi

    if [ ! -z "$EDK2_TEST_PARSER_TAG" ]; then
        sed -i -E 's/SRCREV_edk2-test-parser\s+=\s+"\$\{AUTOREV\}"/SRCREV_edk2-test-parser = \"'${EDK2_TEST_PARSER_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/edk2-test-parser/edk2-test-parser.bb
    fi

    if [ ! -z "$SYSTEMREADY_SCRIPTS_TAG" ]; then
        sed -i -E 's/SRCREV_systemready-scripts\s+=\s+"\$\{AUTOREV\}"/SRCREV_systemready-scripts = \"'${SYSTEMREADY_SCRIPTS_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/systemready-scripts/systemready-scripts.bb
    fi

    if [ ! -z "$PFDI_SRC_TAG" ];then
        sed -i -E 's/SRCREV_sysarch-acs\s+=\s+"\$\{AUTOREV\}"/SRCREV_sysarch-acs = \"'${PFDI_SRC_TAG}'"/g' $TOP_DIR/meta-woden/recipes-acs/pfdi/pfdi.bb
    fi

    # create a bsa-acs patches directory in meta-woden/recipes-acs/bsa-acs-uefi and copy requires BSA patches
    mkdir $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs
    cp $TOP_DIR/../patches/* $TOP_DIR/meta-woden/recipes-acs/bsa-acs-uefi/bsa-acs/.

    # copy .nsh files to meta-woden/recipes-acs/bootfs-files/files
    COMMON_DIR_PATH=`git rev-parse --show-toplevel`"/common"
    mkdir $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files
    cp $COMMON_DIR_PATH/uefi_scripts/*.nsh $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files/.
    mv $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files/startup_dt.nsh $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files/startup.nsh
    cp $COMMON_DIR_PATH/config/*.txt $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files/.

    pushd $TOP_DIR/meta-woden/recipes-acs/bootfs-files/files

    # remove connect -r from startup.nsh, since it is not required for SystemReady-devicetree-band systems
    sed -i 's/connect -r//g' startup.nsh
    cp $TOP_DIR/../../common/linux_scripts/secure_init.sh $TOP_DIR/meta-woden/recipes-acs/install-files/files
    cp $TOP_DIR/../../common/linux_scripts/verify_tpm_measurements.py $TOP_DIR/meta-woden/recipes-acs/install-files/files
    cp $TOP_DIR/../../common/linux_scripts/extract_capsule_fw_version.py $TOP_DIR/meta-woden/recipes-acs/install-files/files

    cp -r $TOP_DIR/../../common/log_parser $TOP_DIR/meta-woden/recipes-acs/install-files/files/
    popd
    # copy any patches to linux src files directory
    cp $COMMON_DIR_PATH/patches/tpm-tis-spi-Add-hardware-wait-polling.patch $TOP_DIR/meta-woden/recipes-kernel/linux/files
    cp $COMMON_DIR_PATH/patches/0001-disable-psci-checker.patch $TOP_DIR/meta-woden/recipes-kernel/linux/files
    cp $COMMON_DIR_PATH/patches/0008-acpi-iort-memory-access-flag-update.patch $TOP_DIR/meta-woden/recipes-acs/fwts/files

}

copy_recipes
customise_image
