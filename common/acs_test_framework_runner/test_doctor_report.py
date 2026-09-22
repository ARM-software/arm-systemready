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

"""Test Doctor's explanations, HTML report and checks of saved JSON, HTML and PDF.

These tests check Doctor, not the separate production parser fixes. Small
temporary reports include correct examples and deliberate errors. Fake browser
and PDF responses test Doctor's decisions without requiring those tools here;
real browser and PDF checks belong to Doctor's optional visual check group.
"""

from collections import Counter
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock
from unittest.mock import patch
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

# Import Doctor from this checkout, not an installed or neighbouring copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "log_parser"))
from doctor_checks.core import Context, Finding
from doctor_checks.report import describe_finding, describe_group, render_html
from doctor_checks import artifacts as doctor_artifacts, artifacts as visual


# Report structure, readable explanations and safe display of untrusted text.

class Page(HTMLParser):
    """Read report text and marked elements without a browser or JavaScript."""

    def __init__(self, source):
        """Parse one report and collect its visible text and elements."""
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.nodes = []
        self.stack = []
        self.text = []
        self.hidden_text_depth = 0
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        """Record the element and its position in the parent stack."""
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        node = {"tag": tag, "attrs": attributes,
                "ancestors": tuple(self.stack), "text": []}
        self.nodes.append(node)
        # Remember parent elements so tests can tell visible text from folded details.
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)
        if tag in {"script", "style"}:
            self.hidden_text_depth += 1

    def handle_endtag(self, tag):
        """Close the matching element and restore its parent context."""
        if tag in {"script", "style"}:
            self.hidden_text_depth -= 1
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        """Keep visible text without treating script or style text as results."""
        if not self.hidden_text_depth:
            self.text.append(text)
            for node in self.stack:
                node["text"].append(text)

    def with_class(self, name):
        """Find elements by a CSS class used as a stable report marker."""
        return [(tag, attrs) for tag, attrs in self.elements
                if name in attrs.get("class", "").split()]

    def with_id(self, identifier):
        """Find elements by their unique report identifier."""
        return [(tag, attrs) for tag, attrs in self.elements if attrs.get("id") == identifier]

    def nodes_with_class(self, name):
        """Find marked elements with their text and parent elements attached."""
        return [node for node in self.nodes if name in node["attrs"].get("class", "").split()]


