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

"""Run dependency-free Chromium smoke tests for the shared report UI."""

from __future__ import annotations

import html
import importlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from threading import Thread


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PARSER_DIR = PROJECT_ROOT / "common" / "log_parser"


def _load_enhancer():
    """Import the report enhancer from the repository under test."""
    sys.path.insert(0, str(LOG_PARSER_DIR))
    return importlib.import_module("report_ui").enhance_html_report


def _chromium_binary() -> str:
    for candidate in ("chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("Chromium is required for the report UI browser smoke test")


class _QuietHandler(SimpleHTTPRequestHandler):
    """Serve smoke pages without adding request noise to test output."""

    def log_message(self, format: str, *args) -> None:
        """Suppress HTTP access logging during smoke tests."""
        del format, args


def _run_page(
    browser: str,
    directory: Path,
    name: str,
    content: str,
    window_size: str = "1600,900",
) -> None:
    page = directory / f"{name}.html"
    page.write_text(content, encoding="utf-8")
    handler = partial(_QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        completed = subprocess.run(
            [
                browser,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-component-update",
                "--no-first-run",
                f"--window-size={window_size}",
                "--virtual-time-budget=2500",
                "--dump-dom",
                f"http://127.0.0.1:{server.server_port}/{page.name}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
    marker = 'data-browser-smoke="PASS"'
    if completed.returncode == 0 and marker in completed.stdout:
        return

    result = re.search(
        r'<pre id="browser-smoke-result">(.*?)</pre>',
        completed.stdout,
        flags=re.DOTALL,
    )
    detail = html.unescape(result.group(1)) if result else "browser result marker missing"
    raise RuntimeError(
        f"{name} browser smoke failed: {detail}; exit={completed.returncode}; "
        f"stdout={completed.stdout[-1600:]}; stderr={completed.stderr[-1200:]}"
    )


DETAIL_PAGE = r"""<!doctype html>
<html><head><title>UI browser smoke</title></head><body data-acs-main-page="acs_summary.html">
<h1>UI browser smoke</h1>
<div class="result-summary">
  <h2>Result Summary</h2>
  <p>For details on Rule Results Status, refer to
    <a href="https://example.test/RuleBasedGuide.md" target="_blank">the guide</a>.</p>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>10</td></tr>
    <tr><td>Passed</td><td>7</td></tr>
    <tr><td>Failed</td><td>2</td></tr>
    <tr><td>Failed with Waiver</td><td>0</td></tr>
    <tr><td>CUSTOM REVIEW</td><td>1</td></tr>
  </tbody></table>
</div>
<div class="chart-container"><div id="detail-chart-probe" style="width:320px">chart</div></div>
<div class="detailed-summary">
  <article class="acs-result-group acs-collapsible acs-collapsed"
           data-acs-default-collapsed="true">
    <div class="acs-case-overview"><div class="acs-case-title">Smoke group</div></div>
    <button type="button" class="acs-group-toggle" aria-expanded="false">Show details</button>
    <table><thead><tr><th>Description</th><th>Test Result</th><th>Reason</th></tr></thead><tbody>
      <tr id="passed-row"><td>Passing outcome</td><td>PASSED</td><td>Short reason</td></tr>
      <tr id="custom-row"><td>Future outcome</td><td>CUSTOM REVIEW</td>
        <td>This deliberately long diagnostic reason verifies that SCT and FWTS reports hide
        verbose evidence initially.<br>It retains every original character for explicit
        on-demand expansion by the report reader.</td></tr>
    </tbody></table>
  </article>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var buttons = Array.prototype.slice.call(document.querySelectorAll(".acs-status-filter"));
    function buttonStartingWith(label) {
      return buttons.find(function (button) { return button.textContent.indexOf(label) === 0; });
    }
    var all = buttonStartingWith("All outcomes ");
    var passed = buttonStartingWith("Passed ");
    var custom = buttonStartingWith("CUSTOM REVIEW ");
    expect(all && all.textContent === "All outcomes 2", "All filter must count two outcomes");
    expect(passed && passed.textContent === "Passed 1", "Passed filter must be generated");
    expect(custom && custom.textContent === "CUSTOM REVIEW 1", "Future status filter must be generated");
    var compact = document.querySelector(".acs-compact-summary");
    var summaryRows = Array.prototype.slice.call(compact.querySelectorAll(".acs-progress-row"));
    var passedSummary = document.querySelector('[data-acs-summary-status="pass"]');
    var waiverSummary = document.querySelector('[data-acs-summary-status="fail-waiver"]');
    var customSummary = document.querySelector('[data-acs-summary-status="status-custom-review"]');
    expect(compact && document.querySelectorAll(".acs-compact-summary").length === 1,
      "Detailed report must contain one compact test-result summary");
    expect(compact.querySelector("h2").textContent === "Test-result summary",
      "Old Result Summary heading must be replaced");
    expect(compact.querySelector(".acs-compact-summary-total").textContent ===
      "10 suite-reported tests", "Suite total must be shown in the compact header");
    expect(summaryRows.length === 4, "Every source status, including zero and dynamic rows, must remain");
    expect(passedSummary.querySelector(".acs-progress-track").getAttribute("aria-valuenow") === "7" &&
      passedSummary.querySelector(".acs-progress-track").getAttribute("aria-valuemax") === "10",
      "Passed progress must expose the source count and suite total");
    expect(passedSummary.querySelector(".acs-progress-fill").style.width === "70%",
      "Passed progress width must use the suite-reported ratio");
    expect(window.getComputedStyle(passedSummary.querySelector(".acs-progress-fill")).backgroundColor ===
      "rgb(22, 163, 74)", "Passed progress must retain the existing green");
    expect(waiverSummary && waiverSummary.getAttribute("data-acs-zero") === "true" &&
      waiverSummary.querySelector(".acs-progress-count").textContent === "0" &&
      waiverSummary.querySelector(".acs-progress-fill").style.width === "0%",
      "Zero-count statuses must remain visible with an empty track");
    expect(customSummary && customSummary.querySelector(".acs-progress-label").textContent === "CUSTOM REVIEW",
      "Dynamic summary statuses must retain their source label");
    expect(window.getComputedStyle(customSummary.querySelector(".acs-progress-fill")).backgroundColor ===
      "rgb(100, 116, 139)", "Dynamic summary statuses must use the neutral fallback color");
    expect(compact.querySelector("table.summary-table").classList.contains("acs-summary-source"),
      "Original summary table must remain as the hidden fallback source");
    expect(compact.querySelector(".acs-reference-note a").textContent.indexOf("Rule result status guide") === 0,
      "Rule-status guide must remain in the compact BSA/SBSA-style summary");
    expect(document.querySelector(".acs-filter-scope").textContent.indexOf("Case and subtest outcomes") === 0,
      "Filter outcomes must have an explicit scope label");
    expect(!document.querySelector(".acs-count-scope-note"),
      "Detailed summary must not show the confusing count-scope note");
    expect(document.querySelector(".acs-print-scope-note").textContent.indexOf("every result group") >= 0,
      "All-results print scope must be explained");
    expect(document.querySelector(".acs-print-banner").textContent.indexOf("All-results PDF") === 0,
      "Printed output must explain the all-results scope");
    expect(!document.querySelector(".chart-container") && !document.querySelector(".acs-chart-panel") &&
      !document.querySelector(".acs-overview-grid"),
      "Detailed report must remove the legacy distribution chart and overview layout");
    expect(!document.querySelector(".acs-summary-card"),
      "Detailed report must remove the legacy summary count cards");
    var longReason = document.querySelector("#custom-row .acs-long-reason");
    var shortReason = document.querySelector("#passed-row .acs-long-reason");
    expect(longReason && !longReason.open, "Verbose SCT/FWTS reason must start collapsed");
    expect(shortReason && !shortReason.open, "Short SCT/FWTS reason must also start collapsed");
    expect(document.querySelectorAll(".acs-long-reason").length === 2,
      "Every SCT/FWTS reason must use a disclosure");
    expect(longReason && longReason.textContent.indexOf("retains every original character") >= 0,
      "Collapsed reason must retain its full diagnostic text");
    expect(longReason && longReason.querySelectorAll(".acs-long-reason-text br").length === 1,
      "Collapsed reason must retain original line-break elements");
    if (longReason) {
      longReason.querySelector("summary").click();
      expect(longReason.open, "Long reason must expand when requested");
    }

    custom.click();
    expect(custom.getAttribute("aria-pressed") === "true", "Custom status button must activate");
    expect(document.getElementById("passed-row").classList.contains("acs-filter-hidden"),
      "Nonmatching result must be hidden");
    expect(!document.getElementById("custom-row").classList.contains("acs-filter-hidden"),
      "Matching result must remain visible");
    all.click();
    expect(all.getAttribute("aria-pressed") === "true", "All button must restore every outcome");

    var group = document.querySelector(".acs-result-group.acs-collapsible");
    expect(!group.classList.contains("acs-collapsed") &&
      group.getAttribute("data-acs-default-collapsed") === "false" &&
      group.querySelector(":scope > .acs-group-toggle").getAttribute("aria-expanded") === "true",
      "Every detailed test group must start expanded by default");
    expect(!group.classList.contains("acs-collapsed"),
      "Default PDF output must retain every expanded result group");
    expect(!document.querySelector(".chart-container"), "Print must not recreate the removed chart");

    var printButton = Array.prototype.find.call(document.querySelectorAll(".acs-button"), function (button) {
      return button.textContent.indexOf("Print all results") === 0;
    });
    window.print = function () { document.body.setAttribute("data-print-clicked", "true"); };
    printButton.click();
    expect(document.body.getAttribute("data-print-clicked") === "true", "Print button must call window.print");
    expect(window.getComputedStyle(document.getElementById("custom-row").cells[0]).textAlign === "left",
      "Result text must be left aligned");
    var headingRect = document.querySelector("body > h1").getBoundingClientRect();
    var kicker = document.querySelector("body > .acs-report-kicker");
    var kickerRect = kicker.getBoundingClientRect();
    var subtitleRect = document.querySelector("body > .acs-report-subtitle").getBoundingClientRect();
    expect(Math.abs(headingRect.left - kickerRect.left) < 1 &&
      Math.abs(headingRect.left - subtitleRect.left) < 1,
      "Detailed title, kicker, and subtitle must align to the same page shell");
    var backLink = document.querySelector(".acs-back-to-main");
    expect(backLink && document.querySelectorAll(".acs-back-to-main").length === 1 &&
      backLink.parentElement === kicker &&
      backLink.getAttribute("href") === "acs_summary.html" &&
      !backLink.hasAttribute("target") &&
      backLink.textContent.indexOf("Back to Main Page") >= 0,
      "Detailed reports with a main page must expose one same-tab Back link");
    expect(document.querySelector(".acs-reference-note a").getAttribute("target") === "_blank",
      "Unrelated external documentation links must retain their new-tab behavior");

    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


BSA_PAGE = r"""<!doctype html>
<html><head><title>BSA compact summary smoke</title>
<style>
.pass, .fail, .fail-waiver, .aborted, .skipped, .warning,
.passed-partial, .not-implemented, .pal-not-supported {
  background: rgb(1, 2, 3); text-align: center;
}
</style></head><body data-acs-main-page="acs_summary.html">
<h1>BSA compact summary smoke</h1>
<div class="result-summary"><h2>Result Summary</h2>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>116</td></tr>
    <tr><td>Passed</td><td class="pass">22</td></tr>
    <tr><td>Failed</td><td class="fail">47</td></tr>
    <tr><td>Failed with Waiver</td><td class="fail-waiver">0</td></tr>
    <tr><td>Aborted</td><td class="aborted">0</td></tr>
    <tr><td>Skipped</td><td class="skipped">12</td></tr>
    <tr><td>Warnings</td><td class="warning">12</td></tr>
    <tr><td>Passed (Partial)</td><td class="passed-partial">3</td></tr>
    <tr><td>Not implemented</td><td class="not-implemented">18</td></tr>
    <tr><td>PAL not supported</td><td class="pal-not-supported">2</td></tr>
  </tbody></table>
</div>
<div class="chart-container"><div id="chart-probe" style="width:320px;height:80px">chart</div></div>
<div class="detailed-summary">
  <div class="test-suite-header">Test Suite: GIC</div>
  <div class="test-suite-info"><strong>Test suite info:</strong><ul>
    <li>GIC requirement context.</li><li>Failures can prevent an OS from booting.</li>
  </ul></div>
  <div class="test-suite-description">Description: Generic Interrupt Controller checks</div>
  <table><thead><tr><th>Test Case</th><th>Description</th><th>Result</th></tr></thead>
    <tbody>
      <tr id="partial-row"><td>B_GIC_01</td><td>GIC version</td><td>PASSED(*PARTIAL)</td></tr>
      <tr id="gic-fail-1"><td>B_GIC_02</td><td>GIC failure one</td><td>FAILED</td></tr>
      <tr id="gic-fail-2"><td>B_GIC_03</td><td>GIC failure two</td><td>FAILED</td></tr>
      <tr id="nested-container"><td colspan="3"><table><thead><tr>
        <th>Subtest</th><th>Description</th><th>Result</th>
      </tr></thead><tbody><tr id="gic-nested-fail">
        <td>B_GIC_04.1</td><td>Nested GIC failure</td><td>FAILED</td>
      </tr></tbody></table></td></tr>
      <tr id="gic-waiver"><td>B_GIC_05</td><td>Waived GIC failure</td><td>FAILED WITH WAIVER</td></tr>
    </tbody></table>
  <div class="test-suite-header">Test Suite: MEM_MAP</div>
  <div class="test-suite-description">Description: Memory map checks</div>
  <table><thead><tr><th>Test Case</th><th>Description</th><th>Result</th></tr></thead>
    <tbody><tr><td>B_MEM_01</td><td>Memory range</td><td>PASSED</td></tr></tbody></table>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var summary = document.querySelector(".acs-compact-summary");
    var overview = document.querySelector(".acs-detail-overview");
    var breakdown = document.querySelector(".acs-failure-summary");
    var toolbar = document.querySelector(".acs-toolbar");
    var summaryRect = summary.getBoundingClientRect();
    var overviewRect = overview.getBoundingClientRect();
    var breakdownRect = breakdown.getBoundingClientRect();
    var toolbarRect = toolbar.getBoundingClientRect();
    var kicker = document.querySelector("body > .acs-report-kicker");
    var backLink = document.querySelector(".acs-back-to-main");
    var backRect = backLink && backLink.getBoundingClientRect();
    var rows = Array.prototype.slice.call(summary.querySelectorAll(".acs-progress-row"));
    var titleRect = summary.querySelector("h2").getBoundingClientRect();
    var totalRect = summary.querySelector(".acs-compact-summary-total").getBoundingClientRect();
    expect(!document.querySelector(".chart-container") && !document.querySelector("#chart-probe"),
      "BSA/SBSA legacy chart must be removed from the rendered report");
    expect(summary.querySelector("h2").textContent === "Test-result summary",
      "Compact summary must use the requested heading");
    expect(summary.querySelector(".acs-compact-summary-total").textContent ===
      "116 suite-reported tests", "Compact summary must show the source total");
    expect(rows.length === 9, "Compact BSA/SBSA summary must preserve every status row");
    expect(rows.map(function (row) {
      return row.querySelector(".acs-progress-label").textContent + " " +
        row.querySelector(".acs-progress-count").textContent;
    }).join(" | ") ===
      "Passed 22 | Failed 47 | Failed with Waiver 0 | Aborted 0 | Skipped 12 | " +
      "Warnings 12 | Passed (Partial) 3 | Not implemented 18 | PAL not supported 2",
      "Moving the summary must preserve every status label and count");
    var partialSummary = document.querySelector('[data-acs-summary-status="passed-partial"]');
    expect(partialSummary && partialSummary.querySelector(".acs-progress-label").textContent ===
      "Passed (Partial)", "Partial summary status must use the clearer label");
    expect(window.getComputedStyle(rows[0]).backgroundColor === "rgba(0, 0, 0, 0)" &&
      window.getComputedStyle(rows[0].querySelector(".acs-progress-label")).textAlign !== "center",
      "Suite status CSS must not tint or re-align compact progress rows");
    expect(overview && breakdown && toolbar && overview.firstElementChild === summary &&
      overview.lastElementChild === breakdown && overview.nextElementSibling === toolbar,
      "Detailed summary and failure breakdown must precede the restored toolbar");
    expect(document.querySelectorAll(".acs-detail-overview").length === 1 &&
      overview.children.length === 2 &&
      !overview.contains(toolbar) &&
      !overview.querySelector(".detailed-summary, .acs-empty-state, .acs-print-banner"),
      "The overview must contain only the summary and complete failure breakdown");
    if (window.innerWidth > 1100) {
      expect(summaryRect.right <= breakdownRect.left &&
        Math.abs(summaryRect.top - breakdownRect.top) < 2 &&
        summaryRect.width >= 340 && breakdownRect.width >= 340 &&
        breakdownRect.left - summaryRect.right >= 10,
        "Detailed summary must sit to the left of the failure breakdown on wide screens");
    } else {
      expect(breakdownRect.top >= summaryRect.bottom &&
        Math.abs(breakdownRect.left - summaryRect.left) < 2 &&
        Math.abs(breakdownRect.width - summaryRect.width) < 2,
        "Detailed summary and failure breakdown must stack without overlap on narrow screens");
    }
    expect(summaryRect.left >= overviewRect.left - 1 &&
      summaryRect.right <= overviewRect.right + 1 &&
      breakdownRect.left >= overviewRect.left - 1 && breakdownRect.right <= overviewRect.right + 1 &&
      toolbarRect.top >= Math.max(summaryRect.bottom, breakdownRect.bottom) &&
      Math.abs(toolbarRect.left - overviewRect.left) < 2 &&
      Math.abs(toolbarRect.right - overviewRect.right) < 2,
      "Overview panels and the restored toolbar must remain aligned without overlap");
    expect(titleRect.right <= totalRect.left || totalRect.top >= titleRect.bottom - 1,
      "Compact header title and total must not overlap");
    rows.forEach(function (row) {
      var labelRect = row.querySelector(".acs-progress-label").getBoundingClientRect();
      var trackRect = row.querySelector(".acs-progress-track").getBoundingClientRect();
      var countRect = row.querySelector(".acs-progress-count").getBoundingClientRect();
      expect(trackRect.width >= 100, "Every compact progress track must retain usable width");
      expect(trackRect.left >= summaryRect.left && trackRect.right <= summaryRect.right,
        "Every compact progress track must remain inside the summary");
      expect(labelRect.right <= countRect.left || trackRect.top >= labelRect.bottom - 1,
        "Compact summary labels and counts must not overlap");
    });
    var failureRows = Array.prototype.slice.call(
      breakdown.querySelectorAll(".acs-failure-row")
    );
    var failureList = breakdown.querySelector(".acs-progress-list");
    expect(window.getComputedStyle(failureList).maxHeight === "none" &&
      window.getComputedStyle(failureList).overflowY === "visible" &&
      failureList.scrollHeight <= failureList.clientHeight + 1,
      "Every failure-summary row must remain visible without an internal scroll area");
    expect(breakdown.querySelector("h2").textContent === "Failures by test suite" &&
      breakdown.querySelector(".acs-compact-summary-total").textContent ===
        "2 test suites · 3 failed · 1 waived",
      "Failure breakdown must declare its complete test-suite scope and totals");
    expect(failureRows.length === 2 &&
      failureRows.map(function (row) {
        return row.querySelector(".acs-progress-label").textContent + ":" +
          row.getAttribute("data-acs-failed") + ":" +
          row.getAttribute("data-acs-failed-with-waiver") + ":" +
          row.getAttribute("data-acs-outcomes");
      }).join(" | ") === "GIC:3:1:5 | MEM_MAP:0:0:1",
      "Every BSA test suite, including the zero-failure suite, must appear exactly once");
    expect(document.getElementById("nested-container").getAttribute("data-acs-row-status") === null &&
      document.getElementById("gic-nested-fail").getAttribute("data-acs-row-status") === "fail",
      "Nested BSA leaf failures must count once without counting their container row");
    expect(failureRows[0].querySelector(".acs-progress-track").getAttribute("aria-valuenow") === "4" &&
      failureRows[0].querySelector(".acs-progress-track").getAttribute("aria-valuemax") === "5" &&
      failureRows[0].querySelector(".acs-failure-fill").style.width === "60%" &&
      failureRows[0].querySelector(".acs-failure-fill-waiver").style.width === "20%" &&
      failureRows[1].getAttribute("data-acs-zero") === "true",
      "Failure tracks must use per-suite outcome ratios and preserve waived failures separately");
    expect(document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      "Compact summary must not create page-level horizontal overflow");
    expect(backLink && document.querySelectorAll(".acs-back-to-main").length === 1 &&
      backLink.parentElement === kicker &&
      backLink.getAttribute("href") === "acs_summary.html" &&
      !backLink.hasAttribute("target") && backRect.height >= 35 &&
      backRect.left >= kicker.getBoundingClientRect().left - 1 &&
      backRect.right <= kicker.getBoundingClientRect().right + 1,
      "Back to Main Page must remain accessible and contained at every viewport");
    var groups = Array.prototype.slice.call(document.querySelectorAll(".acs-result-group"));
    expect(groups.length === 2 && groups.every(function (group) {
      return group.classList.contains("acs-collapsible") && !group.classList.contains("acs-collapsed");
    }), "Small BSA groups must be collapsible but expanded by default");
    expect(groups.length === 2 && groups.every(function (group) {
      return group.querySelector(":scope > .acs-case-overview");
    }), "Every BSA suite must use the shared context-card format");
    var firstGroup = groups[0];
    expect(firstGroup && firstGroup.querySelector(".acs-case-eyebrow").textContent === "Test suite" &&
      firstGroup.querySelector(".acs-case-title").textContent === "GIC",
      "BSA suite context must be normalized without the duplicate SUITE label");
    expect(window.getComputedStyle(firstGroup.querySelector(".acs-case-eyebrow")).color ===
      "rgb(23, 92, 211)", "BSA context card must use the shared accent color");
    expect(window.getComputedStyle(firstGroup.querySelector(".acs-case-title")).fontSize === "18px",
      "BSA context card must use the shared title typography");
    var sourceHeader = firstGroup && firstGroup.querySelector(".test-suite-header");
    expect(sourceHeader && sourceHeader.classList.contains("acs-metadata-source") &&
      window.getComputedStyle(sourceHeader, "::before").content === "none",
      "Raw Test Suite header must be retained only as a hidden source without a SUITE badge");
    var infoItems = firstGroup ? firstGroup.querySelectorAll(".acs-meta-list li") : [];
    expect(infoItems.length === 2 && infoItems[0].textContent === "GIC requirement context." &&
      infoItems[1].textContent === "Failures can prevent an OS from booting.",
      "Suite information list items must remain separate and complete");
    expect(firstGroup && firstGroup.querySelector(".acs-case-description").textContent ===
      "Generic Interrupt Controller checks", "Suite description must remain visible");
    var partialPill = document.querySelector("#partial-row .acs-status-pill");
    expect(partialPill && partialPill.textContent === "PASSED (PARTIAL)",
      "BSA partial result pill must use Passed (Partial)");
    var partialFilter = Array.prototype.find.call(document.querySelectorAll(".acs-status-filter"), function (button) {
      return button.textContent.indexOf("Passed (Partial) ") === 0;
    });
    expect(partialFilter && partialFilter.textContent === "Passed (Partial) 1",
      "BSA partial filter must use Passed (Partial)");
    var jumpSelect = document.querySelector(".acs-control select");
    expect(jumpSelect && jumpSelect.previousElementSibling.textContent === "Jump to test suite" &&
      jumpSelect.options[0].textContent === "Choose a test suite…",
      "BSA jump control must say test suite");
    expect(document.querySelectorAll("input[aria-label='Search report rows']").length === 1 &&
      jumpSelect.options.length === 3 &&
      Array.prototype.map.call(jumpSelect.options, function (option) {
        return option.textContent;
      }).join(" | ") === "Choose a test suite… | GIC | MEM_MAP",
      "Moving controls must preserve search and every jump target");
    expect(Array.prototype.map.call(document.querySelectorAll(".acs-actions .acs-button"), function (button) {
      return button.textContent;
    }).join(" | ") === "Expand all | Collapse all | Reset | Print all results / PDF",
      "Moving controls must preserve every report action in order");
    expect(Array.prototype.map.call(document.querySelectorAll(".acs-status-filter"), function (button) {
      return button.textContent;
    }).join(" | ") === "All outcomes 6 | Passed 1 | Failed 3 | Failed with waiver 1 | Passed (Partial) 1" &&
      document.querySelector(".acs-filter-count").textContent === "Matching 6 of 6 outcomes",
      "Moving controls must preserve filter labels, counts, and matching total");
    var collapse = Array.prototype.find.call(document.querySelectorAll(".acs-button"), function (button) {
      return button.textContent === "Collapse all";
    });
    var expand = Array.prototype.find.call(document.querySelectorAll(".acs-button"), function (button) {
      return button.textContent === "Expand all";
    });
    if (collapse && expand && partialFilter && groups.length === 2) {
      collapse.click();
      expect(groups.every(function (group) { return group.classList.contains("acs-collapsed"); }),
        "Collapse all must close every small DT BSA suite");
      partialFilter.click();
      expect(!groups[0].classList.contains("acs-collapsed") &&
        groups[1].classList.contains("acs-filter-hidden"),
        "Filtering must reopen the matching collapsed BSA suite");
      document.querySelector(".acs-status-filter.info").click();
      expect(groups.every(function (group) { return !group.classList.contains("acs-collapsed"); }),
        "Clearing a filter must restore the small-report expanded default");
      collapse.click();
      expand.click();
      expect(groups.every(function (group) { return !group.classList.contains("acs-collapsed"); }),
        "Expand all must reopen every BSA suite");
    }
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


POST_SCRIPT_PAGE = r"""<!doctype html>
<html><head><title>Post-script compact summary smoke</title></head><body>
<h1>Post-script compact summary smoke</h1>
<div class="summary-container"><h2>Result Summary</h2>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>1</td></tr>
    <tr><td>Passed</td><td class="pass">1</td></tr>
  </tbody></table>
</div>
<div class="chart-container">legacy chart</div>
<div class="detailed-container"><h2>Detailed Subtests</h2>
  <h3>post scripts checks: Post script checks from post-script.log</h3>
  <table><thead><tr><th>Result</th></tr></thead>
  <tbody><tr><td>PASSED</td></tr></tbody></table></div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var summary = document.querySelector(".summary-container.acs-compact-summary");
    expect(summary, "Summary-container variant must receive the compact summary");
    expect(summary.querySelector(".acs-compact-summary-total").textContent ===
      "1 suite-reported test", "Singular suite total must use singular test wording");
    expect(!document.querySelector(".chart-container"),
      "Summary-container detail page must remove its legacy chart");
    expect(document.querySelector(".detailed-container > .acs-case-overview .acs-case-title").textContent ===
      "post scripts checks", "Flat Post-script report must use the shared suite context card");
    expect(document.querySelector(".detailed-container > .acs-case-overview .acs-case-description").textContent ===
      "Post script checks from post-script.log", "Post-script description must remain visible");
    var breakdown = document.querySelector(".acs-failure-summary");
    var failureRows = breakdown.querySelectorAll(".acs-failure-row");
    expect(breakdown.getAttribute("data-acs-breakdown-kind") === "test suite" &&
      failureRows.length === 1 &&
      failureRows[0].querySelector(".acs-progress-label").textContent === "post scripts checks" &&
      failureRows[0].getAttribute("data-acs-failed") === "0" &&
      failureRows[0].getAttribute("data-acs-zero") === "true",
      "Pass-only Post-script report must still list its test suite with zero failures");
    expect(!document.querySelector(".acs-back-to-main"),
      "Suite-only detail output must not link to a main page that was not generated");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


COMPRESSED_COUNTS_PAGE = r"""<!doctype html>
<html><head><title>Compressed FWTS counts</title></head><body>
<h1>FWTS Test Summary</h1>
<div class="result-summary"><h2>Result Summary</h2>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>2</td></tr>
    <tr><td>Passed</td><td>0</td></tr>
    <tr><td>Failed</td><td>2</td></tr>
  </tbody></table>
</div>
<div class="detailed-summary">
  <div class="test-suite-header" data-acs-summary-outcomes="2"
       data-acs-summary-failed="2" data-acs-summary-failed-with-waiver="0">
    Test Suite: dmicheck
  </div>
  <div class="test-suite-description">Description: DMI checks</div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead><tbody>
    <tr><td>Two diagnostics represented by this row</td><td>FAILED</td></tr>
  </tbody></table>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var row = document.querySelector(".acs-failure-row");
    expect(row && row.querySelector(".acs-progress-label").textContent === "dmicheck" &&
      row.getAttribute("data-acs-failed") === "2" &&
      row.getAttribute("data-acs-outcomes") === "2" &&
      row.querySelector(".acs-progress-count").textContent === "2",
      "Per-suite parser counts must survive an FWTS row that represents multiple failures");
    expect(document.querySelector(".acs-compact-summary-total").textContent ===
      "2 suite-reported tests" &&
      document.querySelector(".acs-failure-summary .acs-compact-summary-total").textContent ===
        "1 test suite · 2 failed",
      "FWTS failure breakdown must agree with its suite-reported summary");
    expect(document.querySelector(".acs-status-filter.fail").textContent === "Failed 1",
      "Interactive row filters must continue to describe displayed rows");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


CASE_NAV_PAGE = r"""<!doctype html>
<html><head><title>Test case navigation smoke</title></head><body>
<h1>Standalone Test Summary</h1>
<div class="result-summary"><h2>Result Summary</h2>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>2</td></tr><tr><td>Passed</td><td>2</td></tr>
  </tbody></table>
</div>
<div class="detailed-summary">
  <div class="test-suite-header">Test Suite: Network</div>
  <div class="test-suite-info"><strong>Test suite info:</strong><ul><li>Network context.</li></ul></div>
  <div class="test-suite-description">Description: Network validation</div>
  <div class="test-case-header">Test Case: ping_test</div>
  <div class="test-case-description">Description: Ping the gateway</div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead>
    <tbody><tr><td>Ping</td><td>PASSED</td></tr></tbody></table>
  <div class="test-suite-header">Test Suite: Boot sources</div>
  <div class="test-suite-description">Description: Boot source validation</div>
  <div class="test-case-header">Test Case: block_devices</div>
  <div class="test-case-description">Description: Check block devices</div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead>
    <tbody><tr><td>Block device</td><td>PASSED</td></tr></tbody></table>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var select = document.querySelector(".acs-control select");
    expect(select && select.previousElementSibling.textContent === "Jump to test case" &&
      select.options[0].textContent === "Choose a test case…",
      "Standalone jump control must say test case");
    expect(select && select.options[1].textContent === "Network · ping_test" &&
      select.options[2].textContent === "Boot sources · block_devices",
      "Test-case jump control must contain every disambiguated case target");
    if (select) {
      var target = document.getElementById(select.options[2].value);
      target.scrollIntoView = function () { document.body.setAttribute("data-jump-worked", "true"); };
      select.value = select.options[2].value;
      select.dispatchEvent(new Event("change"));
      expect(document.body.getAttribute("data-jump-worked") === "true" && select.value === "",
        "Test-case jump selection must navigate and reset");
    }
    expect(document.querySelectorAll(".acs-case-overview").length === 2,
      "Every standalone case must use the shared context card");
    var firstOverview = document.querySelector(".acs-case-overview");
    expect(firstOverview.querySelector(".acs-case-eyebrow").textContent === "Test case" &&
      firstOverview.querySelector(".acs-case-title").textContent === "ping_test",
      "Case layouts must use the same Test case and title hierarchy");
    var suiteMeta = Array.prototype.find.call(firstOverview.querySelectorAll(".acs-meta-item"),
      function (item) {
        return item.querySelector(".acs-meta-label").textContent === "Test suite";
      });
    expect(suiteMeta && suiteMeta.querySelector(".acs-meta-value").textContent === "Network" &&
      firstOverview.querySelector(".acs-case-eyebrow").textContent.indexOf("Network") < 0,
      "Case overview must show its test-suite identity once in metadata, not in the eyebrow");
    expect(window.getComputedStyle(firstOverview.querySelector(".acs-case-eyebrow")).color ===
      "rgb(23, 92, 211)", "Standalone context card must use the shared accent color");
    expect(window.getComputedStyle(firstOverview.querySelector(".acs-case-title")).fontSize === "18px",
      "Standalone context card must use the shared title typography");
    expect(document.querySelectorAll(".acs-meta-list li").length === 1 &&
      document.querySelector(".acs-meta-list li").textContent === "Network context.",
      "Standalone suite information must move into the context metadata");
    var breakdown = document.querySelector(".acs-failure-summary");
    var breakdownRows = Array.prototype.slice.call(
      breakdown.querySelectorAll(".acs-failure-row")
    );
    expect(breakdown.getAttribute("data-acs-breakdown-kind") === "test case" &&
      breakdownRows.length === 2 && breakdownRows.map(function (row) {
        return row.querySelector(".acs-progress-label").textContent + ":" +
          row.getAttribute("data-acs-failed");
      }).join(" | ") === "Network · ping_test:0 | Boot sources · block_devices:0",
      "Case-layout reports must list every test case, including zero-failure cases");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


METADATA_CONTEXT_PAGE = r"""<!doctype html>
<html><head><title>SCT context smoke</title></head><body>
<h1>SCT Test Summary</h1>
<div class="result-summary"><h2>Result Summary</h2>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>4</td></tr><tr><td>Passed</td><td>2</td></tr>
    <tr><td>Failed</td><td>2</td></tr>
  </tbody></table>
</div>
<div class="detailed-summary">
  <div class="heading">Test Suite Name: <span>GenericTest</span></div>
  <div class="heading">Sub Test Suite: <span>EFICompliantTest</span></div>
  <div class="heading">Test Case: <span>PlatformSpecificElements</span></div>
  <div class="heading">Test Case Description: <span>Check platform elements</span></div>
  <div class="heading">Test Result: <span>PASSED</span></div>
  <div class="test-suite-info"><strong>Test suite info:</strong><ul><li>UEFI context.</li></ul></div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead>
    <tbody><tr><td>Console protocols</td><td>PASSED</td></tr></tbody></table>
  <div class="heading">Test Suite Name: <span>BootServicesTest</span></div>
  <div class="heading">Sub Test Suite: <span>EventServicesTest</span></div>
  <div class="heading">Test Case: <span>CheckEvent</span></div>
  <div class="heading">Test Case Description: <span>Check event services</span></div>
  <div class="heading">Test Result: <span>PASSED</span></div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead>
    <tbody><tr><td>Event services</td><td>PASSED</td></tr></tbody></table>
  <div class="heading">Test Suite Name: <span>GenericTest</span></div>
  <div class="heading">Sub Test Suite: <span>ProtocolTest</span></div>
  <div class="heading">Test Case: <span>CheckProtocol</span></div>
  <div class="heading">Test Case Description: <span>Check protocol services</span></div>
  <div class="heading">Test Result: <span>FAILED</span></div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead>
    <tbody><tr><td>Protocol services</td><td>FAILED WITH WAIVER</td></tr></tbody></table>
  <div class="heading">Test Suite Name: <span>GenericTest</span></div>
  <div class="heading">Sub Test Suite: <span>ProtocolTest</span></div>
  <div class="heading">Test Case: <span>NoSubtests</span></div>
  <div class="heading">Test Case Description: <span>Case without subtest rows</span></div>
  <div class="heading">Test Result: <span>FAILED</span></div>
  <table><thead><tr><th>Description</th><th>Result</th></tr></thead><tbody></tbody></table>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var overviews = document.querySelectorAll(".acs-case-overview");
    var first = overviews[0];
    expect(overviews.length === 4 && first.querySelector(".acs-case-eyebrow").textContent ===
      "Test case" && first.querySelector(".acs-case-title").textContent ===
      "PlatformSpecificElements", "SCT must use the shared Test case hierarchy");
    expect((first.textContent.match(/GenericTest/g) || []).length === 1 &&
      (first.textContent.match(/EFICompliantTest/g) || []).length === 1,
      "SCT suite and sub-suite values must appear only once in visible case metadata");
    expect(first.getAttribute("data-acs-jump-context") === "GenericTest · EFICompliantTest",
      "SCT must retain non-visible context for disambiguated navigation");
    var select = document.querySelector(".acs-control select");
    expect(select && select.previousElementSibling.textContent === "Jump to test case" &&
      select.options[1].textContent ===
      "GenericTest · EFICompliantTest · PlatformSpecificElements",
      "SCT test-case navigation must retain suite context without repeating it in the card");
    expect(window.getComputedStyle(first.querySelector(".acs-case-eyebrow")).color ===
      "rgb(23, 92, 211)", "SCT context card must use the same shared accent color");
    expect(window.getComputedStyle(first.querySelector(".acs-case-title")).fontSize === "18px",
      "SCT context card must use the same shared title typography");
    var breakdown = document.querySelector(".acs-failure-summary");
    var rows = Array.prototype.slice.call(breakdown.querySelectorAll(".acs-failure-row"));
    expect(breakdown.getAttribute("data-acs-breakdown-kind") === "test suite" &&
      breakdown.querySelector(".acs-compact-summary-total").textContent ===
        "2 test suites · 1 failed · 1 waived",
      "SCT failure breakdown must aggregate cases by test suite");
    expect(rows.length === 2 && rows.map(function (row) {
      return row.querySelector(".acs-progress-label").textContent + ":" +
        row.getAttribute("data-acs-group-count") + ":" +
        row.getAttribute("data-acs-failed") + ":" +
        row.getAttribute("data-acs-failed-with-waiver") + ":" +
        row.getAttribute("data-acs-outcomes");
    }).join(" | ") === "GenericTest:3:1:1:3 | BootServicesTest:1:0:0:1",
      "Every SCT case must contribute once, using its case result only when no subtest row exists");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


CARD_SUMMARY_PAGE = r"""<!doctype html>
<html><head><title>Card summary smoke</title></head><body>
<h1>SBMR-IB Test Summary</h1>
<div class="card"><h2>Result Summary</h2>
  <table class="summary-table"><tbody>
    <tr><td>Total Tests</td><td>2</td></tr>
    <tr><td>Passed</td><td>1</td></tr><tr><td>Failed</td><td>1</td></tr>
  </tbody></table>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var card = document.querySelector(".card");
    expect(card.classList.contains("acs-compact-summary") &&
      card.querySelectorAll(".acs-progress-row").length === 2,
      "Card-based suite summaries must use the compact progress view");
    expect(card.querySelector(".acs-compact-summary-total").textContent ===
      "2 suite-reported tests", "Card summary must preserve its source total");
    expect(!document.querySelector(".acs-summary-print-button"),
      "The consolidated Print / PDF action must not appear on suite-summary pages");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


SUMMARY_PAGE = r"""<!doctype html>
<html><head><title>Summary browser smoke</title></head><body>
<div class="header">ACS Summary</div>
<a id="external-doc" href="https://example.test/reference" target="_blank" hidden>Reference</a>
<div class="container">
<section class="system-info"><h2>System Information</h2><table><tbody>
  <tr><th>Vendor</th><td>Example Vendor</td></tr>
  <tr><th>System</th><td>Example System</td></tr>
  <tr><th>SoC Family</th><td>Example SoC</td></tr>
  <tr><th>Firmware Version</th><td>2026.08 (SCP: 2026.08)</td></tr>
  <tr><th>ACS version</th><td>ACS 3.1</td></tr>
  <tr><th>SRS version</th><td>SRS 3.1</td></tr>
  <tr><th>BSA version</th><td>BSA 1.2</td></tr>
  <tr><th>Band</th><td>SystemReady band</td></tr>
  <tr><th>FW source code</th><td>https://example.test/source</td></tr>
  <tr><th>Flashing instructions</th><td>Unknown</td></tr>
  <tr><th>product website</th><td><a href="https://example.test/product">Product page</a></td></tr>
  <tr><th>UEFI Version</th><td>UEFI 2.10</td></tr>
  <tr><th>Partner ticket</th><td>SR-123</td></tr>
</tbody></table></section>
<section class="acs-results-summary"><h2>ACS Results Summary</h2><table><tbody>
  <tr><th>Band</th><td>SystemReady band</td></tr>
  <tr><th>Date</th><td>2026-08-30 12:34:56</td></tr>
  <tr><th>Build identifier</th><td>build-abcdefghijklmnopqrstuvwxyz-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ</td></tr>
  <tr><th rowspan="3">SRS requirements compliance results</th><td>Not Compliant</td></tr>
  <tr><td><strong>Mandatory:</strong> failed: BSA</td></tr>
  <tr><td><strong>Recommended:</strong> not run: SBMR-OOB</td></tr>
</tbody></table></section>
<section class="acs-results-summary"><h2>Extensions</h2><table><tbody>
  <tr><th rowspan="2">BBSR compliance results</th><td>Compliant with Waivers</td></tr>
  <tr><td><strong>Mandatory:</strong> waived: BBSR-TPM</td></tr>
  <tr><th>SCMI compliance results</th><td>Not Run</td></tr>
  <tr><th>Future compliance result</th><td>Unknown</td></tr>
  <tr><th>Optional compliance result</th><td>Compliant</td></tr>
</tbody></table></section>
<section class="acs-results-summary" id="empty-extension"><h2>Optional Extension</h2><table></table></section>
<section class="acs-results-summary" id="future-extension"><h2>Future Extension</h2>
  <p>Future non-table result content must remain visible.</p>
</section>
<section class="summary-section"><h2>Test Summaries</h2>
  <section class="summary" id="bsa_summary"><h2>BSA Test Summary</h2>
    <div class="result-summary"><h2>Result Summary</h2>
      <table class="summary-table"><tbody>
        <tr><td>Total Tests</td><td>2</td></tr><tr><td>Passed</td><td>1</td></tr>
        <tr><td>Passed (Partial)</td><td>1</td></tr>
      </tbody></table>
    </div>
    <p class="details-link"><a href="bsa_detailed.html" target="_blank">old BSA link</a></p>
  </section>
  <section class="summary" id="fwts_summary"><h2>SBBR-FWTS Test Summary</h2>
    <p class="details-link"><a href="fwts_detailed.html" target="_blank">old FWTS link</a></p>
  </section>
  <section class="summary" id="sct_summary"><h2>SBBR-SCT Test Summary</h2>
    <p class="details-link"><a href="sct_detailed.html" target="_blank">old SCT link</a></p>
  </section>
  <section class="summary" id="sbmr_ib_summary"><h2>SBMR-IB Test Summary</h2>
    <div class="card"><table class="summary-table"><tbody>
      <tr><td>Total Tests</td><td>1</td></tr><tr><td>Passed</td><td>1</td></tr>
    </tbody></table></div>
    <p class="details-link"><a href="sbmr_ib_detailed.html" target="_blank">old SBMR link</a></p>
  </section>
  <section class="summary" id="standalone_summary"><h2>Standalone Test Summary</h2>
    <p class="details-link"><a href="standalone_tests_detailed.html" target="_blank">old Standalone link</a></p>
  </section>
</section>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var nav = Array.prototype.slice.call(document.querySelectorAll(".acs-suite-nav a"));
    var standaloneNav = nav.find(function (link) { return link.textContent === "Standalone"; });
    var fwtsNav = nav.find(function (link) { return link.textContent === "SBBR-FWTS"; });
    var sctNav = nav.find(function (link) { return link.textContent === "SBBR-SCT"; });
    var standaloneDetail = document.querySelector("#standalone_summary .details-link a");
    var fwtsDetail = document.querySelector("#fwts_summary .details-link a");
    var sctDetail = document.querySelector("#sct_summary .details-link a");
    var detailLinks = Array.prototype.slice.call(
      document.querySelectorAll(".summary .details-link a")
    );
    expect(nav.length === 5, "Suite navigation must contain every summary");
    expect(detailLinks.length === 5 && detailLinks.every(function (link) {
      return !link.hasAttribute("target");
    }), "Every detailed-report link must open in the current tab");
    expect(document.getElementById("external-doc").getAttribute("target") === "_blank",
      "Same-tab normalization must not change unrelated external links");
    expect(!document.querySelector(".acs-back-to-main"),
      "The main summary page must not contain a Back to Main Page link");
    var overview = document.querySelector(".acs-summary-overview");
    var information = overview && overview.querySelector(".acs-information-overview");
    var sourceInformationTable = information && information.querySelector("table");
    var fields = information ? Array.prototype.slice.call(
      information.querySelectorAll(".acs-information-field")
    ) : [];
    var sourcePairs = sourceInformationTable ? Array.prototype.map.call(
      sourceInformationTable.querySelectorAll("tr"), function (row) {
        return row.querySelector("th").textContent.trim() + "=" +
          row.querySelector("td").textContent.trim();
      }
    ) : [];
    var generatedPairs = fields.slice().sort(function (left, right) {
      return Number(left.getAttribute("data-acs-source-row")) -
        Number(right.getAttribute("data-acs-source-row"));
    }).map(function (field) {
      return field.querySelector("dt").textContent.trim() + "=" +
        field.querySelector("dd").textContent.trim();
    });
    expect(overview && document.querySelectorAll(".acs-summary-overview").length === 1 &&
      information && fields.length === 13 && sourcePairs.join(" | ") === generatedPairs.join(" | "),
      "Design 3 must preserve every System Information label and value exactly once");
    expect(sourceInformationTable.getAttribute("aria-hidden") === "true" &&
      window.getComputedStyle(sourceInformationTable).display === "none" &&
      information.getAttribute("data-acs-source-fields") === "13",
      "Design 3 must retain the complete source table as a hidden no-JavaScript fallback");
    var groupInventory = Array.prototype.map.call(
      information.querySelectorAll(".acs-information-band"), function (band) {
        return band.getAttribute("data-acs-information-group") + ":" +
          Array.prototype.map.call(band.querySelectorAll("dt"), function (term) {
            return term.textContent.trim();
          }).join(",");
      }
    ).join(" | ");
    expect(groupInventory ===
      "platform:Vendor,System,SoC Family | firmware:Firmware Version,UEFI Version | " +
      "standards:Band,ACS version,SRS version,BSA version | " +
      "support:FW source code,Flashing instructions,product website | " +
      "other:Partner ticket",
      "Design 3 must group known, unknown, linked, and future fields without dropping any field");
    var standardsFields = Array.prototype.slice.call(information.querySelectorAll(
      "[data-acs-information-group='standards'] .acs-information-field"
    ));
    var standardsRects = standardsFields.map(function (field) {
      return field.getBoundingClientRect();
    });
    if (window.innerWidth > 900) {
      var platformRects = Array.prototype.map.call(information.querySelectorAll(
        "[data-acs-information-group='platform'] .acs-information-field"
      ), function (field) { return field.getBoundingClientRect(); });
      expect(standardsFields.slice(0, 3).map(function (field) {
        return field.querySelector("dt").textContent.trim();
      }).join("|") === "Band|ACS version|SRS version" &&
        Math.max.apply(null, standardsRects.slice(0, 3).map(function (rect) { return rect.top; })) -
          Math.min.apply(null, standardsRects.slice(0, 3).map(function (rect) { return rect.top; })) < 2 &&
        standardsRects[3].top >= standardsRects[0].bottom &&
        platformRects.length === 3 && platformRects.every(function (rect, index) {
          return Math.abs(rect.left - standardsRects[index].left) < 2;
        }),
      "The first standards row must contain only Band, ACS Version, and SRS Version aligned to the shared columns");
    }
    expect(information.querySelector("[data-acs-unknown='true'] dd").textContent.trim() === "Unknown" &&
      information.querySelector(".acs-information-field a").getAttribute("href") ===
        "https://example.test/product",
      "Unknown values and links must remain visible and intact");
    var resultCards = Array.prototype.slice.call(
      overview.querySelectorAll(".acs-overview-result-card")
    );
    var resultSourcesPreserved = resultCards.every(function (card) {
      var sourceCells = Array.prototype.slice.call(card.querySelectorAll("table td"));
      var omittedBandIndex = -1;
      if (card.getAttribute("data-acs-duplicate-band-omitted") === "true") {
        var bandRow = Array.prototype.find.call(card.querySelectorAll("table tr"), function (row) {
          var term = row.querySelector("th");
          return term && term.textContent.trim().toLowerCase() === "band";
        });
        omittedBandIndex = bandRow ? sourceCells.indexOf(bandRow.querySelector("td")) : -1;
      }
      var generatedValues = Array.prototype.slice.call(
        card.querySelectorAll("[data-acs-source-result]")
      ).sort(function (left, right) {
        return Number(left.getAttribute("data-acs-source-result")) -
          Number(right.getAttribute("data-acs-source-result"));
      });
      return generatedValues.length === sourceCells.length - (omittedBandIndex >= 0 ? 1 : 0) &&
        generatedValues.every(function (value) {
          var index = Number(value.getAttribute("data-acs-source-result"));
          return index !== omittedBandIndex && sourceCells[index] &&
            sourceCells[index].textContent.replace(/\s+/g, " ").trim() ===
              value.textContent.replace(/\s+/g, " ").trim();
        });
    });
    expect(resultCards.length === 2 &&
      resultCards[0].querySelector("h2").textContent.trim() === "ACS Results Summary" &&
      resultCards[1].querySelector("h2").textContent.trim() === "Extensions" &&
      resultCards.every(function (card) {
        var source = card.querySelector("table");
        return source && source.getAttribute("aria-hidden") === "true" &&
          window.getComputedStyle(source).display === "none";
      }) && resultSourcesPreserved &&
      document.querySelector("#empty-extension.acs-overview-source") &&
      window.getComputedStyle(document.getElementById("empty-extension")).display === "none",
      "ACS Results and Extensions must compact while an empty optional section is safely omitted");
    expect(!document.getElementById("future-extension").classList.contains("acs-overview-source") &&
      window.getComputedStyle(document.getElementById("future-extension")).display !== "none" &&
      document.getElementById("future-extension").textContent.indexOf("must remain visible") >= 0,
      "Unsupported future result content must remain visible as a safe legacy fallback");
    var dateText = Array.prototype.map.call(
      resultCards[0].querySelectorAll(".acs-overview-heading-meta .acs-overview-meta-item"),
      function (item) {
        return item.querySelector("dt").textContent.trim() + "=" +
          item.querySelector("dd").textContent.trim();
      }
    ).join(" | ");
    var metaText = Array.prototype.map.call(
      resultCards[0].querySelectorAll(".acs-overview-result-meta .acs-overview-meta-item"), function (item) {
        return item.querySelector("dt").textContent.trim() + "=" +
          item.querySelector("dd").textContent.trim();
      }
    ).join(" | ");
    var statusText = Array.prototype.map.call(
      overview.querySelectorAll(".acs-overview-result-entry"), function (entry) {
        return entry.querySelector(".acs-overview-result-label").textContent.trim() + "=" +
          Array.prototype.map.call(entry.querySelectorAll(".acs-overview-result-value"),
            function (value) { return value.textContent.replace(/\s+/g, " ").trim(); }
          ).join(" / ");
      }
    ).join(" | ");
    expect(dateText === "Date=2026-08-30 12:34:56" &&
      metaText === "Build identifier=build-abcdefghijklmnopqrstuvwxyz-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ" &&
      resultCards[0].getAttribute("data-acs-duplicate-band-omitted") === "true" &&
      (!resultCards[0].querySelector(".acs-overview-result-meta dt") ||
        resultCards[0].querySelector(".acs-overview-result-meta dt").textContent.indexOf("Band") < 0) &&
      statusText.indexOf("Mandatory: failed: BSA") >= 0 &&
      statusText.indexOf("Recommended: not run: SBMR-OOB") >= 0 &&
      statusText.indexOf("BBSR compliance results=Compliant with Waivers") >= 0 &&
      statusText.indexOf("Mandatory: waived: BBSR-TPM") >= 0 &&
      statusText.indexOf("SCMI compliance results=Not Run") >= 0 &&
      statusText.indexOf("Future compliance result=Unknown") >= 0 &&
      statusText.indexOf("Optional compliance result=Compliant") >= 0,
      "Compact result cards must preserve metadata, details, extensions, and Not Run rows");
    var resultRects = resultCards.map(function (card) { return card.getBoundingClientRect(); });
    if (window.innerWidth > 900) {
      expect(resultRects[1].left >= resultRects[0].right &&
        Math.abs(resultRects[0].width / resultRects[1].width - 1.5) < .08,
      "ACS Results and Extensions must use a balanced 60/40 desktop layout");
    } else {
      expect(resultRects[1].top >= resultRects[0].bottom &&
        Math.abs(resultRects[0].width - resultRects[1].width) < 2,
      "ACS Results and Extensions must stack at equal width on narrow screens");
    }
    var srsEntry = Array.prototype.find.call(
      resultCards[0].querySelectorAll(".acs-overview-result-entry"), function (entry) {
        return entry.querySelector(".acs-overview-result-label").textContent.trim() ===
          "SRS requirements compliance results";
      }
    );
    var srsDetails = srsEntry && srsEntry.querySelectorAll(
      ".acs-overview-result-value[data-acs-primary='false']"
    );
    expect(srsEntry && srsDetails.length === 2 &&
      window.getComputedStyle(srsEntry.querySelector(".acs-overview-result-label")).color ===
        "rgb(23, 32, 51)" &&
      Array.prototype.every.call(srsDetails, function (detail) {
        var prefix = detail.querySelector("strong");
        return window.getComputedStyle(detail).color === "rgb(153, 27, 27)" && prefix &&
          window.getComputedStyle(prefix).color === "rgb(23, 32, 51)" &&
          Number(window.getComputedStyle(prefix).fontWeight) >= 700;
      }),
      "Compliance labels must be dark and bold while failure details remain red");
    expect(resultCards[0].getAttribute("data-acs-card-tone") === "fail" &&
      resultCards[1].getAttribute("data-acs-card-tone") === "warn" &&
      window.getComputedStyle(resultCards[0]).borderLeftColor === "rgb(220, 38, 38)" &&
      window.getComputedStyle(resultCards[1]).borderLeftColor === "rgb(249, 115, 22)",
      "Result-card accents must reflect failure and waiver status without replacing its text");
    var summariesHeadingRow = document.querySelector(".summary-section > .acs-summary-heading-row");
    var summariesHeading = summariesHeadingRow && summariesHeadingRow.querySelector(":scope > h2");
    var summaryPrint = summariesHeadingRow &&
      summariesHeadingRow.querySelector(":scope > .acs-summary-print-button");
    var navContainer = document.querySelector(".summary-section > .acs-suite-nav");
    expect(summariesHeading && summaryPrint && summariesHeadingRow.nextElementSibling === navContainer,
      "The print action and suite navigation must follow the Test Summaries heading cleanly");
    expect(summaryPrint.textContent === "Print / PDF" &&
      summaryPrint.getAttribute("aria-label") ===
        "Print the consolidated ACS summary or save it as PDF",
      "The consolidated report must expose one accessible Print / PDF action");
    window.print = function () {
      document.body.setAttribute("data-summary-print-clicked", "true");
    };
    summaryPrint.click();
    expect(document.body.getAttribute("data-summary-print-clicked") === "true",
      "The consolidated Print / PDF action must invoke browser printing");
    var headingRect = summariesHeading.getBoundingClientRect();
    var printRect = summaryPrint.getBoundingClientRect();
    expect(printRect.left >= headingRect.right && printRect.right <= summariesHeadingRow.getBoundingClientRect().right + 1,
      "The Print / PDF action must stay in the upper-right without overlapping the heading");
    expect(fwtsNav && fwtsNav.getAttribute("href") === "#fwts_summary",
      "FWTS navigation must retain its EBBR/SBBR heading prefix");
    expect(sctNav && sctNav.getAttribute("href") === "#sct_summary",
      "SCT navigation must retain its EBBR/SBBR heading prefix");
    expect(fwtsDetail.textContent.indexOf("View SBBR-FWTS details") === 0,
      "FWTS detailed-report link must retain its EBBR/SBBR prefix");
    expect(sctDetail.textContent.indexOf("View SBBR-SCT details") === 0,
      "SCT detailed-report link must retain its EBBR/SBBR prefix");
    expect(standaloneNav && standaloneNav.getAttribute("href") === "#standalone_summary",
      "Standalone navigation link must target its summary");
    expect(standaloneDetail.getAttribute("href") === "standalone_tests_detailed.html",
      "Standalone detailed-report target must be preserved");
    expect(standaloneDetail.textContent.indexOf("View Standalone details") === 0,
      "Standalone detailed-report link must be upgraded");
    var compactSummaries = document.querySelectorAll(".summary-section .acs-compact-summary");
    expect(compactSummaries.length === 2 && !document.querySelector(".acs-summary-card"),
      "Consolidated summary tables must use compact progress summaries instead of cards");
    expect(document.querySelector("#bsa_summary [data-acs-summary-status='passed-partial'] .acs-progress-label").textContent ===
      "Passed (Partial)", "Consolidated partial status must use the clearer label");
    expect(document.querySelector("#sbmr_ib_summary > .card.acs-compact-summary"),
      "SBMR card-shaped summary must also receive the compact progress view");
    var sectionIds = Array.prototype.map.call(
      document.querySelectorAll(".summary-section > .summary[id]"),
      function (section) { return section.id; }
    );
    expect(sectionIds.join(" | ") ===
      "bsa_summary | fwts_summary | sct_summary | sbmr_ib_summary | standalone_summary",
      "Two-column layout must preserve summary order and identity");
    var cards = sectionIds.map(function (id) { return document.getElementById(id); });
    var cardRects = cards.map(function (card) { return card.getBoundingClientRect(); });
    var firstRect = cardRects[0];
    var secondRect = cardRects[1];
    var thirdRect = cardRects[2];
    var fourthRect = cardRects[3];
    var lastRect = cardRects[4];
    var columnCount = window.getComputedStyle(
      document.querySelector(".summary-section")
    ).gridTemplateColumns.split(" ").length;
    var informationColumns = window.getComputedStyle(
      information.querySelector(".acs-information-values")
    ).gridTemplateColumns.split(" ").length;
    var resultRects = resultCards.map(function (card) { return card.getBoundingClientRect(); });
    if (window.innerWidth > 900) {
      expect(informationColumns === (window.innerWidth > 1100 ? 4 : 3) &&
        resultRects[1].left >= resultRects[0].right,
        "Design 3 must use compact field columns and side-by-side result cards");
      expect(Math.abs(firstRect.top - secondRect.top) < 2 && secondRect.left >= firstRect.right,
        "Consolidated suite summaries must form a clean two-card row");
      expect(thirdRect.top >= Math.max(firstRect.bottom, secondRect.bottom) &&
        Math.abs(thirdRect.top - fourthRect.top) < 2 && fourthRect.left >= thirdRect.right &&
        columnCount === 2,
        "Consolidated Test Summaries must continue on a two-column grid");
      expect(document.getElementById("standalone_summary").classList.contains("acs-summary-orphan") &&
        lastRect.top >= Math.max(thirdRect.bottom, fourthRect.bottom) &&
        Math.abs(lastRect.width - firstRect.width) < 2 &&
        Math.abs(lastRect.left - firstRect.left) < 2,
        "An odd final suite summary must align with the left column below paired rows");
    } else {
      expect(informationColumns === (window.innerWidth <= 560 ? 1 : 2) &&
        resultRects[1].top >= resultRects[0].bottom &&
        Math.abs(resultRects[1].left - resultRects[0].left) < 2,
        "Design 3 result cards and fields must stack cleanly on narrow screens");
      expect(cardRects.every(function (rect, index) {
        return index === 0 || rect.top >= cardRects[index - 1].bottom;
      }) && columnCount === 1,
        "Consolidated suite summaries must stack on narrow screens");
      expect(cardRects.every(function (rect) {
        return Math.abs(rect.left - firstRect.left) < 2 &&
          Math.abs(rect.width - firstRect.width) < 2;
      }), "Every narrow suite summary, including the orphan, must share one width");
    }
    expect(document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      "Two-column summary layout must not create page-level horizontal overflow");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


BAND_MISMATCH_PAGE = r"""<!doctype html>
<html><head><title>Band mismatch browser smoke</title></head><body>
<div class="header">ACS Summary</div>
<div class="container">
<section class="system-info"><h2>System Information</h2><table><tbody>
  <tr><th>Vendor</th><td>Example Vendor</td></tr>
  <tr><th>Band</th><td>Unknown</td></tr>
</tbody></table></section>
<section class="acs-results-summary"><h2>ACS Results Summary</h2><table><tbody>
  <tr><th>Band</th><td>SystemReady Devicetree band</td></tr>
  <tr><th>Date</th><td>2026-08-31 00:00:00</td></tr>
  <tr><th>SRS requirements compliance results</th><td>Compliant</td></tr>
</tbody></table></section>
</div>
<script>
window.addEventListener("load", function () {
  window.setTimeout(function () {
    var failures = [];
    function expect(condition, message) { if (!condition) { failures.push(message); } }
    var card = document.querySelector(".acs-overview-result-card");
    var meta = Array.prototype.map.call(
      card.querySelectorAll(".acs-overview-result-meta .acs-overview-meta-item"),
      function (item) {
        return item.querySelector("dt").textContent.trim() + "=" +
          item.querySelector("dd").textContent.trim();
      }
    ).join(" | ");
    expect(meta === "Band=SystemReady Devicetree band" &&
      !card.hasAttribute("data-acs-duplicate-band-omitted"),
      "A distinct ACS Results Band must remain visible when the System Information value differs");
    var headingDate = card.querySelector(".acs-overview-heading-meta .acs-overview-meta-item");
    expect(headingDate && headingDate.querySelector("dt").textContent.trim() === "Date" &&
      headingDate.querySelector("dd").textContent.trim() === "2026-08-31 00:00:00",
      "A mismatch must not prevent Date from moving beside the ACS Results heading");
    document.documentElement.setAttribute("data-browser-smoke", failures.length ? "FAIL" : "PASS");
    var output = document.createElement("pre");
    output.id = "browser-smoke-result";
    output.textContent = failures.length ? failures.join(" | ") : "PASS";
    document.body.appendChild(output);
  }, 100);
});
</script>
</body></html>"""


def main() -> int:
    """Generate synthetic reports and execute their interactions in Chromium."""
    browser = _chromium_binary()
    enhance_html_report = _load_enhancer()
    image_chart = (
        '<!doctype html><html><head><title>Chart stripping</title></head><body>'
        '<div class="chart-container"><img src="data:image/png;base64,AA=="></div>'
        '<div class="detailed-summary"></div></body></html>'
    )
    stripped_detail = enhance_html_report(image_chart, suite_type="bsa")
    if '<div class="chart-container"' in stripped_detail:
        raise RuntimeError("detailed report retained its legacy chart image payload")
    summary_with_chart = enhance_html_report(
        image_chart.replace('<div class="detailed-summary"></div>', ""),
        suite_type="bsa",
    )
    if '<div class="chart-container"' not in summary_with_chart:
        raise RuntimeError("suite-summary chart markup changed outside detailed-report scope")
    temp_root = Path(os.getcwd())
    with tempfile.TemporaryDirectory(prefix="report_ui_browser_", dir=temp_root) as temp_name:
        directory = Path(temp_name)
        sct_detail = enhance_html_report(DETAIL_PAGE, suite_type="sct")
        fwts_detail = enhance_html_report(DETAIL_PAGE, suite_type="fwts")
        bsa_detail = enhance_html_report(BSA_PAGE, suite_type="bsa")
        post_script_detail = enhance_html_report(POST_SCRIPT_PAGE, suite_type="post-script")
        compressed_counts = enhance_html_report(COMPRESSED_COUNTS_PAGE, suite_type="fwts")
        case_navigation = enhance_html_report(CASE_NAV_PAGE, suite_type="standalone")
        metadata_context = enhance_html_report(METADATA_CONTEXT_PAGE, suite_type="sct")
        card_summary = enhance_html_report(CARD_SUMMARY_PAGE, suite_type="sbmr")
        summary = enhance_html_report(SUMMARY_PAGE, page_type="acs-summary")
        band_mismatch = enhance_html_report(BAND_MISMATCH_PAGE, page_type="acs-summary")
        _run_page(browser, directory, "sct_detail", sct_detail)
        _run_page(browser, directory, "fwts_detail", fwts_detail)
        _run_page(browser, directory, "bsa_detail", bsa_detail)
        _run_page(browser, directory, "bsa_detail_tablet", bsa_detail, "1000,900")
        _run_page(browser, directory, "bsa_detail_mobile", bsa_detail, "480,900")
        _run_page(browser, directory, "post_script_detail", post_script_detail)
        _run_page(browser, directory, "compressed_fwts_counts", compressed_counts)
        _run_page(browser, directory, "case_navigation", case_navigation)
        _run_page(browser, directory, "metadata_context", metadata_context)
        _run_page(browser, directory, "card_summary", card_summary)
        _run_page(browser, directory, "summary", summary, "1600,900")
        _run_page(browser, directory, "summary_tablet", summary, "1000,900")
        _run_page(browser, directory, "summary_mobile", summary, "480,900")
        _run_page(browser, directory, "band_mismatch", band_mismatch, "1000,900")
    print("report UI browser smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
