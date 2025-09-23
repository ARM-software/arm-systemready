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
import os

# Helper function to retrieve dictionary values in a case-insensitive manner
def get_case_insensitive(d, key, default=0):
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default

def detect_columns_used(subtests):
    show_waiver = False
    for subtest in subtests:
        r = subtest.get("sub_test_result", {})
        if r.get("FAILED_WITH_WAIVER", 0) > 0:
            show_waiver = True
            break
    return {
        "show_waiver": show_waiver
    }

# Function to generate bar chart for FWTS results
def generate_bar_chart_fwts(suite_summary):
    labels = ['Passed', 'Failed', 'Failed with Waiver', 'Aborted', 'Skipped', 'Warnings']
    sizes = [
        suite_summary['total_passed'],
        suite_summary['total_failed'],
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary['total_aborted'],
        suite_summary['total_skipped'],
        suite_summary['total_warnings']
    ]
    colors = ['#66bb6a', '#ef5350', '#f39c12', '#9e9e9e', '#ffc107', '#ffeb3b']

    plt.figure(figsize=(12, 7))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    total_tests = sum(sizes)
    max_size = max(sizes) if sizes else 0
    for bar, size in zip(bars, sizes):
        yval = bar.get_height()
        percentage = (size / total_tests) * 100 if total_tests > 0 else 0
        plt.text(
            bar.get_x() + bar.get_width()/2,
            yval + (0.01 * max_size if max_size > 0 else 0.05),
            f'{percentage:.2f}%',
            ha='center',
            va='bottom',
            fontsize=12
        )

    plt.title('FWTS Test Results Distribution', fontsize=18, fontweight='bold')
    plt.ylabel('Total Count', fontsize=14)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# Function to generate HTML content for both summary and detailed pages
