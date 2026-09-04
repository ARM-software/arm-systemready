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

"""Apply the shared, self-contained UI to generated ACS HTML reports.

The parser's suite renderers intentionally retain ownership of their result
calculations and table markup.  This module only adds presentation CSS and
progressive-enhancement JavaScript to the rendered HTML string.  Reports stay
readable when JavaScript is disabled and remain single-file artifacts.
"""

import re


UI_MARKER = 'data-acs-report-ui="2026.4"'
VALID_PAGE_TYPES = {"suite", "acs-summary"}
VALID_SUITE_TYPES = {
    "bsa",
    "fwts",
    "os",
    "pfdi",
    "post-script",
    "sbmr",
    "scmi",
    "sct",
    "standalone",
    "tpm",
}


def center_matplotlib_plot(axis):
    """Center a Matplotlib plotting rectangle within its figure canvas."""
    position = axis.get_position()
    side_margin = max(position.x0, 1.0 - position.x1)
    axis.set_position([
        side_margin,
        position.y0,
        1.0 - (2.0 * side_margin),
        position.height,
    ])


REPORT_CSS = r"""
/* Shared SystemReady ACS report UI. Keep this self-contained for offline use. */
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
    --acs-focus: #1769e0;
    --acs-shadow: 0 8px 26px rgba(16, 42, 76, .07);
    --acs-pass-bg: #dcfce7;
    --acs-pass-text: #166534;
    --acs-fail-bg: #fee2e2;
    --acs-fail-text: #991b1b;
    --acs-warn-bg: #ffedd5;
    --acs-warn-text: #9a3412;
    --acs-partial-bg: #e0f2fe;
    --acs-partial-text: #075985;
    --acs-neutral-bg: #eef2f7;
    --acs-neutral-text: #475467;
    --acs-info-bg: #e8efff;
    --acs-info-text: #344e7a;
    --acs-suite-accent: #175cd3;
    --acs-suite-soft: #edf4ff;
    --acs-suite-border: #bfd3f2;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body.acs-report-ui {
    margin: 0 !important;
    padding: 24px !important;
    background: var(--acs-bg) !important;
    color: var(--acs-text) !important;
    font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.45 !important;
}
body.acs-report-ui > * { max-width: 1540px; margin-left: auto; margin-right: auto; }
body.acs-report-ui > .header {
    max-width: 1540px;
    padding: 22px 26px !important;
    margin-bottom: 16px !important;
    border-radius: 16px;
    background: linear-gradient(118deg, var(--acs-brand-strong), var(--acs-brand)) !important;
    box-shadow: var(--acs-shadow);
    color: #fff !important;
    font-size: 26px !important;
    font-weight: 750 !important;
    letter-spacing: -.02em;
    text-align: left !important;
}
body.acs-report-ui > .container {
    width: auto !important;
    max-width: 1540px !important;
    margin-top: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}
body.acs-report-ui h1,
body.acs-report-ui h2,
body.acs-report-ui h3 {
    color: var(--acs-heading) !important;
    text-align: left !important;
}
body.acs-report-ui h1 {
    margin: 0 0 4px !important;
    padding: 0 !important;
    font-size: clamp(24px, 3vw, 31px) !important;
    line-height: 1.2 !important;
    letter-spacing: -.025em;
}
body.acs-report-ui > h1 {
    margin-left: auto !important;
    margin-right: auto !important;
}
body.acs-report-ui h2 { margin: 0 0 14px !important; font-size: 19px !important; }
body.acs-report-ui h3 { font-size: 16px !important; }
body.acs-report-ui a { color: #175cd3; }
body.acs-report-ui a:hover { color: #0b4db3; }
body.acs-report-ui button,
body.acs-report-ui input,
body.acs-report-ui select { font: inherit; }
body.acs-report-ui button:focus-visible,
body.acs-report-ui input:focus-visible,
body.acs-report-ui select:focus-visible,
body.acs-report-ui a:focus-visible {
    outline: 3px solid color-mix(in srgb, var(--acs-focus) 35%, transparent);
    outline-offset: 2px;
}

.acs-report-kicker {
    margin: 0 0 6px;
    color: var(--acs-suite-accent);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .09em;
    text-transform: uppercase;
}
.acs-report-subtitle {
    margin: 0 0 16px;
    color: var(--acs-muted);
    font-size: 13px;
}
.acs-report-ui[data-acs-view="detail"] .acs-report-kicker {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}
.acs-back-to-main {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 36px;
    padding: 7px 11px;
    color: var(--acs-brand) !important;
    background: var(--acs-panel);
    border: 1px solid #bfd0e5;
    border-radius: 9px;
    box-shadow: 0 3px 10px rgba(16, 42, 76, .05);
    font-size: 12px;
    font-weight: 750;
    letter-spacing: normal;
    margin-left: auto;
    text-decoration: none !important;
    text-transform: none;
    white-space: nowrap;
}
.acs-back-to-main:hover {
    color: var(--acs-brand) !important;
    background: var(--acs-brand-soft);
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .acs-report-kicker,
.acs-report-ui[data-acs-report-kind="acs-summary"] .acs-report-subtitle { display: none; }

.chart-container {
    display: grid !important;
    place-items: center;
    margin: 0 !important;
    padding: 8px !important;
    overflow: auto;
    background: var(--acs-panel) !important;
}
.chart-container img { display: block; max-width: 100%; max-height: 300px; height: auto; object-fit: contain; }
body.acs-report-ui[data-acs-view="detail"] .chart-container,
body.acs-report-ui:has(.detailed-summary, .detailed-container) .chart-container {
    display: none !important;
}
.result-summary .acs-reference-note {
    margin: 8px 0 !important;
    padding: 8px 10px;
    text-align: left !important;
    color: var(--acs-muted);
    background: var(--acs-panel-muted);
    border-left: 3px solid var(--acs-suite-accent);
    border-radius: 7px;
    font-size: 10.5px;
    font-weight: 600 !important;
}
.result-summary .acs-reference-note br { display: none; }
.result-summary .acs-reference-note a { margin-left: 4px; font-weight: 750; }

.result-summary,
.summary-container,
.system-info,
.acs-results-summary,
.summary-section,
.summary {
    margin: 14px 0 !important;
    padding: 16px !important;
    background: var(--acs-panel) !important;
    border: 1px solid var(--acs-line) !important;
    border-radius: 15px !important;
    box-shadow: var(--acs-shadow) !important;
}
.result-summary h2,
.summary-container h2,
.system-info h2,
.acs-results-summary h2 {
    padding: 0 !important;
    border: 0 !important;
}
body.acs-report-ui[data-acs-report-kind="acs-summary"] .acs-overview-source {
    display: none !important;
}
.acs-summary-overview { margin: 14px 0 18px; }
.acs-summary-overview > .acs-information-overview,
.acs-overview-results > .acs-overview-result-card {
    margin: 0 !important;
    padding: 16px !important;
}
.acs-overview-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 0 0 12px;
}
.acs-report-ui .acs-overview-heading h2 {
    margin: 0 !important;
    padding: 0 !important;
    color: var(--acs-heading);
    border: 0 !important;
    font-size: 20px !important;
}
.acs-overview-field-count {
    color: var(--acs-muted);
    font-size: 11px;
    font-weight: 650;
    white-space: nowrap;
}
.acs-information-band {
    display: grid;
    grid-template-columns: 120px minmax(0, 1fr);
    gap: 14px;
    padding: 7px 0;
    border-top: 1px solid #e6edf5;
}
.acs-information-band:first-child { border-top: 0; }
.acs-report-ui .acs-information-band h3 {
    display: flex;
    align-items: center;
    margin: 0 !important;
    padding: 9px 10px !important;
    color: #fff !important;
    background: var(--acs-brand);
    border: 0 !important;
    border-radius: 8px;
    font-size: 10.5px !important;
    font-weight: 850;
    letter-spacing: .07em;
    text-transform: uppercase;
}
.acs-information-values {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px 14px;
    margin: 0;
}
.acs-information-field { min-width: 0; }
.acs-information-field dt {
    min-width: 0;
    margin: 0 0 2px;
    color: var(--acs-muted);
    font-size: 10.5px;
    font-weight: 850;
    letter-spacing: .045em;
    text-transform: uppercase;
    overflow-wrap: anywhere;
}
.acs-information-field dd {
    margin: 0;
    color: var(--acs-text);
    font-size: 12.5px;
    font-weight: 650;
    line-height: 1.4;
    overflow-wrap: anywhere;
}
.acs-information-field[data-acs-unknown="true"] dd {
    color: var(--acs-muted);
    font-weight: 600;
}
.acs-overview-results {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(280px, .7fr);
    align-items: start;
    gap: 14px;
    margin-top: 14px;
}
.acs-overview-results[data-acs-card-count="2"] {
    grid-template-columns: minmax(0, 3fr) minmax(320px, 2fr);
}
.acs-overview-results[data-acs-card-count="1"] {
    grid-template-columns: minmax(0, 1fr);
}
.acs-overview-result-card {
    min-width: 0;
    border-left: 4px solid var(--acs-suite-accent) !important;
}
.acs-overview-result-card[data-acs-card-tone="fail"] { border-left-color: #dc2626 !important; }
.acs-overview-result-card[data-acs-card-tone="pass"] { border-left-color: #16a34a !important; }
.acs-overview-result-card[data-acs-card-tone="warn"] { border-left-color: #f97316 !important; }
.acs-overview-result-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin: -2px 0 10px;
}
.acs-overview-meta-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-width: 0;
    max-width: 100%;
    padding: 4px 8px;
    color: var(--acs-muted);
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
    border-radius: 999px;
    font-size: 10.5px;
    font-weight: 650;
    overflow-wrap: anywhere;
}
.acs-overview-meta-item dt,
.acs-overview-meta-item dd { margin: 0; }
.acs-overview-meta-item dt { font-weight: 800; }
.acs-overview-meta-item dd { min-width: 0; overflow-wrap: anywhere; }
.acs-overview-heading-meta {
    display: flex;
    flex: 0 1 auto;
    margin: 0;
}
.acs-overview-heading-meta .acs-overview-meta-item {
    color: var(--acs-text);
    background: #fff;
}
.acs-overview-result-entry + .acs-overview-result-entry {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #e6edf5;
}
.acs-overview-status-list { margin: 0; }
.acs-overview-result-label {
    color: var(--acs-text);
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .045em;
    text-transform: uppercase;
    overflow-wrap: anywhere;
}
.acs-overview-result-value {
    margin: 3px 0 0;
    color: var(--acs-text);
    font-size: 12.5px;
    font-weight: 650;
    line-height: 1.4;
    overflow-wrap: anywhere;
}
.acs-overview-result-entry[data-acs-tone="fail"] .acs-overview-result-value {
    color: var(--acs-fail-text);
}
.acs-overview-result-entry[data-acs-tone="pass"] .acs-overview-result-value[data-acs-primary="true"] {
    color: var(--acs-pass-text);
}
.acs-overview-result-entry[data-acs-tone="warn"] .acs-overview-result-value[data-acs-primary="true"] {
    color: var(--acs-warn-text);
}
.acs-overview-result-entry[data-acs-tone="neutral"] .acs-overview-result-value[data-acs-primary="true"] {
    color: var(--acs-neutral-text);
}
.acs-overview-result-value[data-acs-primary="true"] {
    font-size: 15px;
    font-weight: 850;
}
.acs-overview-result-value[data-acs-primary="false"] {
    margin-top: 6px;
    padding: 7px 9px;
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
    border-radius: 8px;
}
.acs-overview-result-entry[data-acs-tone="fail"] .acs-overview-result-value[data-acs-primary="false"] {
    background: #fff7f7;
    border-color: #fecaca;
}
.acs-overview-result-entry[data-acs-tone="warn"] .acs-overview-result-value[data-acs-primary="false"] {
    background: #fff7ed;
    border-color: #fed7aa;
}
.acs-overview-result-value[data-acs-primary="false"] strong {
    color: var(--acs-text);
    font-weight: 900;
}
.detailed-summary,
.detailed-container {
    margin-top: 14px !important;
    padding: 0 !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}
.test-suite-header,
.suite-header {
    display: flex;
    align-items: center;
    gap: 9px;
    min-height: 48px;
    margin: 16px 0 0 !important;
    padding: 11px 13px !important;
    color: var(--acs-heading) !important;
    background: var(--acs-panel) !important;
    border: 1px solid var(--acs-line);
    border-radius: 14px 14px 0 0;
    box-shadow: 0 3px 12px rgba(16, 42, 76, .045);
    font-size: 16px !important;
    font-weight: 800 !important;
    letter-spacing: .005em;
    scroll-margin-top: 105px;
}
.test-suite-description,
.test-suite-info,
.suite-reason { color: var(--acs-muted) !important; }

.heading {
    margin: 0 0 6px;
    color: var(--acs-heading);
    font-size: 13px;
    font-weight: 750;
}
.heading span { color: var(--acs-text); font-weight: 500; }

.acs-result-group {
    position: relative;
    margin: 16px 0;
    padding: 14px;
    overflow: hidden;
    background: var(--acs-panel);
    border: 1px solid var(--acs-line);
    border-left: 4px solid var(--acs-suite-accent);
    border-radius: 15px;
    box-shadow: var(--acs-shadow);
    scroll-margin-top: 160px;
}
.acs-result-group > :first-child { margin-top: 0 !important; }
.acs-result-group > :last-child { margin-bottom: 0 !important; }
.acs-result-group.acs-collapsible > .acs-case-overview .acs-case-topline,
.acs-result-group.acs-collapsible > .test-suite-header,
.acs-result-group.acs-collapsible > .suite-header {
    padding-right: 110px !important;
}
.acs-result-group.acs-collapsed > :not(.acs-case-overview):not(.test-suite-header):not(.suite-header):not(.acs-group-toggle) {
    display: none !important;
}
.acs-result-group.acs-collapsed > .acs-case-overview .acs-case-description,
.acs-result-group.acs-collapsed > .acs-case-overview .acs-metadata-grid { display: none !important; }
.acs-group-toggle {
    position: absolute;
    top: 10px;
    right: 12px;
    z-index: 2;
    min-height: 30px;
    padding: 5px 9px;
    cursor: pointer;
    color: var(--acs-suite-accent);
    background: var(--acs-panel);
    border: 1px solid var(--acs-suite-border);
    border-radius: 8px;
    font-size: 10.5px;
    font-weight: 800;
}
.acs-result-group > .test-suite-header,
.acs-result-group > .suite-header {
    min-height: auto;
    margin: -14px -14px 12px !important;
    padding: 12px 14px !important;
    background: linear-gradient(90deg, var(--acs-suite-soft), #fff) !important;
    border: 0;
    border-bottom: 1px solid var(--acs-suite-border);
    border-radius: 0;
    box-shadow: none;
}
.acs-result-group > .test-suite-description,
.acs-result-group > .test-suite-info,
.acs-result-group > .suite-reason {
    margin: 8px 0 12px !important;
    padding: 10px 12px;
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
    border-radius: 10px;
}
.acs-result-group > .test-suite-info { border-left: 3px solid var(--acs-suite-accent); }
.acs-result-group > table { margin-bottom: 0 !important; }
.acs-result-group.acs-group-fail { border-left-color: #dc2626; }
.acs-result-group.acs-group-warning,
.acs-result-group.acs-group-fail-waiver { border-left-color: #f97316; }
.acs-result-group.acs-group-pass { border-left-color: #16a34a; }

.acs-case-card,
.acs-suite-card { padding-top: 0; }
.acs-case-overview {
    margin: 0 -14px 14px;
    padding: 15px 16px 14px;
    background: linear-gradient(120deg, var(--acs-suite-soft), #fff 72%);
    border-bottom: 1px solid var(--acs-suite-border);
}
.acs-case-topline {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
}
.acs-case-identity { min-width: 0; }
.acs-case-eyebrow {
    margin: 0 0 4px;
    color: var(--acs-suite-accent);
    font-size: 10.5px;
    font-weight: 850;
    letter-spacing: .07em;
    text-transform: uppercase;
}
body.acs-report-ui .acs-case-title {
    margin: 0 !important;
    padding: 0 !important;
    color: var(--acs-heading) !important;
    font-size: 18px !important;
    font-weight: 820;
    line-height: 1.25;
}
.acs-case-description {
    max-width: 1050px;
    margin: 7px 0 0;
    color: var(--acs-muted);
    font-size: 12.5px;
}
.acs-case-status { flex: 0 0 auto; }
.acs-metadata-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-top: 13px;
}
.acs-meta-item {
    min-width: 0;
    padding: 9px 10px;
    background: rgba(255, 255, 255, .78);
    border: 1px solid color-mix(in srgb, var(--acs-suite-border) 72%, var(--acs-line));
    border-radius: 9px;
}
.acs-meta-label {
    display: block;
    margin-bottom: 3px;
    color: var(--acs-muted);
    font-size: 9.5px;
    font-weight: 800;
    letter-spacing: .045em;
    text-transform: uppercase;
}
.acs-meta-value {
    display: block;
    color: var(--acs-text);
    font-size: 12px;
    font-weight: 650;
    overflow-wrap: anywhere;
}
.acs-meta-item.acs-meta-wide { grid-column: span 2; }
.acs-meta-item.acs-meta-full { grid-column: 1 / -1; }
.acs-meta-list {
    margin: 3px 0 0;
    padding-left: 18px;
}
.acs-meta-list li + li { margin-top: 3px; }
.acs-meta-item.acs-meta-code .acs-meta-value {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 11px;
}
.acs-metadata-source { display: none !important; }

.case-header,
.test-case-header {
    margin: 14px 0 7px !important;
    color: var(--acs-heading) !important;
    font-size: 14px !important;
    font-weight: 800 !important;
}
.test-case-description { margin: 0 0 10px !important; color: var(--acs-muted) !important; }
.acs-flat-card > h2,
.acs-flat-card > h3 { margin: 0 0 8px !important; }

body.acs-report-ui table {
    width: 100% !important;
    margin: 8px 0 14px !important;
    border: 1px solid var(--acs-line) !important;
    border-collapse: separate !important;
    border-spacing: 0 !important;
    border-radius: 12px;
    overflow: hidden;
    background: var(--acs-panel);
    table-layout: auto;
}
body.acs-report-ui th,
body.acs-report-ui td {
    padding: 9px 11px !important;
    border: 0 !important;
    border-bottom: 1px solid var(--acs-line) !important;
    color: var(--acs-text);
    font-size: 12.5px !important;
    line-height: 1.35;
    text-align: left !important;
    vertical-align: top;
    overflow-wrap: anywhere;
}
body.acs-report-ui th {
    background: var(--acs-brand) !important;
    color: #fff !important;
    font-size: 11px !important;
    font-weight: 800 !important;
    letter-spacing: .035em;
    text-transform: uppercase;
}
body.acs-report-ui tr:last-child > td { border-bottom: 0 !important; }
body.acs-report-ui tbody tr:hover > td { background-color: #f8fbff; }
body.acs-report-ui .subtest-table {
    width: calc(100% - 20px) !important;
    margin: 8px 10px 12px !important;
    border-radius: 10px;
}
body.acs-report-ui .subtest-table th { background: #eaf0f7 !important; color: var(--acs-heading) !important; }

.acs-summary-source { display: none !important; }
.acs-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(125px, 1fr));
    gap: 9px;
    margin-top: 8px;
}
.acs-summary-card {
    min-height: 76px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background: var(--acs-panel-muted);
    border: 1px solid var(--acs-line);
    border-radius: 12px;
    box-shadow: 0 2px 9px rgba(16, 42, 76, .035);
}
.acs-summary-card[data-acs-zero="true"] { opacity: .72; }
.acs-summary-value { color: var(--acs-heading); font-size: 23px; font-weight: 850; line-height: 1; }
.acs-summary-label { margin-top: 6px; color: var(--acs-muted); font-size: 11.5px; font-weight: 650; }
.acs-summary-card.pass { background: var(--acs-pass-bg); border-color: #a7edc2; }
.acs-summary-card.pass .acs-summary-value,
.acs-summary-card.pass .acs-summary-label { color: var(--acs-pass-text); }
.acs-summary-card.fail { background: var(--acs-fail-bg); border-color: #fecaca; }
.acs-summary-card.fail .acs-summary-value,
.acs-summary-card.fail .acs-summary-label { color: var(--acs-fail-text); }
.acs-summary-card.fail-waiver,
.acs-summary-card.warning { background: var(--acs-warn-bg); border-color: #fed7aa; }
.acs-summary-card.fail-waiver .acs-summary-value,
.acs-summary-card.fail-waiver .acs-summary-label,
.acs-summary-card.warning .acs-summary-value,
.acs-summary-card.warning .acs-summary-label { color: var(--acs-warn-text); }
.acs-summary-card.passed-partial { background: var(--acs-partial-bg); border-color: #bae6fd; }
.acs-summary-card.passed-partial .acs-summary-value,
.acs-summary-card.passed-partial .acs-summary-label { color: var(--acs-partial-text); }
.acs-summary-card.pal-not-supported { background: var(--acs-info-bg); }
.acs-summary-card.ignored,
.acs-summary-card.unknown { background: var(--acs-neutral-bg); border-color: #cbd5e1; }
.acs-summary-card.ignored .acs-summary-value,
.acs-summary-card.ignored .acs-summary-label,
.acs-summary-card.unknown .acs-summary-value,
.acs-summary-card.unknown .acs-summary-label { color: var(--acs-neutral-text); }

.result-summary.acs-compact-summary,
.summary-container.acs-compact-summary,
.card.acs-compact-summary {
    width: min(100%, 880px);
    margin: 14px auto 16px !important;
    padding: 18px 20px !important;
}
.acs-compact-summary-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}
.acs-compact-summary-header h2 {
    margin: 0 !important;
    font-size: 16px !important;
}
.acs-compact-summary-total {
    flex: 0 0 auto;
    color: var(--acs-muted);
    font-size: 11px;
    font-weight: 650;
    white-space: nowrap;
}
.acs-progress-list {
    display: grid;
    gap: 7px;
    margin: 0;
}
.acs-progress-row {
    display: grid;
    grid-template-columns: minmax(125px, 185px) minmax(160px, 1fr) minmax(28px, auto);
    align-items: center;
    gap: 10px;
    min-width: 0;
}
.acs-progress-label {
    min-width: 0;
    color: var(--acs-text);
    font-size: 11.5px;
    font-weight: 600;
    line-height: 1.25;
}
.acs-progress-track {
    position: relative;
    height: 8px;
    min-width: 0;
    overflow: hidden;
    background: #e9eef5;
    border-radius: 999px;
}
.acs-progress-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}
.acs-progress-count {
    min-width: 2ch;
    color: var(--acs-heading);
    font-size: 11.5px;
    font-variant-numeric: tabular-nums;
    font-weight: 800;
    line-height: 1;
    text-align: right;
}
body.acs-report-ui td.acs-status-cell {
    background: var(--acs-panel) !important;
    text-align: left !important;
    vertical-align: middle !important;
    font-weight: 750 !important;
}
.acs-status-pill,
.acs-status-filter {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    white-space: nowrap;
    font-size: 11px;
    font-weight: 800;
    line-height: 1.2;
}
.acs-status-pill {
    padding: 4px 9px;
    background: var(--acs-neutral-bg);
    color: var(--acs-neutral-text);
}
.acs-status-pill.pass,
.acs-status-filter.pass[aria-pressed="true"] { background: var(--acs-pass-bg); color: var(--acs-pass-text); }
.acs-status-pill.fail,
.acs-status-filter.fail[aria-pressed="true"] { background: var(--acs-fail-bg); color: var(--acs-fail-text); }
.acs-status-pill.fail-waiver,
.acs-status-pill.warning,
.acs-status-filter.fail-waiver[aria-pressed="true"],
.acs-status-filter.warning[aria-pressed="true"] { background: var(--acs-warn-bg); color: var(--acs-warn-text); }
.acs-status-pill.passed-partial,
.acs-status-filter.passed-partial[aria-pressed="true"] { background: var(--acs-partial-bg); color: var(--acs-partial-text); }
.acs-status-pill.pal-not-supported,
.acs-status-filter.pal-not-supported[aria-pressed="true"] { background: var(--acs-info-bg); color: var(--acs-info-text); }
.acs-status-pill.skipped,
.acs-status-pill.aborted,
.acs-status-pill.ignored,
.acs-status-pill.unknown,
.acs-status-pill.not-tested,
.acs-status-pill.not-implemented,
.acs-status-pill.info,
.acs-status-filter.skipped[aria-pressed="true"],
.acs-status-filter.aborted[aria-pressed="true"],
.acs-status-filter.ignored[aria-pressed="true"],
.acs-status-filter.unknown[aria-pressed="true"],
.acs-status-filter.not-tested[aria-pressed="true"],
.acs-status-filter.not-implemented[aria-pressed="true"],
.acs-status-filter.info[aria-pressed="true"] { background: var(--acs-neutral-bg); color: var(--acs-neutral-text); }
.acs-status-filter[aria-pressed="true"] { background: var(--acs-neutral-bg); color: var(--acs-neutral-text); }
tr[data-acs-row-status] > td:first-child {
    border-left: 4px solid var(--acs-row-accent, #94a3b8) !important;
}
.acs-mobile-status-preview,
.acs-mobile-table-note { display: none; }

body[data-acs-suite="sct"] .acs-result-group > table,
body[data-acs-suite="tpm"] .acs-result-group > table { table-layout: fixed; }
body[data-acs-suite="sct"] .acs-col-guid { width: 15%; }
body[data-acs-suite="sct"] .acs-col-description { width: 23%; }
body[data-acs-suite="sct"] .acs-col-status { width: 10%; }
body[data-acs-suite="sct"] .acs-col-path { width: 22%; }
body[data-acs-suite="sct"] .acs-col-reason { width: 17%; }
body[data-acs-suite="sct"] .acs-col-waiver { width: 13%; }
body[data-acs-suite="post-script"] .acs-flat-card {
    padding: 0 14px 14px !important;
    background: var(--acs-panel) !important;
    border: 1px solid var(--acs-line) !important;
    border-left: 4px solid var(--acs-suite-accent) !important;
    border-radius: 15px !important;
    box-shadow: var(--acs-shadow) !important;
}
body[data-acs-suite="sbmr"] .case-header { padding-top: 5px; border-top: 1px solid var(--acs-line); }

.acs-toolbar {
    position: sticky;
    top: 8px;
    z-index: 30;
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: 7px;
    margin: 10px 0;
    padding: 8px;
    background: var(--acs-bg);
    border: 1px solid var(--acs-line);
    border-radius: 14px;
    box-shadow: var(--acs-shadow);
}
.acs-detail-overview {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: stretch;
    gap: 14px;
    margin: 14px 0 16px;
}
.acs-detail-overview > .acs-compact-summary,
.acs-detail-overview > .acs-failure-summary {
    width: 100%;
    max-width: none;
    margin: 0 !important;
}
.acs-failure-summary {
    min-width: 0;
    padding: 18px 20px;
    background: var(--acs-panel);
    border: 1px solid var(--acs-line);
    border-radius: 15px;
    box-shadow: var(--acs-shadow);
}
.acs-failure-summary .acs-progress-row {
    grid-template-columns: minmax(135px, 215px) minmax(130px, 1fr) minmax(34px, auto);
}
.acs-failure-summary .acs-progress-row[data-acs-zero="true"] { opacity: .7; }
.acs-failure-summary .acs-progress-label { overflow-wrap: anywhere; }
.acs-failure-summary .acs-progress-track { display: flex; }
.acs-failure-summary .acs-progress-fill { flex: 0 0 auto; }
.acs-failure-fill-waiver { background: #f97316; }
.acs-failure-summary .acs-progress-count {
    min-width: 4.5ch;
    white-space: nowrap;
}
.acs-failure-waiver-count {
    color: var(--acs-warn-text);
    font-size: 9px;
    font-weight: 750;
}
.acs-control { display: flex; flex-direction: column; gap: 4px; min-width: 160px; }
.acs-control-grow { flex: 1 1 250px; }
.acs-control-label { color: var(--acs-muted); font-size: 11px; font-weight: 700; }
.acs-control input,
.acs-control select {
    width: 100%;
    min-height: 35px;
    padding: 7px 10px;
    background: #fff;
    color: var(--acs-text);
    border: 1px solid var(--acs-line);
    border-radius: 9px;
}
.acs-status-filters { display: flex; flex: 1 1 100%; flex-wrap: wrap; align-items: center; gap: 6px; }
.acs-filter-scope {
    flex: 1 1 100%;
    color: var(--acs-heading);
    font-size: 11px;
    font-weight: 800;
}
.acs-filter-help {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}
.acs-status-filter {
    gap: 5px;
    padding: 6px 9px;
    cursor: pointer;
    background: #fff;
    color: var(--acs-muted);
    border: 1px solid var(--acs-line);
}
.acs-status-filter:hover { background: var(--acs-suite-soft); border-color: var(--acs-suite-border); }
.acs-status-filter[aria-pressed="true"] {
    border-color: currentColor;
    box-shadow: inset 0 0 0 1px currentColor, 0 2px 7px rgba(16, 42, 76, .08);
}
.acs-status-filter.info[aria-pressed="true"] {
    background: var(--acs-brand);
    border-color: var(--acs-brand);
    color: #fff;
}
.acs-filter-count {
    min-width: 138px;
    padding: 8px 2px;
    color: var(--acs-muted);
    font-size: 11.5px;
    text-align: right;
}
.acs-print-scope-note {
    flex: 1 1 100%;
    margin: 0;
    color: var(--acs-muted);
    font-size: 10.5px;
}
.acs-print-banner { display: none; }
.acs-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.acs-button {
    min-height: 35px;
    padding: 7px 10px;
    cursor: pointer;
    background: #fff;
    color: var(--acs-text);
    border: 1px solid var(--acs-line);
    border-radius: 9px;
    font-size: 12px;
    font-weight: 750;
}
.acs-button:hover { background: var(--acs-brand-soft); border-color: #b8c9df; }
.acs-button-primary { background: var(--acs-brand); border-color: var(--acs-brand); color: #fff; }
.acs-button-primary:hover { background: var(--acs-brand-strong); color: #fff; }
.acs-filter-hidden { display: none !important; }
.acs-context-row { opacity: .76; }
.acs-empty-state {
    display: none;
    margin: 12px 0;
    padding: 20px;
    text-align: center;
    color: var(--acs-muted);
    background: var(--acs-panel);
    border: 1px dashed #b9c6d7;
    border-radius: 13px;
}
.acs-empty-state.visible { display: block; }

.acs-col-guid,
.acs-col-path { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 10.5px !important; }
.acs-col-guid { min-width: 180px; }
.acs-col-description { min-width: 220px; }
.acs-col-status { min-width: 112px; }
.acs-col-reason,
.acs-col-waiver { min-width: 180px; }
.acs-long-value { min-width: 170px; }
.acs-long-value > summary {
    width: max-content;
    max-width: 100%;
    padding: 4px 7px;
    cursor: pointer;
    list-style-position: inside;
    color: var(--acs-suite-accent);
    background: var(--acs-suite-soft);
    border: 1px solid var(--acs-suite-border);
    border-radius: 7px;
    font-family: inherit;
    font-size: 10.5px;
    font-weight: 750;
}
.acs-long-value > code {
    display: block;
    min-width: 280px;
    max-width: 560px;
    margin-top: 7px;
    padding: 8px;
    white-space: normal;
    overflow-wrap: anywhere;
    color: var(--acs-text);
    background: var(--acs-panel-muted);
    border-radius: 7px;
    font-size: 10px;
    line-height: 1.45;
}
.acs-long-reason > .acs-long-reason-text {
    display: block;
    min-width: 280px;
    max-width: 640px;
    margin-top: 7px;
    padding: 8px;
    white-space: normal;
    overflow-wrap: anywhere;
    color: var(--acs-text);
    background: var(--acs-panel-muted);
    border-radius: 7px;
    font-size: 10.5px;
    line-height: 1.45;
}
.acs-long-reason-text > br {
    display: block;
    margin-top: 5px;
    content: "";
}

.acs-suite-nav {
    position: sticky;
    top: 8px;
    z-index: 32;
    max-width: 1540px !important;
    margin: 0 auto 16px !important;
    padding: 9px;
    display: flex;
    gap: 6px;
    overflow-x: auto;
    background: var(--acs-bg);
    border: 1px solid var(--acs-line);
    border-radius: 13px;
    box-shadow: var(--acs-shadow);
}
.acs-suite-nav a {
    flex: 0 0 auto;
    padding: 6px 10px;
    text-decoration: none;
    background: var(--acs-panel);
    border: 1px solid var(--acs-line);
    border-radius: 999px;
    color: var(--acs-brand) !important;
    font-size: 11.5px;
    font-weight: 750;
}
.acs-suite-nav a:hover { background: var(--acs-brand-soft); }
.acs-back-to-top {
    position: fixed;
    right: 20px;
    bottom: 20px;
    z-index: 40;
    width: 36px;
    height: 36px;
    cursor: pointer;
    color: #fff;
    background: var(--acs-brand);
    border: 0;
    border-radius: 50%;
    box-shadow: 0 8px 24px rgba(15, 44, 80, .24);
    font-size: 15px;
    font-weight: 800;
    opacity: 0;
    pointer-events: none;
    transform: translateY(8px);
    transition: opacity .18s ease, transform .18s ease;
}
.acs-back-to-top.visible { opacity: .92; pointer-events: auto; transform: translateY(0); }

.acs-legacy-navigation { display: none !important; }

.acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: stretch;
    gap: 14px;
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > h2 { grid-column: 1 / -1; }
.acs-summary-heading-row {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-width: 0;
}
.acs-summary-heading-row > h2 {
    min-width: 0;
    margin: 0 !important;
}
.acs-summary-print-button {
    flex: 0 0 auto;
    margin-left: auto;
    white-space: nowrap;
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > .acs-suite-nav {
    grid-column: 1 / -1;
    width: 100%;
    margin: -2px 0 0 !important;
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > .summary {
    display: flex;
    flex-direction: column;
    min-width: 0;
    margin: 0 !important;
    padding: 14px !important;
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > .summary.acs-summary-orphan {
    grid-column: 1 / -1;
    width: calc(50% - 7px);
    justify-self: start;
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary > .details-link {
    margin-top: auto;
}
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary h1 { font-size: 20px !important; }
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary .acs-summary-card { min-height: 62px; padding: 9px; }
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary .acs-summary-value { font-size: 20px; }
.acs-report-ui[data-acs-report-kind="acs-summary"] .summary .details-link a { padding: 6px 9px !important; }
.acs-report-ui[data-acs-report-kind="acs-summary"] .acs-compact-summary {
    width: 100%;
    max-width: none;
    margin: 12px 0 !important;
}

.details-link { text-align: right !important; }
.details-link a {
    display: inline-flex !important;
    padding: 7px 11px !important;
    text-decoration: none !important;
    border: 1px solid #bfd0e5 !important;
    border-radius: 9px !important;
    font-size: 12px;
    font-weight: 750 !important;
}
.details-link a:hover { background: var(--acs-brand-soft) !important; color: var(--acs-brand) !important; }
.dropdown { text-align: left !important; margin: 10px 0 16px !important; }
.dropdown button { background: var(--acs-brand) !important; border-radius: 9px !important; }
.dropdown-content { left: 0 !important; transform: none !important; border-radius: 10px; overflow: hidden; }
.compliance-status { border-radius: 999px !important; padding: 4px 9px !important; }

@media (max-width: 1100px) {
    .acs-detail-overview { grid-template-columns: minmax(0, 1fr); }
    .acs-information-values { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (min-width: 1101px) {
    .acs-information-band[data-acs-information-group="standards"] .acs-information-field:nth-child(4) {
        grid-column: 1;
    }
}

@media (max-width: 900px) {
    body.acs-report-ui { padding: 12px !important; }
    body.acs-report-ui > .header { padding: 18px !important; border-radius: 13px; }
    .acs-summary-grid { grid-template-columns: repeat(2, minmax(115px, 1fr)); }
    .acs-toolbar { position: static; align-items: stretch; }
    .acs-control { min-width: 100%; }
    .acs-filter-count { text-align: left; }
    .acs-metadata-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .acs-meta-item.acs-meta-wide { grid-column: span 2; }
    .acs-meta-item.acs-meta-full { grid-column: 1 / -1; }
    body.acs-report-ui table {
        display: block;
        overflow-x: auto;
        white-space: nowrap;
        scrollbar-width: thin;
        scrollbar-color: var(--acs-suite-accent) var(--acs-panel-muted);
    }
    body.acs-report-ui th,
    body.acs-report-ui td { padding: 8px 9px !important; font-size: 12px !important; }
    .acs-mobile-status-preview {
        display: flex;
        align-items: center;
        gap: 6px;
        width: max-content;
        margin-top: 5px;
    }
    .acs-mobile-status-preview::before {
        content: "Result";
        color: var(--acs-muted);
        font-size: 9px;
        font-weight: 750;
        text-transform: uppercase;
    }
    .acs-mobile-table-note {
        display: block;
        margin: 8px 0 12px;
        padding: 8px 10px;
        color: var(--acs-muted);
        background: var(--acs-panel-muted);
        border: 1px solid var(--acs-line);
        border-radius: 8px;
        font-size: 10.5px;
    }
    .acs-suite-nav {
        position: static;
        flex-wrap: wrap;
        overflow: visible;
    }
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section { grid-template-columns: 1fr; }
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > .summary.acs-summary-orphan {
        grid-column: 1;
        width: 100%;
    }
    .acs-overview-results { grid-template-columns: minmax(0, 1fr); }
    .acs-overview-results[data-acs-card-count="2"] {
        grid-template-columns: minmax(0, 1fr);
    }
    .acs-information-band {
        grid-template-columns: minmax(0, 1fr);
        gap: 7px;
    }
    .acs-information-values { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .system-info table,
    .acs-results-summary table {
        display: table !important;
        width: 100% !important;
        table-layout: fixed !important;
        white-space: normal !important;
    }
    .system-info th,
    .acs-results-summary th {
        width: 42% !important;
        min-width: 0 !important;
        white-space: normal !important;
        word-break: normal !important;
        overflow-wrap: anywhere !important;
    }
    .system-info td,
    .acs-results-summary td { white-space: normal !important; }
    .acs-back-to-top { right: 8px; bottom: 8px; }
}

@media (max-width: 560px) {
    .result-summary.acs-compact-summary,
    .summary-container.acs-compact-summary,
    .card.acs-compact-summary { padding: 15px !important; }
    .acs-compact-summary-header {
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 4px 12px;
    }
    .acs-progress-row {
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 4px 10px;
    }
    .acs-progress-track { grid-column: 1 / -1; grid-row: 2; }
    .acs-progress-count { grid-column: 2; grid-row: 1; }
    .acs-case-topline { display: block; }
    .acs-case-status { margin-top: 10px; }
    .acs-metadata-grid { grid-template-columns: 1fr; }
    .acs-meta-item.acs-meta-wide { grid-column: span 1; }
    .acs-meta-item.acs-meta-full { grid-column: 1; }
    .acs-overview-heading {
        align-items: flex-start;
        flex-direction: column;
        gap: 3px;
    }
    .acs-overview-field-count { white-space: normal; }
    .acs-information-values { grid-template-columns: minmax(0, 1fr); }
    .acs-result-group { padding: 11px; border-radius: 12px; }
    .acs-case-overview { margin: 0 -11px 11px; padding: 13px; }
}

@media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
    *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}

@media print {
    @page { size: A4 landscape; margin: 9mm; }
    body.acs-report-ui { padding: 0 !important; background: #fff !important; font-size: 10pt !important; }
    body.acs-report-ui > * { max-width: none; }
    .acs-toolbar,
    .acs-suite-nav,
    .acs-back-to-main,
    .acs-back-to-top,
    .acs-summary-print-button,
    .acs-group-toggle,
    .acs-mobile-table-note,
    .details-link { display: none !important; }
    .result-summary,
    .summary-container,
    .system-info,
    .acs-results-summary,
    .summary { box-shadow: none !important; break-inside: avoid; }
    .acs-summary-overview > .acs-information-overview,
    .acs-overview-results > .acs-overview-result-card {
        padding: 12px !important;
        box-shadow: none !important;
        break-inside: avoid !important;
    }
    .acs-information-band {
        grid-template-columns: 120px minmax(0, 1fr);
        gap: 14px;
        padding: 4px 0;
    }
    .acs-information-values {
        grid-template-columns: repeat(4, minmax(0, 1fr));
        row-gap: 5px;
    }
    .acs-information-band[data-acs-information-group="standards"] .acs-information-field:nth-child(4) {
        grid-column: 1;
    }
    .acs-overview-results {
        grid-template-columns: minmax(0, 3fr) minmax(280px, 2fr);
        gap: 14px;
        break-inside: avoid;
    }
    .acs-overview-results[data-acs-card-count="2"] {
        grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
    }
    .acs-information-band,
    .acs-overview-result-entry { break-inside: avoid; }
    .acs-report-ui .acs-information-band h3 {
        color: var(--acs-heading) !important;
        background: var(--acs-brand-soft) !important;
        border: 1px solid var(--acs-line) !important;
    }
    .acs-detail-overview { display: block !important; }
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section {
        display: block !important;
        margin: 0 !important;
        padding: 0 !important;
        background: #fff !important;
        border: 0 !important;
        box-shadow: none !important;
        break-before: page;
        page-break-before: always;
    }
    .acs-summary-heading-row {
        margin: 0 0 4mm;
        break-after: avoid-page;
        page-break-after: avoid;
    }
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > .summary {
        display: inline-block !important;
        width: 100% !important;
        margin: 0 0 5mm !important;
        padding: 4mm !important;
        vertical-align: top;
        break-inside: avoid !important;
        page-break-inside: avoid !important;
    }
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary-section > .summary:last-child {
        margin-bottom: 0 !important;
    }
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary .acs-compact-summary,
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary h1,
    .acs-report-ui[data-acs-report-kind="acs-summary"] .summary h2 {
        break-inside: avoid !important;
        page-break-inside: avoid !important;
    }
    .acs-filter-hidden,
    .acs-result-group.acs-collapsed > :not(.acs-case-overview):not(.test-suite-header):not(.suite-header):not(.acs-group-toggle):not(.acs-metadata-source) {
        display: revert !important;
    }
    .acs-result-group.acs-collapsed > .acs-case-overview .acs-case-description {
        display: block !important;
    }
    .acs-result-group.acs-collapsed > .acs-case-overview .acs-metadata-grid {
        display: grid !important;
    }
    tr.subtest-row-hidden { display: table-row !important; }
    .acs-empty-state { display: none !important; }
    .acs-print-banner {
        display: block !important;
        margin: 0 0 8mm;
        padding: 3mm 4mm;
        color: #475467;
        background: #f8fafc;
        border: 1px solid #d8e1ed;
        border-radius: 2mm;
        font-size: 9pt;
    }
    body.acs-report-ui table { break-inside: auto; }
    body.acs-report-ui tr { break-inside: avoid; }
    body.acs-report-ui a { color: inherit; text-decoration: none; }
}
"""


