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

TOP_DIR=`pwd`
. $TOP_DIR/../../common/config/common_config.cfg
#The shell variables use in this file are defined in common_config.cfg

export GIT_SSL_NO_VERIFY=1

get_linux_src()
{
    echo "Downloading Linux source code. Version : $LINUX_KERNEL_VERSION"
    git clone --depth 1 --branch v$LINUX_KERNEL_VERSION https://github.com/torvalds/linux.git linux-${LINUX_KERNEL_VERSION}
}

get_busybox_src()
{
    echo "Downloading Busybox source code. TAG : $BUSYBOX_SRC_VERSION"
    git clone https://git.busybox.net/busybox/
    pushd $TOP_DIR/busybox
    git checkout $BUSYBOX_SRC_VERSION
    popd
}

get_uefi_src()
{
    echo "Downloading EDK2 source code. TAG : $EDK2_SRC_VERSION"
    git clone --depth 1 --single-branch \
    --branch $EDK2_SRC_VERSION https://github.com/tianocore/edk2.git
    pushd $TOP_DIR/edk2
    git submodule update --init
    popd
}

get_bsa_src()
{
    pushd $TOP_DIR/edk2
    git clone https://github.com/tianocore/edk2-libc
    if [ -z $ARM_BSA_TAG ]; then
        #No TAG is provided. Download the latest code
        echo "Downloading Arm BSA source code."
        git clone --depth 1 https://github.com/ARM-software/bsa-acs.git ShellPkg/Application/bsa-acs
    else
        echo "Downloading Arm BSA source code. TAG : $ARM_BSA_TAG"
        git clone --depth 1 --branch $ARM_BSA_TAG https://github.com/ARM-software/bsa-acs.git ShellPkg/Application/bsa-acs
    fi
    popd
    pushd  $TOP_DIR/edk2/ShellPkg/Application/bsa-acs
    git pull
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
get_fwts_src()
{
    echo "Downloading FWTS source code. TAG : ${FWTS_SRC_TAG}"
    git clone --single-branch https://git.launchpad.net/fwts
    pushd $TOP_DIR/fwts
    git checkout $FWTS_SRC_TAG
    git submodule update --init
    popd
}
get_sct_src()
{
    echo "Downloading SCT (edk2-test) source code. TAG : ${SCT_SRC_TAG}"
    git clone --single-branch https://github.com/tianocore/edk2-test
    pushd $TOP_DIR/edk2-test
    git checkout $SCT_SRC_TAG
    popd
}


get_linux-acs_src()
{
  if [ -z $ARM_LINUX_ACS_TAG ]; then
      echo "Downloading Arm Linux ACS source code."
      git clone --depth 1 https://gitlab.arm.com/linux-arm/linux-acs linux-acs
  else
      echo "Downloading Arm Linux ACS source code. TAG : ${ARM_LINUX_ACS_TAG}"
      git clone --depth 1 --branch ${ARM_LINUX_ACS_TAG} https://gitlab.arm.com/linux-arm/linux-acs linux-acs
  fi
  pushd $TOP_DIR/linux-${LINUX_KERNEL_VERSION}
  echo "Applying Linux ACS Patch..."
  git am $TOP_DIR/linux-acs/kernel/src/0001-BSA-ACS-Linux-${LINUX_KERNEL_VERSION}.patch
  popd

}

get_bbr_acs_src()
{
   if [ -z $ARM_BBR_TAG ]; then
       #No TAG is provided. Download the latest code
       echo "Downloading Arm BBR source code."
       git clone  --depth 1 https://github.com/ARM-software/bbr-acs.git bbr-acs
   else
       echo "Downloading Arm BBR source code. TAG: $ARM_BBR_TAG"
       git clone  --depth 1 --branch $ARM_BBR_TAG https://github.com/ARM-software/bbr-acs.git bbr-acs
   fi
}

sudo apt install git curl mtools gdisk gcc\
 openssl automake autotools-dev libtool bison flex\
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint \
 make gcc g++ python

get_uefi_src
get_bsa_src
get_bbr_acs_src
get_sct_src
get_grub_src
get_busybox_src
get_linux_src
get_cross_compiler
get_fwts_src
get_linux-acs_src
