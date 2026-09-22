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

"""Run the optional Doctor checks and save their findings for review.

This file selects checks, checks prerequisites, runs commands with time limits,
and writes JSON, text and HTML reports in a new output folder. It also checks
that the portable parser package contains the same files as the checkout.
Doctor reports problems; it never repairs parser code or supplied results.
Importing this module only makes its helpers available; it does not run checks.
"""

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import shlex
import signal
import subprocess
import sys
import tarfile
import tempfile
import traceback

BASE_DIR = Path(__file__).resolve().parents[1]
# Each entry pairs a user-facing check group with the module that runs it.
GROUPS = (("policy", "doctor_checks.merge"), ("package", "doctor_checks.core"),
          ("native", "doctor_checks.probes"), ("merge", "doctor_checks.merge"),
          ("raw", "doctor_checks.probes"), ("reports", "doctor_checks.artifacts"))
FINDING_GROUP_TITLES = {
    "NATIVE_RAW_SCHEMA": "Generated raw JSON does not match its registered schema",
    "MERGE_OVERALL_POLICY": "Overall SRS compliance does not match the requirement policy",
    "MERGE_INCOMPLETE_NOT_GREEN": "Empty or incomplete results must not become Compliant",
    "MERGE_FAILURE_COUNT": "Merged failure counts do not match explicit test outcomes",
    "MERGE_INVALID_INPUT_SAFETY": "Invalid result data must not become Compliant",
    "ARTIFACT.SCHEMA": "Report JSON files do not match their registered schemas",
    "ARTIFACT.PARITY": "Raw and displayed result identities do not agree",
}


# Read evidence and record each check separately from the ACS test results.

def load_json(path):
    """Read JSON without silently accepting duplicate keys or invalid numbers."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + repr(key))
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Non-finite JSON number: " + value)

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            return constant(value)
        return result

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=constant, parse_float=number)


@dataclass
class Finding:
    """Store one Doctor check: what was expected, what happened and the evidence."""

    check_id: str
    status: str
    issue: str
    expected: str
    actual: str
    mode: str = ""
    suite: str = ""
    evidence: list = field(default_factory=list)

    def __post_init__(self):
        if self.status not in {"PASS", "FAIL", "BLOCKED", "WARN"}:
            raise ValueError("Invalid doctor status: " + self.status)

    def to_dict(self):
        return asdict(self)


class Context:
    """Share run settings and keep generated evidence in one new output folder."""

    def __init__(self, parser_dir, output_dir, modes=("DT", "SR"), timeout=60,
                 report_inputs=()):
        self.parser_dir = Path(parser_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.modes = tuple(modes)
        self.timeout = timeout
        self.report_inputs = tuple(report_inputs)
        self.findings = []
        self.python = sys.executable

    def add(self, check_id, status, issue, expected, actual, mode="", suite="",
            evidence=()):
        """Save a finding without changing the result being checked."""
        finding = Finding(check_id, status, str(issue), str(expected), str(actual),
                          mode, suite, [str(path) for path in evidence])
        self.findings.append(finding)
        return finding

    def case_dir(self, name):
        """Give a scenario its own evidence folder without allowing path escapes."""
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Doctor case directory must be relative")
        directory = self.output_dir / "evidence" / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def run(self, command, directory, name="command", timeout=None, cwd=None,
            env=None):
        """Save a command and its output so the check can be repeated later."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        command = [str(item) for item in command]
        environment = os.environ.copy()
        # Put caches in the evidence folder and use the same Python environment
        # for helper commands. Checks must not leave cache files in the source.
        environment.update({"PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg",
                            "MPLCONFIGDIR": str(directory / "mpl-cache"),
                            "PATH": str(Path(self.python).parent) + os.pathsep
                            + environment.get("PATH", "")})
        if env:
            environment.update(env)
        working = str(cwd or self.parser_dir)
        (directory / (name + ".command.json")).write_text(
            json.dumps({"argv": command, "cwd": working,
                        "command": shlex.join(command)}, indent=2) + "\n",
            encoding="utf-8")
        log = directory / (name + ".log")
        try:
            with log.open("w", encoding="utf-8") as handle:
                process = subprocess.Popen(command, cwd=working, env=environment,
                                           stdout=handle, stderr=subprocess.STDOUT,
                                           start_new_session=(os.name == "posix"))
                try:
                    process.wait(timeout=timeout or self.timeout)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    # Stop child processes too, so a timed-out check cannot
                    # keep writing output while later checks are running.
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()
                    raise
            return subprocess.CompletedProcess(command, process.returncode,
                                               log.read_text(encoding="utf-8", errors="replace"))
        except subprocess.TimeoutExpired as error:
            with log.open("a", encoding="utf-8") as handle:
                handle.write("\nDOCTOR: command timed out; check is incomplete.\n")
            raise RuntimeError("Command timed out; see " + str(log)) from error


