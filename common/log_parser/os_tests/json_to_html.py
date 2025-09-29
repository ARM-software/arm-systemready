#!/usr/bin/env python3
# Copyright (c) 2024-2025, Arm Limited or its affiliates. All rights reserved.
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
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from jinja2 import Template
import sys
import argparse
import os

def detect_columns_used(subtests):
    """
    Returns a dict of booleans indicating whether "pass_reasons",
    "fail_reasons", or "skip_reasons" columns are actually used by ANY subtest.

    (We keep this logic so as not to break anything else,
    though we won't actually render separate columns for them.)
    """
    show_pass = False
    show_fail = False
    show_skip = False

    for subtest in subtests:
        r = subtest.get('sub_test_result', {})
        if r.get('pass_reasons'):  # Non-empty list
            show_pass = True
        if r.get('fail_reasons'):
            show_fail = True
        if r.get('skip_reasons'):
            show_skip = True

    return {
        'show_pass': show_pass,
        'show_fail': show_fail,
        'show_skip': show_skip
    }

# Function to generate bar chart for test results
def generate_bar_chart(suite_summary):
    labels = ['Passed', 'Failed', 'Skipped']
    sizes = [
        suite_summary.get('total_passed', 0),
        suite_summary.get('total_failed', 0),
        suite_summary.get('total_skipped', 0)
    ]
    colors = ['#66bb6a', '#ef5350', '#f39c12']

    plt.figure(figsize=(8, 6))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    # Add percentage labels on top of the bars
    total_tests = sum(sizes)
    for bar, size in zip(bars, sizes):
        yval = bar.get_height()
        if total_tests > 0:
            percentage = (size / total_tests) * 100
            label = f'{percentage:.2f}%'
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                yval + 0.05 * total_tests,
                label,
                ha='center',
                va='bottom',
                fontsize=12
            )
        else:
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                yval + 0.05,
                '0%',
                ha='center',
                va='bottom',
                fontsize=12
            )

    plt.title('OS Test Results', fontsize=16, fontweight='bold', pad=20)
    plt.ylabel('Number of Tests', fontsize=14)
    plt.tight_layout()

    # Save the figure to a buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# Function to determine subtest status
def get_subtest_status(subtest_result):
    if subtest_result.get('PASSED', 0) > 0:
        return 'PASSED'
    elif subtest_result.get('FAILED', 0) > 0:
        return 'FAILED'
    elif subtest_result.get('SKIPPED', 0) > 0:
        return 'SKIPPED'
    elif subtest_result.get('ABORTED', 0) > 0:
        return 'ABORTED'
    elif subtest_result.get('WARNINGS', 0) > 0:
        return 'WARNINGS'
    else:
        return 'INFO'  # For informational entries

