
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

1. **Suite-Level Waiver**: Applies to all failed tests in the entire suite.
2. **TestSuite-Level Waiver**: Applies to all failed tests within a specific test suite.
3. **SubSuite-Level Waiver**: Applies to all failed subtests within a specific sub-suite (applicable for suites like `SCT`, `Standalone`, `BBSR-SCT`, `BBSR-FWTS`).
4. **TestCase-Level Waiver**: Applies to a specific failed test case and its failed nested subtests where that suite supports test case waivers.
5. **SubTest-Level Waiver**: Applies to individual subtests. For BSA/SBSA, prefer `sub_Test_Path` for nested subtests.

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

Applies to a specific failed test case and its failed nested subtests where that suite supports test case waivers. For BSA/SBSA, use the `TestCases` array under a `TestSuite` entry. For SCT, Standalone, BBSR-SCT, and BBSR-FWTS, use the `TestCase` object form shown below.

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

Applies to individual subtests.

For BSA/SBSA nested logs, use `sub_Test_Path` when possible. It is the most precise key because the same rule can appear under different parent rules. The parser also supports `sub_Test_Number`, legacy `sub_Rule_ID`, and exact `sub_Test_Description` matching for compatibility.

For other suites, use the suite-specific key such as `SubTestID`, `sub_Test_GUID`, or `sub_Test_Description`.

```json
{
    "Suites": [
        {
            "Suite": "BSA_OR_SBSA",
            "TestSuites": [
                {
                    "TestSuite": "TEST_SUITE_NAME",
                    "TestCases": [
                        {
                            "Test_case": "TEST_CASE_ID_OR_FULL_TEST_CASE",
                            "SubTests": [
                                {
                                    "sub_Test_Path": "TEST_CASE : INDEX / CHILD_RULE : INDEX / NESTED_RULE : INDEX",
                                    "Reason": "REASON_FOR_WAIVER"
                                },
                                {
                                    "sub_Test_Number": "CHILD_RULE : INDEX",
                                    "Reason": "REASON_FOR_WAIVER"
                                },
                                {
                                    "sub_Rule_ID": "LEGACY_RULE_ID",
                                    "Reason": "REASON_FOR_WAIVER"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}
```

- **`sub_Test_Path`**: Preferred BSA/SBSA nested subtest identifier. Use the exact value from the JSON or HTML row tooltip.
- **`sub_Test_Number`**: BSA/SBSA subtest number, for example `PCI_MM_01 : -`. This can be ambiguous if the same subtest number appears in more than one nested branch.
- **`sub_Rule_ID`**: Legacy BSA/SBSA key. It is still accepted by the waiver parser but is not emitted in new BSA/SBSA JSON.
- **`SubTestID` / `sub_Test_GUID`**: Identifier used by other suites where applicable.
- **`sub_Test_Description`**: Description of the subtest. Prefer path or ID matching when available.
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
Note: SubSuite-level waivers are supported only for certain suites (SCT, Standalone, BBSR-SCT, BBSR-FWTS). TestCase-level waivers are also supported for BSA/SBSA through the `TestCases` array form.

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

For BSA/SBSA, target nested subtests by exact `sub_Test_Path`. This avoids ambiguity when the same rule appears in multiple branches.

```json
{
  "Suites": [
    {
      "Suite": "SBSA",
      "TestSuites": [
        {
          "TestSuite": "PCIE",
          "TestCases": [
            {
              "Test_case": "S_L6PCI_1",
              "SubTests": [
                {
                  "sub_Test_Path": "S_L6PCI_1 : - / B_REP_1 : - / JKZMT : - / PCI_MM_01 : -",
                  "Reason": "Device memory decode is not supported on this platform."
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

Waivers using `sub_Test_Number` or legacy `sub_Rule_ID` still work, but they can match more than one nested occurrence when the same number or rule appears in multiple branches:

```json
{
  "Suites": [
    {
      "Suite": "SBSA",
      "TestSuites": [
        {
          "TestSuite": "PCIE",
          "TestCases": [
            {
              "Test_case": "S_L6PCI_1",
              "SubTests": [
                {
                  "sub_Rule_ID": "PCI_MM_01",
                  "Reason": "Device memory decode is not supported on this platform."
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

For Standalone and similar suites, target specific subtests by exact description text.

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
   - **Suite-Level**: Waivers are applied to all failed tests in the suite.
   - **TestSuite-Level**: Waivers are applied to all failed tests within the specified test suites.
   - **SubSuite-Level**: Waivers are applied to all failed subtests within the specified sub-suites.
   - **TestCase-Level**: Waivers are applied to the matching failed test case and its failed nested subtests.
   - **SubTest-Level**: Waivers are applied to individual subtests. BSA/SBSA matching uses `sub_Test_Path`, then `sub_Test_Number`, then legacy `sub_Rule_ID`, then exact description.
3. **Update Test Results**: The script adjusts pass/fail counts and annotates waived tests with the waiver reason.
4. **Output**: The updated test results JSON file replaces the original file, reflecting the applied waivers.

---

## Important Notes

- **Suites Supporting SubSuite/TestCase-Level Waivers**: SubSuite-level waivers are supported only for certain suites (`SCT`, `Standalone`, `BBSR-SCT`, `BBSR-FWTS`). TestCase-level waivers are supported for BSA/SBSA and selected other suites.
- **Waiver Application Order**: Waivers are applied from the highest level (suite) to the lowest level (subtest). Lower-level waivers override higher-level waivers if both are applicable.
- **Nested BSA/SBSA Subtests**: If all failed nested subtests under a failed BSA/SBSA parent are waived, the waiver state propagates up to the failed parent subtest and testcase.
- **Updating Test Results**: The script modifies the original test results JSON file. Ensure you have a backup if you need to retain the original data.
- **Waiver Effect on Statistics**: Failed tests that are waived are counted under `FAILED_WITH_WAIVER` or `Total_failed_with_waiver`, depending on the suite summary format, and the overall failed count is adjusted accordingly.
- **Error Handling**: The script skips waiver entries that are missing required fields and provides warnings if verbosity is enabled.
- **Case Sensitivity**: Suite and test names are case-sensitive. Ensure names in `waiver.json` match those in the test results.

---

By following the templates and guidelines provided in this document, you can effectively apply waivers to your test suite results, ensuring accurate representation of your platform's compliance and capabilities.
