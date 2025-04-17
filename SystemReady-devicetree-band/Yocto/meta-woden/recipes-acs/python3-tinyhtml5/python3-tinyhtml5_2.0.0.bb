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

SUMMARY = "TinyHTML5 is a lightweight HTML parser for Python"
HOMEPAGE = "https://pypi.org/project/tinyhtml5/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=1ba5ada9e6fead1fdc32f43c9f10ba7c"

PV="2.0.0"

SRC_URI = "https://files.pythonhosted.org/packages/source/t/tinyhtml5/tinyhtml5-${PV}.tar.gz"
SRC_URI[sha256sum] = "086f998833da24c300c414d9fe81d9b368fd04cb9d2596a008421cbc705fcfcc"

# Inherit the pypi and setuptools3 classes to handle Python packaging.
inherit pypi python_setuptools_build_meta
# Ensure Python3 is available at runtime.
RDEPENDS:${PN} += "python3"

PYTHON_INSTALL_PACKAGE = "tinyhtml5"