# Check the package a partner would extract, not just files in this checkout.

def verify_checksum(archive):
    """Check both the archive's recorded filename and its SHA-256 checksum."""
    fields = archive.with_name(archive.name + ".sha256").read_text(encoding="utf-8").split()
    wanted = hashlib.sha256(archive.read_bytes()).hexdigest()
    if len(fields) != 2 or fields[0] != wanted or fields[1] != archive.name:
        raise ValueError("Archive checksum or recorded archive name does not match")
    return wanted


def extract_package(archive, destination):
    """Reject unsafe archive paths and links before writing any package files."""
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts or
                    path.parts[0] != "systemready-log-parser" or
                    not (member.isfile() or member.isdir()) or str(path) in names):
                raise ValueError("Unsafe or duplicate package member: " + member.name)
            names.add(str(path))
        if not members:
            raise ValueError("Archive contains no files")
        destination.mkdir(exist_ok=False)
        # Every entry was checked above. This also protects Python versions
        # whose tarfile module does not filter unsafe entries by default.
        bundle.extractall(destination, members=members)
    return destination / "systemready-log-parser" / "common" / "log_parser"


def package_differences(source, packaged):
    """List missing, extra or changed runtime files in the extracted package."""
    expected = {path.relative_to(source).as_posix(): path for path in source.rglob("*")
                if path.is_file() and not any(part in {"tests", "__pycache__"}
                for part in path.relative_to(source).parts) and path.suffix != ".pyc"}
    actual = {path.relative_to(packaged).as_posix(): path for path in packaged.rglob("*") if path.is_file()}
    missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
    changed = sorted(name for name in expected.keys() & actual.keys()
                     if expected[name].read_bytes() != actual[name].read_bytes())
    return {key: value for key, value in (("missing", missing), ("extra", extra), ("changed", changed)) if value}


