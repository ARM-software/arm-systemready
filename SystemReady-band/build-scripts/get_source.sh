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

TOP_DIR=`pwd`
TARGET_ARCH="aarch64"

#Get the band run from automatically
pushd ..
BAND_PATH=`pwd`
popd

. $TOP_DIR/../common/config/systemready-band-source.cfg

export GIT_SSL_NO_VERIFY=1

get_linux_src()
{
    echo "Downloading Linux source code. Version : $LINUX_KERNEL_VERSION"
    git clone --depth 1 --branch v$LINUX_KERNEL_VERSION https://github.com/torvalds/linux.git linux-${LINUX_KERNEL_VERSION}
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download Linux source code"
        exit 1
    fi
}

get_uefi_src()
{
    echo "Downloading EDK2 source code. TAG : $EDK2_SRC_VERSION"
    git clone --depth 1 --single-branch --branch $EDK2_SRC_VERSION https://github.com/tianocore/edk2.git
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download edk2 source code"
        exit 1
    fi
    pushd $TOP_DIR/edk2
    git submodule update --init
    popd
}

get_sysarch_acs_src()
{
    pushd $TOP_DIR/edk2
    git clone https://github.com/tianocore/edk2-libc
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download edk2 libc source code"
        exit 1
    fi

    if [ -z $SYS_ARCH_ACS_TAG ]; then
        #No TAG is provided. Download the latest code
        echo "Downloading Arm SYSARCH-ACS source code."
        git clone --depth 1 https://github.com/ARM-software/sysarch-acs.git ShellPkg/Application/sysarch-acs
    else
        echo "Downloading Arm SYSARCH-ACS source code. TAG : $SYS_ARCH_ACS_TAG"
        git clone --depth 1 --branch $SYS_ARCH_ACS_TAG https://github.com/ARM-software/sysarch-acs.git ShellPkg/Application/sysarch-acs
    fi
    popd
    pushd  $TOP_DIR/edk2/ShellPkg/Application/sysarch-acs
    git pull
    popd
}

get_cross_compiler()
{
    if [ $(uname -m) == "aarch64" ]; then
        echo "=================================================================="
        echo "aarch64 native build"
        echo "WARNING: no cross compiler needed, GCC version recommended: ${GCC_TOOLS_VERSION}"
        echo "=================================================================="
    else
        echo "Downloading cross compiler. Version : ${GCC_TOOLS_VERSION}"
        TAG=aarch64-none-linux-gnu
        mkdir -p tools
        pushd $TOP_DIR/tools
        wget $CROSS_COMPILER_URL --no-check-certificate
	if [ $? -ne 0 ]; then
            echo "Error: Failed to dowload toolchain"
            exit 1
        fi
        tar -xf arm-gnu-toolchain-${GCC_TOOLS_VERSION}-x86_64-${TAG}.tar.xz
	mv arm-gnu-toolchain-13.2.Rel1-x86_64-aarch64-none-linux-gnu arm-gnu-toolchain-13.2.rel1-x86_64-aarch64-none-linux-gnu
        rm arm-gnu-toolchain-${GCC_TOOLS_VERSION}-x86_64-${TAG}.tar.xz
        popd
    fi
}

get_grub_src()
{
    echo "Downloading grub source code,Version: ${GRUB_SRC_TAG}"
    git clone -b $GRUB_SRC_TAG https://github.com/rhboot/grub2.git grub
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download Grub source code"
        exit 1
    fi
    pushd $TOP_DIR/grub
    git submodule update --init
    popd
}

get_sct_src()
{
    echo "Downloading SCT (edk2-test) source code. TAG : ${SCT_SRC_TAG}"
    git clone --single-branch https://github.com/tianocore/edk2-test
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download sct source code"
        exit 1
    fi
    pushd $TOP_DIR/edk2-test
    git checkout $SCT_SRC_TAG
    popd
}

get_linux-acs_src()
{
  if [ -z $ARM_LINUX_ACS_TAG ]; then
      echo "Downloading Arm Linux ACS source code."
      git clone --depth 1 https://gitlab.arm.com/linux-arm/linux-acs.git linux-acs
  else
      echo "Downloading Arm Linux ACS source code. TAG : ${ARM_LINUX_ACS_TAG}"
      git clone --depth 1 --branch ${ARM_LINUX_ACS_TAG} https://gitlab.arm.com/linux-arm/linux-acs.git linux-acs
  fi

    pushd $TOP_DIR/linux-${LINUX_KERNEL_VERSION}
    git am $TOP_DIR/../common/patches/0001-SystemReady-Linux-${LINUX_KERNEL_VERSION}.patch
    git am $TOP_DIR/../common/patches/0001-disable-psci-checker.patch

    #apply patches to linux source
    if [ $LINUX_KERNEL_VERSION == "6.4" ]; then
        git am $TOP_DIR/../common/patches/tpm-tis-spi-Add-hardware-wait-polling.patch
    fi
    popd

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

get_sbmr_acs_src()
{
    echo "Downloading sbmr-acs source code."
    git clone --depth 1 https://github.com/ARM-software/sbmr-acs sbmr-acs
    pushd $TOP_DIR/sbmr-acs
        git archive --format=tar.gz -o sbmr-acs.tar.gz main
    popd
}

get_buildroot_src()
{
    echo "Downloading Buildroot source code. TAG : $BUILDROOT_SRC_VERSION"
    #git clone -b $BUILDROOT_SRC_VERSION https://git.busybox.net/buildroot/
    #TODO  git clone was failing with busybox url, try gitlab
    git clone -b $BUILDROOT_SRC_VERSION https://gitlab.com/buildroot.org/buildroot.git
    if [ $? -ne 0 ]; then
        echo "Error: Failed to download buildroot source code"
        exit 1
    fi
    pushd $TOP_DIR/buildroot/package/fwts
        echo "Applying Buildroot FWTS patch..."
        # patch buildroot config
        git apply $TOP_DIR/../common/patches/build_fwts_version_25.01.00.patch
    popd
    pushd $TOP_DIR/buildroot
        echo "Applying Buildroot SBMR-ACS patch..."
        git apply $TOP_DIR/patches/build_sbmr_acs.patch
        #This patch is to update dmidecode to v3.6 , which is a SBMR requirment.
        git apply $TOP_DIR/patches/0001-dmidecode-version-3.6.patch
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

get_edk2-test-parser_src()
{
    echo "Downloading edk2-test-parser source code. TAG : $EDK2_TEST_PARSER_TAG"
    git clone https://git.gitlab.arm.com/systemready/edk2-test-parser.git
    pushd $TOP_DIR/edk2-test-parser/
    git checkout $EDK2_TEST_PARSER_TAG
    popd
}

source /etc/lsb-release

sudo apt install git curl mtools gdisk gcc \
 openssl automake autotools-dev libtool bison flex\
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint \
 make g++ build-essential wget gettext dosfstools unzip \
 sbsigntool uuid-runtime monkeysphere gnu-efi \
 libfile-slurp-perl help2man libbsd-dev -y

REL="${DISTRIB_RELEASE//[!0-9]/}"
MAJORREL=${REL:0:2}

if [ $MAJORREL -gt 18 ]; then
    sudo apt install python-is-python3 -y
else
    sudo apt install python -y
fi


get_uefi_src
get_efitools_src
get_sct_src
get_sysarch_acs_src
get_bbr_acs_src
get_buildroot_src
get_cross_compiler
get_edk2-test-parser_src
get_grub_src
get_linux_src
get_linux-acs_src
get_sbmr_acs_src
