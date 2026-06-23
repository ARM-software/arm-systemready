#!/usr/bin/env python3
# Copyright (c) 2025-2026, Arm Limited or its affiliates. All rights reserved.
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

"""Generate BSA/SBSA HTML reports from parsed JSON results."""

import base64
import json
import os
import sys
from io import BytesIO

from jinja2 import Template
import matplotlib.pyplot as plt  # pylint: disable=import-error

# Helper function to retrieve dictionary values in a case-insensitive manner
def get_case_insensitive(data, key, default=0):
    """Return a dictionary value by key without requiring exact key casing."""
    for dict_key, value in data.items():
        if dict_key.lower() == key.lower():
            return value
    return default

def has_nested_subtests(subtests):
    """Return True when any subtest contains child subtests."""
    for subtest in subtests or []:
        child_subtests = subtest.get("subtests", [])
        if child_subtests or has_nested_subtests(child_subtests):
            return True
    return False

def annotate_nested_subtests(test_results):
    """Mark each testcase that needs expand/collapse controls in HTML."""
    for test_suite in test_results:
        for testcase in test_suite.get("testcases", []):
            testcase["has_nested_subtests"] = has_nested_subtests(
                testcase.get("subtests", [])
            )

# Function to generate bar chart for test results
def generate_bar_chart(suite_summary):
    """Build a base64 encoded bar chart image for suite summary counts."""
    labels = [
        'Passed',
        'Failed',
        'Failed with Waiver',
        'Aborted',
        'Skipped',
        'Warnings',
        'Passed (Partial)',
        'Not Implemented',
        'PAL Not Supported'
    ]
    sizes = [
        suite_summary.get('total_passed', 0),
        suite_summary.get('total_failed', 0),
        suite_summary.get('total_failed_with_waiver', 0),
        suite_summary.get('total_aborted', 0),
        suite_summary.get('total_skipped', 0),
        suite_summary.get('total_warnings', 0),
        suite_summary.get('total_passed_partial', 0),
        suite_summary.get('total_not_implemented', 0),
        suite_summary.get('total_pal_not_supported', 0)
    ]
    colors = [
        '#d4edda',  # Passed
        '#f8d7da',  # Failed
        '#f39c12',  # Failed with Waiver
        '#9e9e9e',  # Aborted
        '#ffe0b2',  # Skipped
        '#fff3cd',  # Warnings
        '#f8b88b',  # Passed (Partial)
        '#cfd8dc',  # Not Implemented
        '#aed6f1'   # PAL Not Supported
    ]  # Colors for each category

    plt.figure(figsize=(14, 7))
    bars = plt.bar(labels, sizes, color=colors, edgecolor='black')

    # Add percentage labels on top of the bars
    total_tests = suite_summary.get('total_rules_run', 0) or sum(sizes)
    for chart_bar, size in zip(bars, sizes):
        yval = chart_bar.get_height()
        percentage = (size / total_tests) * 100 if total_tests > 0 else 0
        plt.text(
            chart_bar.get_x() + chart_bar.get_width()/2,
            yval + max(sizes)*0.01,
            f'{percentage:.2f}%',
            ha='center',
            va='bottom',
            fontsize=12
        )

    plt.title('Test Results Distribution', fontsize=18, fontweight='bold')
    plt.ylabel('Total Count', fontsize=14)
    plt.xticks(fontsize=11, rotation=30, ha='right')
    plt.yticks(fontsize=12)
    plt.tight_layout()

    # Save the figure to a buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# Function to generate HTML content for both summary and detailed pages
