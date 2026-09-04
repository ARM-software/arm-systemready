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

"""Portable, strict suite-wise SystemReady log parser orchestration."""

import argparse
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from suite_registry import (
    expand_selected_suites,
    get_suite,
    list_suite_names,
    load_registry,
    normalize_suite_name,
    suite_supports_mode,
)


DEFAULT_REGISTRY = BASE_DIR / "suite_registry.json"
SCHEMA_VALIDATOR = BASE_DIR / "validate.py"
DEFAULT_MODE = "SR"
MINIMUM_PYTHON = (3, 8)
MINIMUM_OUTPUT_FREE_BYTES = 10 * 1024 * 1024

EXIT_INPUT = 3
EXIT_DEPENDENCY = 4
EXIT_PARSE = 5
EXIT_SCHEMA = 6
EXIT_REPORT = 7
EXIT_OUTPUT = 8

PACKAGE_NAMES = {
    "chardet": "chardet",
    "jinja2": "Jinja2",
    "jsonschema": "jsonschema",
    "matplotlib": "matplotlib",
    "weasyprint": "weasyprint",
}


def get_log_parser_version():
    version = os.environ.get("LOG_PARSER_VERSION")
    if version:
        return version

    try:
        main_script = (BASE_DIR / "main_log_parser.sh").read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    match = re.search(
        r'^LOG_PARSER_VERSION="([0-9A-Za-z.+-]+)"$',
        main_script,
        flags=re.MULTILINE,
    )
    return match.group(1) if match else "unknown"


class StandaloneError(Exception):
    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code


class MissingSuiteInputError(StandaloneError):
    """A selected suite has no collected input, but a summary can report it."""


class SuiteNotRunError(StandaloneError):
    """A parser recognized its input but found no runnable suite tests."""


@dataclass
class ResolvedInput:
    path: Path
    exists: bool
    supporting: bool = False


@dataclass
class SuiteResult:
    canonical: str
    suite: dict
    execution: dict
    inputs: dict
    json_files: list = field(default_factory=list)
    boot_sources: list = field(default_factory=list)
    detailed_html: Path = None
    summary_html: Path = None


