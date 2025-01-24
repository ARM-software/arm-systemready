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
BAND=$1
CLEAN_BUILD=$3

. $TOP_DIR/../common/config/systemready-band-source.cfg

set -E

handle_error ()
{
    local callinfo=$(caller 0)
    local script=${callinfo##* }
    local lineno=${callinfo%% *}
    local func=${callinfo% *}
    func=${func#* }
    echo
    echo -en "${BOLD}${RED}Build failed: error while running ${func} at line "
    echo -en "${lineno} in ${script} for ${PLATFORM}[$FLAVOUR]"
    echo -e "[$FILESYSTEM_CONFIGURATION].${NORMAL}"
    echo
    exit 1
}

trap handle_error ERR

if [ "$PARALLELISM" != "" ]; then
    echo "Parallelism set in environment to $PARALLELISM, not overridding"
else
    PARALLELISM=`getconf _NPROCESSORS_ONLN`
fi

# Directory variables provided by the framework
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

source $DIR/parse_params.sh
set_formatting

pushd $DIR/..
TOP_DIR=`pwd`
popd

PLATDIR=${TOP_DIR}/output
OUTDIR=${PLATDIR}
LINUX_OUT_DIR=out
LINUX_PATH=linux-${LINUX_KERNEL_VERSION}

if [ -n "$CLEAN_BUILD" ] && [ "$CLEAN_BUILD" = "C" ]; then
    do_clean
fi
do_build
do_package