class DoctorReportTests(unittest.TestCase):
    """Check that the HTML report stays clear, complete and safe to open."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="doctor_report_test_")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    @staticmethod
    def finding(status="FAIL", check_id="MERGE_OVERALL_POLICY", **changes):
        """Create one sample finding, with optional changes for each scenario."""
        values = dict(check_id=check_id,
                      status=status,
                      issue="Recommended failure blocks overall SRS",
                      expected="Suite Not Compliant; overall Compliant",
                      actual="Overall Not Compliant",
                      mode="DT",
                      suite="BSA",
                      evidence=[])
        values.update(changes)
        return Finding(**values)

    def render(self, findings, **changes):
        """Render a report in memory and return a helper for checking its HTML."""
        values = dict(metadata={"revision": "ff0cd1d1", "branch": "user/ashsha06/PJ03164-4164"},
                      output_dir=self.output, status="FAIL",
                      counts=Counter(item.status for item in findings),
                      group_titles={(severity, "MERGE_OVERALL_POLICY"):
                                    "Overall SRS compliance does not match the requirement policy"
                                    for severity in ("FAIL", "WARN", "BLOCKED")})
        values.update(changes)
        source = render_html(findings, **values)
        return source, Page(source)

    def test_escapes_finding_metadata_and_attribute_values(self):
        """Check escapes finding metadata and attribute values."""
        attack = '<img src="x" onerror="alert(1)">'
        item = self.finding(issue=attack, expected="Expected <value> & details", actual=attack,
                            mode='DT" onclick="alert(1)', suite=attack,
                            check_id='CHECK" autofocus="x')
        source, page = self.render([item], metadata={"revision": attack, "branch": attack})
        self.assertIn("&lt;img", source)
        self.assertNotIn(attack, source)
        self.assertTrue(all(tag != "img" for tag, _ in page.elements))
        self.assertTrue(all("onclick" not in attrs and "onerror" not in attrs
                            for _, attrs in page.elements))
        record = page.with_class("finding")[0][1]
        self.assertEqual(item.mode, record["data-mode"])
        self.assertEqual(item.suite, record["data-suite"])
        self.assertEqual(item.check_id, record["data-check-id"])

    def test_legacy_title_stays_searchable_and_severities_stay_separate(self):
        """Check legacy title stays searchable and severities stay separate."""
        findings = [
            self.finding(issue="BSA failure"),
            self.finding(issue="SCT incomplete input", suite="SCT"),
            self.finding(status="BLOCKED", issue="Cannot inspect input", mode="SR")
        ]
        _, page = self.render(findings)
        for _, attrs in page.with_class("finding"):
            self.assertIn("overall srs compliance does not match the requirement policy",
                          attrs["data-search"])
        groups = page.with_class("finding-group")
        self.assertEqual(2, len(groups))
        self.assertEqual({"FAIL", "BLOCKED"}, {attrs["data-severity"] for _, attrs in groups})
        self.assertEqual({"MERGE_OVERALL_POLICY"}, {attrs["data-check-id"] for _, attrs in groups})
        self.assertEqual(3, len(page.with_class("finding")))

    def test_topic_explanations_are_visible_outside_collapsed_technical_details(self):
        """Check topic explanations are visible outside collapsed technical details."""
        _, page = self.render([self.finding()])
        self.assertTrue(all(tag == "article" for tag, _ in page.with_class("finding-group")))
        explanations = page.nodes_with_class("group-explanation")
        self.assertEqual(1, len(explanations))
        for explanation in explanations:
            self.assertEqual("dl", explanation["tag"])
            self.assertFalse(any(parent["tag"] == "details" for parent in explanation["ancestors"]))
            text = " ".join(explanation["text"])
            for heading in ("What happened", "Why it matters", "Next step"):
                self.assertIn(heading, text)
        technical = page.with_class("group-checks")
        self.assertEqual(1, len(technical))
        self.assertEqual("details", technical[0][0])
        self.assertNotIn("open", technical[0][1])
        for node in page.nodes_with_class("finding"):
            self.assertEqual("details", node["tag"])
            self.assertTrue(any("group-checks" in parent["attrs"].get("class", "").split()
                                for parent in node["ancestors"]))

    def test_expected_and_actual_are_retained_in_separate_technical_panels(self):
        """Check expected and actual are retained in separate technical panels."""
        item = self.finding(expected="Expected current-run failures: 2",
                            actual="Observed merged failures: 0")
        _, page = self.render([item])
        self.assertEqual(2, len(page.with_class("comparison-panel")))
        text = " ".join(page.text)
        self.assertIn(item.expected, text)
        self.assertIn(item.actual, text)
        self.assertTrue(any(tag == "h4" for tag, _ in page.elements))
        for node in page.nodes_with_class("comparison-panel"):
            self.assertTrue(any(parent["tag"] == "details" for parent in node["ancestors"]))

    def test_schema_checks_share_a_topic_without_merging_assertions_or_severities(self):
        """Check schema checks share a topic without merging assertions or severities."""
        findings = [self.finding(check_id="NATIVE_RAW_SCHEMA", suite="SCT"),
                    self.finding(check_id="ARTIFACT.SCHEMA", suite="FWTS"),
                    self.finding(check_id="ARTIFACT.SCHEMA", status="WARN", suite="SCT")]
        _, page = self.render(findings)
        groups = page.with_class("finding-group")
        self.assertEqual(2, len(groups))
        failed = [attrs for _, attrs in groups if attrs["data-severity"] == "FAIL"]
        self.assertEqual(1, len(failed))
        self.assertEqual({"NATIVE_RAW_SCHEMA", "ARTIFACT.SCHEMA"},
                         set(failed[0]["data-check-id"].split()))
        self.assertEqual("2", failed[0]["data-total"])
        self.assertEqual(Counter((item.status, item.check_id) for item in findings),
                         Counter((attrs["data-severity"], attrs["data-check-id"])
                                 for _, attrs in page.with_class("finding")))

    def test_sbmr_missing_and_unknown_status_share_one_topic_with_four_original_checks(self):
        """Check SBMR missing and unknown status share one topic with four original checks."""
        findings = [self.finding(check_id=check_id, suite=suite, mode="SR",
                                actual="exit=7; merged=None; HTML=None")
                    for check_id in ("raw.missing-status", "raw.unknown-status")
                    for suite in ("SBMR-IB", "SBMR-OOB")]
        _, page = self.render(findings)
        groups = page.with_class("finding-group")
        self.assertEqual(1, len(groups))
        self.assertEqual("4", groups[0][1]["data-total"])
        self.assertEqual({"raw.missing-status", "raw.unknown-status"},
                         set(groups[0][1]["data-check-id"].split()))
        self.assertEqual(Counter((item.check_id, item.suite) for item in findings),
                         Counter((attrs["data-check-id"], attrs["data-suite"])
                                 for _, attrs in page.with_class("finding")))

    def test_warnings_blocked_checks_and_package_rollups_have_separate_sections(self):
        """Check warnings blocked checks and package rollups have separate sections."""
        findings = [self.finding(), self.finding(status="WARN", check_id="raw.coverage"),
                    self.finding(status="BLOCKED", check_id="VISUAL_BROWSER"),
                    self.finding(check_id="ARTIFACT.CONSISTENCY")]
        _, page = self.render(findings)
        locations = {}
        for node in page.nodes_with_class("finding"):
            sections = [ancestor["attrs"].get("id") for ancestor in node["ancestors"]
                        if "findings-section" in ancestor["attrs"].get("class", "").split()]
            self.assertEqual(1, len(sections))
            locations[node["attrs"]["data-check-id"]] = sections[0]
        self.assertEqual(
            {
                "MERGE_OVERALL_POLICY": "issues-section",
                "raw.coverage": "warnings-section",
                "VISUAL_BROWSER": "blocked-section",
                "ARTIFACT.CONSISTENCY": "summaries-section"
            }, locations)

    def test_original_fields_and_evidence_survive_topic_grouping(self):
        """Check original fields and evidence survive topic grouping."""
        findings = [
            self.finding(check_id=check_id,
                         issue="Exact issue " + check_id,
                         expected="Expected <value>\n" + check_id,
                         actual="Actual & mismatch\n" + check_id,
                         evidence=[str(self.output / "evidence" / (check_id + ".log"))])
            for check_id in ("NATIVE_RAW_SCHEMA", "ARTIFACT.SCHEMA", "ARTIFACT.CONSISTENCY",
                             "raw.missing-status", "raw.unknown-status", "UNREGISTERED.CHECK")
        ]
        _, page = self.render(findings)
        records = {
            node["attrs"]["data-check-id"]: node
            for node in page.nodes_with_class("finding")
        }
        self.assertEqual(len(findings), len(records))
        for item in findings:
            node = records[item.check_id]
            text = "".join(node["text"])
            for value in (item.check_id, item.issue, item.expected, item.actual,
                          item.mode, item.suite, Path(item.evidence[0]).name):
                with self.subTest(check=item.check_id, value=value):
                    self.assertIn(value, text)
            self.assertEqual(item.status, node["attrs"]["data-severity"])
            self.assertEqual(item.mode, node["attrs"]["data-mode"])
            self.assertEqual(item.suite, node["attrs"]["data-suite"])

    def test_affected_suites_are_unique_without_rewriting_original_suite_fields(self):
        """Check affected suites are unique without rewriting original suite fields."""
        findings = [self.finding(check_id="HTML_COMPLIANCE_MATCH", suite=suite, mode="SR")
                    for suite in ("SBMR-IB, SBMR-OOB", "SBMR-IB", "SBMR-OOB")]
        _, page = self.render(findings)
        metadata = page.nodes_with_class("group-meta")
        self.assertEqual(1, len(metadata))
        affected = "".join(metadata[0]["text"])
        self.assertEqual(1, affected.count("SBMR-IB"))
        self.assertEqual(1, affected.count("SBMR-OOB"))
        self.assertEqual(Counter(item.suite for item in findings),
                         Counter(attrs["data-suite"] for _, attrs in page.with_class("finding")))

    def test_compliance_example_is_plain_while_technical_comparison_stays_exact(self):
        """Check compliance example is plain while technical comparison stays exact."""
        actual = ("{'badges': {'BSA': {'expected': 'Recommended (Not Run)', "
                  "'actual': 'Recommended (Compliant)'}}, 'tables': {}}")
        item = self.finding(
            check_id="HTML_COMPLIANCE_MATCH",
            suite="BSA",
            issue=
            "full_BSA_empty: summary badges and detail tables must agree with the independent compliance expectation",
            expected="Exactly one correct badge/row for each applicable card/test",
            actual=actual)
        snapshot = deepcopy(item)
        _, page = self.render([item])
        preview = " ".join("".join(node["text"])
                           for node in page.nodes_with_class("topic-examples"))
        for word in ("BSA", "Recommended", "Not Run", "Compliant"):
            self.assertIn(word, preview)
        self.assertNotIn("{'badges'", preview)
        self.assertNotIn("'actual':", preview)
        self.assertNotIn("full_BSA_empty", preview)
        technical = page.nodes_with_class("finding")
        self.assertEqual(1, len(technical))
        text = "".join(technical[0]["text"])
        for value in (item.check_id, item.issue, item.expected, item.actual):
            self.assertIn(value, text)
        self.assertEqual(snapshot, item)

    def test_summary_counters_include_pass_fail_warn_and_blocked(self):
        """Check summary counters include pass fail warn and blocked."""
        findings = [self.finding(status=status, check_id=status + "_CHECK")
                    for status in ("PASS", "PASS", "FAIL", "WARN", "BLOCKED")]
        _, page = self.render(findings)
        metrics = {attrs["data-count-status"]: int(attrs["data-count"])
                   for _, attrs in page.elements if "data-count-status" in attrs}
        self.assertEqual({"PASS": 2, "FAIL": 1, "WARN": 1, "BLOCKED": 1}, metrics)
        self.assertEqual(3, len(page.with_class("finding")))
        self.assertNotIn("PASS",
                         {attrs["data-severity"]
                          for _, attrs in page.with_class("finding-group")})

    def test_all_pass_has_no_issue_groups_but_keeps_verdict_and_counts(self):
        """Check all pass has no issue groups but keeps verdict and counts."""
        source, page = self.render([self.finding(status="PASS")], status="PASS")
        self.assertEqual([], page.with_class("finding-group"))
        self.assertEqual([], page.with_class("finding"))
        self.assertIn("PASS", " ".join(page.text))
        self.assertIn("1", " ".join(page.text))
        self.assertIn("doctor.json", source)
        self.assertIn("doctor.md", source)
        self.assertNotIn("SBMR", " ".join(page.text))

    def test_green_sbmr_observation_never_gets_blanket_non_green_reassurance(self):
        """Check green SBMR observation never gets blanket non green reassurance."""
        item = self.finding(
            check_id="raw.unknown-status",
            suite="SBMR-IB",
            mode="SR",
            actual="exit=0; raw counts={'passed': 1}; merged='Compliant'; HTML='Compliant'")
        _, page = self.render([item])
        explanation = " ".join(text for node in page.nodes_with_class("group-explanation")
                               for text in node["text"]).lower()
        for unsafe in ("sbmr is safe", "not a false green", "not a false pass",
                       "did not publish a green", "no false-green", "no green result",
                       "stopped without publishing"):
            self.assertNotIn(unsafe, explanation)
        self.assertIn("recorded compliant", explanation)
        self.assertNotIn("not evidence of a completed report incorrectly marked compliant",
                         explanation)

    def test_sbmr_stopped_run_explanation_depends_on_every_recorded_observation(self):
        """Check SBMR stopped run explanation depends on every recorded observation."""
        stopped = self.finding(check_id="raw.missing-status", suite="SBMR-IB", mode="SR",
                               actual="exit=7; merged=None; HTML=None")
        green = self.finding(check_id="raw.unknown-status", suite="SBMR-OOB", mode="SR",
                             actual="exit=0; merged='Compliant'; HTML='Compliant'")
        _, stopped_page = self.render([stopped])
        stopped_explanation = " ".join(
            text for node in stopped_page.nodes_with_class("group-explanation")
            for text in node["text"])
        self.assertIn("No completed merged result or HTML status was recorded", stopped_explanation)
        _, mixed_page = self.render([stopped, green])
        mixed_explanation = " ".join(text
                                     for node in mixed_page.nodes_with_class("group-explanation")
                                     for text in node["text"])
        self.assertIn("At least one", mixed_explanation)
        self.assertNotIn("No completed merged result or HTML status was recorded",
                         mixed_explanation)
        self.assertNotIn("not evidence of a completed report incorrectly marked Compliant",
                         mixed_explanation)

    def test_empty_results_do_not_claim_a_pass(self):
        """Check empty results do not claim a pass."""
        _, page = self.render([], status="INCOMPLETE", metadata={})
        self.assertEqual([], page.with_class("finding-group"))
        text = " ".join(page.text)
        self.assertIn("INCOMPLETE", text)
        self.assertIn("Not recorded", text)
        metrics = {attrs["data-count-status"]: int(attrs["data-count"])
                   for _, attrs in page.elements if "data-count-status" in attrs}
        self.assertEqual({"PASS": 0, "FAIL": 0, "WARN": 0, "BLOCKED": 0}, metrics)

    def test_missing_metadata_values_have_a_readable_fallback(self):
        """Check missing metadata values have a readable fallback."""
        _, page = self.render([self.finding()], metadata={})
        text = " ".join(page.text)
        self.assertIn("Not recorded", text)
        self.assertNotIn("undefined", text)
        self.assertNotIn("None", text)

    def test_relative_evidence_links_are_url_encoded_without_changing_labels(self):
        """Check relative evidence links are url encoded without changing labels."""
        evidence = self.output / "evidence" / "DT report #1" / "case & result?.json"
        item = self.finding(evidence=[str(evidence)])
        source, page = self.render([item])
        links = [attrs["href"] for tag, attrs in page.elements if tag == "a" and "href" in attrs]
        self.assertIn("evidence/DT%20report%20%231/case%20%26%20result%3F.json", links)
        self.assertNotIn(evidence.as_uri(), links)
        self.assertIn("case & result?.json", " ".join(page.text))
        self.assertNotIn('href="evidence/DT report #1/', source)

    def test_all_filter_and_action_controls_have_stable_unique_ids(self):
        """Check all filter and action controls have stable unique IDS."""
        _, page = self.render(
            [self.finding(),
             self.finding(status="WARN", mode="SR", suite="SBMR-IB")])
        for identifier in ("doctor-search", "severity-filter", "mode-filter", "suite-filter",
                           "expand-all", "collapse-all", "reset-filters", "print-report"):
            with self.subTest(identifier=identifier):
                self.assertEqual(1, len(page.with_id(identifier)))
        findings = [attrs for _, attrs in page.with_class("finding")]
        self.assertEqual({"DT", "SR"}, {attrs["data-mode"] for attrs in findings})
        self.assertEqual({"BSA", "SBMR-IB"}, {attrs["data-suite"] for attrs in findings})
        self.assertTrue(all(attrs["data-search"] for attrs in findings))
        self.assertTrue(all(attrs["data-check-id"] for attrs in findings))

    def test_no_javascript_still_has_all_explanations_and_native_details(self):
        """Check no javascript still has all explanations and native details."""
        _, page = self.render([self.finding(), self.finding(status="BLOCKED")])
        self.assertEqual(2, len(page.nodes_with_class("group-explanation")))
        for node in page.nodes_with_class("group-explanation") + page.nodes_with_class(
                "group-checks"):
            for ancestor in (*node["ancestors"], node):
                self.assertNotIn("hidden", ancestor["attrs"])
                self.assertNotIn("js-only", ancestor["attrs"].get("class", "").split())
        self.assertTrue(any(tag == "noscript" for tag, _ in page.elements))

    def test_evidence_filename_cannot_become_an_executable_url(self):
        """Check evidence filename cannot become an executable url."""
        _, page = self.render([self.finding(evidence=["javascript:alert(1)"])])
        links = [attrs["href"] for tag, attrs in page.elements if tag == "a" and "href" in attrs]
        self.assertFalse(any(link.lower().startswith("javascript:") for link in links))

    def test_report_has_no_external_script_style_or_font_dependencies(self):
        """Check report has no external script style or font dependencies."""
        source, page = self.render([self.finding()])
        for tag, attrs in page.elements:
            if tag == "script":
                self.assertNotIn("src", attrs)
            if tag == "link":
                self.assertNotIn("stylesheet", attrs.get("rel", "").lower())
        self.assertNotIn("@import", source)
        self.assertNotIn("fonts.googleapis.com", source)
        self.assertNotIn("cdn.jsdelivr.net", source)

    def test_rendering_does_not_mutate_findings_metadata_or_write_artifacts(self):
        """Check rendering does not mutate findings metadata or write artifacts."""
        findings = [self.finding(evidence=[str(self.output / "evidence.json")])]
        metadata = {"revision": "12345", "modes": ["DT", "SR"]}
        snapshot = deepcopy((findings, metadata))
        self.render(findings, metadata=metadata)
        self.assertEqual(snapshot, (findings, metadata))
        self.assertEqual([], list(self.output.iterdir()))


# Plain-language summaries must match the evidence, not assume an outcome.

class DoctorExplanationTests(unittest.TestCase):
    """Check that explanations name the problem without making unsupported claims."""

    @staticmethod
    def finding(identifier="raw.missing-status", status="FAIL", **changes):
        """Start with a recorded rejection and vary the evidence under test."""
        values = dict(
            check_id=identifier,
            status=status,
            issue="Input handling must be safe",
            expected="Reject clearly or keep non-green",
            actual=("exit=7; raw counts={'passed': 0}; merged=None; HTML=None; HTML Failed=None"),
            mode="SR",
            suite="SBMR-IB",
            evidence=["evidence/parser.log"])
        values.update(changes)
        return Finding(**values)

    def test_schema_ids_share_explanation_without_claiming_wrong_results(self):
        """Check schema IDS share explanation without claiming wrong results."""
        items = [
            self.finding(identifier) for identifier in ("NATIVE_RAW_SCHEMA", "ARTIFACT.SCHEMA")
        ]
        description = describe_group([item.check_id for item in items], items)
        self.assertEqual("issues", description["category"])
        self.assertIn("JSON", description["title"])
        self.assertIn("does not prove", description["impact"])
        self.assertIn("not necessarily separate defects", description["next_step"])

    def test_schema_and_parity_headings_use_plain_language(self):
        """Check schema and parity headings use plain language."""
        for identifier, title in (
                ("NATIVE_RAW_SCHEMA", "Some JSON files do not match the expected format"),
                ("ARTIFACT.PARITY", "Report details do not match the source results")):
            with self.subTest(identifier=identifier):
                self.assertEqual(title,
                                 describe_group(identifier, [self.finding(identifier)])["title"])

    def test_html_compliance_topic_names_wrong_labels_not_first_scenario(self):
        """Check HTML compliance topic names wrong labels not first scenario."""
        item = self.finding(
            "HTML_COMPLIANCE_MATCH",
            suite="BSA",
            mode="DT",
            issue=
            "full_BSA_empty: summary badges and detail tables must agree with the independent compliance expectation",
            expected="Exactly one correct badge/row for each applicable card/test",
            actual=
            "{'badges': {'BSA': {'expected': 'Recommended (Not Run)', 'actual': 'Recommended (Compliant)'}}, 'tables': {}}"
        )
        description = describe_group(item.check_id, [item])
        self.assertIn("compliance", description["title"].lower())
        self.assertTrue(any(word in description["title"].lower()
                            for word in ("wrong", "incorrect", "match", "differ", "disagree")))
        self.assertNotIn("full_BSA_empty", description["title"])
        self.assertNotIn("BSA", description["title"])
        observed = describe_finding(item)["observed"]
        for word in ("BSA", "Recommended", "Not Run", "Compliant"):
            self.assertIn(word, observed)
        self.assertTrue(any(word in observed.lower() for word in ("expected", "should")))
        self.assertTrue(
            any(word in observed.lower() for word in ("actual", "shows", "showed", "displayed")))
        self.assertNotIn("{", observed)
        self.assertNotIn("}", observed)
        self.assertNotIn("'actual':", observed)

    def test_html_comparison_omits_matching_detail_rows(self):
        """Check HTML comparison omits matching detail rows."""
        matching = ("SBMR-IB", "Mandatory", "Compliant")
        missing = ("SBMR-OOB", "Mandatory", "Not Compliant (Not Run)")
        item = self.finding("HTML_COMPLIANCE_MATCH", actual=repr({
            "badges": {}, "tables": {"sbmr_detailed.html": {
                "expected": [matching, missing], "actual": [matching]}}}))
        snapshot = deepcopy(item)
        description = describe_finding(item)
        rows = description.get("comparisons", [])
        self.assertEqual(1, len(rows))
        self.assertIn("SBMR-OOB", rows[0][0])
        self.assertIn("Mandatory", rows[0][1])
        self.assertIn("Not Run", rows[0][1])
        self.assertIn("missing", rows[0][2].lower())
        self.assertNotIn("SBMR-IB", description["observed"])
        self.assertEqual(snapshot, item)

    def test_html_comparison_preserves_repeated_missing_detail_rows(self):
        """Check HTML comparison preserves repeated missing detail rows."""
        row = ("SBMR-OOB", "Mandatory", "Not Compliant (Not Run)")
        item = self.finding("HTML_COMPLIANCE_MATCH", actual=repr({
            "badges": {}, "tables": {"sbmr_detailed.html": {
                "expected": [row, row, row], "actual": [row]}}}))
        rows = describe_finding(item).get("comparisons", [])
        self.assertEqual(2, len(rows))
        self.assertEqual(rows[0], rows[1])
        self.assertIn("SBMR-OOB", rows[0][0])
        self.assertIn("missing", rows[0][2].lower())

    def test_html_comparison_preserves_requirement_changes_missing_and_extra_rows(self):
        """Check HTML comparison preserves requirement changes missing and extra rows."""
        item = self.finding("HTML_COMPLIANCE_MATCH", actual=repr({
            "badges": {}, "tables": {"sbmr_detailed.html": {
                "expected": [("SBMR-IB", "Mandatory", "Compliant"),
                             ("SBMR-OOB", "Mandatory", "Not Compliant (Not Run)")],
                "actual": [("SBMR-IB", "Recommended", "Compliant"),
                           ("SBSA", "Recommended", "Compliant")]}}}))
        rows = describe_finding(item).get("comparisons", [])
        self.assertEqual(3, len(rows))
        by_name = {name.rsplit(" · ", 1)[-1]: (wanted, actual) for name, wanted, actual in rows}
        self.assertIn("Mandatory", by_name["SBMR-IB"][0])
        self.assertIn("Recommended", by_name["SBMR-IB"][1])
        self.assertIn("Mandatory", by_name["SBMR-OOB"][0])
        self.assertIn("missing", by_name["SBMR-OOB"][1].lower())
        self.assertIn("no row", by_name["SBSA"][0].lower())
        self.assertIn("Recommended", by_name["SBSA"][1])

    def test_malformed_comparison_data_is_not_executed_and_does_not_crash(self):
        """Check malformed comparison data is not executed and does not crash."""
        cases = (
            '__import__("os").system("DOCTOR_MUST_NOT_EXECUTE")',
            "{'badges': {'BSA':",
            "{'badges': None, 'tables': None}",
            "{'badges': [], 'tables': []}",
            "{'badges': 7, 'tables': 'not a table'}",
            "{'badges': {'BSA': 'invalid'}, 'tables': {'detail.html': None}}",
            "{'badges': {}, 'tables': {'detail.html': {'expected': ['bad', None, 7], 'actual': {}}}}",
        )
        with mock.patch("os.system") as execute:
            for actual in cases:
                with self.subTest(actual=actual):
                    item = self.finding("HTML_COMPLIANCE_MATCH", actual=actual)
                    snapshot = deepcopy(item)
                    result = describe_finding(item)
                    self.assertIsInstance(result["observed"], str)
                    self.assertEqual([], result.get("comparisons", []))
                    self.assertEqual(snapshot, item)
            execute.assert_not_called()

    def test_empty_log_examples_distinguish_no_report_green_and_invented_outcomes(self):
        """Check empty log examples distinguish no report green and invented outcomes."""
        observations = {}
        cases = {
            "rejected":
            "exit=5; raw counts={'passed': 0, 'failed': 0}; merged=None; HTML=None",
            "green":
            "exit=0; raw counts={'passed': 0, 'failed': 0}; merged='Compliant'; HTML='Compliant'",
            "invented":
            "exit=0; raw counts={'passed': 1, 'failed': 0}; merged='Not Compliant'; HTML='Not Compliant'",
        }
        for case, actual in cases.items():
            item = self.finding("raw.empty-log", actual=actual)
            observations[case] = describe_finding(item)["observed"]
            self.assertIn("Not Run", observations[case])
            self.assertNotIn("{'passed'", observations[case])
        self.assertIn("exit code 5", observations["rejected"])
        self.assertIn("no compliance report", observations["rejected"])
        self.assertNotIn("says Compliant", observations["rejected"])
        self.assertIn("says Compliant", observations["green"])
        self.assertNotIn("no compliance report", observations["green"])
        self.assertIn("1 passed", observations["invented"])
        self.assertIn("Not Compliant", observations["invented"])
        self.assertEqual(3, len(set(observations.values())))

    def test_overall_policy_heading_covers_incorrect_pass_and_incorrect_failure(self):
        """Check overall policy heading covers incorrect pass and incorrect failure."""
        headings = []
        for expected, actual in (("compliant", "Not Compliant"), ("not_compliant", "Compliant")):
            item = self.finding("MERGE_OVERALL_POLICY", expected=expected, actual=actual)
            description = describe_group(item.check_id, [item])
            headings.append(description["title"])
            for keyword in ("Mandatory", "Recommended"):
                self.assertIn(keyword, description["impact"])
            rows = describe_finding(item).get("comparisons", [])
            self.assertEqual(1, len(rows))
            self.assertEqual("Compliant" if expected == "compliant" else "Not Compliant",
                             rows[0][1])
            self.assertEqual(actual, rows[0][2])
        self.assertEqual(headings[0], headings[1])
        self.assertNotIn("Recommended", headings[0])
        self.assertNotIn("incorrect pass", headings[0].lower())
        self.assertNotIn("incorrect fail", headings[0].lower())

    def test_stale_rerun_explanations_use_the_recorded_suite_not_bsa(self):
        """Check stale rerun explanations use the recorded suite not BSA."""
        for suite in ("FWTS", "SCT"):
            with self.subTest(suite=suite):
                item = self.finding(
                    "normal.stale-rerun",
                    suite=suite,
                    issue=
                    f"Removing the {suite} raw log must not reuse the previous run's Compliant JSON.",
                    actual="first='Compliant'; rerun='Compliant'; fresh='Not Compliant: not run'")
                finding = describe_finding(item)
                group = describe_group(item.check_id, [item])
                self.assertIn(suite, finding["title"])
                self.assertNotIn("BSA", " ".join(group.values()))
                self.assertNotIn("BSA", finding["observed"])
                self.assertIn("Compliant", finding["observed"])
                self.assertIn("Not Compliant: not run", finding["observed"])
                self.assertTrue(any(word in finding["observed"].lower()
                                    for word in ("previous", "old", "retained")))

    def test_saved_failure_topics_have_specific_explanations(self):
        # Representative failures from a completed DT/SR run are kept here;
        # tests never depend on a user's saved report or an external file path.
        """Check saved failure topics have specific explanations."""
        cases = (
            ("ARTIFACT.CONSISTENCY", "Supplied report package has correctness problems",
             "11 JSON files, 11 HTML pages; JSON schema validation failed: 2", ("report",
                                                                                "package")),
            ("ARTIFACT.SCHEMA", "merged_results.json violates applicable Doctor schema checks",
             "'SRS scope' is a required property", ("json", "format")),
            ("HTML_COMPLIANCE_MATCH", "full_BSA_empty: summary badges and detail tables must agree",
             "{'badges': {'BSA': {'expected': 'Recommended (Not Run)', 'actual': 'Recommended (Compliant)'}}, 'tables': {}}",
             ("compliance", "label")),
            ("MERGE_EXTENSION_AGGREGATION",
             "full_BBSR-FWTS_empty: BBSR aggregates its three members separately from SRS",
             "Compliant", ("bbsr", "extension")),
            ("MERGE_FAILURE_COUNT", "SCT parent-only failures", "Failed/waived=(0, 0)", ("failure",
                                                                                         "failed")),
            ("MERGE_INCOMPLETE_NOT_GREEN",
             "full_BSA_empty: Empty/header-only input was marked as completed",
             "{'BSA': {'requirement': 'Recommended', 'status': 'compliant'}}",
             ("empty", "incomplete", "not run")),
            ("MERGE_INVALID_INPUT_SAFETY",
             "BSA: invalid result shape must not produce a green result", "Compliant",
             ("invalid", "malformed")),
            ("MERGE_OVERALL_POLICY",
             "full_BSA_missing: Recommended result incorrectly blocks overall SRS",
             "Not Compliant : Recommended - (not run: BSA)", ("recommended", "overall")),
            ("NATIVE_EXECUTION", "Public CLI must parse the known native fixture",
             "dt_memory_map_routes; Exit 5\nIndexError: list index out of range",
             ("parser", "command", "sample", "fixture")),
            ("NATIVE_OUTPUT_INVENTORY",
             "Native route must produce exactly its expected suite JSON files",
             "missing=['reserved_memory_map.json']; unexpected=[]", ("file", "output", "json")),
            ("NATIVE_RAW_SCHEMA",
             "Generated raw file must satisfy applicable Doctor schema checks: os_test.json",
             "'Main Readiness Grouping' is a required property", ("json", "format")),
            ("normal.stale-rerun",
             "Removing the BSA raw log must not reuse the previous run's Compliant JSON.",
             "first='Compliant'; rerun='Compliant'; fresh='Not Compliant: not run'",
             ("previous", "old", "stale", "rerun")),
            ("raw.empty-log",
             "Empty or introductory-only input must be Not Run, not invented test outcomes.",
             "exit=5; raw counts={'passed': 0}; merged=None; HTML=None", ("empty", "not run")),
            ("raw.header-only",
             "Empty or introductory-only input must be Not Run, not invented test outcomes.",
             "exit=5; raw counts={'passed': 0}; merged=None; HTML=None", ("introductory", "header",
                                                                          "not run")),
            ("raw.malformed-log",
             "Incomplete or unrecognized raw evidence must not become a green result.",
             "exit=0; raw counts={'passed': 0}; merged='Compliant'; HTML='Compliant'", ("malformed",
                                                                                        "invalid")),
            ("raw.missing-status",
             "Incomplete or unrecognized raw evidence must not become a green result.",
             "exit=0; raw counts={'passed': 0}; merged='Compliant'; HTML='Compliant'",
             ("status", "compliant")),
            ("raw.missing-terminal-result",
             "Incomplete or unrecognized raw evidence must not become a green result.",
             "exit=0; raw counts={'passed': 1}; merged='Compliant'; HTML='Compliant'",
             ("incomplete", "final", "finish", "end")),
            ("raw.sct-parent-failure",
             "Two explicit failed SCT entries must remain non-compliant when subtest detail is absent.",
             "exit=0; raw counts={'failed': 2}; merged='Compliant'; HTML='Compliant'; HTML Failed=2",
             ("sct", "parent")),
            ("raw.truncated-final-subtest",
             "Incomplete or unrecognized raw evidence must not become a green result.",
             "exit=0; raw counts={'passed': 1, 'warnings': 1}; merged='Compliant'; HTML='Compliant'",
             ("truncated", "incomplete", "finish", "end")),
            ("raw.truncated-log",
             "Incomplete or unrecognized raw evidence must not become a green result.",
             "exit=0; raw counts={'passed': 1}; merged='Compliant'; HTML='Compliant'",
             ("truncated", "incomplete", "finish", "end")),
            ("raw.unknown-status",
             "Incomplete or unrecognized raw evidence must not become a green result.",
             "exit=0; raw counts={'passed': 0}; merged='Compliant'; HTML='Compliant'",
             ("status", "compliant")),
            ("waiver.runtime-map-whole-suite",
             "A valid Runtime Device Map whole-suite waiver must not crash on nested failure reasons.",
             'exit=5; merged=None; HTML=None; TypeError: can only concatenate list (not "str") to list',
             ("waiver", "crash")),
            ("waiver.whole-suite-multiple-assertions",
             "A whole-suite waiver must cover both failed FWTS assertions, not just one.",
             "exit=0; raw counts={'failed': 1, 'failed_with_waiver': 1}; merged='Not Compliant: Failed 1'; HTML='Not Compliant'",
             ("waiver", "fwts")),
        )
        for identifier, issue, actual, topic_words in cases:
            with self.subTest(identifier=identifier):
                item = self.finding(identifier, issue=issue, actual=actual)
                snapshot = deepcopy(item)
                description = describe_group(identifier, [item])
                self.assertNotIn("The recorded check did not establish its expected outcome",
                                 description["happened"])
                words = " ".join(description.values()).lower()
                self.assertTrue(any(word in words for word in topic_words), words)
                self.assertTrue(
                    all(isinstance(value, str) and value for value in description.values()))
                self.assertEqual(snapshot, item)

    def test_missing_json_replay_explains_requirement_without_claiming_public_flow_failure(self):
        """Check missing JSON replay explains requirement without claiming public flow failure."""
        items = [self.finding("raw.conditional-execution", status="WARN", suite=suite, mode=mode,
                             actual="Raw control passed; omitted JSON; merged=Compliant")
                 for mode, suite in (("SR", "SBSA"), ("SR", "SBMR-IB"),
                                     ("SR", "SBMR-OOB"), ("DT", "PFDI"))]
        snapshot = deepcopy(items)
        description = describe_group("raw.conditional-execution", items)
        self.assertEqual("Conditional requirements need execution evidence beyond JSON",
                         description["title"])
        self.assertEqual("coverage", description["category"])
        self.assertIn("raw-log control proves", description["happened"])
        self.assertIn("deliberately", description["happened"])
        self.assertIn("disposable", description["happened"])
        for rule in ("SR SBSA is Mandatory", "both interfaces Mandatory",
                     "DT PFDI", "Conditional-Mandatory", "not allow overall Compliant"):
            self.assertIn(rule, description["impact"])
        self.assertIn("directly to the merger", description["happened"])
        self.assertIn("controlled fault injection does not establish a public-flow failure",
                      description["impact"])
        self.assertIn("standalone already rejects parser errors and missing generated output",
                      description["impact"])
        self.assertIn("did not test whether normal runs can reach this state",
                      description["impact"])
        self.assertIn("Verify the public-flow guards", description["next_step"])
        self.assertIn("fact that a required test ran", description["next_step"])
        for item in items:
            finding = describe_finding(item)
            self.assertIn(item.suite, finding["title"])
            self.assertIn("JSON-only merge replay", finding["title"])
            self.assertIn("public-flow failure not established", finding["observed"])
            self.assertLess(len(finding["observed"]), 600)
            self.assertNotIn("{", finding["observed"])
        self.assertEqual(snapshot, items)

    def test_missing_json_control_pass_and_blocked_do_not_claim_lost_requirements(self):
        """Check missing JSON control pass and blocked do not claim lost requirements."""
        for identifier in ("raw.conditional-execution", "raw.conditional-control"):
            for status, title in (("PASS", "Checks completed successfully"),
                                  ("BLOCKED", "Checks could not finish")):
                with self.subTest(identifier=identifier, status=status):
                    item = self.finding(identifier, status=status)
                    description = describe_group(identifier, [item])
                    self.assertEqual(title, description["title"])
                    self.assertNotIn("raw-log control proves", description["happened"])
                    self.assertNotIn("JSON-only merge replay", describe_finding(item)["title"])

    def test_unrelated_warning_and_unexpected_failures_keep_safe_fallbacks(self):
        """Check unrelated warning and unexpected failures keep safe fallbacks."""
        item = self.finding("raw.conditional-execution", status="FAIL")
        failure = describe_group(item.check_id, [item])
        self.assertNotIn("raw-log control proves", failure["happened"])
        self.assertNotIn("JSON-only merge replay", describe_finding(item)["title"])
        item.status = "WARN"
        other = self.finding("FUTURE_CHECK", status="WARN")
        unrelated = describe_group(other.check_id, [other])
        self.assertEqual("coverage", unrelated["category"])
        self.assertNotIn("raw-log control proves", unrelated["happened"])
        mixed = describe_group([item.check_id, other.check_id], [item, other])
        self.assertNotIn("raw-log control proves", mixed["happened"])

    def test_missing_schema_fields_are_named_but_unknown_category_is_not_test_status(self):
        """Check missing schema fields are named but unknown category is not test status."""
        item = self.finding("NATIVE_RAW_SCHEMA", issue="Generated raw file: bsa.json",
                            actual="'Test_suite_info' is a required property")
        description = describe_finding(item)
        self.assertEqual("bsa.json: format check failed", description["title"])
        self.assertIn("Test_suite_info", description["observed"])
        item.actual = "'UNKNOWN' is not one of the allowed category values"
        observed = describe_finding(item)["observed"]
        self.assertIn("category", observed)
        self.assertNotIn("test status", observed)

    def test_all_sbmr_missing_unknown_cases_can_have_specific_heading(self):
        """Check all SBMR missing unknown cases can have specific heading."""
        items = [self.finding(identifier, suite=suite)
                 for identifier in ("raw.missing-status", "raw.unknown-status")
                 for suite in ("SBMR-IB", "SBMR-OOB")]
        description = describe_group([item.check_id for item in items], items)
        self.assertIn("SBMR", description["title"])
        self.assertIn("did not produce a completed report", description["title"])
        self.assertIn("not evidence", description["impact"])
        self.assertNotIn("incorrectly marked Compliant", description["happened"])
        self.assertEqual("Exit code 7; no completed merged result or HTML status was recorded.",
                         describe_finding(items[0])["observed"])

    def test_non_sbmr_and_missing_suite_never_get_sbmr_heading(self):
        """Check non SBMR and missing suite never get SBMR heading."""
        for suite in ("BSA", "SCT", "", "SBMR-INVENTED", "<script>SBMR</script>"):
            for items in ([self.finding(suite=suite)], [self.finding(), self.finding(suite=suite)]):
                with self.subTest(suite=suite, count=len(items)):
                    self.assertNotIn("SBMR", describe_group("raw.missing-status", items)["title"])

    def test_mixed_observations_do_not_claim_all_reports_stopped(self):
        """Check mixed observations do not claim all reports stopped."""
        completed = self.finding(
            actual="exit=0; merged='Compliant'; HTML='Compliant'; HTML Failed=0")
        description = describe_group("raw.missing-status", [self.finding(), completed])
        self.assertIn("Compliant result", description["title"])
        self.assertIn("At least one", description["happened"])
        self.assertNotIn("No completed", description["happened"])
        self.assertNotIn("not evidence", description["impact"])
        self.assertIn("merged JSON says Compliant", describe_finding(completed)["observed"])

    def test_non_green_and_unknown_observations_do_not_claim_protected_rejection(self):
        """Check non green and unknown observations do not claim protected rejection."""
        for actual in ("exit=0; merged='Not Compliant'; HTML='Not Compliant'",
                       "exit=0; merged=None; HTML=None", "exit=7; merged=None", "No output"):
            with self.subTest(actual=actual):
                description = describe_group("raw.missing-status", [self.finding(actual=actual)])
                self.assertNotIn("did not produce", description["title"])
                self.assertNotIn("Compliant result", description["title"])
                self.assertNotIn("No completed", description["happened"])

    def test_status_spelling_and_html_only_compliant_are_handled_conservatively(self):
        """Check status spelling and HTML only compliant are handled conservatively."""
        for actual in ('exit=0; merged="Compliant"; HTML=None',
                       "exit=1; merged=None; HTML='Compliant'",
                       "exit=0; merged='COMPLIANT'; HTML=None"):
            with self.subTest(actual=actual):
                description = describe_group("raw.unknown-status", [self.finding(actual=actual)])
                self.assertIn("Compliant result", description["title"])
        for actual in ("exit=0; merged='Not Compliant'; HTML=None",
                       "exit=0; merged='Compliant with caveats'; HTML=None",
                       "exit=0; raw counts={'status': 'Compliant'}; merged=None; HTML=None"):
            with self.subTest(actual=actual):
                self.assertNotIn("Compliant result", describe_group("raw.missing-status",
                                 [self.finding(actual=actual)])["title"])

    def test_repeated_fields_and_invalid_exit_are_not_treated_as_known_outcomes(self):
        """Check repeated fields and invalid exit are not treated as known outcomes."""
        for actual in ("exit=7; exit=7; merged=None; HTML=None",
                       "exit=7; merged=None; merged=None; HTML=None",
                       "exit=error; merged=None; HTML=None",
                       "prefix exit=7; merged=None; HTML=None"):
            with self.subTest(actual=actual):
                self.assertNotIn("did not produce", describe_group("raw.missing-status",
                                 [self.finding(actual=actual)])["title"])

    def test_literal_none_status_is_not_confused_with_missing_observation(self):
        """Check literal none status is not confused with missing observation."""
        item = self.finding(actual="exit=7; merged='None'; HTML=None")
        self.assertNotIn("did not produce", describe_group(item.check_id, [item])["title"])
        self.assertEqual("Exit code 7; merged JSON says None; HTML status was not recorded.",
                         describe_finding(item)["observed"])

    def test_rollup_is_summary_without_unverified_deduplication_claim(self):
        """Check rollup is summary without unverified deduplication claim."""
        item = self.finding("ARTIFACT.CONSISTENCY")
        description = describe_group(item.check_id, [item])
        self.assertEqual("summaries", description["category"])
        self.assertIn("before treating it as an additional defect", description["impact"])
        self.assertNotIn("repeats", " ".join(description.values()))

    def test_all_eight_saved_warning_instances_have_explanations(self):
        """Check all eight saved warning instances have explanations."""
        samples = [
            ("PACKAGE_ENVIRONMENT", "Recorded Python"),
            ("MERGE_UNAGREED_STATUS_POLICY", "Not covered"),
            ("raw.completion-evidence", "exit=0; merged='Compliant'; HTML='Compliant'"),
            ("raw.coverage", "DTB-ALIGNMENT, NETWORK-BOOT"),
            ("raw.coverage", "OS-TESTS"),
            ("ARTIFACT.COVERAGE",
             "acs_summary.html: aggregate/unmapped chart standalone_summary.html"),
            ("ARTIFACT.COVERAGE",
             "sbmr.html: link outside supplied package not inspected: ../../report.html"),
            ("VISUAL_SCOPE", "Synthetic DT/SR reports"),
        ]
        for identifier, actual in samples:
            with self.subTest(identifier=identifier, actual=actual):
                item = self.finding(identifier, status="WARN", actual=actual)
                description = describe_group(identifier, [item])
                self.assertEqual("coverage", description["category"])
                self.assertNotEqual(item.issue, description["title"])
                self.assertTrue(
                    all(isinstance(value, str) and value for value in description.values()))

    def test_chart_and_external_link_warnings_explain_different_limits(self):
        """Check chart and external link warnings explain different limits."""
        chart = self.finding("ARTIFACT.COVERAGE",
                             status="WARN",
                             actual="aggregate/unmapped chart chart.html")
        link = self.finding("ARTIFACT.COVERAGE", status="WARN",
                            actual="link outside supplied package not inspected: ../outside.html")
        self.assertIn("chart totals", describe_group(chart.check_id, [chart])["title"])
        self.assertIn("outside", describe_group(link.check_id, [link])["title"])
        self.assertIn("does not establish", describe_group(link.check_id, [link])["impact"])
        mixed = describe_group(chart.check_id, [chart, link])
        self.assertIn("comparisons remain unverified", mixed["title"])

    def test_unknown_category_choice_warns_without_claiming_explicit_or_bundled_use(self):
        """Check unknown category choice warns without claiming explicit or bundled use."""
        for identifier in ("NATIVE_CATEGORY_PROVENANCE", "ARTIFACT.CATEGORY_PROVENANCE"):
            with self.subTest(identifier=identifier):
                item = self.finding(
                    identifier,
                    status="WARN",
                    actual="Run category provenance is unavailable; missing-info requirement "
                    "not applied in bsa.json; all other schema checks remain active")
                snapshot = deepcopy(item)
                description = describe_group(identifier, [item])
                self.assertEqual("coverage", description["category"])
                self.assertEqual("The run's category-file choice is not recorded",
                                 description["title"])
                self.assertIn("could not verify whether", description["happened"])
                self.assertIn("All other format checks remain active", description["impact"])
                self.assertIn("Known bundled defaults alone", description["next_step"])
                self.assertIn("do not make", description["next_step"])
                self.assertIn("or cause this warning", description["next_step"])
                self.assertIn("not treated as a failure", describe_finding(item)["observed"])
                self.assertEqual(snapshot, item)

    def test_known_bundled_defaults_are_not_described_as_unknown_category_choice(self):
        """Check known bundled defaults are not described as unknown category choice."""
        item = self.finding(
            "NATIVE_RAW_SCHEMA",
            status="PASS",
            actual="Strict validator exit 1; category source: bundled; missing Test_suite_info "
            "not required at 1 record(s); all applicable Doctor schema checks passed")
        description = describe_group(item.check_id, [item])
        self.assertEqual("Checks completed successfully", description["title"])
        self.assertNotIn("could not verify", description["happened"])
        self.assertNotIn("failure", description["impact"])

    def test_invalid_category_record_remains_failure_not_coverage_warning(self):
        """Check invalid category record remains failure not coverage warning."""
        for identifier in ("NATIVE_CATEGORY_PROVENANCE", "ARTIFACT.CATEGORY_PROVENANCE"):
            with self.subTest(identifier=identifier):
                item = self.finding(identifier, actual="Invalid run category provenance: "
                                    "Explicit category snapshot SHA-256 does not match")
                description = describe_group(identifier, [item])
                self.assertEqual("issues", description["category"])
                self.assertEqual("The run's category-file record cannot be verified",
                                 description["title"])
                self.assertIn("invalid record", description["happened"])
                self.assertNotIn("not treated", description["impact"])
                self.assertEqual(item.actual, describe_finding(item)["observed"])

    def test_explicit_category_missing_info_stays_schema_failure_without_description_requirement(
            self):
        """Check explicit category missing info stays schema failure without description
        requirement.
        """
        item = self.finding("NATIVE_RAW_SCHEMA", issue="Generated raw file: bsa.json",
                            actual="Strict validator exit 1; category source: explicit\n"
                                   "/test_results/0: 'Test_suite_info' is a required property")
        description = describe_group(item.check_id, [item])
        self.assertEqual("issues", description["category"])
        self.assertEqual("Validator reports missing required fields: Test_suite_info.",
                         describe_finding(item)["observed"])
        self.assertNotIn("Description", " ".join(description.values()))

    def test_both_category_record_ids_can_share_an_explanation(self):
        """Check both category record IDS can share an explanation."""
        items = [self.finding(identifier, status="WARN")
                 for identifier in ("NATIVE_CATEGORY_PROVENANCE", "ARTIFACT.CATEGORY_PROVENANCE")]
        description = describe_group([item.check_id for item in items], items)
        self.assertEqual("The run's category-file choice is not recorded", description["title"])
        blocked = self.finding("ARTIFACT.CATEGORY_PROVENANCE", status="BLOCKED")
        self.assertEqual("Checks could not finish",
                         describe_group(blocked.check_id, [blocked])["title"])

    def test_empty_input_warning_uses_actual_not_presumed_green(self):
        """Check empty input warning uses actual not presumed green."""
        item = self.finding("raw.completion-evidence", status="WARN",
                            actual="exit=0; merged='Compliant'; HTML='Compliant'")
        description = describe_group(item.check_id, [item])
        self.assertIn("recorded Compliant", description["happened"])
        self.assertIn("quiet but completed", description["impact"])
        item.actual = "exit=7; merged=None; HTML=None"
        self.assertNotIn("recorded Compliant", describe_group(item.check_id, [item])["happened"])

    def test_blocked_known_ids_do_not_claim_confirmed_defects(self):
        """Check blocked known IDS do not claim confirmed defects."""
        for identifier in ("NATIVE_RAW_SCHEMA", "ARTIFACT.SCHEMA", "raw.missing-status",
                           "ARTIFACT.CONSISTENCY", "ARTIFACT.PARITY", "ARTIFACT.INPUT"):
            with self.subTest(identifier=identifier):
                item = self.finding(identifier, status="BLOCKED", actual="Missing dependency")
                description = describe_group(identifier, [item])
                self.assertEqual("coverage", description["category"])
                self.assertIn("could not finish", description["title"])
                self.assertIn("not a confirmed parser defect", description["impact"])
                self.assertIn("did not complete", describe_finding(item)["observed"])

    def test_unknown_ids_and_empty_groups_keep_safe_fallbacks(self):
        """Check unknown IDS and empty groups keep safe fallbacks."""
        for status, category in (("FAIL", "issues"), ("WARN", "coverage"),
                                 ("BLOCKED", "coverage"), ("PASS", "summaries")):
            with self.subTest(status=status):
                item = self.finding("FUTURE_CHECK", status=status, issue="New check mismatch")
                description = describe_group(item.check_id, [item])
                self.assertEqual(category, description["category"])
                self.assertTrue(description["next_step"])
        self.assertIn("does not establish", describe_group([], [])["impact"])

    def test_unknown_ids_mixed_with_schema_or_status_do_not_inherit_specific_claims(self):
        """Check unknown IDS mixed with schema or status do not inherit specific claims."""
        for identifier in ("NATIVE_RAW_SCHEMA", "raw.missing-status"):
            items = [self.finding(identifier), self.finding("FUTURE_CHECK")]
            description = describe_group([identifier, "FUTURE_CHECK"], items)
            self.assertEqual(items[0].issue, description["title"])

    def test_literal_angle_bracket_name_difference_is_described_as_text(self):
        """Check literal angle bracket name difference is described as text."""
        item = self.finding(
            "ARTIFACT.PARITY",
            issue="Raw and detailed HTML result identities differ",
            expected=
            "{'missing': [('RAS_07 : 1206', 'RAS ERR<n>ADDR.AI bit status check', 'WARNINGS')]}",
            actual=
            "{'extra_or_changed': [('RAS_07 : 1206', 'RAS ERRADDR.AI bit status check', 'WARNINGS')]}"
        )
        observed = describe_finding(item)["observed"]
        self.assertIn("Raw test name: RAS ERR<n>ADDR.AI bit status check", observed)
        self.assertIn("Displayed test name: RAS ERRADDR.AI bit status check", observed)
        self.assertNotIn("test status", observed)

    def test_malicious_strings_remain_plain_text_and_are_never_evaluated(self):
        """Check malicious strings remain plain text and are never evaluated."""
        attack = '<script>alert("test")</script>'
        item = self.finding("FUTURE_CHECK", issue=attack, actual=attack)
        with patch("builtins.eval", side_effect=AssertionError("must not evaluate")), \
                patch("builtins.exec", side_effect=AssertionError("must not execute")), \
                patch("builtins.open", side_effect=AssertionError("must not read evidence")):
            self.assertEqual(attack, describe_group(item.check_id, [item])["title"])
            self.assertEqual(attack, describe_finding(item)["observed"])
            item.check_id = "raw.missing-status"
            item.actual = "exit=__import__('os').system('false'); merged=None; HTML=None"
            self.assertNotIn("did not produce", describe_group(item.check_id, [item])["title"])

    def test_inputs_are_not_mutated_and_mapping_and_object_apis_agree(self):
        """Check inputs are not mutated and mapping and object apis agree."""
        item = self.finding()
        mapping = item.to_dict()
        snapshot = deepcopy((item, mapping))
        self.assertEqual(describe_group([item.check_id], [item]),
                         describe_group(item.check_id, [mapping]))
        self.assertEqual(describe_finding(item), describe_finding(mapping))
        self.assertEqual(snapshot, (item, mapping))


# Saved report checks compare JSON, compliance labels, chart counts and test text.

class ArtifactChecks(unittest.TestCase):
    """Change disposable report copies to test detection without editing real logs."""

    def setUp(self):
        """Build a tiny, consistent report before each test introduces its change."""
        self.temporary = tempfile.TemporaryDirectory(prefix="doctor_artifact_test_")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.parser = self.base / "parser"
        self.report = self.base / "input"
        self.json_dir = self.report / "acs_jsons"
        self.html_dir = self.report / "html_detailed_summaries"
        for directory in (self.parser, self.json_dir, self.html_dir):
            directory.mkdir(parents=True)
        suite = {"canonical": "BSA", "requirement_key": "BSA", "modes": ["SR", "DT"],
                 "schema": "acs-results-schema.json#/definitions/raw", "json_output": "bsa.json",
                 "json_to_html": "bsa/json_to_html.py",
                 "detailed_html": "bsa_detailed.html", "summary_html": "bsa_summary.html"}
        self.write(self.parser / "suite_registry.json", {"suites": [suite]})
        raw_schema = {
            "type": "object",
            "required": ["test_results", "suite_summary"],
            "properties": {
                "test_results": {
                    "type": "array"
                },
                "suite_summary": {
                    "type": "object",
                    "properties": {
                        "Passed": {
                            "type": "integer",
                            "minimum": 0
                        }
                    }
                }
            }
        }
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
                  "required": ["Suite_Name: acs_info"], "definitions": {"raw": raw_schema}}
        self.write(self.parser / "acs-results-schema.json", schema)
        self.raw = {"test_results": [{"Test_suite": "PE", "Test_case": "PE-01",
                                     "Test_case_description": "Check PE", "test_result": "PASSED"}],
                    "suite_summary": {"Total Rules Run": 1, "Passed": 1, "Failed": 0}}
        self.merged = {"Suite_Name: acs_info": {"ACS Results Summary": {
            "Overall Compliance Result": "Compliant",
            "Suite_Name: Mandatory : BSA_compliance": "Compliant"}}, "Suite_Name: BSA": self.raw}
        self.write(self.json_dir / "bsa.json", self.raw)
        self.write(self.json_dir / "merged_results.json", self.merged)
        self.table = (
            '<table class="summary-table"><tr><td>Total Tests</td><td>1</td></tr>'
            '<tr><td>Passed</td><td>1</td></tr><tr><td>Failed</td><td>0</td></tr></table>')
        self.detail = ('<table class="acs-compliance-table"><tr><th>BSA</th><td>Mandatory</td>'
                       '<td>Compliant</td></tr></table>' + self.table +
                       '<table><tr><th>Test Case</th><th>Description</th><th>Result</th></tr>'
                       '<tr><td>PE-01</td><td>Check PE</td><td>PASSED</td></tr></table>')
        self.summary = ('<div class="acs-results-summary"><table><tr>'
                        '<th rowspan="3">SRS requirements compliance results</th>'
                        '<td class="overall-value">Compliant</td></tr></table></div>'
                        '<div class="summary" id="bsa_summary"><span class="acs-suite-compliance" '
                        'title="BSA: Mandatory (Compliant)">Mandatory (Compliant)</span>' +
                        self.table + '</div>')
        (self.html_dir / "acs_summary.html").write_text(self.summary, encoding="utf-8")
        (self.html_dir / "bsa_detailed.html").write_text(self.detail, encoding="utf-8")

    @staticmethod
    def write(path, data):
        """Write a JSON sample inside the test's temporary folder."""
        path.write_text(json.dumps(data), encoding="utf-8")

    def check(self):
        """Inspect the sample report and prove Doctor did not rewrite any inputs."""
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.report.rglob("*") if path.is_file()}
        ctx = Context(self.parser, self.base / "output", report_inputs=[("SR", self.report)])
        doctor_artifacts.run_reports(ctx)
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in self.report.rglob("*") if path.is_file()}
        self.assertEqual(before, after, "Doctor must never rewrite source reports")
        evidence = json.loads(
            (self.base / "output/evidence/artifacts/0_SR/issues.json").read_text())
        return ctx.findings, evidence["issues"]

    def test_clean_consistent_package_passes_read_only(self):
        """Check clean consistent package passes read only."""
        findings, issues = self.check()
        self.assertEqual([], issues)
        self.assertEqual("PASS", findings[0].status)

    def test_malformed_raw_json_is_not_green(self):
        """Check malformed raw JSON is not green."""
        (self.json_dir / "bsa.json").write_text("{broken", encoding="utf-8")
        findings, issues = self.check()
        self.assertIn("Malformed report JSON", [i["issue"] for i in issues])
        self.assertIn("FAIL", [f.status for f in findings])

    def test_schema_error_has_exact_path_and_message(self):
        """Check schema error has exact path and message."""
        self.raw["suite_summary"]["Passed"] = -1
        self.write(self.json_dir / "bsa.json", self.raw)
        _, issues = self.check()
        errors = next(i["errors"] for i in issues if i["issue"] == "JSON schema validation failed")
        self.assertEqual("/suite_summary/Passed", errors[0]["path"])
        self.assertIn("minimum", errors[0]["message"])
        self.assertIn("Invalid suite counter", [i["issue"] for i in issues])

    def require_suite_info(self):
        """Make the temporary schema require category descriptions for this test."""
        schema_path = self.parser / "acs-results-schema.json"
        schema = json.loads(schema_path.read_text())
        schema["definitions"]["raw"]["properties"]["test_results"]["items"] = {
            "type": "object", "required": ["Test_suite_info"],
            "properties": {"Test_suite_info": {"type": "array", "items": {"type": "string"}}}}
        schema["properties"] = {"Suite_Name: BSA": {"$ref": "#/definitions/raw"}}
        self.write(schema_path, schema)

    def category_manifest(self, source):
        """Record whether the temporary report used a supplied category file."""
        config = self.report / "config"
        config.mkdir(exist_ok=True)
        category = {"source": source}
        if source == "explicit":
            # A supplied file without Description must NOT exempt the required result field.
            snapshot = config / "test_category.json"
            self.write(snapshot, {})
            category.update(path="config/test_category.json",
                            sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
        self.write(config / "parser_run.json", {
            "format_version": 1,
            "mode": "SR",
            "test_category": category
        })

    def test_bundled_info_omission_is_applicable_pass_without_provenance_warning(self):
        """Check bundled info omission is applicable pass without provenance warning."""
        self.require_suite_info()
        self.category_manifest("bundled")
        findings, issues = self.check()
        self.assertEqual([], issues)
        self.assertTrue(all(f.status == "PASS" for f in findings))

    def test_legacy_info_omission_warns_without_guessing_bundled_defaults(self):
        """Check legacy info omission warns without guessing bundled defaults."""
        self.require_suite_info()
        findings, issues = self.check()
        self.assertEqual([], issues)
        warning = next(f for f in findings if f.check_id == "ARTIFACT.CATEGORY_PROVENANCE")
        self.assertEqual("WARN", warning.status)
        self.assertIn("bsa.json", warning.actual)
        self.assertIn("merged_results.json", warning.actual)

    def test_explicit_info_omission_fails_even_if_supplied_category_has_no_description(self):
        """Check explicit info omission fails even if supplied category has no description."""
        self.require_suite_info()
        self.category_manifest("explicit")
        findings, issues = self.check()
        self.assertEqual(2, sum(i["issue"] == "JSON schema validation failed" for i in issues))
        self.assertTrue(
            any(f.check_id == "ARTIFACT.SCHEMA" and f.status == "FAIL" for f in findings))

    def test_present_invalid_info_is_not_exempted_for_bundled_or_legacy(self):
        """Check present invalid info is not exempted for bundled or legacy."""
        self.require_suite_info()
        self.raw["test_results"][0]["Test_suite_info"] = 42
        self.write(self.json_dir / "bsa.json", self.raw)
        self.write(self.json_dir / "merged_results.json", self.merged)
        findings, issues = self.check()
        self.assertTrue(any(i["issue"] == "JSON schema validation failed" for i in issues))
        self.assertFalse(any(f.check_id == "ARTIFACT.CATEGORY_PROVENANCE" for f in findings))
        self.category_manifest("bundled")
        findings, _ = self.check()
        self.assertTrue(
            any(f.check_id == "ARTIFACT.SCHEMA" and f.status == "FAIL" for f in findings))

    def test_tampered_category_provenance_fails_without_hiding_other_schema_faults(self):
        """Check tampered category provenance fails without hiding other schema faults."""
        self.require_suite_info()
        self.category_manifest("explicit")
        self.write(self.report / "config/test_category.json", {"tampered": True})
        self.raw["suite_summary"]["Passed"] = -1
        self.write(self.json_dir / "bsa.json", self.raw)
        findings, issues = self.check()
        self.assertTrue(
            any(f.check_id == "ARTIFACT.CATEGORY_PROVENANCE" and f.status == "FAIL"
                for f in findings))
        errors = [
            error for issue in issues if issue["issue"] == "JSON schema validation failed"
            for error in issue["errors"]
        ]
        self.assertTrue(any(error["validator"] == "minimum" for error in errors))

    def test_detail_status_discrepancy_is_detected(self):
        """Check detail status discrepancy is detected."""
        (self.html_dir / "bsa_detailed.html").write_text(self.detail.replace(
            "<td>Compliant</td>", "<td>Not Compliant</td>"), encoding="utf-8")
        _, issues = self.check()
        self.assertIn("Detail compliance differs from merged JSON", [i["issue"] for i in issues])

    def test_overall_verdict_mutation_is_detected_without_changing_suite_results(self):
        """Check overall verdict mutation is detected without changing suite results."""
        for expected, actual in (("Not Compliant: BSA failed", "Compliant"),
                                 ("Compliant", "Not Compliant"),
                                 ("Compliant with Waivers: BSA", "Compliant")):
            with self.subTest(expected=expected, actual=actual):
                self.merged["Suite_Name: acs_info"]["ACS Results Summary"][
                    "Overall Compliance Result"] = expected
                self.write(self.json_dir / "merged_results.json", self.merged)
                (self.html_dir / "acs_summary.html").write_text(self.summary.replace(
                    '<td class="overall-value">Compliant</td>',
                    '<td class="overall-value">' + actual + '</td>'), encoding="utf-8")
                findings, issues = self.check()
                mismatch = next(issue for issue in issues if issue["issue"] ==
                                "Overall HTML compliance differs from merged JSON")
                self.assertEqual(doctor_artifacts.decision(expected), mismatch["expected"])
                self.assertEqual(actual, mismatch["actual"])
                self.assertTrue(any(f.status == "FAIL" for f in findings))

    def test_overall_verdict_must_be_present_and_unambiguous(self):
        """Check overall verdict must be present and unambiguous."""
        marker = ('<th rowspan="3">SRS requirements compliance results</th>'
                  '<td class="overall-value">Compliant</td>')
        for replacement in ("", marker + '</tr><tr>' + marker):
            with self.subTest(replacement=replacement):
                (self.html_dir / "acs_summary.html").write_text(
                    self.summary.replace(marker, replacement), encoding="utf-8")
                _, issues = self.check()
                self.assertIn("Main HTML overall compliance verdict is missing or ambiguous",
                              [issue["issue"] for issue in issues])

    def test_matching_overall_verdict_supports_waivers_and_nested_text(self):
        """Check matching overall verdict supports waivers and nested text."""
        self.merged["Suite_Name: acs_info"]["ACS Results Summary"][
            "Overall Compliance Result"] = "Compliant with Waivers: BSA"
        self.write(self.json_dir / "merged_results.json", self.merged)
        (self.html_dir / "acs_summary.html").write_text(self.summary.replace(
            '<td class="overall-value">Compliant</td>',
            '<td class="overall-value"><strong>Compliant</strong> with waivers</td>'),
                                                        encoding="utf-8")
        _, issues = self.check()
        self.assertEqual([], issues)

    def test_invalid_standalone_results_keep_schema_findings_and_check_later_packages(self):
        """Check invalid standalone results keep schema findings and check later packages."""
        valid_report = self.base / "valid_input"
        shutil.copytree(self.report, valid_report)
        registry = json.loads((self.parser / "suite_registry.json").read_text())
        registry["suites"].append({"canonical": "ONE", "requirement_key": "ONE",
            "modes": ["SR"], "waiver_suite": "Standalone", "json_output": "one.json",
            "schema": "acs-results-schema.json#/definitions/raw"})
        self.write(self.parser / "suite_registry.json", registry)
        for index, value in enumerate((None, 1, "bad", {}, False)):
            with self.subTest(value=value):
                self.write(self.json_dir / "one.json", {"test_results": value, "suite_summary": {}})
                self.merged["Suite_Name: Standalone"] = []
                self.write(self.json_dir / "merged_results.json", self.merged)
                ctx = Context(self.parser, self.base / ("invalid_output_" + str(index)),
                              report_inputs=[("SR", self.report), ("SR", valid_report)])
                doctor_artifacts.run_reports(ctx)
                self.assertTrue(any(f.check_id == "ARTIFACT.SCHEMA" and f.status == "FAIL"
                                    for f in ctx.findings))
                summaries = [f for f in ctx.findings if f.check_id == "ARTIFACT.CONSISTENCY"]
                self.assertEqual(["FAIL", "PASS"], [f.status for f in summaries])
                evidence = json.loads(
                    (ctx.output_dir / "evidence/artifacts/0_SR/issues.json").read_text())
                self.assertTrue(any(error["path"] == "/test_results"
                                    for issue in evidence["issues"] if "errors" in issue
                                    for error in issue["errors"]))

    def test_invalid_results_in_multi_file_aggregate_do_not_crash(self):
        """Check invalid results in multi file aggregate do not crash."""
        registry = json.loads((self.parser / "suite_registry.json").read_text())
        registry["suites"][0]["json_output_patterns"] = ["bsa_extra*.json"]
        self.write(self.parser / "suite_registry.json", registry)
        self.write(self.json_dir / "bsa_extra.json", {"test_results": None, "suite_summary": {}})
        findings, issues = self.check()
        self.assertTrue(
            any(f.check_id == "ARTIFACT.SCHEMA" and f.status == "FAIL" for f in findings))
        self.assertTrue(any(issue["issue"] == "Invalid result collection" for issue in issues))

    def test_detail_missing_not_run_reason_is_detected(self):
        """Check detail missing not run reason is detected."""
        self.merged["Suite_Name: acs_info"]["ACS Results Summary"][
            "Suite_Name: Mandatory : BSA_compliance"] = "Not Compliant: not run"
        self.write(self.json_dir / "merged_results.json", self.merged)
        (self.html_dir / "bsa_detailed.html").write_text(self.detail.replace(
            "<td>Compliant</td>", "<td>Not Compliant</td>"), encoding="utf-8")
        _, issues = self.check()
        self.assertIn("Detail compliance differs from merged JSON", [i["issue"] for i in issues])

    def test_missing_sbmr_peer_row_is_detected(self):
        """Check missing SBMR peer row is detected."""
        records = {
            "SBMRIB": {
                "suite": "SBMR-IB",
                "requirement": "Mandatory",
                "value": "Compliant"
            },
            "SBMROOB": {
                "suite": "SBMR-OOB",
                "requirement": "Mandatory",
                "value": "Not Compliant: not run"
            }
        }
        page = doctor_artifacts.ReportHTML(self.detail.replace("BSA", "SBMR-IB"))
        issues = []
        doctor_artifacts._inspect_html(Path("sbmr_detailed.html"), page, records, {}, [], issues,
                                       [])
        missing = next(i for i in issues if i["issue"] == "Applicable compliance row is missing")
        self.assertEqual("SBMR-OOB", missing["expected"]["suite"])

    def test_missing_mandatory_standalone_row_is_detected(self):
        """Check missing mandatory standalone row is detected."""
        records = {"CAPSULEUPDATE": {"suite": "Capsule Update", "requirement": "Mandatory",
                                     "value": "Not Compliant: not run"}}
        registry = [{"canonical": "CAPSULE-UPDATE", "requirement_key": "Capsule Update",
                     "waiver_suite": "Standalone"}]
        issues = []
        doctor_artifacts._inspect_html(Path("standalone_tests_detailed.html"),
                                       doctor_artifacts.ReportHTML(""), records, {}, registry,
                                       issues, [])
        self.assertIn("Applicable compliance row is missing", [i["issue"] for i in issues])

    def test_summary_badge_and_chart_mutations_are_detected(self):
        """Check summary badge and chart mutations are detected."""
        text = self.summary.replace(">Mandatory (Compliant)<", ">Recommended (Not Compliant)<")
        text = text.replace("<td>Passed</td><td>1</td>", "<td>Passed</td><td>2</td>")
        (self.html_dir / "acs_summary.html").write_text(text, encoding="utf-8")
        _, issues = self.check()
        self.assertIn("Summary badge differs from merged JSON", [i["issue"] for i in issues])
        self.assertIn("Chart differs from raw suite summary", [i["issue"] for i in issues])

    def test_broken_local_link_is_detected(self):
        """Check broken local link is detected."""
        (self.html_dir / "acs_summary.html").write_text(
            self.summary + '<a href="missing_detail.html">Details</a>', encoding="utf-8")
        _, issues = self.check()
        self.assertIn("Broken local HTML link", [i["issue"] for i in issues])

    def test_unreadable_merged_is_not_green(self):
        """Check unreadable merged is not green."""
        (self.json_dir / "merged_results.json").write_text("null", encoding="utf-8")
        _, issues = self.check()
        self.assertIn("Merged JSON is missing or unreadable", [i["issue"] for i in issues])

    def test_unknown_green_and_false_green_failure_are_detected(self):
        """Check unknown green and false green failure are detected."""
        self.raw["test_results"][0]["test_result"] = "UNKNOWN"
        self.raw["suite_summary"] = {"Total Rules Run": 1, "Passed": 0, "Failed": 1}
        self.write(self.json_dir / "bsa.json", self.raw)
        _, issues = self.check()
        self.assertIn("UNKNOWN result is reported as compliant", [i["issue"] for i in issues])
        self.assertIn("Unwaived suite failures are reported as compliant",
                      [i["issue"] for i in issues])

    def test_sr_os_tool_exception_is_not_a_false_alarm(self):
        """Check SR OS tool exception is not a false alarm."""
        issues = []
        raw = {"test_results": [{"SRS scope": "Recommended", "test_result": "FAILED"}],
               "suite_summary": {"total_failed": 1}}
        doctor_artifacts._raw_integrity(Path("os_test.json"), raw,
                                       {"value": "Compliant"}, issues, sr_os=True)
        self.assertEqual([], issues)

    def test_invalid_counter_types_cannot_crash_or_pass(self):
        """Check invalid counter types cannot crash or pass."""
        for value in (float("nan"), float("inf"), True, "1", -1, 1.5):
            with self.subTest(value=value):
                issues = []
                doctor_artifacts._raw_integrity(Path("bsa.json"),
                                               {"suite_summary": {"Passed": value}}, None, issues)
                self.assertIn("Invalid suite counter", [i["issue"] for i in issues])

    def test_broken_schema_evaluator_is_blocked_not_parser_failure(self):
        """Check broken schema evaluator is blocked not parser failure."""
        (self.parser / "acs-results-schema.json").write_text("{broken", encoding="utf-8")
        findings, issues = self.check()
        self.assertIn("Schema validation could not execute", [i["issue"] for i in issues])
        self.assertTrue(all(f.status == "BLOCKED" for f in findings))

    def test_empty_input_and_missing_report_are_explicit(self):
        """Check empty input and missing report are explicit."""
        ctx = Context(self.parser, self.base / "out")
        doctor_artifacts.run_reports(ctx)
        self.assertEqual("WARN", ctx.findings[0].status)
        ctx = Context(self.parser, self.base / "out2", report_inputs=[("DT", self.base / "absent")])
        doctor_artifacts.run_reports(ctx)
        self.assertEqual("BLOCKED", ctx.findings[0].status)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self):
        """Check strict JSON rejects duplicate keys and nonfinite values."""
        for text in ('{"nested":{"result":"PASS","result":"FAIL"}}',
                     '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}',
                     '{"value":1e999}'):
            with self.subTest(text=text):
                path = self.base / "ambiguous.json"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    doctor_artifacts._strict_json(path)
        path.write_text('{"value":[1,0.5,null,true]}', encoding="utf-8")
        self.assertEqual({"value": [1, 0.5, None, True]}, doctor_artifacts._strict_json(path))

    def test_duplicate_raw_json_keys_fail_without_suppressing_html_errors(self):
        """Check duplicate raw JSON keys fail without suppressing HTML errors."""
        (self.json_dir / "bsa.json").write_text('{"x":1,"x":2}', encoding="utf-8")
        (self.html_dir / "acs_summary.html").write_text(self.summary +
                                                        '<a href="missing.html">X</a>')
        findings, issues = self.check()
        self.assertIn("Malformed report JSON", [i["issue"] for i in issues])
        self.assertIn("Broken local HTML link", [i["issue"] for i in issues])
        self.assertTrue(any(f.check_id == "ARTIFACT.JSON" and f.status == "FAIL" for f in findings))
        self.assertTrue(any(f.check_id == "ARTIFACT.HTML" and f.status == "FAIL" for f in findings))

    def test_raw_merged_balanced_status_swap_is_detected(self):
        """Check raw merged balanced status swap is detected."""
        failed = {
            "Test_case": "PE-02",
            "Test_case_description": "Second PE",
            "test_result": "FAILED"
        }
        self.raw["test_results"].append(failed)
        self.raw["suite_summary"] = {"Total Rules Run": 2, "Passed": 1, "Failed": 1}
        self.merged = deepcopy(self.merged)
        self.merged["Suite_Name: BSA"]["test_results"][0]["test_result"] = "FAILED"
        self.merged["Suite_Name: BSA"]["test_results"][1]["test_result"] = "PASSED"
        self.write(self.json_dir / "bsa.json", self.raw)
        self.write(self.json_dir / "merged_results.json", self.merged)
        _, issues = self.check()
        self.assertIn("Raw and merged result records differ", [i["issue"] for i in issues])
        self.assertNotIn("Raw and merged suite counters differ", [i["issue"] for i in issues])
        difference = next(i["actual"] for i in issues
                          if i["issue"] == "Raw and merged result records differ")
        self.assertEqual("/test_results/0/test_result", difference["path"])
        self.assertEqual("PASSED", difference["expected"])
        self.assertEqual("FAILED", difference["actual"])

    def test_merge_enrichment_is_allowed_but_identity_change_is_not(self):
        """Check merge enrichment is allowed but identity change is not."""
        enriched = deepcopy(self.raw)
        enriched["test_results"][0].update({
            "Waivable": "yes",
            "SRS scope": "Mandatory",
            "Test_suite_info": "metadata",
            "Main Readiness Grouping": "PE"
        })
        suite = {"canonical": "BSA"}
        for change, expected in ((False, []), (True, ["Raw and merged result records differ"])):
            with self.subTest(change=change):
                if change:
                    enriched["test_results"][0]["Test_case"] = "other"
                issues = []
                doctor_artifacts._merged_parity(self.report,
                                                {"BSA": [(Path("bsa.json"), self.raw)]},
                                                {"Suite_Name: BSA": enriched}, [suite], issues)
                self.assertEqual(expected, [i["issue"] for i in issues])

    def test_multi_distribution_os_records_do_not_overwrite_each_other(self):
        """Check multi distribution OS records do not overwrite each other."""
        suites = [{
            "canonical": "OS-TESTS",
            "requirement_key": "OS_TEST",
            "json_output": "os_test.json"
        }]
        second = deepcopy(self.raw)
        second["test_results"][0]["Test_case"] = "ubuntu-02"
        inputs = {"OS-TESTS": [(Path("ethtool_test_linux1.json"), self.raw),
                               (Path("ethtool_test_linux2.json"), second)]}
        merged = {"Suite_Name: OS Tests - ethtool_test_linux1": self.raw,
                  "Suite_Name: OS Tests - ethtool_test_linux2": second}
        issues = []
        doctor_artifacts._merged_parity(self.report, inputs, merged, suites, issues)
        self.assertEqual([], issues)
        merged["Suite_Name: OS Tests - ethtool_test_linux1"] = second
        doctor_artifacts._merged_parity(self.report, inputs, merged, suites, issues)
        self.assertIn("Raw and merged result records differ", [i["issue"] for i in issues])

    def test_standalone_aggregate_preserves_all_records_and_waiver_reasons(self):
        """Check standalone aggregate preserves all records and waiver reasons."""
        a = {
            "test_results": [{
                "Test_case": "one",
                "test_result": "FAILED (WITH WAIVER)",
                "waiver_reason": "accepted"
            }]
        }
        b = {"test_results": [{"Test_case": "two", "test_result": "PASSED"}]}
        suites = [{"canonical": name, "waiver_suite": "Standalone"} for name in ("ONE", "TWO")]
        raw = {"ONE": [(Path("one.json"), a)], "TWO": [(Path("two.json"), b)]}
        merged = {"Suite_Name: Standalone": deepcopy(b["test_results"] + a["test_results"])}
        issues = []
        doctor_artifacts._merged_parity(self.report, raw, merged, suites, issues)
        self.assertEqual([], issues)
        merged["Suite_Name: Standalone"][1]["waiver_reason"] = "lost reason"
        doctor_artifacts._merged_parity(self.report, raw, merged, suites, issues)
        self.assertIn("Raw and merged result records differ", [i["issue"] for i in issues])

    def test_stale_merged_section_with_no_raw_input_is_detected(self):
        """Check stale merged section with no raw input is detected."""
        self.merged["Suite_Name: SCT"] = deepcopy(self.raw)
        self.write(self.json_dir / "merged_results.json", self.merged)
        _, issues = self.check()
        self.assertIn("Merged result section has no matching raw input",
                      [i["issue"] for i in issues])

    def test_anchor_checks_include_percent_encoded_and_same_page_fragments(self):
        """Check anchor checks include percent encoded and same page fragments."""
        detail = self.detail + '<div id="case one"></div>'
        (self.html_dir / "bsa_detailed.html").write_text(detail)
        (self.html_dir / "acs_summary.html").write_text(self.summary +
            '<a href="bsa_detailed.html#case%20one">OK</a><a href="#bsa_summary">OK</a>'
            '<a href="bsa_detailed.html#absent">Bad</a><a href="#absent">Bad</a>')
        _, issues = self.check()
        broken = [i for i in issues if i["issue"] == "Broken local HTML fragment"]
        self.assertEqual(2, len(broken))

    def test_duplicate_html_ids_and_empty_link_target_are_detected(self):
        """Check duplicate HTML IDS and empty link target are detected."""
        (self.html_dir / "empty.html").write_text("")
        (self.html_dir / "acs_summary.html").write_text(self.summary +
            '<div id="bsa_summary"></div><a href="empty.html">Bad</a>')
        _, issues = self.check()
        self.assertIn("Duplicate HTML element ID", [i["issue"] for i in issues])
        self.assertIn("Broken local HTML link", [i["issue"] for i in issues])

    def test_external_symlink_is_not_read(self):
        """Check external symlink is not read."""
        outside = self.base / "external.json"
        outside.write_text('{"secret":"NEVER_READ_THIS"}')
        (self.json_dir / "bsa.json").unlink()
        (self.json_dir / "bsa.json").symlink_to(outside)
        findings, issues = self.check()
        self.assertIn("Report input escapes supplied package", [i["issue"] for i in issues])
        self.assertNotIn("NEVER_READ_THIS", repr(issues) + repr(findings))

    def test_detail_identity_balanced_swap_and_nested_parent_rows(self):
        """Check detail identity balanced swap and nested parent rows."""
        data = {
            "test_results": [{
                "testcases": [{
                    "Test_case":
                    "parent",
                    "Test_case_description":
                    "root",
                    "Test_result":
                    "FAILED",
                    "subtests": [{
                        "sub_Test_Number": "child",
                        "sub_Test_Description": "leaf",
                        "sub_test_result": "PASSED"
                    }]
                }]
            }]
        }
        expected = doctor_artifacts._raw_detail_records(data, "bsa/json_to_html.py")
        markup = (
            '<table><tr><th>Test Case</th><th>Description</th><th>Result</th></tr>'
            '<tr><td><button>-</button>parent</td><td>root</td><td>FAILED</td></tr>'
            '<tr><td colspan="3"><table><tr><th>Subtest #</th><th>Description</th><th>Result</th></tr>'
            '<tr><td>child</td><td>leaf</td><td>PASSED</td></tr></table></td></tr></table>')
        actual, tables = doctor_artifacts._html_detail_records(doctor_artifacts.ReportHTML(markup))
        self.assertEqual(expected, actual)
        self.assertEqual(2, tables)
        swapped = markup.replace('>FAILED<',
                                 '>TMP<').replace('>PASSED<',
                                                  '>FAILED<').replace('>TMP<', '>PASSED<')
        actual, _ = doctor_artifacts._html_detail_records(doctor_artifacts.ReportHTML(swapped))
        self.assertNotEqual(expected, actual)
        self.assertEqual(Counter(record[2] for record in expected),
                         Counter(record[2] for record in actual))

    @staticmethod
    def reason_button_detail_fixture():
        """Build parent and child rows with expandable diagnostic text."""
        data = {"test_results": [{"testcases": [
            {"Test_case": "B_GIC_02 : 202", "Test_case_description": "Parent check",
             "Test_result": "FAILED", "subtests": [
                 {"sub_Test_Number": "B_GIC_02 : 202.1", "sub_Test_Description": "Child check",
                  "sub_test_result": "PASSED"}]}]}]}
        # Match the BSA/SBSA report shape: visible IDs are reason disclosure
        # buttons, while folded reason content occupies its own non-result cell.
        markup = (
            '<table><tr><th>Test Case</th><th>Description</th><th>Result</th>'
            '<th>Waiver Reason</th><th>Reason</th></tr><tr>'
            '<td class="testcase-number"><button class="testcase-toggle">-</button>'
            '<button type="button" class="reason-rule-toggle" aria-expanded="false" '
            'aria-controls="reason-0-0"><span>B_GIC_02 : 202</span></button></td>'
            '<td>Parent check</td><td>FAILED</td><td>N/A</td><td class="test-reason">'
            '<details id="reason-0-0" class="acs-long-value acs-long-reason">'
            '<summary>View full reason</summary><span class="acs-long-reason-text">'
            'OTHER_ID : 999 PASSED is diagnostic text, not another result.</span>'
            '<button class="reason-action" hidden>Hidden reason action</button></details></td></tr>'
            '<tr><td colspan="5"><div class="subtest-controls">'
            '<button class="subtest-control expand-subtests"><span>+</span>Expand all</button>'
            '<button class="subtest-control collapse-subtests">Collapse all</button></div>'
            '<table class="subtest-table"><tr><th>Sub Test Number</th><th>Description</th>'
            '<th>Result</th><th>Waiver Reason</th><th>Reason</th></tr>'
            '<tr class="subtest-row"><td class="subtest-number">'
            '<span class="subtest-toggle-placeholder"></span><button type="button" '
            'class="reason-rule-toggle" aria-expanded="false" aria-controls="reason-0-0-0">'
            'B_GIC_02 : 202.1</button></td><td>Child check</td><td>PASSED</td><td>N/A</td>'
            '<td class="test-reason"><details id="reason-0-0-0" class="acs-long-reason">'
            '<summary>View full reason</summary><span>FAILED is quoted diagnostic text.</span>'
            '</details></td></tr></table></td></tr></table>')
        return data, markup

    def test_reason_rule_button_labels_keep_bsa_and_sbsa_parent_child_identities(self):
        """Check reason rule button labels keep BSA and SBSA parent child identities."""
        data, markup = self.reason_button_detail_fixture()
        expected = doctor_artifacts._raw_detail_records(data, "bsa/json_to_html.py")
        parsed = doctor_artifacts.ReportHTML(markup)
        actual, tables = doctor_artifacts._html_detail_records(parsed)
        self.assertEqual(expected, actual)
        self.assertEqual(sum(actual.values()), 2)
        self.assertEqual(tables, 2)
        for suite in ("BSA", "SBSA"):
            with self.subTest(suite=suite):
                name = suite.lower() + "_detailed.html"
                registry = [{"canonical": suite, "detailed_html": name,
                             "json_to_html": "bsa/json_to_html.py"}]
                issues = []
                doctor_artifacts._detail_parity(Path(name), parsed,
                    {suite: [(Path(suite.lower() + ".json"), data)]}, registry, issues, [])
                self.assertEqual(issues, [])

    def test_reason_rule_buttons_do_not_hide_missing_or_changed_result_identity(self):
        """Check reason rule buttons do not hide missing or changed result identity."""
        data, markup = self.reason_button_detail_fixture()
        expected = doctor_artifacts._raw_detail_records(data, "bsa/json_to_html.py")
        mutations = (
            markup.replace('<span>B_GIC_02 : 202</span>', '<span></span>'),
            markup.replace('B_GIC_02 : 202.1</button>', 'WRONG_ID</button>'),
            markup.replace('<td>Child check</td>', '<td>Different check</td>'),
            markup.replace('<td>FAILED</td>', '<td>TMP</td>')
                  .replace('<td>PASSED</td>', '<td>FAILED</td>')
                  .replace('<td>TMP</td>', '<td>PASSED</td>'))
        for index, changed in enumerate(mutations):
            with self.subTest(mutation=index):
                actual, _ = doctor_artifacts._html_detail_records(
                    doctor_artifacts.ReportHTML(changed))
                self.assertNotEqual(expected, actual)
                self.assertTrue(expected - actual)
                self.assertTrue(actual - expected)

    def test_generic_and_hidden_reason_controls_still_do_not_enter_result_cells(self):
        """Check generic and hidden reason controls still do not enter result cells."""
        markup = ('<table><tr><th>Test Case</th><th>Description</th><th>Result</th></tr>'
                  '<tr><td><button>-</button><button class="subtest-control">'
                  '<span>Expand all</span></button><button hidden class="reason-action">'
                  'Hidden reason action</button>plain-id</td><td>Plain check</td>'
                  '<td>PASSED</td></tr></table>')
        actual, _ = doctor_artifacts._html_detail_records(doctor_artifacts.ReportHTML(markup))
        self.assertEqual(actual, Counter({("plain-id", "Plain check", "PASSED"): 1}))

    def test_unknown_detail_identity_contract_is_blocked_not_green(self):
        """Check unknown detail identity contract is blocked not green."""
        del self.raw["test_results"][0]["Test_case"]
        self.write(self.json_dir / "bsa.json", self.raw)
        self.write(self.json_dir / "merged_results.json", self.merged)
        findings, issues = self.check()
        self.assertIn("Detailed identity comparison could not execute",
                      [i["issue"] for i in issues])
        self.assertTrue(all(f.status == "BLOCKED" for f in findings))

    def test_missing_and_extra_chart_categories_are_detected(self):
        """Check missing and extra chart categories are detected."""
        text = self.summary.replace('<tr><td>Failed</td><td>0</td></tr>',
                                    '<tr><td>Ignored</td><td>3</td></tr>')
        (self.html_dir / "acs_summary.html").write_text(text)
        _, issues = self.check()
        differences = [i for i in issues if i["issue"] == "Chart differs from raw suite summary"]
        self.assertEqual({"failed", "ignored"}, {i["count"] for i in differences})

    def test_combined_sbmr_detail_keeps_both_interface_records(self):
        """Check combined SBMR detail keeps both interface records."""
        ib = {
            "test_results": [{
                "Test_case": "ib-host",
                "Test_case_description": "Host",
                "Test_result": "PASSED"
            }]
        }
        oob = {
            "test_results": [{
                "Test_case": "oob-host",
                "Test_case_description": "Host",
                "Test_result": "FAILED"
            }]
        }
        inputs = {"SBMR-IB": [(Path("ib.json"), ib)], "SBMR-OOB": [(Path("oob.json"), oob)]}
        suites = [{
            "canonical": name,
            "json_to_html": "sbmr/json_to_html.py",
            "detailed_html": filename
        } for name, filename in (("SBMR-IB", "sbmr_ib_detailed.html"), ("SBMR-OOB",
                                                                        "sbmr_oob_detailed.html"))]
        text = ('<table><tr><th>Test Case</th><th>Description</th><th>Result</th></tr>'
                '<tr><td>ib-host</td><td>Host</td><td>PASSED</td></tr>'
                '<tr><td>oob-host</td><td>Host</td><td>FAILED</td></tr></table>')
        issues, coverage = [], []
        doctor_artifacts._detail_parity(Path("sbmr_detailed.html"),
                                        doctor_artifacts.ReportHTML(text), inputs, suites, issues,
                                        coverage)
        self.assertEqual([], issues)
        text = text.replace('oob-host', 'ib-host')
        doctor_artifacts._detail_parity(Path("sbmr_detailed.html"),
                                        doctor_artifacts.ReportHTML(text), inputs, suites, issues,
                                        coverage)
        self.assertIn("Raw and detailed HTML result identities differ",
                      [i["issue"] for i in issues])

    def test_unescaped_description_text_is_not_treated_as_equal(self):
        """Check unescaped description text is not treated as equal."""
        text = self.detail.replace('Check PE', 'Check register &lt;n&gt;')
        data = deepcopy(self.raw)
        data["test_results"][0]["Test_case_description"] = "Check register <n>"
        expected = doctor_artifacts._raw_detail_records(data, "bsa/json_to_html.py")
        actual, _ = doctor_artifacts._html_detail_records(doctor_artifacts.ReportHTML(text))
        self.assertEqual(expected, actual)
        actual, _ = doctor_artifacts._html_detail_records(doctor_artifacts.ReportHTML(
            text.replace('&lt;n&gt;', '<n>')))
        self.assertNotEqual(expected, actual)

    def test_sct_parent_without_subtests_still_requires_a_visible_result(self):
        """Check SCT parent without subtests still requires a visible result."""
        data = {
            "test_results": [{
                "Test_case": "SCT-01",
                "Test_case_description": "Parent failure",
                "Test_result": "FAILED",
                "subtests": []
            }]
        }
        suites = [{
            "canonical": "SCT",
            "json_to_html": "bbr/sct/json_to_html.py",
            "detailed_html": "sct_detailed.html"
        }]
        issues, coverage = [], []
        doctor_artifacts._detail_parity(Path("sct_detailed.html"), doctor_artifacts.ReportHTML(""),
                                        {"SCT": [(Path("sct.json"), data)]}, suites, issues,
                                        coverage)
        self.assertIn("Detailed result rows are missing", [i["issue"] for i in issues])

    @staticmethod
    def sct_heading_page(status="IGNORED", children=""):
        """Build SCT's heading-based parent result with optional subtest rows."""
        return ('<div class="heading">Test Suite Name: <span>Misc</span></div>'
                '<div class="heading">Test Case: <span>SCT-01</span></div>'
                '<div class="heading">Test Case Description: <span>Parent check</span></div>'
                '<div class="heading">Test Entry Point GUID: <span>parent-guid</span></div>'
                '<div class="heading">Test Result: <span>' + status + '</span></div>'
                '<table><thead><tr><th>Sub Test GUID</th><th>Sub Test Description</th>'
                '<th>Sub Test Result</th></tr></thead><tbody>' + children + '</tbody></table>')

    def sct_parity_issues(self, data, text):
        """Compare an SCT JSON sample with the corresponding visible HTML text."""
        issues = []
        suites = [{"canonical": "SCT", "json_to_html": "bbr/sct/json_to_html.py",
                   "detailed_html": "sct_detailed.html"}]
        doctor_artifacts._detail_parity(Path("sct_detailed.html"),
                                        doctor_artifacts.ReportHTML(text),
                                        {"SCT": [(Path("sct.json"), data)]}, suites, issues, [])
        return issues

    def test_sct_childless_heading_results_match_raw_statuses(self):
        """Check SCT childless heading results match raw statuses."""
        for status in ("IGNORED", "SKIPPED", "NOT SUPPORTED", "FAILED"):
            with self.subTest(status=status):
                data = {
                    "test_results": [{
                        "Test_case": "SCT-01",
                        "Test_case_description": "Parent check",
                        "test_result": status,
                        "subtests": []
                    }]
                }
                self.assertEqual([], self.sct_parity_issues(data, self.sct_heading_page(status)))

    def test_sct_heading_does_not_double_count_child_results(self):
        """Check SCT heading does not double count child results."""
        data = {
            "test_results": [{
                "Test_case":
                "SCT-01",
                "Test_case_description":
                "Parent check",
                "test_result":
                "FAILED",
                "subtests": [{
                    "sub_Test_GUID": "child-guid",
                    "sub_Test_Description": "Child check",
                    "sub_test_result": "FAILED"
                }]
            }]
        }
        child = '<tr><td>child-guid</td><td>Child check</td><td>FAILED</td></tr>'
        self.assertEqual([], self.sct_parity_issues(data, self.sct_heading_page("FAILED", child)))
        self.assertTrue(self.sct_parity_issues(data, self.sct_heading_page("FAILED")))

    def test_sct_childless_heading_mutations_and_missing_fields_are_detected(self):
        """Check SCT childless heading mutations and missing fields are detected."""
        data = {"test_results": [{"Test_case": "SCT-01", "Test_case_description": "Parent check",
                                 "test_result": "IGNORED", "subtests": []}]}
        text = self.sct_heading_page()
        mutations = (text.replace("SCT-01",
                                  "SCT-02"), text.replace("Parent check", "Different check"),
                     text.replace("IGNORED", "PASSED"),
                     text.replace('<div class="heading">Test Result: <span>IGNORED</span></div>',
                                  ""),
                     text.replace('<div class="heading">Test Case: <span>SCT-01</span></div>', ""))
        for changed in mutations:
            with self.subTest(markup=changed):
                issues = self.sct_parity_issues(data, changed)
                self.assertIn("Raw and detailed HTML result identities differ",
                              [i["issue"] for i in issues])

    def test_sct_childless_heading_duplicate_multiplicity_is_preserved(self):
        """Check SCT childless heading duplicate multiplicity is preserved."""
        entry = {"Test_case": "SCT-01", "Test_case_description": "Parent check",
                 "test_result": "IGNORED", "subtests": []}
        text = self.sct_heading_page()
        self.assertEqual([], self.sct_parity_issues({"test_results": [entry, entry]}, text + text))
        self.assertTrue(self.sct_parity_issues({"test_results": [entry, entry]}, text))
        self.assertTrue(self.sct_parity_issues({"test_results": [entry]}, text + text))

    def test_sct_heading_contract_is_not_applied_to_other_renderers(self):
        """Check SCT heading contract is not applied to other renderers."""
        actual, _ = doctor_artifacts._html_detail_records(
            doctor_artifacts.ReportHTML(self.sct_heading_page()))
        self.assertEqual(Counter(), actual)

    def test_chart_total_is_derived_when_raw_has_only_status_counts(self):
        """Check chart total is derived when raw has only status counts."""
        data = {
            "suite_summary": {
                "total_passed": 8,
                "total_failed": 1,
                "total_failed_with_waiver": 2
            }
        }
        registry = [{"canonical": "FWTS", "summary_html": "fwts_summary.html"}]
        text = ('<table class="summary-table"><tr><td>Total Tests</td><td>11</td></tr>'
                '<tr><td>Passed</td><td>8</td></tr><tr><td>Failed</td><td>1</td></tr>'
                '<tr><td>Failed with Waiver</td><td>2</td></tr></table>')
        issues, coverage = [], []
        doctor_artifacts._inspect_html(Path("fwts_summary.html"), doctor_artifacts.ReportHTML(text),
                                       {}, {"FWTS": data}, registry, issues, coverage)
        self.assertEqual([], issues)
        doctor_artifacts._inspect_html(Path("fwts_summary.html"),
                                       doctor_artifacts.ReportHTML(text.replace('>11<', '>9<')), {},
                                       {"FWTS": data}, registry, issues, coverage)
        difference = next(i for i in issues if i["issue"] == "Chart differs from raw suite summary")
        self.assertEqual("total", difference["count"])
        self.assertEqual(11, difference["expected"])
        self.assertEqual(9, difference["actual"])

    def test_sbmr_zero_ignored_counter_has_no_required_chart_row(self):
        """Check SBMR zero ignored counter has no required chart row."""
        registry = [{"canonical": "SBMR-IB", "summary_html": "sbmr_ib_summary.html"}]
        data = {"suite_summary": {"total_passed": 1, "total_ignored": 0}}
        text = ('<table class="summary-table"><tr><td>Total Tests</td><td>1</td></tr>'
                '<tr><td>Passed</td><td>1</td></tr></table>')
        issues, coverage = [], []
        doctor_artifacts._inspect_html(Path("sbmr_ib_summary.html"),
                                       doctor_artifacts.ReportHTML(text), {}, {"SBMR-IB": data},
                                       registry, issues, coverage)
        self.assertEqual([], issues)
        data["suite_summary"]["total_ignored"] = 2
        doctor_artifacts._inspect_html(Path("sbmr_ib_summary.html"),
                                       doctor_artifacts.ReportHTML(text), {}, {"SBMR-IB": data},
                                       registry, issues, coverage)
        differences = [i for i in issues if i["issue"] == "Chart differs from raw suite summary"]
        self.assertEqual({"total", "ignored"}, {i["count"] for i in differences})


