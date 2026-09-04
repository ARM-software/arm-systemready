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

"""Validate merged ACS results or individual suite JSON files."""

import argparse
import fnmatch
import json
import re
import sys
import warnings
from pathlib import Path

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from jsonschema import Draft202012Validator, RefResolver
        from jsonschema.exceptions import best_match
except ImportError:
    print("ERROR: Missing required Python package: jsonschema", file=sys.stderr)
    print("Install it with: python3 -m pip install jsonschema", file=sys.stderr)
    sys.exit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from suite_registry import expand_selected_suites, load_registry


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

DEFAULT_REGISTRY = SCRIPT_DIR / "suite_registry.json"
DEFAULT_SCHEMA = SCRIPT_DIR / "acs-results-schema.json"


def _suite_by_canonical(registry):
    return {suite.get("canonical"): suite for suite in registry if suite.get("canonical")}


def _schema_location(registry_path, suite):
    schema_ref = suite.get("schema")
    if not schema_ref:
        return None, None, None

    if "#" in schema_ref:
        schema, fragment = schema_ref.split("#", 1)
        fragment = f"#{fragment}"
    else:
        schema = schema_ref
        fragment = ""

    schema_path = Path(schema)
    if schema_path.is_absolute():
        return schema_path, fragment, schema_ref
    return Path(registry_path).resolve().parent / schema_path, fragment, schema_ref


def _build_file_schema_index(registry, registry_path):
    exact = {}
    patterns = []

    for suite in registry:
        schema_path, schema_fragment, schema_ref = _schema_location(registry_path, suite)
        if not schema_path:
            continue

        suite_info = {
            "canonical": suite.get("canonical", "UNKNOWN"),
            "schema": schema_path,
            "schema_fragment": schema_fragment,
            "schema_ref": schema_ref,
        }

        json_output = suite.get("json_output")
        if json_output:
            exact[json_output] = suite_info

        for pattern in suite.get("json_output_patterns", []):
            patterns.append((pattern, suite_info))

    return exact, patterns


def _find_schema_for_file(json_file, exact, patterns):
    basename = Path(json_file).name
    if basename in exact:
        return exact[basename]

    for pattern, suite_info in patterns:
        if fnmatch.fnmatch(basename, pattern):
            return suite_info

    return None


def _discover_selected_files(selected_suites, json_dir, registry, registry_path):
    suites_by_name = _suite_by_canonical(registry)
    discovered = []
    missing = []
    seen = set()

    for canonical in expand_selected_suites(selected_suites, registry):
        suite = suites_by_name.get(canonical)
        if not suite or not suite.get("schema"):
            continue

        candidates = []
        json_output = suite.get("json_output")
        if json_output:
            candidates.append(Path(json_dir) / json_output)

        for pattern in suite.get("json_output_patterns", []):
            candidates.extend(sorted(Path(json_dir).glob(pattern)))

        existing = [candidate for candidate in candidates if candidate.is_file()]
        if not existing:
            expected = [str(candidate) for candidate in candidates] or ["<no json_output registered>"]
            missing.append((canonical, expected))
            continue

        for path in existing:
            resolved = str(path.resolve())
            if resolved not in seen:
                seen.add(resolved)
                discovered.append(path)

    return discovered, missing


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_schema(schema_path, schema_fragment):
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)

    schema_uri = schema_path.resolve().as_uri()
    if schema_fragment:
        # Keep the selected fragment and its local references in one resource.
        # New jsonschema releases otherwise resolve nested #/definitions refs
        # against the external-ref wrapper instead of the complete schema.
        validator_schema = {
            "$schema": schema.get(
                "$schema", "https://json-schema.org/draft/2020-12/schema"
            ),
            "$ref": schema_fragment,
        }
        for definitions_key in ("definitions", "$defs"):
            if definitions_key in schema:
                validator_schema[definitions_key] = schema[definitions_key]
        Draft202012Validator.check_schema(validator_schema)
        return schema, Draft202012Validator(validator_schema)

    base_uri = schema_path.resolve().parent.as_uri() + "/"
    resolver = RefResolver(
        base_uri=base_uri,
        referrer=schema,
        store={schema_uri: schema},
    )
    return schema, Draft202012Validator(schema, resolver=resolver)


def _format_path(path):
    parts = []
    for item in path:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        elif parts:
            parts.append(f".{item}")
        else:
            parts.append(str(item))
    return "".join(parts) if parts else "<root>"


def _suite_from_path(path, default_suite="<root>"):
    if path:
        first = path[0]
        if isinstance(first, str) and first.startswith("Suite_Name:"):
            return first
    return default_suite