def load_registry_data(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise StandaloneError(f"Cannot load suite registry '{path}': {error}", EXIT_INPUT) from error

    standalone = data.get("standalone")
    if not isinstance(standalone, dict):
        raise StandaloneError("Suite registry has no standalone configuration.", EXIT_INPUT)
    return data, standalone


def split_values(values):
    result = []
    for group in values or []:
        for value in group:
            result.extend(item.strip() for item in value.split(",") if item.strip())
    return result


def flatten_values(values):
    return [value for group in (values or []) for value in group]


def parse_direct_inputs(values, canonical, execution):
    supplied = flatten_values(values)
    if not supplied:
        return {}

    specs = [
        spec for spec in execution.get("inputs", [])
        if spec.get("kind", "file") == "file"
    ]
    if not specs:
        raise StandaloneError(
            f"{canonical}: direct log files are not supported for this suite.", EXIT_INPUT
        )

    specs_by_name = {
        spec["name"].strip().lower().replace("-", "_"): spec for spec in specs
    }
    named = {}
    positional = []
    for value in supplied:
        possible_name, separator, possible_path = value.partition("=")
        normalized_name = possible_name.strip().lower().replace("-", "_")
        if separator and normalized_name in specs_by_name:
            if not possible_path.strip():
                raise StandaloneError(
                    f"{canonical}: direct input '{possible_name}' has an empty path.",
                    EXIT_INPUT,
                )
            input_name = specs_by_name[normalized_name]["name"]
            if input_name in named:
                raise StandaloneError(
                    f"{canonical}: direct input '{input_name}' was provided more than once.",
                    EXIT_INPUT,
                )
            named[input_name] = possible_path
        elif separator and "/" not in possible_name and "\\" not in possible_name:
            expected = ", ".join(spec["name"] for spec in specs)
            raise StandaloneError(
                f"{canonical}: unknown direct input name '{possible_name}'. "
                f"Expected one of: {expected}.",
                EXIT_INPUT,
            )
        else:
            positional.append(value)

    remaining = [spec for spec in specs if spec["name"] not in named]
    if len(positional) > len(remaining):
        expected = ", ".join(spec["name"] for spec in specs)
        raise StandaloneError(
            f"{canonical}: received {len(supplied)} direct log files, but the registry "
            f"defines only {len(specs)} file inputs ({expected}).",
            EXIT_INPUT,
        )

    if len(positional) == 1 and len(remaining) > 1:
        required = [spec for spec in remaining if spec.get("required")]
        targets = required if len(required) == 1 else remaining[:1]
    else:
        targets = remaining[:len(positional)]
    for spec, value in zip(targets, positional):
        named[spec["name"]] = value

    resolved = {}
    used_paths = set()
    for spec in specs:
        input_name = spec["name"]
        if input_name not in named:
            continue
        path = Path(named[input_name]).expanduser().resolve()
        if not path.is_file():
            raise StandaloneError(
                f"{canonical}: direct input '{input_name}' is not a file: {path}",
                EXIT_INPUT,
            )
        if path in used_paths:
            raise StandaloneError(
                f"{canonical}: the same direct log was assigned more than once: {path}",
                EXIT_INPUT,
            )
        used_paths.add(path)
        resolved[input_name] = ResolvedInput(
            path,
            True,
            bool(spec.get("supporting")),
        )
    return resolved


def parse_outputs(value, defaults):
    requested = []
    for item in (value.split(",") if value else defaults):
        name = item.strip().lower()
        if name and name not in requested:
            requested.append(name)
    valid = {"json", "html", "summary", "pdf"}
    invalid = [item for item in requested if item not in valid]
    if invalid:
        raise StandaloneError(
            f"Unsupported output stage(s): {', '.join(invalid)}. Use json, html, summary, or pdf.",
            EXIT_INPUT,
        )
    if "pdf" in requested and "summary" not in requested:
        requested.append("summary")
    if "summary" in requested and "html" not in requested:
        requested.append("html")
    if "json" not in requested:
        requested.append("json")
    return [stage for stage in ("json", "html", "summary", "pdf") if stage in requested]


def build_input_roots(results_path=None):
    roots = {}
    if results_path:
        roots.update({
            "results": results_path,
            "firmware": results_path.parent / "fw",
            "os_logs": results_path.parent / "os-logs",
        })
    return roots


def resolve_input(spec, roots):
    root_name = spec.get("root")
    if root_name not in roots:
        raise StandaloneError(
            f"Registry input '{spec.get('name', '?')}' uses unknown root '{root_name}'.",
            EXIT_INPUT,
        )
    candidates = spec.get("candidates", [])
    if not candidates:
        raise StandaloneError(
            f"Registry input '{spec.get('name', '?')}' has no candidate paths.", EXIT_INPUT
        )

    expected = None
    for candidate in candidates:
        path = (roots[root_name] / candidate).resolve()
        expected = expected or path
        kind = spec.get("kind", "file")
        exists = path.is_dir() if kind == "directory" else path.is_file()
        if exists:
            return ResolvedInput(path, True, bool(spec.get("supporting")))
    return ResolvedInput(expected, False, bool(spec.get("supporting")))


def resolve_suite_inputs(canonical, execution, roots, direct_inputs=None):
    direct_inputs = direct_inputs or {}
    resolved = {}
    missing_required = []
    primary_found = 0

    for spec in execution.get("inputs", []):
        if spec["name"] in direct_inputs:
            item = direct_inputs[spec["name"]]
        elif spec.get("root") in roots:
            item = resolve_input(spec, roots)
        else:
            item = ResolvedInput(
                Path(f"<{spec.get('root', 'input')}>") / spec["candidates"][0],
                False,
                bool(spec.get("supporting")),
            )
        resolved[spec["name"]] = item
        if item.exists and not item.supporting:
            primary_found += 1
        if spec.get("required") and not item.exists:
            missing_required.append(item.path)

    if missing_required:
        lines = "\n".join(f"  - {path}" for path in missing_required)
        raise MissingSuiteInputError(
            f"{canonical}: required input is missing:\n{lines}", EXIT_INPUT
        )

    minimum = int(execution.get("minimum_inputs", 0))
    if primary_found < minimum:
        expected = [item.path for item in resolved.values() if not item.supporting]
        lines = "\n".join(f"  - {path}" for path in expected)
        raise MissingSuiteInputError(
            f"{canonical}: requires at least {minimum} input log(s); found {primary_found}:\n{lines}",
            EXIT_INPUT,
        )
    return resolved


def registry_script(suite, key):
    relative = suite.get(key)
    if not relative:
        raise StandaloneError(
            f"{suite.get('canonical', '?')}: registry field '{key}' is missing.", EXIT_INPUT
        )
    path = (BASE_DIR / relative).resolve()
    if not path.is_file():
        raise StandaloneError(
            f"{suite.get('canonical', '?')}: registered script does not exist: {path}",
            EXIT_INPUT,
        )
    return path


def parser_not_run_statuses(canonical, execution):
    """Return validated parser statuses that mean a suite could not run."""
    configured = execution.get("not_run_exit_codes", {})
    if not isinstance(configured, dict):
        raise StandaloneError(
            f"{canonical}: not_run_exit_codes must map statuses to reasons.",
            EXIT_INPUT,
        )

    statuses = {}
    for raw_status, reason in configured.items():
        try:
            status = int(raw_status)
        except (TypeError, ValueError):
            status = 0
        if status <= 0 or str(status) != str(raw_status):
            raise StandaloneError(
                f"{canonical}: invalid not-run parser status '{raw_status}'.",
                EXIT_INPUT,
            )
        if not isinstance(reason, str) or not reason.strip():
            raise StandaloneError(
                f"{canonical}: not-run parser status {status} has no reason.",
                EXIT_INPUT,
            )
        statuses[status] = reason.strip()
    return statuses


def validate_registry(registry, standalone, registry_path=DEFAULT_REGISTRY):
    suite_map = {suite.get("canonical"): suite for suite in registry}
    execution_map = standalone.get("suite_execution", {})
    known_handlers = {
        "capsule",
        "multi_log",
        "os_tests",
        "psci",
        "sbmr",
        "sct",
        "single_log",
        "standalone_single",
    }
    known_roots = {"results", "firmware", "os_logs"}
    alias_owners = {}

    for suite in registry:
        canonical = suite.get("canonical")
        if not canonical:
            raise StandaloneError("Registry contains a suite without a canonical name.", EXIT_INPUT)
        for alias in [canonical] + suite.get("aliases", []):
            token = "-".join(alias.strip().upper().replace("_", "-").split())
            owner = alias_owners.get(token)
            if owner and owner != canonical:
                raise StandaloneError(
                    f"Registry alias '{alias}' is shared by {owner} and {canonical}.", EXIT_INPUT
                )
            alias_owners[token] = canonical

        if suite.get("included_suites"):
            for child in suite["included_suites"]:
                if child not in suite_map:
                    raise StandaloneError(
                        f"{canonical}: included suite '{child}' is not registered.", EXIT_INPUT
                    )
            continue

        execution = execution_map.get(canonical)
        if not execution:
            raise StandaloneError(
                f"{canonical}: standalone execution configuration is missing.", EXIT_INPUT
            )
        if execution.get("handler") not in known_handlers:
            raise StandaloneError(
                f"{canonical}: unsupported standalone handler '{execution.get('handler')}'.",
                EXIT_INPUT,
            )
        parser_not_run_statuses(canonical, execution)
        input_names = set()
        for input_spec in execution.get("inputs", []):
            input_name = input_spec.get("name")
            if not input_name or input_name in input_names:
                raise StandaloneError(
                    f"{canonical}: input names must be present and unique.", EXIT_INPUT
                )
            input_names.add(input_name)
            if input_spec.get("root") not in known_roots:
                raise StandaloneError(
                    f"{canonical}: input '{input_name}' uses an unknown root.", EXIT_INPUT
                )
            candidates = input_spec.get("candidates")
            if not candidates:
                raise StandaloneError(
                    f"{canonical}: input '{input_name}' has no candidate path.", EXIT_INPUT
                )
            for candidate in candidates:
                candidate_path = Path(candidate)
                if candidate_path.is_absolute() or ".." in candidate_path.parts:
                    raise StandaloneError(
                        f"{canonical}: input '{input_name}' must stay within its registered root.",
                        EXIT_INPUT,
                    )
        registry_script(suite, "logs_to_json")
        registry_script(suite, "json_to_html")
        if execution.get("handler") == "os_tests" and "SR" in suite.get("modes", []):
            registry_script(suite, "sr_logs_to_json")
        for support_script in suite.get("supporting_logs_to_json", []):
            support_path = (BASE_DIR / support_script).resolve()
            if not support_path.is_file():
                raise StandaloneError(
                    f"{canonical}: registered supporting parser does not exist: {support_path}",
                    EXIT_INPUT,
                )

        schema_value = suite.get("schema", "")
        if schema_value:
            schema_path = schema_value.split("#", 1)[0]
            resolved_schema = (Path(registry_path).resolve().parent / schema_path).resolve()
            if not resolved_schema.is_file():
                raise StandaloneError(
                    f"{canonical}: registered schema does not exist: {schema_path}", EXIT_INPUT
                )

    required_summary_inputs = {"uefi_version", "dmidecode", "ipmitool", "psci"}
    summary_inputs = standalone.get("summary_inputs", {})
    if set(summary_inputs) != required_summary_inputs:
        raise StandaloneError(
            "Standalone summary_inputs must define uefi_version, dmidecode, ipmitool, and psci.",
            EXIT_INPUT,
        )
    for name, spec in summary_inputs.items():
        candidates = spec.get("candidates")
        if spec.get("root") not in known_roots or not candidates:
            raise StandaloneError(
                f"Standalone summary input '{name}' has an invalid root or candidates.",
                EXIT_INPUT,
            )
        for candidate in candidates:
            relative_path = Path(candidate)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise StandaloneError(
                    f"Standalone summary input '{name}' must stay within its registered root.",
                    EXIT_INPUT,
                )


def validate_support_files(outputs, schema_requested, waiver):
    paths = [BASE_DIR / "enrich_suite_json.py"]
    if waiver:
        paths.append(BASE_DIR / "apply_waivers.py")
    if schema_requested:
        paths.append(SCHEMA_VALIDATOR)
    if "summary" in outputs:
        paths.extend(
            BASE_DIR / name
            for name in ("acs_info.py", "merge_jsons.py", "generate_acs_summary.py")
        )

    missing = [path for path in paths if not path.is_file()]
    if missing:
        lines = "\n".join(f"  - {path}" for path in missing)
        raise StandaloneError(f"Required standalone support file is missing:\n{lines}", EXIT_INPUT)


def check_dependencies(modules):
    missing = []
    for module in sorted(set(modules)):
        command = [sys.executable, "-c", f"import {module}"]
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            missing.append((module, result.stderr.strip().splitlines()[-1:] or ["import failed"]))

    if missing:
        packages = ", ".join(PACKAGE_NAMES.get(module, module) for module, _ in missing)
        install_command = (
            f"{sys.executable} -m pip install -r {BASE_DIR / 'requirements.txt'}"
        )
        raise StandaloneError(
            f"Missing or unusable Python dependencies: {packages}. "
            f"Install with: {install_command}",
            EXIT_DEPENDENCY,
        )


def run_command(label, command, failure_code, accepted_return_codes=()):
    print(f"{label}")
    command = [str(item) for item in command]
    try:
        process = subprocess.Popen(command, start_new_session=True)
    except OSError as error:
        raise StandaloneError(
            f"Cannot start command: {' '.join(command)}: {error}", failure_code
        ) from error
    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    if return_code != 0 and return_code not in accepted_return_codes:
        raise StandaloneError(
            f"Command failed with status {return_code}: {' '.join(command)}",
            failure_code,
        )
    return return_code


def validate_json_output(canonical, path):
    if not path.is_file():
        raise StandaloneError(f"{canonical}: parser did not create {path}", EXIT_PARSE)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise StandaloneError(f"{canonical}: invalid generated JSON '{path}': {error}", EXIT_PARSE) from error
    if not isinstance(data, dict) or not isinstance(data.get("test_results"), list):
        raise StandaloneError(
            f"{canonical}: generated JSON has no test_results list: {path}", EXIT_PARSE
        )


def apply_waiver(canonical, suite, json_file, waiver, test_category):
    if not waiver:
        return
    command = [
        sys.executable,
        BASE_DIR / "apply_waivers.py",
        suite.get("waiver_suite", canonical),
        json_file,
        waiver,
        test_category,
        "--quiet",
    ]
    run_command(f"[{canonical}] Applying waivers", command, EXIT_PARSE)
    validate_json_output(canonical, json_file)


def primary_inputs(resolved):
    return [item.path for item in resolved.values() if item.exists and not item.supporting]


def run_os_tests(canonical, suite, execution, resolved, mode, json_dir):
    result = SuiteResult(canonical, suite, execution, resolved)
    os_logs = resolved["os_logs"].path

    if mode == "SR":
        output = json_dir / suite["json_output"]
        post_script = resolved["post_script"].path
        command = [
            sys.executable,
            registry_script(suite, "sr_logs_to_json"),
            os_logs,
            post_script,
            output,
        ]
        run_command(f"[{canonical}] Parsing SR OS logs", command, EXIT_PARSE)
        validate_json_output(canonical, output)
        result.json_files.append(output)
        return result

    os_directories = sorted(path for path in os_logs.glob("linux*") if path.is_dir())
    for os_directory in os_directories:
        ethtool_log = os_directory / "ethtool_test.log"
        if not ethtool_log.is_file():
            continue
        output = json_dir / f"ethtool_test_{os_directory.name}.json"
        command = [
            sys.executable,
            registry_script(suite, "logs_to_json"),
            ethtool_log,
            output,
            os_directory.name,
        ]
        run_command(f"[{canonical}] Parsing {os_directory.name}", command, EXIT_PARSE)
        validate_json_output(canonical, output)
        result.json_files.append(output)
        boot_sources = os_directory / "boot_sources.log"
        result.boot_sources.append(boot_sources if boot_sources.is_file() else "Unknown")

    if not result.json_files:
        raise MissingSuiteInputError(
            f"{canonical}: no linux*/ethtool_test.log inputs found under {os_logs}", EXIT_INPUT
        )
    return result


def run_suite(canonical, suite, execution, roots, mode, json_dir, direct_inputs=None):
    resolved = resolve_suite_inputs(canonical, execution, roots, direct_inputs)
    handler = execution.get("handler")
    if handler == "os_tests":
        return run_os_tests(canonical, suite, execution, resolved, mode, json_dir)

    output = json_dir / suite["json_output"]
    parser_script = registry_script(suite, "logs_to_json")
    result = SuiteResult(canonical, suite, execution, resolved)

    if handler in {"multi_log", "single_log", "standalone_single", "sbmr"}:
        command = [sys.executable, parser_script, *primary_inputs(resolved), output]
    elif handler == "sct":
        supporting = resolved.get("edk2")
        if supporting and supporting.exists:
            support_scripts = suite.get("supporting_logs_to_json", [])
            if not support_scripts:
                raise StandaloneError(f"{canonical}: supporting SCT parser is not registered.", EXIT_INPUT)
            support_output_name = next(
                spec.get("output") for spec in execution["inputs"] if spec.get("name") == "edk2"
            )
            support_output = json_dir / support_output_name
            support_script = (BASE_DIR / support_scripts[0]).resolve()
            run_command(
                f"[{canonical}] Parsing supporting EDK2 log",
                [sys.executable, support_script, supporting.path, support_output],
                EXIT_PARSE,
            )
        command = [sys.executable, parser_script, "--mode", mode, resolved["log"].path, output]
    elif handler == "capsule":
        command = [
            sys.executable,
            parser_script,
            "capsule_update",
            resolved["update"].path,
            resolved["on_disk"].path,
            resolved["results"].path,
            output,
        ]
    elif handler == "psci":
        command = [sys.executable, parser_script, "psci_check", resolved["log"].path, output]
    else:
        raise StandaloneError(f"{canonical}: unsupported registry handler '{handler}'.", EXIT_INPUT)

    not_run_statuses = parser_not_run_statuses(canonical, execution)
    return_code = run_command(
        f"[{canonical}] Parsing logs",
        command,
        EXIT_PARSE,
        not_run_statuses,
    )
    if return_code:
        output.unlink(missing_ok=True)
        raise SuiteNotRunError(
            f"{canonical}: {not_run_statuses[return_code]} "
            f"(parser status {return_code}).",
            EXIT_PARSE,
        )
    validate_json_output(canonical, output)
    result.json_files.append(output)
    return result


def render_reports(results, html_dir):
    standalone_results = [
        result for result in results
        if result.execution.get("handler") in {"standalone_single", "capsule", "psci"}
    ]
    regular_results = [result for result in results if result not in standalone_results]

    for result in regular_results:
        suite = result.suite
        detailed = html_dir / suite["detailed_html"]
        summary = html_dir / suite["summary_html"]
        command = [
            sys.executable,
            registry_script(suite, "json_to_html"),
            *result.json_files,
            detailed,
            summary,
        ]
        handler = result.execution.get("handler")
        if handler == "sbmr":
            report = result.inputs.get("report")
            command.append(report.path if report and report.exists else "")
        elif handler == "os_tests":
            command.append("--include-drop-down")
            if result.boot_sources:
                command.extend(["--boot-sources-paths", *result.boot_sources])
        run_command(f"[{result.canonical}] Generating HTML", command, EXIT_REPORT)
        if not detailed.is_file() or not summary.is_file():
            raise StandaloneError(
                f"{result.canonical}: HTML renderer did not create expected outputs.", EXIT_REPORT
            )
        result.detailed_html = detailed
        result.summary_html = summary

    if standalone_results:
        registry = load_registry()
        group = get_suite("STANDALONE", registry)
        detailed = html_dir / group["detailed_html"]
        summary = html_dir / group["summary_html"]
        json_files = [path for result in standalone_results for path in result.json_files]
        command = [
            sys.executable,
            registry_script(group, "json_to_html"),
            *json_files,
            detailed,
            summary,
            "--include-drop-down",
        ]
        run_command("[STANDALONE] Generating combined HTML", command, EXIT_REPORT)
        if not detailed.is_file() or not summary.is_file():
            raise StandaloneError(
                "STANDALONE: HTML renderer did not create expected outputs.", EXIT_REPORT
            )
        for result in standalone_results:
            result.detailed_html = detailed
            result.summary_html = summary


def generate_acs_info(standalone, roots, args, json_dir):
    summary_inputs = standalone.get("summary_inputs", {})

    def summary_path(name):
        spec = summary_inputs[name]
        if spec["root"] not in roots:
            return None
        paths = [
            (roots[spec["root"]] / candidate).resolve()
            for candidate in spec["candidates"]
        ]
        return next((path for path in paths if path.is_file()), paths[0])

    dmidecode = summary_path("dmidecode")
    empty_dmidecode = None
    if not dmidecode or not dmidecode.is_file():
        empty_dmidecode = json_dir / ".empty_dmidecode.log"
        empty_dmidecode.touch()
        dmidecode = empty_dmidecode

    command = [
        sys.executable,
        BASE_DIR / "acs_info.py",
        "--acs_config_path", args.acs_config or "",
        "--system_config_path", args.system_config or "",
        "--uefi_version_log", summary_path("uefi_version") or "",
        "--dmidecode_log", dmidecode,
        "--ipmitool_log", summary_path("ipmitool") or "",
        "--psci_kernel_log", summary_path("psci") or "",
        "--output_dir", json_dir,
    ]
    try:
        run_command("[SUMMARY] Gathering ACS information", command, EXIT_REPORT)
    finally:
        if empty_dmidecode:
            empty_dmidecode.unlink(missing_ok=True)
    acs_info = json_dir / "acs_info.json"
    if not acs_info.is_file():
        raise StandaloneError("ACS information generation did not create acs_info.json.", EXIT_REPORT)
    return acs_info


def merge_results(mode, selected, test_category, json_files, output):
    command = [
        sys.executable,
        BASE_DIR / "merge_jsons.py",
        "--mode", mode,
        "--test-category", test_category,
        "--selected-suites", ",".join(selected),
        output,
        *json_files,
    ]
    run_command("[SUMMARY] Merging selected suite JSON files", command, EXIT_REPORT)
    if not output.is_file():
        raise StandaloneError("Merge did not create merged_results.json.", EXIT_REPORT)


def generate_combined_summary(results, roots, args, html_dir, merged_json, acs_info):
    summaries = {result.canonical: result.summary_html for result in results if result.summary_html}
    standalone_summary = next(
        (
            result.summary_html
            for result in results
            if result.execution.get("handler") in {"standalone_single", "capsule", "psci"}
        ),
        None,
    )

    ordered = [
        summaries.get("BSA"),
        summaries.get("SBSA"),
        summaries.get("FWTS"),
        summaries.get("SCT"),
        summaries.get("BBSR-FWTS"),
        summaries.get("BBSR-SCT"),
        summaries.get("BBSR-TPM"),
        summaries.get("PFDI"),
        summaries.get("POST-SCRIPT"),
        standalone_summary,
        summaries.get("OS-TESTS"),
        None,
        summaries.get("SBMR-IB"),
        summaries.get("SBMR-OOB"),
        summaries.get("SCMI"),
    ]
    output = html_dir / "acs_summary.html"
    command = [
        sys.executable,
        BASE_DIR / "generate_acs_summary.py",
        *(str(path) if path else "" for path in ordered),
        output,
        "--merged_json", merged_json,
        "--acs_info_json", acs_info,
        "--use-acs-info-system-info",
    ]
    if args.acs_config:
        command.extend(["--acs_config_path", args.acs_config])
    if args.system_config:
        command.extend(["--system_config_path", args.system_config])
    results_root = roots.get("results")
    uefi_version = results_root / "uefi_dump/uefi_version.log" if results_root else None
    if uefi_version and uefi_version.is_file():
        command.extend(["--uefi_version_log", uefi_version])

    run_command("[SUMMARY] Generating combined HTML", command, EXIT_REPORT)
    if not output.is_file():
        raise StandaloneError("Combined report did not create acs_summary.html.", EXIT_REPORT)
    return output


def generate_pdf(html_path, pdf_path):
    code = (
        "import sys; from weasyprint import CSS, HTML; "
        "HTML(sys.argv[1]).write_pdf(sys.argv[2], stylesheets=[CSS(string='@page { margin: 0; }')])"
    )
    run_command(
        "[SUMMARY] Generating PDF",
        [sys.executable, "-c", code, html_path, pdf_path],
        EXIT_REPORT,
    )
    if not pdf_path.is_file():
        raise StandaloneError("PDF generation did not create acs_summary.pdf.", EXIT_REPORT)


def lexical_absolute(path):
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def paths_overlap(first, second):
    return first == second or first in second.parents or second in first.parents


def validate_output_target(target, roots, direct_inputs=()):
    target = lexical_absolute(target)
    if target.is_symlink():
        raise StandaloneError(f"Refusing to use a symlink output path: {target}", EXIT_OUTPUT)

    resolved_target = target.resolve(strict=False)
    results_root = roots.get("results")
    results_path = Path(results_root).resolve() if results_root else None
    default_output = (
        (results_path / "acs_summary").resolve(strict=False)
        if results_path else None
    )
    for root_name, root_path in roots.items():
        resolved_root = Path(root_path).resolve(strict=False)
        if not paths_overlap(resolved_target, resolved_root):
            continue
        if root_name == "results" and resolved_target == default_output:
            continue
        allowed_note = (
            f" Only '{default_output}' may be inside results."
            if root_name == "results"
            else " Input and output paths must be separate."
        )
        raise StandaloneError(
            f"Output '{target}' overlaps the effective {root_name} input root "
            f"'{resolved_root}'.{allowed_note}",
            EXIT_OUTPUT,
        )

    for input_path in direct_inputs:
        resolved_input = Path(input_path).resolve()
        if paths_overlap(resolved_target, resolved_input):
            raise StandaloneError(
                f"Output '{target}' overlaps direct input log '{resolved_input}'. "
                "Input and output paths must be separate.",
                EXIT_OUTPUT,
            )

    if target.exists():
        raise StandaloneError(
            f"Output '{target}' already exists. Delete or move the stale output, "
            "or choose a different --output path.",
            EXIT_OUTPUT,
        )


def check_output_readiness(target):
    target = lexical_absolute(target)
    ancestor = target.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if not ancestor.is_dir() or ancestor.is_symlink():
        raise StandaloneError(
            f"Output parent is not a usable directory: {ancestor}", EXIT_OUTPUT
        )

    try:
        free_bytes = shutil.disk_usage(ancestor).free
    except OSError as error:
        raise StandaloneError(
            f"Cannot inspect free space for output parent '{ancestor}': {error}", EXIT_OUTPUT
        ) from error
    if free_bytes < MINIMUM_OUTPUT_FREE_BYTES:
        raise StandaloneError(
            f"Output filesystem has less than {MINIMUM_OUTPUT_FREE_BYTES // (1024 * 1024)} MiB "
            f"free at '{ancestor}'.",
            EXIT_OUTPUT,
        )

    probe = None
    try:
        probe = Path(tempfile.mkdtemp(prefix=".standalone-write-test-", dir=ancestor))
        (probe / "write-test").write_text("ok", encoding="ascii")
    except OSError as error:
        raise StandaloneError(
            f"Output parent is not writable: {ancestor}: {error}", EXIT_OUTPUT
        ) from error
    finally:
        if probe:
            shutil.rmtree(probe, ignore_errors=True)


def prepare_output(output_path, roots, direct_inputs=()):
    target = lexical_absolute(output_path)
    validate_output_target(target, roots, direct_inputs)
    check_output_readiness(target)
    stage = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    except OSError as error:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)
        raise StandaloneError(f"Cannot prepare output '{target}': {error}", EXIT_OUTPUT) from error
    return target, stage


