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

SUMMARY = "Python support for WeasyPrint"
HOMEPAGE = "https://weasyprint.org/"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=ff136e5f45edb10a900832c046832544"

# Fetch from github
SRC_URI = "git://github.com/Kozea/WeasyPrint;destsuffix=weasyiprint;protocol=https;branch=main;name=weasyprint"
SRC_URI[sha256sum] = "cb424e63e8dd3f14195bfe5f203527646aa40a2f00ac819f9d39b8304cec0044"
SRCREV_weasyprint = "${AUTOREV}"

# Build with Python setuptools
inherit pypi python_setuptools_build_meta
# Define build-time dependencies
DEPENDS = "python3 python3-cffi python3-pillow python3-lxml python3-setuptools"

# Define runtime dependencies
RDEPENDS:${PN} += "\
    python3-cffi \
    python3-pillow \
    python3-lxml \
    python3-setuptools \
"

# Enable native and SDK builds
BBCLASSEXTEND = "native nativesdk"
