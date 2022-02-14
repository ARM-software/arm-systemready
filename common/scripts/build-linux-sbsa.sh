#!/bin/bash

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
TOP_DIR=`pwd`
. $TOP_DIR/../../common/config/sr_common_config.cfg

export KERNEL_SRC=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}/out
LINUX_PATH=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}
SBSA_PATH=$TOP_DIR/edk2/ShellPkg/Application/sbsa-acs

build_sbsa_kernel_driver()
{
 pushd $TOP_DIR/linux-acs/sbsa-acs-drv/files
    arch=$(uname -m)
    echo $arch
    if [[ $arch = "aarch64" ]]
    then
        echo "arm64 native build"
        export CROSS_COMPILE=''
    else
        GCC=tools/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-
        export CROSS_COMPILE=$TOP_DIR/$GCC
    fi
 ./setup.sh $TOP_DIR/edk2/ShellPkg/Application/sbsa-acs
 ./linux_sbsa_acs.sh
 popd
}


build_sbsa_app()
{
 pushd $SBSA_PATH/linux_app/sbsa-acs-app
 make clean
 make
 popd
}

pack_in_ramdisk()
{
  if [ ! -d $TOP_DIR/ramdisk/linux-sbsa ]; then
    mkdir $TOP_DIR/ramdisk/linux-sbsa
  fi
  cp $TOP_DIR/linux-acs/sbsa-acs-drv/files/sbsa_acs.ko $TOP_DIR/ramdisk/linux-sbsa
  cp $SBSA_PATH/linux_app/sbsa-acs-app/sbsa $TOP_DIR/ramdisk/linux-sbsa
}

build_sbsa_kernel_driver
build_sbsa_app
pack_in_ramdisk