def _collect_key_issues(error):
    missing = set()
    unexpected = set()

    def handle(candidate):
        if candidate.validator == "required" and isinstance(candidate.instance, dict):
            required = candidate.validator_value
            if isinstance(required, list):
                missing.update(key for key in required if key not in candidate.instance)
        elif candidate.validator == "additionalProperties" and isinstance(candidate.message, str):
            unexpected.update(re.findall(r"'([^']+)'", candidate.message))

    if error.context:
        for suberror in error.context:
            handle(suberror)
    else:
        handle(error)

    return missing, unexpected


def _best_suberror(error):
    if error.validator not in ("anyOf", "oneOf") or not error.context:
        return None

    non_additional = [
        suberror for suberror in error.context if suberror.validator != "additionalProperties"
    ]
    candidate = best_match(non_additional) if non_additional else None
    if candidate is not None and candidate.validator == "type":
        for suberror in error.context:
            if suberror.validator == "additionalProperties":
                return suberror
    return candidate if candidate is not None else best_match(error.context)


def _error_tag(error, missing, unexpected):
    if missing:
        return "MISSING_KEY"
    if unexpected:
        return "UNEXPECTED_KEY"
    if error.validator == "not":
        return "DISALLOWED_VALUE"
    if error.validator == "type":
        return "TYPE_MISMATCH"
    if error.validator == "enum":
        return "ENUM"
    if error.validator:
        return str(error.validator).upper()
    return "VALIDATION"


def _shorten_message(error):
    message = error.message
    if isinstance(error.instance, dict) and message.startswith("{") and " is " in message:
        return "object" + message[message.find(" is "):]
    if isinstance(error.instance, list) and message.startswith("[") and " is " in message:
        return "array" + message[message.find(" is "):]
    if error.validator == "not" and isinstance(error.schema, dict):
        disallowed = error.schema.get("not")
        if isinstance(disallowed, dict) and disallowed.get("enum"):
            return f"value '{error.instance}' is not allowed"
    return message


def _subtest_result_unexpected_keys(instance, schema):
    try:
        allowed = set(schema["definitions"]["sub_test_result_object"]["properties"])
    except (KeyError, TypeError):
        return set()

    if not isinstance(instance, dict) or not isinstance(instance.get("subtests"), list):
        return set()

    unexpected = set()
    for subtest in instance["subtests"]:
        if not isinstance(subtest, dict):
            continue
        result = subtest.get("sub_test_result")
        if isinstance(result, dict):
            unexpected.update(set(result) - allowed)
    return unexpected


def _is_prefix_path(prefix, full):
    return len(prefix) <= len(full) and all(left == right for left, right in zip(prefix, full))


def _filter_cascading_errors(errors, default_suite):
    by_suite = {}
    for error in errors:
        path = list(error.absolute_path)
        suite = _suite_from_path(path, default_suite)
        by_suite.setdefault(suite, []).append(error)

    filtered = []
    for suite_errors in by_suite.values():
        specific_paths = [
            list(error.absolute_path)
            for error in suite_errors
            if error.validator != "unevaluatedProperties"
        ]
        for error in suite_errors:
            if error.validator == "unevaluatedProperties" and specific_paths:
                path = list(error.absolute_path)
                if any(_is_prefix_path(path, specific) for specific in specific_paths):
                    continue
            filtered.append(error)
    return sorted(filtered, key=lambda item: list(item.absolute_path))


def _report_path(error, default_suite, path_prefix=None):
    path = list(error.absolute_path)
    formatted = _format_path(path)
    if default_suite != "<root>" and _suite_from_path(path) == "<root>":
        prefix = path_prefix or default_suite
        return prefix if formatted == "<root>" else f"{prefix}.{formatted}"
    return formatted


