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

SUMMARY = "A Python library for parsing and translating CSS3 selectors"
HOMEPAGE = "https://pypi.org/project/cssselect2/"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=aa7228954285c7398bb6711fee73b4ac"

# Set the package version.
PV = "0.8.0"

# Fetch the source tarball from PyPI.
SRC_URI = "https://files.pythonhosted.org/packages/source/c/cssselect2/cssselect2-${PV}.tar.gz"
SRC_URI[sha256sum] = "7674ffb954a3b46162392aee2a3a0aedb2e14ecf99fcc28644900f4e6e3e9d3a"
SRCREV_cssselect2 = "${AUTOREV}"

# Inherit the pypi and setuptools3 classes to handle Python packaging.
inherit pypi python_setuptools_build_meta

PYTHON_INSTALL_PACKAGE = "cssselect2"
