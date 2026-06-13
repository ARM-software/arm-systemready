# YAML Test Framework README

## Purpose

This framework lets us test repository scripts by declaring suites and cases in YAML instead of writing a separate Python test module for every script.

It is built around:

- `common/yaml_test_harness/report.py` as the main user-facing entry point
- `common/test_yaml/` for YAML suite definitions
- `common/yaml_test_harness/pytest_runner.py` as the underlying YAML execution engine
- `common/yaml_test_harness/runner_checks.py` for schema validation, execution modes, and expectations
- `common/yaml_test_harness/mock_loader.py` for scenario expansion and mock construction
- `common/yaml_test_harness/case_data_builders.py` for reusable case workspace builders and template expansion
- `common/yaml_test_harness/mock_helpers.py` for reusable mock routers and verification helpers
- `common/reports/` for JUnit XML, combined logs, and per-case work directories

For normal use, run `python3 common/yaml_test_harness/report.py` from the repository root. Internally it calls `common/yaml_test_harness/pytest_runner.py`, which is a standalone Python runner rather than a standard pytest parametrization file.

## Prerequisites

Required:

- Python 3
- `PyYAML`

Install the required Python package with:

```bash
python3 -m pip install PyYAML
```

Optional but recommended when using `report.py`:

- `pylint`
- `mypy`

Install them with:

```bash
python3 -m pip install pylint mypy
```

Notes:

- The YAML framework itself only needs `PyYAML` in addition to the Python standard library.
- If `pylint` or `mypy` are not installed, `report.py` still runs the YAML test flow and prints warnings instead of failing only because those tools are missing.
- Pylint uses the repo-root `.pylintrc` file automatically because `report.py` runs pylint from the repository root. The checked-in config file is `.pylintrc`, not `.pylint.rc`.
- Git is recommended for the default impacted-file mode. If Git metadata is unavailable, use focused runs such as `python3 common/yaml_test_harness/report.py common/log_parser/merge_jsons.py`.
- Hardware-gated suites may also rely on platform commands such as `ip`, `ethtool`, `/bin/sh`, `awk`, `grep`, and `readlink`. Those are not needed for normal scenario-backed runs on a single target unless that target's cases explicitly probe them.

## How It Works

At a high level, each run goes through the following stages:

1. Discover every `.yaml` and `.yml` file under `common/test_yaml/`.
2. Select which YAML suites to run.
   - Default mode runs only suites whose `files:` entries match changed files from Git.
   - Manual mode runs suites for one explicit target passed to `common/yaml_test_harness/report.py` as its positional `target` argument.
3. Normalize and validate the YAML schema.
   - Top-level `suites:` is required.
   - Each suite must define `name`, `files`, and `cases`.
   - Optional suite-level `defaults` are merged into every case.
4. Build a runtime case.
   - If a case contains `scenario:`, the scenario builder generates `args`, `text_files`, `bin_files`, `mocks`, and `patch_constants`.
   - Case-level values override generated values where appropriate.
   - Runtime tokens such as `{dir}`, `{file}`, and `{filename}` are expanded.
5. Materialize a per-case workspace under `common/reports/_work/...`.
   - Generated files, helper scripts, and directory structures are created here.
6. Execute the case using the requested case type.
7. Validate exit code, stdout/stderr content, timeout behavior, and optional post-checks.
8. Write XML and text logs into `common/reports/`.

The work directory is isolated per case, which keeps generated fixtures and side effects from leaking across cases.

## Running The Framework

Use the repo-root wrapper path:

```bash
python3 common/yaml_test_harness/report.py
```

Useful variants:

```bash
python3 common/yaml_test_harness/report.py common/log_parser/merge_jsons.py
python3 common/yaml_test_harness/report.py common/linux_scripts/verify_tpm_measurements.py
```

Notes:

- `common/yaml_test_harness/report.py` is the main command to share with other users of this framework.
- The positional `target` argument is the simplest way to run focused coverage for one script.
- Example: `python3 common/yaml_test_harness/report.py common/log_parser/merge_jsons.py`
- `report.py` runs the YAML-based test flow and also prints the paired `pylint` and `mypy` summaries for the same target set.
- Internally, `report.py` forwards the YAML test portion to `common/yaml_test_harness/pytest_runner.py`.
- Default mode depends on Git change detection. If the repo is not a Git worktree, or there are no detected changes, nothing will be selected.
- When `report.py` auto-collects changed Python files for `pylint` and `mypy`, it skips generated artifacts under `common/reports/` and `reports/`, including directories such as `_work`, `_runner_work`, and `tpm_check_*`.
- XML reports are written to `common/reports/*.xml`.
- Case logs and generated fixtures go under `common/reports/_work/`.