def run_package(ctx):
    """Build and verify a package, then try its command-line entry points."""
    ctx.package_checked = True
    ctx.portable_parser = None
    directory = ctx.case_dir("package")
    archive = directory / "systemready-log-parser-standalone.tar.gz"
    build = ctx.run(["bash", ctx.parser_dir / "package_standalone.sh", archive],
                    directory, "build-package", cwd=directory)
    if build.returncode:
        ctx.add("PACKAGE_BUILD", "FAIL", "Standalone archive cannot be created from this distribution",
                "Public package script creates an archive and checksum",
                "Exit %d; see build-package.log" % build.returncode,
                evidence=(directory / "build-package.log",))
        return
    try:
        digest = verify_checksum(archive)
        packaged = extract_package(archive, directory / "extracted")
        changes = package_differences(ctx.parser_dir, packaged)
    except (OSError, ValueError, tarfile.TarError) as error:
        ctx.add("PACKAGE_INTEGRITY", "FAIL", "Standalone archive integrity cannot be verified",
                "Matching SHA-256, safe extraction, complete runtime", str(error), evidence=(archive,))
        return
    ctx.add("PACKAGE_INTEGRITY", "FAIL" if changes else "PASS",
            "Archive preserves the complete runtime and Doctor fixtures",
            "Identical runtime files after extraction outside the repository",
            changes or "SHA-256 " + digest + "; all files match", evidence=(archive, packaged))
    if changes:
        return
    # Do not let imports from the checkout hide missing files in the package.
    ready = True
    for name, command in (
        ("help", ["bash", packaged / "main_log_parser.sh", "--standalone", "--help"]),
        ("suites", ["bash", packaged / "main_log_parser.sh", "--standalone", "--list-suites"]),
        ("doctor", [ctx.python, "-B", packaged / "doctor.py", "--help"]),
    ):
        result = ctx.run(command, directory, "portable-" + name, cwd=directory,
                         env={"PYTHONPATH": "", "PYTHONNOUSERSITE": "1"})
        ok = result.returncode == 0 and bool(result.stdout.strip())
        ready &= ok
        ctx.add("PACKAGE_CLI", "PASS" if ok else "FAIL",
                "Extracted " + name + " entry point runs without checkout imports",
                "Exit 0 and nonempty output", "Exit " + str(result.returncode),
                evidence=(directory / ("portable-" + name + ".log"),))
    if ready:
        ctx.portable_parser = packaged
    ctx.add("PACKAGE_ENVIRONMENT", "WARN", "Package checks use the recorded Python environment",
            "Separate clean-environment CI jobs verify dependency installation and supported Python versions",
            "No packages are installed or upgraded by Doctor; native probes use " + ctx.python)


# Register optional flags, choose checks and turn their findings into reports.

def add_arguments(parser):
    """Add Doctor options to a CLI; registering them does not run Doctor."""
    parser.add_argument("--health", action="store_true",
                        help="With --doctor: run isolated DT/SR correctness probes")
    parser.add_argument("--doctor-output", metavar="NEW_DIRECTORY",
                        help="New directory for doctor results and reproduction inputs")
    parser.add_argument("--doctor-report", action="append", default=[], metavar="MODE=PATH",
                        help="Also check an existing DT or SR report package, read-only; repeatable")
    parser.add_argument("--doctor-timeout", type=int, default=60, metavar="SECONDS",
                        help="Timeout per external check (default 60; range 1-300)")
    parser.add_argument("--doctor-checks", metavar="GROUPS",
                        help="Comma-separated health groups: policy,package,native,merge,raw,reports (default all)")
    parser.add_argument("--doctor-visual", action="store_true",
                        help="Also run optional Chromium and PDF export smoke checks")
    parser.add_argument("--doctor-browser", metavar="EXECUTABLE",
                        help="Chromium executable for --doctor-visual (otherwise detected on PATH)")


def file_inventory(directory):
    """Hash parser code and metadata so later checks can detect source changes."""
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path.suffix in {".py", ".sh", ".json", ".txt"}
            and not any(part in {"__pycache__", ".git"} for part in path.parts)}


