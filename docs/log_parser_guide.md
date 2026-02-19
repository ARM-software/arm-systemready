# SystemReady ACS Log Parser - Comprehensive Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Usage](#usage)
5. [Log Parser Flow](#log-parser-flow)
6. [Supported Test Suites](#supported-test-suites)
7. [Waiver System](#waiver-system)
8. [Output Structure](#output-structure)
9. [Configuration Files](#configuration-files)
10. [Detailed Component Breakdown](#detailed-component-breakdown)
11. [Compliance Determination](#compliance-determination)
12. [Test Category System](#test-category-system)
13. [Troubleshooting](#troubleshooting)

---

## Overview

The SystemReady ACS (Architecture Compliance Suite) Log Parser is a comprehensive tool designed to parse, analyze, and generate reports from various test suite logs for Arm SystemReady certification. It processes logs from multiple test suites, applies waivers, and generates detailed HTML/PDF summaries with compliance status.

### Key Features
- **Multi-suite parsing**: Supports BSA, SBSA, FWTS, SCT, BBSR, SBMR, PFDI, and more
- **Waiver management**: Apply test-level waivers with justifications
- **Compliance tracking**: Determines pass/fail status based on mandatory/recommended tests
- **HTML/PDF reports**: Generates detailed and summary reports
- **Dual mode support**: SystemReady (SR) and DeviceTree (DT) bands

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     main_log_parser.sh                          │
│                    (Orchestration Layer)                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌──────────┐   ┌──────────┐   ┌──────────────┐
│ acs_info │   │  Suite   │   │apply_waivers │
│   .py    │   │ Parsers  │   │     .py      │
└──────────┘   └──────────┘   └──────────────┘
       │               │               │
       │      ┌────────┴────────┐      │
       │      ▼                 ▼      │
       │  logs_to_json.py  json_to_html.py
       │      │                 │
       └──────┼─────────────────┼──────┘
              │                 │
              ▼                 ▼
       ┌──────────────────────────────┐
       │  generate_acs_summary.py     │
       │  merge_jsons.py              │
       └──────────────────────────────┘
              │
              ▼
       ┌──────────────────────────────┐
       │  HTML Summary + PDF Report   │
       └──────────────────────────────┘
```

---

## Prerequisites

### System Requirements
- **OS**: Linux (bash shell)
- **Python**: 3.6+
- **Root Access**: Required for system information extraction (dmidecode)

### Python Dependencies
```bash
pip3 install jinja2 weasyprint
```

### Directory Structure
```
<acs_results>/
├── uefi/
│   ├── BsaResults.log
│   ├── SbsaResults.log
│   ├── pfdiresults.log
├── uefi_dump/
│   └── uefi_version.log
├── linux_acs/
│   └── bsa_acs_app/BsaResultsKernel.log
│   └── scmi_acs_app/arm_scmi_test_log.txt
├── linux/
│   └── BsaResultsKernel.log
├── fwts/
│   └── FWTSResults.log
├── sct_results/
│   └── Overall/Summary.log
├── bbsr/
│   ├── fwts/FWTSResults.log
│   ├── sct_results/Overall/Summary.log
│   └── tpm2/verify_tpm_measurements.log
├── sbmr/
│   ├── sbmr_in_band_logs/console.log
│   └── sbmr_out_of_band_logs/console.log
├── post-script/
│   └── post-script.log
├── linux_tools/
│   ├── dt_kselftest.log
│   ├── dt-validate-parser.log
│   ├── ethtool-test.log
│   └── read_write_check_blk_devices.log
│   └── psci/psci_kernel.log
├── network_boot/
│   └── network_boot_results.log
└── ../fw/
    ├── capsule-update.log
    ├── capsule-on-disk.log
    └── capsule_test_results.log

<results_root>/os-logs/
└── linux*/
    ├── ethtool_test.log
    └── boot_sources.log
```

---

## Usage

### Basic Command Syntax
```bash
sudo ./main_log_parser.sh <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json]
```

### Example Command
```bash
sudo ./main_log_parser.sh \
    <acs_results_path> \
    <acs_config_path> \
    <system_config_path> \
    <waiver_path>
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `acs_results_directory` | **Yes** | Path to directory containing test results |
| `acs_config.txt` | No | ACS configuration file for test info |
| `system_config.txt` | No | System configuration file for metadata |
| `waiver.json` | No | Waiver file to mark known issues |

### Command Line Flags

The parser automatically detects the mode:
- **SR Mode**: If `/mnt/yocto_image.flag` does NOT exist
- **DT Mode**: If `/mnt/yocto_image.flag` exists

---

## Log Parser Flow

### High-Level Flow

```
1. Initialize Environment
   ├── Check arguments
   ├── Detect SR/DT mode (yocto_image.flag)
   ├── Select test_category file (test_category.json or test_categoryDT.json)
   └── Create output directories

2. Gather System Information (acs_info.py)
   ├── Extract system metadata (dmidecode)
   ├── Parse config files
   └── Generate acs_info.json

3. Parse Individual Test Suites
   ├── BSA/SBSA Parsing
   │   ├── logs_to_json.py → bsa.json
   │   ├── apply_waivers.py (with test_category)
   │   └── json_to_html.py
   ├── FWTS Parsing
   │   ├── logs_to_json.py → fwts.json
   │   ├── apply_waivers.py (with test_category)
   │   └── json_to_html.py
   ├── SCT Parsing
   ├── BBSR Suite Parsing
   ├── SBMR Parsing (SR mode only)
   ├── PFDI Parsing (DT mode only)
   ├── Standalone Tests (DT mode)
   └── OS Tests

4. Apply Waivers (Suite-by-Suite)
   ├── Load waiver.json
   ├── Load selected test_category file for waivability checks
   ├── Match waivers to failed tests
   └── Mark as "FAILED (WITH WAIVER)"

5. Merge JSONs and Generate Summary
   ├── merge_jsons.py → merged_results.json
   ├── Load test_categoryDT.json metadata (current implementation)
   ├── Enrich with Waivable/SRS scope/Readiness grouping
   ├── Determine compliance status
   └── generate_acs_summary.py → acs_summary/html_detailed_summaries/acs_summary.html

6. PDF Generation (DT mode only)
   └── Convert HTML to PDF using weasyprint
```

### Detailed Step-by-Step Flow

#### Step 1: System Info Gathering
```python
# acs_info.py extracts:
- Vendor (from dmidecode -t system)
- System Name (Product Name)
- SoC Family
- Firmware Version (from dmidecode -t bios)
- Timestamp
- Config file parameters
```

#### Step 2: Test Suite Parsing Loop
For each test suite (BSA, FWTS, SCT, etc.):

1. **Check if log file exists**
   - Mandatory logs (marked "M"): Print error if missing and continue
   - Optional logs: Warn and continue

2. **Parse log to JSON** (`logs_to_json.py`)
   - Extract test cases, results, descriptions
   - Structure as hierarchical JSON

3. **Apply waivers** (`apply_waivers.py`)
   - Match failed tests against waiver.json
   - Update status to "FAILED (WITH WAIVER)"

4. **Generate HTML reports** (`json_to_html.py`)
   - Detailed HTML: All test details
   - Summary HTML: Pass/Fail counts

#### Step 3: Merging and Compliance
```python
# merge_jsons.py:
1. Load all suite JSONs
2. Apply suite compliance rules (Mandatory/Recommended)
3. Calculate overall compliance
4. Generate merged_results.json
```

#### Step 4: Final Summary Generation
```python
# generate_acs_summary.py:
1. Load merged_results.json
2. Extract system info
3. Render HTML template with:
   - System information table
   - Per-suite summaries
   - Overall compliance status
   - Links to detailed reports
```

---

## Supported Test Suites

### SystemReady (SR) Band

| Suite | Compliance Level | Description |
|-------|-----------------|-------------|
| **BSA** | Mandatory | Base System Architecture tests (UEFI + Kernel) |
| **SBSA** | Recommended* | Server Base System Architecture |
| **FWTS** | Mandatory | Firmware Test Suite |
| **SCT** | Mandatory | Self Certification Test (UEFI) |
| **BBSR-FWTS** | Extension-Mandatory | BBR Security Recipe - FWTS |
| **BBSR-SCT** | Extension-Mandatory | BBR Security Recipe - SCT |
| **BBSR-TPM** | Extension-Mandatory | BBR Security Recipe - TPM |
| **SBMR-IB** | Recommended* | System BMC Management Recipe - In-Band |
| **SBMR-OOB** | Recommended* | System BMC Management Recipe - Out-of-Band |
| **OS Tests** | Mandatory | SR OS tests (os_test.json from sr_logs_to_json.py) |

*If SBSA is present it is treated as Mandatory; if any SBMR logs are present both SBMR-IB/OOB are treated as Mandatory.

### DeviceTree (DT) Band

| Suite | Compliance Level | Description |
|-------|-----------------|-------------|
| **BSA** | Recommended | Base System Architecture |
| **FWTS** | Mandatory | Firmware Test Suite |
| **SCT** | Mandatory | Self Certification Test |
| **BBSR-FWTS** | Extension-Mandatory | BBR Security Recipe - FWTS |
| **BBSR-SCT** | Extension-Mandatory | BBR Security Recipe - SCT |
| **BBSR-TPM** | Extension-Mandatory | BBR Security Recipe - TPM |
| **DT_VALIDATE** | Mandatory | DeviceTree Validation |
| **DT_KSELFTEST** | Recommended | Kernel Selftest for DT |
| **ETHTOOL_TEST** | Mandatory | Ethernet Tool Tests |
| **READ_WRITE_CHECK_BLK_DEVICES** | Mandatory | Block Device R/W Check |
| **Capsule Update** | Mandatory | UEFI Capsule Update |
| **NETWORK_BOOT** | Recommended | Network Boot Tests |
| **OS Tests** | Mandatory | OS-level tests across distros |
| **PFDI** | Conditional-Mandatory | Platform Fault Detection Interface |
| **POST_SCRIPT** | Recommended | Post-boot validation scripts |
| **PSCI** | Recommended | Power State Coordination Interface |
| **SMBIOS** | Recommended | SMBIOS validation |
| **SCMI** | Extension-Mandatory | System Control and Management Interface (DT only) |

---

## Waiver System

### Overview
The waiver system allows marking known test failures with justifications. Waivers are applied at multiple granularity levels.

### Waiver Hierarchy

```
Suite Level
  └── TestSuite Level
        └── TestCase Level
              └── SubTest Level
```

### Waiver JSON Structure

```json
{
  "Suites": [
    {
      "Suite": "<SuiteName>",
      "Reason": "Optional: Suite-level waiver applies to all tests",
      "TestSuites": [
        {
          "TestSuite": "<TestSuiteName>",
          "Reason": "Optional: TestSuite-level waiver",
          "TestCases": [
            {
              "Test_case": "<TestCaseID>",
              "Reason": "Required: TestCase-level waiver",
              "SubTests": [
                {
                  "sub_Rule_ID": "<SubTestID>",
                  "sub_Test_Description": "<Description>",
                  "Reason": "Required: SubTest-level waiver"
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

### Waiver Examples

#### 1. Suite-Level Waiver (applies to all failed tests in suite)
```json
{
  "Suites": [
    {
      "Suite": "BSA",
      "Reason": "All BSA tests waived for this pre-production variant",
      "TestSuites": []
    }
  ]
}
```

#### 2. TestSuite-Level Waiver
```json
{
  "Suite": "BSA",
  "TestSuites": [
    {
      "TestSuite": "TIMER",
      "Reason": "All PE architectural timer checks waived for this product"
    }
  ]
}
```

#### 3. TestCase-Level Waiver
```json
{
  "Suite": "BSA",
  "TestSuites": [
    {
      "TestSuite": "GIC",
      "TestCases": [
        {
          "Test_case": "B_PPI_00",
          "Reason": "PPI assignments not required on this platform configuration"
        }
      ]
    }
  ]
}
```

#### 4. SubTest-Level Waiver
```json
{
  "Suite": "BSA",
  "TestSuites": [
    {
      "TestSuite": "PCIE",
      "TestCases": [
        {
          "Test_case": "B_PER_08",
          "Reason": "Root complex behavior varies by board implementation",
          "SubTests": [
            {
              "sub_Rule_ID": "PCI_MM_01",
              "sub_Test_Description": "PCIe Device Memory mapping support",
              "Reason": "Device memory decode not supported on this platform"
            }
          ]
        }
      ]
    }
  ]
}
```

#### 5. Standalone/OS Tests Waiver Format
```json
{
  "Suite": "Standalone",
  "TestSuites": [
    {
      "TestCase": {
        "Test_case": "dt_kselftest",
        "SubTests": [
          {
            "sub_Test_Description": "/fw-cfg@9020000",
            "Reason": "ADC node not required on this platform"
          }
        ]
      }
    }
  ]
}
```

#### 6. Complete Multi-Suite Waiver Example
```json
{
  "Suites": [
    {
      "Suite": "BSA",
      "TestSuites": [
        {
          "TestSuite": "TIMER",
          "Reason": "Timer checks waived"
        },
        {
          "TestSuite": "PCIE",
          "TestCases": [
            {
              "Test_case": "B_PER_08",
              "SubTests": [
                {
                  "sub_Rule_ID": "PCI_MM_01",
                  "Reason": "Device memory decode not supported"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "Suite": "SBSA",
      "TestSuites": [
        {
          "TestSuite": "PE",
          "TestCases": [
            {
              "Test_case": "S_L5PE_02",
              "Reason": "PE feature not available on this variant"
            }
          ]
        }
      ]
    },
    {
      "Suite": "Standalone",
      "TestSuites": [
        {
          "TestCase": {
            "TestCase": "ethtool_test",
            "SubTests": [
              {
                "sub_Test_Description": "Ping to www.arm.com on eth0",
                "Reason": "Network stack excluded for this SKU"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

### Waiver Application Logic

1. **Load waivers** from waiver.json
2. **Match waivers** to failed tests based on hierarchy
3. **Apply waivers**:
   - Suite-level: Applies to ALL failed tests in suite
   - TestSuite-level: Applies to ALL failed tests in that TestSuite
   - TestCase-level: Applies to specific TestCase and its SubTests
   - SubTest-level: Applies only to specific SubTest

4. **Mark results**:
   - Original: `FAILED`
   - After waiver: `FAILED (WITH WAIVER)`
   - Add `waiver_reason` field to JSON

5. **Compliance impact**:
   - Tests marked "FAILED (WITH WAIVER)" do NOT count as failures
   - Suite can still pass if all failures are waived

### Important Waiver Rules

- **Reason is REQUIRED** for each waiver entry; missing reasons are skipped (quietly unless verbose)
- Waivers cascade down (Suite → TestSuite → TestCase → SubTest)
- Waivers only apply to **failed** tests (passing tests are not affected)
- Waiver reasons appear in both detailed HTML and summary reports
- Multiple waivers can be applied to the same suite

### Waivability Enforcement

**What happens if "Waivable" is "no" in test_category.json?**

The apply_waivers.py script **enforces waivability** based on test_category metadata:

1. **When test_category.json is provided**:
   - Script checks each test suite's "Waivable" field
   - If `"Waivable": "no"`, the script **skips** that test suite entirely
   - Waivers in waiver.json are **silently ignored** for non-waivable suites
   - Tests remain as "FAILED" (waivers are NOT applied)

2. **When test_category.json is NOT provided**:
   - All waivers are applied (no waivability enforcement)
   - This is a fallback mode

**Example Behavior**:

```json
// test_categoryDT.json
{
  "catID: 1": [
    {
      "Suite": "BSA",
      "Test Suite": "PE",
      "Waivable": "no"  // ← Critical test, cannot be waived
    }
  ]
}
```

```json
// waiver.json (user attempts to waive PE)
{
  "Suites": [
    {
      "Suite": "BSA",
      "TestSuites": [
        {
          "TestSuite": "PE",
          "Reason": "Attempting to waive critical test"
        }
      ]
    }
  ]
}
```

**Result**: 
- The waiver for "PE" is **NOT applied**
- Tests in PE remain "FAILED"
- No error message is shown (silent skip)
- Compliance will fail if PE has failures

**Code Reference** (apply_waivers.py):
```python
# Determine if waivers should be applied based on test_category.json
if output_json_data is None:
    # test_category.json not provided, apply all waivers
    waivable = True
else:
    # Check if the test suite is waivable according to test_category.json
    waivable = False
    for catID, catData in output_json_data.items():
        for row in catData:
            if row.get("Suite", "").lower() == suite_name.lower() and \
               row.get("Test Suite", "").lower() == test_suite_name.lower():
                if row.get("Waivable", "").lower() == "yes":
                    waivable = True
                    break
        if waivable:
            break

if not waivable:
    # Do not process non-waivable test suites
    continue  # Skip this test suite, no waivers applied
```

**Best Practice**:
- Review test_category.json before creating waivers
- Don't attempt to waive critical/non-waivable tests
- Focus waiver efforts on tests marked "Waivable": "yes"

---

## Output Structure

### Generated Directory Structure
```
<acs_results>/acs_summary/
├── acs_jsons/
│   ├── acs_info.json
│   ├── bsa.json
│   ├── sbsa.json
│   ├── fwts.json
│   ├── sct.json
│   ├── bbsr_fwts.json
│   ├── bbsr_sct.json
│   ├── bbsr_tpm.json
│   ├── sbmr_ib.json
│   ├── sbmr_oob.json
│   ├── pfdi.json
│   ├── post_script.json
│   ├── dt_kselftest.json
│   ├── dt_validate.json
│   ├── ethtool_test.json
│   ├── read_write_check_blk_devices.json
│   ├── capsule_update.json
│   ├── psci.json
│   ├── smbios_check.json
│   ├── network_boot.json
│   ├── ethtool_test_<os>.json
│   └── merged_results.json
├── html_detailed_summaries/
│   ├── bsa_detailed.html
│   ├── bsa_summary.html
│   ├── fwts_detailed.html
│   ├── fwts_summary.html
│   ├── sct_detailed.html
│   ├── sct_summary.html
│   ├── ... (one per suite)
│   ├── standalone_tests_detailed.html
│   ├── standalone_tests_summary.html
│   ├── os_tests_detailed.html
│   ├── os_tests_summary.html
│   └── acs_summary.html (Main Report)
└── acs_summary.pdf (DT mode only)
```

### JSON Schema Examples

#### BSA/SBSA JSON Structure
```json
{
  "test_results": [
    {
      "Test_suite": "TIMER",
      "testcases": [
        {
          "Test_case": "B_TIMER_01",
          "Test_case_description": "Check generic timer implementation",
          "Test_result": "PASSED"
        },
        {
          "Test_case": "B_TIMER_02",
          "Test_case_description": "Verify timer interrupt",
          "Test_result": "FAILED (WITH WAIVER)",
          "waiver_reason": "Timer interrupt not supported on this platform"
        }
      ],
      "test_suite_summary": {
        "Total Rules Run": 2,
        "Passed": 1,
        "Failed": 0,
        "Total_failed_with_waiver": 1
      }
    }
  ],
  "suite_summary": {
    "Total Rules Run": 2,
    "Passed": 1,
    "Failed": 0,
    "Total_failed_with_waiver": 1
  }
}
```

#### FWTS/SCT JSON Structure
```json
{
  "test_results": [
    {
      "Test_suite": "UEFI Services",
      "subtests": [
        {
          "sub_Test_Description": "BootServices",
          "sub_test_result": {
            "PASSED": 10,
            "FAILED": 1,
            "FAILED_WITH_WAIVER": 0,
            "fail_reasons": ["Boot order check failed"]
          }
        }
      ],
      "test_suite_summary": {
        "total_passed": 10,
        "total_failed": 1,
        "total_failed_with_waiver": 0
      }
    }
  ]
}
```

#### Merged Results JSON
```json
{
  "Suite_Name: acs_info": {
    "ACS Results Summary": {
      "Suite_Name: Mandatory  : BSA_compliance": "Compliant",
      "Suite_Name: Mandatory  : FWTS_compliance": "Not Compliant: Failed 2",
      "Overall Compliance Result": "Not Compliant : Mandatory - (failed: FWTS)"
    }
  },
  "Suite_Name: BSA": {
    "...": "bsa.json content"
  },
  "Suite_Name: FWTS": {
    "...": "fwts.json content"
  }
}
```

---

## Configuration Files

### 1. system_config.txt
Contains system hardware information.

**Format**: `Key: Value` pairs

**Example**:
```
Vendor: ARM
System Name: RD-Aspen Platform
SoC Family: Neoverse
Firmware Version: 1.2.3
```

### 2. acs_config_dt.txt / acs_config.txt
Contains ACS test configuration.

**Example**:
```
BSA Version: 1.0.8
SBSA Version: 7.1.5
SCT Version: 2.9.0
FWTS Version: 24.01.00
Test Date: 2025-12-15
```

### 3. waiver.json
See [Waiver System](#waiver-system) section above.

### 4. test_category.json / test_categoryDT.json
Defines test metadata for enriching merged results with additional test suite properties.

**Purpose**:
- Provides metadata about each test suite
- Used by `merge_jsons.py` to enrich merged results
- Automatically selected based on SR/DT mode

**Location**:
- SR mode: `/usr/bin/log_parser/test_category.json`
- DT mode: `/usr/bin/log_parser/test_categoryDT.json`

**Fields**:
- **Suite**: Test suite name (e.g., "BSA", "FWTS", "SCT")
- **Test Suite**: Test subsuite name (e.g., "PE", "GIC", "Timer")
- **specName**: Specification name (BSA, SBSA, etc.)
- **rel Import. to main readiness**: Relative importance (Critical/Major/Minor)
- **Waivable**: Whether tests can be waived ("yes"/"no")
- **SRS scope**: Compliance scope (Mandatory/Recommended/Extension)
- **Main Readiness Grouping**: Functional category
- **FunctionID**: Function identifier for grouping

**Example (test_categoryDT.json)**:
```json
{
  "catID: 1": [
    {
      "Suite": "BSA",
      "Test Suite": "PE",
      "specName": "BSA",
      "rel Import. to main readiness": "Critical",
      "Waivable": "yes",
      "SRS scope": "Recommended",
      "FunctionID": 9,
      "Main Readiness Grouping": "Physical readiness"
    }
  ],
  "catID: 4": [
    {
      "Suite": "BSA",
      "Test Suite": "PCIe",
      "specName": "BSA",
      "rel Import. to main readiness": "Minor",
      "Waivable": "yes",
      "SRS scope": "Recommended",
      "FunctionID": 9,
      "Main Readiness Grouping": "Physical readiness"
    }
  ]
}
```

**Usage in Log Parser**:
1. **Automatic Selection**: Based on yocto_image.flag presence
2. **Passed to apply_waivers.py**: As 4th argument for waivability checks
3. **Used by merge_jsons.py**: Currently only loads `test_categoryDT.json` to enrich merged_results.json with metadata
4. **Enrichment Process**:
   - Builds lookup dictionary from test_category data
   - Matches suite/testsuite names (case-insensitive)
   - Adds "Waivable", "SRS scope", and "Main Readiness Grouping" to merged JSON

---

## Detailed Component Breakdown

### 1. main_log_parser.sh
**Purpose**: Orchestrates the entire parsing workflow

**Key Functions**:
- `check_file()`: Validates log file existence (Mandatory/Optional)
- `apply_waivers()`: Calls apply_waivers.py for each suite
- Determines SR vs DT mode via yocto_image.flag

**Processing Order**:
1. System info gathering
2. BSA/SBSA parsing
3. FWTS parsing
4. SCT parsing
5. BBSR suite parsing
6. SBMR parsing (SR mode)
7. PFDI parsing (DT mode)
8. Standalone tests (DT mode)
9. OS tests
10. JSON merging
11. Summary generation
12. PDF conversion (DT mode)

### 2. acs_info.py
**Purpose**: Extract system and ACS information

**Inputs**:
- `--acs_config_path`: ACS config file
- `--system_config_path`: System config file
- `--uefi_version_log`: UEFI version log
- `--output_dir`: Output directory for JSON

**Outputs**:
- `acs_info.json`: System metadata

**Functions**:
- `get_system_info()`: Uses dmidecode to extract system info
- `parse_config()`: Parses key:value config files

### 3. apply_waivers.py
**Purpose**: Apply waivers to failed tests

**Usage**:
```bash
python3 apply_waivers.py <suite_name> <json_file> <waiver_json> <test_category> [--quiet]
```

**Process**:
1. Load waiver.json
2. Extract suite-specific waivers
3. Load test results JSON
4. Match waivers to failed tests (hierarchy-based)
5. Update test status to "FAILED (WITH WAIVER)"
6. Add waiver_reason field
7. Save updated JSON

**Waiver Levels** (in order of precedence):
- Suite-level
- TestSuite-level
- SubSuite-level (SCT/Standalone)
- TestCase-level
- SubTest-level

### 4. logs_to_json.py (per suite)
**Purpose**: Parse raw log files into structured JSON

**Located in**:
- `bsa/logs_to_json.py`
- `bbr/fwts/logs_to_json.py`
- `bbr/sct/logs_to_json.py`
- `standalone_tests/logs_to_json.py`
- `os_tests/logs_to_json.py`
- `sbmr/logs_to_json.py`
- `pfdi/logs_to_json.py`

**Common Pattern**:
```python
1. Read log file
2. Parse test cases using regex/patterns
3. Extract:
   - Test ID
   - Description
   - Result (PASS/FAIL/SKIP)
   - Additional metadata
4. Structure as JSON
5. Calculate summary statistics
6. Write to output JSON
```

### 5. json_to_html.py (per suite)
**Purpose**: Generate HTML reports from JSON

**Outputs**:
- Detailed HTML: Complete test breakdown
- Summary HTML: Pass/Fail counts, embedded in main summary

**Template Variables**:
- Test suite name
- Test counts (Pass/Fail/Skip/Waived)
- Individual test details
- Waiver reasons

### 6. merge_jsons.py
**Purpose**: Combine all suite JSONs into merged_results.json

**Process**:
1. Detect SR/DT mode
2. Load test_categoryDT.json (used for enrichment in both modes)
3. Build test category lookup dictionary
4. Load compliance scope table
5. Load all suite JSONs
6. For each suite:
   - Extract pass/fail counts
   - Determine compliance level (M/R/EM/CM)
   - Enrich with test_category metadata
   - Calculate suite status
7. Determine overall compliance:
   - **Not Compliant**: Any M/CM suite fails or is missing (DT mode: missing R suites also mark Not Compliant)
   - **Compliant with waivers**: Only waived failures in M/CM suites
   - **Compliant**: No failures in M/CM suites

**Test Category Enrichment**:
The script loads test metadata from `test_categoryDT.json` and enriches each test suite entry with:
- **Waivable**: Whether the test suite allows waivers
- **SRS scope**: Compliance scope (Mandatory/Recommended/Extension)
- **Main Readiness Grouping**: Functional category for reporting

This metadata helps in:
- Better reporting and categorization
- Understanding test importance
- Grouping related test suites

**Compliance Rules (as implemented)**:
- **Mandatory (M)**: Missing or failing marks overall Not Compliant
- **Conditional-Mandatory (CM)**: Missing does not change overall; failing marks overall Not Compliant
- **Extension (EM)**: Missing or failing is reported but does not change overall
- **Recommended (R)**:
  - DT mode: missing is treated as Not Compliant
  - SR mode: missing is reported as Not Run and does not change overall

### 7. generate_acs_summary.py
**Purpose**: Generate final HTML summary report

**Inputs**:
- All suite summary HTMLs
- merged_results.json
- System config files

**Output**:
- `acs_summary/html_detailed_summaries/acs_summary.html`: Main compliance report

**Report Sections**:
1. **System Information Table**
   - Vendor, System Name, SoC Family
   - Firmware Version
   - ACS versions
   - Test date

2. **Overall Compliance Status**
   - PASS/FAIL badge
   - Compliance percentage

3. **Suite-by-Suite Summary**
   - Suite name
   - Compliance level (M/R/EM/CM)
   - Pass/Fail/Waived counts
   - Links to detailed reports

4. **Footer**
   - Generated timestamp
   - ACS version info

---

## Compliance Determination

### Decision Tree

```
For each suite:
  ├── Is suite Mandatory?
  │   ├── YES → Any unwaived failures? → FAIL
  │   └── NO → Continue
  │
  ├── Is suite Extension (EM)?
  │   ├── YES → Report status but do NOT change overall compliance
  │   └── NO → Continue
  │
  ├── Is suite Conditional-Mandatory?
  │   ├── YES → Is suite run?
  │   │   ├── YES → Any unwaived failures? → FAIL
  │   │   └── NO → Not Run (no overall impact)
  │   └── NO → Continue
  │
  └── Is suite Recommended?
      └── Failures do NOT affect compliance (DT mode: missing suites are treated as Not Compliant)

Overall Compliance:
  └── Based on the implemented rules above (M/CM failures are decisive; EM is informational; DT recommended-missing is treated as Not Compliant)
```

### Compliance Examples

#### Example 1: SR Mode - PASS
```
BSA (M):        45 PASS, 0 FAIL, 1 FAIL_WAIVED  → PASS
SBSA (R):       30 PASS, 2 FAIL, 0 FAIL_WAIVED  → PASS (Recommended)
FWTS (M):       38 PASS, 0 FAIL, 0 FAIL_WAIVED  → PASS
SCT (M):        120 PASS, 0 FAIL, 2 FAIL_WAIVED → PASS
BBSR-FWTS (EM): NOT RUN                          → SKIP
SBMR-IB (M*):   10 PASS, 1 FAIL, 0 FAIL_WAIVED  → PASS (Promoted to Mandatory when present)

Overall: PASS (All mandatory suites passed)
```

#### Example 2: DT Mode - FAIL
```
BSA (R):            45 PASS, 1 FAIL, 0 FAIL_WAIVED  → FAIL (but Recommended)
FWTS (M):           38 PASS, 0 FAIL, 0 FAIL_WAIVED  → PASS
SCT (M):            120 PASS, 1 FAIL, 0 FAIL_WAIVED → FAIL ❌
DT_VALIDATE (M):    25 PASS, 0 FAIL, 0 FAIL_WAIVED  → PASS
ETHTOOL_TEST (M):   5 PASS, 0 FAIL, 1 FAIL_WAIVED   → PASS
Capsule Update (M): 3 PASS, 0 FAIL, 0 FAIL_WAIVED   → PASS

Overall: FAIL (SCT is mandatory and has unwaived failure)
```

#### Example 3: Extension Suite Handling
```
BSA (M):        PASS
FWTS (M):       PASS
SCT (M):        PASS
BBSR-FWTS (EM): PASS (Extension implemented and passed)
BBSR-SCT (EM):  NOT RUN (Extension not implemented - OK)
BBSR-TPM (EM):  1 FAIL (Extension implemented but failed) → Reported, overall compliance unchanged

Overall: PASS (EM failures do not affect overall compliance)
```

---

## Test Category System

### Overview

The test_category system provides metadata enrichment for test suites, enabling better reporting, categorization, and understanding of test importance. It automatically loads based on the operating mode (SR or DT).

### File Selection

```bash
# In main_log_parser.sh
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    test_category="/usr/bin/log_parser/test_categoryDT.json"  # DT mode
else
    test_category="/usr/bin/log_parser/test_category.json"     # SR mode
fi
```

### Metadata Fields

Each test suite entry in test_category.json contains:

| Field | Description | Example Values |
|-------|-------------|----------------|
| **Suite** | Top-level test suite name | "BSA", "SBSA", "FWTS", "SCT" |
| **Test Suite** | Sub-suite or test group | "PE", "GIC", "Timer", "PCIe" |
| **specName** | Specification reference | "BSA", "SBSA", "UEFI" |
| **rel Import. to main readiness** | Criticality level | "Critical", "Major", "Minor" |
| **Waivable** | Can failures be waived? | "yes", "no" |
| **SRS scope** | Compliance requirement | "Mandatory", "Recommended", "Extension" |
| **Main Readiness Grouping** | Functional category | "Physical readiness", "Firmware readiness" |
| **FunctionID** | Numeric category ID | 1, 2, 9, etc. |

### Usage Flow

```
1. main_log_parser.sh selects test_category file
   └── Based on yocto_image.flag

2. Passed to apply_waivers.py
   ├── Used for waivability validation
   └── Ensures only waivable tests are waived

3. Loaded by merge_jsons.py (currently `test_categoryDT.json` only)
   ├── Builds lookup dictionary: suite → testsuite → metadata
   ├── Enriches merged_results.json with metadata
   └── Adds context for reporting
```

### Example: Metadata Lookup

```python
# merge_jsons.py builds a lookup structure:
test_cat_dict = {
    "bsa": {
        "pe": {
            "Suite": "BSA",
            "Test Suite": "PE",
            "Waivable": "yes",
            "SRS scope": "Recommended",
            "rel Import. to main readiness": "Critical",
            "Main Readiness Grouping": "Physical readiness"
        },
        "pcie": {
            "Suite": "BSA",
            "Test Suite": "PCIe",
            "Waivable": "yes",
            "SRS scope": "Recommended",
            "rel Import. to main readiness": "Minor",
            "Main Readiness Grouping": "Physical readiness"
        }
    }
}
```

### Enrichment in Merged Results

When merge_jsons.py processes test results, it adds metadata:

```json
{
  "suites": [
    {
      "suite_name": "BSA",
      "test_suite": "PE",
      "compliance_level": "Recommended",
      "waivable": "yes",
      "srs_scope": "Recommended",
      "main_readiness_grouping": "Physical readiness",
      "relative_importance": "Critical",
      "suite_status": "PASSED",
      "total_passed": 45,
      "total_failed": 0
    }
  ]
}
```

### Benefits

1. **Enhanced Reporting**: Categorize tests by function and importance
2. **Waiver Validation**: Ensure only waivable tests accept waivers
3. **Waiver Enforcement**: Non-waivable tests cannot be waived (enforced by apply_waivers.py)
4. **Readiness Tracking**: Group tests by readiness categories
5. **Compliance Context**: Understand why tests are mandatory/recommended
6. **Criticality Awareness**: Identify high-impact vs. minor tests

### Waivability Enforcement Details

The test_category system provides **hard enforcement** of waivability:

**Process**:
1. apply_waivers.py loads test_category file (passed as 4th argument)
2. For each test suite in the JSON, checks if "Waivable" == "yes"
3. If "Waivable" == "no":
   - Skips the entire test suite
   - Ignores any waivers defined in waiver.json
   - Leaves test results unchanged (failures remain as "FAILED")
4. If "Waivable" == "yes":
   - Proceeds with waiver application
   - Matches waivers from waiver.json
   - Updates results to "FAILED (WITH WAIVER)"

**Why This Matters**:
- **Critical tests cannot be bypassed**: Ensures compliance integrity
- **Prevents accidental waivers**: Can't waive important architectural checks
- **Enforces certification rules**: Aligns with SystemReady specification requirements

**Example Enforcement**:
```
Test Suite: BSA PE (Waivable: no)
├── Test B_PE_01: FAILED
│   └── Waiver exists in waiver.json
│   └── Result: FAILED (waiver NOT applied) ❌
│
Test Suite: BSA Timer (Waivable: yes)
├── Test B_TIMER_01: FAILED
│   └── Waiver exists in waiver.json
│   └── Result: FAILED (WITH WAIVER) ✅
```

### Differences: SR vs DT Mode

**test_category.json (SR mode)**:
- Focuses on server/system requirements
- Includes SBSA test suites
- SBMR test metadata

**test_categoryDT.json (DT mode)**:
- Focuses on DeviceTree-specific tests
- Includes DT validation metadata
- Standalone test categories
- OS test groupings

---


<!-- AUTO-GENERATED SECTION - DO NOT EDIT MANUALLY -->
<!-- Last reviewed: unknown -->
<!-- This section is automatically updated by auto_update_docs.py -->

### 📊 Auto-Detected Component Status

**Test Suite Parsers Detected:** 9

| Suite | Parser | HTML Generator | Path |
|-------|--------|----------------|------|
| bsa | ✅ | ✅ | `bsa/` |
| bbr_fwts | ✅ | ✅ | `bbr/fwts/` |
| bbr_sct | ✅ | ✅ | `bbr/sct/` |
| bbr_tpm | ✅ | ✅ | `bbr/tpm/` |
| os_tests | ✅ | ✅ | `os_tests/` |
| pfdi | ✅ | ✅ | `pfdi/` |
| post_script | ✅ | ✅ | `post_script/` |
| sbmr | ✅ | ✅ | `sbmr/` |
| standalone_tests | ✅ | ✅ | `standalone_tests/` |

**Waiver-Supported Suites:** BBSR-FWTS, BBSR-SCT, BBSR-TPM, BSA, FWTS, PFDI, SBSA, SBMR, SCT, STANDALONE

**Test Category Files:**

- Runtime paths: `/usr/bin/log_parser/test_category.json`, `/usr/bin/log_parser/test_categoryDT.json`
- Repo copies: `test_category.json`, `test_categoryDT.json` (content format may differ from packaged files)

<!-- END AUTO-GENERATED SECTION -->

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Missing Log Files
**Error**: `ERROR: Log file "<file>" is missing`

**Solutions**:
- Verify test suite actually ran
- Check file path matches expected structure
- For optional suites, ignore warning
- For mandatory suites, rerun tests

#### 2. JSON Parsing Errors
**Error**: `ERROR: BSA logs parsing to json failed`

**Solutions**:
- Check log file format/encoding
- Verify log file is complete (not truncated)
- Look for parsing script errors in terminal output
- Validate log file matches expected format

#### 3. Waiver Not Applied
**Issue**: Test still shows FAILED instead of FAILED (WITH WAIVER)

**Solutions**:
- Check waiver.json syntax (use JSON validator)
- Verify suite name matches exactly (case-sensitive)
- Ensure TestSuite/TestCase names match log output
- Check that "Reason" field is present and non-empty
- Review apply_waivers.py output for matching errors

#### 4. System Info Shows "Unknown"
**Issue**: System information fields show "Unknown"

**Solutions**:
- Run with `sudo` (dmidecode requires root)
- Verify dmidecode is installed: `which dmidecode`
- Check system_config.txt is provided and readable
- Manually populate system_config.txt with info

#### 5. PDF Generation Fails
**Error**: PDF not created in DT mode

**Solutions**:
- Install weasyprint: `pip3 install weasyprint`
- Check HTML file exists and is valid
- Verify sufficient disk space
- Review weasyprint dependencies

#### 6. Compliance Status Incorrect
**Issue**: Expected PASS but shows FAIL (or vice versa)

**Solutions**:
- Review merged_results.json for suite statuses
- Check compliance scope table (M/R/EM/CM)
- Verify all mandatory suite failures are waived
- Check for unintended extension suite failures

#### 7. Performance Issues
**Issue**: Parser takes very long time

**Solutions**:
- Large log files can slow parsing
- Check disk I/O performance
- Reduce unnecessary debug output
- Consider running on faster storage

#### 8. Permission Denied Errors
**Error**: Cannot write to output directory

**Solutions**:
- Run with `sudo`
- Verify write permissions on acs_results directory
- Check disk space availability
- Ensure parent directories exist

### Debug Mode

To enable verbose output in waiver application:
```bash
# Edit apply_waivers.py, set:
verbose = True  # Near line 22
```

To enable path printing:
```bash
# Edit main_log_parser.sh, set:
print_path=1  # Near line 900
```

---

## Advanced Usage

### Running Specific Suites Only

The parser automatically detects which suites are available based on log files present. To run only specific suites:

1. Ensure only desired suite logs exist in acs_results
2. Remove or move other suite logs
3. Run parser normally

### Custom Output Directory

By default, output goes to `<acs_results>/acs_summary/`. To change:

```bash
# Not directly supported - would require script modification
# Workaround: Create symlink
ln -s /desired/output/path <acs_results>/acs_summary
```

### Batch Processing

Process multiple test runs:
```bash
#!/bin/bash
for result_dir in /path/to/results/*; do
    echo "Processing $result_dir"
    sudo ./main_log_parser.sh \
        "$result_dir/acs_results" \
        /path/to/system_config.txt \
        /path/to/acs_config.txt \
        /path/to/waiver.json
done
```

### Waiver Management Best Practices

1. **Version Control**: Keep waiver.json in git
2. **Documentation**: Add comments explaining each waiver (in separate doc)
3. **Review Process**: Require approval before adding waivers
4. **Expiration**: Track waiver expiration dates externally
5. **Minimize Waivers**: Only waive truly unavoidable failures

---

## Appendix

### A. File Naming Conventions

| File Type | Naming Pattern | Example |
|-----------|---------------|---------|
| Suite JSON | `<suite_name>.json` | `bsa.json` |
| Detailed HTML | `<suite_name>_detailed.html` | `fwts_detailed.html` |
| Summary HTML | `<suite_name>_summary.html` | `sct_summary.html` |
| Main Summary | `acs_summary.html` | `acs_summary.html` |
| PDF Report | `acs_summary.pdf` | `acs_summary.pdf` |

### B. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Missing required argument or mandatory log file |
| Other | Python script errors (check output) |

### C. Suite Abbreviations

| Abbreviation | Full Name |
|--------------|-----------|
| BSA | Base System Architecture |
| SBSA | Server Base System Architecture |
| FWTS | Firmware Test Suite |
| SCT | Self Certification Test |
| BBSR | BBR Security Recipe |
| SBMR | System BMC Management Recipe |
| PFDI | Platform Fault Detection Interface |
| TPM | Trusted Platform Module |
| IB | In-Band |
| OOB | Out-of-Band |

### D. Useful Commands

```bash
# Validate JSON syntax
python3 -m json.tool waiver.json

# Check log parser version
git log --oneline -1 main_log_parser.sh

# Count test results
grep -c "PASSED" acs_summary/acs_jsons/bsa.json
grep -c "FAILED" acs_summary/acs_jsons/bsa.json

# View summary in browser
safari acs_results/acs_summary/html_detailed_summaries/acs_summary.html

# Extract compliance status
grep "Overall Compliance" acs_results/acs_summary/acs_jsons/merged_results.json
```

---

## Support and Contact

For issues, questions, or contributions related to the SystemReady ACS Log Parser:

- **Repository**: arm-systemready
- **Documentation**: This file
- **Issues**: Report via appropriate issue tracking system

---

**Document Version**: 1.0  
**Last Updated**: December 16, 2025
**Maintained By**: SystemReady ACS Team
