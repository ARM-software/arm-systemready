
# Applying Waivers to Test Suite Results

## Table of Contents

- [Introduction](#introduction)
- [Waiver Hierarchy](#waiver-hierarchy)
- [Waiver Templates](#waiver-templates)
  - [Suite-Level Waiver](#suite-level-waiver)
  - [TestSuite-Level Waiver](#testsuite-level-waiver)
  - [SubSuite-Level Waiver](#subsuite-level-waiver)
  - [TestCase-Level Waiver](#testcase-level-waiver)
  - [SubTest-Level Waiver](#subtest-level-waiver)
- [Examples](#examples)
- [Understanding the Waiver Application Process](#understanding-the-waiver-application-process)
- [Important Notes](#important-notes)

---

## Introduction

The `main_log_parser.sh` script is designed to automate the processing of test suite results and the application of waivers. Waivers are exceptions granted for certain tests due to specific reasons such as hardware constraints, non-applicable features, or known issues. Applying waivers helps in accurately representing the test outcomes by acknowledging these exceptions.

The script processes log files, applies waivers using the embedded `apply_waivers.py` script, and generates JSON and HTML summary reports.

---

## Waiver Hierarchy

Waivers can be applied at various levels within a test suite. The hierarchy is as follows:

1. **Suite-Level Waiver**: Applies to all failed subtests in the entire suite.
2. **TestSuite-Level Waiver**: Applies to all failed subtests within a specific test suite.
3. **SubSuite-Level Waiver**: Applies to all failed subtests within a specific sub-suite (applicable for suites like `SCT`, `Standalone`, `BBSR-SCT`, `BBSR-FWTS`).
4. **TestCase-Level Waiver**: Applies to all failed subtests within a specific test case (applicable for suites like `SCT`, `Standalone`, `BBSR-SCT`, `BBSR-FWTS`).
5. **SubTest-Level Waiver**: Applies to individual subtests based on `SubTestID` or `sub_Test_Description`.

Waivers are applied in the order listed above. If a waiver is applicable at multiple levels, the most specific waiver (lowest level) takes precedence.

---

## Waiver Templates

Below are the templates for defining waivers at different levels within the `waiver.json` file.

### Suite-Level Waiver

Applies to all failed subtests in the entire suite.

```json
{
    "Suites": [
        {
            "Suite": "SUITE_NAME",
            "Reason": "REASON_FOR_WAIVER"
        }
    ]
}
```

- **`Suite`**: Name of the test suite.
- **`Reason`**: Explanation for the waiver.

### TestSuite-Level Waiver

Applies to all failed subtests within a specific test suite.

```json
{
    "Suites": [
        {
            "Suite": "SUITE_NAME",
            "TestSuites": [
                {
                    "TestSuite": "TEST_SUITE_NAME",
                    "Reason": "REASON_FOR_WAIVER"
                }
            ]
        }
    ]
}
```

- **`TestSuite`**: Name of the test suite within the suite.
- **`Reason`**: Explanation for the waiver.


### SubSuite-Level Waiver

Applies to all failed subtests within a specific sub-suite. Applicable for suites like `SCT`, `Standalone`, `BBSR-SCT`, and `BBSR-FWTS`.

```json
{
    "Suites": [
        {
            "Suite": "SUITE_NAME",
            "TestSuites": [
                {
                    "SubSuite": {
                        "SubSuite": "SUB_SUITE_NAME",
                        "Reason": "REASON_FOR_WAIVER"
                    }
                }
            ]
        }
    ]
}
```

- **`SubSuite`**: Name of the sub-suite.
- **`Reason`**: Explanation for the waiver.

### TestCase-Level Waiver

Applies to all failed subtests within a specific test case. Applicable for suites like `SCT`, `Standalone`, `BBSR-SCT`, and `BBSR-FWTS`.

```json
{
    "Suites": [
        {
            "Suite": "SUITE_NAME",
            "TestSuites": [
                {
                    "TestCase": {
                        "Test_case": "TEST_CASE_NAME",
                        "Reason": "REASON_FOR_WAIVER"
                    }
                }
            ]
        }
    ]
}
```

- **`Test_case`**: Name of the test case.
- **`Reason`**: Explanation for the waiver.

### SubTest-Level Waiver

Applies to individual subtests based on `SubTestID` or `sub_Test_Description`.

```json
{
    "Suites": [
        {
            "Suite": "SUITE_NAME",
            "TestSuites": [
                {
                    "TestCase": {
                        "SubTests": [
                            {
                                "SubTestID": "SUB_TEST_ID",
                                "Reason": "REASON_FOR_WAIVER"
                            },
                            {
                                "sub_Test_Description": "SUB_TEST_DESCRIPTION",
                                "Reason": "REASON_FOR_WAIVER"
                            }
                        ]
                    }
                }
            ]
        }
    ]
}
```

- **`SubTestID`**: Identifier of the subtest (used in suites like `BSA`, `SBSA`).
- **`sub_Test_Description`**: Description of the subtest (used in suites like `FWTS`, `Standalone`, `SCT`, `BBSR-FWTS`, `BBSR-SCT`).
- **`Reason`**: Explanation for the waiver.

---

## Examples

### 1. Suite-Level Waiver

Waiving the entire `BSA` suite due to platform constraints.

```json
{
    "Suites": [
        {
            "Suite": "BSA",
            "Reason": "Platform does not support BSA features."
        }
    ]
}
```

### 2. TestSuite-Level Waiver

Waives all failed subtests in the Standalone DTValidation test suite.

```json
{
  "Suites": [
    {
      "Suite": "Standalone",
      "TestSuites": [
        {
          "TestSuite": "DTValidation",
          "Reason": "Specific DT bindings intentionally omitted for this hardware."
        }
      ]
    }
  ]
}
```

### 3. SubSuite-Level Waiver

Some suites (e.g., SCT) support sub-suite waivers. Example shown for completeness:

```json
{
  "Suites": [
    {
      "Suite": "SCT",
      "TestSuites": [
        {
          "SubSuite": {
            "SubSuite": "VariableServicesTest",
            "Reason": "Waiving entire SubSuite due to platform constraints."
          }
        }
      ]
    }
  ]
}
```
Note: SubSuite/TestCase-level waivers are supported only for certain suites (SCT, Standalone, BBSR-SCT, BBSR-FWTS). Keep this as an example if you’re documenting behavior.

### 4. TestCase-Level Waiver

Waives all failed subtests within the specified test case only.

```json
{
  "Suites": [
    {
      "Suite": "Standalone",
      "TestSuites": [
        {
          "TestCase": {
            "Test_case": "psci_check",
            "Reason": "PSCI nuances out of scope for this product variant."
          }
        }
      ]
    }
  ]
}
```

### 5. SubTest-Level Waiver

Targets specific subtests by exact description text.

```json
{
  "Suites": [
    {
      "Suite": "Standalone",
      "TestSuites": [
        {
          "TestCase": {
            "Test_case": "ethtool_test",
            "SubTests": [
              {
                "sub_Test_Description": "No Ethernet Interfaces Detected",
                "Reason": "Networking stack is not included on this SKU."
              }
            ]
          }
        },
        {
          "TestCase": {
            "Test_case": "dt_kselftest",
            "SubTests": [
              {
                "sub_Test_Description": "/soc@0/bus@32c00000",
                "Reason": "ADC node not required on this platform."
              }
            ]
          }
        }
      ]
    }
  ]
}
```

---

## Understanding the Waiver Application Process

The `apply_waivers.py` script processes waivers in a hierarchical manner:

1. **Load Waivers**: It reads the `waiver.json` file and extracts waivers relevant to the specified `SUITE_NAME`.
2. **Apply Waivers**:
   - **Suite-Level**: Waivers are applied to all failed subtests in the suite.
   - **TestSuite-Level**: Waivers are applied to all failed subtests within the specified test suites.
   - **SubSuite-Level**: Waivers are applied to all failed subtests within the specified sub-suites.
   - **TestCase-Level**: Waivers are applied to all failed subtests within the specified test cases.
   - **SubTest-Level**: Waivers are applied to individual subtests based on `SubTestID` or `sub_Test_Description`.
3. **Update Test Results**: The script adjusts pass/fail counts and annotates waived tests with the waiver reason.
4. **Output**: The updated test results JSON file replaces the original file, reflecting the applied waivers.

---

## Important Notes

- **Suites Supporting SubSuite/TestCase-Level Waivers**: Only certain suites (`SCT`, `Standalone`, `BBSR-SCT`, `BBSR-FWTS`) support waivers at the SubSuite and TestCase levels.
- **Waiver Application Order**: Waivers are applied from the highest level (suite) to the lowest level (subtest). Lower-level waivers override higher-level waivers if both are applicable.
- **Updating Test Results**: The script modifies the original test results JSON file. Ensure you have a backup if you need to retain the original data.
- **Waiver Effect on Statistics**: Failed tests that are waived are counted under `FAILED_WITH_WAIVER`, and the overall failed count is adjusted accordingly.
- **Error Handling**: The script skips waiver entries that are missing required fields and provides warnings if verbosity is enabled.
- **Case Sensitivity**: Suite and test names are case-sensitive. Ensure names in `waiver.json` match those in the test results.

---

By following the templates and guidelines provided in this document, you can effectively apply waivers to your test suite results, ensuring accurate representation of your platform's compliance and capabilities.

