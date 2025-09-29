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

import json, base64, os, sys
from io import BytesIO
from pathlib import Path
import matplotlib.pyplot as plt
from jinja2 import Template


def generate_bar_chart(summary_dict):
    labels = ["Passed", "Failed", "Failed with Waiver",
              "Aborted", "Skipped", "Warnings"]
    sizes = [
        summary_dict.get("total_passed", 0),
        summary_dict.get("total_failed", 0),
        summary_dict.get("total_failed_with_waiver", 0),
        summary_dict.get("total_aborted", 0),
        summary_dict.get("total_skipped", 0),
        summary_dict.get("total_warnings", 0),
    ]
    colors = ["#66bb6a", "#ef5350", "#f39c12",
              "#9e9e9e", "#ffc107", "#ffeb3b"]

    plt.figure(figsize=(12, 7))
    bars = plt.bar(labels, sizes, edgecolor="black", color=colors)

    total = sum(sizes)
    for bar in bars:
        pct = (bar.get_height() / total * 100) if total else 0
        plt.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + max(sizes) * 0.01,
                 f"{pct:.2f}%", ha="center", va="bottom", fontsize=12)

    plt.title("Test Results Distribution", fontsize=18, fontweight="bold")
    plt.ylabel("Total Count", fontsize=14)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ----------------------------- HTML builder ----------------------------- #
def build_html(overall_summary, test_results, chart_b64,
               dest_html, suite_name, summary_only=False):
    tmpl = Template("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{{ suite_name }} Test Summary</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;margin:20px;background:#f4f4f4;}
    h1,h2{color:#2c3e50;text-align:center;}
    table{width:100%;border-collapse:collapse;margin:20px 0;}
    th,td{padding:12px;border:1px solid #ddd;font-size:16px;}
    th{background:#3498db;color:#fff;font-weight:bold;text-align:left;}

    .pass{background:#d4edda;font-weight:bold;text-align:center;}
    .fail{background:#f8d7da;font-weight:bold;text-align:center;}
    .fail-waiver{background:#f39c12;font-weight:bold;text-align:center;}
    .aborted{background:#9e9e9e;font-weight:bold;text-align:center;}
    .skipped{background:#ffe0b2;font-weight:bold;text-align:center;}
    .warning{background:#fff3cd;font-weight:bold;text-align:center;}

    .summary-table{margin:0 auto;width:80%;}
    .summary-table td.total-tests{text-align:center;}
    .chart-container{display:flex;justify-content:center;}

    .result-summary,.detailed-summary{
        margin-top:40px;padding:20px;background:#fff;border-radius:10px;
        box-shadow:0 2px 10px rgba(0,0,0,0.1);}
    .result-summary h2{border-bottom:2px solid #27ae60;padding-bottom:10px;margin-bottom:20px;}

    .test-suite-header{font-size:22px;font-weight:bold;color:#34495e;margin-top:30px;}
    .waiver-reason{text-align:center;}
    .reason { text-align: center; }
  </style>
</head><body>
<h1>{{ suite_name }} Test Summary</h1>

{% if not summary_only %}
<div class="chart-container">
  <img src="data:image/png;base64,{{ chart_b64 }}" alt="Chart">
</div>
{% endif %}

<div class="result-summary">
  <h2>Result Summary</h2>
  <table class="summary-table">
    <tr><th>Status</th><th>Total</th></tr>
    <tr><td>Total Tests</td><td class="total-tests">{{ total_tests }}</td></tr>
    <tr><td>Passed</td><td class="pass">{{ total_passed }}</td></tr>
    <tr><td>Failed</td><td class="fail">{{ total_failed }}</td></tr>
    <tr><td>Failed with Waiver</td><td class="fail-waiver">{{ total_failed_with_waiver }}</td></tr>
    <tr><td>Aborted</td><td class="aborted">{{ total_aborted }}</td></tr>
    <tr><td>Skipped</td><td class="skipped">{{ total_skipped }}</td></tr>
    <tr><td>Warnings</td><td class="warning">{{ total_warnings }}</td></tr>
  </table>
</div>

{% if not summary_only %}
<div class="detailed-summary">
{% for suite in test_results %}
  <div class="test-suite-header">Test Suite: {{ suite.Test_suite }}</div>
  <table>
    <thead>
      <tr>
        <th>Sub Test Number</th><th>Description</th><th>Result</th><th>Reason</th><th>Waiver Reason</th>
      </tr>
    </thead>
    <tbody>
    {% for sub in suite.subtests %}
      <tr>
        <td>{{ sub.sub_Test_Number }}</td>
        <td>{{ sub.sub_Test_Description }}</td>
        <td class="{% if sub.sub_test_result=='PASSED' %}pass{% elif sub.sub_test_result=='FAILED (WITH WAIVER)' %}fail-waiver{% elif sub.sub_test_result=='FAILED' %}fail{% elif sub.sub_test_result=='ABORTED' %}aborted{% elif sub.sub_test_result=='SKIPPED' %}skipped{% else %}warning{% endif %}">
            {{ sub.sub_test_result }}
        </td>
        <td class="reason">{{ sub.reason | default('N/A') }}</td>
        <td class="waiver-reason">{{ sub.waiver_reason | default('N/A') }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
{% endfor %}
</div>
{% endif %}
</body></html>
""")

    tot_tests = (overall_summary["total_passed"] + overall_summary["total_failed"] +
                 overall_summary["total_aborted"] + overall_summary["total_skipped"] +
                 overall_summary["total_warnings"] + overall_summary["total_failed_with_waiver"])

    html = tmpl.render(
        suite_name=suite_name,
        chart_b64=chart_b64,
        test_results=test_results,
        summary_only=summary_only,
        total_tests=tot_tests,
        **overall_summary
    )

    Path(dest_html).write_text(html, encoding="utf-8")


# ----------------------------- main script ----------------------------- #
def main(inp_json, detailed_html, summary_html):
    data = json.loads(Path(inp_json).read_text())

    # everything except the last element (overall Suite_summary) are suites
    suites = data[:-1]

    for suite in suites:
        for sub in suite.get("subtests", []):
            if "waiver_reason" not in sub:
                sres = sub.get("sub_test_result")
                if isinstance(sres, dict) and "waiver_reason" in sres:
                    sub["waiver_reason"] = sres["waiver_reason"]

    # recompute overall counts (case-insensitive helper)
    def ci(d, k):
        return next((v for key, v in d.items() if key.lower() == k.lower()), 0)

    overall = dict.fromkeys(
        ["total_passed", "total_failed", "total_failed_with_waiver",
         "total_aborted", "total_skipped", "total_warnings"], 0)

    for suite in suites:
        smry = suite.get("test_suite_summary", {})
        overall["total_passed"]  += ci(smry, "total_passed")
        overall["total_failed"]  += ci(smry, "total_failed")
        overall["total_failed_with_waiver"] += ci(smry, "total_failed_with_waiver")
        overall["total_aborted"] += ci(smry, "total_aborted")
        overall["total_skipped"] += ci(smry, "total_skipped")
        overall["total_warnings"]+= ci(smry, "total_warnings")

    chart_b64 = generate_bar_chart(overall)

    suite_name = "PFDI"
    build_html(overall, suites, chart_b64, detailed_html, suite_name, summary_only=False)
    build_html(overall, suites, chart_b64, summary_html, suite_name, summary_only=True)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python PFDI_json_to_html.py <input_json> <detailed.html> <summary.html>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
