#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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

"""Keep the existing optional Doctor entry point while its code lives in one folder.

Normal parser commands only register Doctor's flags. Health checks run only
when explicitly requested; importing this launcher never starts them.
"""

import sys

from doctor_checks.core import Context, Finding, add_arguments, main, run_health

# These imports are the existing public entry points, not unused local helpers.
__all__ = ("Context", "Finding", "add_arguments", "main", "run_health", "sys")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
