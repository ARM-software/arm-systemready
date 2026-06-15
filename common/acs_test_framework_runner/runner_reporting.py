from __future__ import annotations

import shutil
import xml.etree.ElementTree as xml_et
from datetime import datetime
from pathlib import Path
from threading import Lock

try:  # Support package imports and direct harness module loading.
    from .runner_checks import (
        TestMeta,
        TestOutcome,
        create_outcome,
        detect_project_root,
        sanitize_name,
        sanitize_xml_text,
    )
except ImportError:  # pragma: no cover - exercised by flat-module harness imports.
    from runner_checks import (
        TestMeta,
        TestOutcome,
        create_outcome,
        detect_project_root,
        sanitize_name,
        sanitize_xml_text,
    )

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = detect_project_root(SCRIPT_DIR)
REPORTS_DIR = PROJECT_ROOT / "common" / "reports"
PLACEHOLDER_XML = REPORTS_DIR / "pytest-placeholder.xml"
LOG_SEPARATOR = "=" * 100
LOG_WRITE_LOCK = Lock()


def append_run_header(
    file_work_dir: Path,
    suite_name: str,
    yaml_file: Path,
    targets: list[str],
) -> None:
    file_work_dir.mkdir(parents=True, exist_ok=True)
    log_path = file_work_dir / "combined.log"

    try:
        yaml_display = yaml_file.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        yaml_display = str(yaml_file)

    lines = [
        "=" * 100,
        f"RUN START: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"YAML: {yaml_display}",
        f"SUITE: {suite_name}",
        f"TARGETS: {', '.join(targets)}",
        "=" * 100,
        "",
    ]

    with LOG_WRITE_LOCK:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
            handle.write("\n")


def build_report_path(group_name: str, yaml_file: Path) -> Path:
    safe_group = sanitize_name(group_name)
    safe_yaml = sanitize_name(yaml_file.stem)
    if safe_group == safe_yaml:
        return REPORTS_DIR / f"{safe_yaml}.xml"
    return REPORTS_DIR / f"{safe_group}__{safe_yaml}.xml"


def create_placeholder_xml(reason: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    testsuite = xml_et.Element("testsuite")
    testsuite.set("name", sanitize_xml_text("pytest"))
    testsuite.set("tests", "0")
    testsuite.set("failures", "0")
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    properties = xml_et.SubElement(testsuite, "properties")

    reason_prop = xml_et.SubElement(properties, "property")
    reason_prop.set("name", "reason")
    reason_prop.set("value", sanitize_xml_text(reason))

    placeholder_prop = xml_et.SubElement(properties, "property")
    placeholder_prop.set("name", "placeholder")
    placeholder_prop.set("value", "true")

    system_out = xml_et.SubElement(testsuite, "system-out")
    system_out.text = sanitize_xml_text(reason)

    xml_et.ElementTree(testsuite).write(
        PLACEHOLDER_XML,
        encoding="utf-8",
        xml_declaration=True,
    )


def remove_placeholder_xml() -> None:
    if PLACEHOLDER_XML.exists():
        PLACEHOLDER_XML.unlink()


def cleanup_old_pytest_xml_reports() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for xml_file in REPORTS_DIR.glob("*.xml"):
        if xml_file.name == "pylint-report.xml":
            continue
        xml_file.unlink(missing_ok=True)

    work_root = REPORTS_DIR / "_work"
    if work_root.exists():
        shutil.rmtree(work_root, ignore_errors=True)


def build_case_log_lines(
    testcase_name: str,
    status: str,
    message: str,
    details: str,
    description: str | None = None,
) -> list[str]:
    normalized_description = ""
    if description is not None:
        normalized_description = " ".join(
            line.strip()
            for line in sanitize_xml_text(description).splitlines()
            if line.strip()
        )

    lines = [
        "=" * 80,
        f"TEST CASE: {testcase_name}",
    ]
    if normalized_description:
        lines.append(f"DESCRIPTION: {normalized_description}")
    lines.extend([
        f"STATUS: {status}",
        f"MESSAGE: {message}",
    ])

    if details:
        lines.extend(["", details.rstrip()])

    return lines


def append_combined_case_log(
    file_work_dir: Path,
    testcase_name: str,
    status: str,
    message: str,
    details: str,
    description: str | None = None,
) -> None:
    file_work_dir.mkdir(parents=True, exist_ok=True)
    log_path = file_work_dir / "combined.log"
    lines = build_case_log_lines(
        testcase_name,
        status,
        message,
        details,
        description=description,
    )

    with LOG_WRITE_LOCK:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines).rstrip())
            handle.write("\n\n")


def write_case_log(
    case_work_dir: Path,
    testcase_name: str,
    status: str,
    message: str,
    details: str,
    description: str | None = None,
) -> None:
    case_work_dir.mkdir(parents=True, exist_ok=True)
    log_path = case_work_dir / "case.log"
    lines = build_case_log_lines(
        testcase_name,
        status,
        message,
        details,
        description=description,
    )

    with LOG_WRITE_LOCK:
        log_path.write_text(
            "\n".join(lines).rstrip() + "\n",
            encoding="utf-8",
        )


