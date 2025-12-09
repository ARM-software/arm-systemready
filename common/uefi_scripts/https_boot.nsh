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

# Logs all actions to: \acs_results_template\acs_results\network_boot\https_network_boot_console.log
if not exist \acs_results_template then
  mkdir \acs_results_template
endif
if not exist \acs_results_template\acs_results then
  mkdir \acs_results_template\acs_results
endif
if not exist \acs_results_template\acs_results\network_boot then
  mkdir \acs_results_template\acs_results\network_boot
endif

set logdir \acs_results_template\acs_results\network_boot
set logfile %logdir%\https_network_boot_console.log

# start a console log
echo [INFO] start_network_boot > %logfile%
date >> %logfile%
time >> %logfile%

# load config
if exist \acs_tests\config\acs_https.conf.nsh then
  echo Loading config from \acs_tests\config\acs_https.conf.nsh >> %logfile%
  \acs_tests\config\acs_https.conf.nsh
else
  echo [ERROR] Config missing at \acs_tests\config\acs_https.conf.nsh >> %logfile%
  goto FailAndExit
endif

# log config variables if present
if not "%HTTPS_IMAGE_URL%" == "" then
  echo HTTPS_IMAGE_URL=%HTTPS_IMAGE_URL% >> %logfile%
endif

if not "%HTTPS_IMAGE_SCHEME%" == "" then
  echo Scheme: %HTTPS_IMAGE_SCHEME% >> %logfile%
else
  echo Scheme: (unknown) >> %logfile%
endif

# validate URL/hostpath variables
if "%HTTPS_IMAGE_HOSTPATH%" == "" then
  if "%HTTPS_IMAGE_URL%" == "" then
    echo [ERROR] No valid URL provided (HTTPS_IMAGE_HOSTPATH and HTTPS_IMAGE_URL empty) >> %logfile%
  else
    echo [ERROR] HTTPS_IMAGE_HOSTPATH not set. Provide a scheme-free host/path in the config. >> %logfile%
    echo Example: raw.githubusercontent.com/owner/repo/path/file.img >> %logfile%
  endif
  goto FailAndExit
endif

echo HOSTPATH=%HTTPS_IMAGE_HOSTPATH% >> %logfile%

# locate ledge.efi and set in-progress flag
set rc 1

for %j in 0 1 2 3 4 5 6 7 8 9 A B C D E F then
  if exist FS%j:\acs_tests\app\ledge.efi then
    FS%j:
    echo ledge.efi found at \acs_tests\app\ledge.efi >> %logfile%

    # create network_boot_in_progress flag
    echo > \acs_tests\app\network_boot_in_progress.flag

    # Decide arguments based on scheme:
    # - http:  ledge.efi -s -u <hostpath> -f -l "ACS-Minimal Image"
    # - else:  ledge.efi -s -u <hostpath> -l "ACS-Minimal Image"
    if "%HTTPS_IMAGE_SCHEME%" == "http" then
      echo Using HTTP mode (-f) >> %logfile%
      \acs_tests\app\ledge.efi -s -u %HTTPS_IMAGE_HOSTPATH% -f -l "ACS-Minimal Image"
    else
      echo Using HTTPS/default mode (no -f) >> %logfile%
      \acs_tests\app\ledge.efi -s -u %HTTPS_IMAGE_HOSTPATH% -l "ACS-Minimal Image"
    endif

    set rc %lasterror%

    # If ledge.efi returns with error, clean flag and fallback to Linux
    if not %rc% == 0 then
      echo [ERROR] ledge.efi failed rc=%rc% >> %logfile%
      if exist \acs_tests\app\network_boot_in_progress.flag then
        rm \acs_tests\app\network_boot_in_progress.flag
      endif
      goto FailAndExit
    endif

    # If ledge.efi returns with rc=0, just log and exit
    echo ledge.efi launched successfully (rc=0). >> %logfile%
    exit 0
  endif
endfor

echo [ERROR] No ledge.efi found under FS?:\acs_tests\app\ >> %logfile%
echo Expected path like FS1:\acs_tests\app\ledge.efi >> %logfile%

goto FailAndExit

:FailAndExit
echo Network boot failed, please check logs, exiting from the script >> %logfile%
if exist \acs_tests\app\network_boot_in_progress.flag then
  rm \acs_tests\app\network_boot_in_progress.flag
endif
echo > \acs_tests\app\network_boot_failed.flag
exit 0
