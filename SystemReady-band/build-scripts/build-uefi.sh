#!/bin/sh

# @file
# Copyright (c) 2021-2025, Arm Limited or its affiliates. All rights reserved.
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

#
# This script uses the following environment variables from the variant
#
# VARIANT - build variant name
# TOP_DIR - workspace root directory
# CROSS_COMPILE - PATH to GCC including CROSS-COMPILE prefix
# PARALLELISM - number of cores to build across
# UEFI_BUILD_ENABLED - Flag to enable building UEFI
# UEFI_PATH - sub-directory containing UEFI code
# UEFI_BUILD_MODE - DEBUG or RELEASE
# UEFI_TOOLCHAIN - Toolchain supported by Linaro uefi-tools
# UEFI_PLATFORMS - List of platforms to build
# UEFI_PLAT_{platform name} - array of platform parameters:
#     - platname - the name of the platform used by the build
#     - makefile - the makefile to execute for this platform
#     - output - where to store the files in packaging phase
#     - defines - extra platform defines during the build
#     - binary - what to call the final output binary


TOP_DIR=`pwd`
arch=$(uname -m)
. $TOP_DIR/../common/config/systemready-band-source.cfg
UEFI_PATH=edk2
UEFI_TOOLCHAIN=GCC5
UEFI_BUILD_MODE=RELEASE
PATCH_DIR=$TOP_DIR/../patches
KEYS_DIR=$TOP_DIR/bbsr-keys
UEFI_SHELL_PATH=edk2/Build/Shell/RELEASE_GCC5/AARCH64

 if [[ $arch != "aarch64" ]]; then
    CROSS_COMPILE=$TOP_DIR/$GCC
fi

do_build()
{
    pushd $TOP_DIR/$UEFI_PATH
    if [[ $arch != "aarch64" ]]; then
        CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
        PATH="$PATH:$CROSS_COMPILE_DIR"
    fi
    source ./edksetup.sh
    make -C BaseTools
    export EDK2_TOOLCHAIN=$UEFI_TOOLCHAIN

    if [[ $arch = "aarch64" ]]; then
        echo "arm64 native build"
    else
        CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
        PATH="$PATH:$CROSS_COMPILE_DIR"
        export ${UEFI_TOOLCHAIN}_AARCH64_PREFIX=$CROSS_COMPILE
    fi
    local vars=
    export PACKAGES_PATH=$TOP_DIR/$UEFI_PATH
    export PYTHON_COMMAND=/usr/bin/python3
    git checkout  ShellPkg/ShellPkg.dsc #build shell with default file
    build -a AARCH64 -t GCC5 -p ShellPkg/ShellPkg.dsc -b $UEFI_BUILD_MODE -n $PARALLELISM
    popd
}

do_clean()
{
    pushd $TOP_DIR/$UEFI_PATH
    if [[ $arch != "aarch64" ]]; then
        CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
        PATH="$PATH:$CROSS_COMPILE_DIR"
    fi
    source ./edksetup.sh
    make -C BaseTools clean
    if patch -R -p0 -s -f --dry-run < $PATCH_DIR/bsa.patch; then
        patch  -R -p0  < $PATCH_DIR/bsa.patch
    fi
    rm -rf Build/Shell/RELEASE_GCC5
    popd
}

do_package ()
{
    echo "Packaging uefi... $VARIANT";

    echo "Signing Shell Application... "
    pushd $TOP_DIR
    # sign Shell.efi with db key
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt $TOP_DIR/$UEFI_SHELL_PATH/Shell_EA4BB293-2D7F-4456-A681-1F22F42CD0BC.efi --output $TOP_DIR/$UEFI_SHELL_PATH/Shell_EA4BB293-2D7F-4456-A681-1F22F42CD0BC.efi

    popd

}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