## Local Git Hooks

The repo includes a local pre-commit hook at `.githooks/pre-commit`.

What it does:

- runs `common/yaml_test_harness/report.py` from the repository root
- uses the default impacted-file selection logic
- writes a hook-specific console capture to `common/reports/precommit_report.log`
- blocks the commit when the report flow exits non-zero

Configure the hook path for this clone:

```bash
git config core.hooksPath .githooks
git config --get core.hooksPath
```

If needed, make the hook executable:

```bash
chmod +x .githooks/pre-commit
```

Run it manually without creating a commit:

```bash
bash .githooks/pre-commit
```

Notes:

- Local hooks only work in a real Git clone/worktree. They do not apply to an extracted ZIP snapshot.
- The hook script is Bash-based and intended to be run from a normal Linux shell.
- To disable the custom hook path for a clone, run `git config --unset core.hooksPath`.

## Report Structure

Main output directory:

```text
common/reports/
  <yaml-group>.xml
  precommit_report.log
  pylint-report.xml
  pylint.log
  mypy-report.xml
  mypy.log
  pytest.log
  pytest-placeholder.xml         # only when no YAML groups are selected
  _work/
    <suite_name>/
      <target_stem>/
        combined.log
        <case_index>_<case_name>/
          case.log
          ...generated files for that case...
  _runner_work/
    runner_env_<id>/             # internal temp dirs for some in-process modes
```

What the main files mean:

- `common/reports/<yaml-group>.xml`: JUnit-style XML for one YAML suite group. Example: `merge_jsons.xml`.
- `common/reports/precommit_report.log`: stdout/stderr captured by the local pre-commit hook.
- `common/reports/pylint-report.xml`: XML summary produced by the `pylint` part of `report.py`.
- `common/reports/mypy-report.xml`: XML summary produced by the `mypy` part of `report.py`.
- `common/reports/pytest.log`: captured stdout/stderr from the YAML runner.
- `common/reports/pylint.log`: captured stdout/stderr from pylint, including the scored and parseable outputs used by the wrapper.
- `common/reports/mypy.log`: captured stdout/stderr from mypy.
- `common/reports/_work/<suite>/<target>/combined.log`: one running log for all cases that executed against that target file in that suite.
- `common/reports/_work/<suite>/<target>/<index_case>/case.log`: one detailed log for a single case, including command, timeout, exit code, stdout/stderr, and post-check details when applicable.
- `common/reports/_runner_work/runner_env_<id>/`: internal scratch directories used by runner-managed execution modes such as `module_main_with_env`.

## Logs Info

`pytest.log`, `pylint.log`, and `mypy.log` are history logs maintained by `report.py`:

- Each run is appended with a timestamped separator.
- The wrapper keeps the most recent 50 log entries.
- These files are the first place to look if the console output was truncated or if you need the raw stdout/stderr from a previous run.
- Generated report artifacts under `common/reports/` and `reports/` are not treated as source targets for the wrapper's default `pylint` and `mypy` changed-file mode.

`precommit_report.log` is the hook-specific run log:

- It is overwritten by each hook run rather than kept as a rolling history log.
- Use it when a commit is blocked and you want the exact hook console output in one file.

`combined.log` is useful for target-level triage:

- It starts with a run header showing the YAML file, suite name, and target path.
- It then lists every executed test case with `TEST CASE`, `STATUS`, and `MESSAGE`.
- Use it when you want one compact chronological view of what happened for a target file.

`case.log` is useful for root-cause analysis:

- Runtime cases usually include command line, shell mode, timeout, exit code, stdout, stderr, and post-check output.
- Mock verification failures and configuration errors are also written here.
- Generated per-case files live beside the case log in the same case work directory.

XML report details:

- Each testcase in the JUnit XML includes `file`, `suite`, `phase`, `type`, `warning`, `message`, and optional `details` in `system-out`.
- The XML `<properties>` section records at least the source YAML file and summary counts such as passed and warnings.

## YAML Structure

Minimal shape:

```yaml
suites:
  - name: example_suite
    files:
      - common/linux_scripts/example.py
    defaults:
      timeout_sec: 20
    cases:
      - name: file_exists
        type: file_exists

      - name: cli_happy_path
        type: cli
        args:
          - "{dir}/input.yaml"
        text_files:
          input.yaml: |
            enabled: true
        expect_exit_code: 0
        expect_stdout_or_stderr_contains:
          - "PASS"
```

Suite fields:

| Field | Meaning |
| --- | --- |
| `name` | Logical suite name used in reports and work directories |
| `files` | One or more target files covered by the suite |
| `command` | Optional suite-wide command override |
| `defaults` | Optional case defaults merged into each case |
| `cases` | List of case definitions |

Common case fields:

| Field | Meaning |
| --- | --- |
| `name` | Required case name |
| `type` | Execution/check type |
| `description` | Optional explanation for humans |
| `args` / `kwargs` | Arguments for CLI or function-style cases |
| `command` | Override the default interpreter command |
| `env` | Environment variables for the case |
| `stdin` | Text passed to stdin |
| `timeout_sec` | Command timeout |
| `scripts` | Helper scripts written into the case workspace |
| `text_files` / `bin_files` | Generated fixture files written into the workspace |
| `dir_structure` | Directories to create before execution |
| `mocks` | Explicit patch definitions |
| `patch_constants` | Attribute overrides patched into imported modules |
| `post_checks` | File existence/content checks after execution |
| `warn_only` | Treat a functional failure as a warning instead of a failing case |
| `skip_unless_env` | Skip unless required env vars are present or match |
| `skip_unless_paths_exist` | Skip when required hardware-visible paths do not exist |
| `skip_unless_commands_succeed` | Skip when probe commands fail |
| `requires_destructive` | Skip unless `RUN_DESTRUCTIVE_HW_TESTS=1` is set |

Output expectation fields commonly used by runtime cases:

- `expect_exit_code`
- `expect_exit_code_in`
- `expect_exit_nonzero`
- `expect_timeout`
- `expect_output`
- `expect_stdout_contains`
- `expect_stderr_contains`
- `expect_stdout_or_stderr_contains`
- `expect_stdout_or_stderr_regex`

Supported `post_checks`:

- `exists`
- `not_exists`
- `file_contains`
- `file_not_contains`
- `file_not_empty`
- `regex`
- `ordered_contains`

Runtime tokens:

- `{dir}`: per-case work directory
- `{file}`: target file path being tested
- `{filename}`: basename of the target file

Case-type-specific fields:

- `py_function`: requires `function`; can also use `expect_exception` and `expect_return_contains`
- `path_exists` / `path_not_exists`: require `path`
- `command_success`, `command_exit_code`, `command_output_contains`, and `command_output_regex`: use `command`, `args`, optional `shell`, optional `cwd`, optional `env`, and optional `timeout_sec`
- `command_exit_code`: requires `expect_exit_code`
- `command_output_contains`: requires `expect_text`
- `command_output_regex`: requires `expect_pattern`

## Supported Case Types

Static and source-level checks:

- `file_exists`
- `py_compile`
- `source_contains`
- `source_contains_any`
- `source_contains_all`
- `function_exists`
- `function_exists_any`
- `main_guard`
- `path_exists`
- `path_not_exists`

Runtime and execution checks:

- `cli`
- `module_cli`
- `py_function`
- `module_main_with_env`

Command/probe checks:

- `command_success`
- `command_exit_code`
- `command_output_contains`
- `command_output_regex`

When to use which runtime type:

- `cli`: runs the target in a real subprocess. Use this when you want real process behavior and do not need in-process patching.
- `module_cli`: executes the script as `__main__` in-process. Use this when you need deterministic mocks, generated patch constants, or scenario-generated runtime behavior.
- `module_main_with_env`: imports the module, patches attributes, changes cwd/env, and calls `main()` directly.
- `py_function`: imports the module and calls one named function.

## Choosing The Right Test Style

Start with the least powerful style that can still prove the requirement.

### 1. Static checks

Use static checks when you only need to prove source or presence facts:

- the file exists and parses
- a function or main guard is present
- required source text or patterns exist
- a required path exists or does not exist on the current machine

Choose this style when:

- you want the fastest and least brittle coverage
- the behavior under test is structural rather than runtime behavior
- running the script would add noise without adding confidence