# Function to generate HTML content for both summary and detailed pages
def generate_html(suite_summary, test_results_list, output_html_path, is_summary_page=True, include_drop_down=False):
    # Set the test suite name to 'OS Tests'
    test_suite_name = 'OS Tests'

    # Template for both summary and detailed pages
    template = Template(r"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ test_suite_name }} Test Summary</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f4f4f4;
            }
            h1, h2, h3 {
                color: #2c3e50;
                text-align: center;
                margin: 0;
                padding: 10px 0;
            }
            h1 {
                margin-bottom: 20px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 12px;
                border: 1px solid #ddd;
                font-size: 16px;
            }
            th {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                text-align: left;
            }
            td:first-child {
                text-align: left;
            }
            .summary-table td:nth-child(2) {
                text-align: center;
                font-weight: bold;
            }
            .pass {
                background-color: #d4edda;
            }
            .fail {
                background-color: #f8d7da;
            }
            .skipped {
                background-color: #fff3cd;
            }
            .info {
                background-color: #d9edf7;  /* Light blue background */
            }
            .summary-table {
                margin: 0 auto;
                width: 80%;
            }
            .summary-table td.total-tests {
                text-align: center;
            }
            .chart-container {
                display: flex;
                justify-content: center;
                margin-bottom: 40px;
            }
            .result-summary, .detailed-summary {
                margin-top: 40px;
                padding: 20px;
                background-color: #fff;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            .result-summary h2 {
                border-bottom: 2px solid #27ae60;
                padding-bottom: 10px;
                margin-bottom: 20px;
                font-weight: bold;
            }
            .test-suite-header {
                font-size: 22px;
                font-weight: bold;
                color: #34495e;
            }
            .test-suite-description {
                font-size: 20px;
                margin-bottom: 20px;
                color: #7f8c8d;
            }
            .test-case-header {
                font-size: 20px;
                font-weight: bold;
                color: #16a085;
                margin-top: 10px;
            }
            .test-case-description {
                font-size: 18px;
                margin-bottom: 15px;
                color: #7f8c8d;
            }
            .detailed-summary td:nth-child(3) {
                text-align: center;
                font-weight: bold;
            }
            .dropdown {
                margin: 20px 0;
                text-align: center;
            }
            .dropdown select {
                padding: 10px;
                font-size: 16px;
            }
        </style>
        <script>
            function jumpToSection() {
                var select = document.getElementById('sectionSelect');
                var sectionId = select.options[select.selectedIndex].value;
                location.hash = sectionId;
            }
        </script>
    </head>
    <body>
        <h1>{{ test_suite_name }} Test Summary</h1>

        {% if not is_summary_page %}
        <div class="chart-container">
            <img src="data:image/png;base64,{{ chart_data }}" alt="OS Test Results">
        </div>
        {% endif %}

        <div class="result-summary">
            <h2>Result Summary</h2>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Total Tests</td>
                        <td class="total-tests">{{ total_tests }}</td>
                    </tr>
                    <tr>
                        <td>Passed</td>
                        <td class="pass">{{ total_passed }}</td>
                    </tr>
                    <tr>
                        <td>Failed</td>
                        <td class="fail">{{ total_failed }}</td>
                    </tr>
                    <tr>
                        <td>Skipped</td>
                        <td class="skipped">{{ total_skipped }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
        {% if include_drop_down %}
        <div class="dropdown">
            <label for="sectionSelect">Jump to Test Case:</label>
            <select id="sectionSelect" onchange="jumpToSection()">
                {% for idx, test_results in enumerate(test_results_list) %}
                {% for test_idx, test in enumerate(test_results) %}
                {% if not test.is_boot_source %}
                <option value="section{{ idx }}_{{ test_idx }}">{{ test.Test_case }}</option>
                {% endif %}
                {% endfor %}
                {% endfor %}
            </select>
        </div>
        {% endif %}
        <div class="detailed-summary">
            {% for idx, test_results in enumerate(test_results_list) %}
            {% for test_idx, test in enumerate(test_results) %}
            <a id="section{{ idx }}_{{ test_idx }}"></a>
            <div class="test-suite-header">Test Suite: {{ test.Test_suite_name }}</div>
            <div class="test-suite-description">Description: {{ test.Test_suite_description }}</div>
            
            {% if test.Test_case %}
            <div class="test-case-header">Test Case: {{ test.Test_case }}</div>
            {% endif %}
            {% if test.Test_case_description %}
            <div class="test-case-description">Description: {{ test.Test_case_description }}</div>
            {% endif %}
            
            {% if test.subtests %}
            <!-- Replace dynamic pass/fail/skip columns with single Reason + Waiver Reason columns -->
            <table>
                <thead>
                    <tr>
                        <th>Sub Test Number</th>
                        <th>Sub Test Description</th>
                        <th>Sub Test Result</th>
                        <th>Reason</th>
                        <th>Waiver Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {% for subtest in test.subtests %}
                    {% set subtest_status = get_subtest_status(subtest.sub_test_result) %}
                    <tr>
                        <td>{{ subtest.sub_Test_Number }}</td>
                        <td>{{ subtest.sub_Test_Description }}</td>
                        <td class="{% if subtest_status == 'PASSED' %}pass{% elif subtest_status == 'FAILED' %}fail{% elif subtest_status == 'SKIPPED' %}skipped{% else %}info{% endif %}">
                            {{ subtest_status }}
                        </td>
                        {% set all_reasons = [] %}
                        {% if subtest.sub_test_result.pass_reasons %}
                            {% for reason in subtest.sub_test_result.pass_reasons %}
                                {% set _ = all_reasons.append(reason) %}
                            {% endfor %}
                        {% endif %}
                        {% if subtest.sub_test_result.fail_reasons %}
                            {% for reason in subtest.sub_test_result.fail_reasons %}
                                {% set _ = all_reasons.append(reason) %}
                            {% endfor %}
                        {% endif %}
                        {% if subtest.sub_test_result.skip_reasons %}
                            {% for reason in subtest.sub_test_result.skip_reasons %}
                                {% set _ = all_reasons.append(reason) %}
                            {% endfor %}
                        {% endif %}
                        <td>
                            {{ all_reasons|join("; ") if all_reasons else "N/A" }}
                        </td>
                        <td>
                            {{ subtest.sub_test_result.waiver_reason if subtest.sub_test_result.waiver_reason else "N/A" }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            {% endfor %}
            {% endfor %}
        </div>
        {% endif %}
    </body>
    </html>
    """)

    # Calculate total tests
    total_tests = suite_summary.get('total_passed', 0) + suite_summary.get('total_failed', 0) + suite_summary.get('total_skipped', 0)

    # If not summary page, generate chart data
    if not is_summary_page:
        chart_data = generate_bar_chart(suite_summary)
    else:
        chart_data = None  # No chart data for summary page

    # Render the HTML content
    html_content = template.render(
        test_suite_name=test_suite_name,
        total_tests=total_tests,
        total_passed=suite_summary.get("total_passed", 0),
        total_failed=suite_summary.get("total_failed", 0),
        total_skipped=suite_summary.get("total_skipped", 0),
        test_results_list=test_results_list,
        is_summary_page=is_summary_page,
        include_drop_down=include_drop_down,
        chart_data=chart_data,  # Will be None if is_summary_page is True
        enumerate=enumerate,
        get_subtest_status=get_subtest_status  # Pass the function to the template
    )

    # Save to HTML file
    with open(output_html_path, "w") as file:
        file.write(html_content)

def main():
    parser = argparse.ArgumentParser(description='Generate HTML report from JSON data.')
    parser.add_argument('input_json_files', nargs='+', help='Input JSON file(s)')
    parser.add_argument('detailed_html_file', help='Detailed HTML output file')
    parser.add_argument('summary_html_file', help='Summary HTML output file')
    parser.add_argument('--include-drop-down', action='store_true', help='Include drop-down menu in detailed summary')
    parser.add_argument('--boot-sources-paths', nargs='*', help='Paths to boot_sources.log files for each OS')
    args = parser.parse_args()

    test_results_list = []
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_skipped = 0

    boot_sources_paths = args.boot_sources_paths if args.boot_sources_paths else []

    for idx, input_json_file in enumerate(args.input_json_files):
        with open(input_json_file, 'r') as json_file:
            try:
                data = json.load(json_file)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from file {input_json_file}: {e}")
                continue

            test_results = data.get("test_results", [])
            os_name = data.get("os_name", "Unknown")
            if test_results:
                if idx < len(boot_sources_paths):
                    boot_sources_path = boot_sources_paths[idx]
                else:
                    boot_sources_path = "Unknown"

                if os_name == "Unknown" and boot_sources_path != "Unknown":
                    # Try to extract OS name from the boot_sources_path
                    os_name = boot_sources_path.split('/')[-2]  

                # Insert the Boot Sources test
                boot_sources_test = {
                    "Test_suite_name": "Boot Sources",
                    "Test_suite_description": "Check for boot sources",
                    "Test_case": f"Boot Sources for {os_name}",
                    "Test_case_description": f"Please review the boot source OS logs for {os_name} - path of {boot_sources_path}",
                    "subtests": [],
                    "is_boot_source": True
                }
                test_results.append(boot_sources_test)

                # Tally pass/fail/skip
                for test in test_results:
                    if test.get('is_boot_source'):
                        continue

                    total_tests += 1
                    test_status = 'PASSED'
                    has_skipped = False
                    has_pass = False

                    if test.get('subtests'):
                        for subtest in test['subtests']:
                            subtest_status = get_subtest_status(subtest['sub_test_result'])
                            if subtest_status == 'FAILED':
                                test_status = 'FAILED'
                                break
                            elif subtest_status == 'SKIPPED':
                                has_skipped = True
                            elif subtest_status not in ('PASSED', 'SKIPPED'):
                                # treat any other status as failure
                                test_status = 'FAILED'
                                break
                            elif subtest_status == 'PASSED':
                                has_pass = True
                        else:
                            if test_status != 'FAILED':
                                test_status = 'PASSED' if has_pass else 'SKIPPED'
                    else:
                        test_status = 'SKIPPED'

                    if test_status == 'PASSED':
                        total_passed += 1
                    elif test_status == 'FAILED':
                        total_failed += 1
                    else:  # 'SKIPPED' or fallback
                        total_skipped += 1

                #
                # For each test, figure out which columns to show
                #
                for t in test_results:
                    subtests = t.get("subtests", [])
                    t["columns_used"] = detect_columns_used(subtests)

                test_results_list.append(test_results)

    # Build the suite_summary
    suite_summary = {
        'total_passed': total_passed,
        'total_failed': total_failed,
        'total_skipped': total_skipped,
    }

    if total_tests == 0:
        print("No valid JSON data found in input files.")
        sys.exit(1)

    # Generate the detailed summary page
    generate_html(
        suite_summary,
        test_results_list,
        args.detailed_html_file,
        is_summary_page=False,
        include_drop_down=args.include_drop_down
    )

    # Generate the summary page
    generate_html(
        suite_summary,
        test_results_list,
        args.summary_html_file,
        is_summary_page=True
    )

if __name__ == "__main__":
    main()
