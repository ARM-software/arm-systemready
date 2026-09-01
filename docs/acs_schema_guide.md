# ACS JSON Schema Validation Guide

This guide explains how to validate complete ACS merged results and individual
suite JSON files with the single SystemReady schema validator.

## Contents

1. [Files and Prerequisites](#files-and-prerequisites)
2. [Choose Merged or Raw Validation](#choose-merged-or-raw-validation)
3. [Validate Merged Results](#validate-merged-results)
4. [Validate Raw Suite JSON](#validate-raw-suite-json)
5. [Understand the Report](#understand-the-report)
6. [How Schema Selection Works](#how-schema-selection-works)
7. [Schema Rules and Error Tags](#schema-rules-and-error-tags)
8. [Exit Codes](#exit-codes)
9. [Maintainer Notes](#maintainer-notes)

## Files and Prerequisites

The schema tools are kept beside the parser so a copied `common/log_parser`
directory remains self-contained:

| File | Purpose |
|---|---|
| `common/log_parser/validate.py` | Validates merged or raw JSON and formats errors |
| `common/log_parser/acs-results-schema.json` | Draft 2020-12 merged and suite contracts |
| `common/log_parser/suite_registry.json` | Maps raw filenames and suites to schema definitions |
| `common/log_parser/suite_registry.py` | Shared registry lookup helpers |

Run commands in this guide from the repository root. Python 3 and the
`jsonschema` package are required:

```bash
python3 -m pip install -r common/log_parser/requirements.txt
common/log_parser/validate.py --help
```

Paths containing spaces must be quoted.

## Choose Merged or Raw Validation

Use an explicit command so the validator never guesses the JSON type:

| Input | Command | What is checked |
|---|---|---|
| Complete `merged_results.json` | `validate.py merged` | Full root, `acs_info`, suite keys, compliance summary, and every included suite |
| Individual suite JSON such as `bsa.json` | `validate.py raw` | The suite definition registered for that filename |

Here, **complete** means the normal parser's full compliance matrix. A
selected-suite standalone `merged_results.json` intentionally omits unselected
compliance entries and is therefore not a full merged-schema validation target.
Use standalone `--schema` or `validate.py raw` for standalone suite JSON.

Schema validation checks JSON structure and field values. It does not decide
whether ACS tests passed. A structurally valid JSON file may contain failed ACS
tests, and a schema failure means the generated JSON does not satisfy its data
contract.

## Validate Merged Results

### Standard Command

```bash
common/log_parser/validate.py merged \
  "/path/to/acs_results/acs_summary/acs_jsons/merged_results.json"
```

The default schema is `common/log_parser/acs-results-schema.json`.

Merged FWTS/SCT wrapper names are band-specific. SystemReady DT uses
`Suite_Name: EBBR-FWTS` and `Suite_Name: EBBR-SCT`; SystemReady SR uses
`Suite_Name: SBBR-FWTS` and `Suite_Name: SBBR-SCT`. Plain `FWTS`/`SCT`, obsolete
`BBR-*`, mixed-band, and opposite-band wrappers are rejected.

### Use a Different Schema

```bash
common/log_parser/validate.py merged \
  "/path/to/merged_results.json" \
  --schema "/path/to/candidate-schema.json"
```

### Show Fewer Example Paths

The complete error count is always retained. This option changes only how many
example locations are printed for each grouped issue:

```bash
common/log_parser/validate.py merged \
  "/path/to/merged_results.json" \
  --max-paths 2
```

## Validate Raw Suite JSON

Raw validation uses `common/log_parser/suite_registry.json` to choose the schema
definition from each file's basename.

### One Suite

```bash
common/log_parser/validate.py raw "/path/to/acs_jsons/bsa.json"
```

### Multiple Suites

```bash
common/log_parser/validate.py raw \
  "/path/to/acs_jsons/bsa.json" \
  "/path/to/acs_jsons/fwts.json" \
  "/path/to/acs_jsons/sct.json"
```

### Discover Selected Suites in a Directory

```bash
common/log_parser/validate.py raw \
  --json-dir "/path/to/acs_jsons" \
  --selected-suites BSA,FWTS,SCT
```

`--selected-suites` accepts canonical suite names and registered aliases. The
validator expands grouped suites and reports a missing generated JSON as an
error.

List the accepted canonical names with:

```bash
common/log_parser/suite_registry.py list
```

### Validate Every JSON in a Directory

```bash
common/log_parser/validate.py raw "/path/to/acs_jsons/"*.json
```

Only filenames registered as raw suite outputs are validated. Files such as
`acs_info.json` and `merged_results.json` are listed under `Skipped Files`. Use
the `merged` command only for a complete normal-parser `merged_results.json`;
validate selected standalone suite files with `raw`.

### During a Standalone Parser Run

The standalone parser invokes the same raw validator when `--schema` is used:

```bash
cd common/log_parser
./main_log_parser.sh \
  --standalone \
  --mode DT \
  --input-log "/path/to/acs_results" \
  --suite BSA \
  --output "/path/to/new-output" \
  --schema
```

The standalone flow parses and enriches the suite JSON before validating it.
Running `validate.py raw` directly validates the file as it exists; it does not
parse logs, add category metadata, apply waivers, or modify JSON.

## Understand the Report

Repeated errors are grouped by suite and issue. A report entry has this form:

```text
*suite=Suite_Name: BSA issue=MISSING_KEY: ... count=9
  *at=Suite_Name: BSA.test_results[0]
  *at=Suite_Name: BSA.test_results[1]
  *... and 7 more
```

Interpret it as follows:

- `suite` identifies the affected merged section or raw suite.
- `issue` identifies the schema rule that failed.
- `count` is the complete number of matching schema violations.
- `*at` shows up to five example JSON paths by default.
- `*... and N more` means the remaining paths were hidden, not ignored.
- `Error Counts by Suite` shows complete totals, including hidden paths.
- `Files Checked` records every raw file that was actually validated.
- `Skipped Files` records inputs whose filenames have no registry mapping.

A large `count` does not mean thousands of lines were printed. It means the
same structural problem occurs in many JSON entries.

## How Schema Selection Works

### Merged Mode

`merged` validates the whole document against the schema root. The root requires
`Suite_Name: acs_info`, permits only declared suite keys, and validates each
included suite with its referenced definition. OS suite keys may also match the
declared `Suite_Name: OS Tests - <name>` pattern.

### Raw Mode

`raw` follows this flow:

```text
raw filename
  -> suite_registry.json filename match
  -> registered schema fragment
  -> acs-results-schema.json suite definition
  -> grouped PASS or FAIL report
```

Examples:

| Raw filename | Schema definition |
|---|---|
| `bsa.json`, `sbsa.json` | `bsa_suite` |
| `fwts.json` | `fwts_suite` |
| `sct.json` | `sct_suite` |
| `bbsr_fwts.json` | `bbsr_fwts_suite` |
| `bbsr_sct.json` | `bbsr_sct_suite` |
| `bbsr_tpm.json` | `tpm_suite` |
| `pfdi.json` | `pfdi_suite` |
| `scmi.json` | `scmi_suite` |
| `sbmr_ib.json`, `sbmr_oob.json` | `sbmr_suite` |
| `post_script.json` | `post_script_suite` |
| `os_test.json`, `ethtool_test_*.json` | `os_tests_suite` |
| Registered standalone child JSON files | `raw_standalone_suite` |

The regular raw suites reuse the same definitions used by their merged suite
entries. The standalone child files use one wrapper because each raw child is
an object while merged output combines those entries under
`Suite_Name: Standalone`.

The FWTS/SCT compliance-summary keys are band-specific:

- SystemReady DT requires `EBBR-FWTS_compliance` and `EBBR-SCT_compliance`.
- SystemReady SR requires `SBBR-FWTS_compliance` and `SBBR-SCT_compliance`.
- Plain `FWTS_compliance` and `SCT_compliance` keys are rejected.
- `Overall Compliance Result` uses the same EBBR/SBBR suite names in its
  `not run` and `failed` lists.

These blocks are strict; missing required fields causes schema errors.

Renaming a raw file to an unregistered basename prevents automatic schema
selection. Keep the registered output name or update the registry deliberately.

## Schema Rules and Error Tags

The schema is intentionally strict. Most objects reject undeclared fields, and
required fields must have the expected type and spelling.

Common issue tags are:

| Issue | Meaning |
|---|---|
| `MISSING_KEY` | A required property is absent |
| `UNEXPECTED_KEY` | The JSON contains a property the contract does not permit |
| `TYPE_MISMATCH` | A value is the wrong JSON type |
| `ENUM` or `DISALLOWED_VALUE` | A value is outside the permitted set |
| `JSON_FILE` | The input is unreadable or is not valid JSON |
| `SCHEMA_FILE` | The schema is missing, unreadable, or invalid |

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Every requested validation passed |
| `1` | JSON failed schema validation, or a requested JSON/schema file was unusable |
| `2` | Invalid command, missing dependency, invalid registry, or no raw file could be validated |

Use the exit code in automation; do not search terminal text for `PASS`.

## Maintainer Notes

When adding or renaming a suite output:

1. Define or update the suite contract in
   `common/log_parser/acs-results-schema.json`.
2. Update the suite entry, output filename, and schema fragment in
   `common/log_parser/suite_registry.json`.
3. Keep parser script paths in the registry relative to
   `common/log_parser`.
4. Test the raw file with `validate.py raw`.
5. Test a complete merged artifact with `validate.py merged`.
6. Test the standalone package and the installed `log_parser` layout.

Do not add a second validator for a new suite. Extend the schema and registry so
the single validator handles it.
