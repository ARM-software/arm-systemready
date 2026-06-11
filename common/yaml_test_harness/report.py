from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def detect_project_root(script_dir: Path) -> Path:
    if script_dir.parent.name == "common":
        return script_dir.parent.parent
    return script_dir.parent


PROJECT_ROOT = detect_project_root(SCRIPT_DIR)

RUNNER_FILE = SCRIPT_DIR / "pytest_runner.py"
REPORTS_DIR = PROJECT_ROOT / "common" / "reports"

PYLINT_XML = REPORTS_DIR / "pylint-report.xml"
PYLINT_LOG = REPORTS_DIR / "pylint.log"

MYPY_XML = REPORTS_DIR / "mypy-report.xml"
MYPY_LOG = REPORTS_DIR / "mypy.log"

PYTEST_LOG = REPORTS_DIR / "pytest.log"

MAX_LOG_ENTRIES = 50
LOG_SEPARATOR = "=" * 100


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def color_text(text: str, color: str) -> str:
    return f"{color}{text}{Color.RESET}"


def ensure_reports_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def append_log_history(log_path: Path, content: str, max_entries: int = MAX_LOG_ENTRIES) -> None:
    ensure_reports_dir()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_content = content.rstrip("\n")
    new_entry = (
        f"{LOG_SEPARATOR}\n"
        f"RUN AT: {timestamp}\n"
        f"{LOG_SEPARATOR}\n"
        f"{normalized_content}\n"
    )

    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8")
    else:
        existing = ""

    existing = existing.strip()
    entries: list[str] = []

    if existing:
        parts = re.split(
            rf"(?m)(?=^{re.escape(LOG_SEPARATOR)}\nRUN AT: )",
            existing,
        )
        entries = [part.strip() for part in parts if part.strip()]

    entries.append(new_entry.strip())
    entries = entries[-max_entries:]

    final_content = "\n\n".join(entries) + "\n"
    log_path.write_text(final_content, encoding="utf-8")


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


def resolve_manual_target(target: str | None) -> Path | None:
    if not target:
        return None

    raw = Path(target)
    if raw.is_absolute():
        return raw.resolve()
    return (PROJECT_ROOT / raw).resolve()


def get_manual_python_target(target: str | None, tool_name: str) -> list[Path] | None:
    resolved_target = resolve_manual_target(target)
    if resolved_target is None:
        return None

    if not resolved_target.exists() or not resolved_target.is_file():
        print(
            f"{color_text('WARNING:', Color.YELLOW)} "
            f"Manual target for {tool_name} not found: {resolved_target}"
        )
        return []

    if resolved_target.suffix != ".py":
        print(
            f"{color_text('WARNING:', Color.YELLOW)} "
            f"Manual target is not a Python file for {tool_name}: {resolved_target}"
        )
        return []

    return [resolved_target]


def sanitize_name(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in value
    )


def is_generated_report_artifact(path: Path) -> bool:
    """Return True when a path points inside a generated report work directory."""
    try:
        rel_path = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return False

    parts = rel_path.parts
    if len(parts) >= 3 and parts[:2] == ("common", "reports"):
        return parts[2].startswith(("_", "tpm_check_"))

    if len(parts) >= 2 and parts[0] == "reports":
        return parts[1].startswith(("_", "tpm_check_"))

    return False


def run_pytest(target: str | None = None, jobs: int = 4) -> tuple[int, str, str]:
    if not RUNNER_FILE.exists():
        return 1, "", f"ERROR: Runner file not found: {RUNNER_FILE}"

    cmd = [sys.executable, str(RUNNER_FILE)]
    if target:
        cmd.extend(["--target", target])
    cmd.extend(["--jobs", str(max(1, jobs))])

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    log_content = (
        "STDOUT\n"
        + "=" * 80
        + "\n"
        + stdout
        + "\n\nSTDERR\n"
        + "=" * 80
        + "\n"
        + stderr
        + "\n"
    )
    append_log_history(PYTEST_LOG, log_content)

    return result.returncode, stdout, stderr


