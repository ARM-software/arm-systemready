#!/bin/bash

# Copyright (c) 2022-2023, ARM Limited and Contributors. All rights reserved.
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
TOP_DIR=`pwd`
BAND=$1
. $TOP_DIR/../../common/config/sr_es_common_config.cfg

export KERNEL_SRC=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}/out
LINUX_PATH=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}
SBSA_PATH=$TOP_DIR/edk2/ShellPkg/Application/sbsa-acs

BUILDROOT_PATH=buildroot
BUILDROOT_ARCH=arm64
BUILDROOT_OUT_DIR=out/$BUILDROOT_ARCH
PLATDIR=${TOP_DIR}/output

build_sbsa_kernel_driver()
{
    pushd $TOP_DIR/linux-acs/sbsa-acs-drv/files
    arch=$(uname -m)
    echo $arch
    if [[ $arch = "aarch64" ]]
    then
        echo "aarch64 native build"
        export CROSS_COMPILE=''
    else
        export CROSS_COMPILE=$TOP_DIR/$GCC
    fi
    ./setup.sh $TOP_DIR/edk2/ShellPkg/Application/sbsa-acs
    ./linux_sbsa_acs.sh
    popd
}


build_sbsa_app()
{
    pushd $SBSA_PATH/linux_app/sbsa-acs-app
    make clean
    make
    popd
}

build_pmu_app()
{
    pushd $SBSA_PATH/linux_app/pmu_app
        arch=$(uname -m)
        echo $arch
        if [[ $arch = "aarch64" ]]
        then
            echo "arm64 native build"
            export CROSS_COMPILE=''
        else
            export CROSS_COMPILE=$TOP_DIR/$GCC
        fi
        export PYTHON=$TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/host/usr/bin/python
        export PYTHONPATH=$TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/
        export CROSSBASE=$TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target
        source build_pmu.sh
    popd
}

build_mte_test()
{
    pushd $SBSA_PATH/linux_app/mte
        arch=$(uname -m)
        echo "ARCH = $arch"
        if [[ $arch = "aarch64" ]]
        then
            echo "arm64 native build"
            export CROSS_COMPILE=''
        else
            export CROSS_COMPILE=$TOP_DIR/$GCC
        fi
        source build_mte.sh
    popd
}

pack_in_ramdisk()
{
  echo "Packaging"

  rm -rf $TOP_DIR/ramdisk/linux-sbsa
  mkdir $TOP_DIR/ramdisk/linux-sbsa

  # Add all needed packages to build root
  cp $TOP_DIR/linux-acs/sbsa-acs-drv/files/sbsa_acs.ko $TOP_DIR/ramdisk/linux-sbsa/
  cp $SBSA_PATH/linux_app/sbsa-acs-app/sbsa $TOP_DIR/ramdisk/linux-sbsa
  cp -r $SBSA_PATH/linux_app/pmu_app/pmuval $TOP_DIR/ramdisk/linux-sbsa

  #copy mte test to ramdisk
  cp $SBSA_PATH/linux_app/mte/mte_test $TOP_DIR/ramdisk/linux-sbsa

  rm -rf $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/pysweep.so
  rm -rf $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/pyperf/perf_events.so
    arch=$(uname -m)
  cp -r $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/PyPerf-0.0.0-py3.10-linux-${arch}.egg/pyperf \
   $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/
  cp $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/PySweep-0.0.0-py3.10-linux-${arch}.egg/pysweep.cpython-310-${arch}-linux-gnu.so \
   $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/
  cp $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/pyperf/perf_events.cpython-310-${arch}-linux-gnu.so \
   $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/pyperf/perf_events.so
  cp $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/pysweep.* \
     $TOP_DIR/${BUILDROOT_PATH}/$BUILDROOT_OUT_DIR/target/lib/python3.10/site-packages/pysweep.so
}

build_sbsa_kernel_driver
build_sbsa_app
build_pmu_app
build_mte_test
pack_in_ramdisk