def registry_issues(data, parser_dir):
    """Find duplicate suite names, conflicting aliases and missing suite files."""
    suites = data.get("suites")
    if not isinstance(suites, list) or not suites:
        return ["suite_registry.json must contain a non-empty suites list"]
    issues, aliases, names, keys = [], {}, set(), set()
    for suite in suites:
        if not isinstance(suite, dict) or not isinstance(suite.get("canonical"), str):
            issues.append("Every suite must have a string canonical name")
            continue
        name = suite["canonical"]
        if name in names:
            issues.append("Duplicate canonical suite: " + name)
        names.add(name)
        for alias in [name] + suite.get("aliases", []):
            token = re.sub(r"[-_\s]+", "-", alias.strip().upper())
            if token in aliases and aliases[token] != name:
                issues.append("Alias %s resolves to both %s and %s" % (alias, aliases[token], name))
            aliases[token] = name
        if suite.get("requirements"):
            key = suite.get("requirement_key")
            if not key or key in keys:
                issues.append("Missing or duplicate requirement key for " + name)
            keys.add(key)
        for mode, requirement in suite.get("requirements", {}).items():
            if mode not in suite.get("modes", []) or requirement not in {"M", "R", "CM", "EM"}:
                issues.append("Invalid requirement/mode for " + name + ": " + mode)
        for key in ("logs_to_json", "json_to_html", "schema"):
            if suite.get(key):
                relative = suite[key].split("#", 1)[0]
                path = (parser_dir / relative).resolve()
                if parser_dir not in path.parents or not path.is_file():
                    issues.append(name + ": missing or out-of-package " + key + " " + relative)
        if suite.get("schema"):
            source, _, fragment = suite["schema"].partition("#")
            try:
                value = load_json(parser_dir / source)
                for token in fragment.lstrip("/").split("/") if fragment else []:
                    value = value[token.replace("~1", "/").replace("~0", "~")]
            except (OSError, ValueError, KeyError, TypeError):
                issues.append(name + ": schema fragment cannot be resolved: " + suite["schema"])
    for suite in suites:
        if isinstance(suite, dict):
            for included in suite.get("included_suites", []):
                if included not in names:
                    issues.append(suite["canonical"] + ": unknown included suite " + included)
    return issues


def check_repository(ctx):
    """Check syntax, suite settings and dependencies before starting scenarios."""
    directory = ctx.case_dir("repository")
    syntax_errors = []
    sources = sorted(path for path in ctx.parser_dir.rglob("*.py")
                     if "__pycache__" not in path.parts)
    for source in sources:
        try:
            ast.parse(source.read_bytes(), filename=str(source))
        except (SyntaxError, ValueError, OSError) as error:
            syntax_errors.append(str(error))
    for index, source in enumerate(sorted(ctx.parser_dir.rglob("*.sh"))):
        # Syntax checks read the shell scripts; they do not execute their tests.
        result = ctx.run(["bash", "-n", source], directory, "shell-%d" % index)
        if result.returncode:
            syntax_errors.append(str(source) + ": " + result.stdout.strip())
    ctx.add("REPO_SYNTAX", "FAIL" if syntax_errors or not sources else "PASS",
            "Parser Python and shell files must be syntactically valid",
            "All files parse; no commands in shell files are executed",
            "\n".join(syntax_errors) or "%d Python files checked, plus shell syntax" % len(sources),
            evidence=[directory])
    try:
        registry = load_json(ctx.parser_dir / "suite_registry.json")
        problems = registry_issues(registry, ctx.parser_dir)
        from standalone_runner import validate_registry
        validate_registry(registry["suites"], registry["standalone"],
                          ctx.parser_dir / "suite_registry.json")
        ctx.add("REPO_REGISTRY", "FAIL" if problems else "PASS",
                "Registry must connect each suite to its parser, schema and execution inputs",
                "Unique aliases/requirements and complete executable registry",
                "\n".join(problems) or "Registry and schema fragments resolve",
                evidence=[ctx.parser_dir / "suite_registry.json"])
    except Exception as error:  # A broken registry must still produce a doctor report.
        ctx.add("REPO_REGISTRY", "FAIL", "Suite registry cannot be used",
                "Valid complete suite registry", str(error))
        registry = {}
    metadata_errors = []
    for source in sorted(ctx.parser_dir.glob("*.json")):
        try:
            load_json(source)
        except (OSError, ValueError) as error:
            metadata_errors.append(str(source) + ": " + str(error))
    ctx.add("REPO_JSON", "FAIL" if metadata_errors else "PASS",
            "Bundled parser metadata must be readable JSON", "No malformed JSON",
            "\n".join(metadata_errors) or "Bundled JSON files decode successfully")
    support = ("requirements.txt", "test_categoryDT.json", "test_category.json",
               "validate.py", "report_ui.py", "generate_acs_summary.py",
               "merge_jsons.py", "apply_waivers.py")
    missing = [name for name in support if not (ctx.parser_dir / name).is_file()]
    ctx.add("REPO_SUPPORT_FILES", "FAIL" if missing else "PASS",
            "Shared parser files and mode metadata must be included in the checkout/package",
            "All shared support files available", ", ".join(missing) or "All available")
    modules = {"chardet", "jinja2", "matplotlib", "jsonschema"}
    for entry in registry.get("standalone", {}).get("suite_execution", {}).values():
        modules.update(entry.get("json_dependencies", []))
    available = {}
    for module in sorted(modules):
        result = ctx.run([ctx.python, "-B", "-c",
                          "import importlib; importlib.import_module(" + repr(module) + ")"],
                         directory, "dependency-" + module)
        available[module] = result.returncode == 0
        ctx.add("DEPENDENCY", "PASS" if result.returncode == 0 else "BLOCKED",
                "Python dependency must import: " + module, "Import succeeds in " + ctx.python,
                "Import succeeded" if result.returncode == 0 else
                (result.stdout.strip().splitlines()[-1] if result.stdout.strip() else
                 "Import failed with exit " + str(result.returncode)) +
                ". Install the parser requirements in this Python environment: " +
                ctx.python + " -m pip install -r " + str(ctx.parser_dir / "requirements.txt"),
                evidence=[directory / ("dependency-" + module + ".log")])
    # A missing renderer must not hide policy checks, packaging or JSON probes.
    # Each group reports its own remaining file/capability failures.
    return {"policy": True, "package": True, "merge": True,
            "native": all(available.get(name, False) for name in ("chardet", "jsonschema")),
            "raw": all(available.values()), "reports": available.get("jsonschema", False),
            "visual": all(available.values())}


