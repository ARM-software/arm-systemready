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
LINUX_PATH=linux-5.10

do_clean
do_build
do_package