def _validation_report(
    instance,
    schema,
    errors,
    default_suite="<root>",
    path_prefix=None,
    max_paths=5,
):
    errors = _filter_cascading_errors(errors, default_suite)
    grouped = {}

    for error in errors:
        suite = _suite_from_path(list(error.absolute_path), default_suite)
        suberror = _best_suberror(error)
        base_error = suberror if suberror is not None else error
        message = _shorten_message(base_error)
        missing, unexpected = _collect_key_issues(base_error)

        if base_error.validator == "unevaluatedProperties" and not missing and not unexpected:
            nested_unexpected = _subtest_result_unexpected_keys(error.instance, schema)
            if nested_unexpected:
                unexpected = nested_unexpected
                names = ", ".join(f"'{key}' was unexpected" for key in sorted(unexpected))
                message = f"Additional properties are not allowed ({names})"

        details = []
        if missing:
            details.append(f"{RED}missing{NC}: " + ", ".join(sorted(missing)))
        if unexpected:
            details.append(f"{BLUE}unexpected{NC}: " + ", ".join(sorted(unexpected)))
        if details:
            message = f"{message} ({'; '.join(details)})"

        tag = _error_tag(base_error, missing, unexpected)
        message = f"{YELLOW}{tag}{NC}: {message}"
        grouped.setdefault((suite, message), []).append(error)

    if default_suite == "<root>" and isinstance(instance, dict):
        suites = sorted(
            key for key in instance if isinstance(key, str) and key.startswith("Suite_Name:")
        )
    elif default_suite != "<root>":
        suites = [default_suite]
    else:
        suites = []

    error_suites = sorted({suite for suite, _ in grouped if suite != "<root>"})
    suites.extend(suite for suite in error_suites if suite not in suites)

    lines = []
    counts = {suite: 0 for suite in suites}
    for suite in suites:
        suite_groups = [
            (message, group_errors)
            for (group_suite, message), group_errors in grouped.items()
            if group_suite == suite
        ]
        if not suite_groups:
            lines.append(f"{GREEN}*suite={suite} no errors{NC}")
            continue

        for message, group_errors in suite_groups:
            counts[suite] += len(group_errors)
            paths = [
                _report_path(error, default_suite, path_prefix) for error in group_errors
            ]
            lines.append(f"{RED}*suite={suite} issue={message} count={len(paths)}{NC}")
            lines.extend(f"{YELLOW}  *at={path}{NC}" for path in paths[:max_paths])
            if len(paths) > max_paths:
                lines.append(f"{YELLOW}  *... and {len(paths) - max_paths} more{NC}")
            lines.append("")

    root_groups = [
        (message, group_errors)
        for (suite, message), group_errors in grouped.items()
        if suite == "<root>"
    ]
    if root_groups:
        counts["<root>"] = 0
        for message, group_errors in root_groups:
            counts["<root>"] += len(group_errors)
            paths = [
                _report_path(error, default_suite, path_prefix) for error in group_errors
            ]
            lines.append(f"{RED}*suite=<root> issue={message} count={len(paths)}{NC}")
            lines.extend(f"{YELLOW}  *at={path}{NC}" for path in paths[:max_paths])
            if len(paths) > max_paths:
                lines.append(f"{YELLOW}  *... and {len(paths) - max_paths} more{NC}")
            lines.append("")

    while lines and not lines[-1]:
        lines.pop()
    return lines, counts


def _count_report_lines(counts):
    lines = [f"{BLUE}--- Error Counts by Suite ---{NC}"]
    for suite, count in counts.items():
        color = GREEN if count == 0 else RED
        lines.append(f"{color}{suite}: {count}{NC}")
    return lines


def _fatal_report(suite, tag, message, path):
    lines = [
        f"{RED}*suite={suite} issue={YELLOW}{tag}{NC}: {message} count=1{NC}",
        f"{YELLOW}  *at={path}{NC}",
    ]
    return lines, {suite: 1}


def _validate_one(json_file, suite_info):
    json_path = Path(json_file)
    result = {
        "canonical": suite_info["canonical"],
        "json_path": json_path,
        "schema_ref": suite_info["schema_ref"],
    }
    schema_path = suite_info["schema"]
    if not schema_path.is_file():
        result["fatal"] = ("SCHEMA_FILE", f"schema not found: {suite_info['schema_ref']}")
        return result

    try:
        result["data"] = _load_json(json_path)
    except Exception as exc:
        result["fatal"] = ("JSON_FILE", f"failed to read JSON: {exc}")
        return result

    try:
        result["schema"], validator = _load_schema(
            schema_path, suite_info["schema_fragment"]
        )
    except Exception as exc:
        result["fatal"] = ("SCHEMA_FILE", f"failed to load schema: {exc}")
        return result

    result["errors"] = sorted(
        validator.iter_errors(result["data"]),
        key=lambda item: list(item.absolute_path),
    )
    return result


def _print_heading(title):
    print(f"{BLUE}====================================={NC}")
    print(f"{BLUE}{title}{NC}")
    print(f"{BLUE}====================================={NC}\n")


