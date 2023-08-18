#!/usr/bin/env bash

# Copyright (c) 2021-2023, ARM Limited and Contributors. All rights reserved.
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

#Optional argument 'arm' shall be set when targeting a 32bit Arm device
if [ "$1" == "arm" ]; then
    TARGET_ARCH="arm"
else
    TARGET_ARCH="aarch64"
fi

#Get the band run from automatically
pushd ..
BAND_PATH=`pwd`
BAND=`basename $BAND_PATH`
popd

echo "Getting the sources for $BAND "

if [ $BAND == "SR" ] || [ $BAND == "ES" ]; then
    . $TOP_DIR/../../common/config/sr_es_common_config.cfg
else
    . $TOP_DIR/../../common/config/common_config.cfg
fi


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

get_sbsa_src()
{
    pushd $TOP_DIR/edk2
    git clone https://github.com/tianocore/edk2-libc
    if [ -z $ARM_SBSA_TAG ]; then
        #No TAG is provided. Download the latest code
        echo "Downloading Arm SBSA source code."
        git clone --depth 1 https://github.com/ARM-software/sbsa-acs.git ShellPkg/Application/sbsa-acs
    else
        echo "Downloading Arm SBSA source code. TAG : $ARM_SBSA_TAG"
        git clone --depth 1 --branch $ARM_SBSA_TAG https://github.com/ARM-software/sbsa-acs.git ShellPkg/Application/sbsa-acs
    fi
    popd
    pushd  $TOP_DIR/edk2/ShellPkg/Application/sbsa-acs
    git pull
    popd
}


get_cross_compiler()
{
    if [ $(uname -m) == "aarch64" ]; then
        echo "=================================================================="
        echo "aarch64 native build"
        echo "WARNING: no cross compiler needed, GCC version recommended: ${LINARO_TOOLS_MAJOR_VERSION}"
        echo "=================================================================="
    else
        echo "Downloading TOOLS Linaro cross compiler. Version : ${LINARO_TOOLS_VERSION}"
        LINARO=https://releases.linaro.org/components/toolchain/binaries
        VERSION=$LINARO_TOOLS_MAJOR_VERSION
        if [ $TARGET_ARCH == "arm" ]; then
            TAG=arm-linux-gnueabihf
        else
            TAG=aarch64-linux-gnu
        fi
        GCC=${TAG}/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_${TAG}.tar.xz
        mkdir -p tools
        pushd $TOP_DIR/tools
        wget $LINARO/$VERSION/$GCC
        tar -xf gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_${TAG}.tar.xz
        rm gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_${TAG}.tar.xz
        popd
    fi
}

get_cross_compiler2()
{
    if [ $(uname -m) == "aarch64" ]; then
        echo "=================================================================="
        echo "aarch64 native build"
        echo "WARNING: no cross compiler needed, GCC version recommended: ${GCC_TOOLS_VERSION}"
        echo "=================================================================="
    else
        echo "Downloading cross compiler. Version : ${GCC_TOOLS_VERSION}"
        if [ $TARGET_ARCH == "arm" ]; then
            TAG=arm-linux-gnueabihf
        else
            TAG=aarch64-none-linux-gnu
        fi
        mkdir -p tools
        pushd $TOP_DIR/tools
        wget $CROSS_COMPILER_URL
        tar -xf gcc-arm-${GCC_TOOLS_VERSION}-x86_64-${TAG}.tar.xz
        rm gcc-arm-${GCC_TOOLS_VERSION}-x86_64-${TAG}.tar.xz
        popd
    fi
}


get_grub_src()
{
    echo "Downloading grub source code,Version: ${GRUB_SRC_TAG}"
    git clone -b $GRUB_SRC_TAG https://github.com/rhboot/grub2.git grub
    pushd $TOP_DIR/grub
    git submodule update --init
    popd
}
get_fwts_src()
{
    echo "Downloading FWTS source code. TAG : ${FWTS_SRC_TAG}"
    git clone --single-branch git://kernel.ubuntu.com/hwe/fwts.git
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

  if [ $TARGET_ARCH != "arm" ]; then
    pushd $TOP_DIR/linux-${LINUX_KERNEL_VERSION}
    #The same patch is applicable BSA and SBSA
    echo "Applying Linux ACS xBSA Patch..."
    git am $TOP_DIR/linux-acs/kernel/src/0001-BSA-ACS-Linux-${LINUX_KERNEL_VERSION}.patch
    popd
  fi

}

get_bbr_acs_src()
{
    echo "Downloading Arm BBR source code."
    git clone https://github.com/ARM-software/bbr-acs.git bbr-acs

    if [ -n "$ARM_BBR_TAG" ]; then
        # TAG provided.
        echo "Checking out Arm BBR TAG: $ARM_BBR_TAG"
        git -C bbr-acs checkout $ARM_BBR_TAG
    fi
}

get_buildroot_src()
{
    echo "Downloading Buildroot source code. TAG : $BUILDROOT_SRC_VERSION"
    git clone -b $BUILDROOT_SRC_VERSION http://git.buildroot.net/buildroot
    pushd $TOP_DIR/buildroot/package/fwts
        echo "Applying Buildroot FWTS patch..."
        git apply $TOP_DIR/../../common/patches/build_fwts_version_23.07.00.patch
    popd
}

get_efitools_src()
{
  if [ -z $EFITOOLS_SRC_TAG ]; then
      echo "Downloading EFI tools source code."
      git clone --depth 1 https://kernel.googlesource.com/pub/scm/linux/kernel/git/jejb/efitools
  else
      echo "Downloading EFI tools source code. TAG : ${EFITOOLS_SRC_TAG}"
      git clone --depth 1 --branch ${EFITOOLS_SRC_TAG} https://kernel.googlesource.com/pub/scm/linux/kernel/git/jejb/efitools
  fi
}

source /etc/lsb-release

sudo apt install git curl mtools gdisk gcc \
 openssl automake autotools-dev libtool bison flex\
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint \
 make g++ build-essential wget gettext dosfstools unzip \
 sbsigntool uuid-runtime monkeysphere gnu-efi \
 libfile-slurp-perl help2man -y

REL="${DISTRIB_RELEASE//[!0-9]/}"
MAJORREL=${REL:0:2}

if [ $MAJORREL -gt 18 ]; then
    sudo apt install python-is-python3 -y
else
    sudo apt install python -y
fi

if [ $TARGET_ARCH == "arm" ]; then
    sudo apt-get install libmpc-dev -y
fi

get_uefi_src
get_bsa_src
get_efitools_src

if [ $BAND == "SR" ]; then
    get_sbsa_src
fi


if [ $BAND == "SR" ] || [ $BAND == "ES" ]; then
    get_buildroot_src
    get_cross_compiler2
else
    get_busybox_src
    get_fwts_src
    get_cross_compiler
fi

get_bbr_acs_src
get_sct_src
get_grub_src
get_linux_src
get_linux-acs_src
