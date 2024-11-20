#!/usr/bin/env python3
# JSON to HTML Converter Script

import json
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from jinja2 import Template
import sys
import argparse
import os

# Function to generate bar chart for test results
def generate_bar_chart(suite_summary):
    labels = ['Passed', 'Failed', 'Skipped']
    sizes = [
        suite_summary.get('total_PASSED', 0),
        suite_summary.get('total_FAILED', 0),
        suite_summary.get('total_SKIPPED', 0)
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
def generate_html(suite_summary, test_cases_list, boot_sources_list, output_html_path, is_summary_page=True, include_drop_down=False):
    # Set the test suite name to 'Manual Tests'
    test_suite_name = 'Manual Tests'

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
                        <td class="pass">{{ total_PASSED }}</td>
                    </tr>
                    <tr>
                        <td>Failed</td>
                        <td class="fail">{{ total_FAILED }}</td>
                    </tr>
                    <tr>
                        <td>Skipped</td>
                        <td class="skipped">{{ total_SKIPPED }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
        {% if include_drop_down %}
        <div class="dropdown">
            <label for="sectionSelect">Jump to Section:</label>
            <select id="sectionSelect" onchange="jumpToSection()">
                {% for idx, boot_source in enumerate(boot_sources_list) %}
                <option value="boot_sources_{{ idx }}">Boot Sources for {{ boot_source.os_name }}</option>
                {% endfor %}
                {% for idx, test_case in enumerate(test_cases_list) %}
                <option value="test_case_{{ idx }}">{{ test_case.Test_case }}</option>
                {% endfor %}
            </select>
        </div>
        {% endif %}
        <div class="detailed-summary">
            {% for idx, boot_source in enumerate(boot_sources_list) %}
            <a id="boot_sources_{{ idx }}"></a>
            <div class="test-suite-header">Test Suite: {{ boot_source.Test_suite_name }}</div>
            <div class="test-suite-description">Description: {{ boot_source.Test_suite_description }}</div>
            
            <div class="test-case-header">Test Case: {{ boot_source.Test_case }}</div>
            <div class="test-case-description">Description: {{ boot_source.Test_case_description }}</div>
            {% endfor %}
            
            {% for idx, test_case in enumerate(test_cases_list) %}
            <a id="test_case_{{ idx }}"></a>
            <div class="test-suite-header">Test Suite: {{ test_case.Test_suite_name }}</div>
            <div class="test-suite-description">Description: {{ test_case.Test_suite_description }}</div>
            
            <div class="test-case-header">Test Case: {{ test_case.Test_case }}</div>
            <div class="test-case-description">Description: {{ test_case.Test_case_description }}</div>
            
            {% if test_case.subtests %}
            <table>
                <thead>
                    <tr>
                        <th>Sub Test Number</th>
                        <th>Sub Test Description</th>
                        <th>Sub Test Result</th>
                        <th>Pass Reasons</th>
                        <th>Fail Reasons</th>
                        <th>Skip Reasons</th>
                    </tr>
                </thead>
                <tbody>
                    {% for subtest in test_case.subtests %}
                    {% set subtest_status = get_subtest_status(subtest.sub_test_result) %}
                    <tr>
                        <td>{{ subtest.sub_Test_Number }}</td>
                        <td>{{ subtest.sub_Test_Description }}</td>
                        <td class="{% if subtest_status == 'PASSED' %}pass{% elif subtest_status == 'FAILED' %}fail{% elif subtest_status == 'SKIPPED' %}skipped{% else %}info{% endif %}">
                            {{ subtest_status }}
                        </td>
                        <td>{{ subtest.sub_test_result.pass_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.fail_reasons | join(', ') }}</td>
                        <td>{{ subtest.sub_test_result.skip_reasons | join(', ') }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
            {% endfor %}
        </div>
        {% endif %}
    </body>
    </html>
    """)

    # Calculate total tests
    total_tests = suite_summary.get('total_PASSED', 0) + suite_summary.get('total_FAILED', 0) + suite_summary.get('total_SKIPPED', 0)

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
        total_SKIPPED=suite_summary.get("total_SKIPPED", 0),
        test_cases_list=test_cases_list,
        boot_sources_list=boot_sources_list,
        is_summary_page=is_summary_page,
        include_drop_down=include_drop_down,
        chart_data=chart_data,  # Will be None if is_summary_page is True
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

    # Load JSON data
    test_cases_list = []
    boot_sources_list = []

    # Initialize counts
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_skipped = 0

    # Ensure boot_sources_paths aligns with input_json_files
    boot_sources_paths = args.boot_sources_paths if args.boot_sources_paths else []

    for idx, input_json_file in enumerate(args.input_json_files):
        with open(input_json_file, 'r') as json_file:
            try:
                data = json.load(json_file)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from file {input_json_file}: {e}")
                continue

            test_results = data.get("test_results", [])
            # Extract os_name from boot_sources_path
            if idx < len(boot_sources_paths):
                boot_sources_path = boot_sources_paths[idx]
                os_name = os.path.basename(os.path.dirname(boot_sources_path))
            else:
                boot_sources_path = "Unknown"
                os_name = "Unknown"

            # Collect Boot Sources info
            boot_sources_info = {
                "Test_suite_name": "Boot Sources",
                "Test_suite_description": "Check for boot sources",
                "Test_case": f"Boot Sources for {os_name}",
                "Test_case_description": f"Please review the boot source OS logs for {os_name} - path of {boot_sources_path}",
                "subtests": []
            }
            boot_sources_list.append(boot_sources_info)

            # Process test cases (exclude Boot Sources)
            for test in test_results:
                # Assuming Boot Sources are already appended separately and not part of test_results
                test_case = {
                    "Test_suite_name": test.get("Test_suite_name", "Unknown Suite"),
                    "Test_suite_description": test.get("Test_suite_description", "No Description"),
                    "Test_case": test.get("Test_case", "Unknown Test Case"),
                    "Test_case_description": test.get("Test_case_description", "No Description"),
                    "subtests": test.get("subtests", [])
                }

                # Determine test case status based on subtests
                test_status = 'PASSED'
                has_skipped = False

                if test_case['subtests']:
                    for subtest in test_case['subtests']:
                        subtest_status = get_subtest_status(subtest.get('sub_test_result', {}))
                        if subtest_status == 'FAILED':
                            test_status = 'FAILED'
                            break
                        elif subtest_status == 'SKIPPED':
                            has_skipped = True
                        elif subtest_status != 'PASSED':
                            # Treat any other status as failure
                            test_status = 'FAILED'
                            break
                    else:
                        # No failures in subtests
                        if has_skipped and test_status != 'FAILED':
                            test_status = 'SKIPPED'
                else:
                    # No subtests; treat as SKIPPED
                    test_status = 'SKIPPED'

                # Update counts based on test_status
                if test_status == 'PASSED':
                    total_passed += 1
                elif test_status == 'FAILED':
                    total_failed += 1
                elif test_status == 'SKIPPED':
                    total_skipped += 1
                else:
                    # Treat any other status as skipped
                    total_skipped += 1

                test_cases_list.append(test_case)

    # Now, create the suite_summary dictionary
    suite_summary = {
        'total_PASSED': total_passed,
        'total_FAILED': total_failed,
        'total_SKIPPED': total_skipped,
    }

    total_tests = suite_summary['total_PASSED'] + suite_summary['total_FAILED'] + suite_summary['total_SKIPPED']

    if total_tests == 0:
        print("No valid JSON data found in input files.")
        sys.exit(1)

    # Generate the detailed summary page
    generate_html(
        suite_summary,
        test_cases_list,
        boot_sources_list,
        args.detailed_html_file,
        is_summary_page=False,
        include_drop_down=args.include_drop_down
    )

    # Generate the summary page (with bar graph)
    generate_html(
        suite_summary,
        test_cases_list,
        boot_sources_list,
        args.summary_html_file,
        is_summary_page=True
    )

if __name__ == "__main__":
    main()
