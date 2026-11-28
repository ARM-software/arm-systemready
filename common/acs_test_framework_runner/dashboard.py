#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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


"""Generate a static HTML dashboard from YAML runner report artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import xml.etree.ElementTree as xml_et
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # Support package imports and direct harness module loading.
    from .change_coverage import load_change_coverage_artifact, stronger_status
    from .runner_checks import detect_project_root, sanitize_name, target_work_name
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from change_coverage import load_change_coverage_artifact, stronger_status
    from runner_checks import detect_project_root, sanitize_name, target_work_name


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
REPORTS_DIR = PROJECT_ROOT / "common" / "reports"
LAST_RUN_REPORTS_DIR = PROJECT_ROOT / "common" / "reports_last_run"
DEFAULT_DASHBOARD_PATH = REPORTS_DIR / "dashboard.html"
EXCLUDED_XML_REPORTS = {"pytest-placeholder.xml", "pylint-report.xml", "mypy-report.xml"}
CASE_LOG_PATTERN = re.compile(r"(?m)^TEST CASE:\s*(?P<name>.+?)\s*$")


@dataclass(slots=True)
class DashboardWriteOptions:
    """Bundle optional inputs used to build the dashboard output."""

    reports_dir: Path = REPORTS_DIR
    generated_at: str | None = None
    case_logs: list[dict[str, str]] | None = None
    testgap_hints: Any = None
    previous_reports_dir: Path | None = None


DASHBOARD_CSS = """
:root {
    --acs-bg: #f3f6fb;
    --acs-panel: #ffffff;
    --acs-panel-muted: #f8fafc;
    --acs-text: #172033;
    --acs-heading: #102a4c;
    --acs-muted: #667085;
    --acs-line: #d8e1ed;
    --acs-brand: #163b68;
    --acs-brand-strong: #0f2c50;
    --acs-brand-soft: #edf4ff;
    --acs-shadow: 0 8px 26px rgba(16, 42, 76, .07);
    --acs-pass-bg: #dcfce7;
    --acs-pass-text: #166534;
    --acs-fail-bg: #fee2e2;
    --acs-fail-text: #991b1b;
    --acs-warn-bg: #ffedd5;
    --acs-warn-text: #9a3412;
    --acs-info-bg: #e8efff;
    --acs-info-text: #344e7a;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body.acs-report-ui {
    margin: 0;
    padding: 24px;
    background: var(--acs-bg);
    color: var(--acs-text);
    font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    line-height: 1.45;
}
body.acs-report-ui > * {
    max-width: 1540px;
    margin-left: auto;
    margin-right: auto;
}
.header {
    padding: 22px 26px;
    margin-bottom: 16px;
    border-radius: 16px;
    background: linear-gradient(118deg, var(--acs-brand-strong), var(--acs-brand));
    box-shadow: var(--acs-shadow);
    color: #fff;
}
.header h1 {
    margin: 0 0 6px;
    font-size: 28px;
    letter-spacing: -.02em;
}
.header p {
    margin: 0;
    color: rgba(255, 255, 255, .86);
}
.container {
    display: grid;
    gap: 18px;
}
.panel {
    background: var(--acs-panel);
    border: 1px solid var(--acs-line);
    border-radius: 16px;
    box-shadow: var(--acs-shadow);
    padding: 20px;
}
.panel h2 {
    margin: 0 0 14px;
    color: var(--acs-heading);
    font-size: 19px;
}
.panel h3 {
    margin: 0 0 10px;
    color: var(--acs-heading);
    font-size: 16px;
}
.acs-toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: end;
    margin-bottom: 16px;
    padding: 16px;
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
    border-radius: 14px;
}
.acs-control {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 260px;
}
.acs-control-label {
    color: var(--acs-muted);
    font-size: 11px;
    font-weight: 700;
}
.acs-control select {
    width: 100%;
    min-height: 36px;
    padding: 7px 10px;
    color: var(--acs-text);
    background: #fff;
    border: 1px solid var(--acs-line);
    border-radius: 9px;
}
.target-picker-summary {
    color: var(--acs-muted);
    font-size: 12px;
    font-weight: 650;
}
.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
}
.stat-card {
    padding: 16px;
    border-radius: 14px;
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
}
.stat-card .label {
    display: block;
    margin-bottom: 6px;
    color: var(--acs-muted);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
}
.stat-card .value {
    color: var(--acs-heading);
    font-size: 28px;
    font-weight: 780;
}
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 14px;
}
.meta-list,
.simple-list {
    margin: 0;
    padding-left: 18px;
}
.meta-list li,
.simple-list li {
    margin: 6px 0;
}
.target-card {
    border: 1px solid var(--acs-line);
    border-radius: 14px;
    background: var(--acs-panel-muted);
    padding: 16px;
}
.target-card + .target-card {
    margin-top: 14px;
}
.target-card-hidden {
    display: none;
}
.target-card-header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 12px;
}
.target-card-header code {
    font-size: 13px;
}
.target-card-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}
.target-log-links,
.target-status-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.target-status-filter {
    min-height: 32px;
    padding: 6px 10px;
    cursor: pointer;
    color: var(--acs-muted);
    background: #fff;
    border: 1px solid var(--acs-line);
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}
.target-status-filter[aria-pressed="true"][data-status-kind="all"] {
    color: var(--acs-heading);
    background: var(--acs-brand-soft);
    border-color: #bfd3f2;
}
.target-status-filter[aria-pressed="true"][data-status-kind="passed"] {
    color: var(--acs-pass-text);
    background: var(--acs-pass-bg);
    border-color: #86efac;
}
.target-status-filter[aria-pressed="true"][data-status-kind="failed"],
.target-status-filter[aria-pressed="true"][data-status-kind="error"] {
    color: var(--acs-fail-text);
    background: var(--acs-fail-bg);
    border-color: #fca5a5;
}
.target-status-filter[aria-pressed="true"][data-status-kind="warning"] {
    color: var(--acs-warn-text);
    background: var(--acs-warn-bg);
    border-color: #fdba74;
}
.target-filter-empty {
    margin-top: 12px;
}
.manifest-sections {
    display: grid;
    gap: 12px;
    margin-top: 14px;
}
.manifest-section {
    border: 1px solid var(--acs-line);
    border-radius: 14px;
    background: var(--acs-panel);
    overflow: hidden;
}
.manifest-section summary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 14px 16px;
    cursor: pointer;
    list-style: none;
    background: var(--acs-panel-muted);
}
.manifest-section summary::-webkit-details-marker {
    display: none;
}
.manifest-section summary::after {
    content: "+";
    color: var(--acs-muted);
    font-size: 18px;
    font-weight: 700;
}
.manifest-section[open] summary::after {
    content: "-";
}
.manifest-section-title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    min-width: 0;
}
.manifest-section-title code {
    font-size: 13px;
}
.manifest-section-body {
    padding: 0 16px 16px;
}
.comparison-note {
    margin: 0 0 14px;
    color: var(--acs-muted);
}
.coverage-function-list {
    margin: 0;
    padding-left: 18px;
}
.coverage-function-list li {
    margin: 10px 0;
}
.coverage-case-links {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 6px;
}
.comparison-panel {
    display: grid;
    gap: 16px;
}
.comparison-overview {
    padding: 16px 18px;
    border: 1px solid #cfe0f6;
    border-radius: 14px;
    background: linear-gradient(180deg, #f9fbff 0%, var(--acs-brand-soft) 100%);
}
.comparison-overview .comparison-note {
    margin-bottom: 0;
}
.comparison-kicker {
    margin: 0 0 8px;
    color: var(--acs-brand);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
}
.comparison-detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 14px;
    align-items: start;
}
.comparison-block {
    min-width: 0;
    padding: 16px;
    border: 1px solid var(--acs-line);
    border-radius: 14px;
    background: var(--acs-panel-muted);
}
.comparison-block-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
}
.comparison-block-header h3,
.comparison-block > h3 {
    margin: 0;
}
.comparison-block .comparison-note,
.comparison-block .muted,
.comparison-block .empty-state,
.comparison-block .meta-list,
.comparison-block .simple-list,
.comparison-block .comparison-case-list {
    margin-top: 0;
}
.comparison-block-wide {
    padding: 18px;
}
.comparison-case-list li {
    margin: 10px 0;
}
.comparison-case-list {
    list-style: none;
    padding-left: 0;
}
.comparison-statuses {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
}
.comparison-flow-arrow {
    color: var(--acs-muted);
    font-weight: 700;
}
.incident-grid,
.attention-grid,
.cluster-grid {
    display: grid;
    gap: 14px;
}
.incident-grid {
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.attention-grid,
.cluster-grid {
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}
.incident-card,
.attention-card,
.cluster-card,
.comparison-drawer {
    border: 1px solid var(--acs-line);
    border-radius: 14px;
    background: var(--acs-panel-muted);
    padding: 16px;
}
.incident-card h3,
.attention-card h3,
.cluster-card h3 {
    margin-bottom: 8px;
}
.incident-brief {
    margin: 0;
    padding-left: 18px;
}
.incident-brief li {
    margin: 6px 0;
}
.attention-card {
    display: grid;
    gap: 10px;
}
.attention-card-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}
.attention-card-title a,
.cluster-targets a,
.comparison-jump-link {
    color: #175cd3;
    text-decoration: none;
    font-weight: 650;
}
.attention-card-title a:hover,
.cluster-targets a:hover,
.comparison-jump-link:hover {
    text-decoration: underline;
}
.cluster-card {
    display: grid;
    gap: 10px;
}
.cluster-meta,
.cluster-targets,
.comparison-artifacts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.comparison-message-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
}
.cluster-sample-cases,
.comparison-artifact-list {
    margin: 0;
    padding-left: 18px;
}
.cluster-sample-cases li,
.comparison-artifact-list li {
    margin: 6px 0;
}
.comparison-drawer {
    padding: 0;
    overflow: hidden;
}
.comparison-drawer summary {
    list-style: none;
    cursor: pointer;
    padding: 16px;
}
.comparison-drawer summary::-webkit-details-marker {
    display: none;
}
.comparison-drawer summary::after {
    content: "+";
    float: right;
    color: var(--acs-muted);
    font-weight: 700;
}
.comparison-drawer[open] summary::after {
    content: "-";
}
.comparison-drawer-body {
    padding: 0 16px 16px;
    border-top: 1px solid var(--acs-line);
}
.comparison-drawer-top {
    display: grid;
    gap: 4px;
}
.comparison-message-box {
    border: 1px solid var(--acs-line);
    border-radius: 12px;
    background: var(--acs-panel);
    padding: 12px;
}
.comparison-message-box h4 {
    margin: 0 0 8px;
    color: var(--acs-heading);
    font-size: 13px;
}
.comparison-message-box pre {
    margin: 0;
    white-space: pre-wrap;
    overflow: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
}
.comparison-inline-note {
    color: var(--acs-muted);
    font-size: 12px;
}
.comparison-section-spacer {
    margin-top: 14px;
}
.badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.status-chip {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 760;
}
.status-passed { background: var(--acs-pass-bg); color: var(--acs-pass-text); }
.status-failed,
.status-error { background: var(--acs-fail-bg); color: var(--acs-fail-text); }
.status-warning,
.status-review { background: var(--acs-warn-bg); color: var(--acs-warn-text); }
.status-covered,
.status-likely { background: var(--acs-info-bg); color: var(--acs-info-text); }
.status-not-applicable { background: var(--acs-panel-muted); color: var(--acs-muted); }
.table-wrap {
    overflow-x: auto;
}
.report-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--acs-panel);
    border-radius: 12px;
    overflow: hidden;
}
.report-table th,
.report-table td {
    padding: 12px 14px;
    text-align: left;
    border-bottom: 1px solid var(--acs-line);
    vertical-align: top;
}
.report-table th {
    background: var(--acs-brand-soft);
    color: var(--acs-heading);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .07em;
}
.report-table tr:last-child td {
    border-bottom: none;
}
.log-links {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}
.case-details summary {
    cursor: pointer;
    color: #175cd3;
    font-weight: 650;
}
.case-details pre {
    margin: 10px 0 0;
    padding: 12px;
    overflow: auto;
    white-space: pre-wrap;
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
    border-radius: 10px;
}
.case-name {
    font-weight: 650;
}
.case-description,
.muted {
    color: var(--acs-muted);
}
.empty-state {
    padding: 28px;
    border: 1px dashed var(--acs-line);
    border-radius: 14px;
    background: var(--acs-panel-muted);
    color: var(--acs-muted);
}
.testgap-list {
    display: grid;
    gap: 10px;
}
.testgap-item {
    border: 1px solid var(--acs-line);
    border-radius: 12px;
    background: var(--acs-panel);
    padding: 12px 14px;
}
.testgap-item strong {
    color: var(--acs-heading);
}
.testgap-item ul {
    margin: 8px 0 0;
    padding-left: 18px;
}
code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
"""


DASHBOARD_SCRIPT = """
document.addEventListener("DOMContentLoaded", function () {
    var cards = Array.prototype.slice.call(
        document.querySelectorAll("[data-dashboard-target-card]")
    );

    function bindTargetStatusFilters(card) {
        var buttons = Array.prototype.slice.call(
            card.querySelectorAll("[data-target-status-filter]")
        );
        if (!buttons.length) {
            return;
        }

        var rows = Array.prototype.slice.call(card.querySelectorAll("[data-case-row]"));
        var sections = Array.prototype.slice.call(card.querySelectorAll("[data-manifest-section]"));
        var empty = card.querySelector("[data-target-filter-empty]");

        function applyStatusFilter(status) {
            var visibleCount = 0;
            rows.forEach(function (row) {
                var matches = status === "all" || row.getAttribute("data-case-status") === status;
                row.hidden = !matches;
                if (matches) {
                    visibleCount += 1;
                }
            });

            sections.forEach(function (section) {
                var sectionRows = Array.prototype.slice.call(section.querySelectorAll("[data-case-row]"));
                var sectionVisibleCount = sectionRows.filter(function (row) {
                    return !row.hidden;
                }).length;
                section.hidden = sectionVisibleCount === 0;
            });

            buttons.forEach(function (button) {
                button.setAttribute(
                    "aria-pressed",
                    button.getAttribute("data-status-value") === status ? "true" : "false"
                );
            });

            if (empty) {
                empty.hidden = visibleCount > 0;
            }
        }

        buttons.forEach(function (button) {
            button.addEventListener("click", function () {
                applyStatusFilter(button.getAttribute("data-status-value") || "all");
            });
        });

        applyStatusFilter("all");
    }

    cards.forEach(bindTargetStatusFilters);

    var select = document.querySelector("[data-dashboard-target-select]");
    if (!select) {
        return;
    }

    var count = document.querySelector("[data-dashboard-target-count]");
    var empty = document.querySelector("[data-dashboard-target-empty]");

    function updateCount(visibleCount, totalCount, selectedTarget) {
        if (!count) {
            return;
        }
        if (!selectedTarget) {
            count.textContent = "Showing all " + visibleCount + " targets";
            return;
        }
        count.textContent = "Showing 1 of " + totalCount + " targets";
    }

    function applyTargetFilter(scrollIntoView) {
        var selectedTarget = select.value;
        var visibleCount = 0;
        var firstVisibleCard = null;

        cards.forEach(function (card) {
            var matches = !selectedTarget || card.getAttribute("data-target") === selectedTarget;
            card.hidden = !matches;
            card.classList.toggle("target-card-hidden", !matches);
            if (matches) {
                visibleCount += 1;
                if (!firstVisibleCard) {
                    firstVisibleCard = card;
                }
            }
        });

        if (empty) {
            empty.hidden = visibleCount > 0;
        }

        updateCount(visibleCount, cards.length, selectedTarget);

        if (selectedTarget && firstVisibleCard) {
            history.replaceState(null, "", "#" + firstVisibleCard.id);
            if (scrollIntoView) {
                firstVisibleCard.scrollIntoView({behavior: "smooth", block: "start"});
            }
        } else if (!selectedTarget && location.hash) {
            history.replaceState(null, "", location.pathname + location.search);
        }
    }

    var currentHash = window.location.hash.replace(/^#/, "");
    if (currentHash) {
        var targetCard = document.getElementById(currentHash);
        if (targetCard && targetCard.hasAttribute("data-target")) {
            select.value = targetCard.getAttribute("data-target");
        }
    }

    select.addEventListener("change", function () {
        applyTargetFilter(true);
    });

    applyTargetFilter(false);
});
"""

def iter_runner_xml_reports(reports_dir: Path) -> list[Path]:
    """Return sorted runner XML reports from the reports directory."""
    if not reports_dir.exists():
        return []

    return sorted(
        path
        for path in reports_dir.glob("*.xml")
        if path.is_file() and path.name not in EXCLUDED_XML_REPORTS
    )

def infer_target_from_testcase_name(testcase_name: str) -> str:
    """Extract the target path from a pytest-style test case name."""
    parts = testcase_name.split("::")
    if len(parts) >= 2 and parts[1].strip():
        return parts[1].strip()
    return ""

def testcase_status(testcase: xml_et.Element) -> tuple[str, str, str]:
    """Return the normalized status, message, and details for a JUnit testcase."""
    error_node = testcase.find("error")
    failure_node = testcase.find("failure")
    skipped_node = testcase.find("skipped")

    if error_node is not None:
        return "error", error_node.get("message", ""), (error_node.text or "").strip()
    if failure_node is not None:
        return "failed", failure_node.get("message", ""), (failure_node.text or "").strip()
    if skipped_node is not None:
        return "warning", skipped_node.get("message", ""), (skipped_node.text or "").strip()

    system_out = testcase.find("system-out")
    return "passed", "Passed", (system_out.text or "").strip() if system_out is not None else ""


def parse_junit_report(xml_path: Path) -> dict[str, Any]:
    """Parse one JUnit XML report into dashboard-friendly case metadata."""
    root = xml_et.parse(xml_path).getroot()
    properties = {
        prop.get("name", ""): prop.get("value", "")
        for prop in root.findall("./properties/property")
    }

    manifest = properties.get("yaml_file", "")
    suite_name = root.get("name", xml_path.stem)
    cases: list[dict[str, Any]] = []

    for testcase in root.findall("testcase"):
        status, message, details = testcase_status(testcase)
        case_name = testcase.get("name", "")
        target = testcase.get("file", "") or infer_target_from_testcase_name(case_name)
        cases.append(
            {
                "name": case_name,
                "target": target,
                "status": status,
                "message": message,
                "details": details,
                "manifest": manifest,
                "suite_name": suite_name,
                "description": "",
            }
        )

    return {
        "manifest": manifest,
        "suite_name": suite_name,
        "cases": cases,
        "xml_report": xml_path,
    }

def build_case_log_index(
    case_logs: list[dict[str, str]],
    cases: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, str]]:
    """Index logs by full case identity, rejecting ambiguous legacy records."""
    identities_by_name: dict[str, list[tuple[str, str, str]]] = {}
    for case in cases:
        identity = build_case_identity(case)
        identities_by_name.setdefault(identity[2], []).append(identity)

    index: dict[tuple[str, str, str], dict[str, str]] = {}
    ambiguous: set[tuple[str, str, str]] = set()
    for item in case_logs:
        target = item.get("target")
        manifest = item.get("manifest")
        candidates = [
            identity
            for identity in identities_by_name.get(item.get("name", ""), [])
            if (not target or identity[0] == target)
            and (not manifest or identity[1] == manifest)
        ]
        if len(candidates) != 1:
            continue

        identity = candidates[0]
        if identity in index:
            ambiguous.add(identity)
        index[identity] = item

    return {
        identity: item
        for identity, item in index.items()
        if identity not in ambiguous
    }


def relative_to_reports(path: Path, reports_dir: Path) -> str:
    """Return a path relative to the reports directory when possible."""
    try:
        return path.relative_to(reports_dir).as_posix()
    except ValueError:
        return str(path)


def display_path(path: Path) -> str:
    """Return a project-relative display path when possible."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def match_case_log_identity(
    candidates: list[dict[str, Any]],
    suite_dir: str,
    target_dir: str,
) -> tuple[str, str, str] | None:
    """Resolve a case log using the runner's suite and full-target directories."""
    matches = [
        case for case in candidates
        if suite_dir == sanitize_name(case["name"].split("::", 1)[0])
        and target_dir == target_work_name(case["target"])
    ]
    if len(matches) == 1:
        return build_case_identity(matches[0])
    if matches or len(candidates) != 1:
        return None

    # Older reports used the target stem as the directory name.
    # Accept them only when the testcase name is unambiguous.
    case = candidates[0]
    suite_names = {
        sanitize_name(case["name"].split("::", 1)[0]),
        sanitize_name(case["suite_name"]),
    }
    if (
        suite_dir in suite_names
        and target_dir == sanitize_name(Path(case["target"]).stem)
    ):
        return build_case_identity(case)
    return None