def collect_pytest_case_logs(target: str | None = None) -> list[dict[str, str]]:
    work_root = REPORTS_DIR / "_work"
    if not work_root.exists():
        return []

    testcases: list[dict[str, str]] = []
    seen_names: set[str] = set()

    pattern = re.compile(
        r"(?ms)^=+\n"
        r"TEST CASE:\s*(?P<name>.+?)\n"
        r"(?:DESCRIPTION:\s*(?P<description>.+?)\n)?"
        r"STATUS:\s*(?P<status>.+?)\n"
        r"MESSAGE:\s*(?P<message>.*?)(?=\n=+\nTEST CASE:|\Z)"
    )

    log_paths: list[Path]
    resolved_target = resolve_manual_target(target)

    if resolved_target is not None:
        target_stem = sanitize_name(resolved_target.stem)
        log_paths = sorted(work_root.rglob(f"{target_stem}/combined.log"))
    else:
        log_paths = sorted(work_root.rglob("combined.log"))

    for log_path in log_paths:
        content = log_path.read_text(encoding="utf-8", errors="replace")

        for match in pattern.finditer(content):
            name = match.group("name").strip()
            if name in seen_names:
                continue
            seen_names.add(name)

            raw_status = match.group("status").strip().upper()

            if raw_status == "PASS":
                normalized_status = "passed"
            elif raw_status == "FAIL":
                normalized_status = "failed"
            elif raw_status == "ERROR":
                normalized_status = "error"
            elif raw_status in {"WARNING", "SKIPPED"}:
                normalized_status = "warning"
            else:
                normalized_status = raw_status.lower()

            testcases.append(
                {
                    "name": name,
                    "description": (match.group("description") or "").strip(),
                    "status": normalized_status,
                    "details": match.group("message").strip(),
                }
            )

    return testcases


def print_pytest_summary(commit_info: dict[str, str], target: str | None = None) -> None:
    print(f"\n{color_text('========== PYTEST REPORT ==========', Color.BLUE)}\n")
    print(f"Branch  : {commit_info['branch']}")
    print(f"Commit  : {commit_info['commit']}")
    print(f"Git     : {commit_info['status']}")

    testcases = collect_pytest_case_logs(target)

    if not testcases:
        print(
            f"\n{color_text('WARNING:', Color.YELLOW)} "
            "No pytest case logs were found."
        )
        print(f"\nFull pytest log: {PYTEST_LOG.relative_to(PROJECT_ROOT)}")
        print(f"\n{color_text('===================================', Color.BLUE)}\n")
        return

    total = len(testcases)
    passed = sum(1 for tc in testcases if tc["status"] == "passed")
    failed = sum(1 for tc in testcases if tc["status"] == "failed")
    errors = sum(1 for tc in testcases if tc["status"] == "error")
    warnings = sum(1 for tc in testcases if tc["status"] == "warning")

    print(f"\n{color_text('Total   :', Color.BLUE)} {total}")
    print(f"{color_text('Passed  :', Color.GREEN)} {passed}")
    print(f"{color_text('Failed  :', Color.RED)} {failed}")
    print(f"{color_text('Errors  :', Color.RED)} {errors}")
    print(f"{color_text('Warnings:', Color.YELLOW)} {warnings}")

    print(f"\n{color_text('All Test Cases:', Color.BLUE)}")

    warning_groups: dict[str, list[dict[str, str]]] = {}

    for tc in testcases:
        status = tc["status"]

        if status == "passed":
            label = color_text("[passed]", Color.GREEN)
            print(f"  - {tc['name']} {label}")
        elif status in {"failed", "error"}:
            label = color_text(f"[{status}]", Color.RED)
            print(f"  - {tc['name']} {label}")
        elif status == "warning":
            short_msg = tc["details"].splitlines()[0].strip() if tc["details"] else "Warning"
            warning_groups.setdefault(short_msg, []).append(tc)
        else:
            label = color_text(f"[{status}]", Color.YELLOW)
            print(f"  - {tc['name']} {label}")

    single_warning_groups = {
        msg: items for msg, items in warning_groups.items() if len(items) == 1
    }
    repeated_warning_groups = {
        msg: items for msg, items in warning_groups.items() if len(items) > 1
    }

    for _msg, items in single_warning_groups.items():
        tc = items[0]
        print(f"  - {tc['name']} {color_text('[warning]', Color.YELLOW)}")

    if repeated_warning_groups:
        print(f"\n{color_text('Collapsed Repeated Warnings:', Color.YELLOW)}")
        for msg, items in repeated_warning_groups.items():
            print(f"  - {color_text('[warning]', Color.YELLOW)} {msg} ({len(items)} case(s))")
            for tc in items:
                print(f"      * {tc['name']}")

    print(f"\nFull pytest log: {PYTEST_LOG.relative_to(PROJECT_ROOT)}")
    print(f"\n{color_text('===================================', Color.BLUE)}\n")


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
        if path.exists() and path.is_file() and not is_generated_report_artifact(path):
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


