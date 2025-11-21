#!/usr/bin/env bash

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

#------------------------------------------
# Generate the disk image for busybox boot
#------------------------------------------


#variables for image generation
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
TOP_DIR=`pwd`
PLATDIR=${TOP_DIR}/output
OUTDIR=${PLATDIR}
GRUB_BUILDROOT_CONFIG_FILE=${TOP_DIR}/build-scripts/config/grub-buildroot.cfg
EFI_CONFIG_FILE=${TOP_DIR}/uefi_scripts/startup.nsh
EE_EFI_CONFIG_FILE=${TOP_DIR}/uefi_scripts/startup_ee.nsh
BBSR_STARTUP_FILE=${TOP_DIR}/uefi_scripts/bbsr_startup.nsh
BSA_CONFIG_FILE=${TOP_DIR}/uefi_scripts/bsa.nsh
SBSA_CONFIG_FILE=${TOP_DIR}/uefi_scripts/sbsa.nsh
BBR_CONFIG_FILE=${TOP_DIR}/uefi_scripts/bbr.nsh
DEBUG_CONFIG_FILE=${TOP_DIR}/uefi_scripts/debug_dump.nsh
ACS_CONFIG_FILE=${TOP_DIR}/build-scripts/config/acs_config.txt
SYSTEM_CONFIG_FILE=${TOP_DIR}/build-scripts/config/system_config.txt
ACS_RUN_CONFIG_FILE=${TOP_DIR}/build-scripts/config/acs_run_config.ini
CONFIG_PARSER_FILE=${TOP_DIR}/uefi_scripts/parser.nsh
CONFIG_PARSER_PYTHON_FILE=${TOP_DIR}/../common/parser/Parser.py
BLOCK_SIZE=512
SEC_PER_MB=$((1024*2))
GRUB_PATH=grub
UEFI_SHELL_PATH=edk2/Build/Shell/RELEASE_GCC5/AARCH64/
SCT_PATH=edk2-test/uefi-sct/AARCH64_SCT
UEFI_APPS_PATH=${TOP_DIR}/edk2/Build/MdeModule/DEBUG_GCC5/AARCH64

create_cfgfiles ()
{
    local fatpart_name="$1"

    mcopy -i  $fatpart_name -o ${GRUB_BUILDROOT_CONFIG_FILE} ::/EFI/BOOT/grub.cfg
    mcopy -i  $fatpart_name -o ${BBSR_STARTUP_FILE}   ::/EFI/BOOT/
    mcopy -i  $fatpart_name -o ${EFI_CONFIG_FILE}     ::/EFI/BOOT/
    mcopy -i  $fatpart_name -o ${EE_EFI_CONFIG_FILE}  ::/EFI/BOOT/
    mcopy -i  $fatpart_name -o ${BSA_CONFIG_FILE}     ::/acs_tests/bsa/
    mcopy -i  $fatpart_name -o ${SBSA_CONFIG_FILE}    ::/acs_tests/bsa/sbsa
    mcopy -i  $fatpart_name -o ${DEBUG_CONFIG_FILE}   ::/acs_tests/debug/
    mcopy -i  $fatpart_name -o ${ACS_CONFIG_FILE}     ::/acs_tests/config/
    mcopy -i  $fatpart_name -o ${SYSTEM_CONFIG_FILE}  ::/acs_tests/config/
    mcopy -i  $fatpart_name -o ${ACS_RUN_CONFIG_FILE}  ::/acs_tests/config/

}