def _run_merged_validation(json_file, schema_file, max_paths):
    json_path = Path(json_file)
    schema_path = Path(schema_file)
    if not json_path.is_file():
        print(f"{RED}Error: File not found: {json_path}{NC}")
        return 1
    if not schema_path.is_file():
        print(f"{RED}Error: Schema file not found: {schema_path}{NC}")
        return 1

    _print_heading("JSON Schema Validation")

    try:
        instance = _load_json(json_path)
    except Exception as exc:
        lines, counts = _fatal_report(
            "<root>", "JSON_FILE", f"failed to read JSON: {exc}", "<root>"
        )
        print(f"{RED}✗ Schema validation FAILED{NC}\n")
        print(f"{RED}Errors:{NC}")
        print("\n".join([*lines, "", *_count_report_lines(counts)]))
        print(f"\n{BLUE}File: {json_path}{NC}")
        print(f"{BLUE}Schema: {schema_path}{NC}\n")
        return 1

    try:
        schema, validator = _load_schema(schema_path, "")
    except Exception as exc:
        lines, counts = _fatal_report(
            "<root>", "SCHEMA_FILE", f"failed to load schema: {exc}", "<schema>"
        )
        print(f"{RED}✗ Schema validation FAILED{NC}\n")
        print(f"{RED}Errors:{NC}")
        print("\n".join([*lines, "", *_count_report_lines(counts)]))
        print(f"\n{BLUE}File: {json_path}{NC}")
        print(f"{BLUE}Schema: {schema_path}{NC}\n")
        return 1

    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    if not errors:
        print(f"{GREEN}✓ Schema validation PASSED{NC}\n")
        print(f"{BLUE}File: {json_path}{NC}")
        print(f"{BLUE}Schema: {schema_path}{NC}\n")
        return 0

    lines, counts = _validation_report(instance, schema, errors, max_paths=max_paths)
    print(f"{RED}✗ Schema validation FAILED{NC}\n")
    print(f"{RED}Errors:{NC}")
    print("\n".join([*lines, "", *_count_report_lines(counts)]))
    print(f"\n{BLUE}File: {json_path}{NC}")
    print(f"{BLUE}Schema: {schema_path}{NC}\n")
    return 1


def _split_selected_suites(value):
    suites = []
    for chunk in value or []:
        for item in chunk.split(","):
            item = item.strip()
            if item:
                suites.append(item)
    return suites


