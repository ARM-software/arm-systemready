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

TOP_DIR=`pwd`

create_scripts_link()
{
 ln -s $TOP_DIR/bbr-acs/common/scripts/build-sct.sh             $TOP_DIR/build-scripts/build-sct.sh
 ln -s $TOP_DIR/bbr-acs/common/scripts/build-uefi-apps.sh       $TOP_DIR/build-scripts/build-uefi-apps.sh
}

init_dir()
{
 rm -rf $TOP_DIR/ramdisk
 rm -rf $TOP_DIR/build-scripts/config
 rm -rf $TOP_DIR/uefi_scripts
 cp -r $TOP_DIR/../common/linux_scripts                $TOP_DIR/ramdisk
 cp -r $TOP_DIR/../common/config                       $TOP_DIR/build-scripts
 cp -r $TOP_DIR/../common/uefi_scripts                 $TOP_DIR/uefi_scripts 
 mkdir -p $TOP_DIR/output
}

create_scripts_link
init_dir

source ./build-scripts/build-all.sh  systemready-band F
source ./build-scripts/make_image.sh systemready-band


