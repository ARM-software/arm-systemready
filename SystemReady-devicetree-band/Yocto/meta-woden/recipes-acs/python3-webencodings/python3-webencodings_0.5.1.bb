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

SUMMARY = "Webencodings is a Python package for encoding detection used by HTML parsing libraries"
HOMEPAGE = "https://pypi.org/project/webencodings/"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=81fb24cd7823cce23b69f721993dce4d"

PV="0.5.1"

SRC_URI = "https://files.pythonhosted.org/packaes/source/w/webencodings/webencodings-${PV}.tar.gz"
SRC_URI[sha256sum] = "082367f568a7812aa5f6922ffe3d9d027cd83829dc32bcaac4c874eeed618000"

inherit setuptools3
RDEPENDS:${PN} += "python3"

PYPI_PACKAGE = "webencodings"