def _run_raw_validation(args):
    max_paths = max(args.max_paths, 1)
    registry_path = Path(args.registry)
    try:
        registry = load_registry(str(registry_path))
    except Exception as exc:
        print(f"{RED}ERROR:{NC} failed to load registry '{registry_path}': {exc}")
        return 2
    exact, patterns = _build_file_schema_index(registry, registry_path)

    json_files = [Path(path) for path in args.json_files]
    missing = []
    selected_suites = _split_selected_suites(args.selected_suites)

    if not json_files and selected_suites:
        if not args.json_dir:
            print(
                f"{RED}ERROR:{NC} --json-dir is required when --selected-suites "
                "is used without JSON files."
            )
            return 2
        json_files, missing = _discover_selected_files(
            selected_suites, args.json_dir, registry, registry_path
        )
    elif not json_files:
        print(
            f"{RED}ERROR:{NC} raw validation requires JSON files, or "
            "--json-dir with --selected-suites."
        )
        return 2

    results = []
    skipped_paths = []
    seen = set()
    for json_file in json_files:
        resolved = str(json_file.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)

        suite_info = _find_schema_for_file(json_file, exact, patterns)
        if not suite_info:
            skipped_paths.append(json_file)
            continue
        results.append(_validate_one(json_file, suite_info))

    if not results and not missing:
        _print_heading("Suite JSON Schema Validation")
        print(f"{RED}✗ Schema validation NOT RUN{NC}\n")
        print(f"{RED}ERROR:{NC} no files matched a registered raw suite schema.")
        if skipped_paths:
            print(f"\n{BLUE}--- Skipped Files (no registered suite schema) ---{NC}")
            for skipped_path in skipped_paths:
                print(f"{YELLOW}{skipped_path}{NC}")
        print(f"\n{BLUE}Registry: {registry_path}{NC}")
        print(f"Schema validation result: {RED}NOT RUN{NC} (0 validated)")
        return 2

    detail_lines = []
    counts = {}
    failed = len(missing)
    passed = 0
    canonical_counts = {}
    for result in results:
        canonical = result["canonical"]
        canonical_counts[canonical] = canonical_counts.get(canonical, 0) + 1

    for canonical, expected_paths in missing:
        suite = f"Suite_Name: {canonical}"
        detail_lines.append(
            f"{RED}*suite={suite} issue={YELLOW}MISSING_JSON{NC}: "
            f"generated JSON not found count=1{NC}"
        )
        detail_lines.extend(
            f"{YELLOW}  *at={expected_path}{NC}" for expected_path in expected_paths[:max_paths]
        )
        if len(expected_paths) > max_paths:
            detail_lines.append(
                f"{YELLOW}  *... and {len(expected_paths) - max_paths} more expected paths{NC}"
            )
        detail_lines.append("")
        counts[suite] = counts.get(suite, 0) + 1

    for result in results:
        path_prefix = f"Suite_Name: {result['canonical']}"
        suite = path_prefix
        if canonical_counts[result["canonical"]] > 1:
            suite += f" [{result['json_path'].name}]"
        if "fatal" in result:
            tag, message = result["fatal"]
            error_path = (
                str(result["json_path"])
                if tag == "JSON_FILE"
                else result["schema_ref"]
            )
            lines, result_counts = _fatal_report(suite, tag, message, error_path)
            failed += 1
        else:
            lines, result_counts = _validation_report(
                result["data"],
                result["schema"],
                result["errors"],
                default_suite=suite,
                path_prefix=path_prefix,
                max_paths=max_paths,
            )
            if result["errors"]:
                failed += 1
            else:
                passed += 1
        detail_lines.extend([*lines, ""])
        for name, count in result_counts.items():
            counts[name] = counts.get(name, 0) + count

    while detail_lines and not detail_lines[-1]:
        detail_lines.pop()

    _print_heading("Suite JSON Schema Validation")

    if failed:
        print(f"{RED}✗ Schema validation FAILED{NC}\n")
        print(f"{RED}Errors:{NC}")
        if detail_lines:
            print("\n".join(detail_lines))
            print()
        print("\n".join(_count_report_lines(counts)))
    else:
        print(f"{GREEN}✓ Schema validation PASSED{NC}")
        if not results:
            print(f"{YELLOW}SKIP{NC} no suite JSON files with registered schemas were found")

    if results:
        print(f"\n{BLUE}--- Files Checked ---{NC}")
        for result in results:
            print(f"{BLUE}{result['canonical']}: {result['json_path']}{NC}")

    if skipped_paths:
        print(f"\n{BLUE}--- Skipped Files (no registered suite schema) ---{NC}")
        for skipped_path in skipped_paths:
            print(f"{YELLOW}{skipped_path}{NC}")

    print(f"\n{BLUE}Registry: {registry_path}{NC}")
    skipped = len(skipped_paths)
    if failed:
        print(
            f"Schema validation result: {RED}FAIL{NC} "
            f"({failed} failed, {passed} passed, {skipped} skipped)"
        )
        return 1

    print(
        f"Schema validation result: {GREEN}PASS{NC} "
        f"({len(results)} validated, {skipped} skipped)"
    )
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Validate SystemReady merged results or individual suite JSON files.",
        epilog=(
            "examples:\n"
            "  validate.py merged /path/to/merged_results.json\n"
            "  validate.py raw /path/to/bsa.json /path/to/fwts.json\n"
            "  validate.py raw --json-dir /path/to/acs_jsons "
            "--selected-suites BSA,FWTS"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    merged_parser = subparsers.add_parser(
        "merged",
        help="Validate one complete merged_results.json file",
        description="Validate one complete merged_results.json file.",
    )
    merged_parser.add_argument("json_file", help="Path to merged_results.json")
    merged_parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA),
        help=f"Merged schema path (default: {DEFAULT_SCHEMA})",
    )
    merged_parser.add_argument(
        "--max-paths",
        "--max-errors",
        dest="max_paths",
        type=int,
        default=5,
        help="Maximum example paths per grouped issue (default: 5)",
    )

    raw_parser = subparsers.add_parser(
        "raw",
        help="Validate one or more individual suite JSON files",
        description=(
            "Validate individual suite JSON files using filename-to-schema "
            "mappings from the suite registry."
        ),
    )
    raw_parser.add_argument("json_files", nargs="*", help="Suite JSON files to validate")
    raw_parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help=f"Suite registry path (default: {DEFAULT_REGISTRY})",
    )
    raw_parser.add_argument(
        "--json-dir",
        help="Directory containing generated suite JSON files",
    )
    raw_parser.add_argument(
        "--selected-suites",
        action="append",
        default=[],
        metavar="NAMES",
        help="Suite name or comma-separated names to discover in --json-dir",
    )
    raw_parser.add_argument(
        "--max-paths",
        "--max-errors",
        dest="max_paths",
        type=int,
        default=5,
        help="Maximum example paths per grouped issue (default: 5)",
    )
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "merged":
        return _run_merged_validation(
            args.json_file,
            args.schema,
            max(args.max_paths, 1),
        )
    if args.command == "raw":
        return _run_raw_validation(args)
    parser.error(f"unsupported validation mode: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
