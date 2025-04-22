#!/bin/bash
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
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

SUMMARY = "DejaVu Fonts - High quality fonts with extensive language support"
HOMEPAGE = "https://dejavu-fonts.github.io/"
LICENSE = "BitstreamVera"
LIC_FILES_CHKSUM = "file://LICENSE;md5=449b2c30bfe5fa897fe87b8b70b16cfa"

PV = "2.37"
SRC_URI = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version-2.37/dejavu-fonts-ttf-2.37.tar.bz2"
SRC_URI[sha256sum] = "fa9ca4d13871dd122f61258a80d01751d603b4d3ee14095d65453b4e846e17d7"

S = "${WORKDIR}/dejavu-fonts-ttf-${PV}"
do_install() {
    # Create the target directory for fonts
    install -d ${D}${datadir}/fonts/dejavu
    # Copy the TrueType fonts to the target directory.
    cp -r ${S}/ttf/* ${D}${datadir}/fonts/dejavu/
}

# Package the dejavu fonts.
FILES:${PN} = "${datadir}/fonts/dejavu"
