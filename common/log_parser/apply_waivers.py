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

import json
import sys
import re
import argparse

def clean_description(desc):
    desc = desc.strip().lower()
    desc = re.sub(r'\s+', ' ', desc)  # Replace multiple spaces with a single space
    desc = re.sub(r'[^\w\s-]', '', desc)  # Remove special characters except hyphens
    return desc

def load_waivers(waiver_data, suite_name):
    suite_level_waivers = []
    testsuite_level_waivers = []
    subsuite_level_waivers = []  # Added for SubSuite-level waivers
    testcase_level_waivers = []  # Added for Test_case-level waivers
    subtest_level_waivers = []

    for suite in waiver_data.get('Suites', []):
        if suite.get('Suite') == suite_name:
            # Check for suite-level waiver
            if 'Reason' in suite and suite['Reason']:
                suite_level_waivers.append({'Reason': suite['Reason']})
            # No error if suite-level waiver is not intended

            # Iterate through TestSuites
            for test_suite in suite.get('TestSuites', []):
                # Attempt to extract TestSuite name
                test_suite_name = test_suite.get('TestSuite')

                # If TestSuite name is not present, attempt to extract from TestCase
                if not test_suite_name:
                    test_case = test_suite.get('TestCase') or test_suite.get('SubSuite', {}).get('TestCase')
                    if isinstance(test_case, str):
                        test_suite_name = test_case
                    elif isinstance(test_case, dict):
                        # If TestCase is a dict, TestSuite name is ambiguous; skip TestSuite-level waiver
                        test_suite_name = None

                # Check for TestSuite-level waiver
                if test_suite_name:
                    if 'Reason' in test_suite and test_suite['Reason']:
                        testsuite_level_waivers.append({'TestSuite': test_suite_name, 'Reason': test_suite['Reason']})
                    elif 'Reason' in test_suite and not test_suite['Reason']:
                        if verbose:
                            print(f"ERROR: Waiver for TestSuite '{test_suite_name}' is missing 'Reason'. Skipping TestSuite-level waiver.")

                # Include 'BBSR-SCT' and 'BBSR-FWTS' suites
                # Only load SubSuite and Test_case waivers if the suite is 'SCT', 'STANDALONE', 'BBSR-SCT', or 'BBSR-FWTS'
                if suite_name.upper() in ['SCT', 'STANDALONE', 'BBSR-SCT', 'BBSR-FWTS', 'BBSR-TPM']:
                    # Check for SubSuite-level waiver
                    if 'SubSuite' in test_suite:
                        subsuite = test_suite['SubSuite']
                        if isinstance(subsuite, dict):
                            subsuite_name = subsuite.get('SubSuite')
                            reason = subsuite.get('Reason')
                            if subsuite_name and reason:
                                subsuite_level_waivers.append({'SubSuite': subsuite_name, 'Reason': reason})
                            elif subsuite_name and not reason:
                                if verbose:
                                    print(f"ERROR: Waiver for SubSuite '{subsuite_name}' is missing 'Reason'. Skipping SubSuite-level waiver.")
                        elif isinstance(subsuite, str):
                            # If SubSuite is a string, it's ambiguous; skip
                            if verbose:
                                print(f"ERROR: SubSuite waiver entry for '{subsuite}' lacks 'Reason'. Skipping.")

                    # Check for Test_case-level waiver
                    if 'TestCase' in test_suite:
                        testcase = test_suite['TestCase']
                        if isinstance(testcase, dict):
                            testcase_name = testcase.get('Test_case')
                            reason = testcase.get('Reason')
                            if testcase_name and reason:
                                testcase_level_waivers.append({'Test_case': testcase_name, 'Reason': reason})
                            elif testcase_name and not reason:
                                if verbose:
                                    print(f"ERROR: Waiver for Test_case '{testcase_name}' is missing 'Reason'. Skipping Test_case-level waiver.")
                        elif isinstance(testcase, str):
                            # If Test_case is a string, it's ambiguous; skip
                            if verbose:
                                print(f"ERROR: Test_case waiver entry for '{testcase}' lacks 'Reason'. Skipping.")

                # Collect SubTest-level waivers
                subtests = test_suite.get('TestCase', {}).get('SubTests', []) or test_suite.get('SubSuite', {}).get('TestCase', {}).get('SubTests', [])
                for subtest in subtests:
                    if 'Reason' not in subtest or not subtest['Reason']:
                        subtest_id_or_desc = subtest.get('SubTestID') or subtest.get('sub_Test_Description') or 'Unknown'
                        if verbose:
                            print(f"ERROR: SubTest waiver '{subtest_id_or_desc}' is missing 'Reason'. Skipping subtest-level waiver.")
                        continue
                    subtest_level_waivers.append(subtest)
            break  # Found the suite, no need to continue

    return suite_level_waivers, testsuite_level_waivers, subsuite_level_waivers, testcase_level_waivers, subtest_level_waivers

