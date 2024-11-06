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

if [ "$#" -ne 2 ]; then
    echo "Usage $0 systemready-band F"
    echo "The second (mandatory) parameter F stands for full package."
    exit 1
fi

# Build SystemReady-band ACS
BAND=$1
PACKAGE=$2

source ./build-scripts/build-efitools.sh
source ./build-scripts/build-bbsr-keys.sh
source ./build-scripts/build-uefi.sh $@
source ./build-scripts/build-bsaefi.sh $@
source ./build-scripts/build-sbsaefi.sh $@
source ./build-scripts/build-sct.sh SBBR $2
source ./build-scripts/build-uefi-apps.sh $@
source ./build-scripts/build-linux.sh $@
source ./build-scripts/build-linux-bsa.sh $@
source ./build-scripts/build-grub.sh $@
source ./build-scripts/build-sbsa-buildroot.sh $@
source ./build-scripts/build-linux-sbsa.sh $@
source ./build-scripts/build-buildroot.sh $@