def discover_case_log_metadata(
    reports_dir: Path,
    cases: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Discover per-case artifacts using the full dashboard case identity."""
    work_root = reports_dir / "_work"
    if not work_root.exists():
        return {}

    cases_by_name: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        cases_by_name.setdefault(case["name"], []).append(case)

    metadata: dict[tuple[str, str, str], dict[str, Any]] = {}
    ambiguous: set[tuple[str, str, str]] = set()
    for case_log in sorted(work_root.rglob("case.log")):
        parts = case_log.relative_to(work_root).parts
        if len(parts) != 4:
            continue
        try:
            content = case_log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        match = CASE_LOG_PATTERN.search(content)
        if match is None:
            continue

        testcase_name = match.group("name").strip()
        identity = match_case_log_identity(
            cases_by_name.get(testcase_name, []), parts[0], parts[1]
        )
        if identity is None:
            continue

        combined_log = case_log.parent.parent / "combined.log"
        change_coverage_path = case_log.parent / "change_coverage.json"
        item: dict[str, Any] = {
            "case_log": relative_to_reports(case_log, reports_dir),
        }
        # Read descriptions/details from this specific log, rather than
        # from a global name-only index spanning all targets.
        description = re.search(r"(?m)^DESCRIPTION:[ \t]*(.*)$", content)
        details = re.search(r"(?ms)^DETAILS:[ \t]*(.*)$", content)
        if description:
            item["description"] = description.group(1).strip()
        if details:
            item["details"] = details.group(1).strip()

        if combined_log.exists():
            item["combined_log"] = relative_to_reports(combined_log, reports_dir)
        if change_coverage_path.exists():
            payload = load_change_coverage_artifact(change_coverage_path)
            if payload is not None:
                item["change_coverage"] = payload
                item["change_coverage_file"] = relative_to_reports(
                    change_coverage_path,
                    reports_dir,
                )
        if identity in metadata:
            ambiguous.add(identity)
        metadata[identity] = item

    return {
        identity: item
        for identity, item in metadata.items()
        if identity not in ambiguous
    }


def collect_dashboard_cases(
    reports_dir: Path = REPORTS_DIR,
    case_logs: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Collect normalized dashboard cases from discovered XML reports."""
    dashboard_cases: list[dict[str, Any]] = []

    # Collect XML identities first so log matching can detect ambiguity
    # across all reports, not just within one XML file.
    for xml_path in iter_runner_xml_reports(reports_dir):
        parsed = parse_junit_report(xml_path)
        for case in parsed["cases"]:
            case["xml_report"] = parsed["xml_report"].name
            dashboard_cases.append(case)

    case_index = build_case_log_index(case_logs or [], dashboard_cases)
    case_log_metadata = discover_case_log_metadata(reports_dir, dashboard_cases)
    for case in dashboard_cases:
        identity = build_case_identity(case)
        metadata = dict(case_log_metadata.get(identity, {}))
        if case_logs is None:
            log_case = metadata
        else:
            log_case = case_index.get(identity, {})
        case["description"] = log_case.get("description", "")
        if not case["details"]:
            case["details"] = log_case.get("details", "")
        # Keep XML details and explicitly supplied descriptions authoritative.
        metadata.pop("description", None)
        metadata.pop("details", None)
        case.update(metadata)

    return dashboard_cases


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize overall case counts by normalized status."""
    return {
        "total": len(cases),
        "passed": sum(1 for case in cases if case["status"] == "passed"),
        "failed": sum(1 for case in cases if case["status"] == "failed"),
        "errors": sum(1 for case in cases if case["status"] == "error"),
        "warnings": sum(1 for case in cases if case["status"] == "warning"),
    }


def build_target_sections(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group dashboard cases into target-oriented sections."""
    grouped: dict[str, dict[str, Any]] = {}

    for case in cases:
        target = case["target"] or "<unknown>"
        section = grouped.setdefault(
            target,
            {
                "target": target,
                "cases": [],
                "manifests": set(),
                "combined_logs": set(),
                "counts": {"total": 0, "passed": 0, "failed": 0, "errors": 0, "warnings": 0},
            },
        )
        section["cases"].append(case)
        if case["manifest"]:
            section["manifests"].add(case["manifest"])
        if case.get("combined_log"):
            section["combined_logs"].add(case["combined_log"])
        section["counts"]["total"] += 1
        status_key = {
            "error": "errors",
            "warning": "warnings",
        }.get(case["status"], case["status"])
        if status_key in section["counts"]:
            section["counts"][status_key] += 1

    targets = sorted(grouped.values(), key=lambda item: item["target"])
    for target in targets:
        target["manifests"] = sorted(target["manifests"])
        target["combined_logs"] = sorted(target["combined_logs"])
        target["cases"] = sorted(target["cases"], key=lambda item: item["name"])
    return targets

def build_case_identity(case: dict[str, Any]) -> tuple[str, str, str]:
    """Build a stable identity string for a dashboard case."""
    return (
        str(case.get("target") or "<unknown>"),
        str(case.get("manifest") or ""),
        str(case.get("name") or ""),
    )


def status_severity(status: str) -> int:
    """Return the sort severity for a normalized case status."""
    return {
        "passed": 0,
        "warning": 1,
        "failed": 2,
        "error": 3,
    }.get(status.lower(), 1)


def count_nonpassing_cases(cases: list[dict[str, Any]]) -> int:
    """Count cases that are not in the passed state."""
    return sum(1 for case in cases if case.get("status") != "passed")


def build_comparison_item(
    current_case: dict[str, Any] | None,
    previous_case: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build comparison metadata for one case across report runs."""
    source = current_case or previous_case or {}
    return {
        "target": str(source.get("target") or "<unknown>"),
        "manifest": str(source.get("manifest") or ""),
        "name": str(source.get("name") or ""),
        "current_anchor": build_case_anchor(current_case) if current_case else "",
        "current_status": str(current_case.get("status") or "") if current_case else "",
        "previous_status": str(previous_case.get("status") or "") if previous_case else "",
        "current_message": str(current_case.get("message") or "") if current_case else "",
        "previous_message": str(previous_case.get("message") or "") if previous_case else "",
        "current_details": str(current_case.get("details") or "") if current_case else "",
        "previous_details": str(previous_case.get("details") or "") if previous_case else "",
        "current_case_log": str(current_case.get("case_log") or "") if current_case else "",
        "current_combined_log": str(current_case.get("combined_log") or "") if current_case else "",
        "current_xml_report": str(current_case.get("xml_report") or "") if current_case else "",
        "previous_case_log": str(previous_case.get("case_log") or "") if previous_case else "",
        "previous_combined_log": (
            str(previous_case.get("combined_log") or "")
            if previous_case else ""
        ),
        "previous_xml_report": str(previous_case.get("xml_report") or "") if previous_case else "",
    }


def build_run_comparison(
    current_cases: list[dict[str, Any]],
    *,
    previous_reports_dir: Path | None,
) -> dict[str, Any] | None:
    """Compare current results against a previous reports directory."""
    if previous_reports_dir is None:
        return None

    previous_reports_dir = Path(previous_reports_dir)
    comparison: dict[str, Any] = {
        "available": False,
        "message": "",
        "previous_reports_dir": display_path(previous_reports_dir),
        "previous_xml_reports": [],
        "summary": {
            "current_total": len(current_cases),
            "previous_total": 0,
            "regressed": 0,
            "fixed": 0,
            "improved": 0,
            "new": 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0,
        },
        "regressed": [],
        "fixed": [],
        "improved": [],
        "new": [],
        "removed": [],
        "changed": [],
        "targets": [],
    }

    if not previous_reports_dir.exists():
        comparison["message"] = "Comparison reports directory was not found."
        return comparison

    previous_xml_reports = iter_runner_xml_reports(previous_reports_dir)
    comparison["previous_xml_reports"] = [path.name for path in previous_xml_reports]
    if not previous_xml_reports:
        comparison["message"] = "No XML reports were found in the comparison reports directory."
        return comparison

    previous_cases = collect_dashboard_cases(reports_dir=previous_reports_dir, case_logs=[])
    comparison["available"] = True
    comparison["summary"]["previous_total"] = len(previous_cases)

    current_index = {build_case_identity(case): case for case in current_cases}
    previous_index = {build_case_identity(case): case for case in previous_cases}

    regressed: list[dict[str, Any]] = []
    fixed: list[dict[str, Any]] = []
    improved: list[dict[str, Any]] = []
    new_cases: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged = 0

    for key in sorted(set(current_index) | set(previous_index)):
        current_case = current_index.get(key)
        previous_case = previous_index.get(key)
        if current_case and previous_case is None:
            new_cases.append(build_comparison_item(current_case, None))
            continue
        if previous_case and current_case is None:
            removed.append(build_comparison_item(None, previous_case))
            continue
        if current_case is None or previous_case is None:
            continue

        current_status = current_case["status"]
        previous_status = previous_case["status"]
        current_severity = status_severity(current_status)
        previous_severity = status_severity(previous_status)
        item = build_comparison_item(current_case, previous_case)

        if current_severity > previous_severity:
            regressed.append(item)
        elif current_severity < previous_severity:
            if current_status == "passed":
                fixed.append(item)
            else:
                improved.append(item)
        elif current_status != previous_status:
            changed.append(item)
        else:
            unchanged += 1

    def sort_key(item: dict[str, Any]) -> tuple[str, str]:
        return str(item["target"]), str(item["name"])

    regressed.sort(key=sort_key)
    fixed.sort(key=sort_key)
    improved.sort(key=sort_key)
    new_cases.sort(key=sort_key)
    removed.sort(key=sort_key)
    changed.sort(key=sort_key)

    target_diffs: dict[str, dict[str, Any]] = {}

    def ensure_target(target_name: str) -> dict[str, Any]:
        return target_diffs.setdefault(
            target_name,
            {
                "target": target_name,
                "current_total": 0,
                "previous_total": 0,
                "current_nonpassing": 0,
                "previous_nonpassing": 0,
                "regressed": 0,
                "fixed": 0,
                "improved": 0,
                "new": 0,
                "removed": 0,
                "changed": 0,
            },
        )

    for case in current_cases:
        target_name = str(case.get("target") or "<unknown>")
        target_entry = ensure_target(target_name)
        target_entry["current_total"] += 1
        if case.get("status") != "passed":
            target_entry["current_nonpassing"] += 1

    for case in previous_cases:
        target_name = str(case.get("target") or "<unknown>")
        target_entry = ensure_target(target_name)
        target_entry["previous_total"] += 1
        if case.get("status") != "passed":
            target_entry["previous_nonpassing"] += 1

    for bucket_name, items in (
        ("regressed", regressed),
        ("fixed", fixed),
        ("improved", improved),
        ("new", new_cases),
        ("removed", removed),
        ("changed", changed),
    ):
        for item in items:
            ensure_target(item["target"])[bucket_name] += 1

    comparison_targets = [
        item
        for item in target_diffs.values()
        if any(
            [
                item["regressed"],
                item["fixed"],
                item["improved"],
                item["new"],
                item["removed"],
                item["changed"],
                item["current_total"] != item["previous_total"],
                item["current_nonpassing"] != item["previous_nonpassing"],
            ]
        )
    ]
    comparison_targets.sort(
        key=lambda item: (
            -item["regressed"],
            -item["new"],
            -item["removed"],
            item["target"],
        )
    )

    comparison["summary"].update(
        {
            "regressed": len(regressed),
            "fixed": len(fixed),
            "improved": len(improved),
            "new": len(new_cases),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": unchanged,
        }
    )
    comparison["regressed"] = regressed
    comparison["fixed"] = fixed
    comparison["improved"] = improved
    comparison["new"] = new_cases
    comparison["removed"] = removed
    comparison["changed"] = changed
    comparison["targets"] = comparison_targets
    return comparison

def normalize_issue_label(message: str, details: str = "", status: str = "") -> str:
    """Normalize root-cause labels into stable dashboard categories."""
    combined = "\n".join(part for part in [message, details] if part).strip().lower()
    if not combined:
        return "Unclassified issue"

    known_labels = (
        (("timeout", "timed out"), "Timeout / wait condition"),
        (("assert", "assertion", "assertionerror", "expected"), "Assertion / expectation mismatch"),
        (("importerror", "no module named", "cannot import"), "Import / module loading failure"),
        (("permission", "access is denied"), "Permission / access failure"),
        (("no such file", "not found", "missing"), "Missing file / artifact"),
        (("config", "yaml", "manifest"), "Configuration / manifest issue"),
    )
    for tokens, label in known_labels:
        if any(token in combined for token in tokens):
            return label
    if status == "warning":
        return "Warning / skipped condition"

    first_line = next(
        (line.strip() for line in combined.splitlines() if line.strip()),
        "unclassified issue",
    )
    normalized = re.sub(r"0x[0-9a-f]+", "0x*", first_line)
    normalized = re.sub(r"\b\d+\b", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .:-")
    return normalized[:88] or "Unclassified issue"


def build_root_cause_clusters(
    cases: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Cluster non-passing cases by normalized root cause."""
    regressed_keys: set[tuple[str, str, str]] = set()
    if comparison and comparison.get("available"):
        for item in comparison.get("regressed", []):
            regressed_keys.add(
                (
                    str(item.get("target") or "<unknown>"),
                    str(item.get("manifest") or ""),
                    str(item.get("name") or ""),
                )
            )

    grouped: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_key = build_case_identity(case)
        if case.get("status") == "passed" and case_key not in regressed_keys:
            continue

        label = normalize_issue_label(
            str(case.get("message") or ""),
            str(case.get("details") or ""),
            str(case.get("status") or ""),
        )
        entry = grouped.setdefault(
            label,
            {
                "label": label,
                "count": 0,
                "regressed": 0,
                "targets": set(),
                "manifests": set(),
                "cases": [],
            },
        )
        entry["count"] += 1
        if case_key in regressed_keys:
            entry["regressed"] += 1
        entry["targets"].add(str(case.get("target") or "<unknown>"))
        if case.get("manifest"):
            entry["manifests"].add(str(case["manifest"]))
        if len(entry["cases"]) < 6:
            entry["cases"].append(
                {
                    "name": str(case.get("name") or ""),
                    "target": str(case.get("target") or "<unknown>"),
                    "status": str(case.get("status") or "warning"),
                    "message": str(case.get("message") or ""),
                    "manifest": str(case.get("manifest") or ""),
                }
            )

    clusters: list[dict[str, Any]] = []
    for entry in grouped.values():
        clusters.append(
            {
                "label": entry["label"],
                "count": entry["count"],
                "regressed": entry["regressed"],
                "targets": sorted(entry["targets"]),
                "target_count": len(entry["targets"]),
                "manifests": sorted(entry["manifests"]),
                "cases": entry["cases"],
            }
        )

    clusters.sort(
        key=lambda item: (
            -item["regressed"],
            -item["count"],
            -item["target_count"],
            item["label"],
        )
    )
    return clusters


def build_incident_summary(
    targets: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
    root_cause_clusters: list[dict[str, Any]],
    attention_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build aggregate incident summary data for dashboard highlights."""
    def count_phrase(count: int, singular: str, plural: str | None = None) -> str:
        plural = plural or f"{singular}s"
        label = singular if count == 1 else plural
        return f"{count} {label}"

    regressed = 0
    new_cases = 0
    recovered_targets = 0
    changed_targets = 0
    most_affected_target = ""

    comparison_available = bool(comparison and comparison.get("available"))
    has_current_issues = any(
        target["counts"].get("failed", 0)
        or target["counts"].get("errors", 0)
        or target["counts"].get("warnings", 0)
        for target in targets
    )

    if comparison_available:
        regressed = int(comparison["summary"].get("regressed", 0))
        new_cases = int(comparison["summary"].get("new", 0))
        changed_targets = len(comparison.get("targets", []))
        recovered_targets = sum(
            1
            for item in comparison.get("targets", [])
            if item.get("previous_nonpassing", 0) > 0 and item.get("current_nonpassing", 0) == 0
        )
        has_incidents = bool(regressed or new_cases or changed_targets)
        if has_incidents and comparison.get("targets"):
            most_affected_target = max(
                comparison["targets"],
                key=lambda item: (
                    item.get("regressed", 0),
                    item.get("current_nonpassing", 0),
                    item.get("new", 0),
                    item.get("current_total", 0),
                ),
            ).get("target", "")
    elif has_current_issues and targets:
        most_affected_target = max(
            targets,
            key=lambda item: (
                item["counts"].get("failed", 0) + item["counts"].get("errors", 0),
                item["counts"].get("warnings", 0),
                item["counts"].get("total", 0),
            ),
        ).get("target", "")

    should_surface_dominant_issue = bool(
        root_cause_clusters and (
            not comparison_available
            or regressed
            or new_cases
            or changed_targets
        )
    )
    dominant_issue = (
        root_cause_clusters[0] if should_surface_dominant_issue else None
    )
    dominant_label = (
        dominant_issue["label"] if dominant_issue else "No dominant issue detected"
    )
    attention_target_count = len(attention_targets)
    nonpassing_target_count = sum(
        1
        for target in targets
        if (
            target["counts"]["failed"]
            or target["counts"]["errors"]
            or target["counts"]["warnings"]
        )
    )

    bullet_points = [
        (
            f'{count_phrase(regressed, "regression", "regressions")} introduced'
            if comparison_available
            else 'No previous run baseline available for regression tracking'
        ),
        (
            f'{count_phrase(recovered_targets, "target", "targets")} recovered'
            if comparison_available
            else (
                f'{count_phrase(attention_target_count, "target", "targets")} '
                'currently need attention'
            )
        ),
        (
            f'{count_phrase(new_cases, "new case", "new cases")} added'
            if comparison_available
            else (
                f'{count_phrase(nonpassing_target_count, "target", "targets")} '
                'currently have non-passing results'
            )
        ),
        f'Most affected target: {most_affected_target or "None"}',
        f'Likely dominant issue: {dominant_label}',
    ]

    return {
        "regressed": regressed,
        "recovered_targets": recovered_targets,
        "new_cases": new_cases,
        "changed_targets": changed_targets,
        "attention_targets": len(attention_targets),
        "most_affected_target": most_affected_target,
        "dominant_issue": dominant_issue,
        "bullet_points": bullet_points,
    }


def build_attention_targets(
    targets: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Rank targets that need the most review attention."""
    comparison_by_target = {}
    if comparison and comparison.get("available"):
        comparison_by_target = {
            item["target"]: item
            for item in comparison.get("targets", [])
        }

    attention: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        target_name = target["target"]
        current_issues = (
            target["counts"].get("failed", 0)
            + target["counts"].get("errors", 0)
            + target["counts"].get("warnings", 0)
        )
        diff = comparison_by_target.get(target_name, {})
        regressed = int(diff.get("regressed", 0))
        new_cases = int(diff.get("new", 0))
        if not (regressed or current_issues or new_cases):
            continue

        reasons: list[dict[str, Any]] = []
        if regressed:
            reasons.append({"label": f'Regressions {regressed}', "class_name": "status-failed"})
        if current_issues:
            class_name = "status-warning"
            if target["counts"].get("failed", 0) or target["counts"].get("errors", 0):
                class_name = "status-failed"
            reasons.append({"label": f'Active issues {current_issues}', "class_name": class_name})
        if new_cases:
            reasons.append({"label": f'New cases {new_cases}', "class_name": "status-covered"})

        attention.append(
            {
                "target": target_name,
                "anchor": f'dashboard-target-{index}',
                "reasons": reasons,
                "regressed": regressed,
                "current_issues": current_issues,
                "new_cases": new_cases,
            }
        )

    attention.sort(
        key=lambda item: (
            -item["regressed"],
            -item["current_issues"],
            -item["new_cases"],
            item["target"],
        )
    )
    return attention

def normalize_testgap_hints(testgap_hints: Any) -> list[dict[str, Any]]:
    """Normalize optional test-gap hints into display-ready records."""
    if not testgap_hints:
        return []

    normalized: list[dict[str, Any]] = []
    for entry in testgap_hints:
        if isinstance(entry, dict):
            target = str(entry.get("target", "")).strip()
            items = entry.get("items", [])
        else:
            target, items = entry

        normalized_items: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized_items.append(
                    {
                        "function_key": str(item.get("function_key", "")).strip(),
                        "status": str(item.get("status", "review")).strip().lower(),
                        "matches": [str(match) for match in item.get("matches", [])],
                    }
                )
            else:
                function_key, status, matches = item
                normalized_items.append(
                    {
                        "function_key": str(function_key).strip(),
                        "status": str(status).strip().lower(),
                        "matches": [str(match) for match in matches],
                    }
                )

        normalized.append({"target": target, "items": normalized_items})

    return normalized


def build_dashboard_data(
    reports_dir: Path = REPORTS_DIR,
    *,
    generated_at: str | None = None,
    case_logs: list[dict[str, str]] | None = None,
    testgap_hints: Any = None,
    previous_reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Assemble the complete dashboard data model from report artifacts."""
    cases = collect_dashboard_cases(reports_dir=reports_dir, case_logs=case_logs)
    manifests = sorted({case["manifest"] for case in cases if case["manifest"]})
    xml_reports = iter_runner_xml_reports(reports_dir)
    targets = build_target_sections(cases)
    comparison = build_run_comparison(
        cases,
        previous_reports_dir=previous_reports_dir,
    )
    attention_targets = build_attention_targets(targets, comparison)
    root_cause_clusters = build_root_cause_clusters(cases, comparison)

    return {
        "generated_at": generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summarize_cases(cases),
        "targets": targets,
        "manifests": manifests,
        "cases": cases,
        "xml_reports": [path.name for path in xml_reports],
        "testgap_hints": normalize_testgap_hints(testgap_hints),
        "comparison": comparison,
        "change_coverage": build_change_coverage_summary(cases),
        "attention_targets": attention_targets,
        "root_cause_clusters": root_cause_clusters,
        "incident_summary": build_incident_summary(
            targets,
            comparison,
            root_cause_clusters,
            attention_targets,
        ),
    }

def build_change_coverage_summary(cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build dashboard data for change-coverage artifacts."""
    target_map: dict[str, dict[str, Any]] = {}

    for case in cases:
        payload = case.get("change_coverage")
        if not isinstance(payload, dict):
            continue

        target_display = str(
            payload.get("target_display")
            or payload.get("target_path")
            or case.get("target")
            or "<unknown>"
        )
        target_entry = target_map.setdefault(
            target_display,
            {
                "target_display": target_display,
                "changed_lines": set(),
                "covered_changed_lines": set(),
                "functions": {},
            },
        )
        target_entry["changed_lines"].update(
            int(line)
            for line in payload.get(
                "executable_changed_lines",
                payload.get("changed_lines", []),
            )
        )
        target_entry["covered_changed_lines"].update(
            int(line) for line in payload.get("covered_changed_lines", [])
        )

        for function in payload.get("functions", []):
            key = (
                str(function.get("name") or "<unknown>"),
                int(function.get("start") or 0),
                int(function.get("end") or 0),
            )
            function_entry = target_entry["functions"].setdefault(
                key,
                {
                    "name": key[0],
                    "start": key[1],
                    "end": key[2],
                    "status": str(function.get("status") or "untouched"),
                    "cases": [],
                },
            )
            function_entry["status"] = stronger_status(
                str(function_entry["status"]),
                str(function.get("status") or "untouched"),
            )
            case_item = {
                "name": str(case.get("name") or ""),
                "target": str(case.get("target") or "<unknown>"),
                "manifest": str(case.get("manifest") or ""),
                "status": str(function.get("status") or "untouched"),
            }
            case_key = (
                case_item["name"],
                case_item["target"],
                case_item["manifest"],
                case_item["status"],
            )
            existing_keys = {
                (item["name"], item["target"], item["manifest"], item["status"])
                for item in function_entry["cases"]
            }
            if case_key not in existing_keys:
                function_entry["cases"].append(case_item)

    if not target_map:
        return None

    summary = {
        "changed_files": len(target_map),
        "changed_functions": 0,
        "covered_functions": 0,
        "partial_functions": 0,
        "untouched_functions": 0,
        "not_applicable_functions": 0,
    }
    targets: list[dict[str, Any]] = []
    order = {"covered": 0, "partial": 1, "untouched": 2, "not_applicable": 3}

    for target_display in sorted(target_map):
        item = target_map[target_display]
        functions = sorted(
            item["functions"].values(),
            key=lambda entry: (order.get(str(entry["status"]), 3), str(entry["name"])),
        )
        for function in functions:
            summary["changed_functions"] += 1
            if function["status"] == "covered":
                summary["covered_functions"] += 1
            elif function["status"] == "partial":
                summary["partial_functions"] += 1
            elif function["status"] == "not_applicable":
                summary["not_applicable_functions"] += 1
            else:
                summary["untouched_functions"] += 1
        targets.append(
            {
                "target_display": target_display,
                "changed_line_count": len(item["changed_lines"]),
                "covered_changed_line_count": len(item["covered_changed_lines"]),
                "functions": functions,
            }
        )

    return {"summary": summary, "targets": targets}

def status_chip_class(status: str) -> str:
    """Return the CSS class used for a status chip."""
    mapping = {
        "passed": "status-passed",
        "failed": "status-failed",
        "error": "status-error",
        "warning": "status-warning",
        "covered": "status-covered",
        "likely": "status-likely",
        "review": "status-review",
        "not_applicable": "status-not-applicable",
    }
    return mapping.get(status.lower(), "status-warning")


def status_label(status: str) -> str:
    """Return the display label for a normalized case status."""
    if status.lower() == "not_applicable":
        return "N/A"
    return status.replace("_", " ").title()


def render_status_chip(status: str) -> str:
    """Render a standard status chip for a normalized status value."""
    return (
        f'<span class="status-chip {status_chip_class(status)}">'
        f'{html.escape(status_label(status))}</span>'
    )


def render_count_chip(class_name: str, label: str, value: Any) -> str:
    """Render a badge-style chip for count-oriented metadata."""
    return (
        f'<span class="status-chip {class_name}">'
        f'{html.escape(label)} {value}</span>'
    )


def render_empty_state(message: str, extra_attributes: str = "") -> str:
    """Render a standard empty-state block with optional HTML attributes."""
    attributes = f" {extra_attributes.strip()}" if extra_attributes else ""
    return f'<div class="empty-state"{attributes}>{html.escape(message)}</div>'


def render_summary_cards(summary: dict[str, int]) -> str:
    """Render the summary cards section for overall case counts."""
    labels = [
        ("Total", summary["total"]),
        ("Passed", summary["passed"]),
        ("Failed", summary["failed"]),
        ("Errors", summary["errors"]),
        ("Warnings", summary["warnings"]),
    ]
    cards = []
    for label, value in labels:
        cards.append(
            "".join(
                [
                    '<div class="stat-card">',
                    f'<span class="label">{html.escape(label)}</span>',
                    f'<span class="value">{value}</span>',
                    '</div>',
                ]
            )
        )
    return '<div class="summary-grid">' + "".join(cards) + '</div>'


def render_manifest_list(manifests: list[str]) -> str:
    """Render an HTML list for manifests or report paths."""
    if not manifests:
        return '<p class="muted">No manifest metadata was found in the generated XML reports.</p>'

    items = "".join(
        f"<li><code>{html.escape(manifest)}</code></li>"
        for manifest in manifests
    )
    return f'<ul class="simple-list">{items}</ul>'


def render_target_picker(targets: list[dict[str, Any]]) -> str:
    """Render the target filter control for the dashboard."""
    if len(targets) <= 1:
        return ""

    options = ['<option value="">All targets</option>']
    for target in targets:
        target_name = target["target"]
        label = f'{target_name} ({target["counts"]["total"]} cases)'
        options.append(
            f'<option value="{html.escape(target_name, quote=True)}">'
            f'{html.escape(label)}</option>'
        )

    return "".join(
        [
            '<div class="acs-toolbar" aria-label="Target controls">',
            '<label class="acs-control">',
            '<span class="acs-control-label">Choose target</span>',
            '<select data-dashboard-target-select aria-label="Choose target">',
            "".join(options),
            '</select>',
            '</label>',
            (
                '<div class="target-picker-summary" '
                f'data-dashboard-target-count>Showing all {len(targets)} '
                'targets</div>'
            ),
            '</div>',
        ]
    )


def render_testgap_panel(testgap_hints: list[dict[str, Any]]) -> str:
    """Render the test-gap hints panel."""
    if not testgap_hints:
        return ""

    groups: list[str] = []
    for target in testgap_hints:
        items: list[str] = []
        for item in target["items"]:
            matches = item.get("matches", [])
            rendered_matches = ""
            if matches:
                rendered_matches = '<ul>' + "".join(
                    f"<li><code>{html.escape(match)}</code></li>"
                    for match in matches[:3]
                ) + '</ul>'
            items.append(
                "".join(
                    [
                        '<div class="testgap-item">',
                        f'<div class="badge-row">{render_status_chip(item["status"])}</div>',
                        f'<p><strong>{html.escape(item["function_key"])}</strong></p>',
                        rendered_matches,
                        '</div>',
                    ]
                )
            )
        groups.append(
            "".join(
                [
                    '<div class="target-card">',
                    '<div class="target-card-header">',
                    f'<h3><code>{html.escape(target["target"] or "<unknown>")}</code></h3>',
                    '</div>',
                    f'<div class="testgap-list">{"".join(items)}</div>',
                    '</div>',
                ]
            )
        )

    return "".join(groups)


def render_log_links(case: dict[str, Any]) -> str:
    """Render HTML links for case-level log artifacts."""
    links: list[str] = []
    case_log = case.get("case_log")
    xml_report = case.get("xml_report")

    if case_log:
        links.append(f'<a href="{html.escape(case_log)}">case.log</a>')
    if xml_report:
        links.append(f'<a href="{html.escape(xml_report)}">xml</a>')

    if not links:
        return '<span class="muted">No log files linked</span>'

    return '<div class="log-links">' + ''.join(links) + '</div>'


def render_target_log_links(target: dict[str, Any]) -> str:
    """Render HTML links for target-level log artifacts."""
    combined_logs = target.get("combined_logs", [])
    if not combined_logs:
        return ""

    links: list[str] = []
    for index, combined_log in enumerate(combined_logs, start=1):
        label = "combined.log" if len(combined_logs) == 1 else f"combined.log {index}"
        links.append(f'<a href="{html.escape(combined_log)}">{html.escape(label)}</a>')

    return '<div class="target-log-links">' + ''.join(links) + '</div>'

def render_target_status_filters(target: dict[str, Any]) -> str:
    """Render status filter chips for one target section."""
    filter_specs = [
        ("all", "All", target["counts"]["total"]),
        ("passed", "Passed", target["counts"]["passed"]),
        ("failed", "Failed", target["counts"]["failed"]),
        ("error", "Errors", target["counts"]["errors"]),
        ("warning", "Warnings", target["counts"]["warnings"]),
    ]

    buttons: list[str] = []
    for status_value, label, count in filter_specs:
        if status_value != "all" and count == 0:
            continue
        buttons.append(
            ''.join(
                [
                    '<button type="button" class="target-status-filter" data-target-status-filter ',
                    f'data-status-value="{html.escape(status_value, quote=True)}" ',
                    f'data-status-kind="{html.escape(status_value, quote=True)}" ',
                    f'aria-pressed="{"true" if status_value == "all" else "false"}">',
                    html.escape(f"{label} {count}"),
                    '</button>',
                ]
            )
        )

    return (
        '<div class="target-status-filters" aria-label="Case status filters">'
        + ''.join(buttons)
        + '</div>'
    )


def render_case_details(case: dict[str, Any]) -> str:
    """Render the detail block for one dashboard case."""
    body_parts: list[str] = []
    if case.get("message"):
        body_parts.append(f'Message: {case["message"]}')
    if case.get("details"):
        body_parts.append(case["details"])

    if not body_parts:
        return '<span class="muted">-</span>'

    body = "\n\n".join(body_parts)
    return (
        '<details class="case-details">'
        '<summary>View details</summary>'
        f'<pre>{html.escape(body)}</pre>'
        '</details>'
    )

def render_target_sections(targets: list[dict[str, Any]]) -> str:
    """Render all target result sections."""
    if not targets:
        return render_empty_state(
            'No YAML runner case results were found in the reports directory.'
        )

    rendered_targets: list[str] = []
    for index, target in enumerate(targets, start=1):
        manifest_groups: dict[str, list[dict[str, Any]]] = {}
        for case in target["cases"]:
            manifest_name = str(case.get("manifest") or "-")
            manifest_groups.setdefault(manifest_name, []).append(case)

        manifest_sections: list[str] = []
        for manifest_index, manifest_name in enumerate(sorted(manifest_groups), start=1):
            rows: list[str] = []
            for case in manifest_groups[manifest_name]:
                description_html = ""
                if case["description"]:
                    description_html = (
                        f'<div class="case-description">{html.escape(case["description"])}</div>'
                    )
                rows.append(
                    "".join(
                        [
                            (
                                f'<tr id="{html.escape(build_case_anchor(case), quote=True)}" '
                                'data-case-row '
                                f'data-case-status="{html.escape(case["status"], quote=True)}">'
                            ),
                            '<td>',
                            f'<div class="case-name">{html.escape(case["name"])}</div>',
                            description_html,
                            '</td>',
                            f'<td>{render_status_chip(case["status"])}</td>',
                            f'<td>{render_log_links(case)}</td>',
                            f'<td>{render_case_details(case)}</td>',
                            '</tr>',
                        ]
                    )
                )

            manifest_sections.append(
                "".join(
                    [
                        (
                            '<details class="manifest-section" data-manifest-section'
                            f'{" open" if manifest_index == 1 else ""}>'
                        ),
                        '<summary>',
                        '<div class="manifest-section-title">',
                        f'<code>{html.escape(manifest_name)}</code>',
                        render_count_chip(
                            'status-covered',
                            'Tests',
                            len(manifest_groups[manifest_name]),
                        ),
                        '</div>',
                        '</summary>',
                        '<div class="manifest-section-body">',
                        '<div class="table-wrap">',
                        '<table class="report-table">',
                        (
                            '<thead><tr><th>Case</th><th>Status</th><th>Logs</th>'
                            '<th>Details</th></tr></thead>'
                        ),
                        f'<tbody>{"".join(rows)}</tbody>',
                        '</table>',
                        '</div>',
                        '</div>',
                        '</details>',
                    ]
                )
            )

        rendered_targets.append(
            "".join(
                [
                    (
                        f'<div class="target-card" id="dashboard-target-{index}" '
                        'data-dashboard-target-card '
                        f'data-target="{html.escape(target["target"], quote=True)}">'
                    ),
                    '<div class="target-card-header">',
                    f'<h3><code>{html.escape(target["target"])}</code></h3>',
                    '<div class="badge-row">',
                    render_count_chip('status-covered', 'Cases', target["counts"]["total"]),
                    render_count_chip('status-passed', 'Passed', target["counts"]["passed"]),
                    render_count_chip('status-failed', 'Failed', target["counts"]["failed"]),
                    render_count_chip('status-error', 'Errors', target["counts"]["errors"]),
                    render_count_chip('status-warning', 'Warnings', target["counts"]["warnings"]),
                    render_count_chip('status-covered', 'Manifests', len(manifest_groups)),
                    '</div>',
                    '</div>',
                    '<div class="target-card-tools">',
                    render_target_log_links(target),
                    render_target_status_filters(target),
                    '</div>',
                    '<div class="manifest-sections">',
                    ''.join(manifest_sections),
                    '</div>',
                    render_empty_state(
                        'No cases match the selected status filter.',
                        'class="empty-state target-filter-empty" data-target-filter-empty hidden',
                    ),
                    '</div>',
                ]
            )
        )

    return "".join(rendered_targets)

def render_comparison_summary_cards(summary: dict[str, int]) -> str:
    """Render summary cards for cross-run comparison counts."""
    labels = [
        ("Current Cases", summary["current_total"]),
        ("Previous Cases", summary["previous_total"]),
        ("Regressed", summary["regressed"]),
        ("Fixed", summary["fixed"]),
        ("New", summary["new"]),
        ("Removed", summary["removed"]),
    ]
    cards: list[str] = []
    for label, value in labels:
        cards.append(
            "".join(
                [
                    '<div class="stat-card">',
                    f'<span class="label">{html.escape(label)}</span>',
                    f'<span class="value">{value}</span>',
                    '</div>',
                ]
            )
        )
    return '<div class="summary-grid">' + ''.join(cards) + '</div>'


def render_comparison_statuses(item: dict[str, Any]) -> str:
    """Render status badges for a comparison item."""
    parts: list[str] = []
    previous_status = item.get("previous_status", "")
    current_status = item.get("current_status", "")

    if previous_status:
        parts.append(
            render_status_chip(previous_status)
        )
    if previous_status and current_status:
        parts.append('<span class="comparison-flow-arrow">&rarr;</span>')
    if current_status:
        parts.append(
            render_status_chip(current_status)
        )

    if not parts:
        return '<span class="muted">No status data</span>'
    return '<div class="comparison-statuses">' + ''.join(parts) + '</div>'


def build_anchor_fragment(value: str) -> str:
    """Build a safe HTML anchor fragment from a text value."""
    fragment = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return fragment[:80] or "item"


def build_case_anchor(case: dict[str, Any]) -> str:
    """Build the anchor identifier for a dashboard case."""
    target = str(case.get("target") or "<unknown>")
    manifest = str(case.get("manifest") or "")
    case_name = str(case.get("name") or "")
    stable_parts = [
        target,
        manifest,
        case_name,
        str(case.get("suite_name") or ""),
        str(case.get("xml_report") or ""),
        str(case.get("status") or ""),
        str(case.get("message") or ""),
        str(case.get("details") or ""),
        str(case.get("case_log") or ""),
        str(case.get("combined_log") or ""),
    ]
    digest = hashlib.sha256("\x1f".join(stable_parts).encode("utf-8", "replace")).hexdigest()[:12]
    return "-".join(
        [
            "case",
            build_anchor_fragment(target or "unknown-target"),
            build_anchor_fragment(manifest or "no-manifest"),
            build_anchor_fragment(case_name or "unnamed-case"),
            digest,
        ]
    )


def render_target_jump_link(target_name: str, target_anchor_map: dict[str, str]) -> str:
    """Render a jump link to a target section when available."""
    label = f'<code>{html.escape(target_name or "<unknown>")}</code>'
    anchor = target_anchor_map.get(target_name)
    if not anchor:
        return label
    return (
        f'<a class="comparison-jump-link" '
        f'href="#{html.escape(anchor, quote=True)}">{label}</a>'
    )


def render_case_jump_link(
    case_name: str,
    target_name: str,
    manifest: str,
    case_anchor_map: dict[tuple[str, str, str], str],
    anchor: str = "",
) -> str:
    """Render a jump link to a specific case when available."""
    resolved_anchor = anchor or case_anchor_map.get((target_name, manifest, case_name), "")
    label = html.escape(case_name or "<unnamed case>")
    if not resolved_anchor:
        return label
    return (
        f'<a class="comparison-jump-link" '
        f'href="#{html.escape(resolved_anchor, quote=True)}">{label}</a>'
    )


def render_comparison_message_box(
    title: str,
    status: str,
    message: str,
    details: str,
) -> str:
    """Render the comparison message block for one case."""
    parts: list[str] = []
    if message:
        parts.append(f"Message: {message}")
    if details and details.strip() != message.strip():
        parts.append(details)
    body = "\n\n".join(parts)
    body_html = (
        f'<pre>{html.escape(body)}</pre>'
        if body
        else '<p class="comparison-inline-note">No details recorded.</p>'
    )
    chip_html = ""
    if status:
        chip_html = ''.join(
            [
                '<div class="badge-row">',
                render_status_chip(status),
                '</div>',
            ]
        )
    return ''.join(
        [
            '<div class="comparison-message-box">',
            f'<h4>{html.escape(title)}</h4>',
            chip_html,
            body_html,
            '</div>',
        ]
    )

def render_comparison_artifacts(title: str, artifacts: list[tuple[str, str]]) -> str:
    """Render artifact links associated with a comparison item."""
    if not artifacts:
        return ''.join(
            [
                '<div class="comparison-section-spacer">',
                f'<h4>{html.escape(title)}</h4>',
                '<p class="comparison-inline-note">No artifacts linked.</p>',
                '</div>',
            ]
        )

    rows = []
    for label, artifact_path in artifacts:
        rows.append(
            ''.join(
                [
                    '<li>',
                    f'<a href="{html.escape(artifact_path, quote=True)}">{html.escape(label)}</a>',
                    f' <span class="comparison-inline-note">{html.escape(artifact_path)}</span>',
                    '</li>',
                ]
            )
        )

    return ''.join(
        [
            '<div class="comparison-section-spacer">',
            f'<h4>{html.escape(title)}</h4>',
            '<ul class="comparison-artifact-list">',
            ''.join(rows),
            '</ul>',
            '</div>',
        ]
    )


def render_comparison_drawer(
    item: dict[str, Any],
    target_anchor_map: dict[str, str],
    case_anchor_map: dict[tuple[str, str, str], str],
) -> str:
    """Render the expandable comparison drawer for one case."""
    manifest_line = ""
    if item.get("manifest"):
        manifest_line = (
            '<div class="case-description">'
            f'<code>{html.escape(item["manifest"])}</code>'
            '</div>'
        )

    current_artifacts = [
        ("case.log", str(item.get("current_case_log") or "")),
        ("combined.log", str(item.get("current_combined_log") or "")),
        ("xml report", str(item.get("current_xml_report") or "")),
    ]
    current_artifacts = [(label, value) for label, value in current_artifacts if value]

    previous_artifacts = [
        ("case.log", str(item.get("previous_case_log") or "")),
        ("combined.log", str(item.get("previous_combined_log") or "")),
        ("xml report", str(item.get("previous_xml_report") or "")),
    ]
    previous_artifacts = [(label, value) for label, value in previous_artifacts if value]

    case_link = render_case_jump_link(
        str(item.get("name") or ""),
        str(item.get("target") or "<unknown>"),
        str(item.get("manifest") or ""),
        case_anchor_map,
        anchor=str(item.get("current_anchor") or ""),
    )

    return ''.join(
        [
            '<li>',
            '<details class="comparison-drawer">',
            '<summary>',
            '<div class="comparison-drawer-top">',
            f'<div class="case-name">{case_link}</div>',
            (
                '<div class="muted">'
                f'{render_target_jump_link(
                    str(item.get("target") or "<unknown>"),
                    target_anchor_map,
                )}'
                '</div>'
            ),
            manifest_line,
            render_comparison_statuses(item),
            '</div>',
            '</summary>',
            '<div class="comparison-drawer-body">',
            '<div class="comparison-message-grid">',
            render_comparison_message_box(
                'Previous result',
                str(item.get("previous_status") or ""),
                str(item.get("previous_message") or ""),
                str(item.get("previous_details") or ""),
            ),
            render_comparison_message_box(
                'Current result',
                str(item.get("current_status") or ""),
                str(item.get("current_message") or ""),
                str(item.get("current_details") or ""),
            ),
            '</div>',
            render_comparison_artifacts('Current artifacts', current_artifacts),
            render_comparison_artifacts('Previous baseline artifacts', previous_artifacts),
            '</div>',
            '</details>',
            '</li>',
        ]
    )


def render_comparison_case_list(
    title: str,
    items: list[dict[str, Any]],
    empty_message: str,
    target_anchor_map: dict[str, str],
    case_anchor_map: dict[tuple[str, str, str], str],
) -> str:
    """Render the list of comparison cases for a target."""
    body: str
    if not items:
        body = f'<p class="muted">{html.escape(empty_message)}</p>'
    else:
        rendered_items = [
            render_comparison_drawer(item, target_anchor_map, case_anchor_map)
            for item in items[:5]
        ]
        body = '<ul class="comparison-case-list">' + ''.join(rendered_items) + '</ul>'
        remaining = len(items) - 5
        if remaining > 0:
            body += f'<p class="muted">+{remaining} more changes</p>'

    return ''.join(
        [
            '<div class="comparison-block">',
            '<div class="comparison-block-header">',
            f'<h3>{html.escape(title)}</h3>',
            f'<span class="status-chip status-covered">Cases {len(items)}</span>',
            '</div>',
            body,
            '</div>',
        ]
    )

def render_comparison_targets(
    targets: list[dict[str, Any]],
    target_anchor_map: dict[str, str],
) -> str:
    """Render comparison results grouped by target."""
    if not targets:
        return render_empty_state(
            'No target-level differences were detected between the two runs.'
        )

    rows: list[str] = []
    for target in targets:
        rows.append(
            ''.join(
                [
                    '<tr>',
                    f'<td>{render_target_jump_link(target["target"], target_anchor_map)}</td>',
                    f'<td>{target["previous_total"]}</td>',
                    f'<td>{target["current_total"]}</td>',
                    f'<td>{target["previous_nonpassing"]}</td>',
                    f'<td>{target["current_nonpassing"]}</td>',
                    f'<td>{target["regressed"]}</td>',
                    f'<td>{target["fixed"]}</td>',
                    f'<td>{target["new"]}</td>',
                    f'<td>{target["removed"]}</td>',
                    '</tr>',
                ]
            )
        )

    return ''.join(
        [
            '<div class="table-wrap">',
            '<table class="report-table comparison-target-table">',
            (
                '<thead><tr><th>Target</th><th>Prev Cases</th><th>Current Cases</th>'
                '<th>Prev Issues</th><th>Current Issues</th><th>Regressed</th>'
                '<th>Fixed</th><th>New</th><th>Removed</th></tr></thead>'
            ),
            f'<tbody>{"".join(rows)}</tbody>',
            '</table>',
            '</div>',
        ]
    )


def render_incident_summary_panel(
    incident_summary: dict[str, Any],
    target_anchor_map: dict[str, str],
) -> str:
    """Render the high-level incident summary panel."""
    dominant_issue = incident_summary.get("dominant_issue")
    dominant_block = '<p class="comparison-inline-note">No dominant issue detected.</p>'
    if dominant_issue:
        target_links = ', '.join(
            render_target_jump_link(target_name, target_anchor_map)
            for target_name in dominant_issue.get("targets", [])[:4]
        ) or '<span class="comparison-inline-note">No affected targets listed.</span>'
        dominant_block = ''.join(
            [
                '<div class="badge-row">',
                render_count_chip(
                    'status-failed',
                    'Cases',
                    dominant_issue.get("count", 0),
                ),
                render_count_chip(
                    'status-warning',
                    'Targets',
                    dominant_issue.get("target_count", 0),
                ),
                render_count_chip(
                    'status-covered',
                    'Regressions',
                    dominant_issue.get("regressed", 0),
                ),
                '</div>',
                f'<p class="muted">{html.escape(dominant_issue.get("label", ""))}</p>',
                f'<div class="cluster-targets">{target_links}</div>',
            ]
        )

    most_affected_target = incident_summary.get("most_affected_target") or ""
    most_affected_html = (
        render_target_jump_link(most_affected_target, target_anchor_map)
        if most_affected_target
        else '<span class="comparison-inline-note">No affected targets</span>'
    )

    brief_items = [
        (
            f'<li>{html.escape(point)}</li>'
            if not point.startswith("Most affected target:")
            and not point.startswith("Likely dominant issue:")
            else ""
        )
        for point in incident_summary.get("bullet_points", [])[:3]
    ]
    brief_items = [item for item in brief_items if item]
    brief_items.append(f'<li>Most affected target: {most_affected_html}</li>')
    likely_issue_label = (
        dominant_issue.get("label", "No dominant issue detected")
        if dominant_issue else "No dominant issue detected"
    )
    brief_items.append(
        f'<li>Likely dominant issue: {html.escape(likely_issue_label)}</li>'
    )

    return ''.join(
        [
            '<section class="panel">',
            '<h2>Incident Summary</h2>',
            '<div class="incident-grid">',
            '<div class="incident-card">',
            '<h3>Incident Brief</h3>',
            '<ul class="incident-brief">',
            ''.join(brief_items),
            '</ul>',
            '</div>',
            '<div class="incident-card">',
            '<h3>Dominant Cluster</h3>',
            dominant_block,
            '</div>',
            '<div class="incident-card">',
            '<h3>Scope</h3>',
            '<div class="badge-row">',
            render_count_chip(
                'status-failed',
                'Attention',
                incident_summary.get("attention_targets", 0),
            ),
            render_count_chip(
                'status-warning',
                'Changed Targets',
                incident_summary.get("changed_targets", 0),
            ),
            render_count_chip(
                'status-covered',
                'Recovered',
                incident_summary.get("recovered_targets", 0),
            ),
            '</div>',
            '</div>',
            '</div>',
            '</section>',
        ]
    )


def render_root_cause_clusters(
    clusters: list[dict[str, Any]],
    target_anchor_map: dict[str, str],
    case_anchor_map: dict[tuple[str, str, str], str],
) -> str:
    """Render grouped root-cause clusters for non-passing cases."""
    if not clusters:
        return ""

    cards: list[str] = []
    for cluster in clusters[:8]:
        target_links = ''.join(
            f'<span>{render_target_jump_link(target_name, target_anchor_map)}</span>'
            for target_name in cluster.get("targets", [])
        ) or '<span class="comparison-inline-note">No targets linked.</span>'

        sample_cases: list[str] = []
        for case in cluster.get("cases", [])[:5]:
            sample_cases.append(
                ''.join(
                    [
                        '<li>',
                        render_case_jump_link(
                            str(case.get("name") or ""),
                            str(case.get("target") or "<unknown>"),
                            str(case.get("manifest") or ""),
                            case_anchor_map,
                            anchor=build_case_anchor(case),
                        ),
                        ' - ',
                        render_target_jump_link(
                            str(case.get("target") or "<unknown>"),
                            target_anchor_map,
                        ),
                        '</li>',
                    ]
                )
            )

        cards.append(
            ''.join(
                [
                    '<div class="cluster-card">',
                    f'<h3>{html.escape(cluster.get("label", "Unclassified issue"))}</h3>',
                    '<div class="cluster-meta">',
                    render_count_chip('status-failed', 'Cases', cluster.get("count", 0)),
                    render_count_chip('status-warning', 'Targets', cluster.get("target_count", 0)),
                    render_count_chip('status-covered', 'Regressions', cluster.get("regressed", 0)),
                    '</div>',
                    f'<div class="cluster-targets">{target_links}</div>',
                    '<ul class="cluster-sample-cases">',
                    (
                        ''.join(sample_cases)
                        or '<li class="comparison-inline-note">No sample cases available.</li>'
                    ),
                    '</ul>',
                    '</div>',
                ]
            )
        )

    return ''.join(
        [
            '<section class="panel">',
            '<h2>Root-Cause Clusters</h2>',
            '<div class="cluster-grid">',
            ''.join(cards),
            '</div>',
            '</section>',
        ]
    )


def render_attention_lane(
    attention_targets: list[dict[str, Any]],
    target_anchor_map: dict[str, str],
) -> str:
    """Render the prioritized attention lane for problematic targets."""
    if not attention_targets:
        return ""

    cards: list[str] = []
    for item in attention_targets:
        cards.append(
            ''.join(
                [
                    '<div class="attention-card">',
                    '<div class="attention-card-title">',
                    f'<h3>{render_target_jump_link(item["target"], target_anchor_map)}</h3>',
                    '</div>',
                    '<div class="badge-row">',
                    ''.join(
                        (
                            f'<span class="status-chip {reason["class_name"]}">'
                            f'{html.escape(reason["label"])}'
                            '</span>'
                        )
                        for reason in item.get("reasons", [])
                    ),
                    '</div>',
                    '</div>',
                ]
            )
        )

    return ''.join(
        [
            '<section class="panel">',
            '<h2>Needs Attention</h2>',
            '<div class="attention-grid">',
            ''.join(cards),
            '</div>',
            '</section>',
        ]
    )


def render_change_coverage_summary_cards(summary: dict[str, int]) -> str:
    """Render summary cards for change-coverage results."""
    labels = [
        ("Changed Files", summary["changed_files"]),
        ("Changed Functions", summary["changed_functions"]),
        ("Covered", summary["covered_functions"]),
        ("Partial", summary["partial_functions"]),
        ("Untouched", summary["untouched_functions"]),
        ("N/A", summary.get("not_applicable_functions", 0)),
    ]
    cards: list[str] = []
    for label, value in labels:
        cards.append(
            "".join(
                [
                    '<div class="stat-card">',
                    f'<span class="label">{html.escape(label)}</span>',
                    f'<span class="value">{value}</span>',
                    '</div>',
                ]
            )
        )
    return '<div class="summary-grid">' + ''.join(cards) + '</div>'


def render_change_coverage_panel(
    change_coverage: dict[str, Any] | None,
    case_anchor_map: dict[tuple[str, str, str], str],
) -> str:
    """Render the change-coverage analysis panel."""
    if not change_coverage:
        return ""

    cards: list[str] = []
    for target in change_coverage.get("targets", []):
        function_rows: list[str] = []
        for function in target.get("functions", []):
            status = str(function.get("status") or "untouched")
            case_links = ''.join(
                (
                    '<span>'
                    f'{render_case_jump_link(
                        item["name"],
                        item["target"],
                        item["manifest"],
                        case_anchor_map,
                    )}'
                    '</span>'
                )
                for item in function.get("cases", [])
            ) or '<span class="comparison-inline-note">No cases recorded.</span>'
            function_rows.append(
                ''.join(
                    [
                        '<li>',
                        f'<strong>{html.escape(function.get("name", "<unknown>"))}()</strong> ',
                        render_status_chip(status),
                        f'<div class="coverage-case-links">{case_links}</div>',
                        '</li>',
                    ]
                )
            )

        cards.append(
            ''.join(
                [
                    '<div class="cluster-card">',
                    (
                        '<h3><code>'
                        f'{html.escape(target.get("target_display", "<unknown>"))}'
                        '</code></h3>'
                    ),
                    '<div class="badge-row">',
                    render_count_chip(
                        'status-covered',
                        'Changed lines',
                        target.get("changed_line_count", 0),
                    ),
                    render_count_chip(
                        'status-passed',
                        'Covered lines',
                        target.get("covered_changed_line_count", 0),
                    ),
                    render_count_chip(
                        'status-warning',
                        'Functions',
                        len(target.get("functions", [])),
                    ),
                    '</div>',
                    '<ul class="coverage-function-list">',
                    (
                        ''.join(function_rows)
                        or '<li class="comparison-inline-note">No changed functions detected.</li>'
                    ),
                    '</ul>',
                    '</div>',
                ]
            )
        )

    return ''.join(
        [
            '<section class="panel">',
            '<h2>Change-Aware Coverage</h2>',
            (
                '<p class="comparison-note">Shows which existing YAML tests '
                'reached changed Python functions and changed lines.</p>'
            ),
            render_change_coverage_summary_cards(change_coverage["summary"]),
            '<div class="cluster-grid">',
            ''.join(cards),
            '</div>',
            '</section>',
        ]
    )


