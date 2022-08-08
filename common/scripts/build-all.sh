#!/usr/bin/env bash

# Copyright (c) 2021-2022, ARM Limited and Contributors. All rights reserved.
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

if [ "$#" -ne 2 ]; then
    echo "Usage $0 <ES|IR|SR|SIE> F"
    echo "The second (mandatory) parameter F stands for full package."
    exit 1
fi

# Build SIE ACS standalone image
if [ $1 == "SIE" ]; then
    source ./build-scripts/build-efitools.sh
    source ./build-scripts/build-sie-keys.sh
    source ./build-scripts/build-uefi.sh $@
    source ./build-scripts/build-sct.sh $@
    source ./build-scripts/build-uefi-apps.sh $@
    source ./build-scripts/build-grub.sh $@
    source ./build-scripts/build-buildroot.sh
    # return to the parent script
    return
fi

# Build IR|ES|SR ACS
BAND=$1
PACKAGE=$2

source ./build-scripts/build-uefi.sh

if [ $BAND == "SR" ]; then
    source ./build-scripts/build-sbsaefi.sh
else
   source ./build-scripts/build-bsaefi.sh $@
fi
source ./build-scripts/build-sct.sh $@
source ./build-scripts/build-uefi-apps.sh $@
source ./build-scripts/build-linux.sh $BAND

if [ $BAND == "SR" ]; then
    source ./build-scripts/build-linux-sbsa.sh
else
    source ./build-scripts/build-linux-bsa.sh
fi

source ./build-scripts/build-grub.sh $@
source ./build-scripts/build-fwts.sh $@
source ./build-scripts/build-busybox.sh $@
