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
    except Exception as e:
        system_info['Firmware Version'] = 'Unknown'

    # Get SoC Family using 'sudo dmidecode -t system | grep -i "Family"'
    try:
        soc_family_output = subprocess.check_output(
            "sudo dmidecode -t system | grep -i 'Family'", shell=True, universal_newlines=True, stderr=subprocess.DEVNULL)
        if 'Family:' in soc_family_output:
            system_info['SoC Family'] = soc_family_output.split('Family:')[1].strip()
        else:
            system_info['SoC Family'] = 'Unknown'
    except Exception as e:
        system_info['SoC Family'] = 'Unknown'

    # Get System Name
    try:
        system_name_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in system_name_output.split('\n'):
            if 'Product Name:' in line:
                system_info['System Name'] = line.split('Product Name:')[1].strip()
                break
    except Exception as e:
        system_info['System Name'] = 'Unknown'

    # Get Vendor
    try:
        vendor_output = subprocess.check_output(
            ["dmidecode", "-t", "system"], universal_newlines=True, stderr=subprocess.DEVNULL)
        for line in vendor_output.split('\n'):
            if 'Manufacturer:' in line:
                system_info['Vendor'] = line.split('Manufacturer:')[1].strip()
                break
    except Exception as e:
        system_info['Vendor'] = 'Unknown'

    # Add date when the summary was generated
    system_info['Summary Generated On Date/time'] = subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S"]).decode().strip()
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