def generate_html(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        suite_summary,
        test_results,
        chart_data,
        output_html_path,
        test_suite_name,
        is_summary_page=True):
    """Render either the detailed or summary BSA/SBSA HTML report."""
    annotate_nested_subtests(test_results)

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
            .fail-waiver {  /* CSS class for Failed with Waiver */
                background-color: #f39c12;
                font-weight: bold;
            }
            .warning {
                background-color: #fff3cd;
                font-weight: bold;
            }
            .passed-partial {
                background-color: #f8b88b;
                font-weight: bold;
            }
            .not-tested {
                background-color: #d7bde2;
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
            .test-suite-header {
                font-size: 22px;
                font-weight: bold;
                color: #34495e;
                margin-top: 30px;
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
            .not-implemented {
                background-color: #cfd8dc;
                font-weight: bold;
                text-align: center;
            }
            .pal-not-supported {
                background-color: #aed6f1;
                font-weight: bold;
                text-align: center;
            }
            .passed-partial {
                background-color: #f8b88b;
                font-weight: bold;
                text-align: center;
            }
            .not-tested {
                background-color: #d7bde2;
                font-weight: bold;
                text-align: center;
            }
            /* New CSS class for Waiver Reason */
            td.waiver-reason {
                text-align: center;
                font-weight: normal;
            }
            /* Keep rule numbers readable while indentation shows nesting. */
            .subtest-number {
                white-space: nowrap;
            }
            .testcase-toggle,
            .subtest-toggle,
            .subtest-control {
                border: 1px solid #6c7a89;
                cursor: pointer;
                font-weight: 600;
                transition: background-color 0.15s ease, border-color 0.15s ease,
                            box-shadow 0.15s ease, color 0.15s ease;
            }
            .testcase-toggle,
            .subtest-toggle {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 22px;
                height: 22px;
                margin-right: 8px;
                border-radius: 50%;
                background: #f7fbff;
                border-color: #6fa8dc;
                color: #1f5f99;
                font-family: Arial, sans-serif;
                font-size: 14px;
                line-height: 1;
                box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.08);
            }
            .testcase-toggle:hover,
            .subtest-toggle:hover {
                background: #e8f3ff;
                border-color: #2f80c7;
            }
            .testcase-toggle[aria-expanded="true"],
            .subtest-toggle[aria-expanded="true"] {
                background: #edf7ed;
                border-color: #58a55c;
                color: #256b2a;
            }
            .testcase-toggle[aria-expanded="false"],
            .subtest-toggle[aria-expanded="false"] {
                background: #fff7e6;
                border-color: #d89614;
                color: #8a5a00;
            }
            .testcase-toggle-placeholder,
            .subtest-toggle-placeholder {
                display: inline-block;
                width: 22px;
                height: 22px;
                margin-right: 8px;
            }
            .testcase-number {
                white-space: nowrap;
            }
            .subtest-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 8px;
            }
            .subtest-title {
                color: #2c3e50;
                font-weight: bold;
            }
            .subtest-controls {
                display: flex;
                flex-wrap: wrap;
                justify-content: flex-end;
                gap: 8px;
            }
            .subtest-control {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                line-height: 1.2;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
            }
            .expand-subtests {
                background: #2f80c7;
                border-color: #2878b5;
                color: #fff;
            }
            .expand-subtests:hover:not(:disabled) {
                background: #236a9f;
                border-color: #1f5f99;
            }
            .collapse-subtests {
                background: #fff;
                border-color: #9aa9b5;
                color: #2c3e50;
            }
            .collapse-subtests:hover:not(:disabled) {
                background: #eef3f7;
                border-color: #6c7a89;
            }
            .subtest-control:disabled {
                cursor: default;
                opacity: 0.45;
                box-shadow: none;
            }
            .control-symbol {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.25);
                font-weight: bold;
                line-height: 1;
            }
            .collapse-subtests .control-symbol {
                background: #edf2f7;
                color: #34495e;
            }
            .testcase-toggle:focus-visible,
            .subtest-toggle:focus-visible,
            .subtest-control:focus-visible {
                outline: 2px solid #1f77b4;
                outline-offset: 2px;
            }
            @media (max-width: 700px) {
                .subtest-header {
                    align-items: flex-start;
                    flex-direction: column;
                }
                .subtest-controls {
                    justify-content: flex-start;
                }
            }
            .subtest-row-hidden {
                display: none;
            }
        </style>
    </head>
    <body>
        {# Render BSA/SBSA subtests recursively so the HTML follows the same
           parent-child order as the JSON and original nested log. #}
        {% macro render_subtest_rows(subtests, parent_path='') %}
            {% for subtest in subtests %}
            {% set nesting_level = subtest.sub_Test_Level | default(1) | int %}
            {% set subtest_path = subtest.sub_Test_Path | default(subtest.sub_Test_Number) %}
            {% set has_children = subtest.subtests is defined and subtest.subtests %}
            {# The row tooltip contains the full sub_Test_Path for comparison
               with logs and for precise waiver targeting. #}
            <tr class="subtest-row" title="{{ subtest_path }}" data-path="{{ subtest_path }}" data-parent="{{ parent_path }}">
                <td class="subtest-number" style="padding-left: {{ 12 + ((nesting_level - 1) * 24) }}px;">
                    {% if has_children %}
                    <button type="button" class="subtest-toggle" aria-expanded="true" aria-label="Collapse nested subtests" title="Collapse nested subtests">-</button>
                    {% else %}
                    <span class="subtest-toggle-placeholder"></span>
                    {% endif %}
                    {{ subtest.sub_Test_Number }}
                </td>
                <td>{{ subtest.sub_Test_Description }}</td>
                <td class="{% if subtest.sub_test_result == 'PASSED' %}pass{% elif subtest.sub_test_result == 'FAILED (WITH WAIVER)' %}fail-waiver{% elif subtest.sub_test_result == 'FAILED' %}fail{% elif subtest.sub_test_result == 'WARNING' %}warning{% elif 'PASSED(*PARTIAL)' in subtest.sub_test_result %}passed-partial{% elif subtest.sub_test_result == 'SKIPPED' %}skipped{% elif subtest.sub_test_result in ['PAL NOT SUPPORTED', 'NOT TESTED (PAL NOT SUPPORTED)'] %}pal-not-supported{% elif subtest.sub_test_result in ['TEST NOT IMPLEMENTED', 'NOT TESTED (TEST NOT IMPLEMENTED)'] %}not-implemented{% elif 'NOT TESTED' in subtest.sub_test_result %}not-tested{% endif %}">
                    {{ subtest.sub_test_result }}
                </td>
                <td class="waiver-reason">
                    {% if 'FAILED (WITH WAIVER)' in subtest.sub_test_result %}
                        {{ subtest.waiver_reason | default("N/A") }}
                    {% else %}
                        N/A
                    {% endif %}
                </td>
            </tr>
            {% if has_children %}
                {# Child rows are printed immediately after their parent with
                   additional indentation from sub_Test_Level. #}
                {{ render_subtest_rows(subtest.subtests, subtest_path) }}
            {% endif %}
            {% endfor %}
        {% endmacro %}
        <h1>{{ test_suite_name }} Test Summary</h1>

        {% if not is_summary_page %}
        <div class="chart-container">
            <img src="data:image/png;base64,{{ chart_data }}" alt="Test Results Distribution">
        </div>
        {% endif %}

        <div class="result-summary">
            <h2>Result Summary</h2>
            {% if not is_summary_page %}
            <p style="text-align: center; font-weight: bold;">
                For details on Rule Results Status, refer to -
                <br>
                <a href="https://github.com/ARM-software/sysarch-acs/blob/main/docs/common/RuleBasedGuide.md#rule-status-in-logs" target="_blank" rel="noopener noreferrer">https://github.com/ARM-software/sysarch-acs/blob/main/docs/common/RuleBasedGuide.md#rule-status-in-logs</a>
            </p>
            {% endif %}
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
                    <tr>
                        <td>Passed (Partial)</td>
                        <td class="passed-partial">{{ total_passed_partial }}</td>
                    </tr>
                    <tr>
                        <td>Not Implemented</td>
                        <td class="not-implemented">{{ total_not_implemented }}</td>
                    </tr>
                    <tr>
                        <td>PAL Not Supported</td>
                        <td class="pal-not-supported">{{ total_pal_not_supported }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        {% if not is_summary_page %}
            <div class="detailed-summary">
            {% for test in test_results %}
            {% set suite_index = loop.index0 %}
            <div class="test-suite-header">Test Suite: {{ test.Test_suite }}</div>
            <table>
                <thead>
                    <tr>
                        <th>Test Case</th>
                        <th>Test Case Description</th>
                        <th>Test Result</th>
                        <th>Waiver Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {% for testcase in test.testcases %}
                    {% set subtest_table_id = "subtests-" ~ suite_index ~ "-" ~ loop.index0 %}
                    <tr>
                        <td class="testcase-number">
                            {% if testcase.subtests %}
                            <button type="button" class="testcase-toggle" aria-expanded="true" aria-controls="{{ subtest_table_id }}-row" aria-label="Collapse subtests" title="Collapse subtests">-</button>
                            {% else %}
                            <span class="testcase-toggle-placeholder"></span>
                            {% endif %}
                            {{ testcase.Test_case }}
                        </td>
                        <td>{{ testcase.Test_case_description }}</td>
                        <td class="{% if testcase.Test_result == 'PASSED' %}pass{% elif testcase.Test_result == 'FAILED (WITH WAIVER)' %}fail-waiver{% elif testcase.Test_result == 'FAILED' %}fail{% elif testcase.Test_result == 'WARNING' %}warning{% elif 'PASSED(*PARTIAL)' in testcase.Test_result %}passed-partial{% elif testcase.Test_result == 'SKIPPED' %}skipped{% elif testcase.Test_result in ['PAL NOT SUPPORTED', 'NOT TESTED (PAL NOT SUPPORTED)'] %}pal-not-supported{% elif testcase.Test_result in ['TEST NOT IMPLEMENTED', 'NOT TESTED (TEST NOT IMPLEMENTED)'] %}not-implemented{% elif 'NOT TESTED' in testcase.Test_result %}not-tested{% endif %}">
                            {{ testcase.Test_result }}
                        </td>
                        <td class="waiver-reason">
                            {% if 'FAILED (WITH WAIVER)' in testcase.Test_result %}
                                {{ testcase.waiver_reason | default("N/A") }}
                            {% else %}
                                N/A
                            {% endif %}
                        </td>
                    </tr>
                    {% if testcase.subtests %}
                    <tr id="{{ subtest_table_id }}-row" style="background-color: #f9f9f9;">
                        <td colspan="4">
                            <div class="subtest-header">
                                <span class="subtest-title">Subtests:</span>
                                {% if testcase.has_nested_subtests %}
                                <div class="subtest-controls" aria-label="Nested subtest display controls">
                                    <button type="button" class="subtest-control expand-subtests" data-table-id="{{ subtest_table_id }}" title="Show every nested row in this testcase">
                                        <span class="control-symbol">+</span>
                                        <span>Expand all</span>
                                    </button>
                                    <button type="button" class="subtest-control collapse-subtests" data-table-id="{{ subtest_table_id }}" title="Hide nested rows and keep top-level subtests visible">
                                        <span class="control-symbol">-</span>
                                        <span>Collapse all</span>
                                    </button>
                                </div>
                                {% endif %}
                            </div>
                            <table id="{{ subtest_table_id }}" class="subtest-table" style="width: 100%; margin-top: 10px;">
                                <thead>
                                    <tr style="background-color: #ecf0f1;">
                                        <th>Sub Test Number</th>
                                        <th>Sub Test Description</th>
                                        <th>Sub Test Result</th>
                                        <th>Waiver Reason</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {{ render_subtest_rows(testcase.subtests) }}
                                </tbody>
                            </table>
                        </td>
                    </tr>
                    {% endif %}
                    {% endfor %}
                </tbody>
            </table>
            {% endfor %}
        </div>
        {% endif %}
        <script>
            (function () {
                function hasClass(element, className) {
                    return element && element.classList && element.classList.contains(className);
                }

                function closestElement(element, matcher) {
                    while (element && element.nodeType === 1) {
                        if (matcher(element)) {
                            return element;
                        }
                        element = element.parentElement;
                    }
                    return null;
                }

                function getChildRows(row) {
                    var table = closestElement(row, function (element) {
                        return element.tagName === 'TABLE' && hasClass(element, 'subtest-table');
                    });
                    if (!table) {
                        return [];
                    }

                    // Each row stores its full sub_Test_Path. Children point to
                    // their parent path, so lookup works at any nesting depth.
                    var path = row.getAttribute('data-path');
                    return Array.prototype.filter.call(
                        table.querySelectorAll('tr.subtest-row'),
                        function (candidate) {
                            return candidate.getAttribute('data-parent') === path;
                        }
                    );
                }

                function getTableControls(table) {
                    var holder = table ? table.parentElement : null;
                    if (!holder) {
                        return {};
                    }
                    return {
                        expand: holder.querySelector('.expand-subtests'),
                        collapse: holder.querySelector('.collapse-subtests')
                    };
                }

                function syncTableControls(table) {
                    var controls = getTableControls(table);
                    if (!controls.expand || !controls.collapse) {
                        return;
                    }

                    var hideableRows = table.querySelectorAll(
                        'tr.subtest-row[data-parent]:not([data-parent=""])'
                    );
                    var hiddenRows = table.querySelectorAll('tr.subtest-row-hidden');
                    controls.expand.disabled = hiddenRows.length === 0;
                    controls.collapse.disabled = (
                        hideableRows.length > 0 && hiddenRows.length === hideableRows.length
                    );
                }

                function setToggleState(button, expanded) {
                    var isTestcaseToggle = hasClass(button, 'testcase-toggle');
                    button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                    button.setAttribute(
                        'aria-label',
                        expanded ? 'Collapse subtests' : 'Expand subtests'
                    );
                    button.setAttribute(
                        'title',
                        isTestcaseToggle
                            ? (expanded ? 'Collapse subtests' : 'Expand subtests')
                            : (expanded ? 'Collapse nested subtests' : 'Expand nested subtests')
                    );
                    button.textContent = expanded ? '-' : '+';
                }

                function setTestcaseExpanded(button, expanded) {
                    var controlledRow = document.getElementById(
                        button.getAttribute('aria-controls')
                    );
                    if (!controlledRow) {
                        return;
                    }
                    controlledRow.classList.toggle('subtest-row-hidden', !expanded);
                    setToggleState(button, expanded);
                }

                function hideDescendants(row) {
                    getChildRows(row).forEach(function (childRow) {
                        childRow.classList.add('subtest-row-hidden');
                        var childToggle = childRow.querySelector('.subtest-toggle');
                        if (childToggle) {
                            setToggleState(childToggle, false);
                        }
                        hideDescendants(childRow);
                    });
                }

                function showChildren(row) {
                    getChildRows(row).forEach(function (childRow) {
                        childRow.classList.remove('subtest-row-hidden');
                        var childToggle = childRow.querySelector('.subtest-toggle');
                        if (childToggle && childToggle.getAttribute('aria-expanded') === 'true') {
                            showChildren(childRow);
                        }
                    });
                }

                function setRowExpanded(row, expanded) {
                    if (!row) {
                        return;
                    }
                    var toggle = row.querySelector('.subtest-toggle');
                    if (toggle) {
                        setToggleState(toggle, expanded);
                    }

                    if (expanded) {
                        showChildren(row);
                    } else {
                        hideDescendants(row);
                    }

                    syncTableControls(closestElement(row, function (element) {
                        return element.tagName === 'TABLE' && hasClass(element, 'subtest-table');
                    }));
                }

                function setTableExpanded(table, expanded) {
                    if (!table) {
                        return;
                    }
                    // Expand/collapse all works inside one testcase table. This
                    // keeps controls from one testcase from changing another.
                    var rows = Array.prototype.slice.call(table.querySelectorAll('tr.subtest-row'));
                    rows.forEach(function (row) {
                        row.classList.remove('subtest-row-hidden');
                        var toggle = row.querySelector('.subtest-toggle');
                        if (toggle) {
                            setToggleState(toggle, expanded);
                        }
                    });

                    if (!expanded) {
                        rows.forEach(function (row) {
                            if (row.getAttribute('data-parent')) {
                                row.classList.add('subtest-row-hidden');
                            }
                        });
                    }
                    syncTableControls(table);
                }

                Array.prototype.forEach.call(
                    document.querySelectorAll('table.subtest-table'),
                    syncTableControls
                );

                document.addEventListener('click', function (event) {
                    // One delegated handler covers every generated subtest row
                    // and the per-testcase Expand all / Collapse all buttons.
                    var button = closestElement(event.target, function (element) {
                        return element.tagName === 'BUTTON';
                    });
                    if (!button) {
                        return;
                    }

                    if (hasClass(button, 'testcase-toggle')) {
                        setTestcaseExpanded(
                            button,
                            button.getAttribute('aria-expanded') !== 'true'
                        );
                    } else if (hasClass(button, 'subtest-toggle')) {
                        var row = closestElement(button, function (element) {
                            return element.tagName === 'TR' && hasClass(element, 'subtest-row');
                        });
                        var expanded = button.getAttribute('aria-expanded') === 'true';
                        setRowExpanded(row, !expanded);
                    } else if (hasClass(button, 'expand-subtests')) {
                        setTableExpanded(
                            document.getElementById(button.getAttribute('data-table-id')),
                            true
                        );
                    } else if (hasClass(button, 'collapse-subtests')) {
                        setTableExpanded(
                            document.getElementById(button.getAttribute('data-table-id')),
                            false
                        );
                    }
                });
            }());
        </script>
    </body>
    </html>
    """)

    # Calculate total_failed_with_waiver by summing from each test suite
    total_failed_with_waiver = 0
    for test_suite in test_results:
        ts_summary = test_suite.get('test_suite_summary', {})
        # Try both field name variations
        total_failed_with_waiver += get_case_insensitive(ts_summary, 'Total_failed_with_waiver',
                                   get_case_insensitive(ts_summary, 'total_failed_with_waiver', 0))

    # Calculate total tests
    # Calculate total tests from suite_summary's Total Rules Run
    total_tests = suite_summary.get("total_rules_run", 0)
    if total_tests == 0:
        # Fallback: sum all categories if Total Rules Run is not present
        total_tests = (
            suite_summary.get("total_passed", 0)
            + suite_summary.get("total_failed", 0)
            + suite_summary.get("total_aborted", 0)
            + suite_summary.get("total_skipped", 0)
            + suite_summary.get("total_warnings", 0)
            + suite_summary.get("total_failed_with_waiver", 0)
            + suite_summary.get("total_not_implemented", 0)
            + suite_summary.get("total_pal_not_supported", 0)
            + suite_summary.get("total_passed_partial", 0)
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
        total_passed_partial=suite_summary.get("total_passed_partial", 0),
        total_not_implemented=suite_summary.get("total_not_implemented", 0),
        total_pal_not_supported=suite_summary.get("total_pal_not_supported", 0),
        test_results=test_results,
        is_summary_page=is_summary_page,
        test_suite_name=test_suite_name.upper()  # Ensure uppercase for consistency
    )

    # Save to HTML file
    with open(output_html_path, "w", encoding="utf-8") as file:
        file.write(html_content)

# Main function to process the JSON file and generate the HTML report
def main(input_json_file, detailed_html_file, summary_html_file):
    """Load parsed JSON and generate detailed and summary HTML files."""
    # Load JSON data
    with open(input_json_file, 'r', encoding="utf-8") as json_file:
        data = json.load(json_file)

    # Extract the test results
    test_results = data.get("test_results", [])

    # Use the top-level suite_summary from JSON which has the correct totals
    suite_summary_from_json = data.get("suite_summary", {})

    # Build summary with proper field mapping from JSON
    suite_summary = {
        'total_passed': suite_summary_from_json.get('Passed', 0),
        'total_failed': suite_summary_from_json.get('Failed', 0),
        'total_failed_with_waiver': suite_summary_from_json.get('Total_failed_with_waiver', 0),
        'total_aborted': suite_summary_from_json.get('Aborted', 0),
        'total_skipped': suite_summary_from_json.get('Skipped', 0),
        'total_warnings': suite_summary_from_json.get('Warnings', 0),
        'total_not_implemented': suite_summary_from_json.get('Not Implemented', 0),
        'total_pal_not_supported': suite_summary_from_json.get('PAL Not Supported', 0),
        'total_passed_partial': suite_summary_from_json.get('Passed (Partial)', 0),
        'total_rules_run': suite_summary_from_json.get('Total Rules Run', 0)
    }

    # Get the test suite name from the input JSON file name
    test_suite_name = os.path.splitext(
        os.path.basename(input_json_file)
    )[0].upper()

    # Generate bar chart
    chart_data = generate_bar_chart(suite_summary)

    # Generate the detailed summary page
    generate_html(
        suite_summary,
        test_results,
        chart_data,
        detailed_html_file,
        test_suite_name,
        is_summary_page=False
    )

    # Generate the summary page with the bar chart
    generate_html(
        suite_summary,
        test_results,
        chart_data,
        summary_html_file,
        test_suite_name,
        is_summary_page=True
    )

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Usage: python json_to_html.py <input_json_file> "
            "<detailed_html_file> <summary_html_file>"
        )
        sys.exit(1)

    input_path = sys.argv[1]
    detailed_path = sys.argv[2]  # This will be the detailed HTML report
    summary_path = sys.argv[3]  # This will be the summary HTML report

    main(input_path, detailed_path, summary_path)
