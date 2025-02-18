#!/usr/bin/env python3
# Copyright (c) 2024, Arm Limited or its affiliates. All rights reserved.
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

# Function to generate bar chart for test results
def generate_bar_chart(suite_summary):
    labels = ['Passed', 'Failed', 'Failed with Waiver']  # Three categories
    sizes = [
        suite_summary.get('total_PASSED', 0),
        suite_summary.get('total_FAILED', 0),
        suite_summary.get('total_FAILED_WITH_WAIVER', 0)
    ]
    colors = ['#66bb6a', '#ef5350', '#f39c12']  # Colors for Passed, Failed, Failed with Waiver

    plt.figure(figsize=(8, 6))  # Adjusted figure size
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

    plt.title('STANDALONE Test Results', fontsize=16, fontweight='bold', pad=20)
    plt.ylabel('Number of STANDALONEs', fontsize=14)
    plt.tight_layout()

    # Save the figure to a buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# Function to generate HTML content for both summary and detailed pages
def generate_html(suite_summary, test_results_list, output_html_path, is_summary_page=True, include_drop_down=False):
    # Set the test suite name to 'STANDALONE' when combining multiple tests
    test_suite_name = 'STANDALONE'

    # Template for both summary and detailed pages
    template = Template("""
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
            /* Center-align and bold the second cell in each row */
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
            .waiver {
                background-color: #f39c12; /* Color for Failed with Waiver */
            }
            .summary-table {
                margin: 0 auto;
                width: 80%;
            }
            /* Center the Total Tests value */
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
            /* New styles for Test Case */
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
            /* Center-align and bold the result cells in detailed tables */
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
            <img src="data:image/png;base64,{{ chart_data }}" alt="STANDALONE Test Results">
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
                        <td>Total STANDALONEs</td>
                        <td class="total-tests">{{ total_tests }}</td>
                    </tr>
                    <tr>
                        <td>Passed</td>
                        <td class="pass">{{ total_PASSED }}</td>
                    </tr>
                    <tr>
                        <td>Failed</td>
                        <td class="fail">{{ total_FAILED }}</td>
                    </tr>
                    <tr>
                        <td>Failed with Waiver</td>
                        <td class="waiver">{{ total_FAILED_WITH_WAIVER }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
        {% if include_drop_down %}
        <div class="dropdown">
            <label for="sectionSelect">Jump to STANDALONE Test:</label>
            <select id="sectionSelect" onchange="jumpToSection()">
                {% for idx, test_results in enumerate(test_results_list) %}
                {% if test_results and test_results[0] %}
                {% set test = test_results[0] %}
                <option value="section{{ idx }}">{{ test.Test_suite_name }} - {{ test.Test_case }}</option>
                {% endif %}
                {% endfor %}
            </select>
        </div>
        {% endif %}
        <div class="detailed-summary">
            {% for idx, test_results in enumerate(test_results_list) %}
            {% if include_drop_down %}
            <a id="section{{ idx }}"></a>
            {% endif %}
            {% for test in test_results %}
            <!-- Updated to use Test_suite_name and Test_suite_description -->
            <div class="test-suite-header">Test Suite: {{ test.Test_suite_name }}</div>
            <div class="test-suite-description">Description: {{ test.Test_suite_description }}</div>
            
            <!-- New Test Case Section -->
            <div class="test-case-header">Test Case: {{ test.Test_case }}</div>
            <div class="test-case-description">Description: {{ test.Test_case_description }}</div>
            
            <table>
                <thead>
                    <tr>
                        <th>Sub Test Number</th>
                        <th>Sub Test Description</th>
                        <th>Sub Test Result</th>
                        <th>Pass Reasons</th>
                        <th>Fail Reasons</th>
                        <th>Abort Reasons</th>
                        <th>Skip Reasons</th>
                        <th>Warning Reasons</th>
                        <th>Waiver Reason</th> <!-- New column -->
                    </tr>
                </thead>
                <tbody>
                    {% for subtest in test.subtests %}
                    <tr>
                        <td>{{ subtest.sub_Test_Number }}</td>
                        <td>{{ subtest.sub_Test_Description }}</td>
                        <td class="{% if subtest.sub_test_result.PASSED > 0 %}pass{% elif subtest.sub_test_result.FAILED > 0 %}fail{% elif subtest.sub_test_result.ABORTED > 0 %}aborted{% elif subtest.sub_test_result.SKIPPED > 0 %}skipped{% elif subtest.sub_test_result.WARNINGS > 0 %}warning{% elif subtest.sub_test_result.FAILED_WITH_WAIVER > 0 %}waiver{% else %}unknown{% endif %}">
                            {% if subtest.sub_test_result.PASSED > 0 %}
                                PASSED
                            {% elif subtest.sub_test_result.FAILED > 0 %}
                                FAILED
                            {% elif subtest.sub_test_result.ABORTED > 0 %}
                                ABORTED
                            {% elif subtest.sub_test_result.SKIPPED > 0 %}
                                SKIPPED
                            {% elif subtest.sub_test_result.WARNINGS > 0 %}
                                WARNINGS
                            {% elif subtest.sub_test_result.FAILED_WITH_WAIVER > 0 %}
                                FAILED WITH WAIVER
                            {% else %}
                                UNKNOWN
                            {% endif %}
                        </td>
                        <td>{{ subtest.sub_test_result.pass_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.fail_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.abort_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.skip_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.warning_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.waiver_reason if subtest.sub_test_result.FAILED_WITH_WAIVER else '' }}</td> <!-- Waiver Reason -->
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endfor %}
            {% endfor %}
        </div>
        {% endif %}
    </body>
    </html>
    """)

    # Calculate total STANDALONEs
    total_tests = suite_summary.get('total_PASSED', 0) + suite_summary.get('total_FAILED', 0) + suite_summary.get('total_FAILED_WITH_WAIVER', 0)

    # If not summary page, generate chart data
    if not is_summary_page:
        chart_data = generate_bar_chart(suite_summary)
    else:
        chart_data = None  # No chart data for summary page

    # Render the HTML content
    html_content = template.render(
        test_suite_name=test_suite_name,
        total_tests=total_tests,
        total_PASSED=suite_summary.get("total_PASSED", 0),
        total_FAILED=suite_summary.get("total_FAILED", 0),
        total_FAILED_WITH_WAIVER=suite_summary.get("total_FAILED_WITH_WAIVER", 0),
        test_results_list=test_results_list,
        is_summary_page=is_summary_page,
        include_drop_down=include_drop_down,
        chart_data=chart_data,  # Will be None if is_summary_page is True
        enumerate=enumerate  # Pass 'enumerate' to the template context
    )

    # Save to HTML file
    with open(output_html_path, "w") as file:
        file.write(html_content)