def copy_run_configs(stage, args):
    config_sources = []
    if args.acs_config:
        config_sources.append(
            (Path(args.acs_config), "acs_config_dt.txt" if args.mode == "DT" else "acs_config.txt")
        )
    if args.system_config:
        config_sources.append(
            (
                Path(args.system_config),
                "system_config_dt.txt" if args.mode == "DT" else "system_config.txt",
            )
        )
    if not config_sources:
        return

    config_dir = stage / "config"
    try:
        config_dir.mkdir()
        for source, output_name in config_sources:
            shutil.copy2(source, config_dir / output_name)
    except OSError as error:
        raise StandaloneError(f"Cannot copy current run configuration: {error}", EXIT_OUTPUT) from error


def publish_output(target, stage, roots, direct_inputs=()):
    try:
        validate_output_target(target, roots, direct_inputs)
        stage.replace(target)
    except OSError as error:
        raise StandaloneError(f"Cannot publish output '{target}': {error}", EXIT_OUTPUT) from error


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run selected SystemReady log parser suites without installed /usr/bin or /mnt state."
    )
    parser.add_argument("--standalone", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--mode",
        choices=["DT", "SR"],
        help=f"Parser mode (default: {DEFAULT_MODE})",
    )
    parser.add_argument(
        "--input-log",
        action="append",
        nargs="+",
        default=[],
        dest="input_logs",
        metavar="[NAME=]PATH",
        help=(
            "ACS results directory or direct suite log file; repeat files or provide "
            "multiple paths in registry input order"
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Output directory; defaults to <input-directory>/acs_summary and is "
            "required for direct log files"
        ),
    )
    parser.add_argument("--suite", "--suites", action="append", nargs="+", dest="suites",
                        help="Selected suite names; repeat or use comma-separated values")
    parser.add_argument("--acs-config", "--acs_config", dest="acs_config")
    parser.add_argument("--system-config", "--system_config", dest="system_config")
    parser.add_argument("--waiver", "--waiver-json", "--waiver_json", dest="waiver")
    parser.add_argument("--test-category", help="Override the bundled mode-specific test category JSON")
    parser.add_argument("--outputs", help="Comma-separated stages: json,html,summary,pdf")
    parser.add_argument("--schema", action="store_true", help="Validate generated raw suite JSON files")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Validate registry, dependencies, inputs, and output readiness, then exit",
    )
    parser.add_argument("--list-suites", action="store_true", help="List suites and exit")
    parser.add_argument(
        "--version",
        action="version",
        version=f"SystemReady ACS Log Parser {get_log_parser_version()}",
        help="Print the complete log parser release version and exit",
    )
    return parser