# Browser and PDF evidence: successful commands alone are not proof of success.

def marker(checks=8, failures=None):
    """Build the result marker that Doctor expects from its browser checks."""
    return '<pre id="doctor-browser-result">' + json.dumps({
        "checks": checks, "failures": failures if failures is not None else []}) + '</pre>'


def pdf_text(prefix="SBBR", outcome="fail"):
    """Build sample extracted PDF text with known counts and compliance."""
    passed, failed, waived, compliance = visual.OUTCOMES[outcome]
    return (prefix + "-FWTS Test Summary\nSRS requirements compliance results\n"
            + compliance + "\nTotal Tests 2\nPassed " + str(passed) + "\nFailed "
            + str(failed) + "\nFailed with Waiver " + str(waived))


class BrowserResultTests(unittest.TestCase):
    """Reject browser output unless the requested checks actually reported results."""

    def test_executed_positive_control(self):
        """Check executed positive control."""
        self.assertEqual(visual.browser_result(marker()), {"checks": 8, "failures": []})

    def test_reported_assertion_failures_are_preserved(self):
        """Check reported assertion failures are preserved."""
        self.assertEqual(visual.browser_result(marker(failures=["Wrong chart count"]))["failures"],
                         ["Wrong chart count"])

    def test_no_marker_cannot_be_a_successful_browser_run(self):
        """Check no marker cannot be a successful browser run."""
        for text in ("", "<html><body>Nice report</body></html>", "Chrome exited normally"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "without running"):
                    visual.browser_result(text)

    def test_zero_few_boolean_and_noninteger_checks_are_incomplete(self):
        """Check zero few boolean and noninteger checks are incomplete."""
        for checks in (0, 1, 3, -1, True, 4.0, "8", None):
            with self.subTest(checks=checks):
                with self.assertRaises(ValueError):
                    visual.browser_result(marker(checks=checks))

    def test_failures_must_be_a_list(self):
        """Check failures must be a list."""
        for failures in ("", "no failure", {}, False):
            with self.subTest(failures=failures):
                with self.assertRaises(ValueError):
                    visual.browser_result(marker(failures=failures))

    def test_bad_json_and_non_object_payloads_are_controlled_errors(self):
        """Check bad JSON and non object payloads are controlled errors."""
        for payload in ("broken", "[]", "null", "1", '"text"', '{}'):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    visual.browser_result('<pre id="doctor-browser-result">' + payload + '</pre>')

    def test_dom_encoded_json_is_decoded(self):
        """Check dom encoded JSON is decoded."""
        text = marker(failures=["Expected A & B"]).replace("&", "&amp;")
        self.assertEqual(visual.browser_result(text)["failures"], ["Expected A & B"])


