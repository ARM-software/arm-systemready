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

TOP_DIR=`pwd`
. $TOP_DIR/../common/config/systemready-band-source.cfg

export KERNEL_SRC=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}/out
LINUX_PATH=$TOP_DIR/linux-${LINUX_KERNEL_VERSION}
ACS_PATH=$TOP_DIR/edk2/ShellPkg/Application/sysarch-acs

BUILDROOT_PATH=buildroot
BUILDROOT_ARCH=arm64
BUILDROOT_OUT_DIR=out/$BUILDROOT_ARCH
PLATDIR=${TOP_DIR}/output

build_sbsa_kernel_driver()
{
    pushd $TOP_DIR/linux-acs/acs-drv/files
    rm -rf $TOP_DIR/linux-acs/acs-drv/files/val
    rm -rf $TOP_DIR/linux-acs/acs-drv/files/test_pool

    arch=$(uname -m)
    echo $arch
    if [[ $arch = "aarch64" ]]
    then
        echo "aarch64 native build"
        export CROSS_COMPILE=''
    else
        export CROSS_COMPILE=$TOP_DIR/$GCC
    fi
    ./acs_setup.sh $TOP_DIR/edk2/ShellPkg/Application/sysarch-acs
    ./linux_acs.sh sbsa
    popd
}


build_sbsa_app()
{
    pushd $ACS_PATH/apps/linux/sbsa-acs-app
    make clean
    make
    popd
}

build_pmu_app()
{
    pushd $ACS_PATH/apps/linux/pmu_app
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
    pushd $ACS_PATH/apps/linux/mte
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
  cp $TOP_DIR/linux-acs/acs-drv/files/sbsa_acs.ko $TOP_DIR/ramdisk/linux-sbsa/
  cp $ACS_PATH/apps/linux/sbsa-acs-app/sbsa $TOP_DIR/ramdisk/linux-sbsa
  cp -r $ACS_PATH/apps/linux/pmu_app/pmuval $TOP_DIR/ramdisk/linux-sbsa

  #copy mte test to ramdisk
  cp $ACS_PATH/apps/linux/mte/mte_test $TOP_DIR/ramdisk/linux-sbsa

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
