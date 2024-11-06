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
import os

# Helper function to retrieve dictionary values in a case-insensitive manner
def get_case_insensitive(d, key, default=0):
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default

# Function to generate bar chart for test results
def generate_bar_chart(suite_summary):
    labels = ['Passed', 'Failed', 'Failed with Waiver', 'Aborted', 'Skipped', 'Warnings']
    sizes = [
        suite_summary.get('total_PASSED', 0),
        suite_summary.get('total_FAILED', 0),
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_ABORTED', 0),
        suite_summary.get('total_SKIPPED', 0),
        suite_summary.get('total_WARNINGS', 0)
    ]
    colors = ['#66bb6a', '#ef5350', '#f39c12', '#9e9e9e', '#ffc107', '#ffeb3b']  # Colors for each category

    plt.figure(figsize=(12, 7))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    # Add percentage labels on top of the bars
    total_tests = sum(sizes)
    for bar, size in zip(bars, sizes):
        yval = bar.get_height()
        percentage = (size / total_tests) * 100 if total_tests > 0 else 0
        plt.text(
            bar.get_x() + bar.get_width()/2, 
            yval + max(sizes)*0.01, 
            f'{percentage:.2f}%', 
            ha='center', 
            va='bottom', 
            fontsize=12
        )

    plt.title('Test Results Distribution', fontsize=18, fontweight='bold')
    plt.ylabel('Total Count', fontsize=14)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.tight_layout()

    # Save the figure to a buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# Function to generate HTML content for both summary and detailed pages