def selected_groups(args):
    """Select requested groups and include package checks when they are needed."""
    names = [name for name, _ in GROUPS]
    value = getattr(args, "doctor_checks", None)
    chosen = set(names) if value is None else {part.strip() for part in value.split(",")}
    if not chosen or not chosen <= set(names):
        raise ValueError("--doctor-checks requires a nonempty selection from " + ",".join(names))
    visual = getattr(args, "doctor_visual", False)
    if getattr(args, "doctor_browser", None) and not visual:
        raise ValueError("--doctor-browser requires --doctor-visual")
    if "native" in chosen or visual:
        chosen.add("package")
    groups = [(name, module) for name, module in GROUPS if name in chosen]
    if visual:
        groups.append(("visual", "doctor_checks.artifacts"))
    return groups


def protected_source_root(parser_dir):
    """Find the whole checkout or package that Doctor must not write inside."""
    parser_dir = Path(parser_dir).resolve()
    for parent in (parser_dir, *parser_dir.parents):
        if (parent / ".git").exists():
            return parent
    if (parser_dir.name == "log_parser" and parser_dir.parent.name == "common" and
            (parser_dir.parent.parent / "LICENSE.md").is_file()):
        return parser_dir.parent.parent
    return parser_dir


def verdict(findings):
    """A blocked or empty run is not a pass, even when no check has failed."""
    counts = Counter(finding.status for finding in findings)
    if counts["FAIL"]:
        return "FAIL", 1
    if counts["BLOCKED"] or not counts["PASS"]:
        return "INCOMPLETE", 2
    return "PASS (checked scope)", 0


