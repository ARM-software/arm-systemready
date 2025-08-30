#!/bin/bash

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

TOP_DIR=`pwd`
. $TOP_DIR/../common/config/systemready-band-source.cfg

# === Configuration ===
EDK2_TAG="$EDK2_SRC_VERSION"
GCC_VERSION="13.2.rel1"
APP_NAME="parser"
GCC_PREFIX="aarch64-none-linux-gnu-"
TOP_DIR=$(pwd)
TOOLCHAIN_PATH="$TOP_DIR/tools/arm-gnu-toolchain-${GCC_VERSION}-x86_64-aarch64-none-linux-gnu/bin"
GCC_BIN="$TOOLCHAIN_PATH/$GCC_PREFIX"
EDK2_DIR="$TOP_DIR/edk2"
LIBC_DIR="$EDK2_DIR/edk2-libc"
APP_PATH="$EDK2_DIR/ShellPkg/Application/$APP_NAME"
KEYS_DIR=$TOP_DIR/bbsr-keys
CONFIG_PARSER_EFI=${TOP_DIR}/parser/Parser.efi

do_build()
{

mkdir -p $TOP_DIR/$APP_NAME
# === Prepare edk2 environment ===
pushd "$EDK2_DIR"

echo "Cleaning previous builds..."
git reset --hard
#git reset --hard
rm -rf Build/*

echo "Applying patches..."
git apply "$TOP_DIR/../common/patches/0001-parser-app.patch"

echo "Setting up parser_app source..."
rm -rf "$APP_PATH"
cp -r "$TOP_DIR/../common/parser" "$APP_PATH"

echo "Setting environment variables..."
export GCC_AARCH64_PREFIX="$GCC_BIN"
export PACKAGES_PATH="$EDK2_DIR:$LIBC_DIR"

echo "packages path : $PACKAGES_PATH"
# === Build ===
echo "Configuring EDK2 build environment..."
source ./edksetup.sh --reconfig
make -C BaseTools/Source/C

echo "Building Parser.efi..."
build -a AARCH64 -t GCC -p ShellPkg/ShellPkg.dsc -m ShellPkg/Application/$APP_NAME/Parser.inf

cp "$EDK2_DIR/Build/Shell/DEBUG_GCC/AARCH64/Parser.efi" "$TOP_DIR/$APP_NAME/Parser.efi"
git reset --hard

popd
echo "✅ Build complete: $TOP_DIR/$APP_NAME/Parser.efi"

}

do_package ()
{
    echo "Packaging uefi... $VARIANT";

    echo "Signing Parser Application... "
    pushd $TOP_DIR
    # sign Parser.efi with db key
    sbsign --key $KEYS_DIR/TestDB1.key --cert $KEYS_DIR/TestDB1.crt $CONFIG_PARSER_EFI --output $TOP_DIR/output/Parser.efi
    
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

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
