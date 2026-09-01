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

"""Enrich raw suite JSON files with test category metadata."""

import argparse
import fnmatch
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from suite_registry import REGISTRY_PATH, load_registry


DEFAULT_REGISTRY = Path(REGISTRY_PATH)

REQUIRED_METADATA_FIELDS = [
    "Main Readiness Grouping",
    "SRS scope",
    "Waivable",
]

ENTRY_ORDER = [
    "Test_suite",
    "Test_suite_name",
    "Main Readiness Grouping",
    "SRS scope",
    "Test_case",
    "Test_case_description",
    "Test_suite_description",
    "Test_suite_info",
    "test_suite_summary",
    "Waivable",
    "Sub_test_suite",
    "Test Entry Point GUID",
    "Returned Status Code",
    "test_result",
    "reason",
    "testcases",
    "Test_cases",
    "subtests",
    "test_case_summary",
]

STANDALONE_SUITES = {
    "CAPSULE-UPDATE",
    "DT-KSELFTEST",
    "DT-VALIDATE",
    "ETHTOOL-TEST",
    "NETWORK-BOOT",
    "OS-TESTS",
    "PSCI",
    "READ-WRITE-CHECK-BLK-DEVICES",
    "RUNTIME-DEV-MAP",
    "SMBIOS",
}

LOOKUP_SUITE_OVERRIDES = {
    "BBSR-TPM": "bbsr-standalone",
    "SBMR-IB": "sbmr",
    "SBMR-OOB": "sbmr",
}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4)


def _category_index(category_data):
    index = {}
    if not isinstance(category_data, dict):
        return index

    for rows in category_data.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            suite = (row.get("Suite") or "").strip().lower()
            test_suite = (row.get("Test Suite") or "").strip().lower()
            if suite and test_suite:
                index.setdefault(suite, {})[test_suite] = row
    return index


def _file_suite_index(registry):
    exact = {}
    patterns = []

    for suite in registry:
        canonical = suite.get("canonical")
        if not canonical:
            continue

        json_output = suite.get("json_output")
        if json_output:
            exact[json_output] = canonical

        for pattern in suite.get("json_output_patterns", []):
            patterns.append((pattern, canonical))

    return exact, patterns


def _canonical_for_file(path, exact, patterns):
    name = Path(path).name
    if name in exact:
        return exact[name]

    for pattern, canonical in patterns:
        if fnmatch.fnmatch(name, pattern):
            return canonical

    return None


def _lookup_suite(canonical):
    if canonical in STANDALONE_SUITES:
        return "standalone"
    return LOOKUP_SUITE_OVERRIDES.get(canonical, canonical.lower())


def _entry_list(data):
    if isinstance(data, dict) and isinstance(data.get("test_results"), list):
        return data["test_results"]
    if isinstance(data, list):
        return data
    return []


def _order_entry(entry):
    ordered = {key: entry[key] for key in ENTRY_ORDER if key in entry}
    for key, value in entry.items():
        if key not in ordered:
            ordered[key] = value
    entry.clear()
    entry.update(ordered)


def _metadata_from_row(row):
    metadata = {}
    if "Main Readiness Grouping" in row:
        metadata["Main Readiness Grouping"] = row["Main Readiness Grouping"]
    if "SRS scope" in row:
        metadata["SRS scope"] = row["SRS scope"]
    if "Description" in row:
        metadata["Test_suite_info"] = row["Description"]
    if "Waivable" in row:
        metadata["Waivable"] = row["Waivable"]
    return metadata


def enrich_file(json_file, canonical, category_rows):
    data = _load_json(json_file)
    entries = _entry_list(data)
    if not entries:
        return 0, 0

    lookup_suite = _lookup_suite(canonical)
    rows_for_suite = category_rows.get(lookup_suite, {})
    enriched = 0
    missing = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        test_suite = (entry.get("Test_suite") or entry.get("Test_suite_name") or "").strip().lower()
        row = rows_for_suite.get(test_suite)
        if not row:
            missing += 1
            continue

        metadata = _metadata_from_row(row)
        if not all(field in metadata for field in REQUIRED_METADATA_FIELDS):
            missing += 1
            continue

        entry.update(metadata)
        _order_entry(entry)
        enriched += 1

    if enriched:
        _write_json(json_file, data)

    return enriched, missing


def main():
    parser = argparse.ArgumentParser(description="Enrich raw suite JSON files with test category metadata.")
    parser.add_argument("json_files", nargs="+", help="Raw suite JSON files to enrich")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to suite_registry.json")
    parser.add_argument("--test-category", required=True, help="Path to test_category.json or test_categoryDT.json")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-file enrichment messages")
    args = parser.parse_args()

    category_path = Path(args.test_category)
    if not category_path.is_file():
        print(f"ERROR: Test category file not found: {category_path}", file=sys.stderr)
        return 1

    registry = load_registry(args.registry)
    exact, patterns = _file_suite_index(registry)
    category_rows = _category_index(_load_json(category_path))

    total_enriched = 0
    total_missing = 0

    for json_file in args.json_files:
        json_path = Path(json_file)
        canonical = _canonical_for_file(json_path, exact, patterns)
        if not canonical:
            continue

        try:
            enriched, missing = enrich_file(json_path, canonical, category_rows)
        except Exception as exc:
            print(f"ERROR: Failed to enrich {json_path}: {exc}", file=sys.stderr)
            return 1

        total_enriched += enriched
        total_missing += missing

        if not args.quiet and (enriched or missing):
            print(f"{json_path}: enriched {enriched}, missing category match {missing}")

    if not args.quiet:
        print(f"Suite JSON enrichment result: {total_enriched} enriched, {total_missing} missing category matches")

    return 0


if __name__ == "__main__":
    sys.exit(main())