# Function to get the status of a subtest
def get_subtest_status(subtest_result):
    if subtest_result.get('PASSED', 0) > 0:
        return 'PASSED'
    elif subtest_result.get('FAILED', 0) > 0:
        return 'FAILED'
    elif subtest_result.get('FAILED_WITH_WAIVER', 0) > 0:  # Handle waiver failure
        return 'FAILED_WITH_WAIVER'
    elif subtest_result.get('ABORTED', 0) > 0:
        return 'ABORTED'
    elif subtest_result.get('SKIPPED', 0) > 0:
        return 'SKIPPED'
    elif subtest_result.get('WARNINGS', 0) > 0:
        return 'WARNINGS'
    else:
        return 'UNKNOWN'

def main():
    parser = argparse.ArgumentParser(description='Generate HTML report from JSON data.')
    parser.add_argument('input_json_files', nargs='+', help='Input JSON file(s)')
    parser.add_argument('detailed_html_file', help='Detailed HTML output file')
    parser.add_argument('summary_html_file', help='Summary HTML output file')
    parser.add_argument('--include-drop-down', action='store_true', help='Include drop-down menu in detailed summary')
    args = parser.parse_args()

    # Load JSON data
    test_results_list = []

    # Initialize combined_suite_summary
    combined_suite_summary = {
        'total_PASSED': 0,
        'total_FAILED': 0,
        'total_FAILED_WITH_WAIVER': 0,
    }

    for input_json_file in args.input_json_files:
        with open(input_json_file, 'r') as json_file:
            try:
                data = json.load(json_file)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from file {input_json_file}: {e}")
                continue

            test_results = data.get("test_results", [])
            if test_results:
                test_results_list.append(test_results)

                # For each STANDALONE (test suite), determine overall result
                for test in test_results:
                    standalone_failed = False
                    failed_with_waiver = False

                    # Flags to determine if STANDALONE is failed with waiver only
                    has_failed_without_waiver = False
                    has_failed_with_waiver = False

                    for subtest in test.get('subtests', []):
                        subtest_result = subtest.get('sub_test_result', {})
                        status = get_subtest_status(subtest_result)

                        if status == 'FAILED':
                            has_failed_without_waiver = True
                        elif status == 'FAILED_WITH_WAIVER':
                            has_failed_with_waiver = True

                    if has_failed_without_waiver:
                        combined_suite_summary['total_FAILED'] += 1
                    elif has_failed_with_waiver:
                        combined_suite_summary['total_FAILED_WITH_WAIVER'] += 1
                    else:
                        combined_suite_summary['total_PASSED'] += 1

    # Calculate total STANDALONEs
    total_standalones = combined_suite_summary['total_PASSED'] + combined_suite_summary['total_FAILED'] + combined_suite_summary['total_FAILED_WITH_WAIVER']

    if total_standalones == 0:
        print("No valid JSON data found in input files.")
        sys.exit(1)

    # Update the combined_suite_summary with total_tests
    combined_suite_summary['total_tests'] = total_standalones

    # Generate the detailed summary page
    generate_html(
        combined_suite_summary,
        test_results_list,
        args.detailed_html_file,
        is_summary_page=False,
        include_drop_down=args.include_drop_down
    )

    # Generate the summary page (with bar graph)
    generate_html(
        combined_suite_summary,
        test_results_list,
        args.summary_html_file,
        is_summary_page=True
    )

if __name__ == "__main__":
    main()
