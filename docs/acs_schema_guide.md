# ACS Merged Schema - Beginner Guide

This document explains the merged results JSON schema in plain language. It is meant for readers seeing the schema for the first time.

## 1) What this schema validates

The schema validates a single JSON file (merged results) that contains multiple test suites. Each suite appears under a key like:

- `Suite_Name: BSA`
- `Suite_Name: FWTS`
- `Suite_Name: SCT`
- `Suite_Name: SBMR`
- `Suite_Name: Standalone`
- `Suite_Name: SCMI`
- `Suite_Name: OS Tests - <name>`
- `Suite_Name: acs_info`

All suite objects are **strict**. Any unexpected key causes a schema error.

## 2) Top-level structure

Top-level object:
- Keys are suite names (strings). Each key maps to a suite object.
- Some suite names are fixed (BSA, FWTS, SCT, SBMR, Standalone, SCMI, PFDI, POST_SCRIPT, BBSR-*).
- OS Tests are flexible and use a pattern: `Suite_Name: OS Tests - <base_name>`.

## 3) Shared definitions (common building blocks)

### 3.1 Summary totals (lowercase)

Most suites use lowercase totals:

- `summary_totals_base` (optional fields):
  - `total_aborted`, `total_failed`, `total_failed_with_waiver`, `total_ignored`, `total_passed`, `total_skipped`, `total_warnings`

- `summary_totals` (required core fields):
  - `total_aborted`, `total_failed`, `total_failed_with_waiver`, `total_passed`, `total_skipped`, `total_warnings`
  - `total_ignored` is optional here

For SCT only, `total_ignored` is **required** by wrapping `summary_totals` with an extra `required` at the SCT usage sites.

### 3.2 BSA suite summary (capital keys)

BSA/SBSA/PFDI use capitalized keys:

- `bsa_suite_summary`:
  - `Total Rules Run`, `Passed`, `Passed (Partial)`, `Warnings`, `Skipped`, `Failed`, `PAL Not Supported`, `Not Implemented`, `Total_failed_with_waiver`

### 3.3 Test category metadata

Many suites require three test category fields on each test result:

- `test_category_base` (required on test_results items)
  - `Main Readiness Grouping`, `SRS scope`, `Waivable`

### 3.4 Base shapes

- `suite_base`:
  - `Suite_Name`

- `test_result_base`:
  - `Test_suite`, `Test_suite_description`, `Sub_test_suite` (optional)

- `test_case_base`:
  - `Test_case`, `Test_case_description`, `Test_result`, `Returned Status Code`, `reason`, `subtests` (as applicable)

- `subtest_base`:
  - Subtest fields used by multiple suites

## 4) Suite-specific shapes

### 4.1 BSA / SBSA / PFDI (BSA-style suites)

Suite object:
- `suite_summary` (bsa_suite_summary)
- `test_results` (array of `bsa_test_result`)

Each `bsa_test_result`:
- `Test_suite`
- `testcases` (array)
- `test_suite_summary` (bsa_suite_summary)
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

Each `bsa_test_case`:
- `Test_case`, `Test_case_description`, `Test_result`, `Test_case_summary`
- Optional: `subtests`, `waiver_reason`
- If `Test_result` is `FAILED (WITH WAIVER)`, `waiver_reason` is required

### 4.2 FWTS / BBSR-FWTS

Suite object:
- `suite_summary` (summary_totals)
- `test_results` (array of `fwts_test_result`)

Each `fwts_test_result`:
- `Test_suite`, `Test_suite_description`, `subtests`, `test_suite_summary` (summary_totals)
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

### 4.3 SCT / BBSR-SCT

Suite object:
- `suite_summary` (summary_totals **with required** `total_ignored`)
- `test_results` (array of `sct_test_result`)

Each `sct_test_result`:
- SCT-required fields: `Returned Status Code`, `Sub_test_suite`, `Test Entry Point GUID`, `Test_case`, `Test_case_description`, `Test_suite`, `reason`, `subtests`, `test_case_summary`, `test_result`
- `test_case_summary` uses summary_totals with **required** `total_ignored`
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

### 4.4 SBMR

Suite object:
- `suite_summary` (summary_totals)
- `test_results` (array of `sbmr_test_result`)

Each `sbmr_test_result`:
- `Test_suite`, `Test_cases`, `test_suite_summary` (summary_totals)
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

### 4.5 Standalone

Standalone suite is an array of independent test entries.

Each entry is either:
- A `standalone_test_result`, or
- A summary-only object containing `suite_summary`

`standalone_test_result` includes:
- `Test_suite`, `Test_suite_description`, `Test_case`, `Test_case_description`, `subtests`, `test_suite_summary`
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

### 4.6 OS Tests

OS Tests suites are **pattern-based**:
- `Suite_Name: OS Tests - <base_name>`

Suite object:
- `suite_summary` (summary_totals)
- `test_results` (array of `os_tests_test_result`)

Each `os_tests_test_result`:
- `Test_suite`, `Test_suite_description`, `Test_case`, `Test_case_description`, `subtests`, `test_suite_summary`
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

### 4.7 SCMI

Suite object:
- `suite_summary` (summary_totals)
- `test_results` (array of `scmi_test_result`)

Each `scmi_test_result`:
- `Test_suite`, `test_suite_summary`, `testcases`
- **Requires** `Main Readiness Grouping`, `SRS scope`, `Waivable` via `test_category_base`

Each `scmi_test_case`:
- `Test_case`, `Test_case_description`, `Test_result`
- Optional `reason`

### 4.8 POST_SCRIPT

Suite object:
- `suite_summary` (summary_totals)
- `test_results` (array of `standard_test_result`)

`standard_test_result`:
- `Test_suite`, `Test_suite_description`, `Sub_test_suite` (optional), `test_suite_summary` (summary_totals)
- **Does not require** `Main Readiness Grouping`, `SRS scope`, `Waivable`

### 4.9 acs_info

`Suite_Name: acs_info` contains:
- `System Info`
- `ACS Results Summary`

These blocks are strict; missing required fields causes schema errors.

## 5) Common error patterns

- Wrong key case: `Total_failed_with_waiver` vs `total_failed_with_waiver`
- Unexpected plural: `total_failed_with_waivers`
- Missing required keys because a suite uses a different structure
- Extra fields anywhere (schema is strict)

## 6) How to validate

Run:

`/data_nvme1n1/ashsha06/schema_changes/syscomp_systemready/common/log_parser/validate.sh \
  /data_nvme1n1/ashsha06/acs_results_template/acs_results/acs_summary/acs_jsons/merged_results.json \
  /data_nvme1n1/ashsha06/schema_changes/syscomp_systemready/common/log_parser/acs-merged-schema-doc.json`
