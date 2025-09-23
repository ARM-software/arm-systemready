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

# 1) Detect which columns are used among all subtests in a given test
def detect_columns_used(subtests):
    """
    We keep this function for minimal code changes, 
    but the only value effectively used now is show_waiver.
    """
    show_pass = False
    show_fail = False
    show_abort = False
    show_skip = False
    show_warning = False
    show_waiver = False

    for subtest in subtests:
        r = subtest.get('sub_test_result', {})
        if r.get('pass_reasons'):
            show_pass = True
        if r.get('fail_reasons'):
            show_fail = True
        if r.get('abort_reasons'):
            show_abort = True
        if r.get('skip_reasons'):
            show_skip = True
        if r.get('warning_reasons'):
            show_warning = True
        # If any subtest has "FAILED_WITH_WAIVER", we show the Waiver column
        if r.get('FAILED_WITH_WAIVER', 0) > 0:
            show_waiver = True

    return {
        'show_pass': show_pass,
        'show_fail': show_fail,
        'show_abort': show_abort,
        'show_skip': show_skip,
        'show_warning': show_warning,
        'show_waiver': show_waiver
    }


# Function to generate bar chart for test results
def generate_bar_chart(suite_summary):
    labels = ['Passed', 'Failed', 'Failed with Waiver']  # We track "Failed with Waiver" separately
    sizes = [
        suite_summary.get('total_passed', 0),
        suite_summary.get('total_failed', 0),
        suite_summary.get('total_failed_with_waiver', 0)
    ]
    colors = ['#66bb6a', '#ef5350', '#f39c12']

    plt.figure(figsize=(8, 6))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    total_tests = sum(sizes)
    for bar, size in zip(bars, sizes):
        yval = bar.get_height()
        if total_tests > 0:
            percentage = (size / total_tests) * 100
            label = f'{percentage:.2f}%'
        else:
            label = '0%'
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            yval + (max(sizes)*0.02 if total_tests > 0 else 0.1),
            label,
            ha='center',
            va='bottom',
            fontsize=12
        )

    plt.title('Standalone test Results', fontsize=16, fontweight='bold', pad=20)
    plt.ylabel('Number of Standalone tests', fontsize=14)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def generate_html(suite_summary, test_results_list, output_html_path,
                  is_summary_page=True, include_drop_down=False):
    test_suite_name = 'Standalone'

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
        .waiver {
            background-color: #f39c12; 
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
        <img src="data:image/png;base64,{{ chart_data }}" alt="Standalone tests Results">
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
                    <td>Total Standalone tests</td>
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
                    <td class="waiver">{{ total_failed_with_waiver }}</td>
                </tr>
            </tbody>
        </table>
    </div>

    {% if not is_summary_page %}
    {% if include_drop_down %}
    <div class="dropdown">
        <label for="sectionSelect">Jump to Standalone tests:</label>
        <select id="sectionSelect" onchange="jumpToSection()">
            {% for idx, test_results in enumerate(test_results_list) %}
            {% if test_results and test_results[0] %}
            {% set test = test_results[0] %}
            <option value="section{{ idx }}">{{ test.Test_suite }} - {{ test.Test_case }}</option>
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

        <div class="test-suite-header">Test Suite: {{ test.Test_suite }}</div>
        <div class="test-suite-description">Description: {{ test.Test_suite_description }}</div>

        <div class="test-case-header">Test Case: {{ test.Test_case }}</div>
        <div class="test-case-description">Description: {{ test.Test_case_description }}</div>

        {# We ignore dynamic reason columns and use a single "Reason" + "Waiver Reason" #}
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
                {% set r = subtest.sub_test_result %}
                {% set status = (
                    'PASSED' if r.PASSED > 0 else
                    'FAILED_WITH_WAIVER' if r.FAILED_WITH_WAIVER > 0 else
                    'FAILED' if r.FAILED > 0 else
                    'ABORTED' if r.ABORTED > 0 else
                    'SKIPPED' if r.SKIPPED > 0 else
                    'WARNINGS' if r.WARNINGS > 0 else
                    'UNKNOWN'
                ) %}
                <tr>
                    <td>{{ subtest.sub_Test_Number }}</td>
                    <td>{{ subtest.sub_Test_Description }}</td>
                    <td class="{% if status == 'PASSED' %}pass{% elif status == 'FAILED' %}fail{% elif status == 'FAILED_WITH_WAIVER' %}waiver{% endif %}">
                        {% if status == 'FAILED_WITH_WAIVER' %}
                            FAILED WITH WAIVER
                        {% else %}
                            {{ status }}
                        {% endif %}
                    </td>
                    {# Combine pass, fail, skip, abort, warning reasons into one "Reason" column #}
                    {% set all_reasons = [] %}
                    {% for reasons in [r.pass_reasons, r.fail_reasons, r.abort_reasons, r.skip_reasons, r.warning_reasons] if reasons %}
                        {% for reason in reasons %}
                            {% if reason is iterable and reason is not string %}
                                {% for subreason in reason %}
                                    {% set _ = all_reasons.append(subreason) %}
                                {% endfor %}
                            {% else %}
                                {% set _ = all_reasons.append(reason) %}
                            {% endif %}
                        {% endfor %}
                    {% endfor %}
                    <td>
                        {{ all_reasons|join("<br>")|safe if all_reasons else "N/A" }}
                    </td>
                    <td>
                        {{ r.waiver_reason if r.waiver_reason else "N/A" }}
                    </td>
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

    # Compute total tests for summary
    total_tests = (suite_summary.get('total_passed', 0) +
                   suite_summary.get('total_failed', 0) +
                   suite_summary.get('total_failed_with_waiver', 0))

    # If not summary page, generate chart
    if not is_summary_page:
        chart_data = generate_bar_chart(suite_summary)
    else:
        chart_data = None

    html_content = template.render(
        test_suite_name=test_suite_name,
        total_tests=total_tests,
        total_passed=suite_summary.get("total_passed", 0),
        total_failed=suite_summary.get("total_failed", 0),
        total_failed_with_waiver=suite_summary.get("total_failed_with_waiver", 0),
        test_results_list=test_results_list,
        is_summary_page=is_summary_page,
        include_drop_down=include_drop_down,
        chart_data=chart_data,
        enumerate=enumerate
    )

    with open(output_html_path, "w") as f:
        f.write(html_content)


def get_subtest_status(subtest_result):
    if subtest_result.get('PASSED', 0) > 0:
        return 'PASSED'
    elif subtest_result.get('FAILED_WITH_WAIVER', 0) > 0:
        return 'FAILED_WITH_WAIVER'
    elif subtest_result.get('FAILED', 0) > 0:
        return 'FAILED'
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
    parser.add_argument('--include-drop-down', action='store_true',
                        help='Include drop-down menu in detailed summary')
    args = parser.parse_args()

    test_results_list = []
    combined_suite_summary = {
        'total_passed': 0,
        'total_failed': 0,
        'total_failed_with_waiver': 0
    }

    for input_json_file in args.input_json_files:
        try:
            with open(input_json_file, 'r') as jf:
                data = json.load(jf)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading {input_json_file}: {e}")
            continue

        test_results = data.get("test_results", [])
        if test_results:
            # 2) For each test in test_results, compute columns_used
            for test in test_results:
                subtests = test.get("subtests", [])
                test["columns_used"] = detect_columns_used(subtests)

            test_results_list.append(test_results)

            # Determine overall pass/fail
            for test in test_results:
                has_failed_without_waiver = False
                has_failed_with_waiver = False

                for subtest in test.get('subtests', []):
                    st_status = get_subtest_status(subtest.get('sub_test_result', {}))
                    if st_status == 'FAILED':
                        has_failed_without_waiver = True
                    elif st_status == 'FAILED_WITH_WAIVER':
                        has_failed_with_waiver = True

                if has_failed_without_waiver:
                    combined_suite_summary['total_failed'] += 1
                elif has_failed_with_waiver:
                    combined_suite_summary['total_failed_with_waiver'] += 1
                else:
                    combined_suite_summary['total_passed'] += 1

    total_standalones = (combined_suite_summary['total_passed'] +
                         combined_suite_summary['total_failed'] +
                         combined_suite_summary['total_failed_with_waiver'])
    if total_standalones == 0:
        print("No valid data found in input JSON(s).")
        sys.exit(1)

    # Generate detailed summary
    generate_html(
        combined_suite_summary,
        test_results_list,
        args.detailed_html_file,
        is_summary_page=False,
        include_drop_down=args.include_drop_down
    )

    # Generate summary page
    generate_html(
        combined_suite_summary,
        test_results_list,
        args.summary_html_file,
        is_summary_page=True
    )

if __name__ == "__main__":
    main()