Do not use static checks when you actually need to prove exit codes, stdout/stderr, generated files, side effects, or control flow.

### 2. Subprocess CLI execution

Use `type: cli` when the script should be exercised the way a user runs it:

- real interpreter startup
- real `sys.argv`, stdin, stdout, and stderr flow
- real process exit codes and timeout behavior
- cases where shell mode, `command`, `cwd`, or environment handling matter

Choose this style when:

- process boundaries matter
- you want the closest match to production CLI behavior
- you do not need in-process mocks or patched constants

Important limitation:

- `cli` runs in a separate process, so in-process `mocks:` and `patch_constants:` do not affect the target script.
- `cli` can still use generated files, args, env, and `post_checks`, but it is the wrong choice when the test depends on patched Python internals.

### 3. In-Process Execution

Use in-process execution when you need the runner to patch or control Python state inside the target:

- `module_cli`: best when the script is still being tested as a CLI entry point, but you need deterministic `mocks:`, generated `patch_constants:`, or scenario-generated runtime setup
- `module_main_with_env`: best when the module exposes a real `main()` and you want to call it directly under a controlled cwd and environment
- `py_function`: best for narrow unit-like checks of one function's return value or raised exception

Choose this style when:

- you need mocked `subprocess`, `open`, helper functions, or module attributes
- you want scenario builders to inject runtime setup into the same interpreter
- you need tighter control than a real subprocess allows

Tradeoff:

- in-process modes are less faithful to a true separate process than `cli`
- `module_main_with_env` skips the normal `__main__` execution path and calls `main()` directly, so use it only when that is the behavior you actually want to verify

### 4. Scenario-Backed Cases

A scenario-backed case is not a separate `type:`. It is a runtime case that also includes `scenario:` so a builder in `mock_loader.py` can generate `args`, files, mocks, and patch constants for you.

Use a scenario-backed case when:

- the same domain setup is repeated across many cases
- the script is hardware-facing or environment-heavy
- hand-writing `text_files:`, `bin_files:`, `mocks:`, and `patch_constants:` for every case would be noisy and error-prone

Choose this style when:

- an existing scenario kind already models the domain well
- the important part of the test is the behavior, not the low-level mock wiring
- you want consistent fixture generation across a whole suite

Practical rule:

- most scenario-backed cases should use `module_cli` or `module_main_with_env`, because scenario builders often generate `mocks:` and `patch_constants:` that only in-process execution can see
- use `cli` with `scenario:` only when the scenario is effectively just generating files, args, or environment input and does not rely on in-process patching

Short decision guide:

1. If a structural check is enough, use a static case type.
2. If real process behavior matters, use `cli`.
3. If mocks or patched Python state matter, use an in-process type.
4. If setup is repetitive or domain-specific, add `scenario:` on top of the appropriate runtime type.

## Scenarios And Mocking

Scenario builders reduce repetitive low-level setup. The currently registered scenario kinds are:

| Scenario kind | What it auto-generates |
| --- | --- |
| `ethtool` | Network interface fixtures, tool availability, command routers, sysfs-style reads, connectivity outcomes |
| `verify_tpm` | `pcr.yaml`, `event.yaml`, event-log fault injection mocks, expected argument wiring |
| `capsule_vars` | efivarfs-style binary fixtures and capsule variable defaults |
| `acs_info` | ACS info inputs and mocked platform data |
| `merge_jsons` | input JSON trees, ACS info payloads, mode-specific runtime setup |
| `blk_devices` | block-device discovery, partition layout, and subprocess behavior for the script main flow |
| `blk_write_check` | direct write/readback/restore flows for block-device write checks |
| `runtime_device_mapping` | generated DTS/memmap/log inputs and selected file-open patches |

`blk_devices` is aligned with the current `common/linux_scripts/read_write_check_blk_devices.py` implementation. For full-flow cases, it is intended to drive the real `main()` path under an in-process runtime type, patch `{module}.input_with_timeout`, and mock the current command forms such as `lsblk -e 7 -d -n -o NAME,TYPE`, `lsblk -rn -o NAME,TYPE /dev/<disk>`, and `dd if=/dev/<target> of=/dev/null bs=1M count=1`.

Example of a scenario-backed case:

