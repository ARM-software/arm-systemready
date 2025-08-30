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
. $TOP_DIR/../common/config/systemready-band-source.cfg
UEFI_PATH=edk2
UEFI_TOOLCHAIN=GCC
UEFI_BUILD_MODE=RELEASE
CROSS_COMPILE=$TOP_DIR/$GCC
UEFI_LIBC_PATH=edk2-libc
OUTDIR=${TOP_DIR}/output
SBSA_EFI_PATH=edk2/Build/Shell/DEBUG_GCC/AARCH64/
KEYS_DIR=$TOP_DIR/bbsr-keys

do_build()
{
    pushd $TOP_DIR/$UEFI_PATH
    source ./edksetup.sh
    make -C BaseTools/Source/C
    export EDK2_TOOLCHAIN=$UEFI_TOOLCHAIN
    arch=$(uname -m)
    if [[ $arch = "aarch64" ]]
    then
        echo "arm64 native compile"
    else
        CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
        PATH="$PATH:$CROSS_COMPILE_DIR"
        export ${UEFI_TOOLCHAIN}_AARCH64_PREFIX=$CROSS_COMPILE
    fi

    export PACKAGES_PATH=$TOP_DIR/$UEFI_PATH:$TOP_DIR/$UEFI_PATH/$UEFI_LIBC_PATH
    source ShellPkg/Application/sysarch-acs/tools/scripts/acsbuild.sh sbsa
    popd
}

do_clean()
{
    pushd $TOP_DIR/$UEFI_PATH
    CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
    PATH="$PATH:$CROSS_COMPILE_DIR"
    source ./edksetup.sh
    make -C BaseTools/Source/C clean
    rm -rf Build/Shell/DEBUG_GCC
    popd
}

do_package ()
{
    echo "Packaging SBSA...";
    # Copy binaries to output folder
    cp $TOP_DIR/$SBSA_EFI_PATH/Sbsa.efi $OUTDIR/Sbsa.efi
    # sign Sbsa.efi with db key
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt $OUTDIR/Sbsa.efi --output $OUTDIR/Sbsa.efi
}

exit_fun() {
   exit 1 # Exit script
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

source $DIR/framework.sh $@

