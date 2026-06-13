from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

_SPEC = importlib.util.spec_from_file_location(
    "yaml_harness_pytest_runner",
    HARNESS_DIR / "pytest_runner.py",
)
assert _SPEC is not None
assert _SPEC.loader is not None
pytest_runner = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = pytest_runner
_SPEC.loader.exec_module(pytest_runner)


def test_harness_sources_changed_ignores_pycache() -> None:
    changed_paths = {
        pytest_runner.HARNESS_DIR / "__pycache__" / "pytest_runner.cpython-313.pyc",
    }

    assert pytest_runner.harness_sources_changed(changed_paths) is False


def test_select_yaml_runs_runs_all_groups_when_harness_changes(monkeypatch) -> None:
    yaml_files = [
        pytest_runner.PROJECT_ROOT / "common" / "test_yaml" / "group_one.yaml",
        pytest_runner.PROJECT_ROOT / "common" / "test_yaml" / "group_two.yaml",
    ]
    changed_paths = {pytest_runner.HARNESS_DIR / "mock_loader.py"}

    monkeypatch.setattr(
        pytest_runner,
        "get_recently_changed_paths",
        lambda: changed_paths,
    )
    monkeypatch.setattr(
        pytest_runner,
        "yaml_targets_changed_files",
        lambda yaml_file, _changed: ({f"{yaml_file.stem}.py"}, None),
    )
    monkeypatch.setattr(
        pytest_runner,
        "get_yaml_target_entries",
        lambda yaml_file: ({f"{yaml_file.stem}.py", f"{yaml_file.stem}_extra.py"}, None),
    )

    selected_runs, warnings = pytest_runner.select_yaml_runs(yaml_files)

    assert warnings == []
    assert selected_runs == [
        (yaml_files[0], {"group_one.py", "group_one_extra.py"}),
        (yaml_files[1], {"group_two.py", "group_two_extra.py"}),
    ]


def test_select_yaml_runs_preserves_target_only_selection(monkeypatch) -> None:
    yaml_files = [pytest_runner.PROJECT_ROOT / "common" / "test_yaml" / "group_one.yaml"]

    monkeypatch.setattr(
        pytest_runner,
        "get_recently_changed_paths",
        lambda: {pytest_runner.PROJECT_ROOT / "common" / "linux_scripts" / "target.py"},
    )
    monkeypatch.setattr(
        pytest_runner,
        "yaml_targets_changed_files",
        lambda _yaml_file, _changed: ({"target.py"}, None),
    )
    get_yaml_target_entries_called = False

    def fake_get_yaml_target_entries(_yaml_file: Path) -> tuple[set[str], None]:
        nonlocal get_yaml_target_entries_called
        get_yaml_target_entries_called = True
        return {"target.py", "unrelated.py"}, None

    monkeypatch.setattr(
        pytest_runner,
        "get_yaml_target_entries",
        fake_get_yaml_target_entries,
    )

    selected_runs, warnings = pytest_runner.select_yaml_runs(yaml_files)

    assert warnings == []
    assert get_yaml_target_entries_called is False
    assert selected_runs == [(yaml_files[0], {"target.py"})]