REPORT_JS = r"""
(function () {
    "use strict";

    var STATUS_ORDER = [
        "pass", "fail", "fail-waiver", "warning", "passed-partial",
        "skipped", "aborted", "ignored", "not-implemented", "not-tested",
        "pal-not-supported", "unknown", "info"
    ];
    var STATUS_LABELS = {
        "pass": "Passed",
        "fail": "Failed",
        "fail-waiver": "Failed with waiver",
        "warning": "Warning",
        "passed-partial": "Passed (Partial)",
        "skipped": "Skipped",
        "aborted": "Aborted",
        "ignored": "Ignored",
        "not-implemented": "Not implemented",
        "not-tested": "Not tested",
        "pal-not-supported": "PAL not supported",
        "unknown": "Unknown",
        "info": "Info"
    };
    var STATUS_DISPLAY = {
        "pass": "PASSED",
        "fail": "FAILED",
        "fail-waiver": "FAILED WITH WAIVER",
        "warning": "WARNING",
        "passed-partial": "PASSED (PARTIAL)",
        "skipped": "SKIPPED",
        "aborted": "ABORTED",
        "ignored": "IGNORED",
        "not-implemented": "NOT IMPLEMENTED",
        "not-tested": "NOT TESTED",
        "pal-not-supported": "PAL NOT SUPPORTED",
        "unknown": "UNKNOWN",
        "info": "INFO"
    };
    var STATUS_ACCENTS = {
        "pass": "#16a34a",
        "fail": "#dc2626",
        "fail-waiver": "#f97316",
        "warning": "#f97316",
        "passed-partial": "#0284c7",
        "skipped": "#94a3b8",
        "aborted": "#64748b",
        "ignored": "#94a3b8",
        "not-implemented": "#64748b",
        "not-tested": "#64748b",
        "pal-not-supported": "#4f6b9b",
        "unknown": "#94a3b8",
        "info": "#4f6b9b"
    };
    var SUITE_PROFILES = {
        "bsa": {
            label: "BSA / SBSA",
            subtitle: "Hierarchical rule and subtest results with focused status navigation.",
            layout: "hierarchy"
        },
        "sct": {
            label: "UEFI SCT",
            subtitle: "Case context, entry-point GUIDs, source paths, and subtest evidence in one view.",
            layout: "metadata"
        },
        "tpm": {
            label: "BBSR TPM",
            subtitle: "TPM case context and verification results grouped for quick review.",
            layout: "metadata"
        },
        "fwts": {
            label: "FWTS",
            subtitle: "Firmware test suites grouped with requirements, descriptions, and evidence.",
            layout: "suite"
        },
        "pfdi": {
            label: "PFDI",
            subtitle: "Platform fault detection checks with concise results and reasons.",
            layout: "suite"
        },
        "post-script": {
            label: "Post-script",
            subtitle: "Post-processing validation checks in a compact operational view.",
            layout: "flat"
        },
        "sbmr": {
            label: "SBMR",
            subtitle: "Management interface suites and cases grouped by execution area.",
            layout: "suite"
        },
        "scmi": {
            label: "SCMI",
            subtitle: "Protocol suites, access reasons, and testcase outcomes in focused sections.",
            layout: "suite"
        },
        "os": {
            label: "OS tests",
            subtitle: "Operating-system validations grouped by suite and testcase context.",
            layout: "case"
        },
        "standalone": {
            label: "Standalone tests",
            subtitle: "Independent validation tools grouped by suite and testcase context.",
            layout: "case"
        }
    };

    function normalizeText(value) {
        return (value || "").replace(/\s+/g, " ").trim();
    }

    function statusSlug(value) {
        var slug = normalizeText(value).toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 48);
        return slug ? "status-" + slug : "unknown";
    }

    function classifyStatus(value, className, allowDynamic) {
        var classes = " " + (className || "").toLowerCase().replace(/_/g, "-") + " ";
        var text = normalizeText(value).toUpperCase().replace(/_/g, " ");
        if (!text || text === "N/A" || text === "NA" || text === "-") {
            return "";
        }
        if (classes.indexOf(" fail-waiver ") >= 0 || classes.indexOf(" waiver ") >= 0 ||
                /FAIL(?:ED|URE)?(?:\s+|\s*\()(?:WITH\s+)?WAIVER\)?/.test(text)) {
            return "fail-waiver";
        }
        if (classes.indexOf(" passed-partial ") >= 0 || text.indexOf("PARTIAL") >= 0) {
            return "passed-partial";
        }
        if (classes.indexOf(" pal-not-supported ") >= 0 || text.indexOf("PAL NOT SUPPORTED") >= 0) {
            return "pal-not-supported";
        }
        if (classes.indexOf(" not-implemented ") >= 0 || text.indexOf("NOT IMPLEMENTED") >= 0) {
            return "not-implemented";
        }
        if (classes.indexOf(" not-tested ") >= 0 || text.indexOf("NOT TESTED") >= 0) {
            return "not-tested";
        }
        if (text === "IGNORED" || /KNOWN\s+.+\s+LIMITATION/.test(text) || text === "NOT SUPPORTED") {
            return "ignored";
        }
        if (text.indexOf("PASSED WITH WARNING") === 0) {
            return "warning";
        }
        if (classes.indexOf(" fail ") >= 0 || /^(FAIL|FAILED|FAILURE)(?:\b|\s)/.test(text)) {
            return "fail";
        }
        if (classes.indexOf(" warning ") >= 0 || classes.indexOf(" warnings ") >= 0 ||
                text === "WARN" || text.indexOf("WARNING") === 0) {
            return "warning";
        }
        if (classes.indexOf(" aborted ") >= 0 || text.indexOf("ABORT") === 0) {
            return "aborted";
        }
        if (classes.indexOf(" skipped ") >= 0 || text.indexOf("SKIP") === 0) {
            return "skipped";
        }
        if (classes.indexOf(" pass ") >= 0 || text.indexOf("PASS") === 0 || text === "SUCCESS") {
            return "pass";
        }
        if (classes.indexOf(" info ") >= 0 || text === "INFO") {
            return "info";
        }
        if (classes.indexOf(" ignored ") >= 0) {
            return "ignored";
        }
        if (classes.indexOf(" unknown ") >= 0 || text === "UNKNOWN") {
            return "unknown";
        }
        return allowDynamic ? statusSlug(text) : "";
    }

    function classifyStatusCell(cell, allowDynamic) {
        var text = normalizeText(cell.textContent).toUpperCase().replace(/_/g, " ");
        if (!text || text === "N/A" || text === "NA" || text === "-" || text.length > 100) {
            return "";
        }
        var known = classifyStatus(text, cell.className, false);
        if (known) {
            return known;
        }
        return allowDynamic ? classifyStatus(text, cell.className, true) : "";
    }

    function statusLabel(status, originalText) {
        if (STATUS_LABELS[status]) {
            return STATUS_LABELS[status];
        }
        return normalizeText(originalText).replace(/_/g, " ");
    }

    function statusDisplay(status, originalText) {
        return STATUS_DISPLAY[status] || normalizeText(originalText).replace(/_/g, " ");
    }

    function statusAccent(status) {
        return STATUS_ACCENTS[status] || "#64748b";
    }

    function addReportHeading() {
        var heading = document.querySelector("body > h1, body > .container h1");
        if (!heading || heading.previousElementSibling &&
                heading.previousElementSibling.classList.contains("acs-report-kicker")) {
            return;
        }
        var profile = SUITE_PROFILES[document.body.getAttribute("data-acs-suite")] || {};
        var isDetailed = Boolean(document.querySelector(".detailed-summary, .detailed-container"));
        document.body.setAttribute("data-acs-view", isDetailed ? "detail" : "summary");
        if (isDetailed && /\bTest Summary$/i.test(normalizeText(heading.textContent))) {
            heading.textContent = normalizeText(heading.textContent)
                .replace(/\bTest Summary$/i, "Detailed Results");
            document.title = heading.textContent;
        }
        var kicker = document.createElement("div");
        kicker.className = "acs-report-kicker";
        kicker.textContent = "SystemReady ACS \u00b7 " + (profile.label || "Validation report");
        heading.parentNode.insertBefore(kicker, heading);

        var subtitle = document.createElement("p");
        subtitle.className = "acs-report-subtitle";
        subtitle.textContent = profile.subtitle ||
            "Searchable results, clear status counts, and print-ready detail.";
        var mainPage = document.body.getAttribute("data-acs-main-page");
        if (isDetailed && mainPage) {
            var backLink = document.createElement("a");
            backLink.className = "acs-back-to-main";
            backLink.href = mainPage;
            backLink.textContent = "\u2190 Back to Main Page";
            kicker.appendChild(backLink);
        }
        heading.insertAdjacentElement("afterend", subtitle);
    }

    function summaryTableRows(table) {
        var entries = [];
        Array.prototype.forEach.call(table.querySelectorAll("tr"), function (row) {
            var cells = row.cells;
            if (!cells || cells.length < 2 || row.querySelector("th")) {
                return;
            }
            var label = normalizeText(cells[0].textContent);
            var value = normalizeText(cells[cells.length - 1].textContent);
            if (!label) {
                return;
            }
            var numericValue = Number(value.replace(/,/g, ""));
            entries.push({
                label: label,
                value: value || "0",
                count: isFinite(numericValue) ? Math.max(0, numericValue) : 0,
                valueClass: cells[cells.length - 1].className
            });
        });
        return entries;
    }

    function upgradeCompactSummary(table, entries) {
        var container = table.closest(".result-summary, .summary-container, .card");
        if (!container) {
            return false;
        }
        var totalEntry = entries.find(function (entry) {
            return /^Total\b/i.test(entry.label);
        });
        var statusEntries = entries.filter(function (entry) {
            return entry !== totalEntry;
        });
        if (!statusEntries.length) {
            return false;
        }
        var derivedTotal = statusEntries.reduce(function (sum, entry) {
            return sum + entry.count;
        }, 0);
        var totalCount = totalEntry ? totalEntry.count : derivedTotal;
        var totalDisplay = totalEntry ? totalEntry.value : String(derivedTotal);

        container.classList.add("acs-compact-summary");
        var heading = container.querySelector("h2");
        if (heading && heading.parentNode !== container) {
            heading = null;
        }
        var header = document.createElement("div");
        header.className = "acs-compact-summary-header";
        container.insertBefore(header, heading || container.firstChild);
        if (heading) {
            heading.textContent = "Test-result summary";
            header.appendChild(heading);
        } else {
            heading = document.createElement("h2");
            heading.textContent = "Test-result summary";
            header.appendChild(heading);
        }
        var total = document.createElement("span");
        total.className = "acs-compact-summary-total";
        total.textContent = totalDisplay + " suite-reported " +
            (totalCount === 1 ? "test" : "tests");
        header.appendChild(total);

        var list = document.createElement("div");
        list.className = "acs-progress-list";
        list.setAttribute("role", "list");
        list.setAttribute("aria-label", "Suite-reported test results");
        statusEntries.forEach(function (entry) {
            var status = classifyStatus(entry.label, entry.valueClass, true);
            var progressMaximum = Math.max(totalCount, entry.count, 1);
            var percentage = totalCount > 0 ?
                Math.min(100, (entry.count / totalCount) * 100) : 0;
            var item = document.createElement("div");
            item.className = "acs-progress-row acs-progress-" + (status || "unknown");
            item.setAttribute("role", "listitem");
            item.setAttribute("data-acs-summary-status", status || "unknown");
            item.setAttribute("data-acs-zero", String(entry.count === 0));

            var label = document.createElement("span");
            label.className = "acs-progress-label";
            label.textContent = status === "passed-partial" ?
                statusLabel(status, entry.label) : entry.label;

            var track = document.createElement("span");
            track.className = "acs-progress-track";
            track.setAttribute("role", "progressbar");
            track.setAttribute("aria-label", entry.label);
            track.setAttribute("aria-valuemin", "0");
            track.setAttribute("aria-valuemax", String(progressMaximum));
            track.setAttribute("aria-valuenow", String(entry.count));
            var fill = document.createElement("span");
            fill.className = "acs-progress-fill";
            fill.setAttribute("aria-hidden", "true");
            fill.style.backgroundColor = statusAccent(status);
            fill.style.width = percentage.toFixed(4).replace(/\.?0+$/, "") + "%";
            fill.style.minWidth = entry.count > 0 ? "2px" : "0";
            track.appendChild(fill);

            var count = document.createElement("span");
            count.className = "acs-progress-count";
            count.textContent = entry.value;

            item.appendChild(label);
            item.appendChild(track);
            item.appendChild(count);
            list.appendChild(item);
        });

        table.classList.add("acs-summary-source");
        table.setAttribute("aria-hidden", "true");
        table.insertAdjacentElement("afterend", list);
        return true;
    }

    function upgradeSummaryTables() {
        Array.prototype.forEach.call(document.querySelectorAll("table.summary-table"), function (table) {
            if (table.classList.contains("acs-summary-source")) {
                return;
            }
            upgradeCompactSummary(table, summaryTableRows(table));
        });
    }

    function textWithoutPrefix(element, prefix) {
        return normalizeText(element ? element.textContent : "").replace(prefix, "").trim();
    }

    function headingFields(group) {
        var fields = {};
        Array.prototype.forEach.call(group.querySelectorAll(".heading"), function (heading) {
            var valueNode = heading.querySelector("span");
            var value = normalizeText(valueNode ? valueNode.textContent : "");
            var label = normalizeText(heading.textContent);
            if (value) {
                label = label.slice(0, Math.max(0, label.length - value.length));
            }
            label = label.replace(/:\s*$/, "").toLowerCase();
            fields[label] = value || "N/A";
            heading.classList.add("acs-metadata-source");
            heading.setAttribute("aria-hidden", "true");
        });
        return fields;
    }

    function metaItem(label, value, className) {
        var item = document.createElement("div");
        item.className = "acs-meta-item" + (className ? " " + className : "");
        var name = document.createElement("span");
        name.className = "acs-meta-label";
        name.textContent = label;
        var content = document.createElement("span");
        content.className = "acs-meta-value";
        content.textContent = value || "N/A";
        item.appendChild(name);
        item.appendChild(content);
        return item;
    }

    function sourceMetaItem(label, source, prefix, className) {
        if (!source) {
            return null;
        }
        var item = metaItem(label, "", className);
        var content = item.querySelector(".acs-meta-value");
        var listItems = source.querySelectorAll("li");
        if (listItems.length) {
            var list = document.createElement("ul");
            list.className = "acs-meta-list";
            Array.prototype.forEach.call(listItems, function (entry) {
                var listItem = document.createElement("li");
                listItem.textContent = normalizeText(entry.textContent);
                list.appendChild(listItem);
            });
            content.textContent = "";
            content.appendChild(list);
        } else {
            content.textContent = textWithoutPrefix(source, prefix) || "N/A";
        }
        return item;
    }

    function caseOverview(title, description, eyebrow, statusText) {
        var overview = document.createElement("section");
        overview.className = "acs-case-overview";
        var top = document.createElement("div");
        top.className = "acs-case-topline";
        var identity = document.createElement("div");
        identity.className = "acs-case-identity";
        var context = document.createElement("div");
        context.className = "acs-case-eyebrow";
        context.textContent = eyebrow || "Test case";
        var heading = document.createElement("h3");
        heading.className = "acs-case-title";
        heading.textContent = title || "Unnamed test case";
        identity.appendChild(context);
        identity.appendChild(heading);
        if (description && description !== "N/A") {
            var detail = document.createElement("p");
            detail.className = "acs-case-description";
            detail.textContent = description;
            identity.appendChild(detail);
        }
        top.appendChild(identity);
        if (statusText && statusText !== "N/A") {
            var status = classifyStatus(statusText, "", true) || "unknown";
            var statusWrap = document.createElement("div");
            statusWrap.className = "acs-case-status";
            var pill = document.createElement("span");
            pill.className = "acs-status-pill " + status;
            pill.setAttribute("data-acs-status", status);
            pill.setAttribute("data-acs-status-label", statusLabel(status, statusText));
            pill.textContent = statusDisplay(status, statusText);
            statusWrap.appendChild(pill);
            top.appendChild(statusWrap);
        }
        overview.appendChild(top);
        return overview;
    }

    function buildMetadataOverview(group) {
        var fields = headingFields(group);
        var suiteName = fields["test suite name"] || "N/A";
        var subSuite = fields["sub test suite"] || "N/A";
        var overview = caseOverview(
            fields["test case"],
            fields["test case description"],
            "Test case",
            fields["test result"]
        );
        overview.setAttribute(
            "data-acs-jump-context",
            suiteName + (subSuite !== "N/A" ? " \u00b7 " + subSuite : "")
        );
        overview.setAttribute("data-acs-test-suite", suiteName);
        overview.setAttribute("data-acs-sub-test-suite", subSuite);
        overview.setAttribute("data-acs-test-case", fields["test case"] || "N/A");
        var grid = document.createElement("div");
        grid.className = "acs-metadata-grid";
        grid.appendChild(metaItem("Test suite", suiteName));
        grid.appendChild(metaItem("Sub test suite", subSuite));
        if (fields["test entry point guid"]) {
            grid.appendChild(metaItem(
                "Test entry point GUID",
                fields["test entry point guid"],
                "acs-meta-code"
            ));
        }
        if (fields.reason) {
            grid.appendChild(metaItem("Reason", fields.reason, "acs-meta-wide"));
        }
        if (fields["device path"]) {
            grid.appendChild(metaItem("Device path", fields["device path"], "acs-meta-code"));
        }
        var suiteInfo = group.querySelector(".test-suite-info");
        if (suiteInfo) {
            grid.appendChild(sourceMetaItem(
                "Test suite info",
                suiteInfo,
                /^(?:Test_suite_info|Test suite info):\s*/i,
                "acs-meta-full"
            ));
            suiteInfo.classList.add("acs-metadata-source");
            suiteInfo.setAttribute("aria-hidden", "true");
        }
        overview.appendChild(grid);
        group.insertBefore(overview, group.firstChild);
    }

    function buildCaseOverview(group) {
        var suiteHeader = group.querySelector(".test-suite-header");
        var suiteDescription = group.querySelector(".test-suite-description");
        var caseHeader = group.querySelector(".test-case-header");
        var caseDescription = group.querySelector(".test-case-description");
        var suiteName = textWithoutPrefix(suiteHeader, /^Test Suite:\s*/i);
        var overview = caseOverview(
            textWithoutPrefix(caseHeader, /^Test Case:\s*/i),
            textWithoutPrefix(caseDescription, /^Description:\s*/i),
            "Test case",
            ""
        );
        overview.setAttribute("data-acs-jump-context", suiteName);
        overview.setAttribute("data-acs-test-suite", suiteName);
        overview.setAttribute(
            "data-acs-test-case",
            textWithoutPrefix(caseHeader, /^Test Case:\s*/i)
        );
        var grid = document.createElement("div");
        grid.className = "acs-metadata-grid";
        grid.appendChild(metaItem("Test suite", suiteName));
        grid.appendChild(metaItem(
            "Suite description",
            textWithoutPrefix(suiteDescription, /^Description:\s*/i),
            "acs-meta-wide"
        ));
        var suiteInfo = group.querySelector(".test-suite-info");
        if (suiteInfo) {
            grid.appendChild(sourceMetaItem(
                "Test suite info",
                suiteInfo,
                /^(?:Test_suite_info|Test suite info):\s*/i,
                "acs-meta-full"
            ));
        }
        overview.appendChild(grid);
        [suiteHeader, suiteDescription, suiteInfo, caseHeader, caseDescription].forEach(function (element) {
            if (element) {
                element.classList.add("acs-metadata-source");
                element.setAttribute("aria-hidden", "true");
            }
        });
        group.insertBefore(overview, group.firstChild);
    }

    function buildSuiteOverview(group) {
        var suiteHeader = group.querySelector(":scope > .test-suite-header, :scope > .suite-header");
        if (!suiteHeader) {
            return;
        }
        var suiteDescription = group.querySelector(":scope > .test-suite-description");
        var suiteInfo = group.querySelector(":scope > .test-suite-info");
        var suiteReason = group.querySelector(":scope > .suite-reason");
        var suiteName = textWithoutPrefix(suiteHeader, /^Test Suite:\s*/i);
        var description = textWithoutPrefix(
            suiteDescription,
            /^(?:Suite )?Description:\s*/i
        );
        var overview = caseOverview(suiteName, description, "Test suite", "");
        overview.setAttribute("data-acs-test-suite", suiteName);
        [
            "data-acs-summary-outcomes",
            "data-acs-summary-failed",
            "data-acs-summary-failed-with-waiver"
        ].forEach(function (attribute) {
            if (suiteHeader.hasAttribute(attribute)) {
                overview.setAttribute(attribute, suiteHeader.getAttribute(attribute));
            }
        });
        var grid = document.createElement("div");
        grid.className = "acs-metadata-grid";
        if (suiteInfo) {
            grid.appendChild(sourceMetaItem(
                "Test suite info",
                suiteInfo,
                /^(?:Test_suite_info|Test suite info):\s*/i,
                "acs-meta-full"
            ));
        }
        if (suiteReason) {
            grid.appendChild(sourceMetaItem(
                "Reason",
                suiteReason,
                /^Reason:\s*/i,
                "acs-meta-full"
            ));
        }
        if (grid.children.length) {
            overview.appendChild(grid);
        }
        [suiteHeader, suiteDescription, suiteInfo, suiteReason].forEach(function (element) {
            if (element) {
                element.classList.add("acs-metadata-source");
                element.setAttribute("aria-hidden", "true");
            }
        });
        group.insertBefore(overview, group.firstChild);
    }

    function buildFlatOverview(detail, profile) {
        var sectionTitle = detail.querySelector(":scope > h3");
        var heading = detail.querySelector(":scope > h2");
        var rawTitle = normalizeText(sectionTitle ? sectionTitle.textContent : "");
        var titleParts = rawTitle.match(/^([^:]+):\s*(.*)$/);
        var title = titleParts ? titleParts[1] : (rawTitle || profile.label || "Test results");
        var description = titleParts ? titleParts[2] : "";
        var overview = caseOverview(title, description, "Test suite", "");
        overview.setAttribute("data-acs-test-suite", title);
        [heading, sectionTitle].forEach(function (element) {
            if (element) {
                element.classList.add("acs-metadata-source");
                element.setAttribute("aria-hidden", "true");
            }
        });
        detail.insertBefore(overview, detail.firstChild);
    }

    function wrapThroughFirstTable(start, className) {
        var parent = start.parentNode;
        var group = document.createElement("article");
        group.className = "acs-result-group " + className;
        parent.insertBefore(group, start);
        var node = start;
        while (node) {
            var next = node.nextElementSibling;
            group.appendChild(node);
            if (node.tagName === "TABLE") {
                break;
            }
            node = next;
        }
        return group;
    }

    function wrapUntilNextSuite(start, selector) {
        var parent = start.parentNode;
        var group = document.createElement("section");
        group.className = "acs-result-group acs-suite-card";
        parent.insertBefore(group, start);
        var node = start;
        while (node) {
            var next = node.nextElementSibling;
            if (node !== start && node.matches(selector)) {
                break;
            }
            group.appendChild(node);
            node = next;
        }
        return group;
    }

    function upgradeSuiteLayouts() {
        var suiteType = document.body.getAttribute("data-acs-suite");
        var profile = SUITE_PROFILES[suiteType] || {};
        var detail = document.querySelector(".detailed-summary, .detailed-container");
        if (!detail || detail.classList.contains("acs-layout-ready")) {
            return;
        }
        detail.classList.add("acs-layout-ready");

        if (profile.layout === "metadata") {
            Array.prototype.forEach.call(detail.querySelectorAll(":scope > .heading"), function (heading) {
                if (heading.parentNode !== detail ||
                        !/^Test Suite Name:/i.test(normalizeText(heading.textContent))) {
                    return;
                }
                var group = wrapThroughFirstTable(heading, "acs-case-card");
                buildMetadataOverview(group);
            });
        } else if (profile.layout === "case") {
            Array.prototype.forEach.call(detail.querySelectorAll(":scope > .test-suite-header"), function (header) {
                if (header.parentNode !== detail) {
                    return;
                }
                var group = wrapThroughFirstTable(header, "acs-case-card");
                buildCaseOverview(group);
            });
        } else if (profile.layout === "suite" || profile.layout === "hierarchy") {
            var selector = ".test-suite-header, .suite-header";
            Array.prototype.forEach.call(detail.querySelectorAll(":scope > .test-suite-header, :scope > .suite-header"), function (header) {
                if (header.parentNode !== detail) {
                    return;
                }
                buildSuiteOverview(wrapUntilNextSuite(header, selector));
            });
        } else if (profile.layout === "flat") {
            detail.classList.add("acs-result-group", "acs-flat-card");
            buildFlatOverview(detail, profile);
        }
    }

    function columnClass(label) {
        var text = normalizeText(label).toLowerCase();
        if (/result|status/.test(text)) { return "acs-col-status"; }
        if (/guid/.test(text)) { return "acs-col-guid"; }
        if (/path/.test(text)) { return "acs-col-path"; }
        if (/waiver/.test(text)) { return "acs-col-waiver"; }
        if (/reason/.test(text)) { return "acs-col-reason"; }
        if (/description/.test(text)) { return "acs-col-description"; }
        if (/number|^#$|test case/.test(text)) { return "acs-col-number"; }
        return "";
    }

    function upgradeTableColumns() {
        var suiteType = document.body.getAttribute("data-acs-suite");
        var collapseReasons = suiteType === "sct" || suiteType === "fwts";
        Array.prototype.forEach.call(document.querySelectorAll("table:not(.summary-table)"), function (table) {
            if (!table.tHead || !table.tHead.rows.length) {
                return;
            }
            var headings = Array.prototype.slice.call(table.tHead.rows[0].cells);
            headings.forEach(function (heading, index) {
                var className = columnClass(heading.textContent);
                if (!className) {
                    return;
                }
                heading.classList.add(className);
                Array.prototype.forEach.call(table.tBodies, function (body) {
                    Array.prototype.forEach.call(body.rows, function (row) {
                        var cell = row.cells[index];
                        if (!cell) {
                            return;
                        }
                        cell.classList.add(className);
                        if (className === "acs-col-path" &&
                                normalizeText(cell.textContent).length > 100 &&
                                !cell.querySelector(".acs-long-value")) {
                            var fullPath = normalizeText(cell.textContent);
                            var disclosure = document.createElement("details");
                            disclosure.className = "acs-long-value";
                            var label = document.createElement("summary");
                            label.textContent = "View source path";
                            var code = document.createElement("code");
                            code.textContent = fullPath;
                            disclosure.appendChild(label);
                            disclosure.appendChild(code);
                            cell.title = fullPath;
                            cell.textContent = "";
                            cell.appendChild(disclosure);
                        } else if (className === "acs-col-reason" &&
                                collapseReasons &&
                                !cell.querySelector(".acs-long-reason")) {
                            var reasonDisclosure = document.createElement("details");
                            reasonDisclosure.className = "acs-long-value acs-long-reason";
                            var reasonLabel = document.createElement("summary");
                            reasonLabel.textContent = "View full reason";
                            var reasonText = document.createElement("span");
                            reasonText.className = "acs-long-reason-text";
                            while (cell.firstChild) {
                                reasonText.appendChild(cell.firstChild);
                            }
                            reasonDisclosure.appendChild(reasonLabel);
                            reasonDisclosure.appendChild(reasonText);
                            cell.appendChild(reasonDisclosure);
                        }
                    });
                });
            });
        });
    }

    function statusColumnIndex(table) {
        if (!table) {
            return -1;
        }
        if (typeof table.acsStatusColumnIndex === "number") {
            return table.acsStatusColumnIndex;
        }
        var index = -1;
        if (table.tHead && table.tHead.rows.length) {
            var rows = Array.prototype.slice.call(table.tHead.rows).reverse();
            rows.some(function (headerRow) {
                return Array.prototype.some.call(headerRow.cells, function (heading, cellIndex) {
                    var label = normalizeText(heading.textContent).toLowerCase();
                    if (/\b(result|status|outcome)\b/.test(label) &&
                            !/reason|summary|description/.test(label)) {
                        index = cellIndex;
                        return true;
                    }
                    return false;
                });
            });
        }
        table.acsStatusColumnIndex = index;
        return index;
    }

    function directStatusCell(row) {
        var cells = Array.prototype.slice.call(row.cells || []);
        var table = row.closest("table");
        var headerIndex = statusColumnIndex(table);
        if (headerIndex >= 0 && cells[headerIndex]) {
            var headerStatus = classifyStatusCell(cells[headerIndex], true);
            if (headerStatus) {
                return {
                    cell: cells[headerIndex],
                    status: headerStatus,
                    label: statusLabel(headerStatus, cells[headerIndex].textContent)
                };
            }
        }
        for (var index = 0; index < cells.length; index += 1) {
            var status = classifyStatusCell(cells[index], false);
            if (status) {
                return {
                    cell: cells[index],
                    status: status,
                    label: statusLabel(status, cells[index].textContent)
                };
            }
        }
        return null;
    }

    function upgradeStatusCells() {
        Array.prototype.forEach.call(document.querySelectorAll("table:not(.summary-table) tbody > tr"), function (row) {
            if (row.querySelector("table") || row.closest(".system-info, .acs-results-summary")) {
                return;
            }
            var found = directStatusCell(row);
            if (!found) {
                return;
            }
            var cell = found.cell;
            row.classList.add("acs-row-" + found.status);
            row.setAttribute("data-acs-row-status", found.status);
            row.style.setProperty("--acs-row-accent", statusAccent(found.status));
            cell.classList.add("acs-status-cell");
            cell.setAttribute("data-acs-status", found.status);
            cell.setAttribute("data-acs-status-label", found.label);
            if (cell.querySelector(".acs-status-pill")) {
                return;
            }
            var text = normalizeText(cell.textContent);
            var pill = document.createElement("span");
            pill.className = "acs-status-pill " + found.status;
            pill.setAttribute("data-acs-status", found.status);
            pill.setAttribute("data-acs-status-label", found.label);
            pill.textContent = statusDisplay(found.status, text);
            cell.textContent = "";
            cell.appendChild(pill);
        });
    }

    function decorateGroupStatuses() {
        var priority = [
            "fail", "fail-waiver", "warning", "passed-partial", "pass",
            "skipped", "aborted", "ignored", "not-implemented", "not-tested",
            "pal-not-supported", "unknown", "info"
        ];
        Array.prototype.forEach.call(document.querySelectorAll(".acs-result-group"), function (group) {
            var status = "";
            var overviewStatus = group.querySelector(".acs-case-status .acs-status-pill");
            if (overviewStatus) {
                status = overviewStatus.getAttribute("data-acs-status") || "";
            }
            if (!status) {
                priority.some(function (candidate) {
                    if (group.querySelector(".acs-row-" + candidate)) {
                        status = candidate;
                        return true;
                    }
                    return false;
                });
            }
            if (!status) {
                var firstStatusRow = group.querySelector("[data-acs-row-status]");
                status = firstStatusRow ? firstStatusRow.getAttribute("data-acs-row-status") : "";
            }
            if (status) {
                group.classList.add("acs-group-" + status);
                group.setAttribute("data-acs-group-status", status);
                group.style.borderLeftColor = statusAccent(status);
            }
        });
    }

    function removeDetailedCharts() {
        if (document.body.getAttribute("data-acs-view") !== "detail") {
            return;
        }
        Array.prototype.forEach.call(document.querySelectorAll(".chart-container"), function (chart) {
            chart.remove();
        });
        Array.prototype.forEach.call(document.querySelectorAll(".acs-chart-panel"), function (panel) {
            panel.remove();
        });
    }

    function decorateSummaryContext() {
        if (document.body.getAttribute("data-acs-view") !== "detail") {
            return;
        }
        Array.prototype.forEach.call(document.querySelectorAll(".result-summary p"), function (paragraph) {
            if (paragraph.querySelector("a[href*='RuleBasedGuide']")) {
                paragraph.classList.add("acs-reference-note");
                var link = paragraph.querySelector("a");
                link.textContent = "Rule result status guide \u2197";
            }
        });
    }

    function addMobileStatusPreviews() {
        Array.prototype.forEach.call(document.querySelectorAll("tr[data-acs-row-status]"), function (row) {
            if (row.querySelector(".acs-mobile-status-preview")) {
                return;
            }
            var statusCell = row.querySelector(".acs-status-cell");
            var pill = statusCell && statusCell.querySelector(".acs-status-pill");
            if (!pill) {
                return;
            }
            var description = row.querySelector(".acs-col-description") || row.cells[1] || row.cells[0];
            if (!description || description === statusCell) {
                return;
            }
            var preview = document.createElement("span");
            preview.className = "acs-mobile-status-preview";
            preview.appendChild(pill.cloneNode(true));
            description.appendChild(preview);
        });
    }

    function hideLegacyNavigation() {
        Array.prototype.forEach.call(document.querySelectorAll(".dropdown"), function (dropdown) {
            dropdown.classList.add("acs-legacy-navigation");
            dropdown.setAttribute("aria-hidden", "true");
        });
    }

    function addMobileTableNote(toolbar) {
        if (!toolbar || document.querySelector(".acs-mobile-table-note")) {
            return;
        }
        var note = document.createElement("p");
        note.className = "acs-mobile-table-note";
        note.textContent = "Results are repeated beside descriptions on narrow screens. Swipe tables for paths, reasons, and waivers.";
        toolbar.insertAdjacentElement("afterend", note);
    }

    function groupSearchText(group) {
        if (!group) {
            return "";
        }
        if (typeof group.acsSearchText === "string") {
            return group.acsSearchText;
        }
        var contextParts = [];
        Array.prototype.forEach.call(group.children, function (child) {
            if (child.tagName !== "TABLE" && !child.querySelector("table")) {
                contextParts.push(child.textContent);
            }
        });
        group.acsSearchText = normalizeText(contextParts.join(" ")).toLowerCase();
        return group.acsSearchText;
    }

    function statusRows() {
        var records = [];
        Array.prototype.forEach.call(document.querySelectorAll("table:not(.summary-table) tbody > tr"), function (row) {
            var table = row.closest("table");
            if (!table || table.closest(".system-info") || table.closest(".acs-results-summary") ||
                    row.querySelector("table")) {
                return;
            }
            var found = directStatusCell(row);
            if (found) {
                var group = row.closest(".acs-result-group");
                records.push({
                    row: row,
                    group: group,
                    status: found.status,
                    label: found.label,
                    text: normalizeText(row.textContent).toLowerCase() + " " + groupSearchText(group),
                    match: true
                });
            }
        });
        Array.prototype.forEach.call(document.querySelectorAll(".acs-result-group"), function (group) {
            var pill = group.querySelector(".acs-case-status .acs-status-pill[data-acs-status]");
            if (pill) {
                group.acsOverviewStatus = pill.getAttribute("data-acs-status");
                group.acsOverviewStatusLabel = pill.getAttribute("data-acs-status-label") ||
                    statusLabel(group.acsOverviewStatus, pill.textContent);
            }
            if (!pill) {
                return;
            }
            var status = pill.getAttribute("data-acs-status");
            records.push({
                row: null,
                group: group,
                status: status,
                label: pill.getAttribute("data-acs-status-label") || statusLabel(status, pill.textContent),
                text: groupSearchText(group),
                match: true
            });
        });
        return records;
    }

    function navigationTargets() {
        var profile = SUITE_PROFILES[document.body.getAttribute("data-acs-suite")] || {};
        if (profile.layout === "flat") {
            return {kind: "test suite", targets: []};
        }
        var kind = profile.layout === "case" || profile.layout === "metadata" ?
            "test case" : "test suite";
        var targets = [];
        Array.prototype.forEach.call(document.querySelectorAll(".acs-result-group"), function (group, index) {
            var title = group.querySelector(":scope > .acs-case-overview .acs-case-title");
            var label = normalizeText(title ? title.textContent : "");
            if (!label) {
                return;
            }
            if (!group.id) {
                group.id = "acs-" + kind.replace(/\s+/g, "-") + "-" + index;
            }
            var overview = group.querySelector(":scope > .acs-case-overview");
            var context = normalizeText(
                overview ? overview.getAttribute("data-acs-jump-context") : ""
            );
            targets.push({
                element: group,
                label: kind === "test case" && context ? context + " · " + label : label
            });
        });
        return {kind: kind, targets: targets};
    }

    function actionButton(label, className) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "acs-button" + (className ? " " + className : "");
        button.textContent = label;
        return button;
    }

    function setGroupCollapsed(group, collapsed) {
        group.classList.toggle("acs-collapsed", collapsed);
        var toggle = group.querySelector(":scope > .acs-group-toggle");
        if (toggle) {
            toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
            toggle.textContent = collapsed ? "Show details" : "Hide details";
        }
    }

    function enableGroupCollapsing(groups) {
        groups.forEach(function (group) {
            if (group.classList.contains("acs-flat-card") ||
                    !group.querySelector(":scope > .acs-case-overview")) {
                return;
            }
            if (!group.classList.contains("acs-collapsible")) {
                group.classList.add("acs-collapsible");
                var toggle = document.createElement("button");
                toggle.type = "button";
                toggle.className = "acs-group-toggle";
                toggle.addEventListener("click", function () {
                    setGroupCollapsed(group, !group.classList.contains("acs-collapsed"));
                });
                group.appendChild(toggle);
            }
            group.setAttribute("data-acs-default-collapsed", "false");
            setGroupCollapsed(group, false);
        });
    }

    function buildFailureSummary(groups) {
        var suiteType = document.body.getAttribute("data-acs-suite");
        var profile = SUITE_PROFILES[suiteType] || {};
        var groupBySuite = suiteType === "sct" ||
            profile.layout === "suite" || profile.layout === "hierarchy" ||
            profile.layout === "flat";
        var unitKind = groupBySuite ? "test suite" : "test case";
        var units = [];
        var unitMap = Object.create(null);

        groups.forEach(function (group) {
            var overview = group.querySelector(":scope > .acs-case-overview");
            var title = normalizeText(overview &&
                overview.querySelector(".acs-case-title") ?
                overview.querySelector(".acs-case-title").textContent : "");
            var suiteName = normalizeText(
                overview ? overview.getAttribute("data-acs-test-suite") : ""
            );
            var caseName = normalizeText(
                overview ? overview.getAttribute("data-acs-test-case") : ""
            );
            var subSuiteName = normalizeText(
                overview ? overview.getAttribute("data-acs-sub-test-suite") : ""
            );
            var label;
            var key;
            var unit;

            if (groupBySuite) {
                label = suiteName && suiteName !== "N/A" ? suiteName : title;
                label = label || "Unnamed test suite";
                key = "suite:" + normalizeText(label);
                unit = unitMap[key];
                if (!unit) {
                    unit = {
                        label: label,
                        groups: [],
                        outcomes: 0,
                        failed: 0,
                        waived: 0
                    };
                    unitMap[key] = unit;
                    units.push(unit);
                }
            } else {
                label = caseName && caseName !== "N/A" ? caseName : title;
                label = label || "Unnamed test case";
                var context = [];
                if (suiteName && suiteName !== "N/A" && suiteName !== label) {
                    context.push(suiteName);
                }
                if (subSuiteName && subSuiteName !== "N/A" &&
                        subSuiteName !== label && subSuiteName !== suiteName) {
                    context.push(subSuiteName);
                }
                context.push(label);
                label = context.join(" \u00b7 ");
                key = "case:" + JSON.stringify([
                    suiteName, subSuiteName, caseName || title
                ].map(function (value) { return normalizeText(value); }));
                unit = unitMap[key];
                if (!unit) {
                    unit = {
                        label: label,
                        groups: [],
                        outcomes: 0,
                        failed: 0,
                        waived: 0
                    };
                    unitMap[key] = unit;
                    units.push(unit);
                }
            }
            unit.groups.push(group);
            var groupStatuses = [];
            var leafRowCount = 0;
            Array.prototype.forEach.call(
                group.querySelectorAll("table tbody > tr"),
                function (row) {
                    if (row.closest(".acs-result-group") !== group || row.querySelector("table")) {
                        return;
                    }
                    leafRowCount += 1;
                    groupStatuses.push(
                        row.getAttribute("data-acs-row-status") || "unknown"
                    );
                }
            );
            if (!leafRowCount) {
                var overviewStatus = overview && overview.querySelector(
                    ".acs-case-status .acs-status-pill[data-acs-status]"
                );
                if (overviewStatus) {
                    groupStatuses.push(overviewStatus.getAttribute("data-acs-status"));
                }
            }
            var summaryOutcomes = overview && overview.hasAttribute(
                "data-acs-summary-outcomes"
            ) ? Number(overview.getAttribute("data-acs-summary-outcomes")) : NaN;
            var summaryFailed = overview && overview.hasAttribute(
                "data-acs-summary-failed"
            ) ? Number(overview.getAttribute("data-acs-summary-failed")) : NaN;
            var summaryWaived = overview && overview.hasAttribute(
                "data-acs-summary-failed-with-waiver"
            ) ? Number(overview.getAttribute(
                "data-acs-summary-failed-with-waiver"
            )) : NaN;
            if (Number.isFinite(summaryOutcomes) && summaryOutcomes >= 0 &&
                    Number.isFinite(summaryFailed) && summaryFailed >= 0 &&
                    Number.isFinite(summaryWaived) && summaryWaived >= 0) {
                unit.outcomes += summaryOutcomes;
                unit.failed += summaryFailed;
                unit.waived += summaryWaived;
            } else {
                unit.outcomes += groupStatuses.length;
                unit.failed += groupStatuses.filter(function (status) {
                    return status === "fail";
                }).length;
                unit.waived += groupStatuses.filter(function (status) {
                    return status === "fail-waiver";
                }).length;
            }
        });

        var totalFailed = 0;
        var totalWaived = 0;
        units.forEach(function (unit) {
            totalFailed += unit.failed;
            totalWaived += unit.waived;
        });

        var panel = document.createElement("aside");
        panel.className = "acs-failure-summary";
        panel.setAttribute("aria-labelledby", "acs-failure-summary-title");
        panel.setAttribute("data-acs-breakdown-kind", unitKind);
        panel.setAttribute("data-acs-unit-count", String(units.length));

        var header = document.createElement("div");
        header.className = "acs-compact-summary-header";
        var heading = document.createElement("h2");
        heading.id = "acs-failure-summary-title";
        heading.textContent = "Failures by " + unitKind;
        var total = document.createElement("span");
        total.className = "acs-compact-summary-total";
        total.textContent = units.length + " " + unitKind +
            (units.length === 1 ? "" : "s") + " \u00b7 " +
            totalFailed + " failed" +
            (totalWaived ? " \u00b7 " + totalWaived + " waived" : "");
        header.appendChild(heading);
        header.appendChild(total);
        panel.appendChild(header);

        var list = document.createElement("div");
        list.className = "acs-progress-list";
        list.setAttribute("role", "list");
        list.setAttribute(
            "aria-label",
            "Failure counts for every " + unitKind + " in this report"
        );
        units.forEach(function (unit) {
            var outcomeCount = unit.outcomes;
            var maximum = Math.max(outcomeCount, unit.failed + unit.waived, 1);
            var failedWidth = outcomeCount > 0 ?
                Math.min(100, (unit.failed / outcomeCount) * 100) : 0;
            var waiverWidth = outcomeCount > 0 ?
                Math.min(100 - failedWidth, (unit.waived / outcomeCount) * 100) : 0;
            var item = document.createElement("div");
            item.className = "acs-progress-row acs-failure-row";
            item.setAttribute("role", "listitem");
            item.setAttribute("data-acs-group-count", String(unit.groups.length));
            item.setAttribute("data-acs-outcomes", String(outcomeCount));
            item.setAttribute("data-acs-failed", String(unit.failed));
            item.setAttribute("data-acs-failed-with-waiver", String(unit.waived));
            item.setAttribute(
                "data-acs-zero", String(unit.failed === 0 && unit.waived === 0)
            );

            var label = document.createElement("span");
            label.className = "acs-progress-label";
            label.textContent = unit.label;

            var track = document.createElement("span");
            track.className = "acs-progress-track";
            track.setAttribute("role", "progressbar");
            track.setAttribute(
                "aria-label",
                unit.label + ": " + unit.failed + " failed, " +
                unit.waived + " failed with waiver, " + outcomeCount + " outcomes"
            );
            track.setAttribute("aria-valuemin", "0");
            track.setAttribute("aria-valuemax", String(maximum));
            track.setAttribute("aria-valuenow", String(unit.failed + unit.waived));
            var failedFill = document.createElement("span");
            failedFill.className = "acs-progress-fill acs-failure-fill";
            failedFill.setAttribute("aria-hidden", "true");
            failedFill.style.backgroundColor = statusAccent("fail");
            failedFill.style.width = failedWidth.toFixed(4).replace(/\.?0+$/, "") + "%";
            failedFill.style.minWidth = unit.failed > 0 ? "2px" : "0";
            track.appendChild(failedFill);
            if (unit.waived) {
                var waiverFill = document.createElement("span");
                waiverFill.className = "acs-progress-fill acs-failure-fill-waiver";
                waiverFill.setAttribute("aria-hidden", "true");
                waiverFill.style.width = waiverWidth.toFixed(4).replace(/\.?0+$/, "") + "%";
                waiverFill.style.minWidth = "2px";
                track.appendChild(waiverFill);
            }

            var count = document.createElement("span");
            count.className = "acs-progress-count";
            count.appendChild(document.createTextNode(String(unit.failed)));
            if (unit.waived) {
                var waiverCount = document.createElement("span");
                waiverCount.className = "acs-failure-waiver-count";
                waiverCount.textContent = " + " + unit.waived + " waived";
                waiverCount.title = unit.waived + " failed with waiver";
                count.appendChild(waiverCount);
            }

            item.appendChild(label);
            item.appendChild(track);
            item.appendChild(count);
            list.appendChild(item);
        });
        panel.appendChild(list);
        return panel;
    }

    function buildDetailedToolbar() {
        var records = statusRows();
        var resultGroups = Array.prototype.slice.call(document.querySelectorAll(".acs-result-group"));
        resultGroups.forEach(function (group) { group.acsFilterRecords = []; });
        records.forEach(function (record) {
            if (record.group) {
                record.group.acsFilterRecords.push(record);
            }
        });
        enableGroupCollapsing(resultGroups);
        var toolbar = document.createElement("section");
        toolbar.className = "acs-toolbar";
        toolbar.setAttribute("aria-label", "Report controls");

        var searchControl = document.createElement("label");
        searchControl.className = "acs-control acs-control-grow";
        var searchLabel = document.createElement("span");
        searchLabel.className = "acs-control-label";
        searchLabel.textContent = "Search results";
        var search = document.createElement("input");
        search.type = "search";
        search.placeholder = "Test, rule, description, reason\u2026";
        search.setAttribute("aria-label", "Search report rows");
        searchControl.appendChild(searchLabel);
        searchControl.appendChild(search);
        toolbar.appendChild(searchControl);

        var navigation = navigationTargets();
        if (navigation.targets.length > 1) {
            var suiteControl = document.createElement("label");
            suiteControl.className = "acs-control";
            var suiteLabel = document.createElement("span");
            suiteLabel.className = "acs-control-label";
            suiteLabel.textContent = "Jump to " + navigation.kind;
            var suiteSelect = document.createElement("select");
            suiteSelect.setAttribute("aria-label", "Jump to " + navigation.kind);
            var prompt = document.createElement("option");
            prompt.value = "";
            prompt.textContent = "Choose a " + navigation.kind + "\u2026";
            suiteSelect.appendChild(prompt);
            navigation.targets.forEach(function (header) {
                var option = document.createElement("option");
                option.value = header.element.id;
                option.textContent = header.label;
                suiteSelect.appendChild(option);
            });
            suiteSelect.addEventListener("change", function () {
                var target = document.getElementById(suiteSelect.value);
                if (target) {
                    target.scrollIntoView({behavior: "smooth", block: "start"});
                    suiteSelect.value = "";
                }
            });
            suiteControl.appendChild(suiteLabel);
            suiteControl.appendChild(suiteSelect);
            toolbar.appendChild(suiteControl);
        }

        var actions = document.createElement("div");
        actions.className = "acs-actions";
        var reset = actionButton("Reset");
        var print = actionButton("Print all results / PDF");
        print.setAttribute("aria-label", "Print all result rows or save them as PDF");
        print.title = "Prints every result group and nested result row, including items collapsed or filtered on screen.";
        actions.appendChild(reset);
        actions.appendChild(print);

        var hasExpanders = document.querySelector(".testcase-toggle, .expand-subtests, .collapse-subtests, .acs-group-toggle");
        var expand;
        var collapse;
        if (hasExpanders) {
            expand = actionButton("Expand all", "acs-button-primary");
            collapse = actionButton("Collapse all");
            actions.insertBefore(expand, reset);
            actions.insertBefore(collapse, reset);
        }
        var count = document.createElement("div");
        count.className = "acs-filter-count";
        count.setAttribute("aria-live", "polite");
        toolbar.appendChild(count);
        toolbar.appendChild(actions);

        var filters = document.createElement("div");
        filters.className = "acs-status-filters";
        filters.setAttribute("aria-label", "Filter by status");
        toolbar.appendChild(filters);

        var filterScope = document.createElement("div");
        filterScope.className = "acs-filter-scope";
        filterScope.textContent = "Case and subtest outcomes in this report";
        filters.appendChild(filterScope);

        var filterHelp = document.createElement("p");
        filterHelp.className = "acs-filter-help";
        filterHelp.textContent = "Choose one status to focus the report. Choose it again, or All, to restore every result.";
        filters.appendChild(filterHelp);

        var printScopeNote = document.createElement("p");
        printScopeNote.className = "acs-print-scope-note";
        printScopeNote.textContent = "PDF includes every result group and nested result row, including items collapsed or filtered on screen. Summary totals remain unchanged.";
        toolbar.appendChild(printScopeNote);

        var totals = {};
        var labels = {};
        var encountered = [];
        var activeStatus = "";
        records.forEach(function (record) {
            if (encountered.indexOf(record.status) < 0) {
                encountered.push(record.status);
            }
            totals[record.status] = (totals[record.status] || 0) + 1;
            labels[record.status] = labels[record.status] || record.label || statusLabel(record.status, record.status);
        });
        var allButton = document.createElement("button");
        allButton.type = "button";
        allButton.className = "acs-status-filter info";
        allButton.setAttribute("aria-pressed", "true");
        allButton.textContent = "All outcomes " + records.length;
        filters.appendChild(allButton);
        var filterButtons = {};
        var orderedStatuses = STATUS_ORDER.filter(function (status) { return totals[status]; });
        encountered.forEach(function (status) {
            if (orderedStatuses.indexOf(status) < 0) {
                orderedStatuses.push(status);
            }
        });
        orderedStatuses.forEach(function (status) {
            if (!totals[status]) {
                return;
            }
            var button = document.createElement("button");
            button.type = "button";
            button.className = "acs-status-filter " + status;
            button.setAttribute("aria-pressed", "false");
            button.textContent = labels[status] + " " + totals[status];
            button.addEventListener("click", function () {
                activeStatus = activeStatus === status ? "" : status;
                applyFilters();
            });
            filterButtons[status] = button;
            filters.appendChild(button);
        });

        var anchor = document.querySelector(".detailed-summary, .detailed-container");
        var overview = null;
        if (anchor) {
            anchor.parentNode.insertBefore(toolbar, anchor);
            var summary = anchor.parentNode.querySelector(
                ":scope > .result-summary.acs-compact-summary, " +
                ":scope > .summary-container.acs-compact-summary, " +
                ":scope > .card.acs-compact-summary"
            );
            if (summary) {
                overview = document.createElement("section");
                overview.className = "acs-detail-overview";
                overview.setAttribute(
                    "aria-label", "Result summary and failure breakdown"
                );
                summary.parentNode.insertBefore(overview, summary);
                overview.appendChild(summary);
                overview.appendChild(buildFailureSummary(resultGroups));
            }
        } else {
            document.body.insertBefore(toolbar, document.body.firstChild);
        }
        var empty = document.createElement("div");
        empty.className = "acs-empty-state";
        empty.textContent = "No report rows match the selected filters.";
        toolbar.insertAdjacentElement("afterend", empty);
        var printBanner = document.createElement("div");
        printBanner.className = "acs-print-banner";
        printBanner.textContent = "All-results PDF: every result group and nested result row is included. Suite-reported totals above still cover the complete run.";
        empty.insertAdjacentElement("afterend", printBanner);
        addMobileTableNote(toolbar);

        function applyFilters() {
            var query = normalizeText(search.value).toLowerCase();
            var visible = 0;
            records.forEach(function (record) {
                record.match = (!activeStatus || record.status === activeStatus) &&
                    (!query || record.text.indexOf(query) >= 0);
                if (record.row) {
                    record.row.classList.toggle("acs-filter-hidden", !record.match);
                    record.row.classList.remove("acs-context-row");
                }
                if (record.match) {
                    visible += 1;
                }
            });

            Array.prototype.forEach.call(document.querySelectorAll("tr"), function (container) {
                if (!container.querySelector("table")) {
                    return;
                }
                var childMatches = records.some(function (record) {
                    return record.match && container.contains(record.row);
                });
                var parentRow = container.previousElementSibling;
                var parentRecord = records.find(function (record) { return record.row === parentRow; });
                var parentMatches = parentRecord && parentRecord.match;
                container.classList.toggle("acs-filter-hidden", !childMatches && !parentMatches);
                if (childMatches && parentRecord && !parentMatches) {
                    parentRow.classList.remove("acs-filter-hidden");
                    parentRow.classList.add("acs-context-row");
                }
            });

            var matchingGroupCount = resultGroups.filter(function (group) {
                return (group.acsFilterRecords || []).some(function (record) {
                    return record.match;
                });
            }).length;
            var expandMatchingGroups = Boolean(activeStatus || query) && matchingGroupCount <= 40;

            resultGroups.forEach(function (group) {
                var groupRecords = group.acsFilterRecords || [];
                if (groupRecords.length) {
                    var groupMatches = groupRecords.some(function (record) {
                        return record.match;
                    });
                    group.classList.toggle("acs-filter-hidden", !groupMatches);
                    if (group.classList.contains("acs-collapsible")) {
                        if (activeStatus || query) {
                            if (!groupMatches) {
                                setGroupCollapsed(group, true);
                            } else if (expandMatchingGroups) {
                                setGroupCollapsed(group, false);
                            } else {
                                setGroupCollapsed(group, true);
                            }
                        } else {
                            setGroupCollapsed(
                                group,
                                group.getAttribute("data-acs-default-collapsed") === "true"
                            );
                        }
                    }
                }
            });

            allButton.setAttribute("aria-pressed", activeStatus ? "false" : "true");
            Object.keys(filterButtons).forEach(function (status) {
                filterButtons[status].setAttribute("aria-pressed", activeStatus === status ? "true" : "false");
            });
            count.textContent = "Matching " + visible + " of " + records.length + " outcomes";
            if ((activeStatus || query) && !expandMatchingGroups && matchingGroupCount > 40) {
                count.textContent += " · groups kept collapsed for performance";
            }
            empty.classList.toggle("visible", visible === 0);
        }

        allButton.addEventListener("click", function () {
            activeStatus = "";
            applyFilters();
        });
        search.addEventListener("input", applyFilters);
        reset.addEventListener("click", function () {
            search.value = "";
            activeStatus = "";
            applyFilters();
            search.focus();
        });
        print.addEventListener("click", function () { window.print(); });

        if (expand && collapse) {
            expand.addEventListener("click", function () {
                Array.prototype.forEach.call(document.querySelectorAll(".testcase-toggle[aria-expanded='false']"), function (button) {
                    button.click();
                });
                Array.prototype.forEach.call(document.querySelectorAll(".expand-subtests:not(:disabled)"), function (button) {
                    if (!button.closest(".acs-toolbar")) { button.click(); }
                });
                Array.prototype.forEach.call(document.querySelectorAll(".acs-result-group.acs-collapsed"), function (group) {
                    setGroupCollapsed(group, false);
                });
            });
            collapse.addEventListener("click", function () {
                Array.prototype.forEach.call(document.querySelectorAll(".testcase-toggle[aria-expanded='true']"), function (button) {
                    button.click();
                });
                Array.prototype.forEach.call(document.querySelectorAll(".collapse-subtests:not(:disabled)"), function (button) {
                    if (!button.closest(".acs-toolbar")) { button.click(); }
                });
                Array.prototype.forEach.call(document.querySelectorAll(".acs-result-group.acs-collapsible:not(.acs-collapsed)"), function (group) {
                    setGroupCollapsed(group, true);
                });
            });
        }

        document.addEventListener("keydown", function (event) {
            var tag = document.activeElement && document.activeElement.tagName;
            if (event.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
                event.preventDefault();
                search.focus();
            }
            if (event.key === "Escape" && document.activeElement === search) {
                search.value = "";
                applyFilters();
            }
        });
        applyFilters();
    }

    function informationGroup(label) {
        var text = normalizeText(label).toLowerCase();
        if (/source\s+code|flashing|website|operat(?:ed|ing)\s+systems?|test\s*lab|assistance|support|instructions/.test(text)) {
            return "support";
        }
        if (/firmware|uefi/.test(text)) {
            return "firmware";
        }
        if (text === "band") {
            return "standards";
        }
        if (/^(?:vendor|manufacturer|system(?:\s+name|\s+model)?|soc\s+family|platform)$/.test(text)) {
            return "platform";
        }
        if (/version|standard|specification|profile/.test(text)) {
            return "standards";
        }
        return "other";
    }

    function cloneCellContents(cell, target) {
        Array.prototype.forEach.call(cell.childNodes, function (node) {
            target.appendChild(node.cloneNode(true));
        });
    }

    function informationFieldPriority(source) {
        var label = normalizeText(source.labelCell.textContent).toLowerCase();
        var priorities = {"band": 0, "acs version": 1, "srs version": 2};
        return Object.prototype.hasOwnProperty.call(priorities, label) ?
            priorities[label] : 3 + source.index;
    }

    function buildInformationOverview(section) {
        var table = section.querySelector("table");
        if (!table) {
            return false;
        }
        var definitions = [
            {key: "platform", label: "Platform", fields: []},
            {key: "firmware", label: "Firmware", fields: []},
            {key: "standards", label: "ACS & standards", fields: []},
            {key: "support", label: "Support", fields: []},
            {key: "other", label: "Other information", fields: []}
        ];
        var groups = {};
        definitions.forEach(function (definition) {
            groups[definition.key] = definition;
        });
        var rows = Array.prototype.slice.call(table.querySelectorAll("tr"));
        var fieldCount = 0;
        var invalidRow = !rows.length;
        rows.forEach(function (row, index) {
            var labelCells = Array.prototype.filter.call(row.cells, function (cell) {
                return cell.tagName === "TH";
            });
            var valueCells = Array.prototype.filter.call(row.cells, function (cell) {
                return cell.tagName === "TD";
            });
            if (labelCells.length !== 1 || valueCells.length !== 1) {
                invalidRow = true;
                return;
            }
            var labelCell = labelCells[0];
            var valueCell = valueCells[0];
            var label = normalizeText(labelCell && labelCell.textContent);
            if (!label) {
                invalidRow = true;
                return;
            }
            groups[informationGroup(label)].fields.push({
                labelCell: labelCell,
                valueCell: valueCell,
                index: index
            });
            fieldCount += 1;
        });
        if (invalidRow || !fieldCount || fieldCount !== rows.length) {
            return false;
        }

        var heading = section.querySelector("h2");
        if (!heading) {
            heading = document.createElement("h2");
            heading.textContent = "System Information";
            section.insertBefore(heading, section.firstChild);
        }
        if (!heading.id) {
            heading.id = "acs-system-information-heading";
        }
        var headingRow = document.createElement("div");
        headingRow.className = "acs-overview-heading";
        heading.parentNode.insertBefore(headingRow, heading);
        headingRow.appendChild(heading);
        var count = document.createElement("span");
        count.className = "acs-overview-field-count";
        count.textContent = fieldCount + (fieldCount === 1 ? " field" : " fields");
        headingRow.appendChild(count);

        var bands = document.createElement("div");
        bands.className = "acs-information-bands";
        definitions.forEach(function (definition) {
            if (!definition.fields.length) {
                return;
            }
            var band = document.createElement("section");
            band.className = "acs-information-band";
            band.setAttribute("data-acs-information-group", definition.key);
            var bandHeading = document.createElement("h3");
            bandHeading.textContent = definition.label;
            band.appendChild(bandHeading);
            var values = document.createElement("dl");
            values.className = "acs-information-values";
            var orderedFields = definition.fields.slice();
            if (definition.key === "standards") {
                orderedFields.sort(function (left, right) {
                    return informationFieldPriority(left) - informationFieldPriority(right) ||
                        left.index - right.index;
                });
            }
            orderedFields.forEach(function (source) {
                var field = document.createElement("div");
                field.className = "acs-information-field";
                field.setAttribute("data-acs-source-row", String(source.index));
                field.setAttribute("data-acs-unknown", String(
                    normalizeText(source.valueCell.textContent).toLowerCase() === "unknown"
                ));
                var term = document.createElement("dt");
                cloneCellContents(source.labelCell, term);
                var description = document.createElement("dd");
                cloneCellContents(source.valueCell, description);
                field.appendChild(term);
                field.appendChild(description);
                values.appendChild(field);
            });
            band.appendChild(values);
            bands.appendChild(band);
        });
        headingRow.insertAdjacentElement("afterend", bands);
        table.classList.add("acs-overview-source");
        table.setAttribute("aria-hidden", "true");
        section.classList.add("acs-information-overview");
        section.setAttribute("aria-labelledby", heading.id);
        section.setAttribute("data-acs-source-fields", String(fieldCount));
        return true;
    }

    function collectResultEntries(table) {
        var entries = [];
        var current = null;
        var valueIndex = 0;
        Array.prototype.forEach.call(table.querySelectorAll("tr"), function (row) {
            var labelCell = row.querySelector("th");
            var valueCells = Array.prototype.slice.call(row.querySelectorAll("td"));
            if (labelCell) {
                current = {
                    labelCell: labelCell,
                    label: normalizeText(labelCell.textContent),
                    values: []
                };
                entries.push(current);
            } else if (!current && valueCells.length) {
                current = {labelCell: null, label: "Additional information", values: []};
                entries.push(current);
            }
            if (!current) {
                return;
            }
            valueCells.forEach(function (cell) {
                current.values.push({cell: cell, index: valueIndex});
                valueIndex += 1;
            });
        });
        return entries;
    }

    function complianceTone(value) {
        var text = normalizeText(value).toUpperCase();
        if (/NOT\s+COMPLIANT|FAIL(?:ED|URE)?/.test(text)) {
            return "fail";
        }
        if (/WAIVER|WARNING/.test(text)) {
            return "warn";
        }
        if (/^(?:COMPLIANT|PASS(?:ED)?)\b/.test(text)) {
            return "pass";
        }
        return "neutral";
    }

    function resultEntryIsStatus(entry) {
        return /compliance|result/.test(entry.label.toLowerCase()) && entry.values.length;
    }

    function buildResultOverview(section, index) {
        var table = section.querySelector("table");
        var entries = table ? collectResultEntries(table) : [];
        if (!table || !entries.length) {
            return false;
        }
        var heading = section.querySelector("h2");
        if (!heading) {
            heading = document.createElement("h2");
            heading.textContent = "Results";
            section.insertBefore(heading, section.firstChild);
        }
        if (!heading.id) {
            heading.id = "acs-overview-result-heading-" + index;
        }
        var headingRow = document.createElement("div");
        headingRow.className = "acs-overview-heading";
        heading.parentNode.insertBefore(headingRow, heading);
        headingRow.appendChild(heading);

        var isAcsResults = normalizeText(heading.textContent).toLowerCase() ===
            "acs results summary";
        var dateEntry = isAcsResults ? entries.find(function (entry) {
            return normalizeText(entry.label).toLowerCase() === "date";
        }) : null;
        if (dateEntry) {
            var headingMeta = document.createElement("dl");
            headingMeta.className = "acs-overview-heading-meta";
            var dateItem = document.createElement("div");
            dateItem.className = "acs-overview-meta-item";
            var dateTerm = document.createElement("dt");
            if (dateEntry.labelCell) {
                cloneCellContents(dateEntry.labelCell, dateTerm);
            } else {
                dateTerm.textContent = dateEntry.label;
            }
            dateItem.appendChild(dateTerm);
            dateEntry.values.forEach(function (source) {
                var dateValue = document.createElement("dd");
                dateValue.setAttribute("data-acs-source-result", String(source.index));
                cloneCellContents(source.cell, dateValue);
                dateItem.appendChild(dateValue);
            });
            headingMeta.appendChild(dateItem);
            headingRow.appendChild(headingMeta);
        }

        var content = document.createElement("div");
        content.className = "acs-overview-result-content";
        var systemBandFields = Array.prototype.filter.call(
            document.querySelectorAll(".acs-information-overview .acs-information-field"),
            function (field) {
                var term = field.querySelector("dt");
                return term && normalizeText(term.textContent).toLowerCase() === "band";
            }
        );
        var resultBandEntries = isAcsResults ? entries.filter(function (entry) {
            return normalizeText(entry.label).toLowerCase() === "band";
        }) : [];
        var duplicateBandEntry = null;
        if (systemBandFields.length === 1 && resultBandEntries.length === 1 &&
                resultBandEntries[0].values.length === 1) {
            var systemBandValue = systemBandFields[0].querySelector("dd");
            if (systemBandValue && normalizeText(systemBandValue.textContent) ===
                    normalizeText(resultBandEntries[0].values[0].cell.textContent)) {
                duplicateBandEntry = resultBandEntries[0];
            }
        }
        var metaEntries = entries.filter(function (entry) {
            return !resultEntryIsStatus(entry) && entry !== dateEntry &&
                entry !== duplicateBandEntry;
        });
        if (duplicateBandEntry) {
            section.setAttribute("data-acs-duplicate-band-omitted", "true");
        }
        if (metaEntries.length) {
            var meta = document.createElement("dl");
            meta.className = "acs-overview-result-meta";
            metaEntries.forEach(function (entry) {
                var item = document.createElement("div");
                item.className = "acs-overview-meta-item";
                var term = document.createElement("dt");
                if (entry.labelCell) {
                    cloneCellContents(entry.labelCell, term);
                } else {
                    term.textContent = entry.label;
                }
                item.appendChild(term);
                entry.values.forEach(function (source) {
                    var description = document.createElement("dd");
                    description.setAttribute("data-acs-source-result", String(source.index));
                    cloneCellContents(source.cell, description);
                    item.appendChild(description);
                });
                meta.appendChild(item);
            });
            content.appendChild(meta);
        }

        var cardTone = "pass";
        var statusEntries = entries.filter(resultEntryIsStatus);
        var toneRank = {pass: 0, neutral: 1, warn: 2, fail: 3};
        var statusList = document.createElement("dl");
        statusList.className = "acs-overview-status-list";
        statusEntries.forEach(function (entry) {
            var result = document.createElement("div");
            result.className = "acs-overview-result-entry";
            var primaryText = normalizeText(entry.values[0].cell.textContent);
            var tone = complianceTone(primaryText);
            result.setAttribute("data-acs-tone", tone);
            if (toneRank[tone] > toneRank[cardTone]) {
                cardTone = tone;
            }
            var label = document.createElement("dt");
            label.className = "acs-overview-result-label";
            if (entry.labelCell) {
                cloneCellContents(entry.labelCell, label);
            } else {
                label.textContent = entry.label;
            }
            result.appendChild(label);
            entry.values.forEach(function (source, valuePosition) {
                var value = document.createElement("dd");
                value.className = "acs-overview-result-value";
                value.setAttribute("data-acs-primary", String(valuePosition === 0));
                value.setAttribute("data-acs-source-result", String(source.index));
                cloneCellContents(source.cell, value);
                result.appendChild(value);
            });
            statusList.appendChild(result);
        });
        if (!statusEntries.length) {
            cardTone = "neutral";
        } else {
            content.appendChild(statusList);
        }
        headingRow.insertAdjacentElement("afterend", content);
        table.classList.add("acs-overview-source");
        table.setAttribute("aria-hidden", "true");
        section.classList.add("acs-overview-result-card");
        section.setAttribute("aria-labelledby", heading.id);
        section.setAttribute("data-acs-card-tone", cardTone);
        section.setAttribute("data-acs-source-results", String(table.querySelectorAll("td").length));
        return true;
    }

    function upgradeAcsSummaryOverview() {
        if (document.querySelector(".acs-summary-overview")) {
            return;
        }
        var container = document.querySelector("body > .container");
        if (!container) {
            return;
        }
        var systemInformation = null;
        var resultSources = [];
        Array.prototype.forEach.call(container.children, function (child) {
            if (child.classList.contains("system-info")) {
                systemInformation = child;
            } else if (child.classList.contains("acs-results-summary")) {
                resultSources.push(child);
            }
        });
        var emptyResultSections = resultSources.filter(function (section) {
            var table = section.querySelector("table");
            var hasOtherContent = Array.prototype.some.call(section.childNodes, function (node) {
                if (node.nodeType === 3) {
                    return Boolean(normalizeText(node.textContent));
                }
                return node.nodeType === 1 && !/^(?:H[1-6]|TABLE)$/.test(node.tagName) &&
                    Boolean(normalizeText(node.textContent));
            });
            return table && !table.querySelector("tr") && !hasOtherContent;
        });
        var resultSections = resultSources.filter(function (section) {
            var rows = Array.prototype.slice.call(section.querySelectorAll("table tr"));
            return rows.length && rows.every(function (row) { return row.querySelector("td"); });
        });
        if (!systemInformation || !resultSections.length ||
                !systemInformation.querySelector("table tr th")) {
            return;
        }
        if (!buildInformationOverview(systemInformation)) {
            return;
        }
        var overview = document.createElement("div");
        overview.className = "acs-summary-overview";
        overview.setAttribute("data-acs-source-sections", String(resultSections.length + 1));
        systemInformation.parentNode.insertBefore(overview, systemInformation);
        overview.appendChild(systemInformation);
        var results = document.createElement("div");
        results.className = "acs-overview-results";
        resultSections.forEach(function (section, index) {
            buildResultOverview(section, index + 1);
            results.appendChild(section);
        });
        emptyResultSections.forEach(function (section) {
            section.classList.add("acs-overview-source");
            section.setAttribute("aria-hidden", "true");
        });
        results.setAttribute("data-acs-card-count", String(resultSections.length));
        overview.appendChild(results);
    }

    function summaryLabel(section) {
        var labels = {
            "bsa_summary": "BSA",
            "sbsa_summary": "SBSA",
            "scmi_summary": "SCMI",
            "sbmr_ib_summary": "SBMR-IB",
            "sbmr_oob_summary": "SBMR-OOB",
            "post_script_summary": "POST-SCRIPT",
            "standalone_summary": "Standalone",
            "bbsr_fwts_summary": "BBSR-FWTS",
            "bbsr_sct_summary": "BBSR-SCT",
            "bbsr_tpm_summary": "BBSR-TPM",
            "pfdi_summary": "PFDI",
            "OS_tests_summary": "OS Tests"
        };
        if (labels[section.id]) {
            return labels[section.id];
        }
        var heading = section.querySelector("h1, h2, h3");
        if (heading) {
            return normalizeText(heading.textContent)
                .replace(/\s+(?:Test|Log) Summary$/i, "");
        }
        return section.id.replace(/_summary$/i, "").replace(/_/g, " ").toUpperCase();
    }

    function buildSummaryNavigation() {
        var sections = Array.prototype.slice.call(document.querySelectorAll(".summary[id]"));
        if (sections.length < 2) {
            return;
        }
        if (sections.length % 2) {
            sections[sections.length - 1].classList.add("acs-summary-orphan");
        }
        var nav = document.createElement("nav");
        nav.className = "acs-suite-nav";
        nav.setAttribute("aria-label", "Suite summaries");
        sections.forEach(function (section) {
            var link = document.createElement("a");
            link.href = "#" + section.id;
            link.textContent = summaryLabel(section);
            nav.appendChild(link);
            section.style.scrollMarginTop = "76px";
        });
        var summariesHeading = document.querySelector(".summary-section > h2");
        if (summariesHeading) {
            summariesHeading.insertAdjacentElement("afterend", nav);
        } else {
            var header = document.querySelector("body > .header");
            if (header) {
                header.insertAdjacentElement("afterend", nav);
            } else {
                document.body.insertBefore(nav, document.body.firstChild);
            }
        }
    }

    function addSummaryPrintButton() {
        var heading = document.querySelector(".summary-section > h2");
        if (!heading || heading.parentNode.querySelector(":scope > .acs-summary-heading-row")) {
            return;
        }
        var row = document.createElement("div");
        row.className = "acs-summary-heading-row";
        heading.parentNode.insertBefore(row, heading);
        row.appendChild(heading);
        var print = actionButton("Print / PDF", "acs-button-primary acs-summary-print-button");
        print.setAttribute("aria-label", "Print the consolidated ACS summary or save it as PDF");
        print.addEventListener("click", function () { window.print(); });
        row.appendChild(print);
    }

    function shortenDetailLinks() {
        Array.prototype.forEach.call(document.querySelectorAll(".summary[id]"), function (section) {
            var link = section.querySelector(".details-link a");
            if (!link) {
                return;
            }
            var label = summaryLabel(section);
            link.removeAttribute("target");
            link.setAttribute("aria-label", "Open detailed report for " + label);
            link.textContent = "View " + label + " details \u2192";
        });
    }

    function addBackToTop() {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "acs-back-to-top";
        button.setAttribute("aria-label", "Back to top");
        button.title = "Back to top";
        button.textContent = "\u2191";
        button.addEventListener("click", function () {
            window.scrollTo({top: 0, behavior: "smooth"});
        });
        document.body.appendChild(button);
        function updateVisibility() {
            button.classList.toggle("visible", window.scrollY > 600);
        }
        window.addEventListener("scroll", updateVisibility, {passive: true});
        updateVisibility();
    }

    function initialize() {
        addReportHeading();
        upgradeSummaryTables();
        upgradeSuiteLayouts();
        upgradeTableColumns();
        upgradeStatusCells();
        addMobileStatusPreviews();
        decorateGroupStatuses();
        removeDetailedCharts();
        decorateSummaryContext();
        if (document.body.getAttribute("data-acs-report-kind") === "acs-summary") {
            buildSummaryNavigation();
            addSummaryPrintButton();
            shortenDetailLinks();
            upgradeAcsSummaryOverview();
        } else {
            buildDetailedToolbar();
        }
        hideLegacyNavigation();
        addBackToTop();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }
}());
"""


