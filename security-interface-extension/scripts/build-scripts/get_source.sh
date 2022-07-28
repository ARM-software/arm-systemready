#!/usr/bin/env bash

# Copyright (c) 2021-2022, ARM Limited and Contributors. All rights reserved.
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

TOP_DIR=`pwd`
. $TOP_DIR/../../common/config/common_config.cfg
#The shell variables use in this file are defined in common_config.cfg

get_uefi_src()
{
    echo "Downloading EDK2 source code. TAG : $EDK2_SRC_VERSION"
    git clone --depth 1 --single-branch \
    --branch $EDK2_SRC_VERSION https://github.com/tianocore/edk2.git
    pushd $TOP_DIR/edk2
    git submodule update --init
    popd
}

get_cross_compiler()
{
    echo "Downloading TOOLS source code. Version : ${LINARO_TOOLS_VERSION}"
    LINARO=https://releases.linaro.org/components/toolchain/binaries
    VERSION=$LINARO_TOOLS_MAJOR_VERSION
    GCC=aarch64-linux-gnu/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu.tar.xz
    mkdir -p tools
    pushd $TOP_DIR/tools
    wget $LINARO/$VERSION/$GCC
    tar -xf gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu.tar.xz
    rm gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu.tar.xz
    popd
}

get_grub_src()
{
    echo "Downloading grub source code."
    git clone https://git.savannah.gnu.org/git/grub.git
    pushd $TOP_DIR/grub
    git submodule update --init
    popd
}

get_sct_src()
{
    git clone --single-branch https://github.com/tianocore/edk2-test
    pushd $TOP_DIR/edk2-test
    git checkout 421a6997ef362c6286c4ef87d21d5367a9d1fb58
    echo "Applying security interface extension ACS patch..."
    cp -r $TOP_DIR/bbr-acs/bbsr/sct-tests/BBSRVariableSizeTest uefi-sct/SctPkg/TestCase/UEFI/EFI/RuntimeServices
    cp -r $TOP_DIR/bbr-acs/bbsr/sct-tests/SecureBoot uefi-sct/SctPkg/TestCase/UEFI/EFI/RuntimeServices
    cp -r $TOP_DIR/bbr-acs/bbsr/sct-tests/TCG2Protocol uefi-sct/SctPkg/TestCase/UEFI/EFI/Protocol
    cp -r $TOP_DIR/bbr-acs/bbsr/sct-tests/TCG2.h uefi-sct/SctPkg/UEFI/Protocol
    patch -p1 <../bbr-acs/bbsr/patches/0001-security-extension-update-edk2-test-to-integrate-sec.patch
    popd
}

get_efitools_src()
{
  git clone --branch v1.9.2 https://kernel.googlesource.com/pub/scm/linux/kernel/git/jejb/efitools
}

get_buildroot_src()
{
  git clone --single-branch git://git.buildroot.net/buildroot
  pushd $TOP_DIR/buildroot
  git checkout $BUILDROOT_SRC_TAG
  echo "Updating buildroot..."
  # uprev tpm2-tools to 5.1.1
  patch -p1 < $TOP_DIR/../../common/config/buildroot/tpm2-tools-5.1.1.patch
  # copy in a customized kernel config
  mkdir -p ./board/arm/system-ready
  cp $TOP_DIR/../../common/config/buildroot/kernel.config ./board/arm/system-ready
  # copy in a customized busybox config
  cp $TOP_DIR/../../common/config/buildroot/busybox.config ./package/busybox/busybox.config
  # copy in a systemready specific defconfig
  cp $TOP_DIR/../../common/config/buildroot/arm_systemready_defconfig ./configs
  # copy in the rootfs overlay
  cp -a $TOP_DIR/../../common/config/buildroot/rootfs-overlay .
  # copy in the fwts ini file
  mkdir -p rootfs-overlay/bin
  cp $TOP_DIR/bbr-acs/bbsr/config/bbsr_fwts_tests.ini rootfs-overlay/bin
  popd
}

get_bbr_acs_src()
{
   git clone  --single-branch --branch security-interface-extension-acs https://github.com/ARM-software/bbr-acs.git bbr-acs
}

sudo apt install git curl mtools gdisk gcc\
 openssl automake autotools-dev libtool bison flex\
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint\
 make gcc g++ python\
 sbsigntool uuid-runtime monkeysphere make g++ gnu-efi\
 libfile-slurp-perl help2man

get_uefi_src
get_bbr_acs_src
get_sct_src
get_grub_src
get_cross_compiler
get_efitools_src
get_buildroot_src
