#!/bin/sh

# @file
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
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

echo -off
connect -r

echo "UEFI Execution Enviroment can be used to run desired acs test suite manually"
echo "The supported test suites for UEFI enviroment are"
echo "  BSA"
echo "  SBSA"
echo "  SCT"
echo " To run BSA test suite with desired options, edit the acs_tests\config\acs_run_config.ini file using uefi edit command or acs_tests\parser\parser.nsh and then invoke the acs_tests\bsa\bsa.nsh"
echo " To run SBSA test suite with desired options, edit the acs_tests\config\acs_run_config.ini file using uefi edit command or acs_tests\parser\parser.nsh and then invoke the acs_tests\bsa\sbsa\sbsa.nsh"
echo " To run SCT test suite with desired options, cd to acs_tests\bbr\SCT\SCT.efi -u"
echo " "