```yaml
- name: cli_mock_open_raises_on_event_log
  type: module_cli
  scenario:
    kind: verify_tpm
    pcrs:
      sha256: ["pcr0", "pcr1", "pcr2", "pcr3", "pcr4", "pcr5", "pcr6", "pcr7"]
    event_pcrs:
      sha256: ["pcr0", "pcr1", "pcr2", "pcr3", "pcr4", "pcr5", "pcr6", "pcr7"]
    event_log_open_error: mocked read failure
  expect_exit_nonzero: true
  expect_stdout_or_stderr_contains:
    - "mocked read failure"
```

Explicit `mocks:` are still supported for one-off cases. Mock targets can use `{module}` as a placeholder when the target module name is only known at runtime.

Scenario-generated passthrough rules can be marked as required, so the test fails if the expected mocked path is never actually hit. That prevents silent mock misses.

## Current Coverage

The current YAML catalog covers both utility scripts and hardware-facing flows.

Scenario-backed script coverage:

| Suite group | Main focus |
| --- | --- |
| `ethtool_test` | interface discovery, virtual vs physical NIC filtering, tool presence, link state, IPv4/IPv6, gateway and internet probes |
| `verify_tpm_measurements` | CLI validation, missing/invalid inputs, PCR/event matching, event-log read and parse failures |
| `capsule_ondisk_reporting_vars_check` | efivarfs variable parsing, attributes, capsule reporting entries, warn-only documentation of current behavior |
| `runtime_device_mapping_conflict_checker` | DTS and memmap inputs, conflict detection, parser failures, log-open failures, warn-only known behavior |
| `read_write_check_blk_devices` | raw disks, MBR/GPT layouts, precious partitions, write/readback/restore flows, destructive gating |
| `acs_info` | platform-info extraction and formatted output paths |
| `merge_jsons` | merge modes, missing/invalid inputs, ACS info interactions, output generation |

Generic and utility coverage:

| Suite group | Main focus |
| --- | --- |
| `apply_waivers` | waiver application logic and CLI behavior |
| `generate_acs_summary` | summary generation behavior |
| `logs_to_json_common`, `sr_logs_to_json_specific`, `edk2_logs_to_json_specific` | log parsing and JSON conversion flows |
| `json_to_html_common` plus suite-specific HTML suites | HTML report generation across FWTS, SCT, TPM, BSA, SBMR, SCMI, standalone, and related outputs |
| `merge_summary` | summary merge behavior |
| `parser_common` | shared parser helpers |
| `extract_capsule_fw_version` | firmware version extraction cases |
| `validate_sh` | shell script validation and environment checks |

Hardware-gated coverage:

- `ethtool_test_hardware`
- `verify_tpm_measurements_hardware`
- `capsule_ondisk_reporting_vars_check_hardware`
- `runtime_device_mapping_conflict_checker_hardware`
- `read_write_check_blk_devices_hardware`

These hardware suites use `skip_unless_paths_exist` and `skip_unless_commands_succeed` so they are skipped cleanly on machines that do not expose the required platform state.

## Adding A New Case

Recommended workflow:

1. Pick the existing YAML suite that already targets the script you want to cover.
2. Use the simplest case type that expresses the requirement.
   - Static check if only source structure matters.
   - `cli` if subprocess behavior matters and mocks are not needed.
   - `module_cli` if you need deterministic mocking or scenario-generated setup.
3. Reuse suite `defaults` for shared flags like `timeout_sec` or expected exit code.
4. Prefer a scenario builder if the domain already has one.
5. Use explicit `mocks:` only for narrow fault injection that is not worth promoting into a scenario builder yet.
6. Add `post_checks` when the script's output is file-based.
7. Run `python3 common/yaml_test_harness/report.py <target>` and inspect `common/reports/` if the case fails.

## Maintenance Notes

- Several suites exist in both hyphenated and underscored YAML filenames, for example `verify-tpm-measurements.yaml` and `verify_tpm_measurements.yaml`. Treat those as compatibility aliases and keep them synchronized when both are still required.
- Use `warn_only: true` for known current behavior that should remain visible in reports without blocking the run.
- Use `requires_destructive: true` only for cases that really touch hardware state, and gate them with `RUN_DESTRUCTIVE_HW_TESTS=1`.
- If a new domain starts accumulating repeated mocks and generated fixtures, add a proper scenario builder in `mock_loader.py` instead of duplicating low-level setup across many YAML cases.

