#!/bin/sh

# @file
# Copyright (c) 2021-2024, Arm Limited or its affiliates. All rights reserved.
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
. $TOP_DIR/../common/config/systemready-band-source.cfg

export KERNEL_SRC=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}/out
LINUX_PATH=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}
BSA_PATH=$TOP_DIR/edk2/ShellPkg/Application/bsa-acs

build_bsa_kernel_driver()
{
 pushd $TOP_DIR/linux-acs/acs-drv/files
 rm -rf $TOP_DIR/linux-acs/acs-drv/files/val
 rm -rf $TOP_DIR/linux-acs/acs-drv/files/test_pool

 arch=$(uname -m)
    echo $arch
    if [[ $arch = "aarch64" ]]
    then
        echo "arm64 native build"
        export CROSS_COMPILE=''
    else
        export CROSS_COMPILE=$TOP_DIR/$GCC
    fi
 ./bsa_setup.sh $TOP_DIR/edk2/ShellPkg/Application/bsa-acs
 ./linux_bsa_acs.sh
 popd
}


build_bsa_app()
{
 pushd $BSA_PATH/linux_app/bsa-acs-app
 make clean
 make
 popd
}

pack_in_ramdisk()
{
  if [ ! -d $TOP_DIR/ramdisk/linux-bsa ]; then
    mkdir $TOP_DIR/ramdisk/linux-bsa
  fi
  cp $TOP_DIR/linux-acs/acs-drv/files/bsa_acs.ko $TOP_DIR/ramdisk/linux-bsa
  cp $BSA_PATH/linux_app/bsa-acs-app/bsa $TOP_DIR/ramdisk/linux-bsa
}

build_bsa_kernel_driver
build_bsa_app
pack_in_ramdisk

