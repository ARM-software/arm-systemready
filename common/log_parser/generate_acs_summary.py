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

import argparse
import os
import subprocess
import re
from jinja2 import Template

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

    # Get SoC Family using 'sudo dmidecode -t system | grep -i "Family"'
    try:
        soc_family_output = subprocess.check_output(
            "sudo dmidecode -t system | grep -i 'Family'", shell=True, universal_newlines=True, stderr=subprocess.DEVNULL)
        if 'Family:' in soc_family_output:
            system_info['SoC Family'] = soc_family_output.split('Family:')[1].strip()
        else:
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

def get_failed_with_waiver_counts(content):
    failed = 0
    failed_with_waiver = 0
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "Failed with Waiver" in line:
            try:
                count_line = lines[i + 1].strip()
                start = count_line.find('>') + 1
                end = count_line.find('</td>', start)
                num_part = count_line[start:end].strip()
                failed_with_waiver = int(num_part)
                i += 1
            except (IndexError, ValueError):
                pass
        elif "Failed" in line and "Failed with Waiver" not in line:
            try:
                count_line = lines[i + 1].strip()
                start = count_line.find('>') + 1
                end = count_line.find('</td>', start)
                num_part = count_line[start:end].strip()
                failed = int(num_part)
                i += 1
            except (IndexError, ValueError):
                pass
        i += 1

    return failed, failed_with_waiver

def determine_overall_compliance(bsa_summary_content, sbsa_summary_content, fwts_summary_content, sct_summary_content,
                                 bbsr_fwts_summary_content, bbsr_sct_summary_content,
                                 standalone_summary_content, OS_tests_summary_content):
    overall_compliance = 'Compliant'
    summaries = {
        'BSA': bsa_summary_content,
        'SBSA': sbsa_summary_content,
        'FWTS': fwts_summary_content,
        'SCT': sct_summary_content,
        'BBSR-FWTS': bbsr_fwts_summary_content,
        'BBSR-SCT': bbsr_sct_summary_content,
        'Standalone tests': standalone_summary_content,
        'OS tests': OS_tests_summary_content
    }

    all_failed_zero = True
    compliant_with_waivers = True
    suite_counts = {}

    for suite, content in summaries.items():
        if content:
            failed, failed_with_waiver = get_failed_with_waiver_counts(content)
            suite_counts[suite] = {'Failed': failed, 'Failed with Waiver': failed_with_waiver}
            # Check compliance
            if failed != failed_with_waiver:
                compliant_with_waivers = False
            if failed != 0 or failed_with_waiver != 0:
                all_failed_zero = False

    if all_failed_zero:
        overall_compliance = 'Compliant'
    elif compliant_with_waivers:
        any_failures = any(
            (counts['Failed with Waiver'] > 0) for counts in suite_counts.values()
        )
        if any_failures:
            overall_compliance = 'Compliant with Waivers'
        else:
            overall_compliance = 'Compliant'
    else:
        overall_compliance = 'Not compliant'

    for suite, counts in suite_counts.items():
        print(f"Suite: {suite}, Failed: {counts['Failed']}, Failed with Waiver: {counts['Failed with Waiver']}")
    print(f"\nOverall Compliance: {overall_compliance}\n")

    return overall_compliance


