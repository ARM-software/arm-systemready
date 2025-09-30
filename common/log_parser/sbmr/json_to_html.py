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
import os
import sys

# ----------------------------
# Helpers
# ----------------------------

def get_case_insensitive(d, key, default=0):
    if not isinstance(d, dict):
        return default
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default

def summarize_subtests_list(subtests):
    total = {
        'total_passed': 0,
        'total_failed': 0,
        'total_failed_with_waiver': 0,
        'total_aborted': 0,
        'total_skipped': 0,
        'total_warnings': 0,
        'total_ignored': 0,
    }
    for st in subtests or []:
        res = st.get('sub_test_result')
        if isinstance(res, dict):
            total['total_passed']             += res.get('PASSED', 0)
            total['total_failed']             += res.get('FAILED', 0)
            total['total_failed_with_waiver'] += res.get('FAILED_WITH_WAIVER', 0)
            total['total_aborted']            += res.get('ABORTED', 0)
            total['total_skipped']            += res.get('SKIPPED', 0)
            total['total_warnings']           += res.get('WARNINGS', 0)
        else:
            u = (res or "").upper()
            if 'PASS' in u:
                total['total_passed'] += 1
            elif 'FAIL' in u:
                if '(WITH WAIVER)' in u:
                    total['total_failed_with_waiver'] += 1
                else:
                    total['total_failed'] += 1
            elif 'ABORT' in u:
                total['total_aborted'] += 1
            elif 'SKIP' in u:
                total['total_skipped'] += 1
            elif 'WARN' in u:
                total['total_warnings'] += 1
            else:
                total['total_ignored'] += 1
    return total

def compute_suite_summary_from_results(test_results):
    agg = {
        'total_passed': 0,
        'total_failed': 0,
        'total_failed_with_waiver': 0,
        'total_aborted': 0,
        'total_skipped': 0,
        'total_warnings': 0,
        'total_ignored': 0,
    }
    for suite in test_results:
        if isinstance(suite, dict) and 'Test_cases' in suite:
            ss = suite.get('test_suite_summary', {})
            for k in agg:
                agg[k] += get_case_insensitive(ss, k, 0)
        else:
            ss = suite.get('test_suite_summary')
            if not ss:
                ss = summarize_subtests_list(suite.get('subtests', []))
            for k in agg:
                agg[k] += ss.get(k, 0)
    return agg

def generate_bar_chart(suite_summary):
    labels = ['Passed', 'Failed', 'Failed with Waiver', 'Aborted', 'Skipped', 'Warnings']
    sizes = [
        suite_summary.get('total_passed', 0),
        suite_summary.get('total_failed', 0),
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_aborted', 0),
        suite_summary.get('total_skipped', 0),
        suite_summary.get('total_warnings', 0)
    ]
    colors = ['#66bb6a', '#ef5350', '#f39c12', '#9e9e9e', '#ffc107', '#ffeb3b']

    plt.figure(figsize=(12, 7))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    total_tests = sum(sizes)
    max_size = max(sizes) if sizes else 0
    for bar, size in zip(bars, sizes):
        y = bar.get_height()
        pct = (size / total_tests) * 100 if total_tests > 0 else 0
        plt.text(
            bar.get_x() + bar.get_width()/2,
            y + (0.01 * max_size if max_size else 0.1),
            f'{pct:.2f}%',
            ha='center',
            va='bottom',
            fontsize=12
        )

    plt.title('Test Results Distribution', fontsize=18, fontweight='bold')
    plt.ylabel('Total Count', fontsize=14)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# ----------------------------
# HTML templates
# ----------------------------

