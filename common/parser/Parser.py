#!/usr/bin/env python3
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

import configparser
import argparse

def read_config(config_file):
    try:
        config = configparser.ConfigParser()
        config.read(config_file)
        return config
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        return None

def process_bsa(config):
    if not config.getboolean('BSA', 'automation_bsa_run', fallback=False):
        print("BSA section is disabled or missing.")
        return []

    cmd = ['/bin/bsa']
  #  modules = config.get('BSA', 'bsa_modules', fallback=None)
  #  tests = config.get('BSA', 'bsa_tests', fallback=None)
    skip = config.get('BSA', 'bsa_skip', fallback=None)
    verbose = config.get('BSA', 'bsa_verbose', fallback=None)

    #if modules:
    #    cmd.append(f'-m {modules}')
    #if tests:
    #    cmd.append(f'-t {",".join(tests.split(","))}')
    if skip:
        cmd.append(f'--skip {skip}')
    if verbose:
        cmd.append(f' -v{verbose}')

    return cmd

def process_sbsa(config):
    if not config.getboolean('SBSA', 'automation_sbsa_run', fallback=False):
        print("SBSA section is disabled or missing.")
        return []

    cmd = ['/bin/sbsa']
  #  modules = config.get('SBSA', 'sbsa_modules', fallback=None)
    level = config.get('SBSA', 'sbsa_level', fallback=None)
  #  tests = config.get('SBSA', 'sbsa_tests', fallback=None)
    skip = config.get('SBSA', 'sbsa_skip', fallback=None)
    verbose = config.get('SBSA', 'sbsa_verbose', fallback=None)

   # if modules:
   #     cmd.append(f'-m {modules}')
    if level:
        cmd.append(f'-l {level}')
   # if tests:
   #     cmd.append(f'-t {",".join(tests.split(","))}')
    if skip:
        cmd.append(f'--skip {skip}')
    if verbose:
        cmd.append(f' -v {verbose}')

    return cmd

def process_fwts(config):
    if not config.getboolean('FWTS', 'automation_fwts_run', fallback=False):
        print("FWTS section is disabled or missing.")
        return []

    cmd = ['fwts']

    module = config.get('FWTS', 'fwts_modules', fallback=None)
    if module:
        cmd.append(f'{module}')

    return cmd

def check_section_enable(config, section, enabled_key):
    if not config:
        print("Configuration not loaded properly.")
        return None

    if section not in config:
        print(f"Section {section} is missing in the configuration file.")
        return False

    enabled = config.getboolean(section, enabled_key, fallback=False)
    return enabled

def main():
    parser = argparse.ArgumentParser(description='Config parser')
    parser.add_argument('-bsa', action='store_true', help='Process BSA section')
    parser.add_argument('-sbsa', action='store_true', help='Process SBSA section')
    parser.add_argument('-fwts', action='store_true', help='Process FWTS section')
    parser.add_argument('-automation', action='store_true', help='Process generic section')

    parser.add_argument('-automation_bsa_run', action='store_true', help='Check if BSA is enabled')
    parser.add_argument('-automation_sbsa_run', action='store_true', help='Check if SBSA is enabled')
    parser.add_argument('-automation_fwts_run', action='store_true', help='Check if FWTS is enabled')
    parser.add_argument('-automation_bbsr_fwts_run', action='store_true', help='Check if BBSR FWTS is enabled')
    parser.add_argument('-automation_bbsr_tpm_run', action='store_true', help='Check if BBSR TPM is enabled')
    parser.add_argument('--config', default='/mnt/acs_tests/config/acs_run_config.ini', help='Path to the config file')
    parser.add_argument('-automation_sbmr_in_band_run', action='store_true', help='Check if SBMR is enabled')

    args = parser.parse_args()

    config = read_config(args.config)
    if not config:
        return

    if args.bsa:
        cmd = process_bsa(config)
        if cmd:
            print(' '.join(cmd))
    elif args.sbsa:
        cmd = process_sbsa(config)
        if cmd:
            print(' '.join(cmd))
    elif args.fwts:
        cmd = process_fwts(config)
        if cmd:
            print(' '.join(cmd))
    elif args.automation:
        enabled = check_section_enable(config, 'AUTOMATION', 'config_enabled_for_automation_run')
        print(enabled)
    elif args.automation_bsa_run:
        enabled = check_section_enable(config, 'BSA', 'automation_bsa_run')
        print(enabled)
    elif args.automation_sbsa_run:
        enabled = check_section_enable(config, 'SBSA', 'automation_sbsa_run')
        print(enabled)
    elif args.automation_fwts_run:
        enabled = check_section_enable(config, 'FWTS', 'automation_fwts_run')
        print(enabled)
    elif args.automation_bbsr_fwts_run:
        enabled = check_section_enable(config, 'BBSR_FWTS', 'automation_bbsr_fwts_run')
        print(enabled)
    elif args.automation_bbsr_tpm_run:
        enabled = check_section_enable(config, 'BBSR_TPM', 'automation_bbsr_tpm_run')
        print(enabled)
    elif args.automation_sbmr_in_band_run:
        enabled = check_section_enable(config, 'SBMR', 'automation_sbmr_in_band_run')
        print(enabled)
    else:
        print("Please specify a valid command or use --help for more information.")
        return

if __name__ == '__main__':
    main()
