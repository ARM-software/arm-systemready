#!/usr/bin/env bash

# @file
# Copyright (c) 2022-2024, Arm Limited or its affiliates. All rights reserved.
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
kas build kas/woden.yml
if [ $? -eq 0 ]; then
    if [ -f $TOP_DIR/meta-woden/build/tmp/deploy/images/genericarm64/woden-image-genericarm64.rootfs.wic ]; then
      cd $TOP_DIR/meta-woden/build/tmp/deploy/images/genericarm64
      rm ir-acs-live-image-genericarm64.wic.xz 2> /dev/null
      cp woden-image-genericarm64.rootfs.wic ir-acs-live-image-genericarm64.wic
      xz -z ir-acs-live-image-genericarm64.wic
      echo "The built image is at $TOP_DIR/meta-woden/build/tmp/deploy/images/genericarm64/ir-acs-live-image-genericarm64.wic.xz"
    fi
fi
popd

