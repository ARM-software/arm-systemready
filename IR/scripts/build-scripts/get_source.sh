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

get_bsa_src()
{
    pushd $TOP_DIR/edk2
    git clone https://github.com/tianocore/edk2-libc
    git clone ssh://$USER@ap-gerrit-1.ap01.arm.com:29418/avk/syscomp_bsa ShellPkg/Application/bsa-acs
    popd
    pushd  $TOP_DIR/edk2/ShellPkg/Application/bsa-acs
    git pull
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
    git clone --depth 1 --single-branch --branch V20.11.00 https://git.launchpad.net/fwts
    pushd $TOP_DIR/fwts
    git submodule update --init
    popd
}
get_sct_src()
{
    git clone --single-branch https://github.com/tianocore/edk2-test
    pushd $TOP_DIR/edk2-test
    git checkout 421a6997ef362c6286c4ef87d21d5367a9d1fb58
    popd
}


get_linux-acs_src()
{
  git clone ssh://ap-gerrit-1.ap01.arm.com:29418/avk/syscomp_linux_acs linux-acs
  pushd $TOP_DIR/linux-5.10
  echo "Applying Linux ACS Patch..."
  git am $TOP_DIR/linux-acs/kernel/src/0001-BSA-SBSA-ACS-Linux-5.10.patch
  popd

}


sudo apt install git curl mtools gdisk gcc\
 openssl automake autotools-dev libtool bison flex\
 bc uuid-dev python3 libglib2.0-dev libssl-dev autopoint

get_uefi_src
get_bsa_src
get_sct_src
get_grub_src
get_busybox_src
get_linux_src
get_cross_compiler
get_fwts_src
get_linux-acs_src