class PdfContractTests(unittest.TestCase):
    """Check that PDF text retains suite names, exact counts and compliance."""

    def test_positive_controls_for_both_modes_and_all_outcomes(self):
        """Check positive controls for both modes and all outcomes."""
        for prefix in ("EBBR", "SBBR"):
            for outcome in visual.OUTCOMES:
                with self.subTest(prefix=prefix, outcome=outcome):
                    self.assertEqual(
                        visual.pdf_problems(pdf_text(prefix, outcome), prefix, outcome), [])

    def test_print_wrapping_and_extra_whitespace_do_not_change_semantics(self):
        """Check print wrapping and extra whitespace do not change semantics."""
        text = pdf_text().replace(" ", " \n ")
        self.assertEqual(visual.pdf_problems(text, "SBBR", "fail"), [])

    def test_wrong_or_missing_suite_identity_is_detected(self):
        """Check wrong or missing suite identity is detected."""
        for replacement in ("EBBR-FWTS", "SBBR-SCT", "", "NOT-SBBR-FWTS"):
            with self.subTest(replacement=replacement):
                text = pdf_text().replace("SBBR-FWTS", replacement)
                self.assertTrue(any("suite identity" in issue
                                    for issue in visual.pdf_problems(text, "SBBR", "fail")))

    def test_noncompliant_is_not_accepted_as_compliant_substring(self):
        """Check noncompliant is not accepted as compliant substring."""
        self.assertTrue(
            any("Expected overall Compliant" in issue
                for issue in visual.pdf_problems(pdf_text(outcome="fail"), "SBBR", "pass")))

    def test_waiver_status_must_not_be_reduced_to_plain_compliant(self):
        """Check waiver status must not be reduced to plain compliant."""
        text = pdf_text(outcome="waived").replace("Compliant with waivers", "Compliant")
        self.assertTrue(any("Expected overall Compliant with waivers" in issue
                            for issue in visual.pdf_problems(text, "SBBR", "waived")))

    def test_missing_compliance_heading_cannot_match_unrelated_status(self):
        """Check missing compliance heading cannot match unrelated status."""
        text = pdf_text().replace("SRS requirements compliance results", "Unrelated test output")
        self.assertTrue(
            any("actual missing" in issue for issue in visual.pdf_problems(text, "SBBR", "fail")))

    def test_each_exact_counter_is_independently_checked(self):
        """Check each exact counter is independently checked."""
        for label in ("Total Tests 2", "Passed 1", "Failed 1", "Failed with Waiver 0"):
            with self.subTest(label=label):
                text = pdf_text().replace(label, label.rsplit(" ", 1)[0] + " 9")
                self.assertTrue(any("Expected PDF count" in issue
                                    for issue in visual.pdf_problems(text, "SBBR", "fail")))

    def test_count_prefix_does_not_accept_ten_as_one(self):
        """Check count prefix does not accept ten as one."""
        text = pdf_text().replace("Passed 1", "Passed 10")
        self.assertTrue(
            any("Passed=1" in issue for issue in visual.pdf_problems(text, "SBBR", "fail")))

    def test_contradictory_duplicate_count_cannot_hide_behind_matching_count(self):
        """Check contradictory duplicate count cannot hide behind matching count."""
        self.assertTrue(visual.pdf_problems(pdf_text() + "\nPassed 9", "SBBR", "fail"))

    def test_empty_pdf_text_never_passes(self):
        """Check empty PDF text never passes."""
        self.assertGreaterEqual(len(visual.pdf_problems("", "SBBR", "fail")), 6)