def run_pylint(target: str | None = None) -> int:
    ensure_reports_dir()

    pylint_exe = shutil.which("pylint")
    if pylint_exe is None:
        print(f"{color_text('WARNING:', Color.YELLOW)} pylint not found in PATH.")
        create_empty_pylint_xml("pylint not installed")
        append_log_history(PYLINT_LOG, "pylint not installed")
        return 0

    manual_targets = get_manual_python_target(target, "pylint")
    targets = (
        manual_targets
        if manual_targets is not None
        else get_recently_changed_python_files()
    )

    if not targets:
        print(
            f"{color_text('WARNING:', Color.YELLOW)} "
            "No recently changed Python files found by git for pylint."
        )
        create_empty_pylint_xml("no recently changed python files found")
        append_log_history(PYLINT_LOG, "no recently changed python files found")
        return 0

    print(
        color_text(
            "[INFO] Running pylint on recently changed Python files:",
            Color.BLUE,
        )
    )
    for target_path in targets:
        try:
            rel = target_path.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = target_path
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

    log_content = (
        "PARSEABLE STDOUT\n"
        + "=" * 80
        + "\n"
        + (parseable_result.stdout or "")
        + "\n\nPARSEABLE STDERR\n"
        + "=" * 80
        + "\n"
        + (parseable_result.stderr or "")
        + "\n\nSCORE STDOUT\n"
        + "=" * 80
        + "\n"
        + (score_result.stdout or "")
        + "\n\nSCORE STDERR\n"
        + "=" * 80
        + "\n"
        + (score_result.stderr or "")
        + "\n\nEXTRACTED SCORE\n"
        + "=" * 80
        + "\n"
        + pylint_score
        + "\n"
    )
    append_log_history(PYLINT_LOG, log_content)

    print(
        f"{color_text('[INFO]', Color.BLUE)} "
        f"Full pylint log saved to: {PYLINT_LOG.relative_to(PROJECT_ROOT)}"
    )

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

        issues = (
            issues_by_file.get(str(target), [])
            or issues_by_file.get(rel, [])
        )
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
    print(f"\n{color_text('========== PYLINT REPORT ==========', Color.BLUE)}\n")
    print(f"Branch  : {commit_info['branch']}")
    print(f"Commit  : {commit_info['commit']}")
    print(f"Git     : {commit_info['status']}")

    if not PYLINT_XML.exists():
        print(f"\n{color_text('WARNING:', Color.YELLOW)} No pylint XML report found.")
        print(f"\n{color_text('===================================', Color.BLUE)}\n")
        return

    try:
        tree = ET.parse(PYLINT_XML)
        root = tree.getroot()
    except Exception as exc:
        print(
            f"\n{color_text('WARNING:', Color.YELLOW)} "
            f"Failed to parse pylint XML report: {exc}"
        )
        print(f"\n{color_text('===================================', Color.BLUE)}\n")
        return

    total = int(root.attrib.get("tests", 0))
    failures = int(root.attrib.get("failures", 0))
    errors = int(root.attrib.get("errors", 0))
    skipped = int(root.attrib.get("skipped", 0))
    passed = total - failures - errors - skipped
    pylint_score = get_pylint_score_from_xml(root)

    print(f"\n{color_text('Total   :', Color.BLUE)} {total}")
    print(f"{color_text('Passed  :', Color.GREEN)} {passed}")
    print(f"{color_text('Failed  :', Color.RED)} {failures}")
    print(f"{color_text('Errors  :', Color.RED)} {errors}")
    print(f"{color_text('Warnings:', Color.YELLOW)} {skipped}")
    print(f"{color_text('Score   :', Color.BLUE)} {pylint_score}")

    print(f"\n{color_text('Detailed Issues:', Color.BLUE)}\n")

    for testcase in root.findall("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            continue

        file_name = testcase.attrib.get("name", "unknown")
        details = (failure.text or "").strip().splitlines()

        print(color_text(file_name, Color.RED))
        for line in details:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                line_no = parts[1]
                rest = parts[2].strip()
                print(color_text(f"  - line {line_no}: {rest}", Color.RED))
            else:
                print(color_text(f"  - {line}", Color.RED))
        print()

    system_out = root.findtext("system-out", default="").strip()
    if system_out and total == 0:
        print(f"Note: {system_out}")

    print(f"\nFull pylint log: {PYLINT_LOG.relative_to(PROJECT_ROOT)}")
    print(f"\n{color_text('===================================', Color.BLUE)}\n")


def run_mypy_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_mypy(target: str | None = None) -> int:
    ensure_reports_dir()

    mypy_exe = shutil.which("mypy")
    if mypy_exe is None:
        print(f"{color_text('WARNING:', Color.YELLOW)} mypy not found in PATH.")
        create_empty_mypy_xml("mypy not installed")
        append_log_history(MYPY_LOG, "mypy not installed")
        return 0

    manual_targets = get_manual_python_target(target, "mypy")
    targets = (
        manual_targets
        if manual_targets is not None
        else get_recently_changed_python_files()
    )

    if not targets:
        print(
            f"{color_text('WARNING:', Color.YELLOW)} "
            "No recently changed Python files found by git for mypy."
        )
        create_empty_mypy_xml("no recently changed python files found")
        append_log_history(MYPY_LOG, "no recently changed python files found")
        return 0

    print(
        color_text(
            "[INFO] Running mypy on recently changed Python files:",
            Color.BLUE,
        )
    )
    for target_path in targets:
        try:
            rel = target_path.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = target_path
        print(f"  - {rel}")

    cmd = [
        mypy_exe,
        "--show-error-codes",
        "--no-color-output",
        "--no-error-summary",
        *[str(path) for path in targets],
    ]
    result = run_mypy_command(cmd)

    log_content = (
        "STDOUT\n"
        + "=" * 80
        + "\n"
        + (result.stdout or "")
        + "\n\nSTDERR\n"
        + "=" * 80
        + "\n"
        + (result.stderr or "")
        + "\n"
    )
    append_log_history(MYPY_LOG, log_content)

    print(
        f"{color_text('[INFO]', Color.BLUE)} "
        f"Full mypy log saved to: {MYPY_LOG.relative_to(PROJECT_ROOT)}"
    )

    write_mypy_xml(
        stdout=result.stdout,
        stderr=result.stderr,
        targets=targets,
    )
    return result.returncode


def write_mypy_xml(
    stdout: str,
    stderr: str,
    targets: list[Path],
) -> None:
    commit_info = get_commit_info()

    testsuite = ET.Element("testsuite")
    testsuite.set("name", "mypy")
    testsuite.set("tests", str(len(targets)))

    failures = 0
    issues_by_file: dict[str, list[str]] = {}

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(
            r"^(.*?\.py)(?::\d+)?(?::\d+)?:\s*(error|note):\s*(.*)$",
            line,
        )
        if match:
            file_key = match.group(1).strip()
            issues_by_file.setdefault(file_key, []).append(line)

    for target in targets:
        try:
            rel = str(target.relative_to(PROJECT_ROOT))
        except ValueError:
            rel = str(target)

        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("classname", "mypy")
        testcase.set("name", rel)

        issues = (
            issues_by_file.get(str(target), [])
            or issues_by_file.get(rel, [])
        )
        if issues:
            failures += 1
            failure = ET.SubElement(testcase, "failure")
            failure.set("message", f"{len(issues)} mypy issue(s)")
            failure.text = "\n".join(issues)

    testsuite.set("failures", str(failures))
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    system_out = ET.SubElement(testsuite, "system-out")
    system_out.text = (
        f"branch={commit_info['branch']}\n"
        f"commit={commit_info['commit']}\n"
        f"git_status={commit_info['status']}\n"
        f"{stderr.strip()}".strip()
    )

    tree = ET.ElementTree(testsuite)
    tree.write(MYPY_XML, encoding="utf-8", xml_declaration=True)


def create_empty_mypy_xml(reason: str) -> None:
    commit_info = get_commit_info()

    testsuite = ET.Element("testsuite")
    testsuite.set("name", "mypy")
    testsuite.set("tests", "0")
    testsuite.set("failures", "0")
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")

    ET.SubElement(testsuite, "properties")

    system_out = ET.SubElement(testsuite, "system-out")
    system_out.text = (
        f"branch={commit_info['branch']}\n"
        f"commit={commit_info['commit']}\n"
        f"git_status={commit_info['status']}\n"
        f"reason={reason}"
    )

    tree = ET.ElementTree(testsuite)
    tree.write(MYPY_XML, encoding="utf-8", xml_declaration=True)


def print_mypy_summary(commit_info: dict[str, str]) -> None:
    print(f"\n{color_text('=========== MYPY REPORT ===========', Color.BLUE)}\n")
    print(f"Branch  : {commit_info['branch']}")
    print(f"Commit  : {commit_info['commit']}")
    print(f"Git     : {commit_info['status']}")

    if not MYPY_XML.exists():
        print(f"\n{color_text('WARNING:', Color.YELLOW)} No mypy XML report found.")
        print(f"\n{color_text('===================================', Color.BLUE)}\n")
        return

    try:
        tree = ET.parse(MYPY_XML)
        root = tree.getroot()
    except Exception as exc:
        print(
            f"\n{color_text('WARNING:', Color.YELLOW)} "
            f"Failed to parse mypy XML report: {exc}"
        )
        print(f"\n{color_text('===================================', Color.BLUE)}\n")
        return

    total = int(root.attrib.get("tests", 0))
    failures = int(root.attrib.get("failures", 0))
    errors = int(root.attrib.get("errors", 0))
    skipped = int(root.attrib.get("skipped", 0))
    passed = total - failures - errors - skipped

    print(f"\n{color_text('Total   :', Color.BLUE)} {total}")
    print(f"{color_text('Passed  :', Color.GREEN)} {passed}")
    print(f"{color_text('Failed  :', Color.RED)} {failures}")
    print(f"{color_text('Errors  :', Color.RED)} {errors}")
    print(f"{color_text('Warnings:', Color.YELLOW)} {skipped}")

    print(f"\n{color_text('Detailed Issues:', Color.BLUE)}\n")

    for testcase in root.findall("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            continue

        file_name = testcase.attrib.get("name", "unknown")
        details = (failure.text or "").strip().splitlines()

        print(color_text(file_name, Color.RED))
        for line in details:
            print(color_text(f"  - {line}", Color.RED))
        print()

    system_out = root.findtext("system-out", default="").strip()
    if system_out and total == 0:
        print(f"Note: {system_out}")

    print(f"\nFull mypy log: {MYPY_LOG.relative_to(PROJECT_ROOT)}")
    print(f"\n{color_text('===================================', Color.BLUE)}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate test reports and run analysis tools."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Manual target file for focused analysis",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Number of YAML test cases to run in parallel (default: 4)",
    )
    args = parser.parse_args()

    ensure_reports_dir()
    commit_info = get_commit_info()

    if args.target:
        print(
            f"{color_text('[INFO]', Color.BLUE)} "
            f"Manual target override enabled: {args.target}"
        )

    pytest_exit_code, _pytest_stdout, _pytest_stderr = run_pytest(args.target, jobs=args.jobs)
    pylint_exit_code = run_pylint(args.target)
    mypy_exit_code = run_mypy(args.target)

    print_pytest_summary(commit_info, args.target)
    print_pylint_summary(commit_info)
    print_mypy_summary(commit_info)

    if pytest_exit_code != 0:
        return pytest_exit_code
    if pylint_exit_code != 0:
        return pylint_exit_code
    return mypy_exit_code


if __name__ == "__main__":
    sys.exit(main())