def apply_suite_level_waivers(test_suite_entry, suite_waivers):
    # Apply waivers to all applicable failed subtests in the suite
    for waiver in suite_waivers:
        reason = waiver['Reason']
        for subtest in test_suite_entry.get('subtests', []):
            sub_test_result = subtest.get('sub_test_result')

            # Apply waiver only if the test has failed
            if isinstance(sub_test_result, dict):
                if sub_test_result.get('FAILED', 0) > 0:
                    sub_test_result['FAILED'] -= 1
                    sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                    # Insert waiver_reason inside sub_test_result
                    sub_test_result['waiver_reason'] = reason
                    existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                    updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                    sub_test_result['fail_reasons'] = updated_fail_reasons
                    if verbose:
                        print(f"Suite-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' with reason: {reason}")
            elif isinstance(sub_test_result, str):
                if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper() or 'FAIL' in sub_test_result.upper():
                    if '(WITH WAIVER)' not in sub_test_result.upper():
                        subtest['sub_test_result'] += ' (WITH WAIVER)'
                        subtest['waiver_reason'] = reason
                        if verbose:
                            print(f"Suite-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' with reason: {reason}")

def apply_testsuite_level_waivers(test_suite_entry, testsuite_waivers):
    # Get the test_suite_name considering different keys
    test_suite_name = test_suite_entry.get('Test_suite') or test_suite_entry.get('Test_suite_name')
    # Apply waivers to all applicable failed subtests within specific TestSuites
    for waiver in testsuite_waivers:
        target_testsuite = waiver['TestSuite']
        reason = waiver['Reason']
        if test_suite_name == target_testsuite:
            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')

                # Apply waiver only if the test has failed
                if isinstance(sub_test_result, dict):
                    if sub_test_result.get('FAILED', 0) > 0:
                        sub_test_result['FAILED'] -= 1
                        sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                        # Insert waiver_reason inside sub_test_result
                        sub_test_result['waiver_reason'] = reason
                        existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                        updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                        sub_test_result['fail_reasons'] = updated_fail_reasons
                        if verbose:
                            print(f"TestSuite-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' in TestSuite '{target_testsuite}' with reason: {reason}")
                elif isinstance(sub_test_result, str):
                    if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                            subtest['waiver_reason'] = reason
                            if verbose:
                                print(f"TestSuite-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' in TestSuite '{target_testsuite}' with reason: {reason}")

def apply_subsuite_level_waivers(test_suite_entry, subsuite_waivers):
    # Apply waivers to all applicable failed subtests within specific SubSuites
    for waiver in subsuite_waivers:
        target_subsuite = waiver['SubSuite']
        reason = waiver['Reason']
        if test_suite_entry.get('Sub_test_suite') == target_subsuite:
            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')

                # Apply waiver only if the test has failed
                if isinstance(sub_test_result, dict):
                    if sub_test_result.get('FAILED', 0) > 0:
                        sub_test_result['FAILED'] -= 1
                        sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                        # Insert waiver_reason inside sub_test_result
                        sub_test_result['waiver_reason'] = reason
                        existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                        updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                        sub_test_result['fail_reasons'] = updated_fail_reasons
                        if verbose:
                            print(f"SubSuite-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' with reason: {reason}")
                elif isinstance(sub_test_result, str):
                    if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                            subtest['waiver_reason'] = reason
                            if verbose:
                                print(f"SubSuite-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' with reason: {reason}")

