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
import argparse
import os
import subprocess
import re
from jinja2 import Template
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def get_system_info():
    system_info = {}

    # Get Firmware Version
    try:
        fw_version_output = subprocess.check_output(
            ["dmidecode", "-t", "bios"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in fw_version_output.split('\n'):
            if 'Version:' in line:
                system_info['Firmware Version'] = line.split('Version:')[1].strip()
                break
    except Exception:
        system_info['Firmware Version'] = 'Unknown'

    # SoC Family
    try:
        soc_family_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL
        )
        # Iterate each line looking for "Family:"
        for line in soc_family_output.split('\n'):
            if 'Family:' in line:
                system_info['SoC Family'] = line.split('Family:', 1)[1].strip()
                break
        else:
            # #If we didn't find 'Family:'
            system_info['SoC Family'] = 'Unknown'
    except Exception:
        system_info['SoC Family'] = 'Unknown'

    # Get System Name
    try:
        system_name_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in system_name_output.split('\n'):
            if 'Product Name:' in line:
                system_info['System Name'] = line.split('Product Name:')[1].strip()
                break
        else:
            # If we didn't find 'Product Name:'
            system_info['System Name'] = 'Unknown'    
    except Exception:
        system_info['System Name'] = 'Unknown'

    # Get Vendor
    try:
        vendor_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in vendor_output.split('\n'):
            if 'Manufacturer:' in line:
                system_info['Vendor'] = line.split('Manufacturer:')[1].strip()
                break
    except Exception:
        system_info['Vendor'] = 'Unknown'

    # Add date when the summary was generated
    try:
        system_info['Summary Generated On Date/time'] = subprocess.check_output(
            ["date", "+%Y-%m-%d %H:%M:%S"], universal_newlines=True).strip()
    except Exception:
        system_info['Summary Generated On Date/time'] = 'Unknown'

    return system_info

def parse_config(config_path):
    config_info = {}
    try:
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as config_file:
                for line in config_file:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        config_info[key.strip()] = value.strip()
        else:
            print(f"Config file {config_path} not provided or does not exist.")
    except Exception as e:
        print(f"Error reading {config_path}: {e}")
    return config_info

def get_uefi_version(uefi_version_log):
    uefi_version = 'Unknown'
    try:
        if uefi_version_log and os.path.exists(uefi_version_log):
            with open(uefi_version_log, 'r', encoding='utf-16') as file:
                for line in file:
                    if 'UEFI v' in line:
                        uefi_version = line.strip()
                        break
        else:
            uefi_version = 'Not provided'
    except Exception as e:
        print(f"Error reading UEFI version log: {e}")
    return uefi_version

def remove_result_summary_headings(content):
    # Use regular expressions to remove any heading containing 'Result Summary'
    pattern = r'<h[1-6][^>]*>\s*Result Summary\s*</h[1-6]>'
    content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    return content

def read_html_content(file_path):
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
            # Remove 'Result Summary' headings
            content = remove_result_summary_headings(content)
            return content
    else:
        return None

def adjust_bbsr_headings(content, suite_name):
    if content:
        pattern = r'(<h[1-6][^>]*>)(.*? Test Summary)(</h[1-6]>)'
        replacement = r'\1' + suite_name + r' Test Summary\3'
        content = re.sub(pattern, replacement, content, count=1, flags=re.IGNORECASE)
    return content

def adjust_detailed_summary_heading(file_path, suite_name):
    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        content = adjust_bbsr_headings(content, suite_name)
        with open(file_path, 'w') as file:
            file.write(content)

def read_overall_compliance_from_merged_json(merged_json_path):
    """
    Opens the merged_results.json and retrieves the final
    "Overall Compliance Result" from:
      data["Suite_Name: acs_info"]["ACS Results Summary"]["Overall Compliance Result"]
    """
    overall_result = "Unknown"
    try:
        with open(merged_json_path, 'r') as jf:
            data = json.load(jf)
        acs_info_data = data.get("Suite_Name: acs_info", {})
        acs_summary = acs_info_data.get("ACS Results Summary", {})
        overall_result = acs_summary.get("Overall Compliance Result", "Unknown")
    except Exception as e:
        print(f"Warning: Could not read merged JSON or find 'Overall Compliance Result': {e}")
    return overall_result

##############################################################################
# VIEW PAGE
##############################################################################

def get_case_insensitive(d, key, default=0):
    """Helper to retrieve dictionary values ignoring case."""
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default

def generate_bar_chart(suite_summary):
    """Generate a bar chart (base64-encoded PNG) for the pass/fail distribution."""
    labels = [
        'Passed',
        'Failed',
        'Failed with Waiver',
        'Aborted',
        'Skipped',
        'Warnings'
    ]
    sizes = [
        suite_summary.get('total_PASSED', 0),
        suite_summary.get('total_FAILED', 0),
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_ABORTED', 0),
        suite_summary.get('total_SKIPPED', 0),
        suite_summary.get('total_WARNINGS', 0)
    ]
    colors = ['#66bb6a','#ef5350','#f39c12','#9e9e9e','#ffc107','#ffeb3b']

    plt.figure(figsize=(10, 6))
    plt.gcf().subplots_adjust(top=0.90, bottom=0.30)

    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')
    total_tests = sum(sizes)

    # Add percentage labels on top of each bar
    for bar, size in zip(bars, sizes):
        height = bar.get_height()
        pct = (size / total_tests)*100 if total_tests else 0
        plt.text(
            bar.get_x() + bar.get_width()/2,
            height + 0.3,
            f"{pct:.1f}%",
            ha='center'
        )

    plt.title('Test Results Distribution')
    plt.ylabel('Count')
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def generate_view_html_page(view_name, test_items, output_html_path):

    # Check if sub_test_suite or test_case exist anywhere (unchanged logic)
    sub_test_suite_exists = False
    test_case_exists = False
    for titem in test_items:
        if "Sub_test_suite" in titem and titem["Sub_test_suite"]:
            sub_test_suite_exists = True
        if "Test_case" in titem and titem["Test_case"]:
            test_case_exists = True

        subtests = titem.get("subtests", [])
        for s in subtests:
            if "Sub_test_suite" in s and s["Sub_test_suite"]:
                sub_test_suite_exists = True
            if "Test_case" in s and s["Test_case"]:
                test_case_exists = True

    # We collect results in a dictionary keyed by (Parent_Suite_Name, Test_suite)
    suite_to_counts = {}

    for titem in test_items:
        parent_suite = titem.get("Parent_Suite_Name", "UnknownParent")
        child_suite  = titem.get("Test_suite",       "UnknownChild")
        suite_key = (parent_suite, child_suite)

        if suite_key not in suite_to_counts:
            suite_to_counts[suite_key] = {
                'total_PASSED': 0,
                'total_FAILED': 0,
                'total_failed_with_waiver': 0,
                'total_ABORTED': 0,
                'total_SKIPPED': 0,
                'total_WARNINGS': 0
            }

        subtests = titem.get("subtests", [])
        for sub in subtests:
            result_text = "UNKNOWN"
            res_dict = sub.get("sub_test_result")

            if isinstance(res_dict, dict):
                passed   = res_dict.get('PASSED', 0)
                failed   = res_dict.get('FAILED', 0)
                aborted  = res_dict.get('ABORTED', 0)
                skipped  = res_dict.get('SKIPPED', 0)
                warnings = res_dict.get('WARNINGS', 0)

                if failed > 0:
                    if sub.get("waiver_reason"):
                        result_text = "FAILED (WITH WAIVER)"
                    else:
                        result_text = "FAILED"
                elif passed > 0:
                    result_text = "PASSED"
                elif aborted > 0:
                    result_text = "ABORTED"
                elif skipped > 0:
                    result_text = "SKIPPED"
                elif warnings > 0:
                    result_text = "WARNING"
            elif isinstance(res_dict, str):
                result_text = res_dict.upper()

            # HERE is where we do the snippet to handle "fail"/"waiver"/"abort" etc:
            result_lower = (result_text or "").lower()

            if "fail" in result_lower:
                if "waiver" in result_lower:
                    suite_to_counts[suite_key]['total_failed_with_waiver'] += 1
                else:
                    suite_to_counts[suite_key]['total_FAILED'] += 1
            elif "pass" in result_lower:
                suite_to_counts[suite_key]['total_PASSED'] += 1
            elif "abort" in result_lower:
                suite_to_counts[suite_key]['total_ABORTED'] += 1
            elif "skip" in result_lower:
                suite_to_counts[suite_key]['total_SKIPPED'] += 1
            elif "warn" in result_lower:
                suite_to_counts[suite_key]['total_WARNINGS'] += 1

        #iterate over every subtest and count its result
    suite_summary = {
        'total_PASSED': 0,
        'total_FAILED': 0,
        'total_failed_with_waiver': 0,
        'total_ABORTED': 0,
        'total_SKIPPED': 0,
        'total_WARNINGS': 0
    }

    for item in test_items:
        subtests = item.get("subtests", [])
        for sub in subtests:
            result_text = ""
            res_dict = sub.get("sub_test_result")
            if isinstance(res_dict, dict):
                # We determine result_text from the dictionary values
                if res_dict.get('FAILED_WITH_WAIVER', 0) > 0:
                    result_text = "failed (with waiver)"
                if res_dict.get('FAILED', 0) > 0:
                    result_text = "failed"
                elif res_dict.get('PASSED', 0) > 0:
                    result_text = "passed"
                elif res_dict.get('ABORTED', 0) > 0:
                    result_text = "aborted"
                elif res_dict.get('SKIPPED', 0) > 0:
                    result_text = "skipped"
                elif res_dict.get('WARNINGS', 0) > 0:
                    result_text = "warning"
            elif isinstance(res_dict, str):
                result_text = res_dict.lower()

            # any "fail" counts as failed; if "waiver" is present, count both.
            result_text = (result_text or "").lower()
            if "fail" in result_text:
                suite_summary['total_FAILED'] += 1
                if "waiver" in result_text:
                    suite_summary['total_failed_with_waiver'] += 1
            elif "pass" in result_text:
                suite_summary['total_PASSED'] += 1
            elif "abort" in result_text:
                suite_summary['total_ABORTED'] += 1
            elif "skip" in result_text:
                suite_summary['total_SKIPPED'] += 1
            elif "warn" in result_text:
                suite_summary['total_WARNINGS'] += 1
            # else, do nothing for unknown


    chart_data = generate_bar_chart(suite_summary)

    html_template = Template(r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ view_name }} View</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f4;
        }
        h1, h2 {
            color: #2c3e50;
            text-align: center;
        }
        .chart-container {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px auto;
            background-color: #fff;
        }
        th, td {
            padding: 12px;
            border: 1px solid #ddd;
            font-size: 14px;
            text-align: center; /* center text by default */
        }
        th {
            background-color: #3498db;
            color: white;
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
            width: 70%;
        }
        .summary-table td {
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>{{ view_name }} View</h1>
    <div class="chart-container">
        <img src="data:image/png;base64,{{ chart_data }}" alt="Bar Chart">
    </div>
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
                <td>{{ suite_summary.total_PASSED + suite_summary.total_FAILED
                       + suite_summary.total_failed_with_waiver + suite_summary.total_ABORTED
                       + suite_summary.total_SKIPPED + suite_summary.total_WARNINGS }}</td>
            </tr>
            <tr>
                <td>Passed</td>
                <td class="pass">{{ suite_summary.total_PASSED }}</td>
            </tr>
            <tr>
                <td>Failed</td>
                <td class="fail">{{ suite_summary.total_FAILED }}</td>
            </tr>
            <tr>
                <td>Failed with Waiver</td>
                <td class="fail-waiver">{{ suite_summary.total_failed_with_waiver }}</td>
            </tr>
            <tr>
                <td>Aborted</td>
                <td class="aborted">{{ suite_summary.total_ABORTED }}</td>
            </tr>
            <tr>
                <td>Skipped</td>
                <td class="skipped">{{ suite_summary.total_SKIPPED }}</td>
            </tr>
            <tr>
                <td>Warnings</td>
                <td class="warning">{{ suite_summary.total_WARNINGS }}</td>
            </tr>
        </tbody>
    </table>

    <h2>Detailed Results</h2>
    {% for test in test_items %}
    <table>
        <thead>
            <tr>
                <th colspan="100">Suite: {{ test.Parent_Suite_Name }} ({{ test.Test_suite }})</th>
            </tr>
            <tr>
                <th>Sub Test #</th>
                <th>Sub Test Description</th>
                <th>Result</th>

                {% if sub_test_suite_exists %}
                <th>Sub Test Suite</th>
                {% endif %}

                {% if test_case_exists %}
                <th>Test Case</th>
                {% endif %}

                <th>Reason</th>
                <th>Waiver Reason</th>
            </tr>
        </thead>
        <tbody>
            {% for sub in test.subtests %}
            {% set result_text = "" %}
            {% if sub.sub_test_result is string %}
                {% set result_text = sub.sub_test_result %}
            {% elif sub.sub_test_result is mapping %}
                {% set passed = sub.sub_test_result.get('PASSED', 0) %}
                {% set failed = sub.sub_test_result.get('FAILED', 0) %}
                {% set failed_with_waiver = sub.sub_test_result.get('FAILED_WITH_WAIVER', 0) %}
                {% set aborted = sub.sub_test_result.get('ABORTED', 0) %}
                {% set skipped = sub.sub_test_result.get('SKIPPED', 0) %}
                {% set warnings = sub.sub_test_result.get('WARNINGS', 0) %}

                {% if failed_with_waiver > 0 %}
                    {% set result_text = "FAILED (WITH WAIVER)" %}
                {% elif failed > 0 %}
                    {% set result_text = "FAILED" %}
                {% elif passed > 0 %}
                    {% set result_text = "PASSED" %}
                {% elif aborted > 0 %}
                    {% set result_text = "ABORTED" %}
                {% elif skipped > 0 %}
                    {% set result_text = "SKIPPED" %}
                {% elif warnings > 0 %}
                    {% set result_text = "WARNING" %}
                {% else %}
                    {% set result_text = "UNKNOWN" %}
                {% endif %}
            {% else %}
                {% set result_text = "UNKNOWN" %}
            {% endif %}


            {% set result_class = "" %}
            {% set upper_txt = result_text.upper() %}
            {% if "FAILED" in upper_txt and "WAIVER" in upper_txt %}
                {% set result_class = "fail-waiver" %}
            {% elif "FAIL" in upper_txt %}
                {% set result_class = "fail" %}
            {% elif "PASS" in upper_txt %}
                {% set result_class = "pass" %}
            {% elif "ABORT" in upper_txt %}
                {% set result_class = "aborted" %}
            {% elif "SKIP" in upper_txt %}
                {% set result_class = "skipped" %}
            {% elif "WARN" in upper_txt %}
                {% set result_class = "warning" %}
            {% endif %}

            <tr>
                <td>{{ sub.sub_Test_Number }}</td>
                <td>{{ sub.sub_Test_Description }}</td>
                <td class="{{ result_class }}">{{ result_text }}</td>

                {% if sub_test_suite_exists %}
                <td>{{ sub.Sub_test_suite if sub.Sub_test_suite else "N/A" }}</td>
                {% endif %}

                {% if test_case_exists %}
                <td>{{ sub.Test_case if sub.Test_case else "N/A" }}</td>
                {% endif %}

                <td>
                    {# Check top-level sub.reason if present #}
                    {% if sub.reason is defined and sub.reason %}
                        {{ sub.reason }}

                    {# Otherwise, check sub_test_result for pass_reasons #}
                    {% elif sub.sub_test_result is defined 
                        and sub.sub_test_result.pass_reasons is defined
                        and sub.sub_test_result.pass_reasons %}
                        {{ sub.sub_test_result.pass_reasons | join('<br>') | safe }}

                    {# Then check skip_reasons, if any #}
                    {% elif sub.sub_test_result is defined
                        and sub.sub_test_result.skip_reasons is defined
                        and sub.sub_test_result.skip_reasons %}
                        {{ sub.sub_test_result.skip_reasons | join('<br>') | safe }}

                    {# Then fail_reasons #}
                    {% elif sub.sub_test_result is defined
                        and sub.sub_test_result.fail_reasons is defined
                        and sub.sub_test_result.fail_reasons %}
                        {{ sub.sub_test_result.fail_reasons | join('<br>') | safe }}

                    {# Then fallback to any old "RULES FAILED"/"RULES SKIPPED" logic #}
                    {% elif 'RULES FAILED' in sub %}
                        {{ sub['RULES FAILED'] }}
                    {% elif 'RULES SKIPPED' in sub %}
                        {{ sub['RULES SKIPPED'] }}

                    {# Finally, if nothing is found, display "N/A" #}
                    {% else %}
                        N/A
                    {% endif %}
                </td>

                <td>
                    {% if 'WAIVER' in upper_txt and sub.waiver_reason %}
                        {{ sub.waiver_reason }}
                    {% else %}
                        N/A
                    {% endif %}
                </td>

            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endfor %}
</body>
</html>
""")

    rendered_html = html_template.render(
        view_name=view_name,
        test_items=test_items,
        suite_summary=suite_summary,
        chart_data=chart_data,
        sub_test_suite_exists=sub_test_suite_exists,
        test_case_exists=test_case_exists
    )

    with open(output_html_path, 'w') as f:
        f.write(rendered_html)

def generate_multi_view_pages(merged_json_path, summary_output_dir):

    if not os.path.isfile(merged_json_path):
        print(f"No merged_results.json found at: {merged_json_path}")
        return []

    with open(merged_json_path, 'r') as jf:
        merged_data = json.load(jf)

    grouping_dict = {}
    for key, val in merged_data.items():
        if not key.startswith("Suite_Name:"):
            continue

        parent_suite_name = key.replace("Suite_Name:", "").strip()

        if not isinstance(val, list):
            continue
        for test_dict in val:
            if not isinstance(test_dict, dict):
                continue

            test_dict["Parent_Suite_Name"] = parent_suite_name

            readiness = test_dict.get("Main Readiness Grouping", "").strip()
            if not readiness:
                readiness = "UNKNOWN_GROUPING"
            grouping_dict.setdefault(readiness, []).append(test_dict)

    view_links = []
    for grouping_name, test_items in grouping_dict.items():
        safe_name = re.sub(r"\s+", "_", grouping_name.lower())
        view_filename = f"{safe_name}_view.html"
        view_path = os.path.join(summary_output_dir, view_filename)
        generate_view_html_page(grouping_name, test_items, view_path)

        view_links.append({
            "name": grouping_name,
            "href": view_filename
        })

    return view_links

def generate_html(system_info, acs_results_summary,
                  bsa_summary_path, sbsa_summary_path, fwts_summary_path, sct_summary_path,
                  bbsr_fwts_summary_path, bbsr_sct_summary_path,bbsr_tpm_summary_path,
                  post_script_summary_path,
                  standalone_summary_path, OS_tests_summary_path,
                  output_html_path):

    # Read the summary HTML content from each suite
    bsa_summary_content = read_html_content(bsa_summary_path)
    sbsa_summary_content = read_html_content(sbsa_summary_path)
    fwts_summary_content = read_html_content(fwts_summary_path)
    sct_summary_content = read_html_content(sct_summary_path)
    bbsr_fwts_summary_content = read_html_content(bbsr_fwts_summary_path)
    bbsr_sct_summary_content = read_html_content(bbsr_sct_summary_path)
    bbsr_tpm_summary_content = read_html_content(bbsr_tpm_summary_path) 
    post_script_summary_content = read_html_content(post_script_summary_path)
    standalone_summary_content = read_html_content(standalone_summary_path)
    OS_tests_summary_content = read_html_content(OS_tests_summary_path)

    # Adjust headings in BBSR/Standalone/OS summaries
    bbsr_fwts_summary_content = adjust_bbsr_headings(bbsr_fwts_summary_content, 'BBSR-FWTS')
    bbsr_sct_summary_content = adjust_bbsr_headings(bbsr_sct_summary_content, 'BBSR-SCT')
    bbsr_tpm_summary_content = adjust_bbsr_headings(bbsr_tpm_summary_content, 'BBSR-TPM')
    post_script_summary_content = adjust_bbsr_headings(post_script_summary_content, 'POST-SCRIPT')
    OS_tests_summary_content = adjust_bbsr_headings(OS_tests_summary_content, 'OS')
    standalone_summary_content = adjust_bbsr_headings(standalone_summary_content, 'Standalone')

    # Jinja2 template for the final HTML page
    html_template = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>ACS Summary</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f5f5f5;
                color: #333;
                margin: 0;
                padding: 0;
            }
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 24px;
            }
            .container {
                width: 80%;
                margin: 40px auto;
                padding: 20px;
                background-color: #fff;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            h1, h2 {
                color: #2c3e50;
                text-align: left;
            }
            .system-info, .acs-results-summary {
                margin-bottom: 40px;
                padding: 20px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            .system-info h2, .acs-results-summary h2 {
                text-align: left;
                color: #2c3e50;
            }
            .summary-section {
                margin-bottom: 40px;
            }
            .summary {
                margin-bottom: 40px;
                padding: 20px;
                border-bottom: 1px solid #ddd;
            }
            .details-link {
                text-align: center;
                margin-top: 10px;
            }
            .details-link a {
                color: #3498db;
                text-decoration: none;
                font-weight: bold;
                padding: 10px 20px;
                border: 2px solid #3498db;
                border-radius: 5px;
                display: inline-block;
                transition: background-color 0.3s, color 0.3s;
            }
            .details-link a:hover {
                background-color: #3498db;
                color: white;
            }
            .dropdown {
                text-align: center;
                margin-bottom: 40px;
                position: relative;
                display: inline-block;
            }
            .dropdown button {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            .dropdown-content {
                display: none;
                position: absolute;
                background-color: #f9f9f9;
                min-width: 220px;
                box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
                z-index: 1;
                left: 50%;
                transform: translateX(-50%);
            }
            .dropdown-content a {
                color: black;
                padding: 12px 16px;
                text-decoration: none;
                display: block;
                text-align: left;
            }
            .dropdown-content a:hover {
                background-color: #f1f1f1;
            }
            .dropdown:hover .dropdown-content {
                display: block;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }
            table, th, td {
                border: 1px solid #ddd;
            }
            th, td {
                padding: 12px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        </style>
    </head>
    <body>
        <div class="header">
            ACS Summary
        </div>
        <div class="container">
            <div class="system-info">
                <h2>System Information</h2>
                <table>
                    <tr>
                        <th>Vendor</th>
                        <td>{{ system_info.get('Vendor', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>System</th>
                        <td>{{ system_info.get('System Name', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>SoC Family</th>
                        <td>{{ system_info.get('SoC Family', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>Firmware Version</th>
                        <td>{{ system_info.get('Firmware Version', 'Unknown') }}</td>
                    </tr>
                    {% for key, value in system_info.items() %}
                    {% if key not in ['Vendor', 'System Name', 'SoC Family', 'Firmware Version'] %}
                    <tr>
                        <th>{{ key }}</th>
                        <td>{{ value }}</td>
                    </tr>
                    {% endif %}
                    {% endfor %}
                </table>
            </div>
            <div class="acs-results-summary">
                <h2>ACS Results Summary</h2>
                <table>
                    <tr>
                        <th>Band</th>
                        <td>{{ acs_results_summary.get('Band', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>Date</th>
                        <td>{{ acs_results_summary.get('Date', 'Unknown') }}</td>
                    </tr>
                    <tr>
                        <th>Overall Compliance Results</th>
                        <td style="
                            color: 
                            {% if 'Not Compliant' in acs_results_summary.get('Overall Compliance Results', '') %}
                                red
                            {% elif 'Compliant with Waivers' in acs_results_summary.get('Overall Compliance Results', '') %}
                                #FFBF00
                            {% elif 'Compliant' in acs_results_summary.get('Overall Compliance Results', '') %}
                                green
                            {% else %}
                                black
                            {% endif %}
                        ">
                            {{ acs_results_summary.get('Overall Compliance Results', 'Unknown') }}
                        </td>
                    </tr>
                </table>
            </div>
            <div class="dropdown">
                <button>Go to Summary</button>
                <div class="dropdown-content">
                    {% if bsa_summary_content %}
                    <a href="#bsa_summary">BSA Summary</a>
                    {% endif %}
                    {% if sbsa_summary_content %}
                    <a href="#sbsa_summary">SBSA Summary</a>
                    {% endif %}
                    {% if fwts_summary_content %}
                    <a href="#fwts_summary">FWTS Summary</a>
                    {% endif %}
                    {% if sct_summary_content %}
                    <a href="#sct_summary">SCT Summary</a>
                    {% endif %}
                    {% if post_script_summary_content %} 
                    <a href="#post_script_summary">POST-SCRIPT Summary</a> 
                    {% endif %} 
                    {% if standalone_summary_content %}
                    <a href="#standalone_summary">Standalone tests Summary</a>
                    {% endif %}
                    {% if bbsr_fwts_summary_content %}
                    <a href="#bbsr_fwts_summary">BBSR-FWTS Summary</a>
                    {% endif %}
                    {% if bbsr_sct_summary_content %}
                    <a href="#bbsr_sct_summary">BBSR-SCT Summary</a>
                    {% endif %} 
                    {% if bbsr_tpm_summary_content %}
                    <a href="#bbsr_tpm_summary">BBSR-TPM Summary</a>
                    {% endif %}
                    {% if OS_tests_summary_content %}
                    <a href="#OS_tests_summary">OS tests Summary</a>
                    {% endif %}
                </div>
            </div>

            <div class="dropdown">
                <button>Go to Views</button>
                <div id="views-dropdown-content" class="dropdown-content">
                <div class="dropdown-content">
                    {% for view_link in view_links %}
                    <a href="{{ view_link.href }}" target="_blank">{{ view_link.name }}</a>
                    {% endfor %}
                </div>
            </div>

            <div class="summary-section">
                <h2>Test Summaries</h2>
                {% if bsa_summary_content %}
                <div class="summary" id="bsa_summary">
                    {{ bsa_summary_content | safe }}
                    <div class="details-link">
                        <a href="bsa_detailed.html" target="_blank">Click here to go to the detailed summary for BSA</a>
                    </div>
                </div>
                {% endif %}
                {% if sbsa_summary_content %}
                <div class="summary" id="sbsa_summary">
                    {{ sbsa_summary_content | safe }}
                    <div class="details-link">
                        <a href="sbsa_detailed.html" target="_blank">Click here to go to the detailed summary for SBSA</a>
                    </div>
                </div>
                {% endif %}
                {% if fwts_summary_content %}
                <div class="summary" id="fwts_summary">
                    {{ fwts_summary_content | safe }}
                    <div class="details-link">
                        <a href="fwts_detailed.html" target="_blank">Click here to go to the detailed summary for FWTS</a>
                    </div>
                </div>
                {% endif %}
                {% if sct_summary_content %}
                <div class="summary" id="sct_summary">
                    {{ sct_summary_content | safe }}
                    <div class="details-link">
                        <a href="sct_detailed.html" target="_blank">Click here to go to the detailed summary for SCT</a>
                    </div>
                </div>
                {% endif %}
                {% if post_script_summary_content %} 
                <div class="summary" id="post_script_summary"> 
                    {{ post_script_summary_content | safe }} 
                    <div class="details-link"> 
                        <a href="post_script_detailed.html" target="_blank">Click here to go to the detailed summary for POST-SCRIPT</a> 
                    </div> 
                </div> 
                {% endif %} 
                {% if standalone_summary_content %}
                <div class="summary" id="standalone_summary">
                    {{ standalone_summary_content | safe }}
                    <div class="details-link">
                        <a href="standalone_tests_detailed.html" target="_blank">Click here to go to the detailed summary for Standalone tests</a>
                    </div>
                </div>
                {% endif %}
                {% if bbsr_fwts_summary_content %}
                <div class="summary" id="bbsr_fwts_summary">
                    {{ bbsr_fwts_summary_content | safe }}
                    <div class="details-link">
                        <a href="bbsr_fwts_detailed.html" target="_blank">Click here to go to the detailed summary for BBSR-FWTS</a>
                    </div>
                </div>
                {% endif %}
                {% if bbsr_sct_summary_content %}
                <div class="summary" id="bbsr_sct_summary">
                    {{ bbsr_sct_summary_content | safe }}
                    <div class="details-link">
                        <a href="bbsr_sct_detailed.html" target="_blank">Click here to go to the detailed summary for BBSR-SCT</a>
                    </div>
                </div>
                {% endif %}
                {% if bbsr_tpm_summary_content %}
                <div class="summary" id="bbsr_tpm_summary">
                    {{ bbsr_tpm_summary_content | safe }}
                    <div class="details-link">
                        <a href="bbsr_tpm_detailed.html" target="_blank">Click here to go to the detailed summary for BBSR-TPM</a>
                    </div>
                </div>
                {% endif %}
                {% if OS_tests_summary_content %}
                <div class="summary" id="OS_tests_summary">
                    {{ OS_tests_summary_content | safe }}
                    <div class="details-link">
                        <a href="os_tests_detailed.html" target="_blank">Click here to go to the detailed summary for OS Tests</a>
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </body>
    </html>
    '''

    main_template_str = html_template
    T = Template(main_template_str)
    rendered_html = T.render(
        system_info=system_info,
        acs_results_summary=acs_results_summary,
        bsa_summary_content=bsa_summary_content,
        sbsa_summary_content=sbsa_summary_content,
        fwts_summary_content=fwts_summary_content,
        sct_summary_content=sct_summary_content,
        bbsr_fwts_summary_content=bbsr_fwts_summary_content,
        bbsr_sct_summary_content=bbsr_sct_summary_content,
        bbsr_tpm_summary_content=bbsr_tpm_summary_content,
        post_script_summary_content=post_script_summary_content,
        standalone_summary_content=standalone_summary_content,
        OS_tests_summary_content=OS_tests_summary_content,
        view_links=[]
    )

    readiness_link_html = """
    <div style="text-align:center; margin-top:20px;">
        <a href="readiness_view.html" target="_blank" style="color: #3498db; text-decoration: none; font-weight: bold; padding: 10px 20px; border: 2px solid #3498db; border-radius: 5px; transition: background-color 0.3s, color 0.3s;">
            Go to Readiness View Page
        </a>
    </div>
    """
    final_html = rendered_html.replace('</div>\n    </body>', readiness_link_html + '\n</div>\n    </body>')

    with open(output_html_path, 'w') as html_file:
        html_file.write(final_html)

    # Adjust headings in the *detailed* summary pages
    detailed_summaries = [
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_fwts_detailed.html'), 'BBSR-FWTS'),
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_sct_detailed.html'), 'BBSR-SCT'),
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_tpm_detailed.html'), 'BBSR-TPM'), 
        (os.path.join(os.path.dirname(output_html_path), 'os_tests_detailed.html'), 'OS'),
        (os.path.join(os.path.dirname(output_html_path), 'standalone_tests_detailed.html'), 'Standalone'),
        (os.path.join(os.path.dirname(output_html_path), 'post_script_detailed.html'), 'POST-SCRIPT')
    ]
    for file_path, suite_name in detailed_summaries:
        adjust_detailed_summary_heading(file_path, suite_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ACS Summary HTML page")
    parser.add_argument("--merged_json", default="", help="Path to merged_results.json if you want to pull final compliance from there")
    parser.add_argument("bsa_summary_path", help="Path to the BSA summary HTML file")
    parser.add_argument("sbsa_summary_path", help="Path to the SBSA summary HTML file")
    parser.add_argument("fwts_summary_path", help="Path to the FWTS summary HTML file")
    parser.add_argument("sct_summary_path", help="Path to the SCT summary HTML file")
    parser.add_argument("bbsr_fwts_summary_path", help="Path to the BBSR FWTS summary HTML file")
    parser.add_argument("bbsr_sct_summary_path", help="Path to the BBSR SCT summary HTML file")
    parser.add_argument("bbsr_tpm_summary_path", help="Path to the BBSR TPM summary HTML file") 
    parser.add_argument("post_script_summary_path", help="Path to the post-script summary HTML file")
    parser.add_argument("standalone_summary_path", help="Path to the Standalone tests summary HTML file")
    parser.add_argument("OS_tests_summary_path", help="Path to the OS Tests summary HTML file")
    parser.add_argument("capsule_update_summary_path", help="Path to the Capsule Update summary HTML file")
    parser.add_argument("output_html_path", help="Path to the output ACS summary HTML file")
    parser.add_argument("--acs_config_path", default="", help="Path to the acs_config.txt file")
    parser.add_argument("--system_config_path", default="", help="Path to the system_config.txt file")
    parser.add_argument("--uefi_version_log", default="", help="Path to the uefi_version.log file")
    parser.add_argument("--device_tree_dts", default="", help="Path to the device_tree.dts file")

    args = parser.parse_args()

    # 1) Basic system info
    system_info = get_system_info()

    # 2) Merge data from ACS config & system config
    acs_config_info = parse_config(args.acs_config_path)
    system_config_info = parse_config(args.system_config_path)
    system_info.update(acs_config_info)
    system_info.update(system_config_info)

    # 3) UEFI version
    uefi_version = get_uefi_version(args.uefi_version_log)
    system_info['UEFI Version'] = uefi_version

    # 4) Extract summary date from system_info
    summary_generated_date = system_info.pop('Summary Generated On Date/time', 'Unknown')

    # 5) Read in the stand-alone & capsule summary, then combine them
    standalone_summary_content = read_html_content(args.standalone_summary_path)
    capsule_update_summary_content = read_html_content(args.capsule_update_summary_path)
    if capsule_update_summary_content:
        # Append capsule content to standalone if it exists
        if not standalone_summary_content:
            standalone_summary_content = capsule_update_summary_content
        else:
            standalone_summary_content += "<hr/>\n" + capsule_update_summary_content

    # 6) Collect the summary contents for each suite so we can get the fail/waiver counts (purely for printing)
    suite_content_map = {
        "BSA": read_html_content(args.bsa_summary_path),
        "SBSA": read_html_content(args.sbsa_summary_path),
        "FWTS": read_html_content(args.fwts_summary_path),
        "SCT": read_html_content(args.sct_summary_path),
        "BBSR-FWTS": read_html_content(args.bbsr_fwts_summary_path),
        "BBSR-SCT": read_html_content(args.bbsr_sct_summary_path),
        "BBSR-TPM": read_html_content(args.bbsr_tpm_summary_path),
        "POST-SCRIPT": read_html_content(args.post_script_summary_path),
        "Standalone tests": standalone_summary_content,
        "OS tests": read_html_content(args.OS_tests_summary_path)
    }

    # 8) Read overall compliance solely from merged JSON (if provided)
    overall_compliance = "Unknown"
    if args.merged_json and os.path.isfile(args.merged_json):
        overall_compliance = read_overall_compliance_from_merged_json(args.merged_json)
    else:
        print("Warning: merged JSON not provided or does not exist => Overall compliance unknown")

    # 9) Prepare the dictionary that will be used in the final HTML
    acs_results_summary = {
        'Band': acs_config_info.get('Band', 'Unknown'),
        'Date': summary_generated_date,
        'Overall Compliance Results': overall_compliance
    }

    summary_dir = os.path.dirname(args.output_html_path)
    view_links = []
    if args.merged_json and os.path.isfile(args.merged_json):
        view_links = generate_multi_view_pages(args.merged_json, summary_dir)

    generate_html(
        system_info,
        acs_results_summary,
        args.bsa_summary_path,
        args.sbsa_summary_path,
        args.fwts_summary_path,
        args.sct_summary_path,
        args.bbsr_fwts_summary_path,
        args.bbsr_sct_summary_path,
        args.bbsr_tpm_summary_path, 
        args.post_script_summary_path,
        args.standalone_summary_path,
        args.OS_tests_summary_path,
        args.output_html_path
    )

    with open(args.output_html_path, 'r') as f:
        main_html_contents = f.read()

    link_html = ""
    for link in view_links:
        link_html += f'<a href="{link["href"]}" target="_blank">{link["name"]}</a>\n'

    placeholder_pattern = r'(<div id="views-dropdown-content"[^>]*>\s*)(.*?)\s*(</div>)'
    replaced_html = re.sub(
        placeholder_pattern,
        rf'\1{link_html}\3',
        main_html_contents,
        flags=re.DOTALL
    )

    with open(args.output_html_path, 'w') as f:
        f.write(replaced_html)
