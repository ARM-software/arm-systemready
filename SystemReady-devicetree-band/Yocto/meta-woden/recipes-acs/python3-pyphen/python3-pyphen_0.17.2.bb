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

SUMMARY = "A pure Python module to hyphenate words (used in text processing and typesetting)"
HOMEPAGE = "https://pypi.org/project/pyphen/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=ce317ca4dfa0c33c1acbf1b21c1cf5a7"

PV = "0.17.2"

SRC_URI = "https://files.pythonhosted.org/packages/source/p/pyphen/pyphen-${PV}.tar.gz"
SRC_URI[sha256sum] = "f60647a9c9b30ec6c59910097af82bc5dd2d36576b918e44148d8b07ef3b4aa3"

# Inherit the pypi and setuptools3 classes to handle Python packaging.
inherit pypi python_setuptools_build_meta
RDEPENDS:${PN} += "python3"

PYTHON_INSTALL_PACKAGE = "pyphen"
