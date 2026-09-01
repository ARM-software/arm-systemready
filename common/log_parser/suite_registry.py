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

"""Shared suite registry helpers for log parser orchestration and merging."""

import argparse
import json
import sys
from pathlib import Path


REGISTRY_PATH = str(Path(__file__).resolve().with_name("suite_registry.json"))


def _token(value):
    return "-".join(
        part
        for part in (value or "").strip().upper().replace("_", "-").replace(" ", "-").split("-")
        if part
    )


def load_registry(path=REGISTRY_PATH):
    with open(path, "r", encoding="utf-8") as registry_file:
        data = json.load(registry_file)
    suites = data.get("suites", [])
    if not isinstance(suites, list):
        raise ValueError("suite_registry.json must contain a 'suites' list")
    return suites


def _suite_by_canonical(registry):
    return {suite["canonical"]: suite for suite in registry}


def _alias_map(registry):
    aliases = {}
    for suite in registry:
        canonical = suite.get("canonical")
        if not canonical:
            continue
        aliases[_token(canonical)] = canonical
        for alias in suite.get("aliases", []):
            aliases[_token(alias)] = canonical
    return aliases


def normalize_suite_name(name, registry=None):
    registry = registry or load_registry()
    return _alias_map(registry).get(_token(name), "")


def list_suite_names(registry=None):
    registry = registry or load_registry()
    return [suite["canonical"] for suite in registry]


def get_suite(canonical, registry=None):
    registry = registry or load_registry()
    return _suite_by_canonical(registry).get(canonical)


def suite_modes(canonical, registry=None):
    suite = get_suite(canonical, registry)
    return suite.get("modes", []) if suite else []


def suite_supports_mode(canonical, mode, registry=None):
    return mode.upper() in suite_modes(canonical, registry)


def suite_includes(selected_canonical, wanted_canonical, registry=None):
    registry = registry or load_registry()
    selected = get_suite(selected_canonical, registry)
    if not selected:
        return False
    return wanted_canonical in selected.get("included_suites", [])


def expand_selected_suites(selected_suites, registry=None):
    registry = registry or load_registry()
    expanded = []
    seen = set()
    for selected in selected_suites or []:
        canonical = normalize_suite_name(selected, registry)
        if not canonical:
            continue
        suite = get_suite(canonical, registry)
        values = suite.get("included_suites", []) if suite else []
        if not values:
            values = [canonical]
        for value in values:
            if value not in seen:
                seen.add(value)
                expanded.append(value)
    return expanded


def requirement_table(mode, registry=None):
    registry = registry or load_registry()
    table = []
    mode = mode.upper()
    for suite in registry:
        requirements = suite.get("requirements", {})
        if mode in requirements:
            table.append((suite["requirement_key"], requirements[mode]))
    return table


def selected_requirement_keys(selected_suites, registry=None):
    registry = registry or load_registry()
    selected = []
    seen = set()
    for canonical in expand_selected_suites(selected_suites, registry):
        suite = get_suite(canonical, registry)
        requirement_key = suite.get("requirement_key") if suite else None
        if requirement_key and requirement_key not in seen:
            seen.add(requirement_key)
            selected.append(requirement_key)
    return selected


def _main():
    parser = argparse.ArgumentParser(description="Query the SystemReady log parser suite registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List canonical suite names")

    normalize_parser = subparsers.add_parser("normalize", help="Normalize a suite name or alias")
    normalize_parser.add_argument("suite")

    includes_parser = subparsers.add_parser("includes", help="Check whether one suite group includes another suite")
    includes_parser.add_argument("selected")
    includes_parser.add_argument("wanted")

    supports_parser = subparsers.add_parser("supports-mode", help="Check whether a suite supports a mode")
    supports_parser.add_argument("suite")
    supports_parser.add_argument("mode", choices=["SR", "DT", "sr", "dt"])

    modes_parser = subparsers.add_parser("modes", help="Print suite modes")
    modes_parser.add_argument("suite")

    selected_keys_parser = subparsers.add_parser("selected-requirement-keys", help="Print selected requirement keys")
    selected_keys_parser.add_argument("suites", nargs="*")

    args = parser.parse_args()
    registry = load_registry()

    if args.command == "list":
        print("\n".join(list_suite_names(registry)))
        return 0

    if args.command == "normalize":
        normalized = normalize_suite_name(args.suite, registry)
        if normalized:
            print(normalized)
            return 0
        return 1

    if args.command == "includes":
        selected = normalize_suite_name(args.selected, registry)
        wanted = normalize_suite_name(args.wanted, registry)
        if selected and wanted and suite_includes(selected, wanted, registry):
            return 0
        return 1

    if args.command == "supports-mode":
        suite = normalize_suite_name(args.suite, registry)
        if suite and suite_supports_mode(suite, args.mode, registry):
            return 0
        return 1

    if args.command == "modes":
        suite = normalize_suite_name(args.suite, registry)
        if not suite:
            return 1
        print(" ".join(suite_modes(suite, registry)))
        return 0

    if args.command == "selected-requirement-keys":
        print("\n".join(selected_requirement_keys(args.suites, registry)))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(_main())
