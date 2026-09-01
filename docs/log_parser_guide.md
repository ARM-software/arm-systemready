# SystemReady ACS Log Parser Guide

## Contents

1. [Purpose](#purpose)
2. [Before You Start](#before-you-start)
3. [Choose an Execution Mode](#choose-an-execution-mode)
4. [Prerequisites](#prerequisites)
5. [Normal Parser](#normal-parser)
6. [Standalone Parser](#standalone-parser)
7. [Supported Suites and Inputs](#supported-suites-and-inputs)
8. [Configuration and Waivers](#configuration-and-waivers)
9. [Output Files](#output-files)
10. [Schema Validation](#schema-validation)
11. [Packaging for a Partner](#packaging-for-a-partner)
12. [Main Components](#main-components)
13. [Exit Codes](#exit-codes)

## Purpose

The SystemReady ACS log parser converts collected suite logs into JSON, suite
HTML reports, a merged compliance result, and a combined ACS summary.

The parser provides two separate interfaces:

1. **Normal parser:** the original environment-integrated parser from the main
   branch. It auto-detects DT/SR and runs every applicable suite.
2. **Standalone parser:** an opt-in portable runner for selected suites. It uses
   explicit input options, defaults to SR mode, and does not require the original
   ACS target environment.

### Why Standalone Support Was Added

The normal parser is designed to run in the installed ACS environment. A
partner may instead have only copied results or individual logs on another
Linux system.

Standalone support allows that user to:

- run one selected suite or several selected suites;
- parse an ACS results directory or direct log files;
- run without `/usr/bin/log_parser`, `/mnt/acs_tests`, or
  `/mnt/yocto_image.flag`;
- select DT or SR explicitly when needed instead of using the parser host to
  infer it;
- check inputs and dependencies before parsing with `--doctor`;
- generate only the required output stages;
- validate raw suite JSON with `--schema`;
- apply waivers and include configuration metadata;
- publish output only after all requested stages succeed;
- package the parser and verify the package checksum.

The standalone addition does not replace the normal parser. Commands without
`--standalone` continue through the original main-branch flow.

## Before You Start

### How to Read Commands

- Replace text inside angle brackets, such as `<acs_results_directory>`, with a
  real path. Do not type the angle brackets.
- Text inside square brackets is optional. Do not type the square brackets.
- Keep paths containing spaces inside quotes.
- A standalone `--output` path must not exist before the run starts. Its parent
  directory may already exist.

### Open the Parser Directory

For a source checkout:

```bash
cd /path/to/syscomp_systemready/common/log_parser
```

For an extracted partner package:

```bash
cd /path/to/systemready-log-parser/common/log_parser
```

Unless a section explicitly says **repository root**, every
`./main_log_parser.sh` and dependency command in this guide runs from this
`common/log_parser` directory.

Confirm that the entry point is available:

```bash
./main_log_parser.sh --standalone --help
```

### Copy Only the Log-Parser Directory

`common/log_parser` is self-contained for parser execution. The suite registry,
registry helper, schema validator, merged-results schema, category files, parser
scripts, and Python requirements are all stored in this directory. A CI job may
copy or download only `common/log_parser`; it does not need `common/tools`.

Update existing CI commands to use these paths:

| Previous path | Current path |
|---|---|
| `common/tools/suite_registry.json` | `common/log_parser/suite_registry.json` |
| `common/tools/suite_registry.py` | `common/log_parser/suite_registry.py` |
| `common/tools/validate.py` | `common/log_parser/validate.py` |
| `common/tools/acs-results-schema.json` | `common/log_parser/acs-results-schema.json` |

The previous `common/tools` paths are no longer installed or packaged.

After copying the directory, verify the isolated layout from outside the source
repository:

```bash
cd /path/to/copied/log_parser
python3 -m pip install -r requirements.txt
./main_log_parser.sh --version
./main_log_parser.sh --standalone --list-suites
./validate.py --help
```

These commands load the entry point, registry, and validator directly from the
copied directory. A real parse should then use the same copied directory and the
required Python packages from `requirements.txt`.

## Choose an Execution Mode

| Requirement | Normal parser | Standalone parser |
|---|---|---|
| Original full parser behavior | Yes | No |
| Run every applicable suite | Yes | Only when explicitly selected |
| Run selected suites | No | Yes |
| Mode selection | Auto-detected | Optional; defaults to SR, or use `--mode DT`/`--mode SR` |
| Input | ACS results directory | ACS results directory or direct files |
| Installed ACS paths | Expected | Not required |
| Custom output directory | No | Yes |
| Dependency/input preflight | No | `--doctor` |
| Raw suite schema validation | No | Optional `--schema` |
| Output stages | Fixed | Selectable |

Use the normal parser when reproducing the existing complete ACS parser flow.
Use standalone when parsing copied results, selecting suites, supplying direct
logs, or running outside the installed ACS environment.

Use this decision rule:

```text
Need the original full run in its installed ACS environment?
  Yes -> normal parser
  No  -> standalone parser

Need one suite, several selected suites, direct files, or an explicit mode?
  Yes -> standalone parser
```

Do not combine normal positional syntax with standalone options. In particular,
`--suite`, `--mode`, and `--input-log` work only when `--standalone` is present.

### Three Different Standalone Decisions

```text
--standalone = how to run: use the portable runner
--mode       = what kind of results: DT or SR (optional; SR is the default)
--suite      = which tests to parse
```

`--standalone` does not mean DT or SR. `--mode` does not select a suite. All
three decisions are independent. If `--mode` is omitted, the runner selects SR
and prints a notice before continuing. DT results must use `--mode DT`.

## Prerequisites

### System Requirements

- Linux
- Bash
- Python 3.8 or newer
- Read access to collected logs
- Write access to the output parent directory
- At least 10 MiB free space for a standalone run

### Python Packages

From `common/log_parser`, install all parser packages with:

```bash
python3 -m pip install -r requirements.txt
```

The equivalent command from the repository or extracted package root is:

```bash
python3 -m pip install -r common/log_parser/requirements.txt
```

The requirements file installs every supported stage. Individual packages are
required only when the selected suites or output stages use them:

| Package | When it is mandatory |
|---|---|
| `chardet` | Parsing BSA, SBSA, SCT, BBSR-SCT, PFDI, or SCMI |
| `Jinja2` | Generating HTML, including the default standalone output |
| `matplotlib` | Generating HTML, including the default standalone output |
| `jsonschema` | Using `--schema` |
| `weasyprint` | Requesting the `pdf` output stage |

WeasyPrint may also require operating-system Cairo and Pango packages. A
JSON-only run needs only the dependencies used by its selected suite. Installing
the complete requirements file is recommended for a portable partner setup.

Using a virtual environment is recommended:

```bash
mkdir -p "$HOME/.venvs"
python3 -m venv "$HOME/.venvs/systemready-log-parser"
source "$HOME/.venvs/systemready-log-parser/bin/activate"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Keeping the virtual environment outside `common/log_parser` also prevents it
from being included in a partner archive.

## Normal Parser

The normal parser is the original main-branch behavior. It accepts positional
arguments, auto-detects mode, and considers every suite applicable to that
mode.

The normal flow in `main_log_parser.sh` uses host state and fixed suite log
paths rather than the registry's standalone input-discovery paths. It still uses
the bundled registry for metadata enrichment and compliance mapping. The
important boundaries are:

- `/mnt/yocto_image.flag` selects normal DT or SR behavior and the matching
  category file bundled beside `main_log_parser.sh`;
- the ACS config `Band`, not the host flag by itself, controls whether
  `acs_info.py` adds BMC firmware or PSCI version metadata;
- compliance is calculated for the full requirement set of the detected mode,
  including applicable suites that were not run.

### Normal Parser Syntax

Run from `common/log_parser`:

```bash
./main_log_parser.sh \
  <acs_results_directory> \
  [acs_config] \
  [system_config] \
  [waiver_json]
```

Square brackets mean optional. Do not type the brackets.

### Mandatory Normal Argument

| Position | Value | Meaning |
|---|---|---|
| 1 | ACS results directory | Directory containing collected ACS suite logs |

### Optional Normal Arguments

| Position | Value | Meaning |
|---|---|---|
| 2 | ACS config | Adds ACS metadata to the summary |
| 3 | System config | Adds system metadata to the summary |
| 4 | Waiver JSON | Applies approved waivers |

Because these arguments are positional, keep their order. To provide a waiver
without configs, pass empty placeholders for positions 2 and 3.

Example with a waiver but no configs:

```bash
./main_log_parser.sh \
  /path/to/acs_results \
  "" \
  "" \
  /path/to/waiver.json
```

### Basic Normal Run

```bash
./main_log_parser.sh /path/to/acs_results
```

### Normal Run With DT Configs and Waiver

```bash
./main_log_parser.sh \
  /path/to/acs_results \
  /path/to/acs_config_dt.txt \
  /path/to/system_config_dt.txt \
  /path/to/waiver.json
```

### Normal Run With SR Configs and Waiver

```bash
./main_log_parser.sh \
  /path/to/acs_results \
  /path/to/acs_config.txt \
  /path/to/system_config.txt \
  /path/to/waiver.json
```

### How Normal Mode Is Selected

The normal parser checks the parser machine:

```text
/mnt/yocto_image.flag exists     -> DT mode
/mnt/yocto_image.flag is absent  -> SR mode
```

It then uses the matching category file beside `main_log_parser.sh`:

```text
DT -> <log_parser_directory>/test_categoryDT.json
SR -> <log_parser_directory>/test_category.json
```

Check what the normal parser will select before running it:

```bash
if [ -f /mnt/yocto_image.flag ]; then
  echo "Normal parser will use DT mode"
else
  echo "Normal parser will use SR mode"
fi
```

The ACS config filename and its `Band` value do **not** select normal mode. For
example, passing `acs_config_dt.txt` on a machine without
`/mnt/yocto_image.flag` still runs the normal parser in SR mode. Use standalone
with explicit `--mode DT` when parsing copied DT results on such a machine.

The normal interface does not accept standalone options such as `--mode`,
`--suite`, `--input-log`, `--doctor`, `--schema`, or `--output`.
Without `--standalone`, the original script treats its first argument as the ACS
results path, so do not try to pass named standalone options to a normal run.

### What the Normal Parser Does

1. Creates or reuses `<acs_results>/acs_summary`.
2. Gathers ACS and system information.
3. Checks and parses every mode-applicable suite log.
4. Applies waivers when the fourth argument was supplied.
5. Generates suite JSON and HTML.
6. Merges all generated suite JSON.
7. Calculates compliance for the full mode requirement set.
8. Generates the combined HTML summary.
9. Attempts PDF generation on the DT path.

The normal parser writes to `<acs_results>/acs_summary`. Remove or move stale
output before a clean rerun when old artifacts must not be retained.

## Standalone Parser

Standalone is selected only by adding `--standalone`. It requires input and
suite selection. Mode is optional: SR is used by default, while DT must be
selected with `--mode DT`.

`--doctor` follows the preflight branch and exits without parsing or creating
output. A real run writes into a temporary directory and publishes the requested
output path only after every selected stage succeeds.

### Standalone Syntax

```bash
./main_log_parser.sh \
  --standalone \
  [--mode <DT|SR>] \
  --input-log <acs_results_directory_or_log_file> \
  --suite <suite_name> \
  [optional_arguments]
```

### Mandatory Standalone Arguments

| Argument | Meaning |
|---|---|
| `--standalone` | Select the portable standalone runner |
| `--input-log PATH` | Supply one ACS results directory or direct log files |
| `--suite NAME` or `--suites NAMES...` | Select suites to execute |

`--output PATH` is also mandatory when direct files are supplied. It is
optional when `--input-log` is an ACS results directory.

The informational commands `--help`, `--list-suites`, and `--version` exit
without parsing, so they do not require mode, input, suite, or output options.

### Optional Standalone Arguments

| Argument | Meaning |
|---|---|
| `--mode DT\|SR` | Select DT or SR; if omitted, SR is used and a notice is printed |
| `--output PATH` | Write to this new directory |
| `--acs-config PATH` | Add ACS metadata and validate its Band against mode |
| `--system-config PATH` | Add system metadata |
| `--waiver PATH` | Apply this waiver JSON to selected suites |
| `--test-category PATH` | Override the bundled mode category file |
| `--outputs STAGES` | Select `json`, `html`, `summary`, and/or `pdf` |
| `--schema` | Validate generated raw suite JSON |
| `--doctor` | Check readiness and exit without parsing |
| `--list-suites` | Print canonical suite names and exit |
| `--version` | Print the complete log parser release version and exit |

Compatibility spellings `--acs_config`, `--system_config`, `--waiver-json`,
and `--waiver_json` are accepted. New commands should use the hyphenated forms
shown above.

### How `--input-log` Works

`--input-log` has two clear forms.

#### Form 1: ACS Results Directory

Pass exactly one directory:

```bash
--input-log /path/to/acs_results
```

The registry checks the exact relative paths registered for each selected suite.
It does not recursively search the directory for matching filenames. A log that
exists at a different path is treated as missing. This form supports one suite,
multiple suites, and suite groups.

The parser also automatically discovers the two external roots relative to the
results directory:

```text
<run_directory>/
|-- acs_results/    <- value passed to --input-log
|-- fw/             <- capsule-update logs
`-- os-logs/        <- OS test directories
```

For example, with:

```text
--input-log /data/run/acs_results
```

the parser automatically uses:

```text
results logs  -> /data/run/acs_results
capsule logs  -> /data/run/fw
OS logs       -> /data/run/os-logs
```

No extra root options are required. Keep `acs_results`, `fw`, and `os-logs` as
sibling directories in the collected run layout.

If one suite's logs use a different layout, supply those files directly. If
several suites use a different layout, either arrange them in the registered
layout or update their standalone paths in
`common/log_parser/suite_registry.json` before packaging the parser. These input
discovery paths do not change the normal parser's fixed log locations.

#### Form 2: Direct Log Files

Pass one or more files for exactly one executable suite:

```bash
--input-log /path/to/BsaResults.log
```

For suites with more than one possible input, named values avoid ambiguity:

```bash
--input-log uefi=/path/to/BsaResults.log \
--input-log kernel=/path/to/BsaResultsKernel.log
```

Direct-file mode requires `--output`. It cannot select multiple suites or a
suite group. Use an ACS results directory for those cases.

With several unnamed files, direct inputs are assigned in the registry's input
order. With one unnamed file, the runner assigns it to the suite's only required
file input when exactly one exists; otherwise it uses the first registered file
input. Use the names in the [Direct Input Names](#direct-input-names) table
whenever a suite has multiple inputs. This prevents a kernel or supporting log
from being assigned incorrectly.

`OS-TESTS` consumes an OS-log directory, so run it from the ACS results
directory layout rather than direct files.

### Standalone Mode Selection

```text
--mode DT -> SystemReady Devicetree collected results
--mode SR -> non-Devicetree SystemReady collected results
omitted   -> SR mode by default
```

Mode controls suite availability, bundled category selection, requirement
levels, config Band validation, mode-sensitive parsers, and merged compliance.
Standalone never guesses mode from the parser host. When `--mode` is omitted,
it uses the deterministic SR default and prints:

```text
INFO: --mode was not provided; standalone parser will run in SR mode by default.
```

For an SR run, `--mode` may therefore be omitted:

```bash
./main_log_parser.sh \
  --standalone \
  --input-log /path/to/acs_results \
  --suite SBSA \
  --output /path/to/new-sbsa-output
```

Examples:

- `SBSA` is SR-only.
- `PFDI` is DT-only.
- Selecting a suite in the wrong mode fails before parsing.

If an ACS config is available, inspect its `Band` field:

```bash
grep -i '^Band:' /path/to/acs_config.txt
```

Use `--mode DT` when the value contains `SystemReady Devicetree`. Use
`--mode SR` for the non-Devicetree `SystemReady band`. If no config is
available, obtain the band from whoever collected the results; do not infer it
from the machine that is only parsing the copied logs.

### List Suites

```bash
./main_log_parser.sh --standalone --list-suites
```

### Check the Log Parser Version

```bash
./main_log_parser.sh --version
```

Example when the parser release version is `1.0.0`:

```text
SystemReady ACS Log Parser 1.0.0
```

The standalone form reports the same whole-parser version:

```bash
./main_log_parser.sh --standalone --version
```

`LOG_PARSER_VERSION` is hardcoded once near the top of `main_log_parser.sh`.
Release owners must update that value when publishing a new log parser release.
The version identifies the complete packaged parser, not an individual suite,
ACS release, Git commit, or SystemReady specification version.

### First Standalone Run

Start with one suite and a new output path. These shell variables make it clear
which paths must be replaced:

```bash
RESULTS=/path/to/acs_results
OUTPUT=/path/to/new-bsa-output
```

Check the exact intended run first:

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log "$RESULTS" \
  --suite BSA \
  --output "$OUTPUT" \
  --doctor
```

If the preflight result is `PASS`, run the same command without `--doctor`:

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log "$RESULTS" \
  --suite BSA \
  --output "$OUTPUT"
```

Do not create `OUTPUT` yourself. Standalone publishes that directory after the
requested parsing and reporting stages finish successfully.

### BSA From an ACS Results Directory

When both registered BSA logs exist, both are parsed into one `bsa.json`:

```text
uefi/BsaResults.log
linux_acs/bsa_acs_app/BsaResultsKernel.log
```

Command:

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log /path/to/acs_results \
  --suite BSA \
  --output /path/to/new-bsa-output
```

BSA can run when at least one registered BSA log exists. If only the kernel log
is provided directly, name it explicitly with `kernel=`.

### Multiple Suites From an ACS Results Directory

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log /path/to/acs_results \
  --suites BSA FWTS SCT \
  --output /path/to/new-multi-suite-output
```

These selection forms are equivalent:

```text
--suites BSA FWTS SCT
--suite BSA,FWTS,SCT
--suite BSA --suite FWTS --suite SCT
```

### BSA From Two Direct Logs

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log uefi=/path/to/BsaResults.log \
  --input-log kernel=/path/to/BsaResultsKernel.log \
  --suite BSA \
  --output /path/to/new-bsa-output
```

### Complete Standalone BSA Example

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log /path/to/acs_results \
  --suite BSA \
  --output /path/to/new-bsa-output \
  --acs-config /path/to/acs_config_dt.txt \
  --system-config /path/to/system_config_dt.txt \
  --waiver /path/to/waiver.json \
  --schema
```

This command discovers BSA logs, applies BSA waivers, enriches metadata,
validates raw BSA JSON, generates suite HTML, and creates selected-only merged
and combined summaries.

### Doctor Preflight

`--doctor` checks suite/mode compatibility, the registry, parser files, required
dependencies, required input paths, output safety, write access, and free space.
It does not parse log contents or create final output.

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log /path/to/acs_results \
  --suite BSA \
  --output /path/to/new-output \
  --schema \
  --doctor
```

A doctor PASS means the run can start. It does not guarantee that log contents
or generated JSON will pass parsing and schema validation.

Use the same mode, input, suites, output stages, schema flag, configs, waiver,
and output path planned for the real run. Then remove only `--doctor`. This
ensures the preflight checks the dependencies and files for the intended run.

### Output Selection

Default standalone stages are:

```text
json,html,summary
```

| Command value | Effective stages | Main result |
|---|---|---|
| Omit `--outputs` | JSON, HTML, summary | Raw suite JSON, suite HTML, merged JSON, combined HTML |
| `--outputs json` | JSON | Raw suite JSON only |
| `--outputs html` | JSON, HTML | Raw suite JSON and suite HTML |
| `--outputs json,html` | JSON, HTML | Same as `--outputs html` |
| `--outputs summary` | JSON, HTML, summary | Default output without naming every stage |
| `--outputs pdf` | JSON, HTML, summary, PDF | Complete output including `acs_summary.pdf` |

JSON is always included. Summary automatically includes HTML, and PDF
automatically includes summary. Separate multiple stage names with commas, for
example `--outputs json,html`, not spaces. PDF requires WeasyPrint.

An HTML-stage run (`--outputs html` or `--outputs json,html`) does not create
`merged_results.json` or the combined `acs_summary.html`; those files belong to
the summary stage.

### Existing Output

Standalone requires a new output path. If the requested path already exists,
the command fails before parsing.

To rerun, do one of these before starting the parser:

1. Delete the stale output directory after confirming it is no longer needed.
2. Move the stale output directory to an archive location.
3. Choose a different `--output` path.

The parser never deletes or replaces an existing directory.

When `--input-log` is an ACS results directory and `--output` is omitted, the
default is `<acs_results>/acs_summary`. That default must not already exist.

## Supported Suites and Inputs

Paths in this table are relative to the directory passed through `--input-log`.
Entries beginning with `../fw/` or `../os-logs/` resolve through sibling
directories beside that input directory.

| Canonical suite | Mode | Registered input | Input rule |
|---|---|---|---|
| `BSA` | DT, SR | `uefi/BsaResults.log`; kernel alternatives | At least one |
| `SBSA` | SR | `uefi/SbsaResults.log`; `linux/SbsaResultsKernel.log` | At least one |
| `FWTS` | DT, SR | `fwts/FWTSResults.log` | Required |
| `SCT` | DT, SR | `sct_results/Overall/Summary.log`; optional `edk2-test-parser/edk2-test-parser.log` | Summary required |
| `BBSR-FWTS` | DT, SR | `bbsr/fwts/FWTSResults.log` | Required |
| `BBSR-SCT` | DT, SR | `bbsr/sct_results/Overall/Summary.log`; optional `edk2-test-parser/edk2-test-parser-bbsr.log` | Summary required |
| `BBSR-TPM` | DT, SR | `bbsr/tpm2/verify_tpm_measurements.log` | Required |
| `PFDI` | DT | `uefi/pfdiresults.log` | Required |
| `SCMI` | DT | `linux_acs/scmi_acs_app/arm_scmi_test_log.txt` | At least one; unavailable raw transport is `Not Run` |
| `SBMR-IB` | SR | `sbmr/sbmr_in_band_logs/output.xml`; optional `sbmr/sbmr_in_band_logs/report.html` | XML required |
| `SBMR-OOB` | SR | `sbmr/sbmr_out_of_band_logs/output.xml`; optional `sbmr/sbmr_out_of_band_logs/report.html` | XML required |
| `POST-SCRIPT` | DT | `post-script/post-script.log` | Required |
| `DT-KSELFTEST` | DT | `linux_tools/dt_kselftest.log` | Required |
| `DT-VALIDATE` | DT | `linux_tools/dt-validate-parser.log` | Required |
| `ETHTOOL-TEST` | DT | `linux_tools/ethtool-test.log` | Required |
| `READ-WRITE-CHECK-BLK-DEVICES` | DT | `linux_tools/read_write_check_blk_devices.log` | Required |
| `CAPSULE-UPDATE` | DT | Required `../fw/capsule_test_results.log`; optional `../fw/capsule-update.log` and `../fw/capsule-on-disk.log` | Results required |
| `PSCI` | DT | `linux_tools/psci/psci_kernel.log` | Required |
| `SMBIOS` | DT | `sct_results/Overall/Summary.log` | Required |
| `NETWORK-BOOT` | DT | `network_boot/network_boot_results.log` | Required |
| `RUNTIME-DEV-MAP` | DT | `linux_tools/runtime_device_mapping_conflict_test.log` | Required |
| `OS-TESTS` | DT, SR | `../os-logs/` directory; optional `post-script/post-script.log` | Directory required |

The **Input rule** column describes what the standalone parser must find when
that suite is selected. It is not the suite's Mandatory, Recommended, or
Extension compliance classification.

BSA kernel alternatives are:

```text
linux_acs/bsa_acs_app/BsaResultsKernel.log
linux/BsaResultsKernel.log
```

### How the Registry Is Used

`common/log_parser/suite_registry.json` is the standalone runner's suite
directory.
For each suite it defines:

- canonical name, accepted aliases, and DT/SR availability;
- exact input roots and candidate paths;
- parser and HTML-generator scripts;
- raw JSON and HTML filenames;
- waiver/compliance mapping and the matching merged suite schema definition;
- grouped-suite expansion and required Python modules.

When a user selects BSA, for example, the runner reads the BSA registry entry,
checks its UEFI and kernel candidates, runs the registered BSA parser, and
writes the registered outputs. `--doctor` uses the same entry and prints an
error containing the expected path when a required input is missing.

Changing a registered input path changes standalone discovery for that suite.
It does not change the normal parser, which retains its original paths. Changing
a canonical suite name is a larger compatibility change because category files,
schemas, waivers, parser-emitted names, and report labels may also contain that
name.

Registered candidate paths must remain relative to their assigned `results`,
`firmware`, or `os_logs` root. Absolute paths and paths containing `..` are
rejected. Use direct `--input-log` files instead of placing machine-specific
absolute paths in a shared registry.

### Suite Groups

| Group | Mode | Expansion |
|---|---|---|
| `SBMR` | SR | `SBMR-IB`, `SBMR-OOB` |
| `STANDALONE` | DT | The nine DT tests listed below |

`STANDALONE` expands to:

```text
DT-KSELFTEST
DT-VALIDATE
ETHTOOL-TEST
READ-WRITE-CHECK-BLK-DEVICES
CAPSULE-UPDATE
PSCI
SMBIOS
NETWORK-BOOT
RUNTIME-DEV-MAP
```

The uppercase `STANDALONE` value is a suite group. It is different from the
lowercase `--standalone` option that selects the portable runner.

### Direct Input Names

| Suite | Names accepted before `=` |
|---|---|
| `BSA`, `SBSA` | `uefi`, `kernel` |
| `SCT`, `BBSR-SCT` | `log`, `edk2` |
| `SBMR-IB`, `SBMR-OOB` | `log`, `report` |
| `CAPSULE-UPDATE` | `update`, `on_disk`, `results` |
| Other direct-file suites | `log` |

## Configuration and Waivers

### ACS Config

ACS config is optional. It supplies summary metadata. Standalone validates a
provided `Band` against the selected mode, including the default SR mode.

Expected names:

```text
DT -> acs_config_dt.txt
SR -> acs_config.txt
```

`--mode` selects DT or SR; the filename does not. If `--mode` is omitted, SR is
selected. The runner reads the ACS config's `Band` value and stops with exit
code 3 if that value conflicts with the selected mode. A nonstandard filename
produces only a naming warning when its content matches the selected mode.

### System Config

System config is optional and supplies system metadata.

Expected names:

```text
DT -> system_config_dt.txt
SR -> system_config.txt
```

These filenames are conventions used by the collection environment. The runner
copies a supplied config into the output using the mode-appropriate filename.

The standalone runner reads machine information only from supplied configs and
archived result logs. It does not inspect the parser host with `dmidecode`.

### Waiver JSON

Waivers are optional. They apply only when a waiver file is supplied. A waiver
does not remove a test; it records the approved reason and updates compliance
according to the existing waiver logic and category waivability.

Minimal structure:

```json
{
  "Suites": [
    {
      "Suite": "BSA",
      "TestSuites": [
        {
          "TestSuite": "TIMER",
          "TestCases": [
            {
              "Test_case": "B_TIME_02 : 407",
              "Reason": "Approved platform-specific waiver reason."
            }
          ]
        }
      ]
    }
  ]
}
```

Use precise suite, test-suite, test-case, and subtest identifiers from generated
JSON. Keep waiver reasons explicit and reviewable.

Before parsing, standalone verifies that the waiver file is valid JSON with a
top-level `Suites` array. An unreadable, malformed, or incorrectly structured
waiver file stops with exit code 3 and no output is published. This input check
does not guarantee that valid waiver entries match the selected suite results.

### Category Files

Standalone defaults to bundled category files:

```text
DT -> common/log_parser/test_categoryDT.json
SR -> common/log_parser/test_category.json
```

Use `--test-category` when logs belong to a release with a different category
file. The selected file is used by waiver handling, raw metadata enrichment,
and merged compliance generation.

The normal parser uses the bundled category file selected by its auto-detected
mode. That file is also applied to individual suite JSON files before they are
merged.

## Output Files

### Normal Output

```text
<acs_results>/acs_summary/
```

Final individual suite JSON files are stored in
`<acs_results>/acs_summary/acs_jsons/`. When a suite and test-suite entry matches
the selected category file, each corresponding test result receives the same
available `Test_suite_info`, `Waivable`, `SRS scope`, and
`Main Readiness Grouping` metadata used in `merged_results.json`. For example,
`Test_suite_info` is added only when the matching category row provides a
`Description`. An entry without a category match is left unchanged and is
reported by the enrichment step.

### Standalone Output

```text
<output>/
|-- acs_jsons/
|   |-- <suite>.json
|   |-- acs_info.json              # summary stage
|   `-- merged_results.json        # summary stage
|-- html_detailed_summaries/
|   |-- <suite>_detailed.html      # HTML stage
|   |-- <suite>_summary.html       # HTML stage
|   `-- acs_summary.html           # summary stage
|-- config/                        # supplied configs
`-- acs_summary.pdf                # PDF stage
```

Most suites create the registry's suite JSON filename. `OS-TESTS` creates one
`ethtool_test_<OS-directory>.json` file for each discovered `os-logs/linux*`
directory instead.

For directory-input summary runs, a selected suite with no collected input is
recorded with its requirement-specific missing status in `merged_results.json`
and `acs_summary.html`. No raw suite JSON, suite HTML, or broken detailed-report
link is created for that suite. Missing inputs remain errors for `--doctor`,
direct-file input, and runs without the summary stage.

If an SCMI log explicitly reports that its raw transport is unavailable, the
SCMI parser's status `2` is handled in the same way and SCMI is reported as
`Not Run`. Other nonzero SCMI parser statuses remain parser failures.

Standalone builds output in a temporary sibling directory. It publishes the
final directory only after every requested stage succeeds. Failed or
interrupted runs remove the temporary directory.

### Band-Specific Merged Results JSON

```json
{
  "Suite_Name: acs_info": {
    "ACS Results Summary": {
      "Suite_Name: Mandatory  : BSA_compliance": "Compliant",
      "Suite_Name: Mandatory  : SBBR-FWTS_compliance": "Not Compliant: Failed 2",
      "Overall Compliance Result": "Not Compliant : Mandatory - (failed: SBBR-FWTS)"
    }
  },
  "Suite_Name: BSA": {
    "...": "bsa.json content"
  },
  "Suite_Name: SBBR-FWTS": {
    "...": "fwts.json content"
  }
}
```

SystemReady DT reports use `Suite_Name: EBBR-FWTS` and
`Suite_Name: EBBR-SCT`; SystemReady SR reports use the corresponding
`Suite_Name: SBBR-FWTS` and `Suite_Name: SBBR-SCT` keys. Their compliance
summary keys use the same band-specific prefix: `EBBR-FWTS_compliance` and
`EBBR-SCT_compliance` for DT, or `SBBR-FWTS_compliance` and
`SBBR-SCT_compliance` for SR. Plain `FWTS_compliance` and `SCT_compliance`
summary keys are not emitted or accepted.

The suite names inside `Overall Compliance Result` use the same display
prefix. For example, a failing SCT run is reported as `EBBR-SCT` for DT or
`SBBR-SCT` for SR; compliant suites are not included in the failure list.

Plain `Suite_Name: FWTS` and `Suite_Name: SCT` merged wrappers are rejected;
there is no compatibility fallback for those keys. The obsolete DT wrappers
`Suite_Name: BBR-FWTS` and `Suite_Name: BBR-SCT` are also rejected; DT uses
`EBBR` exclusively. Mixed EBBR/SBBR wrappers, or wrappers that disagree with
the report Band, are rejected rather than silently choosing a prefix.

### What to Inspect After a Run

For the default stages:

1. Open `<output>/html_detailed_summaries/acs_summary.html` for the combined
   selected-suite summary.
2. Open the corresponding `*_detailed.html` file in
   `<output>/html_detailed_summaries/` for test-level details.
3. Inspect `<output>/acs_jsons/merged_results.json` for the selected merged
   compliance result.
4. Inspect the suite JSON in `<output>/acs_jsons/` for raw parsed results.

If only `--outputs json` was requested, steps 1 through 3 are intentionally not
available.

### Shared Report Interface

`common/log_parser/report_ui.py` applies the same offline, self-contained
interface to normal and standalone suite reports. Detailed suite reports turn
their overview table into one compact test-result progress summary when
JavaScript is available, while the original table remains as the no-JavaScript
fallback. The consolidated ACS summary uses the same progress presentation and
places two suite summaries per row on wide screens and one per row on narrow
screens.

- Detailed reports provide search, one-click status filters, matching-result
  counts, test-suite or test-case navigation as appropriate, reset, print/PDF,
  and expand/collapse controls. Small reports start expanded; large reports keep
  their performance-oriented collapsed defaults.
- Status buttons are discovered from result, status, and outcome fields, so new
  status text does not require a UI code change. `All` is selected initially.
- Suite profiles retain suite-specific data and hierarchy while presenting
  suite, case, description, reason, and suite-information fields through one
  consistent context-card layout, color, and type scale. Suite cards use a
  `Test suite` label, while case cards use `Test case`; suite and sub-suite
  names appear once in case metadata. Multi-line suite information remains a
  list.
- Detailed reports omit the legacy result-distribution chart and count-card
  overview. Their compact summary keeps every reported status, including zero
  and future statuses, with the existing status colors. A companion breakdown
  lists every test suite or test case, including zero-failure units, without an
  internal scroll area. Tables remain left-aligned, status pills stay compact,
  and wide evidence columns scroll on narrow screens.
- SCT source locations and FWTS/SCT reasons use disclosures without removing the
  complete content from the HTML.
- Press `/` to focus report search and `Escape` to clear it.
- The consolidated summary embeds sanitized suite-summary bodies and places its
  sticky suite navigator directly below `Test Summaries`, without nested HTML
  documents or duplicated scripts.
- The responsive print layout requires no network resources.

#### Report UI Browser Smoke Test

The browser smoke test creates synthetic SCT, FWTS, BSA, Standalone,
Post-script, SBMR, and consolidated summary reports, applies the shared
interface, and opens them in headless Chromium. It verifies compact summary
totals, progress ratios, complete suite or case failure breakdowns, zero and
dynamic statuses, desktop and mobile layout, status filters and counts,
small-report collapse/expand behavior, test-suite and test-case navigation,
normalized suite information, reason disclosures, current-view printing, text
alignment, and detailed-report links. It tests browser behavior; the parser
suites separately verify JSON and parsed results.

Run it from the repository root with `chromium` or `chromium-browser` available
on `PATH`:

```bash
python3 common/acs_test_framework_runner/report_ui_browser_smoke.py
```

A successful run prints `report UI browser smoke: PASS`.

### Compliance Result Versus Process Success

`Standalone run result: PASS` means the requested report stages completed.
For directory-input summary runs, selected missing or non-runnable suites may
be recorded as `Not Run` or `Not Compliant: not run`; inspect merged compliance.
It does not mean every ACS test passed. Test failures remain in JSON, HTML, and
compliance output.

## Schema Validation

The repository has one schema command, `common/log_parser/validate.py`. Select
what you are validating with its first argument:

- `merged` validates a complete normal-parser `merged_results.json`.
- `raw` validates one or more individual suite JSON files.

A selected-suite standalone `merged_results.json` intentionally contains only
the selected compliance entries. The unchanged full merged schema requires the
complete normal-parser compliance matrix, so do not use `merged` validation as
the schema result for a selected standalone run. Use standalone `--schema` or
`validate.py raw` for its generated suite JSON files.

### Validate During a Standalone Run

Add `--schema` to a standalone run to validate each generated raw suite JSON:

```bash
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log /path/to/acs_results \
  --suite BSA \
  --output /path/to/new-output \
  --schema
```

Each executable suite is validated with the same suite definition used for its
entry in `merged_results.json`. The only wrapper-specific definition is for the
nine standalone child files: each raw file is an object with `test_results` and
`suite_summary`, while merged output combines their validated result entries in
the `Suite_Name: Standalone` array. This does not run the merged-root schema
against `merged_results.json`.

Schema validation is strict. Missing required category metadata, fields that the
merged contract does not allow, or an invalid suite structure fails the run
before final output is published. Use the category file matching the ACS release
that produced the logs. Raw-only schema exceptions are not applied.

Running without `--schema` allows parsing without this strict raw-suite check.
It does not prove that the raw suite JSON satisfies the schema.

Both raw-suite and merged validation group repeated failures by suite and issue.
For each issue, `count` is the total number of failures, `*at` shows up to five
example JSON paths, and `*... and N more` reports how many additional paths were
hidden. `Error Counts by Suite` retains the complete totals. Raw validation also
lists every checked file and identifies files skipped because no suite schema is
registered for their filename.

### Validate Existing JSON Files

From `common/log_parser`, validate a completed normal-parser merged result with:

```bash
./validate.py merged \
  /path/to/acs_summary/acs_jsons/merged_results.json
```

Validate one raw suite JSON, or several raw suite JSON files, with:

```bash
./validate.py raw /path/to/acs_summary/acs_jsons/bsa.json

./validate.py raw /path/to/acs_summary/acs_jsons/*.json
```

The validator uses `common/log_parser/acs-results-schema.json` and
`common/log_parser/suite_registry.json` by default. In `merged` mode, use
`--schema PATH` only when intentionally testing an alternate schema. In `raw`
mode, use `--registry PATH` only when intentionally testing alternate raw-file
mappings and schema references. The glob form may report `merged_results.json`
and `acs_info.json` as skipped because they are not raw suite JSON files.

See [ACS JSON Schema Validation Guide](acs_schema_guide.md) for schema
selection, output interpretation, and exit codes.

## Packaging for a Partner

From the repository root:

```bash
common/log_parser/package_standalone.sh \
  /path/to/systemready-log-parser-standalone.tar.gz
```

The command creates:

```text
systemready-log-parser-standalone.tar.gz
systemready-log-parser-standalone.tar.gz.sha256
```

Verify and extract:

```bash
cd /path/containing/the/package
sha256sum -c systemready-log-parser-standalone.tar.gz.sha256
tar -xzf systemready-log-parser-standalone.tar.gz
cd systemready-log-parser/common/log_parser
python3 -m pip install -r requirements.txt
./main_log_parser.sh --version
./main_log_parser.sh --standalone --help
```

The package includes parser scripts, the suite registry, schema validator,
category files, schema, the log-parser and schema guides, requirements, and the
license. All runtime support files remain under
`common/log_parser` in the archive; no `common/tools` directory is required.
The complete `common/log_parser` directory is archived as one unit, so
suite-specific `logs_to_json.py` and `json_to_html.py` files do not need a
second, manually maintained package list.

The archive is intended for standalone execution. Its normal parser path still
expects the original ACS runtime environment; category files are resolved from
the extracted `common/log_parser` directory.

## Main Components

| Component | Responsibility |
|---|---|
| `main_log_parser.sh` | Owns the parser release version, dispatches standalone, or runs the original normal flow |
| `standalone_runner.py` | Portable orchestration and validation |
| `common/log_parser/suite_registry.json` | Suite names, aliases, modes, paths, inputs, outputs, and schemas |
| `common/log_parser/suite_registry.py` | Shared registry loading, alias resolution, and suite lookup helpers |
| `logs_to_json.py` | Suite-specific log parsing |
| `apply_waivers.py` | Existing waiver application |
| `enrich_suite_json.py` | Adds category metadata to raw suite JSON |
| `common/log_parser/validate.py` | Validates merged or raw suite JSON and formats grouped schema errors |
| `json_to_html.py` | Suite-specific HTML generation |
| `merge_jsons.py` | Merges results and calculates compliance |
| `generate_acs_summary.py` | Generates combined HTML summary |

## Exit Codes

Standalone uses these exit codes:

| Code | Meaning |
|---|---|
| `0` | Requested parser operation completed |
| `2` | Command-line syntax error |
| `3` | Invalid mode, suite, registry, config, or input |
| `4` | Missing or unusable dependency |
| `5` | Parser, waiver, enrichment, or JSON failure |
| `6` | Raw suite schema validation failure |
| `7` | HTML, merge, summary, or PDF failure |
| `8` | Output preparation or publication failure |

The normal parser retains its existing shell exit behavior.