def render_comparison_panel(
    comparison: dict[str, Any] | None,
    target_anchor_map: dict[str, str],
    case_anchor_map: dict[tuple[str, str, str], str],
) -> str:
    """Render the cross-run comparison panel when comparison data exists."""
    if comparison is None:
        return ""

    if not comparison.get("available"):
        return ''.join(
            [
                '<section class="panel">',
                '<h2>Run Comparison</h2>',
                (
                    '<p class="comparison-note">Compare baseline: <code>'
                    f'{html.escape(comparison.get("previous_reports_dir", ""))}'
                    '</code></p>'
                ),
                render_empty_state(
                    comparison.get("message", "No comparison data is available."),
                ),
                '</section>',
            ]
        )

    summary = comparison["summary"]
    note_parts = [
        'Compared current reports against ',
        f'<code>{html.escape(comparison["previous_reports_dir"])}</code>',
        f' using {len(comparison.get("previous_xml_reports", []))} previous XML reports.',
    ]
    tracked_badges = ''.join(
        [
            f'<span class="status-chip status-passed">Improved {summary["improved"]}</span>',
            f'<span class="status-chip status-warning">Same severity {summary["changed"]}</span>',
            f'<span class="status-chip status-covered">Unchanged {summary["unchanged"]}</span>',
        ]
    )

    return ''.join(
        [
            '<section class="panel">',
            '<h2>Run Comparison</h2>',
            '<div class="comparison-panel">',
            '<div class="comparison-overview">',
            '<p class="comparison-kicker">Baseline Comparison</p>',
            f'<p class="comparison-note">{"".join(note_parts)}</p>',
            f'<div class="badge-row">{tracked_badges}</div>',
            '</div>',
            render_comparison_summary_cards(summary),
            '<div class="comparison-detail-grid">',
            ''.join(
                [
                    '<div class="comparison-block">',
                    '<div class="comparison-block-header">',
                    '<h3>Previous XML Reports</h3>',
                    render_count_chip(
                        'status-covered',
                        'Files',
                        len(comparison.get("previous_xml_reports", [])),
                    ),
                    '</div>',
                    render_manifest_list(comparison.get("previous_xml_reports", [])),
                    '</div>',
                ]
            ),
            render_comparison_case_list(
                'Regressed Cases',
                comparison["regressed"],
                'No regressions were detected.',
                target_anchor_map,
                case_anchor_map,
            ),
            render_comparison_case_list(
                'Fixed Cases',
                comparison["fixed"],
                'No fixes were detected.',
                target_anchor_map,
                case_anchor_map,
            ),
            render_comparison_case_list(
                'New Cases',
                comparison["new"],
                'No newly introduced cases were detected.',
                target_anchor_map,
                case_anchor_map,
            ),
            render_comparison_case_list(
                'Removed Cases',
                comparison["removed"],
                'No removed cases were detected.',
                target_anchor_map,
                case_anchor_map,
            ),
            '</div>',
            '<div class="comparison-block comparison-block-wide">',
            '<div class="comparison-block-header">',
            '<h3>Per-Target Diff</h3>',
            render_count_chip(
                'status-warning',
                'Changed Targets',
                len(comparison["targets"]),
            ),
            '</div>',
            render_comparison_targets(comparison["targets"], target_anchor_map),
            '</div>',
            '</div>',
            '</section>',
        ]
    )