def apply_default_mode(args):
    if args.mode:
        return False

    args.mode = DEFAULT_MODE
    print(
        f"INFO: --mode was not provided; standalone parser will run in "
        f"{DEFAULT_MODE} mode by default."
    )
    return True


def validate_waiver_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            waiver_data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise StandaloneError(
            f"Waiver file is not valid JSON: {path}: {error}", EXIT_INPUT
        ) from error

    suites = waiver_data.get("Suites") if isinstance(waiver_data, dict) else None
    if not isinstance(suites, list):
        raise StandaloneError(
            "Waiver JSON must be an object containing a 'Suites' array: "
            f"{path}",
            EXIT_INPUT,
        )


def validate_cli_paths(args):
    missing = [name for name in ("suites", "input_logs") if not getattr(args, name)]
    if missing:
        raise StandaloneError(
            "Standalone mode requires --suite/--suites and --input-log.",
            EXIT_INPUT,
        )

    supplied_inputs = flatten_values(args.input_logs)
    directory_inputs = []
    for value in supplied_inputs:
        if "=" in value:
            continue
        path = Path(value).expanduser().resolve()
        if path.is_dir():
            directory_inputs.append(path)

    if directory_inputs:
        if len(supplied_inputs) != 1:
            raise StandaloneError(
                "An ACS results directory must be the only --input-log value.",
                EXIT_INPUT,
            )
        results = directory_inputs[0]
        args.results = str(results)
        args.input_logs = []
    else:
        results = None
        args.results = None

    if not results and not args.output:
        raise StandaloneError(
            "--output is required when --input-log contains direct log files.",
            EXIT_INPUT,
        )

    args.output = str(
        lexical_absolute(args.output) if args.output else results / "acs_summary"
    )

    for label, value in (
        ("ACS config", args.acs_config),
        ("system config", args.system_config),
        ("waiver", args.waiver),
    ):
        if value and not Path(value).expanduser().is_file():
            raise StandaloneError(f"{label} file does not exist: {value}", EXIT_INPUT)
    if args.acs_config:
        args.acs_config = str(Path(args.acs_config).expanduser().resolve())
    if args.system_config:
        args.system_config = str(Path(args.system_config).expanduser().resolve())
    if args.waiver:
        args.waiver = str(Path(args.waiver).expanduser().resolve())
        validate_waiver_json(args.waiver)