def generate_html_fwts(suite_summary, test_results, chart_data, output_html_path, is_summary_page=True):
    # Jinja2 template with ONE "Reason" column + a fixed "Waiver Reason" column
    template = Template(r"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FWTS Test Summary</title>
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
            .fail-waiver {
                background-color: #f39c12;
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
                background-color: #ffe0b2;
                font-weight: bold;
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
            td.pass, td.fail, td.fail-waiver, td.warning, td.aborted, td.skipped {
                text-align: center;
                font-weight: bold;
            }
            td.waiver-reason {
                text-align: center;
                font-weight: normal;
            }
        </style>
    </head>
    <body>
        <h1>FWTS Test Summary</h1>

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
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
        <div class="detailed-summary">
            {% for test in test_results %}
            <div class="test-suite-header">Test Suite: {{ test.Test_suite }}</div>
            <div class="test-suite-description">Description: {{ test.Test_suite_description }}</div>

            <table>
                <thead>
                    <tr>
                        <th>Sub Test Number</th>
                        <th>Sub Test Description</th>
                        <th>Sub Test Result</th>
                        <th>Reason</th>
                        <th>Waiver Reason</th>  <!-- Fixed column for Waiver Reason -->
                    </tr>
                </thead>
                <tbody>
                    {% for subtest in test.subtests %}
                    {% set s = subtest.sub_test_result %}
                    <tr>
                        <td>{{ subtest.sub_Test_Number }}</td>
                        <td>{{ subtest.sub_Test_Description }}</td>
                        <td class="{% if s.FAILED > 0 %}fail
                                    {% elif s.PASSED > 0 %}pass
                                    {% elif s.FAILED_WITH_WAIVER|default(0) > 0 %}fail-waiver
                                    {% elif s.ABORTED > 0 %}aborted
                                    {% elif s.SKIPPED > 0 %}skipped
                                    {% elif s.WARNINGS > 0 %}warning
                                    {% endif %}">
                            {% if s.FAILED > 0 %}
                                FAILED
                            {% elif s.PASSED > 0 %}
                                PASSED
                            {% elif s.FAILED_WITH_WAIVER|default(0) > 0 %}
                                FAILED WITH WAIVER
                            {% elif s.ABORTED > 0 %}
                                ABORTED
                            {% elif s.SKIPPED > 0 %}
                                SKIPPED
                            {% elif s.WARNINGS > 0 %}
                                WARNINGS
                            {% else %}
                                UNKNOWN
                            {% endif %}
                        </td>
                        {# Consolidate all reasons into one block #}
                        {% set all_reasons = [] %}
                        {% if s.pass_reasons %}{% for reason in s.pass_reasons %}{% set _ = all_reasons.append(reason) %}{% endfor %}{% endif %}
                        {% if s.fail_reasons %}{% for reason in s.fail_reasons %}{% set _ = all_reasons.append(reason) %}{% endfor %}{% endif %}
                        {% if s.abort_reasons %}{% for reason in s.abort_reasons %}{% set _ = all_reasons.append(reason) %}{% endfor %}{% endif %}
                        {% if s.skip_reasons %}{% for reason in s.skip_reasons %}{% set _ = all_reasons.append(reason) %}{% endfor %}{% endif %}
                        {% if s.warning_reasons %}{% for reason in s.warning_reasons %}{% set _ = all_reasons.append(reason) %}{% endfor %}{% endif %}
                        <td>{{ all_reasons|join("<br>") if all_reasons else "N/A" }}</td>

                        <td class="waiver-reason">
                            {% if s.FAILED_WITH_WAIVER|default(0) > 0 %}
                                {{ s.waiver_reason|default("N/A") }}
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

    total_tests = (
        suite_summary["total_passed"]
        + suite_summary["total_failed"]
        + suite_summary["total_aborted"]
        + suite_summary["total_skipped"]
        + suite_summary["total_warnings"]
    )

    html_content = template.render(
        chart_data=chart_data,
        total_tests=total_tests,
        total_passed=suite_summary["total_passed"],
        total_failed=suite_summary["total_failed"],
        total_failed_with_waiver=suite_summary.get("total_failed_with_waiver", 0),
        total_aborted=suite_summary["total_aborted"],
        total_skipped=suite_summary["total_skipped"],
        total_warnings=suite_summary["total_warnings"],
        test_results=test_results,
        is_summary_page=is_summary_page
    )

    with open(output_html_path, "w") as file:
        file.write(html_content)

def main(input_json_file, detailed_html_file, summary_html_file):
    with open(input_json_file, 'r') as json_file:
        data = json.load(json_file)

    suite_summary = {
        'total_passed': 0,
        'total_failed': 0,
        'total_failed_with_waiver': 0,
        'total_aborted': 0,
        'total_skipped': 0,
        'total_warnings': 0
    }

    test_results = data["test_results"]

    # Aggregate totals & detect columns for each suite
    for test_suite in test_results:
        ts_summary = test_suite.get('test_suite_summary', {})
        suite_summary['total_passed'] += get_case_insensitive(ts_summary, 'total_passed', ts_summary.get('total_passed', 0))
        suite_summary['total_failed'] += get_case_insensitive(ts_summary, 'total_failed', ts_summary.get('total_failed', 0))
        suite_summary['total_failed_with_waiver'] += get_case_insensitive(ts_summary, 'total_failed_with_waiver', ts_summary.get('total_failed_with_waiver', 0))
        suite_summary['total_aborted'] += get_case_insensitive(ts_summary, 'total_aborted', ts_summary.get('total_aborted', 0))
        suite_summary['total_skipped'] += get_case_insensitive(ts_summary, 'total_skipped', ts_summary.get('total_skipped', 0))
        suite_summary['total_warnings'] += get_case_insensitive(ts_summary, 'total_warnings', ts_summary.get('total_warnings', 0))

        # Retain column detection for minimal code changes (but we always show Waiver anyway)
        subtests = test_suite.get("subtests", [])
        test_suite["columns_used"] = detect_columns_used(subtests)

    # Generate bar chart
    chart_data = generate_bar_chart_fwts(suite_summary)

    # Generate the detailed summary page
    generate_html_fwts(suite_summary, test_results, chart_data, detailed_html_file, is_summary_page=False)

    # Generate the summary page
    generate_html_fwts(suite_summary, test_results, chart_data, summary_html_file, is_summary_page=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python fwts_generate_html.py <input_json_file> <detailed_html_file> <summary_html_file>")
        sys.exit(1)

    input_json_file = sys.argv[1]
    detailed_html_file = sys.argv[2]
    summary_html_file = sys.argv[3]

    main(input_json_file, detailed_html_file, summary_html_file)
