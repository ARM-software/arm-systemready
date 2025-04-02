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

for %i in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
    if exist FS%i:\acs_tests\parser\Parser.efi then
        FS%i
        echo "UEFI Execution Enviroment can be used to run an acs test suite manually with desired options"
        echo "The supported test suites for UEFI enviroment are"
        echo "  BSA"
        echo "  SBSA"
        echo "  SCT"
        echo " "
        echo " To view or modify the supported command line parameters for a test suite"
        echo " Edit the acs_tests\config\acs_run_config.ini using edit command or by running acs_tests\parser\parser.nsh"
        echo " "
        echo " To run BSA test suite, execute the acs_tests\bsa\bsa.nsh"
        echo " To run SBSA test suite, execute the acs_tests\bsa\sbsa\sbsa.nsh"
        echo " To run SCT test suite, execute acs_tests\bbr\SCT\SCT.efi -u"
        echo " "
        goto Done
    endif
endfor
:Done