def validate_mode_configs(args):
    if args.acs_config:
        band = ""
        try:
            with open(args.acs_config, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    key, separator, value = line.partition(":")
                    if separator and key.strip().lower() == "band":
                        band = value.strip()
                        break
        except OSError as error:
            raise StandaloneError(f"Cannot read ACS config '{args.acs_config}': {error}", EXIT_INPUT) from error
        is_dt_band = "devicetree" in band.lower()
        if band and args.mode == "DT" and not is_dt_band:
            raise StandaloneError(
                f"Selected DT mode conflicts with ACS config Band '{band}'.", EXIT_INPUT
            )
        if band and args.mode == "SR" and is_dt_band:
            raise StandaloneError(
                f"Selected SR mode conflicts with ACS config Band '{band}'.", EXIT_INPUT
            )

    expected_suffix = "_dt.txt" if args.mode == "DT" else ".txt"
    for label, value in (("ACS", args.acs_config), ("system", args.system_config)):
        if not value:
            continue
        name = Path(value).name.lower()
        looks_dt = name.endswith("_dt.txt")
        if args.mode == "DT" and not looks_dt:
            print(f"WARNING: {label} config '{Path(value).name}' does not use the expected {expected_suffix} name.")
        elif args.mode == "SR" and looks_dt:
            print(f"WARNING: {label} config '{Path(value).name}' looks like a DT-mode config.")


def validate_python_version():
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(item) for item in MINIMUM_PYTHON)
        current = ".".join(str(item) for item in sys.version_info[:3])
        raise StandaloneError(
            f"Python {required} or newer is required; current interpreter is {current}.",
            EXIT_DEPENDENCY,
        )


