#!/bin/bash

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
GCC=tools/gcc-linaro-7.5.0-2019.12-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-
export CROSS_COMPILE=$TOP_DIR/$GCC
export KERNEL_SRC=$TOP_DIR/linux-5.10/out
LINUX_PATH=$TOP_DIR/linux-5.10
BSA_PATH=$TOP_DIR/edk2/ShellPkg/Application/bsa-acs

build_bsa_kernel_driver()
{
 pushd $TOP_DIR/linux-acs/bsa-acs-drv/files
 ./setup.sh $TOP_DIR/edk2/ShellPkg/Application/bsa-acs
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
  cp $TOP_DIR/linux-acs/bsa-acs-drv/files/bsa_acs.ko $TOP_DIR/ramdisk/linux-bsa
  cp $BSA_PATH/linux_app/bsa-acs-app/bsa $TOP_DIR/ramdisk/linux-bsa
}

build_bsa_kernel_driver
build_bsa_app
pack_in_ramdisk

