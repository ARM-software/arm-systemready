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

SUMMARY = "TinyCSS2 is a low-level CSS parser for Python"
HOMEPAGE = "https://pypi.org/project/tinycss2/"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=1d072d7e30e34f33f8ae956ada04fa2c"

PV="1.4.0"

SRC_URI = "https://files.pythonhosted.org/packages/source/t/tinycss2/tinycss2-${PV}.tar.gz"
SRC_URI[sha256sum] = "10c0972f6fc0fbee87c3edb76549357415e94548c1ae10ebccdea16fb404a9b7"

# Inherit the pypi and setuptools3 classes to handle Python packaging.
inherit pypi python_setuptools_build_meta
RDEPENDS:${PN} += "python3"

PYTHON_INSTALL_PACKAGE = "tinycss2"