def handle_termination(_signum, _frame):
    raise KeyboardInterrupt


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    validate_python_version()
    signal.signal(signal.SIGTERM, handle_termination)
    _, standalone = load_registry_data(DEFAULT_REGISTRY)
    parser = build_parser()
    args = parser.parse_args()
    registry = load_registry()

    if args.list_suites:
        print("\n".join(list_suite_names(registry)))
        return 0

    apply_default_mode(args)
    validate_cli_paths(args)
    validate_mode_configs(args)
    validate_registry(registry, standalone)

    requested = split_values(args.suites)
    normalized = []
    for name in requested:
        canonical = normalize_suite_name(name, registry)
        if not canonical:
            raise StandaloneError(f"Unsupported suite '{name}'. Use --list-suites.", EXIT_INPUT)
        normalized.append(canonical)
    selected = expand_selected_suites(normalized, registry)
    if not selected:
        raise StandaloneError("No executable suites were selected.", EXIT_INPUT)

    execution_map = standalone["suite_execution"]
    direct_inputs = {}
    if flatten_values(args.input_logs):
        if len(selected) != 1:
            raise StandaloneError(
                "Direct --input-log values require exactly one executable suite. "
                "Run each suite separately or pass one ACS results directory to "
                "--input-log for a multi-suite run.",
                EXIT_INPUT,
            )
        direct_inputs = parse_direct_inputs(
            args.input_logs,
            selected[0],
            execution_map[selected[0]],
        )

    for canonical in selected:
        if not suite_supports_mode(canonical, args.mode, registry):
            raise StandaloneError(
                f"{canonical} is not available in {args.mode} mode.", EXIT_INPUT
            )

    outputs = parse_outputs(args.outputs, standalone.get("default_outputs", []))
    test_category = Path(args.test_category).expanduser().resolve() if args.test_category else (
        BASE_DIR / ("test_categoryDT.json" if args.mode == "DT" else "test_category.json")
    )
    if not test_category.is_file():
        raise StandaloneError(f"Test category file does not exist: {test_category}", EXIT_INPUT)

    roots = build_input_roots(Path(args.results) if args.results else None)
    direct_paths = [item.path for item in direct_inputs.values()]
    validate_output_target(Path(args.output), roots, direct_paths)
    validate_support_files(outputs, args.schema, args.waiver)

    modules = []
    for canonical in selected:
        modules.extend(execution_map[canonical].get("json_dependencies", []))
    dependency_groups = standalone.get("dependency_modules", {})
    if "html" in outputs:
        modules.extend(dependency_groups.get("html", []))
    if "summary" in outputs:
        modules.extend(dependency_groups.get("summary", []))
    if args.schema:
        modules.extend(dependency_groups.get("schema", []))
    if "pdf" in outputs:
        modules.extend(dependency_groups.get("pdf", []))

    check_dependencies(modules)

    print("Standalone SystemReady log parser")
    print(f"  Mode           : {args.mode}")
    print(f"  Input directory: {args.results or 'not provided (direct log mode)'}")
    for input_name, item in direct_inputs.items():
        print(f"  Direct input   : {input_name}={item.path}")
    print(f"  Output         : {args.output}")
    print(f"  Selected suites: {', '.join(selected)}")
    print(f"  Output stages  : {', '.join(outputs)}")
    print(f"  Test category  : {test_category}")

    if args.doctor:
        for canonical in selected:
            resolved = resolve_suite_inputs(
                canonical,
                execution_map[canonical],
                roots,
                direct_inputs,
            )
            if execution_map[canonical].get("handler") == "os_tests" and args.mode == "DT":
                os_logs = resolved["os_logs"].path
                if not any(path.is_file() for path in os_logs.glob("linux*/ethtool_test.log")):
                    raise StandaloneError(
                        f"{canonical}: no linux*/ethtool_test.log inputs found under {os_logs}",
                        EXIT_INPUT,
                    )
            print(f"  {canonical:<28} READY")
        check_output_readiness(Path(args.output))
        print("  Output destination           READY")
        print("Standalone preflight result: PASS")
        return 0

    target, stage = prepare_output(Path(args.output), roots, direct_paths)
    try:
        json_dir = stage / "acs_jsons"
        html_dir = stage / "html_detailed_summaries"
        json_dir.mkdir(parents=True)
        if "html" in outputs:
            html_dir.mkdir(parents=True)
        copy_run_configs(stage, args)

        results = []
        missing_suites = []
        not_runnable_suites = []
        for canonical in selected:
            suite = get_suite(canonical, registry)
            try:
                result = run_suite(
                    canonical,
                    suite,
                    execution_map[canonical],
                    roots,
                    args.mode,
                    json_dir,
                    direct_inputs,
                )
            except MissingSuiteInputError as error:
                if direct_inputs or "summary" not in outputs:
                    raise
                missing_suites.append(canonical)
                print(f"WARNING: {error}", file=sys.stderr)
                continue
            except SuiteNotRunError as error:
                if "summary" not in outputs:
                    raise
                not_runnable_suites.append(canonical)
                print(f"WARNING: {error}", file=sys.stderr)
                continue
            for json_file in result.json_files:
                apply_waiver(canonical, suite, json_file, args.waiver, test_category)
            results.append(result)

        raw_jsons = [path for result in results for path in result.json_files]
        if raw_jsons:
            run_command(
                "[METADATA] Enriching raw suite JSON files",
                [
                    sys.executable,
                    BASE_DIR / "enrich_suite_json.py",
                    "--registry", DEFAULT_REGISTRY,
                    "--test-category", test_category,
                    *raw_jsons,
                ],
                EXIT_PARSE,
            )
        else:
            print("[METADATA] Skipped: no raw suite JSON files were generated.")

        if args.schema:
            if raw_jsons:
                run_command(
                    "[SCHEMA] Validating raw suite JSON files",
                    [
                        sys.executable,
                        SCHEMA_VALIDATOR,
                        "raw",
                        "--registry", DEFAULT_REGISTRY,
                        *raw_jsons,
                    ],
                    EXIT_SCHEMA,
                )
            else:
                print("[SCHEMA] Skipped: no raw suite JSON files were generated.")

        if "html" in outputs:
            render_reports(results, html_dir)

        if "summary" in outputs:
            acs_info = generate_acs_info(standalone, roots, args, json_dir)
            merged = json_dir / "merged_results.json"
            merge_results(args.mode, selected, test_category, [acs_info, *raw_jsons], merged)
            combined_html = generate_combined_summary(
                results, roots, args, html_dir, merged, acs_info
            )
            if "pdf" in outputs:
                generate_pdf(combined_html, stage / "acs_summary.pdf")

        publish_output(target, stage, roots, direct_paths)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    print("")
    print("Standalone run result: PASS")
    if missing_suites:
        print(f"Suites without collected logs: {', '.join(missing_suites)}")
    if not_runnable_suites:
        print(f"Suites reported as Not Run: {', '.join(not_runnable_suites)}")
    print(f"Output: {target}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StandaloneError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(error.exit_code)
    except KeyboardInterrupt:
        print("ERROR: Standalone run interrupted; staged output was removed.", file=sys.stderr)
        sys.exit(130)
