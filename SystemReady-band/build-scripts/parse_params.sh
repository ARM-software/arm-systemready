#!/bin/sh

# @file
# Copyright (c) 2021-2024, Arm Limited or its affiliates. All rights reserved.
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

#Print the script that the user explicitly called.

get_shell_type() {
    tty -s && echo "INTERACTIVE" || echo "NON-INTERACTIVE"
}

set_formatting() {
    if [ "$(get_shell_type)" = "INTERACTIVE" ] ; then
        export BOLD="\e[1m"
        export NORMAL="\e[0m"
        export RED="\e[31m"
        export GREEN="\e[32m"
        export YELLOW="\e[33m"
        export BLUE="\e[94m"
        export CYAN="\e[36m"
    fi
}

export PARSE_PARAMS_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
