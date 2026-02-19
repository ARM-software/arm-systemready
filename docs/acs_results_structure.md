# Test Suite Parsers - Data Structure Documentation

Comprehensive reference for JSON output structures across all test suite parsers.

---

## Data Structure Table

| **Key/Object Name** | **BSA** | **BBSR-FWTS** | **BBSR-SCT** | **FWTS** | **SCT** | **PFDI** | **Standalone** | **POST_SCRIPT** | **SBMR** |
|---------------------|---------|---------------|--------------|----------|---------|----------|----------------|-----------------|----------|
| **═══ SUITE GROUP ═══** | | | | | | | | | |
| **Suite_Name** | String | String | String | String | String | String | String | String | String |
| **suite_summary** | **dict:**<br>• Failed<br>• Not Implemented<br>• PAL Not Supported<br>• Passed<br>• Passed (Partial)<br>• Skipped<br>• Total Rules Run<br>• Total_failed_with_waiver<br>• Warnings | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | **dict:**<br>• total_aborted<br>• total_failed<br>• total_ignored<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | **dict:**<br>• total_aborted<br>• total_failed<br>• total_ignored<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | **⚠️ Suite_summary**<br>**dict** (last element):<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings | **dict:**<br>• total_aborted<br>• total_failed<br>• **⚠️ total_failed_with_waivers**<br>• total_passed<br>• total_skipped<br>• total_warnings | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | **dict:**<br>• total_aborted<br>• total_failed<br>• total_ignored<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver |
| | | | | | | | | | |
| **═══ TEST SUITE GROUP (test_results[]) ═══** | | | | | | | | | |
| **test_results[]** | Array | Array | Array | Array | Array | N/A | Array | Array | Array |
| **Test_suite** | String | String | String | String | String | String | String | String | String |
| **Test_suite_description** | - | String | - | String | - | - | String | String | - |
| **test_suite_summary** | **dict:**<br>• Failed<br>• Not Implemented<br>• PAL Not Supported<br>• Passed<br>• Passed (Partial)<br>• Skipped<br>• Total Rules Run<br>• Total_failed_with_waiver<br>• Warnings | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | - | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | - | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings | **dict:**<br>• total_aborted<br>• total_failed<br>• **⚠️ total_failed_with_waivers**<br>• total_passed<br>• total_skipped<br>• total_warnings | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | **dict:**<br>• total_aborted<br>• total_failed<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver |
| **Main Readiness Grouping** | String | String | String | String | String | String | String | String | - |
| **SRS scope** | String | String | String | String | String | String | String | String | - |
| **Waivable** | String | String | String | String | String | String | String | String | - |
| **Sub_test_suite** | - | - | String | - | String | - | - | - | - |
| | | | | | | | | | |
| **═══ TEST CASE GROUP (testcases[]) ═══** | | | | | | | | | |
| **testcases[]** | **⚠️ testcases[]** Array | - | - | - | - | - | - | - | **⚠️ Test_cases[]** Array |
| **Test_case** | String | - | String | - | String | - | String | - | String |
| **Test_case_description** | String | - | String | - | String | - | String | - | - |
| **test_case_summary** | **dict:**<br>• Failed<br>• Not Implemented<br>• PAL Not Supported<br>• Passed<br>• Passed (Partial)<br>• Skipped<br>• Total Rules Run<br>• Total_failed_with_waiver<br>• Warnings | - | **dict:**<br>• total_aborted<br>• total_failed<br>• total_ignored<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | - | **dict:**<br>• total_aborted<br>• total_failed<br>• total_ignored<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver | - | - | - | **dict:**<br>• total_aborted<br>• total_failed<br>• total_ignored<br>• total_passed<br>• total_skipped<br>• total_warnings<br>• Total_failed_with_waiver |
| **Test Entry Point GUID** | - | - | String | - | String | - | - | - | - |
| **Test_result** | String | - | String | - | String | - | - | - | - |
| **Returned Status Code** | - | - | String | - | String | - | - | - | - |
| **reason** | - | - | String | - | String | - | - | - | String |
| | | | | | | | | | |
| **═══ SUBTEST GROUP (subtests[]) ═══** | | | | | | | | | |
| **subtests[]** | Array | Array | Array | Array | Array | Array | Array | Array | Array |
| **sub_Test_Number** | String | String | String | String | String | String | String | String | String |
| **sub_Test_Description** | String | String | String | String | String | String | String | String | String |
| **sub_Test_GUID** | - | - | String | - | String | - | - | - | - |
| **sub_Rule_ID** | String | - | - | - | - | - | - | - | - |
| **sub_test_result** | **String:**<br>• PASSED<br>• FAILED<br>• SKIPPED | **dict:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNINGS<br>• FAILED_WITH_WAIVER<br>• pass_reasons (Array)<br>• fail_reasons (Array)<br>• skip_reasons (Array)<br>• abort_reasons (Array)<br>• warning_reasons (Array) | **String:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNING | **dict:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNINGS<br>• FAILED_WITH_WAIVER<br>• pass_reasons (Array)<br>• fail_reasons (Array)<br>• skip_reasons (Array)<br>• abort_reasons (Array)<br>• warning_reasons (Array) | **String:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNING | **String:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNING | **dict:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNINGS<br>• FAILED_WITH_WAIVER<br>• pass_reasons (Array)<br>• fail_reasons (Array)<br>• skip_reasons (Array)<br>• abort_reasons (Array)<br>• warning_reasons (Array)<br>• waiver_reason (Array) | **dict:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNINGS<br>• pass_reasons (Array)<br>• fail_reasons (Array)<br>• skip_reasons (Array)<br>• abort_reasons (Array)<br>• warning_reasons (Array) | **String:**<br>• PASSED<br>• FAILED<br>• SKIPPED<br>• ABORTED<br>• WARNING |
| **reason** | - | - | String | - | String | String | - | - | String |

**Legend:**
- `-` Field not present in this suite
- All integer fields are type Integer
- All reason arrays contain String elements
- **⚠️** Indicates suite-specific naming variation (different case or spelling)
- **Bold** highlights fields with case/spelling variations across suites

---

## Key Structural Differences

1. **PFDI** - ONLY suite with top-level Array (not dict with test_results)
2. **BSA** - Uses unique summary field names (Passed, Failed, Skipped vs total_passed, total_failed, total_skipped)
3. **Naming variations:**
   - `suite_summary` (most) vs `Suite_summary` (PFDI - capital S)
   - `testcases[]` (BSA - lowercase) vs `Test_cases[]` (SBMR - capital T)
   - `Total_failed_with_waiver` (BSA, BBSR-FWTS, BBSR-SCT, FWTS, SCT, POST_SCRIPT, SBMR - capital T, singular) vs `total_failed_with_waivers` (Standalone - lowercase, plural)
4. **BBSR-FWTS, FWTS, Standalone, POST_SCRIPT** - Use dict for sub_test_result with reason arrays
5. **BSA, BBSR-SCT, SCT, PFDI, SBMR** - Use String for sub_test_result