def apply_testcase_level_waivers(test_suite_entry, testcase_waivers):
    # Apply waivers to all applicable failed subtests within specific Test_cases
    for waiver in testcase_waivers:
        target_testcase = waiver['Test_case']
        reason = waiver['Reason']
        if test_suite_entry.get('Test_case') == target_testcase:
            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')

                # Apply waiver only if the test has failed
                if isinstance(sub_test_result, dict):
                    if sub_test_result.get('FAILED', 0) > 0:
                        sub_test_result['FAILED'] -= 1
                        sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                        # Insert waiver_reason inside sub_test_result
                        sub_test_result['waiver_reason'] = reason
                        existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                        updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                        sub_test_result['fail_reasons'] = updated_fail_reasons
                        if verbose:
                            print(f"Test_case-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' with reason: {reason}")
                elif isinstance(sub_test_result, str):
                    if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                            subtest['waiver_reason'] = reason
                            if verbose:
                                print(f"Test_case-level waiver applied to subtest '{subtest.get('sub_Test_Description')}' with reason: {reason}")

def apply_subtest_level_waivers(test_suite_entry, subtest_waivers, suite_name):
    # Apply waivers to individual subtests based on SubTestID or sub_Test_Description
    for subtest in test_suite_entry.get('subtests', []):
        sub_test_result = subtest.get('sub_test_result')

        if isinstance(sub_test_result, dict):
            # For FWTSResults.json and STANDALONE JSONs where sub_test_result is a dict with result counts
            subtest_description = subtest.get('sub_Test_Description')
            subtest_number = subtest.get('sub_Test_Number')

            for waiver in subtest_waivers:
                waiver_desc = waiver.get('sub_Test_Description')
                # For FWTS and STANDALONE, use descriptions
                if waiver_desc:
                    cleaned_waiver_desc = clean_description(waiver_desc)
                    cleaned_subtest_desc = clean_description(subtest_description)
                    # Special handling for "Boot sources" TestSuite
                    if suite_name.upper() == 'STANDALONE':
                        # If TestSuite-level waiver is applied, all subtests should have waivers already
                        # Otherwise, handle individual subtest waivers
                        if cleaned_waiver_desc in cleaned_subtest_desc:
                            # Apply waiver
                            failed = sub_test_result.get('FAILED', 0)
                            failed_with_waiver = sub_test_result.get('FAILED_WITH_WAIVER', 0)

                            if failed > 0:
                                sub_test_result['FAILED'] = failed - 1
                                sub_test_result['FAILED_WITH_WAIVER'] = failed_with_waiver + 1
                            else:
                                # Edge case: FAILED is already 0
                                sub_test_result['FAILED_WITH_WAIVER'] = failed_with_waiver + 1

                            # Add waiver_reason inside sub_test_result
                            reason = waiver.get('Reason', '')
                            if reason:
                                sub_test_result['waiver_reason'] = reason
                                existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                                updated_fail_reasons = [(s + ' (WITH WAIVER)') for fr in existing_fail_reasons for s in (fr if isinstance(fr, list) else [fr])]
                                sub_test_result['fail_reasons'] = updated_fail_reasons
                            if verbose:
                                print(f"Subtest-level waiver applied to subtest '{subtest_description}' with reason: {reason}")
                            break  # Waiver applied, exit the loop
                    else:
                        # For FWTS, BBSR-FWTS, and other suites
                        if cleaned_waiver_desc == cleaned_subtest_desc:
                            # Apply waiver
                            if 'FAILED (WITH WAIVER)' not in sub_test_result.upper() and 'FAILURE (WITH WAIVER)' not in sub_test_result.upper():
                                subtest['sub_test_result'] += ' (WITH WAIVER)'
                            # Add waiver_reason inside sub_test_result
                            reason = waiver.get('Reason', '')
                            if reason:
                                sub_test_result['waiver_reason'] = reason
                                existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                                updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                                sub_test_result['fail_reasons'] = updated_fail_reasons
                            if verbose:
                                print(f"Subtest-level waiver applied to subtest '{subtest_description}' with reason: {reason}")
                            break  # Waiver applied, exit the loop

        elif isinstance(sub_test_result, str):
            # Only apply waivers to FAILED/FAILURE tests
            if 'FAILED' not in sub_test_result.upper() and 'FAILURE' not in sub_test_result.upper():
                continue

            subtest_description = subtest.get('sub_Test_Description')
            subtest_number = subtest.get('sub_Test_Number')

            # Get the subtest_id based on the suite
            if suite_name.upper() in ['SCT', 'BBSR-SCT']:
                subtest_id = subtest.get('sub_Test_GUID')
            else:
                subtest_id = subtest_number

            for waiver in subtest_waivers:
                waiver_desc = waiver.get('sub_Test_Description')
                waiver_id = waiver.get('SubTestID')
                if suite_name.upper() in ['FWTS', 'STANDALONE', 'BBSR-FWTS']:
                    # For FWTS, STANDALONE, and BBSR-FWTS, use descriptions
                    if waiver_desc:
                        cleaned_waiver_desc = clean_description(waiver_desc)
                        cleaned_subtest_desc = clean_description(subtest_description)
                        if cleaned_waiver_desc in cleaned_subtest_desc:
                            # Apply waiver
                            if 'FAILED (WITH WAIVER)' not in sub_test_result.upper() and 'FAILURE (WITH WAIVER)' not in sub_test_result.upper():
                                subtest['sub_test_result'] += ' (WITH WAIVER)'
                            # Add waiver_reason inside sub_test_result
                            reason = waiver.get('Reason', '')
                            if reason:
                                subtest['sub_test_result'] += f', waiver_reason: "{reason}"'  # Adding inside sub_test_result
                            if verbose:
                                print(f"Subtest-level waiver applied to subtest '{subtest_description}' with reason: {reason}")
                            break
                else:
                    # For other suites, check SubTestID and description
                    if waiver_id and waiver_id == subtest_id:
                        # Apply waiver
                        if 'FAILED (WITH WAIVER)' not in sub_test_result.upper() and 'FAILURE (WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                        # Add waiver_reason as a separate key
                        reason = waiver.get('Reason', '')
                        if reason:
                            subtest['waiver_reason'] = reason
                        if verbose:
                            print(f"Subtest-level waiver applied to subtest '{subtest_description}' with SubTestID '{subtest_id}' and reason: {reason}")
                        break
                    elif waiver_desc:
                        cleaned_waiver_desc = clean_description(waiver_desc)
                        cleaned_subtest_desc = clean_description(subtest_description)
                        if cleaned_waiver_desc == cleaned_subtest_desc:
                            # Apply waiver
                            if 'FAILED (WITH WAIVER)' not in sub_test_result.upper() and 'FAILURE (WITH WAIVER)' not in sub_test_result.upper():
                                subtest['sub_test_result'] += ' (WITH WAIVER)'
                            # Add waiver_reason as a separate key
                            reason = waiver.get('Reason', '')
                            if reason:
                                subtest['waiver_reason'] = reason
                            if verbose:
                                print(f"Subtest-level waiver applied to subtest '{subtest_description}' with reason: {reason}")
                            break
            # Handle other cases if needed