def render_dashboard_html(data: dict[str, Any]) -> str:
    """Render the complete dashboard HTML document."""
    summary = data["summary"]
    subtitle = (
        f'{summary["total"]} cases across {len(data["targets"])} targets and '
        f'{len(data["manifests"])} manifests'
    )
    target_anchor_map = {
        target["target"]: f'dashboard-target-{index}'
        for index, target in enumerate(data["targets"], start=1)
    }
    case_anchor_map = {
        build_case_identity(case): build_case_anchor(case)
        for case in data.get("cases", [])
    }

    return "".join(
        [
            '<!DOCTYPE html>',
            '<html lang="en">',
            '<head>',
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<title>ACS YAML Runner Dashboard</title>',
            f'<style>{DASHBOARD_CSS}</style>',
            '</head>',
            '<body class="acs-report-ui" data-acs-report-kind="acs-summary">',
            '<div class="header">',
            '<p class="acs-report-kicker">SystemReady ACS</p>',
            '<h1>YAML Runner Dashboard</h1>',
            f'<p>{html.escape(subtitle)}</p>',
            f'<p>Generated at {html.escape(data["generated_at"])}</p>',
            '</div>',
            '<div class="container">',
            render_incident_summary_panel(data.get("incident_summary", {}), target_anchor_map),
            '<section class="panel">',
            '<h2>Summary</h2>',
            render_summary_cards(summary),
            '</section>',
            '<section class="panel">',
            '<h2>Run Metadata</h2>',
            '<div class="meta-grid">',
            '<div>',
            '<h3>XML Reports</h3>',
            f'<p class="muted">{len(data["xml_reports"])} report files discovered.</p>',
            render_manifest_list(data["xml_reports"]),
            '</div>',
            '<div>',
            '<h3>Manifests</h3>',
            f'<p class="muted">{len(data["manifests"])} manifest groups represented.</p>',
            render_manifest_list(data["manifests"]),
            '</div>',
            '</div>',
            '</section>',
            render_comparison_panel(data.get("comparison"), target_anchor_map, case_anchor_map),
            render_change_coverage_panel(data.get("change_coverage"), case_anchor_map),
            render_root_cause_clusters(
                data.get("root_cause_clusters", []),
                target_anchor_map,
                case_anchor_map,
            ),
            render_attention_lane(data.get("attention_targets", []), target_anchor_map),
            '<section class="panel">',
            '<h2>Target Results</h2>',
            render_target_picker(data["targets"]),
            render_target_sections(data["targets"]),
            render_empty_state(
                'No targets match the selected filter.',
                'data-dashboard-target-empty hidden',
            ),
            '</section>',
            (
                ''.join(
                    [
                        '<section class="panel">',
                        '<h2>Test Gap Hints</h2>',
                        render_testgap_panel(data["testgap_hints"]),
                        '</section>',
                    ]
                )
                if data["testgap_hints"]
                else ''
            ),
            '</div>',
            f'<script>{DASHBOARD_SCRIPT}</script>',
            '</body>',
            '</html>',
        ]
    )