def write_junit_xml(
    xml_report: Path,
    suite_name: str,
    yaml_file: Path,
    outcomes: list[TestOutcome],
) -> None:
    tests = len(outcomes)
    failures = sum(
        1
        for item in outcomes
        if not item.passed and not item.error and not item.skipped and not item.warning
    )
    errors = sum(1 for item in outcomes if item.error)
    skipped = sum(1 for item in outcomes if item.skipped)
    # Keep the XML summary property aligned with the console summary, where
    # hardware-gated skips are surfaced as warnings rather than hard failures.
    warnings = sum(1 for item in outcomes if item.skipped or item.warning)
    passed = sum(
        1 for item in outcomes if item.passed and not item.skipped and not item.warning
    )

    testsuite = xml_et.Element("testsuite")
    testsuite.set("name", sanitize_xml_text(suite_name))
    testsuite.set("tests", str(tests))
    testsuite.set("failures", str(failures))
    testsuite.set("errors", str(errors))
    testsuite.set("skipped", str(skipped))

    properties = xml_et.SubElement(testsuite, "properties")

    yaml_prop = xml_et.SubElement(properties, "property")
    yaml_prop.set("name", "yaml_file")
    yaml_prop.set(
        "value",
        sanitize_xml_text(yaml_file.relative_to(PROJECT_ROOT).as_posix()),
    )

    passed_prop = xml_et.SubElement(properties, "property")
    passed_prop.set("name", "passed")
    passed_prop.set("value", sanitize_xml_text(str(passed)))

    warnings_prop = xml_et.SubElement(properties, "property")
    warnings_prop.set("name", "warnings")
    warnings_prop.set("value", sanitize_xml_text(str(warnings)))

    for outcome in outcomes:
        testcase = xml_et.SubElement(testsuite, "testcase")
        testcase.set(
            "classname",
            sanitize_xml_text(sanitize_name(outcome.file_path or suite_name)),
        )
        testcase.set("name", sanitize_xml_text(outcome.testcase_name))
        testcase.set("file", sanitize_xml_text(outcome.file_path))

        if outcome.skipped:
            skipped_node = xml_et.SubElement(testcase, "skipped")
            skipped_node.set("message", sanitize_xml_text(outcome.message))
            skipped_node.text = sanitize_xml_text(outcome.details)
        elif not outcome.passed and outcome.error:
            error_node = xml_et.SubElement(testcase, "error")
            error_node.set("message", sanitize_xml_text(outcome.message))
            error_node.text = sanitize_xml_text(outcome.details)
        elif not outcome.passed:
            failure_node = xml_et.SubElement(testcase, "failure")
            failure_node.set("message", sanitize_xml_text(outcome.message))
            failure_node.text = sanitize_xml_text(outcome.details)

        system_out = xml_et.SubElement(testcase, "system-out")
        body = [
            f"file={outcome.file_path}",
            f"suite={outcome.meta.suite_name}",
            f"phase={outcome.meta.phase}",
            f"type={outcome.meta.test_type}",
            f"warning={outcome.warning}",
            f"message={outcome.message}",
        ]
        if outcome.details:
            body.extend(["details:", outcome.details])

        system_out.text = sanitize_xml_text("\n".join(body))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    xml_et.ElementTree(testsuite).write(
        xml_report,
        encoding="utf-8",
        xml_declaration=True,
    )


def print_group_summary(
    suite_name: str,
    outcomes: list[TestOutcome],
    xml_report: Path,
) -> None:
    total = len(outcomes)
    passed = sum(
        1 for item in outcomes if item.passed and not item.skipped and not item.warning
    )
    failures = sum(
        1
        for item in outcomes
        if not item.passed and not item.error and not item.skipped and not item.warning
    )
    errors = sum(1 for item in outcomes if item.error)
    warnings = sum(1 for item in outcomes if item.skipped or item.warning)

    print(f"\n[INFO] Finished group : {suite_name}")
    print(
        f"[INFO] XML report     : "
        f"{xml_report.relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(f"Total   : {total}")
    print(f"Passed  : {passed}")
    print(f"Failed  : {failures}")
    print(f"Errors  : {errors}")
    print(f"Warnings: {warnings}")

    failed_items = [
        item for item in outcomes
        if not item.passed and not item.skipped and not item.warning
    ]
    if failed_items:
        print("\n[FAILURES]")
        for item in failed_items:
            kind = "ERROR" if item.error else "FAIL"
            print(
                f"  - [{kind}] "
                f"{item.file_path} :: {item.testcase_name} :: {item.message}"
            )

    warning_items = [item for item in outcomes if item.skipped or item.warning]
    if warning_items:
        print("\n[WARNINGS]")
        for item in warning_items:
            label = "[WARNING]" if item.warning else "[HW WARNING]"
            print(
                f"  - {label} "
                f"{item.file_path} :: {item.testcase_name} :: {item.message}"
            )


def build_config_error_outcome(
    yaml_file: Path,
    message: str,
    details: str,
) -> TestOutcome:
    return create_outcome(
        testcase_name="config::load_yaml",
        file_path=yaml_file.relative_to(PROJECT_ROOT).as_posix(),
        passed=False,
        message=sanitize_xml_text(message),
        meta=TestMeta(
            suite_name="config",
            phase="config",
            test_type="config",
        ),
        details=sanitize_xml_text(details),
        error=True,
    )