def _add_body_attributes(match, page_type, suite_type):
    """Return a body tag with the shared class and page type attributes."""
    attributes = match.group(1) or ""
    class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', attributes, re.IGNORECASE)
    if class_match:
        classes = class_match.group(2).split()
        if "acs-report-ui" not in classes:
            classes.append("acs-report-ui")
        replacement = f'class={class_match.group(1)}{" ".join(classes)}{class_match.group(1)}'
        attributes = attributes[:class_match.start()] + replacement + attributes[class_match.end():]
    else:
        attributes += ' class="acs-report-ui"'
    attributes += f' data-acs-report-kind="{page_type}"'
    if suite_type:
        attributes += f' data-acs-suite="{suite_type}"'
    attributes += f" {UI_MARKER}"
    return f"<body{attributes}>"


def enhance_html_report(html_content, page_type="suite", suite_type=None):
    """Return HTML with the shared theme and progressive UI injected once."""
    if not isinstance(html_content, str):
        raise TypeError("html_content must be a string")
    if page_type not in VALID_PAGE_TYPES:
        raise ValueError(f"unsupported report page type: {page_type}")
    if suite_type is not None and suite_type not in VALID_SUITE_TYPES:
        raise ValueError(f"unsupported report suite type: {suite_type}")
    if page_type == "acs-summary" and suite_type is not None:
        raise ValueError("suite_type is not valid for the consolidated summary")
    if UI_MARKER in html_content:
        return html_content

    output = html_content
    is_detailed = re.search(
        r"class\s*=\s*[\"'][^\"']*\bdetailed-(?:summary|container)\b",
        output,
        re.IGNORECASE,
    )
    if is_detailed:
        output = re.sub(
            r"<div\s+class\s*=\s*([\"'])chart-container\1\s*>"
            r"\s*<img\b[^>]*>\s*</div\s*>",
            "",
            output,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if not re.search(r'<meta\s+[^>]*name=["\']viewport["\']', output, re.IGNORECASE):
        viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        output = re.sub(
            r"(<head\b[^>]*>)",
            r"\1\n" + viewport,
            output,
            count=1,
            flags=re.IGNORECASE,
        )
    if not re.search(r'<meta\s+[^>]*charset=', output, re.IGNORECASE):
        charset = '<meta charset="utf-8">\n'
        output = re.sub(
            r"(<head\b[^>]*>)",
            r"\1\n" + charset,
            output,
            count=1,
            flags=re.IGNORECASE,
        )

    style_block = f'\n<style id="acs-report-theme">\n{REPORT_CSS}\n</style>\n'
    if re.search(r"</head\s*>", output, re.IGNORECASE):
        output = re.sub(
            r"</head\s*>",
            lambda _match: style_block + "</head>",
            output,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        output = style_block + output

    output, replacements = re.subn(
        r"<body\b([^>]*)>",
        lambda match: _add_body_attributes(match, page_type, suite_type),
        output,
        count=1,
        flags=re.IGNORECASE,
    )
    if not replacements:
        suite_attribute = f' data-acs-suite="{suite_type}"' if suite_type else ""
        output = (
            f'<body class="acs-report-ui" data-acs-report-kind="{page_type}"'
            f'{suite_attribute} {UI_MARKER}>\n{output}\n</body>'
        )

    script_block = f'\n<script id="acs-report-interactions">\n{REPORT_JS}\n</script>\n'
    if re.search(r"</body\s*>", output, re.IGNORECASE):
        output = re.sub(
            r"</body\s*>",
            lambda _match: script_block + "</body>",
            output,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        output += script_block
    return output
