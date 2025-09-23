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
from jinja2 import Environment, FileSystemLoader, Template

# Helper function to retrieve dictionary values in a case-insensitive manner
def get_case_insensitive(d, key, default=0):
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default

# Helper function to determine CSS class based on subtest result
def determine_css_class(subtest_result):
    subtest_result_upper = subtest_result.upper()
    if 'FAILED WITH WAIVER' in subtest_result_upper or 'FAILURE (WITH WAIVER)' in subtest_result_upper:
        return 'fail-waiver'
    elif 'FAILED' in subtest_result_upper:
        return 'fail'
    elif 'PASSED' in subtest_result_upper:
        return 'pass'
    elif 'WARNING' in subtest_result_upper:
        return 'warning'
    elif 'ABORTED' in subtest_result_upper:
        return 'aborted'
    elif 'SKIPPED' in subtest_result_upper:
        return 'skipped'
    else:
        # Anything else (IGNORED, KNOWN U-BOOT LIMITATION, etc.) is 'unknown' in the detailed table
        return 'unknown'

# Function to generate bar chart for SCT results with 'Failed with Waiver' and 'Ignored'
def generate_bar_chart_improved(suite_summary):
    # Updated labels to include 'Failed with Waiver' AND 'Ignored'
    labels = [
        'Passed',
        'Failed',
        'Failed with Waiver',
        'Aborted',
        'Skipped',
        'Warnings',
        'Ignored'
    ]
    sizes = [
        suite_summary.get('total_passed', 0),
        suite_summary.get('total_failed', 0) - suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_aborted', 0),
        suite_summary.get('total_skipped', 0),
        suite_summary.get('total_warnings', 0),
        suite_summary.get('total_ignored', 0)  # new field
    ]
    # Updated colors to include a color for 'Ignored'
    colors = [
        '#66bb6a',  # Passed
        '#ef5350',  # Failed
        '#f39c12',  # Failed with Waiver
        '#9e9e9e',  # Aborted
        '#ffc107',  # Skipped
        '#ffeb3b',  # Warnings
        '#b2bec3'   # Ignored (gray-ish)
    ]

    plt.figure(figsize=(12, 7))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    # Add percentage labels on top of each bar
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

    plt.title('SCT Test Results Distribution', fontsize=18, fontweight='bold')
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
def generate_html_improved(suite_summary, test_results, chart_data, output_html_path, is_summary_page=True):
    # Initialize Jinja2 environment
    env = Environment()
    env.filters['determine_css_class'] = determine_css_class

    # Template for both summary and detailed pages with Waiver handling + 'Ignored'
    template = env.from_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SCT Test Summary</title>
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
                table-layout: fixed;
                word-wrap: break-word;
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
            .fail-waiver {
                background-color: #f39c12;
                font-weight: bold;
                color: white;
            }
            .warning {
                background-color: #fff3cd;
                font-weight: bold;
            }
            .aborted {
                background-color: #e0e0e0;
                font-weight: bold;
            }
            .skipped {
                background-color: #ffe0b2;
                font-weight: bold;
            }
            .unknown {
                background-color: #cccccc;
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
            .heading {
                font-size: 18px;
                margin-bottom: 5px;
                color: #34495e;
                font-weight: bold;
            }
            .heading span {
                font-weight: normal;
            }
            td.pass, td.fail, td.fail-waiver, td.warning, td.aborted, td.skipped, td.unknown {
                text-align: center;
                font-weight: bold;
            }
            .waiver-reason {
                text-align: center;
                font-weight: normal;
            }
            .reason-col {
                text-align: center;
                font-weight: normal;
            }
        </style>
    </head>
    <body>
        <h1>SCT Test Summary</h1>

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
                        <td class="pass">{{ total_passed }}</td>
                    </tr>
                    <tr>
                        <td>Failed</td>
                        <td class="fail">{{ total_failed }}</td>
                    </tr>
                    <tr>
                        <td>Failed with Waiver</td>
                        <td class="fail-waiver">{{ total_failed_with_waiver }}</td>
                    </tr>
                    <tr>
                        <td>Aborted</td>
                        <td class="aborted">{{ total_aborted }}</td>
                    </tr>
                    <tr>
                        <td>Skipped</td>
                        <td class="skipped">{{ total_skipped }}</td>
                    </tr>
                    <tr>
                        <td>Warnings</td>
                        <td class="warning">{{ total_warnings }}</td>
                    </tr>
                    <!-- NEW ROW for Ignored -->
                    <tr>
                        <td>Ignored</td>
                        <td class="unknown">{{ total_ignored }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
        <div class="detailed-summary">
            {% for test in test_results %}
            <div class="heading">Test Suite Name: <span>{{ test.Test_suite }}</span></div>
            <div class="heading">Sub Test Suite: <span>{{ test.Sub_test_suite }}</span></div>
            <div class="heading">Test Case: <span>{{ test.Test_case }}</span></div>
            <div class="heading">Test Case Description: <span>{{ test.Test_case_description }}</span></div>
            <div class="heading">Test Entry Point GUID: <span>{{ test["Test Entry Point GUID"] }}</span></div>
            <div class="heading">Test Result: <span>{{ test.test_result if test.test_result else "N/A" }}</span></div>
            <div class="heading">Reason: <span>{{ test.reason if test.reason else "N/A" }}</span></div>
            <div class="heading">Device Path: <span>{{ test.get('Device Path', 'N/A') }}</span></div>
            <br>
            <table>
                <thead>
                    <tr>
                        <th>Sub Test GUID</th>
                        <th>Sub Test Description</th>
                        <th>Sub Test Result</th>
                        <th>Sub Test Path</th>
                        <th>Reason</th>
                        <th>Waiver Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {% for subtest in test.subtests %}
                    <tr>
                        <td>{{ subtest.sub_Test_GUID }}</td>
                        <td>{{ subtest.sub_Test_Description }}</td>
                        <td class="{{ subtest.sub_test_result | determine_css_class }}">{{ subtest.sub_test_result }}</td>
                        <td>{{ subtest.sub_Test_Path }}</td>
                        <td class="reason-col">
                            {{ subtest.reason if subtest.reason else "N/A" }}
                        </td>
                        <td class="waiver-reason">
                            {% if 'FAILED WITH WAIVER' in subtest.sub_test_result.upper() or 'FAILURE (WITH WAIVER)' in subtest.sub_test_result.upper() %}
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

    # Instead of re-summing, we just read the final suite_summary from the JSON
    total_tests = (
        suite_summary["total_passed"]
        + suite_summary["total_failed"] - suite_summary["total_failed_with_waiver"]
        + suite_summary["total_failed_with_waiver"]
        + suite_summary["total_aborted"]
        + suite_summary["total_skipped"]
        + suite_summary["total_warnings"]
        + suite_summary.get("total_ignored", 0)
    )

    # Render the HTML content
    html_content = template.render(
        chart_data=chart_data,
        total_tests=total_tests,
        total_passed=suite_summary.get("total_passed", 0),
        total_failed=suite_summary.get("total_failed", 0),
        total_failed_with_waiver=suite_summary.get("total_failed_with_waiver", 0),
        total_aborted=suite_summary.get("total_aborted", 0),
        total_skipped=suite_summary.get("total_skipped", 0),
        total_warnings=suite_summary.get("total_warnings", 0),
        total_ignored=suite_summary.get("total_ignored", 0),
        test_results=test_results,
        is_summary_page=is_summary_page
    )

    with open(output_html_path, "w") as file:
        file.write(html_content)

def main(input_json_file, detailed_html_file, summary_html_file):
    # Load JSON data
    with open(input_json_file, 'r') as json_file:
        data = json.load(json_file)

    # We DIRECTLY take the final suite_summary from the JSON
    suite_summary = data["suite_summary"]
    # And the test_results
    test_results = data["test_results"]

    # Generate improved bar chart as base64 encoded image
    chart_data = generate_bar_chart_improved(suite_summary)

    # Generate the detailed summary page
    generate_html_improved(suite_summary, test_results, chart_data, detailed_html_file, is_summary_page=False)

    # Generate the summary page with the bar chart
    generate_html_improved(suite_summary, test_results, chart_data, summary_html_file, is_summary_page=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python json_to_html.py <input_json_file> <detailed_html_file> <summary_html_file>")
        sys.exit(1)

    input_json_file = sys.argv[1]
    detailed_html_file = sys.argv[2]
    summary_html_file = sys.argv[3]

    main(input_json_file, detailed_html_file, summary_html_file)
