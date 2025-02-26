#!/usr/bin/env bash

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

set -x
TOP_DIR=`pwd`
pushd $TOP_DIR/meta-woden
kas shell kas/woden.yml
bitbake llvm-native
if [ $? -eq 1 ]; then
    echo "llvm-native recipe failed"
    exit
fi
bitbake rust-native
if [ $? -eq 1 ]; then
    echo "rust-native recipe failed"
    exit
fi
bitbake glibc
if [ $? -eq 1 ]; then
    echo "glibc recipe failed"
    exit
fi
bitbake glibc-locale
if [ $? -eq 1 ]; then
    echo "glibc-locale recipe failed"
    exit
fi
bitbake qemu-system-native
if [ $? -eq 1 ]; then
    echo "qemu-system-native recipe failed"
    exit
fi
bitbake woden-image
if [ $? -eq 0 ]; then
    if [ -f $TOP_DIR/meta-woden/build/tmp/deploy/images/genericarm64/woden-image-genericarm64.rootfs.wic ]; then
      cd $TOP_DIR/meta-woden/build/tmp/deploy/images/genericarm64
      rm systemready-dt-acs_live_image.wic.xz 2> /dev/null
      cp woden-image-genericarm64.rootfs.wic systemready-dt_acs_live_image.wic
      xz -z systemready-dt_acs_live_image.wic
      echo "The built image is at $TOP_DIR/meta-woden/build/tmp/deploy/images/genericarm64/systemready-dt_acs_live_image.wic.xz"
    fi
fi
popd