def render_reports(ctx, metadata):
    """Write all findings to JSON and readable text/HTML views of the same run."""
    # Only health runs load the report builder; ordinary parsing just adds flags.
    from .report import render_html
    status, exit_code = verdict(ctx.findings)
    counts = Counter(finding.status for finding in ctx.findings)
    payload = dict(metadata, verdict=status, exit_code=exit_code, counts=dict(counts),
                   findings=[finding.to_dict() for finding in ctx.findings])
    (ctx.output_dir / "doctor.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = ["# Log parser doctor: " + status, "", "Revision: " + metadata["revision"],
             "", "Counts: " + json.dumps(dict(counts)), "",
             "Synthetic tests are parser-health probes, not hardware certification results.",
             "Recommended suites are checked against the non-blocking overall-compliance contract.",
             "PASS applies only to the recorded checks. BLOCKED is unverified, never passed.", ""]
    lines.append("Counts are assertions, not distinct bugs; one defect can fail multiple scenarios.\n")
    titles = {}
    for item in ctx.findings:
        if item.status == "PASS":
            continue
        label = "%s [%s] %s %s" % (item.status, item.check_id, item.mode, item.suite)
        key = item.status, item.check_id
        title = FINDING_GROUP_TITLES.get(item.check_id, item.issue)
        if key in titles and titles[key] != title:
            # An outer group describes every finding, not whichever file or
            # scenario happened to be reported first. Details retain exact text.
            title = item.check_id.replace("_", " ").replace(".", " ").capitalize()
        titles[key] = title
        lines.extend(["## " + label, "", item.issue, "", "Expected: " + item.expected,
                      "", "Actual: " + item.actual, ""])
        for evidence in item.evidence:
            lines.append("Evidence: " + evidence)
    (ctx.output_dir / "doctor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    document = render_html(ctx.findings, metadata, ctx.output_dir, status, counts, titles)
    (ctx.output_dir / "index.html").write_text(document, encoding="utf-8")
    return status, exit_code, counts


def run_health(args, parser_dir=BASE_DIR):
    """Run the explicitly requested health checks without changing their inputs."""
    if not 1 <= args.doctor_timeout <= 300:
        raise ValueError("--doctor-timeout must be between 1 and 300 seconds")
    groups = selected_groups(args)
    inputs = []
    modes = (args.mode,) if args.mode else ("DT", "SR")
    for value in args.doctor_report:
        mode, separator, raw_path = value.partition("=")
        if separator != "=" or mode not in {"DT", "SR"} or not raw_path:
            raise ValueError("--doctor-report requires DT=/path or SR=/path")
        if mode not in modes:
            raise ValueError("Report mode %s conflicts with --mode %s" % (mode, args.mode))
        inputs.append((mode, Path(raw_path).expanduser().resolve()))
    if args.doctor_output:
        # Never overwrite a previous run, supplied report or source directory.
        output = Path(args.doctor_output).expanduser().resolve()
        for protected in [protected_source_root(parser_dir)] + [path for _, path in inputs]:
            if output == protected or protected in output.parents:
                raise ValueError("Doctor output must be outside parser sources and supplied reports")
        output.mkdir(parents=True, exist_ok=False)
    else:
        temporary_parent = Path(tempfile.gettempdir()).resolve()
        for protected in [protected_source_root(parser_dir)] + [path for _, path in inputs]:
            if temporary_parent == protected or protected in temporary_parent.parents:
                raise ValueError("Temporary directory is inside parser sources or a supplied report; "
                                 "set --doctor-output to a new directory outside both")
        output = Path(tempfile.mkdtemp(prefix="log-parser-health-", dir=temporary_parent))
    ctx = Context(parser_dir, output, modes, args.doctor_timeout, inputs)
    ctx.browser = getattr(args, "doctor_browser", None)
    if any(group == "package" for group, _ in groups):
        # Intent exists even if importing the package-check module later fails.
        ctx.package_checked = True
        ctx.portable_parser = None
    before = file_inventory(ctx.parser_dir)
    directory = ctx.case_dir("repository")
    revision = "Unknown (not a Git checkout); source hashes are recorded"
    worktree = "Not a Git checkout"
    if shutil.which("git"):
        result = ctx.run(["git", "rev-parse", "HEAD"], directory, "revision")
        if result.returncode == 0:
            revision = result.stdout.strip()
            result = ctx.run(["git", "status", "--short", "--branch"], directory, "worktree")
            worktree = result.stdout.strip()
    metadata = {"revision": revision, "parser_dir": str(ctx.parser_dir),
                "worktree_status": worktree,
                "python": ctx.python, "modes": list(modes),
                "check_groups": [group for group, _ in groups],
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "source_sha256": before,
                "scope": "Repository, synthetic raw-log/waiver/merge/HTML checks; supplied reports read-only"}
    print("Log parser doctor — deep health check", flush=True)
    print("Revision: " + revision + "\nModes: " + ", ".join(modes) + "\nEvidence: " + str(output), flush=True)
    try:
        ready = check_repository(ctx)
    except Exception as error:
        ctx.add("REPO_CHECK_ERROR", "BLOCKED", "Repository checks could not finish",
                "Completed prerequisites", str(error), evidence=[directory])
        ready = False
    if not getattr(args, "doctor_visual", False):
        ctx.add("VISUAL_COVERAGE", "WARN", "Browser and PDF export checks were not requested",
                "Use --doctor-visual for optional rendering smoke checks",
                "Static JSON/HTML checks do not verify JavaScript or PDF output")
    omitted = sorted({name for name, _ in GROUPS} - {name for name, _ in groups})
    if omitted:
        ctx.add("SCOPE_LIMIT", "WARN", "Focused health run; other groups were not checked",
                "Omit --doctor-checks for the full default scope", ", ".join(omitted))
    for group, module in groups:
        print("Checking " + group + "...", flush=True)
        previous = len(ctx.findings)
        try:
            group_ready = ready.get(group, False) if isinstance(ready, dict) else ready
            if group_ready:
                getattr(importlib.import_module(module), "run_" + group)(ctx)
            else:
                ctx.add("CHECK_GROUP", "BLOCKED", group + " checks were not executed",
                        "Usable dependencies and repository prerequisites",
                        "Resolve prerequisite errors above, then rerun")
        except (Exception, SystemExit) as error:
            # A broken check must be visible, but should not hide evidence
            # from other independent groups that can still run.
            trace = ctx.case_dir(group) / "doctor-error.log"
            trace.write_text(traceback.format_exc(), encoding="utf-8")
            ctx.add("CHECK_GROUP_ERROR", "BLOCKED", group + " checks did not complete",
                    "Doctor probe executes and evaluates its result", str(error), evidence=[trace])
        if previous == len(ctx.findings):
            ctx.add("ZERO_CHECKS", "BLOCKED", group + " executed no assertions",
                    "At least one explicit check or coverage warning", "No findings returned")
        counts = Counter(item.status for item in ctx.findings[previous:])
        print(group + ": " + str(dict(counts)), flush=True)
    after = file_inventory(ctx.parser_dir)
    # Compare content, not modification times, to catch accidental source edits.
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    ctx.add("SOURCE_UNCHANGED", "FAIL" if changed else "PASS",
            "Health checks must not change parser source or metadata",
            "Identical source hashes before and after checks", ", ".join(changed) or "Unchanged")
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    status, code, counts = render_reports(ctx, metadata)
    grouped = defaultdict(list)
    for item in ctx.findings:
        if item.status in {"FAIL", "BLOCKED"}:
            grouped[(item.status, item.check_id.split(":")[0])].append(item)
    print("\nResult: " + status + " " + str(dict(counts)))
    for (severity, rule), items in grouped.items():
        sample = items[0]
        print("\n%s [%s] (%d assertions): %s" % (severity, rule, len(items), sample.issue))
        print("  Example %s %s: expected %s; actual %s" %
              (sample.mode, sample.suite, sample.expected[:350], sample.actual[:500]))
    print("\nOpen " + str(output / "index.html"))
    print("All checks and evidence: " + str(output / "doctor.json"))
    return code


def main():
    """Allow a manual Doctor run even if the normal parser entry point is broken."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("DT", "SR"))
    add_arguments(parser)
    args = parser.parse_args()
    try:
        return run_health(args)
    except (ValueError, OSError) as error:
        print("Doctor input/output error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
