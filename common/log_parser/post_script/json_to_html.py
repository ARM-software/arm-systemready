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
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from jinja2 import Template
import sys

# Helper function for case-insensitive dictionary get
def get_case_insensitive(d, key, default=0):
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default

def generate_bar_chart(suite_summary):
    """
    Generate a bar chart:
    """
    labels = ['Passed', 'Failed', 'Failed with Waiver', 'Aborted', 'Skipped', 'Warnings']
    sizes = [
        suite_summary.get('total_passed', 0),
        suite_summary.get('total_failed', 0),
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_aborted', 0),
        suite_summary.get('total_skipped', 0),
        suite_summary.get('total_warnings', 0)
    ]
    # Same color array as FWTS
    colors = ['#66bb6a', '#ef5350', '#f39c12', '#9e9e9e', '#ffc107', '#ffeb3b']

    plt.figure(figsize=(12, 7))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    total_tests = sum(sizes)
    max_size = max(sizes) if sizes else 0
    for bar, size in zip(bars, sizes):
        height = bar.get_height()
        pct = (size / total_tests) * 100 if total_tests else 0
        # Place the % label slightly above each bar
        plt.text(
            bar.get_x() + bar.get_width()/2,
            height + (0.01 * max_size if max_size else 0.05),
            f'{pct:.2f}%',
            ha='center',
            va='bottom',
            fontsize=12
        )

    plt.title('Post-Script Test Results Distribution', fontsize=18, fontweight='bold')
    plt.ylabel('Total Count', fontsize=14)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.tight_layout()

    # Convert plot to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def generate_html(suite_summary, test_results, chart_data, output_html_path, is_summary_page=False):
    template = Template(r"""
<!DOCTYPE html>
<html>
<head>
    <title>Post-Script Test {{ "Summary" if is_summary_page else "Detailed Results" }}</title>
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

        /* Matching FWTS color classes */
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

        .summary-container, .detailed-container {
            margin-top: 40px;
            padding: 20px;
            background-color: #fff;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .summary-container h2 {
            border-bottom: 2px solid #27ae60;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .summary-table {
            margin: 0 auto;
            width: 50%;
        }
        .chart-container {
            display: flex;
            justify-content: center;
        }
    </style>
</head>
<body>
    <h1>Post-Script Log {{ "Summary" if is_summary_page else "Detailed Results" }}</h1>

    {% if not is_summary_page %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ chart_data }}" alt="Test Results Distribution">
    </div>
    {% endif %}

    <div class="summary-container">
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
                    <td>{{ total_tests }}</td>
                </tr>
                <tr>
                    <td>Passed</td>
                    <td class="pass">{{ suite_summary.total_passed }}</td>
                </tr>
                <tr>
                    <td>Failed</td>
                    <td class="fail">{{ suite_summary.total_failed }}</td>
                </tr>
                <tr>
                    <td>Failed with Waiver</td>
                    <td class="fail-waiver">{{ suite_summary.total_failed_with_waiver }}</td>
                </tr>
                <tr>
                    <td>Aborted</td>
                    <td class="aborted">{{ suite_summary.total_aborted }}</td>
                </tr>
                <tr>
                    <td>Skipped</td>
                    <td class="skipped">{{ suite_summary.total_skipped }}</td>
                </tr>
                <tr>
                    <td>Warnings</td>
                    <td class="warning">{{ suite_summary.total_warnings }}</td>
                </tr>
            </tbody>
        </table>
    </div>

    {% if not is_summary_page %}
    <div class="detailed-container">
        <h2>Detailed Subtests</h2>
        {% for suite in test_results %}
        <h3>{{ suite.Test_suite }}: {{ suite.Test_suite_description }}</h3>
        <table>
            <thead>
                <tr>
                    <th>Sub Test Number</th>
                    <th>Sub Test Description</th>
                    <th>Result</th>
                    <th>Reasons</th>
                    <th>Waiver Reason</th>
                </tr>
            </thead>
            <tbody>
            {% for st in suite.subtests %}
                {% set r = st.sub_test_result %}
                <tr>
                    <td>{{ st.sub_Test_Number }}</td>
                    <td>{{ st.sub_Test_Description }}</td>

                    {# Determine the correct CSS class based on result #}
                    {% set result_class = "" %}
                    {% if r.PASSED > 0 %}
                        {% set result_class = "pass" %}
                    {% elif r.FAILED > 0 %}
                        {% set result_class = "fail" %}
                    {% elif r.FAILED_WITH_WAIVER is defined and r.FAILED_WITH_WAIVER > 0 %}
                        {% set result_class = "fail-waiver" %}
                    {% elif r.ABORTED > 0 %}
                        {% set result_class = "aborted" %}
                    {% elif r.SKIPPED > 0 %}
                        {% set result_class = "skipped" %}
                    {% elif r.WARNINGS > 0 %}
                        {% set result_class = "warning" %}
                    {% else %}
                        {% set result_class = "" %}
                    {% endif %}

                    <td class="{{ result_class }}">
                        {% if r.PASSED > 0 %}
                            PASSED
                        {% elif r.FAILED > 0 %}
                            FAILED
                        {% elif r.FAILED_WITH_WAIVER is defined and r.FAILED_WITH_WAIVER > 0 %}
                            FAILED WITH WAIVER
                        {% elif r.ABORTED > 0 %}
                            ABORTED
                        {% elif r.SKIPPED > 0 %}
                            SKIPPED
                        {% elif r.WARNINGS > 0 %}
                            WARNING
                        {% else %}
                            UNKNOWN
                        {% endif %}
                    </td>

                    {# Collect all reason lists #}
                    {% set all_reasons = [] %}
                    {% if r.pass_reasons is defined %}
                        {% for reason in r.pass_reasons %}
                            {% set _ = all_reasons.append(reason) %}
                        {% endfor %}
                    {% endif %}
                    {% if r.fail_reasons is defined %}
                        {% for reason in r.fail_reasons %}
                            {% set _ = all_reasons.append(reason) %}
                        {% endfor %}
                    {% endif %}
                    {% if r.abort_reasons is defined %}
                        {% for reason in r.abort_reasons %}
                            {% set _ = all_reasons.append(reason) %}
                        {% endfor %}
                    {% endif %}
                    {% if r.skip_reasons is defined %}
                        {% for reason in r.skip_reasons %}
                            {% set _ = all_reasons.append(reason) %}
                        {% endfor %}
                    {% endif %}
                    {% if r.warning_reasons is defined %}
                        {% for reason in r.warning_reasons %}
                            {% set _ = all_reasons.append(reason) %}
                        {% endfor %}
                    {% endif %}

                    <td>{{ all_reasons|join("; ") if all_reasons else "N/A" }}</td>

                    {% if r.FAILED_WITH_WAIVER is defined and r.FAILED_WITH_WAIVER > 0 and r.waiver_reason is defined %}
                        <td>{{ r.waiver_reason }}</td>
                    {% else %}
                        <td>N/A</td>
                    {% endif %}
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
        + suite_summary.get("total_failed_with_waiver", 0)
        + suite_summary["total_aborted"]
        + suite_summary["total_skipped"]
        + suite_summary["total_warnings"]
    )

    html_content = template.render(
        is_summary_page=is_summary_page,
        suite_summary=suite_summary,
        total_tests=total_tests,
        test_results=test_results,
        chart_data=chart_data
    )

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <input_json> <detailed_html> <summary_html>")
        sys.exit(1)

    input_json_file = sys.argv[1]
    detailed_html_file = sys.argv[2]
    summary_html_file = sys.argv[3]

    with open(input_json_file, 'r', encoding='utf-8') as jf:
        data = json.load(jf)

    # suite_summary we can take directly from top-level "suite_summary"
    suite_summary = data.get("suite_summary", {
        "total_passed": 0,
        "total_failed": 0,
        "total_failed_with_waiver": 0,
        "total_aborted": 0,
        "total_skipped": 0,
        "total_warnings": 0
    })
    test_results = data.get("test_results", [])

    # Generate bar chart (now uses the same style/size/colors as FWTS)
    chart_data = generate_bar_chart(suite_summary)

    # Create the Detailed page
    generate_html(suite_summary, test_results, chart_data, detailed_html_file, is_summary_page=False)

    # Create the Summary page
    generate_html(suite_summary, test_results, chart_data, summary_html_file, is_summary_page=True)

if __name__ == "__main__":
    main()