def generate_html(suite_summary, test_results, chart_data, output_html_path, test_suite_name, is_summary_page=True):
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
            .pass {
                background-color: #d4edda;
                font-weight: bold;
            }
            .fail {
                background-color: #f8d7da;
                font-weight: bold;
            }
            .fail-waiver {  /* CSS class for Failed with Waiver */
                background-color: #ffeeba;
                font-weight: bold;
            }
            .warning {
                background-color: #fff3cd;
                font-weight: bold;
            }
            .aborted {
                background-color: #9e9e9e;
                font-weight: bold;
            }
            .skipped {
                background-color: #ffc107;
                font-weight: bold;
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
                margin-top: 30px;
            }
            .test-suite-description {
                font-size: 20px;
                margin-bottom: 20px;
                color: #7f8c8d;
            }
            td.pass, td.fail, td.fail-waiver, td.warning, td.aborted, td.skipped {
                text-align: center;
                font-weight: bold;
            }
            /* New CSS class for Waiver Reason */
            td.waiver-reason {
                text-align: center;
                font-weight: normal;
            }
        </style>
    </head>
    <body>
        <h1>{{ test_suite_name }} Test Summary</h1>

        {% if not is_summary_page %}
        <div class="chart-container">
            <img src="data:image/png;base64,{{ chart_data }}" alt="Test Results Distribution">
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
                        <td class="pass">{{ total_PASSED }}</td>
                    </tr>
                    <tr>
                        <td>Failed</td>
                        <td class="fail">{{ total_FAILED }}</td>
                    </tr>
                    <tr>
                        <td>Failed with Waiver</td>
                        <td class="fail-waiver">{{ total_failed_with_waiver }}</td>
                    </tr>
                    <tr>
                        <td>Aborted</td>
                        <td class="aborted">{{ total_ABORTED }}</td>
                    </tr>
                    <tr>
                        <td>Skipped</td>
                        <td class="skipped">{{ total_SKIPPED }}</td>
                    </tr>
                    <tr>
                        <td>Warnings</td>
                        <td class="warning">{{ total_WARNINGS }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
        <div class="detailed-summary">
            {% for test in test_results %}
            <div class="test-suite-header">Test Suite: {{ test.Test_suite }}</div>
            <table>
                <thead>
                    <tr>
                        <th>Sub Test Number</th>
                        <th>Sub Test Description</th>
                        <th>Sub Test Result</th>
                        <th>Rules Failed/Skipped</th>
                        <!-- New Column Header for Waiver Reason -->
                        <th>Waiver Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {% for subtest in test.subtests %}
                    <tr>
                        <td>{{ subtest.sub_Test_Number }}</td>
                        <td>{{ subtest.sub_Test_Description }}</td>
                        <td class="{% if subtest.sub_test_result == 'PASSED' %}pass{% elif subtest.sub_test_result == 'FAILED (WITH WAIVER)' %}fail-waiver{% elif subtest.sub_test_result == 'FAILED' %}fail{% elif subtest.sub_test_result == 'ABORTED' %}aborted{% elif subtest.sub_test_result == 'SKIPPED' %}skipped{% elif subtest.sub_test_result == 'WARNING' %}warning{% endif %}">
                            {{ subtest.sub_test_result }}
                        </td>
                        <td>
                            {% if 'FAILED' in subtest.sub_test_result and 'RULES FAILED' in subtest %}
                                {{ subtest['RULES FAILED'] }}
                            {% elif 'SKIPPED' in subtest.sub_test_result and 'RULES SKIPPED' in subtest %}
                                {{ subtest['RULES SKIPPED'] }}
                            {% else %}
                                N/A
                            {% endif %}
                        </td>
                        <!-- New Data Cell for Waiver Reason -->
                        <td class="waiver-reason">
                            {% if 'FAILED (WITH WAIVER)' in subtest.sub_test_result %}
                                {{ subtest.waiver_reason | default("N/A") }}
                            {% else %}
                                N/A
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endfor %}
        </div>
        {% endif %}
    </body>
    </html>
    """)

    # Calculate total_failed_with_waiver by summing from each test suite
    total_failed_with_waiver = 0
    for test_suite in test_results:
        ts_summary = test_suite.get('test_suite_summary', {})
        total_failed_with_waiver += get_case_insensitive(ts_summary, 'total_failed_with_waiver')

    # Compute overall suite_summary from test_results
    suite_summary = {
        'total_PASSED': 0,
        'total_FAILED': 0,  # Only counts FAILED without waiver
        'total_failed_with_waiver': total_failed_with_waiver,
        'total_ABORTED': 0,
        'total_SKIPPED': 0,
        'total_WARNINGS': 0
    }

    for test_suite in test_results:
        ts_summary = test_suite.get('test_suite_summary', {})
        suite_summary['total_PASSED'] += get_case_insensitive(ts_summary, 'total_passed')
        suite_summary['total_FAILED'] += get_case_insensitive(ts_summary, 'total_failed')
        # 'total_failed_with_waiver' already summed above
        suite_summary['total_ABORTED'] += get_case_insensitive(ts_summary, 'total_aborted')
        suite_summary['total_SKIPPED'] += get_case_insensitive(ts_summary, 'total_skipped')
        suite_summary['total_WARNINGS'] += get_case_insensitive(ts_summary, 'total_warnings')

    # Calculate total tests
    total_tests = (
        suite_summary.get("total_PASSED", 0)
        + suite_summary.get("total_FAILED", 0)
        + suite_summary.get("total_ABORTED", 0)
        + suite_summary.get("total_SKIPPED", 0)
        + suite_summary.get("total_WARNINGS", 0)
    )

    # Render the HTML content
    html_content = template.render(
        chart_data=chart_data,
        total_tests=total_tests,
        total_PASSED=suite_summary.get("total_PASSED", 0),
        total_FAILED=suite_summary.get("total_FAILED", 0),
        total_failed_with_waiver=suite_summary.get("total_failed_with_waiver", 0),
        total_ABORTED=suite_summary.get("total_ABORTED", 0),
        total_SKIPPED=suite_summary.get("total_SKIPPED", 0),
        total_WARNINGS=suite_summary.get("total_WARNINGS", 0),
        test_results=test_results,
        is_summary_page=is_summary_page,
        test_suite_name=test_suite_name.upper()  # Ensure uppercase for consistency
    )

    # Save to HTML file
    with open(output_html_path, "w") as file:
        file.write(html_content)

# Main function to process the JSON file and generate the HTML report
def main(input_json_file, detailed_html_file, summary_html_file):
    # Load JSON data
    with open(input_json_file, 'r') as json_file:
        data = json.load(json_file)

    # Extract the suite summary and test results
    # Assuming the last element is the overall Suite_summary
    test_results = data[:-1]

    # Get the test suite name from the input JSON file name
    test_suite_name = os.path.splitext(os.path.basename(input_json_file))[0].upper()

    # Generate bar chart as base64 encoded image
    # suite_summary from the last element is ignored; recompute from test_results
    # We'll pass a temporary summary to generate_bar_chart, which we'll recompute here
    # Alternatively, modify generate_bar_chart to accept individual counts
    # To keep it simple, compute the overall summary here and pass to both functions

    # Recompute suite_summary
    def get_case_insensitive(d, key, default=0):
        for k, v in d.items():
            if k.lower() == key.lower():
                return v
        return default

    suite_summary = {
        'total_PASSED': 0,
        'total_FAILED': 0,  # Only counts FAILED without waiver
        'total_failed_with_waiver': 0,
        'total_ABORTED': 0,
        'total_SKIPPED': 0,
        'total_WARNINGS': 0
    }

    for test_suite in test_results:
        ts_summary = test_suite.get('test_suite_summary', {})
        suite_summary['total_PASSED'] += get_case_insensitive(ts_summary, 'total_passed')
        suite_summary['total_FAILED'] += get_case_insensitive(ts_summary, 'total_failed')
        suite_summary['total_failed_with_waiver'] += get_case_insensitive(ts_summary, 'total_failed_with_waiver')
        suite_summary['total_ABORTED'] += get_case_insensitive(ts_summary, 'total_aborted')
        suite_summary['total_SKIPPED'] += get_case_insensitive(ts_summary, 'total_skipped')
        suite_summary['total_WARNINGS'] += get_case_insensitive(ts_summary, 'total_warnings')

    # Generate bar chart
    chart_data = generate_bar_chart(suite_summary)

    # Generate the detailed summary page
    generate_html(suite_summary, test_results, chart_data, detailed_html_file, test_suite_name, is_summary_page=False)

    # Generate the summary page with the bar chart
    generate_html(suite_summary, test_results, chart_data, summary_html_file, test_suite_name, is_summary_page=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python json_to_html.py <input_json_file> <detailed_html_file> <summary_html_file>")
        sys.exit(1)

    input_json_file = sys.argv[1]
    detailed_html_file = sys.argv[2]  # This will be the detailed HTML report
    summary_html_file = sys.argv[3]  # This will be the summary HTML report

    main(input_json_file, detailed_html_file, summary_html_file)