def apply_waivers(suite_name, json_file, waiver_file='waiver.json', output_json_file=None):
    # Load the JSON data
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
    except Exception as e:
        if verbose:
            print(f"WARNING: Failed to read or parse {json_file}: {e}")
        return

    # Load waiver.json
    try:
        with open(waiver_file, 'r') as f:
            waiver_data = json.load(f)
    except Exception as e:
        if verbose:
            print(f"INFO: Failed to read or parse {waiver_file}: {e}")
        return

    # Load test_category.json if provided
    if output_json_file:
        try:
            with open(output_json_file, 'r') as f:
                output_json_data = json.load(f)
        except Exception as e:
            if verbose:
                print(f"WARNING: Failed to read or parse {output_json_file}: {e}")
            output_json_data = None
    else:
        output_json_data = None

    # Get waivers for the suite, categorized by their scope
    suite_level_waivers, testsuite_level_waivers, subsuite_level_waivers, testcase_level_waivers, subtest_level_waivers = load_waivers(waiver_data, suite_name)

    if not (suite_level_waivers or testsuite_level_waivers or (suite_name.upper() in ['SCT', 'STANDALONE', 'BBSR-SCT', 'BBSR-FWTS'] and (subsuite_level_waivers or testcase_level_waivers)) or subtest_level_waivers):
        if verbose:
            print(f"No valid waivers found for suite '{suite_name}'. No changes applied.")
        return

    # Handle different json_data structures
    if 'test_results' in json_data:
        # For fwts.json, sct.json, and STANDALONE JSONs
        test_suite_entries = json_data['test_results']
    elif isinstance(json_data, list):
        # For BSA/SBSA json
        test_suite_entries = json_data
    elif isinstance(json_data, dict):
        test_suite_entries = [json_data]
    else:
        if verbose:
            print(f"ERROR: Unexpected JSON data structure in {json_file}")
        return

    # Process each test suite in the JSON data
    for test_suite_entry in test_suite_entries:
        test_suite_name = test_suite_entry.get('Test_suite') or test_suite_entry.get('Test_suite_name')
        if not test_suite_name:
            continue  # Skip entries that are not test suites

        # Determine if waivers should be applied based on test_category.json
        if output_json_data is None:
            # test_category.json not provided, apply all waivers
            waivable = True
        else:
            # Check if the test suite is waivable according to test_category.json
            waivable = False
            for catID, catData in output_json_data.items():
                # catData is a list
                for row in catData:
                    if row.get("Suite", "").lower() == suite_name.lower() and row.get("Test Suite", "").lower() == test_suite_name.lower():
                        if row.get("Waivable", "").lower() == "yes":
                            waivable = True
                            break  # Found a waivable test suite, exit the loops
                if waivable:
                    break

        if not waivable:
            # Do not process non-waivable test suites
            continue

        # Apply suite-level waivers if any
        if suite_level_waivers:
            apply_suite_level_waivers(test_suite_entry, suite_level_waivers)

        # Apply TestSuite-level waivers if any
        if testsuite_level_waivers:
            apply_testsuite_level_waivers(test_suite_entry, testsuite_level_waivers)

        # Include 'BBSR-SCT' and 'BBSR-FWTS' suites
        # Only apply SubSuite and Test_case level waivers if the suite is 'SCT', 'STANDALONE', 'BBSR-SCT', or 'BBSR-FWTS'
        if suite_name.upper() in ['SCT', 'STANDALONE', 'BBSR-SCT', 'BBSR-FWTS', 'BBSR-TPM']:
            # Apply SubSuite-level waivers if any
            if subsuite_level_waivers:
                apply_subsuite_level_waivers(test_suite_entry, subsuite_level_waivers)

            # Apply Test_case-level waivers if any
            if testcase_level_waivers:
                apply_testcase_level_waivers(test_suite_entry, testcase_level_waivers)

        # Apply subtest-level waivers
        if subtest_level_waivers:
            apply_subtest_level_waivers(test_suite_entry, subtest_level_waivers, suite_name)

        # Update test suite summary
        # Determine the summary field based on suite name
        if suite_name.upper() in ['SCT', 'BBSR-SCT', 'BBSR-TPM']:
            summary_field = 'test_case_summary'
        elif suite_name.upper() == 'STANDALONE':
            summary_field = 'test_suite_summary'
        else:
            summary_field = 'test_suite_summary'

        if summary_field in test_suite_entry:
            # Reset counters
            total_passed = 0
            total_failed = 0
            total_failed_with_waiver = 0
            total_aborted = 0
            total_skipped = 0
            total_warnings = 0
            total_ignored = 0

            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')
                if isinstance(sub_test_result, dict):
                    total_passed += sub_test_result.get('PASSED', 0)
                    total_failed += sub_test_result.get('FAILED', 0)
                    total_failed_with_waiver += sub_test_result.get('FAILED_WITH_WAIVER', 0)
                    total_aborted += sub_test_result.get('ABORTED', 0)
                    total_skipped += sub_test_result.get('SKIPPED', 0)
                    total_warnings += sub_test_result.get('WARNINGS', 0)
                elif isinstance(sub_test_result, str):
                    r = sub_test_result.upper()
                    if 'PASS' in r:
                        total_passed += 1
                    elif 'FAIL' in r:
                        if '(WITH WAIVER)' in r:
                            total_failed_with_waiver += 1
                        else:
                            total_failed += 1
                    elif 'ABORTED' in r:
                        total_aborted += 1
                    elif 'SKIPPED' in r:
                        total_skipped += 1
                    elif 'WARNING' in r:
                        total_warnings += 1
                    else:
                        # anything else (IGNORED, NOT SUPPORTED, etc.)
                        total_ignored += 1

            # Update the summary field with the new counts
            test_suite_entry[summary_field] = {
                'total_passed': total_passed,
                'total_failed': total_failed,
                'total_failed_with_waiver': total_failed_with_waiver,
                'total_aborted': total_aborted,
                'total_skipped': total_skipped,
                'total_warnings': total_warnings,
                'total_ignored': total_ignored,
            }
    if "suite_summary" in json_data and isinstance(json_data["suite_summary"], dict):
        total_passed_top = 0
        total_failed_top = 0
        total_failed_with_waiver_top = 0
        total_aborted_top = 0
        total_skipped_top = 0
        total_warnings_top = 0
        total_ignored_top = 0  # adjust if you track ignored at sub-level

        if "test_results" in json_data and isinstance(json_data["test_results"], list):
            for suite_obj in json_data["test_results"]:
                # Prefer the more detailed test_case_summary when it exists
                if (
                    "test_case_summary" in suite_obj
                    and isinstance(suite_obj["test_case_summary"], dict)
                ):
                    summary = suite_obj["test_case_summary"]
                else:
                    summary = suite_obj.get("test_suite_summary", {})

                total_passed_top              += summary.get("total_passed", 0)
                total_failed_top              += summary.get("total_failed", 0)
                total_failed_with_waiver_top  += summary.get("total_failed_with_waiver", 0)
                total_aborted_top             += summary.get("total_aborted", 0)
                total_skipped_top             += summary.get("total_skipped", 0)
                total_warnings_top            += summary.get("total_warnings", 0)
                total_ignored_top             += summary.get("total_ignored", 0)

        # this eliminates the old UPPER-CASE keys
        json_data["suite_summary"] = {
            "total_passed":               total_passed_top,
            "total_failed":               total_failed_top,
            "total_failed_with_waiver":   total_failed_with_waiver_top,
            "total_aborted":              total_aborted_top,
            "total_skipped":              total_skipped_top,
            "total_warnings":             total_warnings_top,
            "total_ignored":              total_ignored_top,
        }

    # Write the updated JSON data back to the file
    try:
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=4)
        print(f"Waivers successfully applied and '{json_file}' has been updated.")
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to write updated data to {json_file}: {e}")
        return

def main():
    parser = argparse.ArgumentParser(description='Apply waivers to test suite JSON results.')
    parser.add_argument('suite_name', help='Name of the test suite')
    parser.add_argument('json_file', help='Path to the JSON file')
    parser.add_argument('waiver_file', nargs='?', default='waiver.json', help='Path to the waiver file (default: waiver.json)')
    parser.add_argument('output_json_file', nargs='?', default=None, help='Path to the test category file (default: None)')
    parser.add_argument('--quiet', action='store_true', help='Suppress detailed output')
    args = parser.parse_args()

    # Set the global verbosity flag
    global verbose
    verbose = not args.quiet

    # Now call the apply_waivers function
    apply_waivers(args.suite_name, args.json_file, args.waiver_file, args.output_json_file)

if __name__ == '__main__':
    main()