def generate_html(system_info, acs_results_summary,
                  bsa_summary_path, sbsa_summary_path, fwts_summary_path, sct_summary_path,
                  bbsr_fwts_summary_path, bbsr_sct_summary_path,
                  standalone_summary_path, OS_tests_summary_path,
                  output_html_path):
    bsa_summary_content = read_html_content(bsa_summary_path)
    sbsa_summary_content = read_html_content(sbsa_summary_path)
    fwts_summary_content = read_html_content(fwts_summary_path)
    sct_summary_content = read_html_content(sct_summary_path)
    bbsr_fwts_summary_content = read_html_content(bbsr_fwts_summary_path)
    bbsr_sct_summary_content = read_html_content(bbsr_sct_summary_path)
    standalone_summary_content = read_html_content(standalone_summary_path)
    OS_tests_summary_content = read_html_content(OS_tests_summary_path)

    # Adjust headings where needed
    bbsr_fwts_summary_content = adjust_bbsr_headings(bbsr_fwts_summary_content, 'BBSR-FWTS')
    bbsr_sct_summary_content = adjust_bbsr_headings(bbsr_sct_summary_content, 'BBSR-SCT')
    OS_tests_summary_content = adjust_bbsr_headings(OS_tests_summary_content, 'OS')
    standalone_summary_content = adjust_bbsr_headings(standalone_summary_content, 'Standalone')

    # We color-code "Overall Compliance Results" using inline styling based on the final value
    # "Not compliant" → red, "Compliant" → green, "Compliant with Waivers" → amber (#FFBF00).
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
                            {% if acs_results_summary.get('Overall Compliance Results') == 'Not compliant' %}
                                red
                            {% elif acs_results_summary.get('Overall Compliance Results') == 'Compliant' %}
                                green
                            {% elif acs_results_summary.get('Overall Compliance Results') == 'Compliant with Waivers' %}
                                #FFBF00
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
                    {% if standalone_summary_content %}
                    <a href="#standalone_summary">Standalone tests Summary</a>
                    {% endif %}
                    {% if bbsr_fwts_summary_content %}
                    <a href="#bbsr_fwts_summary">BBSR-FWTS Summary</a>
                    {% endif %}
                    {% if bbsr_sct_summary_content %}
                    <a href="#bbsr_sct_summary">BBSR-SCT Summary</a>
                    {% endif %}
                    {% if OS_tests_summary_content %}
                    <a href="#OS_tests_summary">OS tests Summary</a>
                    {% endif %}
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

    template = Template(html_template)
    html_output = template.render(
        system_info=system_info,
        acs_results_summary=acs_results_summary,
        bsa_summary_content=bsa_summary_content,
        sbsa_summary_content=sbsa_summary_content,
        fwts_summary_content=fwts_summary_content,
        sct_summary_content=sct_summary_content,
        bbsr_fwts_summary_content=bbsr_fwts_summary_content,
        bbsr_sct_summary_content=bbsr_sct_summary_content,
        standalone_summary_content=standalone_summary_content,
        OS_tests_summary_content=OS_tests_summary_content
    )

    with open(output_html_path, 'w') as html_file:
        html_file.write(html_output)

    # Adjust headings in detailed summary pages
    detailed_summaries = [
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_fwts_detailed.html'), 'BBSR-FWTS'),
        (os.path.join(os.path.dirname(output_html_path), 'bbsr_sct_detailed.html'), 'BBSR-SCT'),
        (os.path.join(os.path.dirname(output_html_path), 'os_tests_detailed.html'), 'OS'),
        (os.path.join(os.path.dirname(output_html_path), 'standalone_tests_detailed.html'), 'Standalone')
    ]
    for file_path, suite_name in detailed_summaries:
        adjust_detailed_summary_heading(file_path, suite_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ACS Summary HTML page")
    parser.add_argument("bsa_summary_path", help="Path to the BSA summary HTML file")
    parser.add_argument("sbsa_summary_path", help="Path to the SBSA summary HTML file")
    parser.add_argument("fwts_summary_path", help="Path to the FWTS summary HTML file")
    parser.add_argument("sct_summary_path", help="Path to the SCT summary HTML file")
    parser.add_argument("bbsr_fwts_summary_path", help="Path to the BBSR FWTS summary HTML file")
    parser.add_argument("bbsr_sct_summary_path", help="Path to the BBSR SCT summary HTML file")
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

    # 5) Extract summary date from system_info
    summary_generated_date = system_info.pop('Summary Generated On Date/time', 'Unknown')

    # 6) Read in the stand-alone & capsule summary, then combine them
    standalone_summary_content = read_html_content(args.standalone_summary_path)
    capsule_update_summary_content = read_html_content(args.capsule_update_summary_path)
    if capsule_update_summary_content:
        # Append capsule content to standalone
        if not standalone_summary_content:
            standalone_summary_content = capsule_update_summary_content
        else:
            standalone_summary_content += "<hr/>\n" + capsule_update_summary_content

    # 7) Prepare to determine overall compliance
    bsa_summary_content = read_html_content(args.bsa_summary_path)
    sbsa_summary_content = read_html_content(args.sbsa_summary_path)
    fwts_summary_content = read_html_content(args.fwts_summary_path)
    sct_summary_content = read_html_content(args.sct_summary_path)
    bbsr_fwts_summary_content = read_html_content(args.bbsr_fwts_summary_path)
    bbsr_sct_summary_content = read_html_content(args.bbsr_sct_summary_path)
    OS_tests_summary_content = read_html_content(args.OS_tests_summary_path)

    overall_compliance = determine_overall_compliance(
        bsa_summary_content,
        sbsa_summary_content,
        fwts_summary_content,
        sct_summary_content,
        bbsr_fwts_summary_content,
        bbsr_sct_summary_content,
        standalone_summary_content,
        OS_tests_summary_content
    )

    acs_results_summary = {
        'Band': acs_config_info.get('Band', 'Unknown'),
        'Date': summary_generated_date,
        'Overall Compliance Results': overall_compliance
    }

    generate_html(
        system_info,
        acs_results_summary,
        args.bsa_summary_path,
        args.sbsa_summary_path,
        args.fwts_summary_path,
        args.sct_summary_path,
        args.bbsr_fwts_summary_path,
        args.bbsr_sct_summary_path,
        args.standalone_summary_path,
        args.OS_tests_summary_path,
        args.output_html_path
    )
    