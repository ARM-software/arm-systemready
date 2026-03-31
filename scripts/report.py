from __future__ import annotations

import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

RUNNER_FILE = SCRIPT_DIR / "pytest_runner.py"
REPORTS_DIR = PROJECT_ROOT / "reports"
PYLINT_XML = REPORTS_DIR / "pylint-report.xml"
PYLINT_LOG = REPORTS_DIR / "pylint.log"
PYTEST_LOG = REPORTS_DIR / "pytest.log"


def ensure_reports_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_git_command(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_commit_info() -> dict[str, str]:
    info = {
        "commit": "NO_COMMIT_AVAILABLE",
        "branch": "UNKNOWN_BRANCH",
        "status": "UNKNOWN_STATUS",
    }

    code, stdout, _ = run_git_command(["rev-parse", "--is-inside-work-tree"])
    if code != 0 or stdout.lower() != "true":
        info["status"] = "NOT_A_GIT_REPOSITORY"
        return info

    code, stdout, _ = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    if code == 0 and stdout:
        info["branch"] = stdout

    code, stdout, _ = run_git_command(["rev-parse", "HEAD"])
    if code == 0 and stdout:
        info["commit"] = stdout
        info["status"] = "COMMIT_FOUND"
    else:
        info["status"] = "NO_COMMIT_YET"

    return info


def cleanup_old_pytest_xml_reports() -> None:
    ensure_reports_dir()
    for xml_file in REPORTS_DIR.glob("*.xml"):
        if xml_file.name == PYLINT_XML.name:
            continue
        xml_file.unlink(missing_ok=True)


def run_pytest() -> int:
    if not RUNNER_FILE.exists():
        print(f"ERROR: Runner file not found: {RUNNER_FILE}")
        return 1

    cleanup_old_pytest_xml_reports()

    result = subprocess.run(
        [sys.executable, str(RUNNER_FILE)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    with PYTEST_LOG.open("w", encoding="utf-8") as handle:
        handle.write("STDOUT\n")
        handle.write("=" * 80 + "\n")
        handle.write(result.stdout or "")
        handle.write("\n\nSTDERR\n")
        handle.write("=" * 80 + "\n")
        handle.write(result.stderr or "")
        handle.write("\n")

    return result.returncode


def parse_pytest_xml(xml_file: Path) -> dict:
    tree = ET.parse(xml_file)
    root = tree.getroot()

    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")

    total = 0
    failures = 0
    errors = 0
    skipped = 0
    testcases = []
    placeholder_reason = ""

    for suite in suites:
        total += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))

        properties = suite.find("properties")
        if properties is not None:
            for prop in properties.findall("property"):
                if prop.attrib.get("name") == "reason":
                    placeholder_reason = prop.attrib.get("value", "")

        system_out = suite.findtext("system-out", default="").strip()
        if not placeholder_reason and system_out:
            placeholder_reason = system_out

        for testcase in suite.findall("testcase"):
            name = testcase.attrib.get("name", "unknown")
            status = "passed"
            details = ""

            failure_node = testcase.find("failure")
            error_node = testcase.find("error")
            skipped_node = testcase.find("skipped")

            if failure_node is not None:
                status = "failed"
                details = (
                    failure_node.attrib.get("message") or failure_node.text or ""
                ).strip()
            elif error_node is not None:
                status = "error"
                details = (
                    error_node.attrib.get("message") or error_node.text or ""
                ).strip()
            elif skipped_node is not None:
                status = "skipped"
                details = (
                    skipped_node.attrib.get("message") or skipped_node.text or ""
                ).strip()

            testcases.append(
                {
                    "name": name,
                    "status": status,
                    "details": details,
                }
            )

    return {
        "file": xml_file.name,
        "total": total,
        "passed": total - failures - errors - skipped,
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
        "testcases": testcases,
        "placeholder_reason": placeholder_reason,
    }


def print_pytest_summary(results: list[dict], commit_info: dict[str, str]) -> None:
    print("\n========== PYTEST REPORT ==========\n")
    print(f"Branch  : {commit_info['branch']}")
    print(f"Commit  : {commit_info['commit']}")
    print(f"Git     : {commit_info['status']}")

    if not results:
        print("\nWARNING: No XML reports found for pytest.")
        print(f"Pytest log: {PYTEST_LOG.relative_to(PROJECT_ROOT)}")
        print("\n===================================\n")
        return

    total = 0
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    placeholder_notes: list[str] = []
    all_testcases: list[dict[str, str]] = []

    for result in results:
        total += result["total"]
        passed += result["passed"]
        failed += result["failed"]
        errors += result["errors"]
        skipped += result["skipped"]

        if result.get("placeholder_reason") and result["total"] == 0:
            placeholder_notes.append(
                f"{result['file']}: {result['placeholder_reason']}"
            )

        for tc in result["testcases"]:
            all_testcases.append(
                {
                    "file": result["file"],
                    "name": tc["name"],
                    "status": tc["status"],
                    "details": tc["details"],
                }
            )

    print(f"\nTotal   : {total}")
    print(f"Passed  : {passed}")
    print(f"Failed  : {failed}")
    print(f"Errors  : {errors}")
    print(f"Skipped : {skipped}")

    if all_testcases:
        print("\nAll Test Cases:")
        for tc in all_testcases:
            print(f"  - {tc['name']} [{tc['status']}]")
            if tc["details"] and tc["status"] != "passed":
                print(f"    {tc['details']}")

    if placeholder_notes:
        print("\nPlaceholder Reports:")
        for note in placeholder_notes:
            print(f"  - {note}")

    print(f"\nFull pytest log: {PYTEST_LOG.relative_to(PROJECT_ROOT)}")
    print("\n===================================\n")


def get_recently_changed_python_files() -> list[Path]:
    changed_files: set[str] = set()

    git_queries = [
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    ]

    for query in git_queries:
        code, stdout, _ = run_git_command(query)
        if code != 0:
            continue

        for item in stdout.splitlines():
            item = item.strip()
            if item.endswith(".py"):
                changed_files.add(item)

    paths = []
    for item in sorted(changed_files):
        path = (PROJECT_ROOT / item).resolve()
        if path.exists() and path.is_file():
            paths.append(path)

    return paths


def extract_pylint_score(output: str) -> str:
    score_patterns = [
        r"rated at\s+(-?\d+(?:\.\d+)?)\/10",
        r"Your code has been rated at\s+(-?\d+(?:\.\d+)?)\/10",
    ]

    for pattern in score_patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            return f"{match.group(1)}/10"

    return "N/A"


def run_pylint_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_pylint() -> int:
    ensure_reports_dir()

    pylint_exe = shutil.which("pylint")
    if pylint_exe is None:
        print("WARNING: pylint not found in PATH.")
        create_empty_pylint_xml("pylint not installed")
        PYLINT_LOG.write_text("pylint not installed\n", encoding="utf-8")
        return 0

    targets = get_recently_changed_python_files()
    if not targets:
        print("WARNING: No recently changed Python files found by git for pylint.")
        create_empty_pylint_xml("no recently changed python files found")
        PYLINT_LOG.write_text(
            "no recently changed python files found\n",
            encoding="utf-8",
        )
        return 0

    print("[INFO] Running pylint on recently changed Python files:")
    for target in targets:
        try:
            rel = target.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = target
        print(f"  - {rel}")

    parseable_cmd = [
        pylint_exe,
        "--output-format=parseable",
        "--score=y",
        *[str(path) for path in targets],
    ]
    score_cmd = [
        pylint_exe,
        "--score=y",
        *[str(path) for path in targets],
    ]

    parseable_result = run_pylint_command(parseable_cmd)
    score_result = run_pylint_command(score_cmd)
    pylint_score = extract_pylint_score(
        "\n".join(
            [
                score_result.stdout or "",
                score_result.stderr or "",
                parseable_result.stdout or "",
                parseable_result.stderr or "",
            ]
        )
    )

    with PYLINT_LOG.open("w", encoding="utf-8") as handle:
        handle.write("PARSEABLE STDOUT\n")
        handle.write("=" * 80 + "\n")
        handle.write(parseable_result.stdout or "")
        handle.write("\n\nPARSEABLE STDERR\n")
        handle.write("=" * 80 + "\n")
        handle.write(parseable_result.stderr or "")
        handle.write("\n\nSCORE STDOUT\n")
        handle.write("=" * 80 + "\n")
        handle.write(score_result.stdout or "")
        handle.write("\n\nSCORE STDERR\n")
        handle.write("=" * 80 + "\n")
        handle.write(score_result.stderr or "")
        handle.write("\n")

    print(f"[INFO] Full pylint log saved to: {PYLINT_LOG.relative_to(PROJECT_ROOT)}")

    write_pylint_xml(
        parseable_stdout=parseable_result.stdout,
        parseable_stderr=parseable_result.stderr,
        targets=targets,
        pylint_score=pylint_score,
    )
    return parseable_result.returncode


def write_pylint_xml(
    parseable_stdout: str,
    parseable_stderr: str,
    targets: list[Path],
    pylint_score: str,
) -> None:
    commit_info = get_commit_info()

    testsuite = ET.Element("testsuite")
    testsuite.set("name", "pylint")
    testsuite.set("tests", str(len(targets)))

    failures = 0
    issues_by_file: dict[str, list[str]] = {}

    for line in parseable_stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        file_key = line.split(":", 1)[0].strip()
        issues_by_file.setdefault(file_key, []).append(line)

    properties = ET.SubElement(testsuite, "properties")

    score_prop = ET.SubElement(properties, "property")
    score_prop.set("name", "pylint_score")
    score_prop.set("value", pylint_score)

    for target in targets:
        try:
            rel = str(target.relative_to(PROJECT_ROOT))
        except ValueError:
            rel = str(target)

        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("classname", "pylint")
        testcase.set("name", rel)

        issues = issues_by_file.get(str(target), []) or issues_by_file.get(rel, [])
        if issues:
            failures += 1
            failure = ET.SubElement(testcase, "failure")
            failure.set("message", f"{len(issues)} pylint issue(s)")
            failure.text = "\n".join(issues)

    testsuite.set("failures", str(failures))
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    system_out = ET.SubElement(testsuite, "system-out")
    system_out.text = (
        f"branch={commit_info['branch']}\n"
        f"commit={commit_info['commit']}\n"
        f"git_status={commit_info['status']}\n"
        f"pylint_score={pylint_score}\n"
        f"{parseable_stderr.strip()}".strip()
    )

    tree = ET.ElementTree(testsuite)
    tree.write(PYLINT_XML, encoding="utf-8", xml_declaration=True)


def create_empty_pylint_xml(reason: str) -> None:
    commit_info = get_commit_info()

    testsuite = ET.Element("testsuite")
    testsuite.set("name", "pylint")
    testsuite.set("tests", "0")
    testsuite.set("failures", "0")
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    properties = ET.SubElement(testsuite, "properties")
    score_prop = ET.SubElement(properties, "property")
    score_prop.set("name", "pylint_score")
    score_prop.set("value", "N/A")

    system_out = ET.SubElement(testsuite, "system-out")
    system_out.text = (
        f"branch={commit_info['branch']}\n"
        f"commit={commit_info['commit']}\n"
        f"git_status={commit_info['status']}\n"
        f"pylint_score=N/A\n"
        f"reason={reason}"
    )

    tree = ET.ElementTree(testsuite)
    tree.write(PYLINT_XML, encoding="utf-8", xml_declaration=True)


def get_pylint_score_from_xml(root: ET.Element) -> str:
    properties = root.find("properties")
    if properties is not None:
        for prop in properties.findall("property"):
            if prop.attrib.get("name") == "pylint_score":
                return prop.attrib.get("value", "N/A")

    system_out = root.findtext("system-out", default="")
    match = re.search(r"pylint_score=(.+)", system_out)
    if match:
        return match.group(1).strip()

    return "N/A"


def print_pylint_summary(commit_info: dict[str, str]) -> None:
    print("\n========== PYLINT REPORT ==========\n")
    print(f"Branch  : {commit_info['branch']}")
    print(f"Commit  : {commit_info['commit']}")
    print(f"Git     : {commit_info['status']}")

    if not PYLINT_XML.exists():
        print("\nWARNING: No pylint XML report found.")
        print("\n===================================\n")
        return

    try:
        tree = ET.parse(PYLINT_XML)
        root = tree.getroot()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"\nWARNING: Failed to parse pylint XML report: {exc}")
        print("\n===================================\n")
        return

    total = int(root.attrib.get("tests", 0))
    failures = int(root.attrib.get("failures", 0))
    errors = int(root.attrib.get("errors", 0))
    skipped = int(root.attrib.get("skipped", 0))
    passed = total - failures - errors - skipped
    pylint_score = get_pylint_score_from_xml(root)

    print(f"\nTotal   : {total}")
    print(f"Passed  : {passed}")
    print(f"Failed  : {failures}")
    print(f"Errors  : {errors}")
    print(f"Skipped : {skipped}")
    print(f"Score   : {pylint_score}")

    print("\nDetailed Issues:\n")

    for testcase in root.findall("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            continue

        file_name = testcase.attrib.get("name", "unknown")
        details = (failure.text or "").strip().splitlines()

        print(f"{file_name}")
        for line in details:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                line_no = parts[1]
                rest = parts[2].strip()
                print(f"  - line {line_no}: {rest}")
            else:
                print(f"  - {line}")
        print()

    system_out = root.findtext("system-out", default="").strip()
    if system_out and total == 0:
        print(f"Note: {system_out}")

    print(f"\nFull pylint log: {PYLINT_LOG.relative_to(PROJECT_ROOT)}")
    print("\n===================================\n")


def main() -> int:
    ensure_reports_dir()
    commit_info = get_commit_info()

    pytest_exit_code = run_pytest()
    pylint_exit_code = run_pylint()

    pytest_results = []
    pytest_xml_files = sorted(REPORTS_DIR.glob("*.xml"))
    pytest_xml_files = [path for path in pytest_xml_files if path.name != PYLINT_XML.name]

    for xml_file in pytest_xml_files:
        try:
            pytest_results.append(parse_pytest_xml(xml_file))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"WARNING: Could not parse '{xml_file}': {exc}")

    print_pytest_summary(pytest_results, commit_info)
    print_pylint_summary(commit_info)

    if pytest_exit_code != 0:
        return pytest_exit_code
    return pylint_exit_code


if __name__ == "__main__":
    sys.exit(main())
