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

SUMMARY = "A library to manipulate font files, required by WeasyPrint for font handling"
HOMEPAGE = "https://github.com/fonttools/fonttools"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=211c9e4671bde3881351f22a2901f692"

PV = "4.56.0"

SRC_URI = "https://files.pythonhosted.org/packages/source/f/fonttools/fonttools-${PV}.tar.gz"
SRC_URI[sha256sum] = "a114d1567e1a1586b7e9e7fc2ff686ca542a82769a296cef131e4c4af51e58f4"

inherit pypi setuptools3
RDEPENDS:${PN} += "python3"

PYTHON_INSTALL_PACKAGE = "fontTools"