create_fatpart ()
{
    local fatpart_name="$1"  #Name of the FAT partition disk image
    local fatpart_size="$2"  #FAT partition size (in 512-byte blocks)

    dd if=/dev/zero of=$fatpart_name bs=$BLOCK_SIZE count=$fatpart_size
    mkfs.vfat $fatpart_name -n $fatpart_name
    mmd -i $fatpart_name ::/EFI
    mmd -i $fatpart_name ::/EFI/BOOT
    mmd -i $fatpart_name ::/acs_tests
    mmd -i $fatpart_name ::/acs_tests/bsa
    mmd -i $fatpart_name ::/acs_tests/bsa/sbsa
    mmd -i $fatpart_name ::/acs_tests/bbr
    mmd -i $fatpart_name ::/acs_tests/debug
    mmd -i $fatpart_name ::/acs_tests/app
    mmd -i $fatpart_name ::/acs_tests/bbsr-keys
    mmd -i $fatpart_name ::/acs_results
    mmd -i $fatpart_name ::/acs_tests/config
    mmd -i $fatpart_name ::/acs_tests/parser

    mcopy -i $fatpart_name $OUTDIR/bootaa64.efi ::/EFI/BOOT
    mcopy -i $fatpart_name $OUTDIR/Shell.efi ::/EFI/BOOT

    mcopy -i $fatpart_name $OUTDIR/Image ::/
    mcopy -i $fatpart_name $PLATDIR/ramdisk-buildroot.img  ::/

    mcopy -i $fatpart_name $OUTDIR/Bsa.efi ::/acs_tests/bsa
    mcopy -i $fatpart_name $OUTDIR/Sbsa.efi ::/acs_tests/bsa/sbsa

    mcopy -s -i $fatpart_name SCT/* ::/acs_tests/bbr

    # ship BBSR public keys
    mcopy -i $fatpart_name ${TOP_DIR}/bbsr-keys/*.der ::/acs_tests/bbsr-keys
    mcopy -i $fatpart_name ${TOP_DIR}/bbsr-keys/*.auth ::/acs_tests/bbsr-keys

    mcopy -i $fatpart_name ${UEFI_APPS_PATH}/CapsuleApp.efi ::/acs_tests/app
    mcopy -i $fatpart_name $OUTDIR/Parser.efi  ::/acs_tests/parser
    mcopy -i $fatpart_name $CONFIG_PARSER_FILE  ::/acs_tests/parser
    mcopy -i $fatpart_name $CONFIG_PARSER_PYTHON_FILE  ::/acs_tests/parser

    echo "FAT partition image created"
}

create_diskimage ()
{
    local image_name="$1"
    local part_start="$2"
    local fatpart_size="$3"

    (echo n; echo 1; echo $part_start; echo +$((fatpart_size-1));\
    echo 0700; echo w; echo y) | gdisk $image_name
}

prepare_disk_image ()
{
    echo
    echo
    echo "-------------------------------------"
    echo "Preparing disk image"
    echo "-------------------------------------"

    IMG_BB=systemready_acs_live_image.img
    echo -e "\e[1;32m Build SystemReady Band Live Image at $PLATDIR/$IMG_BB \e[0m"

    pushd $TOP_DIR/$GRUB_PATH/output

    local FAT_SIZE_MB=640
    local PART_START=$((1*SEC_PER_MB))
    local FAT_SIZE=$((FAT_SIZE_MB*SEC_PER_MB))

    rm -f $PLATDIR/$IMG_BB
    cp grubaa64.efi $OUTDIR/bootaa64.efi
    cp $TOP_DIR/$UEFI_SHELL_PATH/Shell_EA4BB293-2D7F-4456-A681-1F22F42CD0BC.efi $OUTDIR/Shell.efi

    cp -Tr $TOP_DIR/$SCT_PATH/ SCT
    grep -q -F 'mtools_skip_check=1' ~/.mtoolsrc || echo "mtools_skip_check=1" >> ~/.mtoolsrc

    #Package images for Busybox
    rm -f $IMG_BB
    dd if=/dev/zero of=part_table bs=$BLOCK_SIZE count=$PART_START

    #Space for partition table at the top
    cat part_table > $IMG_BB

    #Create fat partition
    create_fatpart "BOOT_ACS" $FAT_SIZE
    create_cfgfiles "BOOT_ACS"
    cat BOOT_ACS >> $IMG_BB

    #Space for backup partition table at the bottom (1M)
    cat part_table >> $IMG_BB

    # create disk image and copy into output folder
    create_diskimage $IMG_BB $PART_START $FAT_SIZE
    cp $IMG_BB $PLATDIR

    #remove intermediate files
    rm -f part_table
    rm -f BOOT_ACS
    #remove compressed image if present from previous build
    if [ -f $PLATDIR/$IMG_BB.xz ]; then
        rm $PLATDIR/$IMG_BB.xz
    fi
    echo "Compressing the image : $PLATDIR/$IMG_BB"
    xz -T0 -z $PLATDIR/$IMG_BB

    if [ -f $PLATDIR/$IMG_BB.xz ]; then
        echo "Completed preparation of disk image for busybox boot"
        echo "Image path : $PLATDIR/$IMG_BB.xz"
    fi
    echo "----------------------------------------------------"
}
exit_fun() {
   exit 1 # Exit script
}

#prepare the disk image
prepare_disk_image