def write_dashboard(
    output_path: Path = DEFAULT_DASHBOARD_PATH,
    *,
    options: DashboardWriteOptions | None = None,
) -> Path:
    """Build dashboard data and write the generated HTML to disk."""
    config = options or DashboardWriteOptions()
    data = build_dashboard_data(
        reports_dir=config.reports_dir,
        generated_at=config.generated_at,
        case_logs=config.case_logs,
        testgap_hints=config.testgap_hints,
        previous_reports_dir=config.previous_reports_dir,
    )
    html_content = render_dashboard_html(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def main() -> int:
    """Parse CLI arguments and generate the dashboard HTML output."""
    parser = argparse.ArgumentParser(
        description="Generate a static HTML dashboard for YAML runner reports."
    )
    parser.add_argument(
        "--reports-dir",
        default=str(REPORTS_DIR),
        help="Directory containing runner XML reports and work logs",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_DASHBOARD_PATH),
        help="Path to the generated dashboard HTML file",
    )
    parser.add_argument(
        "--compare-reports-dir",
        help=(
            'Optional previous reports directory to compare against '
            '(defaults to last run snapshot)'
        ),
    )
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    previous_reports_dir = (
        Path(args.compare_reports_dir)
        if args.compare_reports_dir
        else (LAST_RUN_REPORTS_DIR if LAST_RUN_REPORTS_DIR.exists() else None)
    )

    output_path = write_dashboard(
        output_path=Path(args.output),
        options=DashboardWriteOptions(
            reports_dir=reports_dir,
            previous_reports_dir=previous_reports_dir,
        ),
    )
    print(f"[INFO] Dashboard written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
