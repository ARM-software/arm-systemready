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

get_linux_src()
{
    git clone --depth 1 --branch v5.10 https://github.com/torvalds/linux.git linux-5.10
}

get_busybox_src()
{
    git clone https://git.busybox.net/busybox/
    pushd $TOP_DIR/busybox
    git checkout 1_31_stable
    popd
}

get_uefi_src()
{
    git clone --depth 1 --single-branch \
    --branch edk2-stable202102 https://github.com/tianocore/edk2.git
    pushd $TOP_DIR/edk2
    git submodule update --init
    popd
}

get_cross_compiler()
{
    LINARO=https://releases.linaro.org/components/toolchain/binaries
    VERSION=7.5-2019.12
    GCC=aarch64-linux-gnu/gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz
    mkdir -p tools
    pushd $TOP_DIR/tools
    wget $LINARO/$VERSION/$GCC
    tar -xf gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz
    rm gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu.tar.xz
    popd
}

get_grub_src()
{
    git clone https://git.savannah.gnu.org/git/grub.git
    pushd $TOP_DIR/grub
    git submodule update --init
    popd
}
get_fwts_src()
{
    git clone --depth 1 --single-branch --branch V21.03.00 https://git.launchpad.net/fwts
    pushd $TOP_DIR/fwts
    git submodule update --init
    popd
}
get_sct_src()
{
    git clone --single-branch --branch security-extension-acs-beta0 https://github.com/stuyoder/edk2-test.git  edk2-test
    pushd $TOP_DIR/edk2-test
    popd
}

get_efitools_src()
{
  git clone --branch v1.9.2 https://kernel.googlesource.com/pub/scm/linux/kernel/git/jejb/efitools
}

get_bbr_acs_src()
{
  git clone  --single-branch --branch security-extension-acs-beta0 https://github.com/stuyoder/bbr-acs.git bbr-acs
}

sudo apt install git curl mtools gdisk gcc\
 openssl automake autotools-dev libtool bison flex\
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint\
 sbsigntool uuid-runtime monkeysphere make g++ gnu-efi\
 libfile-slurp-perl help2man

get_uefi_src
get_bbr_acs_src
get_sct_src
get_grub_src
get_busybox_src
get_linux_src
get_cross_compiler
get_fwts_src
get_efitools_src
