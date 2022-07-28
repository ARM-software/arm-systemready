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

create_scripts_link()
{
 ln -sf $TOP_DIR/../../common/scripts/build-all-arm.sh           $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/build-uefi-arm.sh          $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/build-linux-arm.sh         $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/build-grub-arm.sh          $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/build-busybox-arm.sh       $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/make_image-arm.sh          $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/bbr-acs/common/scripts/build-sct-arm.sh         $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/bbr-acs/common/scripts/build-fwts-arm.sh        $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/bbr-acs/common/scripts/build-uefi-apps-arm.sh   $TOP_DIR/build-scripts

 ln -sf $TOP_DIR/../../common/scripts/framework.sh               $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/parse_params.sh            $TOP_DIR/build-scripts
 ln -sf $TOP_DIR/../../common/scripts/cross_toolchain-arm.sh     $TOP_DIR/build-scripts
}

init_dir()
{
    rm -rf $TOP_DIR/ramdisk
    rm -rf $TOP_DIR/build-scripts/config
    cp -r $TOP_DIR/../../common/ramdisk                         $TOP_DIR
    cp -r $TOP_DIR/../../common/config                          $TOP_DIR/build-scripts
}

create_scripts_link
init_dir


source ./build-scripts/build-all-arm.sh  IR F
source ./build-scripts/make_image-arm.sh IR
