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
    git clone --single-branch https://github.com/tianocore/edk2-test
    pushd $TOP_DIR/edk2-test
    git checkout 421a6997ef362c6286c4ef87d21d5367a9d1fb58
    echo "Applying security-extension ACS patch..."
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0001-uefi-sct-SctPkg-Secure-Boot-add-variable-size-test.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0002-uefi-sct-SctPkg-add-test-infrastructure-for-Secure-B.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0003-uefi-sct-SctPkg-add-dependency-infrastructure-for-Se.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0004-uefi-sct-SctPkg-sign-the-.efi-images.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0005-uefi-sct-SctPkg-add-variable-attributes-Secure-Boot-.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0006-uefi-sct-SctPkg-support-.auth-files-in-creating-the-.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0007-uefi-sct-SctPkg-add-initial-Secure-Boot-variable-upd.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0008-uefi-sct-SctPkg-TCG2-Protocol-add-header-with-TCG2-p.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0009-uefi-sct-SctPkg-TCG2-Protocol-add-GetCapability-Test.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0010-uefi-sct-SctPkg-TCG2-Protocol-add-GetActivePcrBanks-.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0011-uefi-sct-SctPkg-TCG2-Protocol-add-HashLogExtendEvent.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0012-uefi-sct-SctPkg-TCG2-Protocol-add-GetEventLog-test.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0013-uefi-sct-SctPkg-TCG2-Protocol-add-SubmitCommand-test.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0014-uefi-sct-SctPkg-Secure-Boot-verify-update-of-db-vari.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0015-uefi-sct-SctPkg-SecureBoot-verify-update-of-db-signe.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0016-uefi-sct-SctPkg-Secure-Boot-verify-update-of-dbx-var.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0017-uefi-sct-SctPkg-Secure-Boot-verify-db-update-by-2nd-.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0018-uefi-sct-SctPkg-Secure-Boot-move-SB-variable-cleanup.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0019-uefi-sct-SctPkg-Secure-Boot-add-image-loading-test.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0020-security-extension-updates-to-image-generation.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0021-security-extension-add-assertions-2-5-for-image-load.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0022-security-extension-add-checkpoint2-to-image-loading.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0023-uefi-sct-SctPkg-Secure-Boot-fix-image-generation-for.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0024-security-extension-add-check-of-Image-Execution-Info.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0025-uefi-sct-SctPkg-add-additional-Secure-Boot-variable-.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0026-uefi-sct-SctPkg-add-additional-Secure-Boot-variable-.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0027-uefi-sct-SctPkg-Secure-Boot-init-secure-boot-variabl.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0028-uefi-sct-SctPkg-Secure-Boot-fix-some-typos-in-variab.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0029-uefi-sct-SctPkg-Secure-Boot-rename-dependency-dir-to.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0030-uefi-sct-SctPkg-Secure-Boot-improve-image-loading-te.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0031-uefi-sct-SctPkg-Secure-Boot-remove-image-load-test-a.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0032-uefi-sct-SctPkg-Secure-Boot-fix-image-name-consisten.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0033-uefi-sct-SctPkg-Secure-Boot-Add-Arm-2021-copyright-d.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0034-uefi-sct-SctPkg-Secure-Boot-fixes-to-creation-of-KEK.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0035-uefi-sct-SctPkg-Secure-Boot-increase-future-date-var.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0036-uefi-sct-SctPkg-Remove-warnings-in-TCG2-protocol-tes.patch
    git apply -p1 < $TOP_DIR/bbr-acs/bbsr/patches/0037-uefi-sct-SctPkg-Secure-Boot-fix-unused-variable-warn.patch
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
   git clone  --single-branch --branch security-extension-acs https://github.com/ARM-software/bbr-acs.git bbr-acs
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