class BrowserExecutionTests(unittest.TestCase):
    """Check browser setup and outcomes using fake server and command responses."""

    def invoke(self, stdout, returncode=0):
        """Simulate both browser sizes without launching a browser or HTTP server."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        source, destination = root / "source", root / "browser"
        source.mkdir()
        destination.mkdir()
        page = source / "fwts_detailed.html"
        content = '<html><head><title>Results</title></head><body><h1>FWTS</h1></body></html>'
        page.write_text(content)
        ctx = Context(root, root)
        ctx.run = mock.Mock(return_value=subprocess.CompletedProcess([], returncode, stdout))
        server = mock.Mock(server_port=41111)
        with mock.patch.object(visual, "ThreadingHTTPServer", return_value=server), \
                mock.patch.object(visual, "Thread") as thread:
            visual.check_browser(ctx, "/browser", page, destination, "SR", "fail")
        self.assertEqual(page.read_text(), content,
                         "Original generated report must not be instrumented in place")
        self.assertIn("doctor-browser-result", (destination / page.name).read_text())
        self.assertIn("window.doctorErrors", (destination / page.name).read_text())
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()
        thread.return_value.join.assert_called_once()
        return ctx

    def test_both_viewports_must_execute_and_pass(self):
        """Check both viewports must execute and pass."""
        ctx = self.invoke(marker())
        self.assertEqual(len(ctx.findings), 2)
        self.assertTrue(all(finding.status == "PASS" for finding in ctx.findings))
        sizes = {next(str(arg) for arg in call.args[0] if str(arg).startswith("--window-size="))
                 for call in ctx.run.call_args_list}
        self.assertEqual(sizes, {"--window-size=1600,900", "--window-size=430,900"})

    def test_javascript_assertion_failure_is_failure(self):
        """Check javascript assertion failure is failure."""
        ctx = self.invoke(marker(failures=["Report overflows viewport"]))
        self.assertTrue(all(finding.status == "FAIL" for finding in ctx.findings))
        self.assertTrue(all("overflows" in finding.actual for finding in ctx.findings))

    def test_successful_process_without_assertions_is_failure(self):
        """Check successful process without assertions is failure."""
        ctx = self.invoke("<html>Uninitialized report</html>")
        self.assertTrue(all(finding.status == "FAIL" for finding in ctx.findings))

    def test_nonzero_browser_exit_cannot_pass_matching_marker(self):
        """Check nonzero browser exit cannot pass matching marker."""
        ctx = self.invoke(marker(), returncode=1)
        self.assertTrue(all(finding.status == "FAIL" for finding in ctx.findings))


class VisualDependencyTests(unittest.TestCase):
    """Keep browser and PDF checks independent when one tool is unavailable."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.ctx = Context(self.root / "source", self.root / "output", modes=("DT",))
        self.ctx.portable_parser = self.root / "package" / "log_parser"

    def completed(self, code=0, text="ok"):
        """Return a fake command result for a dependency or generation step."""
        return subprocess.CompletedProcess([], code, text)

    def test_no_verified_package_is_blocked_and_does_not_invoke_tools(self):
        """Check no verified package is blocked and does not invoke tools."""
        self.ctx.portable_parser = None
        self.ctx.run = mock.Mock()
        visual.run_visual(self.ctx)
        self.assertEqual(self.ctx.findings[0].check_id, "VISUAL_PACKAGE")
        self.assertEqual(self.ctx.findings[0].status, "BLOCKED")
        self.ctx.run.assert_not_called()

    def test_absent_browser_and_pdf_dependencies_are_both_blocked(self):
        """Check absent browser and PDF dependencies are both blocked."""
        self.ctx.run = mock.Mock(return_value=self.completed(1, "missing package"))
        with mock.patch.object(visual.shutil, "which", return_value=None):
            visual.run_visual(self.ctx)
        self.assertEqual({finding.check_id: finding.status for finding in self.ctx.findings}, {
            "VISUAL_BROWSER_DEPENDENCY": "BLOCKED", "VISUAL_PDF_DEPENDENCY": "BLOCKED"})
        self.ctx.run.assert_called_once()

    def test_missing_browser_does_not_suppress_available_pdf_checks(self):
        """Check missing browser does not suppress available PDF checks."""
        calls = []

        def invoke(command, directory, name, **kwargs):
            """Simulate PDF text extraction while leaving browser checks unavailable."""
            calls.append(name)
            if name == "pdf-read":
                outcome = Path(directory).name.split("_", 1)[1]
                (Path(directory) / "pdf-text.txt").write_text(pdf_text("EBBR", outcome))
            return self.completed()

        self.ctx.run = invoke
        with mock.patch.object(visual.shutil, "which", return_value=None):
            visual.run_visual(self.ctx)
        self.assertEqual(calls.count("pdf-read"), 3)
        self.assertEqual([finding.status for finding in self.ctx.findings
                          if finding.check_id == "VISUAL_BROWSER_DEPENDENCY"], ["BLOCKED"])
        self.assertEqual([finding.status for finding in self.ctx.findings
                          if finding.check_id == "VISUAL_PDF"], ["PASS", "PASS", "PASS"])

    def test_missing_pdf_dependencies_do_not_suppress_available_browser_checks(self):
        """Check missing PDF dependencies do not suppress available browser checks."""
        browser = self.root / "chromium"
        browser.write_text("synthetic executable path; never invoked")
        self.ctx.browser = browser

        def invoke(command, directory, name, **kwargs):
            """Provide generated HTML while simulating a missing PDF dependency."""
            if name == "pdf-dependencies":
                return self.completed(1, "pypdf missing")
            if name == "generate":
                reports = Path(directory) / "output" / "html_detailed_summaries"
                reports.mkdir(parents=True)
                for page in ("acs_summary.html", "fwts_detailed.html"):
                    (reports / page).write_text("<html><body>Generated report</body></html>")
            return self.completed()

        self.ctx.run = invoke
        with mock.patch.object(visual, "check_browser") as check:
            visual.run_visual(self.ctx)
        self.assertEqual(check.call_count, 6)
        self.assertEqual([finding.status for finding in self.ctx.findings
                          if finding.check_id == "VISUAL_PDF_DEPENDENCY"], ["BLOCKED"])
        self.assertFalse(any(finding.check_id == "VISUAL_PDF" for finding in self.ctx.findings))

    def test_failed_generation_does_not_create_green_browser_results(self):
        """Check failed generation does not create green browser results."""
        browser = self.root / "chromium"
        browser.write_text("synthetic")
        self.ctx.browser = browser
        self.ctx.run = mock.Mock(side_effect=[self.completed(1)] + [self.completed(5)] * 3)
        with mock.patch.object(visual, "check_browser") as check:
            visual.run_visual(self.ctx)
        check.assert_not_called()
        blocked = [
            finding for finding in self.ctx.findings
            if finding.check_id == "VISUAL_DEPENDENT_CHECKS"
        ]
        self.assertEqual(len(blocked), 3)
        self.assertTrue(all(finding.status == "BLOCKED" for finding in blocked))

    def test_generated_category_has_description_required_by_raw_schema(self):
        """Check generated category has description required by raw schema."""
        self.ctx.run = mock.Mock(return_value=self.completed())
        with mock.patch.object(visual.shutil, "which", return_value=None):
            visual.run_visual(self.ctx)
        category = json.loads(
            (self.ctx.output_dir / "evidence/visual/DT_pass/category.json").read_text())
        self.assertEqual(category["doctor"][0]["Description"],
                         ["Doctor synthetic FWTS interface checks"])


if __name__ == "__main__":
    unittest.main()