def get_device_tree_version(device_tree_dts):
    dt_version = 'Unknown'
    try:
        if device_tree_dts and os.path.exists(device_tree_dts):
            with open(device_tree_dts, 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    if '/dts-v' in line:
                        # Extract the version number
                        start_index = line.find('/dts-v') + len('/dts-v')
                        end_index = line.find(';', start_index)
                        if end_index == -1:
                            end_index = len(line)
                        version_info = line[start_index:end_index].strip()
                        version_info = version_info.rstrip('/;')
                        dt_version = 'v' + version_info
                        break
        else:
            dt_version = 'Not provided'
    except Exception as e:
        print(f"Error reading Device Tree DTS file: {e}")
    return dt_version

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

def determine_overall_compliance(bsa_summary_content, sbsa_summary_content, fwts_summary_content, sct_summary_content, mvp_summary_content):
    # Initialize as 'Compliant'
    overall_compliance = 'Compliant'
    # Check for 'Failed' or 'Aborted' in any of the summaries
    for content in [bsa_summary_content, sbsa_summary_content, fwts_summary_content, sct_summary_content, mvp_summary_content]:
        if content:
            if 'Failed' in content or 'Aborted' in content:
                overall_compliance = 'Not compliant'
                break
    return overall_compliance

def generate_html(system_info, acs_results_summary, bsa_summary_path, sbsa_summary_path, fwts_summary_path, sct_summary_path,
                  mvp_summary_path, output_html_path):
    bsa_summary_content = read_html_content(bsa_summary_path)
    sbsa_summary_content = read_html_content(sbsa_summary_path)
    fwts_summary_content = read_html_content(fwts_summary_path)
    sct_summary_content = read_html_content(sct_summary_path)
    mvp_summary_content = read_html_content(mvp_summary_path)

    html_template = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <!-- Head content -->
        <meta charset="UTF-8">
        <title>ACS Summary</title>
        <!-- Include styles here -->
        <style>
            /* Styles as provided earlier */
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
            .system-info {
                margin-bottom: 40px;
                padding: 20px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            .system-info h2 {
                text-align: left;
                color: #2c3e50;
            }
            .acs-results-summary {
                margin-bottom: 40px;
                padding: 20px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            .acs-results-summary h2 {
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
                        <td>{{ acs_results_summary.get('Overall Compliance Results', 'Unknown') }}</td>
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
                    {% if mvp_summary_content %}
                    <a href="#mvp_summary">MVP Summary</a>
                    {% endif %}
                </div>
            </div>
            <div class="summary-section">
                <h2>Test Summaries</h2>
                {% if bsa_summary_content %}
                <div class="summary" id="bsa_summary">
                    {{ bsa_summary_content | safe }}
                    <div class="details-link">
                        <a href="BSA_detailed.html" target="_blank">Click here to go to the detailed summary for BSA</a>
                    </div>
                </div>
                {% endif %}
                {% if sbsa_summary_content %}
                <div class="summary" id="sbsa_summary">
                    {{ sbsa_summary_content | safe }}
                    <div class="details-link">
                        <a href="SBSA_detailed.html" target="_blank">Click here to go to the detailed summary for SBSA</a>
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
                        <a href="SCT_detailed.html" target="_blank">Click here to go to the detailed summary for SCT</a>
                    </div>
                </div>
                {% endif %}
                {% if mvp_summary_content %}
                <div class="summary" id="mvp_summary">
                    {{ mvp_summary_content | safe }}
                    <div class="details-link">
                        <a href="MVP_detailed.html" target="_blank">Click here to go to the detailed summary for MVP</a>
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
        bsa_summary_content=read_html_content(bsa_summary_path),
        sbsa_summary_content=read_html_content(sbsa_summary_path),
        fwts_summary_content=read_html_content(fwts_summary_path),
        sct_summary_content=read_html_content(sct_summary_path),
        mvp_summary_content=read_html_content(mvp_summary_path)
    )

    with open(output_html_path, 'w') as html_file:
        html_file.write(html_output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ACS Summary HTML page")
    parser.add_argument("bsa_summary_path", help="Path to the BSA summary HTML file")
    parser.add_argument("sbsa_summary_path", help="Path to the SBSA summary HTML file")
    parser.add_argument("fwts_summary_path", help="Path to the FWTS summary HTML file")
    parser.add_argument("sct_summary_path", help="Path to the SCT summary HTML file")
    parser.add_argument("mvp_summary_path", help="Path to the MVP summary HTML file")
    parser.add_argument("output_html_path", help="Path to the output ACS summary HTML file")
    parser.add_argument("--acs_config_path", default="", help="Path to the acs_config.txt file")
    parser.add_argument("--system_config_path", default="", help="Path to the system_config.txt file")
    parser.add_argument("--uefi_version_log", default="", help="Path to the uefi_version.log file")
    parser.add_argument("--device_tree_dts", default="", help="Path to the device_tree.dts file")

    args = parser.parse_args()

    system_info = get_system_info()
    acs_config_info = parse_config(args.acs_config_path)
    system_config_info = parse_config(args.system_config_path)

    # Merge configurations into system_info
    system_info.update(acs_config_info)
    system_info.update(system_config_info)

    uefi_version = get_uefi_version(args.uefi_version_log)
    dt_version = get_device_tree_version(args.device_tree_dts)

    # Add UEFI and Device Tree versions to system_info
    system_info['UEFI Version'] = uefi_version
    system_info['Device Tree Version'] = dt_version

    # Extract and remove date from system_info to place it in acs_results_summary
    summary_generated_date = system_info.pop('Summary Generated On Date/time', 'Unknown')

    # Determine Overall Compliance Results
    bsa_summary_content = read_html_content(args.bsa_summary_path)
    sbsa_summary_content = read_html_content(args.sbsa_summary_path)
    fwts_summary_content = read_html_content(args.fwts_summary_path)
    sct_summary_content = read_html_content(args.sct_summary_path)
    mvp_summary_content = read_html_content(args.mvp_summary_path)

    overall_compliance = determine_overall_compliance(
        bsa_summary_content,
        sbsa_summary_content,
        fwts_summary_content,
        sct_summary_content,
        mvp_summary_content
    )

    # Prepare ACS Results Summary
    acs_results_summary = {
        'Band': acs_config_info.get('Band', 'Unknown'),  # Extract 'Band' from acs_config_info
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
        args.mvp_summary_path,
        args.output_html_path
    )
