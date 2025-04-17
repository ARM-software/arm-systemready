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

SUMMARY = "Pydyf: a Python library for building PDFs using CSS layout"
HOMEPAGE = "https://pypi.org/project/pydyf/"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=cbcacfe0ddf7cfbafcbef1f7cedd3c5b"

PV = "0.11.0"

SRC_URI = "https://files.pythonhosted.org/packages/source/p/pydyf/pydyf-${PV}.tar.gz"
SRC_URI[sha256sum] = "394dddf619cca9d0c55715e3c55ea121a9bf9cbc780cdc1201a2427917b86b64"

# Inherit the pypi and setuptools3 classes to handle Python packaging.
inherit pypi python_setuptools_build_meta
RDEPENDS:${PN} += "python3"

PYTHON_INSTALL_PACKAGE = "pydyf"