DETAIL_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ page_title }} Test Details</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
        h1, h2, h3 { color: #2c3e50; text-align: center; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; border: 1px solid #ddd; font-size: 16px; }
        th { background-color: #3498db; color: white; font-weight: bold; text-align: left; }
        .pass { background-color: #d4edda; font-weight: bold; }
        .fail { background-color: #f8d7da; font-weight: bold; }
        .fail-waiver { background-color: #f39c12; font-weight: bold; }
        .warning { background-color: #fff3cd; font-weight: bold; }
        .aborted { background-color: #bdbdbd; font-weight: bold; }
        .skipped { background-color: #ffe0b2; font-weight: bold; }
        .summary-table { margin: 0 auto; width: 80%; }
        .summary-table td.total-tests { text-align: center; }
        .chart-container { display: flex; justify-content: center; }
        .result-summary, .detailed-summary {
            margin-top: 40px; padding: 20px; background-color: #fff;
            border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .suite-header { font-size: 22px; font-weight: bold; color: #34495e; margin-top: 30px; }
        .case-header  { font-size: 18px; font-weight: bold; color: #2c3e50; margin-top: 10px; }
        td.pass, td.fail, td.fail-waiver, td.warning, td.aborted, td.skipped { text-align: center; font-weight: bold; }
        td.reason { font-size: 14px; color: #444; }
        .detailed-summary table { table-layout: fixed; }
        .detailed-summary table thead th:nth-child(1),
        .detailed-summary table tbody td:nth-child(1) { width: 60px; }
        .detailed-summary table thead th:nth-child(2),
        .detailed-summary table tbody td:nth-child(2) { width: auto; }
        .detailed-summary table thead th:nth-child(3),
        .detailed-summary table tbody td:nth-child(3) { width: 140px; }
        .detailed-summary table thead th:nth-child(4),
        .detailed-summary table tbody td:nth-child(4) { width: 40%; }
        .detailed-summary td, .detailed-summary th { overflow: hidden; text-overflow: ellipsis; }
        .detailed-summary td:nth-child(2), .detailed-summary td:nth-child(4) {
            white-space: normal; word-break: break-word; overflow-wrap: anywhere;
        }
        .detailed-summary td.reason { white-space: pre-wrap; }
        /* --- SBMR report link card --- */
        .report-card{
        max-width: 920px;
        margin: 40px auto 10px;
        padding: 16px 18px;
        background: #ffffff;
        border: 1px solid #e3e6ea;
        border-left: 6px solid #3498db;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }
        .report-card-title{
        font-weight: 700;
        color: #2c3e50;
        margin: 0 0 8px 0;
        font-size: 18px;
        }
        .report-card-actions{
        display:flex;
        align-items:center;
        gap:12px;
        flex-wrap:wrap;
        }
        .report-card-btn{
        display:inline-block;
        padding:10px 16px;
        border-radius: 8px;
        background:#3498db;
        color:#fff !important;
        text-decoration:none;
        font-weight:700;
        border: 1px solid #2e86c1;
        }
        .report-card-btn:focus,
        .report-card-btn:hover{
        filter: brightness(0.95);
        }
        .report-card-path{
        color:#6b6f76;
        font-size: 14px;
        word-break: break-all;
        opacity: 0.95;
        }
    </style>
</head>
<body>
    <h1>{{ page_title }} Test Details</h1>

    <div class="chart-container">
        <img src="data:image/png;base64,{{ ds.chart_data }}" alt="Test Results Distribution">
    </div>

    <div class="result-summary">
        <h2>Overall Summary ({{ ds.label }})</h2>
        <table class="summary-table">
            <thead><tr><th>Status</th><th>Total</th></tr></thead>
            <tbody>
                <tr><td>Total Tests</td><td class="total-tests">{{ ds.total_tests }}</td></tr>
                <tr><td>Passed</td><td class="pass">{{ ds.summary.total_passed }}</td></tr>
                <tr><td>Failed</td><td class="fail">{{ ds.summary.total_failed }}</td></tr>
                <tr><td>Failed with Waiver</td><td class="fail-waiver">{{ ds.summary.total_failed_with_waiver }}</td></tr>
                <tr><td>Aborted</td><td class="aborted">{{ ds.summary.total_aborted }}</td></tr>
                <tr><td>Skipped</td><td class="skipped">{{ ds.summary.total_skipped }}</td></tr>
                <tr><td>Warnings</td><td class="warning">{{ ds.summary.total_warnings }}</td></tr>
            </tbody>
        </table>
    </div>

    <div class="detailed-summary">
        {% for suite in ds.suites %}
            <div class="suite-header">Test Suite: {{ suite.Test_suite }}</div>

            {% if suite.Test_cases is defined and suite.Test_cases %}
                {% for case in suite.Test_cases %}
                    <div class="case-header">Test Case: {{ case.Test_case }}</div>
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Description</th>
                                <th>Result</th>
                                <th>Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for st in case.subtests %}
                            {% set r = (st.sub_test_result or '') %}
                            {% set u = r.upper() %}
                            <tr>
                                <td>{{ st.sub_Test_Number }}</td>
                                <td>{{ st.sub_Test_Description }}</td>
                                <td class="{% if 'PASS' in u %}pass{% elif 'WITH WAIVER' in u %}fail-waiver{% elif 'FAIL' in u %}fail{% elif 'ABORT' in u %}aborted{% elif 'SKIP' in u %}skipped{% elif 'WARN' in u %}warning{% endif %}">
                                    {{ r }}
                                </td>
                                <td class="reason">{{ st.reason if st.reason is defined else 'N/A' }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                {% endfor %}
            {% else %}
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Description</th>
                            <th>Result</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for st in suite.subtests %}
                        {% set r = (st.sub_test_result or '') %}
                        {% set u = r.upper() %}
                        <tr>
                            <td>{{ st.sub_Test_Number }}</td>
                            <td>{{ st.sub_Test_Description }}</td>
                            <td class="{% if 'PASS' in u %}pass{% elif 'WITH WAIVER' in u %}fail-waiver{% elif 'FAIL' in u %}fail{% elif 'ABORT' in u %}aborted{% elif 'SKIP' in u %}skipped{% elif 'WARN' in u %}warning{% endif %}">
                                {{ r }}
                            </td>
                            <td class="reason">{{ st.reason if st.reason is defined else 'N/A' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% endif %}
        {% endfor %}
    {% if report_link %}
    <div class="report-card">
    <div class="report-card-title">SBMR report</div>
    <div class="report-card-actions">
        <a class="report-card-btn" href="{{ report_link }}">Open report.html</a>
        <div class="report-card-path">{{ report_link }}</div>
    </div>
    </div>
    {% endif %}
    </div>
</body>
</html>
""")

SUMMARY_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ page_title }} Test Summary</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
        h1, h2 { color: #2c3e50; text-align: center; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; border: 1px solid #ddd; font-size: 16px; }
        th { background-color: #3498db; color: white; font-weight: bold; text-align: left; }
        .pass { background-color: #d4edda; font-weight: bold; }
        .fail { background-color: #f8d7da; font-weight: bold; }
        .fail-waiver { background-color: #f39c12; font-weight: bold; }
        .warning { background-color: #fff3cd; font-weight: bold; }
        .aborted { background-color: #bdbdbd; font-weight: bold; }
        .skipped { background-color: #ffe0b2; font-weight: bold; }
        .summary-table { margin: 0 auto; width: 80%; }
        .summary-table td.total-tests { text-align: center; }
        .card { background: #fff; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px; }
    </style>
</head>
<body>
    <h1>{{ page_title }} Test Summary</h1>

    <div class="card">
        <h2>Overall Summary</h2>
        <table class="summary-table">
            <thead><tr><th>Status</th><th>Total</th></tr></thead>
            <tbody>
                <tr><td>Total Tests</td><td class="total-tests">{{ total_tests }}</td></tr>
                <tr><td>Passed</td><td class="pass">{{ total_passed }}</td></tr>
                <tr><td>Failed</td><td class="fail">{{ total_failed }}</td></tr>
                <tr><td>Failed with Waiver</td><td class="fail-waiver">{{ total_failed_with_waiver }}</td></tr>
                <tr><td>Aborted</td><td class="aborted">{{ total_aborted }}</td></tr>
                <tr><td>Skipped</td><td class="skipped">{{ total_skipped }}</td></tr>
                <tr><td>Warnings</td><td class="warning">{{ total_warnings }}</td></tr>
            </tbody>
        </table>
    </div>
</body>
</html>
""")

# ----------------------------
# Rendering
# ----------------------------

def render_detail_html(dataset, output_html_path, page_title, report_link=None):
    html = DETAIL_TEMPLATE.render(ds=dataset, page_title=page_title.upper(), report_link=report_link)
    with open(output_html_path, "w") as f:
        f.write(html)

def render_summary_html(combined_summary, output_html_path, page_title):
    total_tests = (
        combined_summary.get("total_passed", 0)
        + combined_summary.get("total_failed", 0)
        + combined_summary.get("total_aborted", 0)
        + combined_summary.get("total_skipped", 0)
        + combined_summary.get("total_warnings", 0)
        + combined_summary.get("total_failed_with_waiver", 0)
    )
    html = SUMMARY_TEMPLATE.render(
        page_title=page_title.upper(),
        total_tests=total_tests,
        total_passed=combined_summary.get("total_passed", 0),
        total_failed=combined_summary.get("total_failed", 0),
        total_failed_with_waiver=combined_summary.get("total_failed_with_waiver", 0),
        total_aborted=combined_summary.get("total_aborted", 0),
        total_skipped=combined_summary.get("total_skipped", 0),
        total_warnings=combined_summary.get("total_warnings", 0),
    )
    with open(output_html_path, "w") as f:
        f.write(html)

# ----------------------------
# Main
# ----------------------------

def friendly_label_from_filename(path):
    base = os.path.splitext(os.path.basename(path))[0].upper()
    # Aim for user-friendly labels:
    # sbmr_ib.json -> SBMR IB   |   sbmr_oob.json -> SBMR OOB
    base = base.replace("_", " ").replace("-", " ")
    return base

def uid_from_label(label):
    # Safe id for HTML element ids
    return "".join(ch for ch in label if ch.isalnum()).lower()

def main():
    if len(sys.argv) < 4:
        print("Usage: python json_to_html.py <input_json> <detailed_html_file> <summary_html_file> [report_html_abs_path]")
        sys.exit(1)

    input_json_file, detailed_html_file, summary_html_file = sys.argv[1:4]
    report_html_abs = sys.argv[4] if len(sys.argv) >= 5 else os.environ.get("SBMR_REPORT_HTML", "")

    with open(input_json_file, "r") as jf:
        data = json.load(jf)

    suites = data.get("test_results", [])
    suite_summary = data.get("suite_summary") or compute_suite_summary_from_results(suites)

    total_tests = (
        suite_summary.get("total_passed", 0)
        + suite_summary.get("total_failed", 0)
        + suite_summary.get("total_aborted", 0)
        + suite_summary.get("total_skipped", 0)
        + suite_summary.get("total_warnings", 0)
        + suite_summary.get("total_failed_with_waiver", 0)
    )
    chart_data = generate_bar_chart(suite_summary)

    label = friendly_label_from_filename(input_json_file)
    dataset = {
        "uid": uid_from_label(label),
        "label": label,
        "suites": suites,
        "summary": suite_summary,
        "chart_data": chart_data,
        "total_tests": total_tests,
    }

    page_title = label  # keep simple
    # If a report.html absolute path was provided, convert to a relative href from the detailed HTML dir
    report_link = None
    if report_html_abs:
        try:
            report_html_abs = os.path.abspath(report_html_abs)
            if os.path.exists(report_html_abs):
                detail_dir = os.path.dirname(os.path.abspath(detailed_html_file))
                report_link = os.path.relpath(report_html_abs, start=detail_dir).replace(os.sep, "/")
        except Exception:
            report_link = None

    render_detail_html(dataset, detailed_html_file, page_title, report_link)
    render_summary_html(suite_summary, summary_html_file, page_title)

if __name__ == "__main__":
    main()