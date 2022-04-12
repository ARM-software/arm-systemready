#!/usr/bin/env bash
#
# When CROSS_COMPILE is not set, ensure local toolchain is used
# for 32bit Arm cross compiling.
# This script defines GCC, CROSS_COMPILE and CROSS_COMPILE_DIR.

if [[ ! ${CROSS_COMPILE+x} ]]; then
    GCC=tools/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-
    CROSS_COMPILE=$TOP_DIR/$GCC
    CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
    if [ ! -e ${CROSS_COMPILE}gcc ]; then
        echo "Can't find local cross toolchain, aborting..."
        exit -1
    fi
    PATH="$PATH:$CROSS_COMPILE_DIR"
fi

export CROSS_COMPILE
