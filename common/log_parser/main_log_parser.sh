#!/bin/bash
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Define color codes
YELLOW='\033[1;33m'  # Yellow for WARNING
RED='\033[0;31m'     # Red for ERROR
NC='\033[0m'         # No Color (Reset)

# Determine the base directory of the script
BASE_DIR=$(dirname "$(realpath "$0")")

# Determine paths
SCRIPTS_PATH="$BASE_DIR"

# Check for required arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json]"
    exit 1
fi

# Add the YOCTO_FLAG variable
YOCTO_FLAG="/mnt/yocto_image.flag"

# Check if the YOCTO_FLAG exists
if [ -f "$YOCTO_FLAG" ]; then
    YOCTO_FLAG_PRESENT=1
else
    YOCTO_FLAG_PRESENT=0
fi

LOGS_PATH=$1
ACS_CONFIG_PATH=$2
SYSTEM_CONFIG_PATH=$3
WAIVER_JSON=$4

if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    test_category="/usr/bin/log_parser/test_categoryDT.json"
else
    test_category="/usr/bin/log_parser/test_category.json"
fi

# Check if ACS_CONFIG_PATH is provided
if [ -z "$ACS_CONFIG_PATH" ]; then
    echo -e "${YELLOW}WARNING: ACS information will be affected on summary page as acs_config.txt is not provided${NC}"
    echo ""
    echo "If you want ACS information, please use this format: $0 <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json]"
    echo ""
fi

# Check if SYSTEM_CONFIG_PATH is provided
if [ -z "$SYSTEM_CONFIG_PATH" ]; then
    echo -e "${YELLOW}WARNING: System information may be incomplete as system_config.txt is not provided${NC}"
    echo ""
    echo "If you want complete system information, please use this format: $0 <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json]"
    echo ""
fi

# Initialize waiver-related variables
WAIVERS_APPLIED=0

###############################################################################
#               Gather ACS Info (acs_info.py)
###############################################################################
ACS_SUMMARY_DIR="$LOGS_PATH/acs_summary"
JSONS_DIR="$ACS_SUMMARY_DIR/acs_jsons"
mkdir -p "$ACS_SUMMARY_DIR"
mkdir -p "$JSONS_DIR"

#echo "Gathering ACS info into acs_info.txt and acs_info.json..."
python3 "$SCRIPTS_PATH/acs_info.py" \
    --acs_config_path "$ACS_CONFIG_PATH" \
    --system_config_path "$SYSTEM_CONFIG_PATH" \
    --uefi_version_log "$LOGS_PATH/uefi_dump/uefi_version.log" \
    --output_dir "$JSONS_DIR"
echo ""

# Check if waiver.json is provided
if [ -n "$WAIVER_JSON" ]; then
    if [ -f "$WAIVER_JSON" ]; then
        WAIVERS_APPLIED=1
        echo "Waivers will be applied using:"
        echo "  Waiver File        : $WAIVER_JSON"
        echo ""
    else
        echo -e "${YELLOW}WARNING: waiver.json ('$WAIVER_JSON') must be provided to apply waivers.${NC}"
        echo "Waivers will not be applied."
        echo ""
        WAIVER_JSON=""
    fi
else
    echo -e "${YELLOW}WARNING: waiver.json not provided. Waivers will not be applied.${NC}"
    echo ""
    WAIVER_JSON=""
fi

# Function to check if a file exists
check_file() {
    if [ ! -f "$1" ]; then
        if [ "${2:-}" = "M" ]; then
            echo -e "${RED}ERROR: Log file "$1" is missing.${NC}"
        else
            echo -e "${YELLOW}WARNING: Log file "$1" is missing.${NC}"
        fi
        return 1
    fi
    echo -e "Processing "$1" file."
    return 0
}

# print missing json
print_missing_json() {
    local debug=0
    if [ debug = 1 ]; then
        echo -e "${YELLOW}WARNING: "$1" is missing.${NC}"
    fi
}

# Function to apply waivers
apply_waivers() {
    local suite_name="$1"
    local json_file="$2"

    if [ "$WAIVERS_APPLIED" -eq 1 ]; then
        python3 "$SCRIPTS_PATH/apply_waivers.py" "$suite_name" "$json_file" "$WAIVER_JSON" "$test_category" --quiet
    fi
}

# Create directories for JSONs and HTMLs inside acs_summary
HTMLS_DIR="$ACS_SUMMARY_DIR/html_detailed_summaries"
mkdir -p "$HTMLS_DIR"

# Initialize processing flags
BSA_PROCESSED=0
SBSA_PROCESSED=0
FWTS_PROCESSED=0
SCT_PROCESSED=0
BBSR_FWTS_PROCESSED=0
BBSR_SCT_PROCESSED=0
BBSR_TPM_PROCESSED=0
Standalone_PROCESSED=0
OS_TESTS_PROCESSED=0
CAPSULE_PROCESSED=0
POST_SCRIPT_PROCESSED=0
PFDI_PROCESSED=0
SBMR_PROCESSED=0
SBMR_IB_PROCESSED=0
SBMR_OOB_PROCESSED=0

################################################################################
# BSA PARSING
################################################################################
BSA_LOG="$LOGS_PATH/uefi/BsaResults.log"
BSA_KERNEL_LOG="$LOGS_PATH/linux_acs/bsa_acs_app/BsaResultsKernel.log"
if [ ! -f "$BSA_KERNEL_LOG" ]; then
    BSA_KERNEL_LOG="$LOGS_PATH/linux/BsaResultsKernel.log"
fi
BSA_JSON="$JSONS_DIR/bsa.json"
BSA_LOGS=()

if [ $YOCTO_FLAG_PRESENT -eq 0 ]; then
    if check_file "$BSA_LOG" "M"; then
        BSA_LOGS+=("$BSA_LOG")
    fi
    if check_file "$BSA_KERNEL_LOG" "M"; then
        BSA_LOGS+=("$BSA_KERNEL_LOG")
    fi
else
    if check_file "$BSA_LOG"; then
        BSA_LOGS+=("$BSA_LOG")
    fi
    if check_file "$BSA_KERNEL_LOG"; then
        BSA_LOGS+=("$BSA_KERNEL_LOG")
    fi
fi

if [ ${#BSA_LOGS[@]} -gt 0 ]; then
    BSA_PROCESSED=1
    python3 "$SCRIPTS_PATH/bsa/logs_to_json.py" "${BSA_LOGS[@]}" "$BSA_JSON"
    if [ $? -ne 0 ]; then
        BSA_PROCESSED=0
        echo -e "${RED}ERROR: BSA logs parsing to json failed.${NC}"
    else
        apply_waivers "BSA" "$BSA_JSON"
        python3 "$SCRIPTS_PATH/bsa/json_to_html.py" "$BSA_JSON" "$HTMLS_DIR/bsa_detailed.html" "$HTMLS_DIR/bsa_summary.html"
    fi
fi

################################################################################
# SBSA PARSING (if YOCTO_FLAG not present)
################################################################################
if [ $YOCTO_FLAG_PRESENT -eq 0 ]; then
    SBSA_LOG="$LOGS_PATH/uefi/SbsaResults.log"
    SBSA_KERNEL_LOG="$LOGS_PATH/linux/SbsaResultsKernel.log"
    SBSA_JSON="$JSONS_DIR/sbsa.json"
    SBSA_LOGS=()

    SbsaRunEnabled=$(grep -E '^SbsaRunEnabled=' "/mnt/acs_tests/config/acs_run_config.ini" 2>/dev/null | cut -d'=' -f2)
    SbsaRunEnabled=${SbsaRunEnabled:-0}  # Default to 0 if empty
    if [ "$SbsaRunEnabled" -eq 1 ]; then
        if check_file "$SBSA_LOG" "M"; then
            SBSA_LOGS+=("$SBSA_LOG")
        fi
        if check_file "$SBSA_KERNEL_LOG" "M"; then
            SBSA_LOGS+=("$SBSA_KERNEL_LOG")
        fi
    else
        if check_file "$SBSA_LOG"; then
            SBSA_LOGS+=("$SBSA_LOG")
        fi
        if check_file "$SBSA_KERNEL_LOG"; then
            SBSA_LOGS+=("$SBSA_KERNEL_LOG")
        fi
    fi

    if [ ${#SBSA_LOGS[@]} -gt 0 ]; then
        SBSA_PROCESSED=1
        python3 "$SCRIPTS_PATH/bsa/logs_to_json.py" "${SBSA_LOGS[@]}" "$SBSA_JSON"
        if [ $? -ne 0 ]; then
            SBSA_PROCESSED=0
            echo -e "${RED}ERROR: SBSA logs parsing to json failed.${NC}"
        else
            apply_waivers "SBSA" "$SBSA_JSON"
            python3 "$SCRIPTS_PATH/bsa/json_to_html.py" "$SBSA_JSON" "$HTMLS_DIR/sbsa_detailed.html" "$HTMLS_DIR/sbsa_summary.html"
        fi
    fi
fi

################################################################################
# FWTS PARSING
################################################################################
FWTS_LOG="$LOGS_PATH/fwts/FWTSResults.log"
FWTS_JSON="$JSONS_DIR/fwts.json"
if check_file "$FWTS_LOG" "M"; then
    FWTS_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/fwts/logs_to_json.py" "$FWTS_LOG" "$FWTS_JSON"
    if [ $? -ne 0 ]; then
        FWTS_PROCESSED=0
        echo -e "${RED}ERROR: FWTS logs parsing to json failed.${NC}"
    else
        apply_waivers "FWTS" "$FWTS_JSON"
        python3 "$SCRIPTS_PATH/bbr/fwts/json_to_html.py" "$FWTS_JSON" "$HTMLS_DIR/fwts_detailed.html" "$HTMLS_DIR/fwts_summary.html"
    fi
fi

################################################################################
# SCT PARSING
################################################################################
SCT_LOG="$LOGS_PATH/sct_results/Overall/Summary.log"
SCT_JSON="$JSONS_DIR/sct.json"
EDK2_PARSER_LOG="$LOGS_PATH/edk2-test-parser/edk2-test-parser.log"
EDK2_PARSER_JSON="$JSONS_DIR/edk2_test_parser.json"

if check_file "$SCT_LOG" "M"; then
    SCT_PROCESSED=1
    # EDK2 Log Parsing: Process the edk2-test-parser.log
    if check_file "$EDK2_PARSER_LOG"; then
        python3 "$SCRIPTS_PATH/bbr/sct/logs_to_json_edk2.py" "$EDK2_PARSER_LOG" "$EDK2_PARSER_JSON"
    fi
    python3 "$SCRIPTS_PATH/bbr/sct/logs_to_json.py" "$SCT_LOG" "$SCT_JSON"
    if [ $? -ne 0 ]; then
        SCT_PROCESSED=0
        echo -e "${RED}ERROR: SCT logs parsing to json failed.${NC}"
    else
        apply_waivers "SCT" "$SCT_JSON"
        python3 "$SCRIPTS_PATH/bbr/sct/json_to_html.py" "$SCT_JSON" "$HTMLS_DIR/sct_detailed.html" "$HTMLS_DIR/sct_summary.html"
    fi
fi

################################################################################
# BBSR FWTS PARSING
################################################################################
BBSR_FWTS_LOG="$LOGS_PATH/bbsr/fwts/FWTSResults.log"
BBSR_FWTS_JSON="$JSONS_DIR/bbsr_fwts.json"
if check_file "$BBSR_FWTS_LOG"; then
    BBSR_FWTS_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/fwts/logs_to_json.py" "$BBSR_FWTS_LOG" "$BBSR_FWTS_JSON"
    apply_waivers "BBSR-FWTS" "$BBSR_FWTS_JSON"
    python3 "$SCRIPTS_PATH/bbr/fwts/json_to_html.py" "$BBSR_FWTS_JSON" "$HTMLS_DIR/bbsr_fwts_detailed.html" "$HTMLS_DIR/bbsr_fwts_summary.html"
fi

################################################################################
# BBSR SCT PARSING
################################################################################
BBSR_SCT_LOG="$LOGS_PATH/bbsr/sct_results/Overall/Summary.log"
BBSR_SCT_JSON="$JSONS_DIR/bbsr_sct.json"
if check_file "$BBSR_SCT_LOG"; then
    BBSR_SCT_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/sct/logs_to_json.py" "$BBSR_SCT_LOG" "$BBSR_SCT_JSON"
    apply_waivers "BBSR-SCT" "$BBSR_SCT_JSON"
    python3 "$SCRIPTS_PATH/bbr/sct/json_to_html.py" "$BBSR_SCT_JSON" "$HTMLS_DIR/bbsr_sct_detailed.html" "$HTMLS_DIR/bbsr_sct_summary.html"
fi

################################################################################
# BBSR TPM PARSING
################################################################################
BBSR_TPM_LOG="$LOGS_PATH/bbsr/tpm2/verify_tpm_measurements.log"
BBSR_TPM_JSON="$JSONS_DIR/bbsr_tpm.json"
if check_file "$BBSR_TPM_LOG"; then
    BBSR_TPM_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/tpm/logs_to_json.py" "$BBSR_TPM_LOG" "$BBSR_TPM_JSON"
    apply_waivers "BBSR-TPM" "$BBSR_TPM_JSON"
    python3 "$SCRIPTS_PATH/bbr/tpm/json_to_html.py" "$BBSR_TPM_JSON" "$HTMLS_DIR/bbsr_tpm_detailed.html" "$HTMLS_DIR/bbsr_tpm_summary.html"
fi

################################################################################
# PFDI PARSING
################################################################################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    PFDI_LOG="$LOGS_PATH/uefi/pfdiresults.log"   # adjust if your log lives elsewhere
    PFDI_JSON="$JSONS_DIR/pfdi.json"
    PFDI_PROCESSED=0

    if check_file "$PFDI_LOG" "CM"; then
        PFDI_PROCESSED=1
        if python3 "$SCRIPTS_PATH/pfdi/logs_to_json.py" \
                "$PFDI_LOG" \
                "$PFDI_JSON"; then
            apply_waivers "PFDI" "$PFDI_JSON"
            python3 "$SCRIPTS_PATH/pfdi/json_to_html.py" \
                    "$PFDI_JSON" \
                    "$HTMLS_DIR/pfdi_detailed.html" \
                    "$HTMLS_DIR/pfdi_summary.html"
        else
            if [ $? -eq 1 ]; then
                PFDI_PROCESSED=0
                echo -e " PFDI -- Not Implemented"
            else
                PFDI_PROCESSED=0
                echo -e "${RED}ERROR: PFDI logs parsing to json failed.${NC}"
            fi
        fi
    fi
fi
################################################################################
# SBMR PARSING (IB + OOB)
################################################################################
# Execute only if YOCTO_FLAG_PRESENT is 0
if [ "$YOCTO_FLAG_PRESENT" -eq 0 ]; then

    # Paths relative to LOGS_PATH (new layout)
    SBMR_IB_LOG="$LOGS_PATH/sbmr/sbmr_in_band_logs/console.log"
    SBMR_OOB_LOG="$LOGS_PATH/sbmr/sbmr_out_of_band_logs/console.log"

    SBMR_IB_JSON="$JSONS_DIR/sbmr_ib.json"
    SBMR_OOB_JSON="$JSONS_DIR/sbmr_oob.json"

    # Reset flags
    SBMR_IB_PROCESSED=0
    SBMR_OOB_PROCESSED=0

    # Parse IB
    if check_file "$SBMR_IB_LOG" "M"; then
        SBMR_IB_PROCESSED=1
        python3 "$SCRIPTS_PATH/sbmr/logs_to_json.py" "$SBMR_IB_LOG" "$SBMR_IB_JSON"
        if [ $? -ne 0 ]; then
            SBMR_IB_PROCESSED=0
            echo -e "${RED}ERROR: SBMR IB logs parsing to json failed.${NC}"
        else
            apply_waivers "SBMR" "$SBMR_IB_JSON"
        fi
    fi

    # Parse OOB
    if check_file "$SBMR_OOB_LOG" "M"; then
        SBMR_OOB_PROCESSED=1
        python3 "$SCRIPTS_PATH/sbmr/logs_to_json.py" "$SBMR_OOB_LOG" "$SBMR_OOB_JSON"
        if [ $? -ne 0 ]; then
            SBMR_OOB_PROCESSED=0
            echo -e "${RED}ERROR: SBMR OOB logs parsing to json failed.${NC}"
        else
            apply_waivers "SBMR" "$SBMR_OOB_JSON"
        fi
    fi

    # Generate separate HTMLs per band
    if [ $SBMR_IB_PROCESSED -eq 1 ]; then
        python3 "$SCRIPTS_PATH/sbmr/json_to_html.py" \
            "$SBMR_IB_JSON" \
            "$HTMLS_DIR/sbmr_ib_detailed.html" \
            "$HTMLS_DIR/sbmr_ib_summary.html" \
            "$LOGS_PATH/sbmr/sbmr_in_band_logs/report.html"
    fi

    if [ $SBMR_OOB_PROCESSED -eq 1 ]; then
        python3 "$SCRIPTS_PATH/sbmr/json_to_html.py" \
            "$SBMR_OOB_JSON" \
            "$HTMLS_DIR/sbmr_oob_detailed.html" \
            "$HTMLS_DIR/sbmr_oob_summary.html" \
            "$LOGS_PATH/sbmr/sbmr_out_of_band_logs/report.html"
    fi

fi
################################################################################
# POST-SCRIPT LOG PARSING
################################################################################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    POST_SCRIPT_LOG="$LOGS_PATH/post-script/post-script.log"
    POST_SCRIPT_JSON="$JSONS_DIR/post_script.json"

    # Attempt to parse post-script.log if it exists
    if check_file "$POST_SCRIPT_LOG" "M"; then
        POST_SCRIPT_PROCESSED=1
        python3 "$SCRIPTS_PATH/post_script/logs_to_json.py" "$POST_SCRIPT_LOG" "$POST_SCRIPT_JSON"
        if [ $? -ne 0 ]; then
            POST_SCRIPT_PROCESSED=0
            echo -e "${RED}ERROR: post-script logs parsing to json failed.${NC}"
        else
            # Optionally apply waivers if your apply_waivers.py is relevant
            apply_waivers "POST_SCRIPT" "$POST_SCRIPT_JSON"

            # Generate the HTML (detailed + summary)
            python3 "$SCRIPTS_PATH/post_script/json_to_html.py" \
                "$POST_SCRIPT_JSON" \
                "$HTMLS_DIR/post_script_detailed.html" \
                "$HTMLS_DIR/post_script_summary.html"
        fi
    fi
fi
################################################################################
# STANDALONE TESTS PARSING (including Capsule)
################################################################################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    LINUX_TOOLS_LOGS_PATH="$LOGS_PATH/linux_tools"
    Standalone_JSONS=()

    # 1) DT_KSELFTEST
    DT_KSELFTEST_LOG="$LINUX_TOOLS_LOGS_PATH/dt_kselftest.log"
    DT_KSELFTEST_JSON="$JSONS_DIR/dt_kselftest.json"
    if check_file "$DT_KSELFTEST_LOG"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" \
            "$DT_KSELFTEST_LOG" \
            "$DT_KSELFTEST_JSON"
        Standalone_JSONS+=("$DT_KSELFTEST_JSON")
        apply_waivers "Standalone" "$DT_KSELFTEST_JSON"
    fi

    # 2) DT_VALIDATE
    DT_VALIDATE_LOG="$LINUX_TOOLS_LOGS_PATH/dt-validate-parser.log"
    DT_VALIDATE_JSON="$JSONS_DIR/dt_validate.json"
    if check_file "$DT_VALIDATE_LOG" "M"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" \
            "$DT_VALIDATE_LOG" \
            "$DT_VALIDATE_JSON"
        Standalone_JSONS+=("$DT_VALIDATE_JSON")
        apply_waivers "Standalone" "$DT_VALIDATE_JSON"
    fi

    # 3) ETHTOOL_TEST
    ETHTOOL_TEST_LOG="$LINUX_TOOLS_LOGS_PATH/ethtool-test.log"
    ETHTOOL_TEST_JSON="$JSONS_DIR/ethtool_test.json"
    if check_file "$ETHTOOL_TEST_LOG" "M"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" \
            "$ETHTOOL_TEST_LOG" \
            "$ETHTOOL_TEST_JSON"
        Standalone_JSONS+=("$ETHTOOL_TEST_JSON")
        apply_waivers "Standalone" "$ETHTOOL_TEST_JSON"
    fi

    # 4) READ_WRITE_CHECK
    READ_WRITE_CHECK_LOG="$LINUX_TOOLS_LOGS_PATH/read_write_check_blk_devices.log"
    READ_WRITE_CHECK_JSON="$JSONS_DIR/read_write_check_blk_devices.json"
    if check_file "$READ_WRITE_CHECK_LOG" "M"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" \
            "$READ_WRITE_CHECK_LOG" \
            "$READ_WRITE_CHECK_JSON"
        Standalone_JSONS+=("$READ_WRITE_CHECK_JSON")
        apply_waivers "Standalone" "$READ_WRITE_CHECK_JSON"
    fi

    # 5) CAPSULE UPDATE => parse as standalone
    CAPSULE_UPDATE_LOG="$(dirname "$LOGS_PATH")/fw/capsule-update.log"
    CAPSULE_ON_DISK_LOG="$(dirname "$LOGS_PATH")/fw/capsule-on-disk.log"
    CAPSULE_TEST_RESULTS_LOG="$(dirname "$LOGS_PATH")/fw/capsule_test_results.log"
    CAPSULE_JSON="$JSONS_DIR/capsule_update.json"

#    if check_file "$CAPSULE_UPDATE_LOG" "M" && check_file "$CAPSULE_ON_DISK_LOG" "M" && check_file "$CAPSULE_TEST_RESULTS_LOG" "M"; then
    if check_file "$CAPSULE_TEST_RESULTS_LOG" "M"; then
            python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" \
            capsule_update \
            "$CAPSULE_UPDATE_LOG" \
            "$CAPSULE_ON_DISK_LOG" \
            "$CAPSULE_TEST_RESULTS_LOG" \
            "$CAPSULE_JSON"

        if [ -f "$CAPSULE_JSON" ]; then
            CAPSULE_PROCESSED=1
            apply_waivers "Standalone" "$CAPSULE_JSON"
            Standalone_JSONS+=("$CAPSULE_JSON")
        else
            echo "WARNING: Capsule Update JSON not created."
        fi
    fi

    # 6) PSCI CHECK
    PSCI_LOG="$LINUX_TOOLS_LOGS_PATH/psci/psci_kernel.log"
    PSCI_JSON="$JSONS_DIR/psci.json"
    if check_file "$PSCI_LOG"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" psci_check "$PSCI_LOG" "$PSCI_JSON"
        if [ $? -ne 0 ]; then
            echo -e "${RED}ERROR: PSCI log parsing to json failed.${NC}"
        else
            # Important: add PSCI JSON to the same array that we pass to json_to_html!
            Standalone_JSONS+=("$PSCI_JSON")
        fi
    fi

    # 7) SMBIOS CHECK (strict parser like PSCI)
    SMBIOS_LOG="$LOGS_PATH/sct_results/Overall/Summary.log"
    SMBIOS_JSON="$JSONS_DIR/smbios_check.json"

    if check_file "$SMBIOS_LOG" "M"; then
        # Use correct full path to standalone SMBIOS parser
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" \
            "$SMBIOS_LOG" \
            "$SMBIOS_JSON"
        # If parser succeeded, include in Standalone reports
        if [ $? -eq 0 ]; then
            apply_waivers "Standalone" "$SMBIOS_JSON"
            Standalone_JSONS+=("$SMBIOS_JSON")
        else
            echo -e "${RED}ERROR: SMBIOS log parsing to json failed.${NC}"
        fi
    else
        echo -e "${YELLOW}WARNING: SMBIOS log not found: $SMBIOS_LOG${NC}"
    fi

    # Now generate a single STANDALONE HTML
    if [ ${#Standalone_JSONS[@]} -gt 0 ]; then
        Standalone_PROCESSED=1
        Standalone_DETAILED_HTML="$HTMLS_DIR/standalone_tests_detailed.html"
        Standalone_SUMMARY_HTML="$HTMLS_DIR/standalone_tests_summary.html"

        python3 "$SCRIPTS_PATH/standalone_tests/json_to_html.py" \
            "${Standalone_JSONS[@]}" \
            "$Standalone_DETAILED_HTML" \
            "$Standalone_SUMMARY_HTML" \
            --include-drop-down
    fi
fi

################################################################################
# OS TESTS PARSING
################################################################################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    OS_LOGS_PATH="$(dirname "$LOGS_PATH")/os-logs"
    OS_JSONS_DIR="$JSONS_DIR"
    mkdir -p "$OS_JSONS_DIR"
    OS_JSONS=()
    BOOT_SOURCES_PATHS=()

    if [ -d "$OS_LOGS_PATH" ] && [ "$(ls -A "$OS_LOGS_PATH")" ]; then
        for OS_DIR in "$OS_LOGS_PATH"/linux*; do
            if [ -d "$OS_DIR" ]; then
                OS_NAME=$(basename "$OS_DIR")
                ETH_TOOL_LOG="$OS_DIR/ethtool_test.log"
                BOOT_SOURCES_LOG="$OS_DIR/boot_sources.log"

                if [ -f "$ETH_TOOL_LOG" ]; then
                    OUTPUT_JSON="$OS_JSONS_DIR/ethtool_test_${OS_NAME}.json"
                    python3 "$SCRIPTS_PATH/os_tests/logs_to_json.py" \
                        "$ETH_TOOL_LOG" \
                        "$OUTPUT_JSON" \
                        "$OS_NAME"
                    OS_JSONS+=("$OUTPUT_JSON")
                    apply_waivers "os Tests" "$OUTPUT_JSON"
                    OS_TESTS_PROCESSED=1

                    if [ -f "$BOOT_SOURCES_LOG" ]; then
                        BOOT_SOURCES_PATHS+=("$BOOT_SOURCES_LOG")
                    else
                        BOOT_SOURCES_PATHS+=("Unknown")
                    fi
                else
                    echo -e "${RED}ERROR: ethtool_test.log not found in $OS_DIR${NC}"
                fi
            fi
        done
    else
        echo -e "${RED}ERROR: No os-logs found in os-logs directory at $OS_LOGS_PATH${NC}"
    fi

    if [ ${#OS_JSONS[@]} -gt 0 ]; then
        OS_DETAILED_HTML="$HTMLS_DIR/os_tests_detailed.html"
        OS_SUMMARY_HTML="$HTMLS_DIR/os_tests_summary.html"
        python3 "$SCRIPTS_PATH/os_tests/json_to_html.py" \
            "${OS_JSONS[@]}" \
            "$OS_DETAILED_HTML" \
            "$OS_SUMMARY_HTML" \
            --include-drop-down \
            --boot-sources-paths "${BOOT_SOURCES_PATHS[@]}"
    fi
fi

################################################################################
# UEFI version
################################################################################
UEFI_VERSION_LOG="$LOGS_PATH/uefi_dump/uefi_version.log"

if [ ! -f "$UEFI_VERSION_LOG" ]; then
    echo "INFO: UEFI version log '$(basename "$UEFI_VERSION_LOG")' not found."
    UEFI_VERSION_LOG=""
fi

################################################################################
# MERGE JSON
################################################################################
MERGED_JSON="$JSONS_DIR/merged_results.json"
JSON_FILES=()

###############################################################################
#             Add acs_info.JSON to the Merge
###############################################################################
acs_info_json="$JSONS_DIR/acs_info.json"
if [ -f "$acs_info_json" ]; then
    JSON_FILES+=("$acs_info_json")
else
    print_missing_json "acs_info.json"
fi

# Add BSA
if [ -f "$BSA_JSON" ]; then
    JSON_FILES+=("$BSA_JSON")
else
    print_missing_json "bsa.json"
fi

# Add SBSA
if [ $SBSA_PROCESSED -eq 1 ] && [ -f "$SBSA_JSON" ]; then
    JSON_FILES+=("$SBSA_JSON")
elif [ $SBSA_PROCESSED -eq 1 ]; then
    print_missing_json "sbsa.json"
fi

# FWTS
if [ -f "$FWTS_JSON" ]; then
    JSON_FILES+=("$FWTS_JSON")
else
    print_missing_json "fwts.json"
fi

# SCT
if [ -f "$SCT_JSON" ]; then
    JSON_FILES+=("$SCT_JSON")
else
    print_missing_json "sct.json"
fi

# SBMR IB
if [ $SBMR_IB_PROCESSED -eq 1 ] && [ -f "$SBMR_IB_JSON" ]; then
    JSON_FILES+=("$SBMR_IB_JSON")
else
    print_missing_json "sbmr_ib.json"
fi

# SBMR OOB
if [ $SBMR_OOB_PROCESSED -eq 1 ] && [ -f "$SBMR_OOB_JSON" ]; then
    JSON_FILES+=("$SBMR_OOB_JSON")
else
    print_missing_json "sbmr_oob.json"
fi

# BBSR-FWTS
if [ $BBSR_FWTS_PROCESSED -eq 1 ] && [ -f "$BBSR_FWTS_JSON" ]; then
    JSON_FILES+=("$BBSR_FWTS_JSON")
else
    print_missing_json "bbsr_fwts.json"
fi

# BBSR-SCT
if [ $BBSR_SCT_PROCESSED -eq 1 ] && [ -f "$BBSR_SCT_JSON" ]; then
    JSON_FILES+=("$BBSR_SCT_JSON")
else
    print_missing_json "bbsr_sct.json"
fi

# BBSR-TPM
if [ $BBSR_TPM_PROCESSED -eq 1 ] && [ -f "$BBSR_TPM_JSON" ]; then
    JSON_FILES+=("$BBSR_TPM_JSON")
else
    print_missing_json "bbsr_tpm.json"
fi

# PFDI
if [ $PFDI_PROCESSED -eq 1 ] && [ -f "$PFDI_JSON" ]; then
    JSON_FILES+=("$PFDI_JSON")
else
    print_missing_json "pfdi.json"
fi

# POST-SCRIPT
if [ $POST_SCRIPT_PROCESSED -eq 1 ] && [ -f "$POST_SCRIPT_JSON" ]; then
    JSON_FILES+=("$POST_SCRIPT_JSON")
else
    print_missing_json "post_script.json"
fi

# Standalone
if [ $Standalone_PROCESSED -eq 1 ] && [ ${#Standalone_JSONS[@]} -gt 0 ]; then
    JSON_FILES+=("${Standalone_JSONS[@]}")
else
    print_missing_json "standalone.json"
fi

# OS Tests
if [ $OS_TESTS_PROCESSED -eq 1 ] && [ ${#OS_JSONS[@]} -gt 0 ]; then
    JSON_FILES+=("${OS_JSONS[@]}")
else
    print_missing_json "os-tests"
fi

if [ ${#JSON_FILES[@]} -gt 0 ]; then
    python3 "$SCRIPTS_PATH/merge_jsons.py" "$MERGED_JSON" "${JSON_FILES[@]}"
    echo "ACS Merged JSON: $MERGED_JSON"
else
    echo "No JSON files to merge."
fi

echo ""

################################################################################
# NOW Generate ACS Summary (ONLY ONCE, at the very end)
################################################################################
ACS_SUMMARY_HTML="$HTMLS_DIR/acs_summary.html"
ACS_SUMMARY_PDF="$ACS_SUMMARY_DIR/acs_summary.pdf"
GENERATE_ACS_SUMMARY_CMD="python3 \"$SCRIPTS_PATH/generate_acs_summary.py\""

# 1) BSA
if [ $BSA_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bsa_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 2) SBSA
if [ $SBSA_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/sbsa_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 3) FWTS
if [ $FWTS_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/fwts_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 4) SCT
if [ $SCT_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/sct_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 5) BBSR-FWTS
if [ $BBSR_FWTS_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bbsr_fwts_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 6) BBSR-SCT
if [ $BBSR_SCT_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bbsr_sct_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 7) BBSR-TPM
if [ $BBSR_TPM_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bbsr_tpm_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 8) PFDI
if [ $PFDI_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/pfdi_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 9) POST-SCRIPT
if [ $POST_SCRIPT_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/post_script_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 10) STANDALONE
if [ $Standalone_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$Standalone_SUMMARY_HTML\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 11) OS TESTS
if [ $OS_TESTS_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$OS_SUMMARY_HTML\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 12) CAPSULE UPDATE SUMMARY
CAPSULE_SUMMARY_HTML=""
GENERATE_ACS_SUMMARY_CMD+=" \"$CAPSULE_SUMMARY_HTML\""

# 13) SBMR-IB
if [ $SBMR_IB_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/sbmr_ib_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# 14) SBMR-OOB
if [ $SBMR_OOB_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/sbmr_oob_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Then the final argument is the summary HTML
GENERATE_ACS_SUMMARY_CMD+=" \"$ACS_SUMMARY_HTML\""

# Optional arguments
if [ -n "$ACS_CONFIG_PATH" ]; then
    GENERATE_ACS_SUMMARY_CMD+=" --acs_config_path \"$ACS_CONFIG_PATH\""
fi

if [ -n "$SYSTEM_CONFIG_PATH" ]; then
    GENERATE_ACS_SUMMARY_CMD+=" --system_config_path \"$SYSTEM_CONFIG_PATH\""
fi

if [ -n "$UEFI_VERSION_LOG" ]; then
    GENERATE_ACS_SUMMARY_CMD+=" --uefi_version_log \"$UEFI_VERSION_LOG\""
fi

if [ -n "$DEVICE_TREE_DTS" ]; then
    GENERATE_ACS_SUMMARY_CMD+=" --device_tree_dts \"$DEVICE_TREE_DTS\""
fi

# If merged_results.json was created, pass it along
if [ -f "$MERGED_JSON" ]; then
    GENERATE_ACS_SUMMARY_CMD+=" --merged_json \"$MERGED_JSON\""
fi

# Finally, call generate_acs_summary.py exactly ONCE at the end
eval "$GENERATE_ACS_SUMMARY_CMD"

print_path=0  # For debug only
if [ $print_path -eq 1 ]; then
    # (All these "print" blocks remain unchanged for debugging)
    if [ $BSA_PROCESSED -eq 1 ]; then
        echo "BSA JSON                  : $BSA_JSON"
        echo "BSA Detailed Summary      : $HTMLS_DIR/bsa_detailed.html"
        echo "BSA Summary               : $HTMLS_DIR/bsa_summary.html"
        echo ""
    fi
    if [ $SBSA_PROCESSED -eq 1 ]; then
        echo "SBSA JSON                 : $SBSA_JSON"
        echo "SBSA Detailed Summary     : $HTMLS_DIR/sbsa_detailed.html"
        echo "SBSA Summary              : $HTMLS_DIR/sbsa_summary.html"
        echo ""
    fi
    if [ $FWTS_PROCESSED -eq 1 ]; then
        echo "FWTS JSON                 : $FWTS_JSON"
        echo "FWTS Detailed Summary     : $HTMLS_DIR/fwts_detailed.html"
        echo "FWTS Summary              : $HTMLS_DIR/fwts_summary.html"
        echo ""
    fi
    if [ $SCT_PROCESSED -eq 1 ]; then
        echo "SCT JSON                  : $SCT_JSON"
        echo "SCT Detailed Summary      : $HTMLS_DIR/sct_detailed.html"
        echo "SCT Summary               : $HTMLS_DIR/sct_summary.html"
        echo ""
    fi
    if [ $BBSR_FWTS_PROCESSED -eq 1 ]; then
        echo "BBSR FWTS JSON            : $BBSR_FWTS_JSON"
        echo "BBSR FWTS Detailed Summary: $HTMLS_DIR/bbsr_fwts_detailed.html"
        echo "BBSR FWTS Summary         : $HTMLS_DIR/bbsr_fwts_summary.html"
        echo ""
    fi
    if [ $BBSR_SCT_PROCESSED -eq 1 ]; then
        echo "BBSR SCT JSON             : $BBSR_SCT_JSON"
        echo "BBSR SCT Detailed Summary : $HTMLS_DIR/bbsr_sct_detailed.html"
        echo "BBSR SCT Summary          : $HTMLS_DIR/bbsr_sct_summary.html"
        echo ""
    fi
    if [ $BBSR_TPM_PROCESSED -eq 1 ]; then
        echo "BBSR TPM JSON             : $BBSR_TPM_JSON"
        echo "BBSR TPM Detailed Summary : $HTMLS_DIR/bbsr_tpm_detailed.html"
        echo "BBSR TPM Summary          : $HTMLS_DIR/bbsr_tpm_summary.html"
        echo ""
    fi
    if [ $POST_SCRIPT_PROCESSED -eq 1 ]; then
        echo "POST SCRIPTS JSON             : $POST_SCRIPT_JSON"
        echo "POST SCRIPTS Detailed Summary : $HTMLS_DIR/post_script_detailed.html"
        echo "POST SCRIPTS Summary          : $HTMLS_DIR/post_script_summary.html"
        echo ""
    fi
    if [ $Standalone_PROCESSED -eq 1 ]; then
        echo "Standalone tests Detailed Summary      : $Standalone_DETAILED_HTML"
        echo "Standalone tests Summary               : $Standalone_SUMMARY_HTML"
        echo ""
    fi
    if [ $OS_TESTS_PROCESSED -eq 1 ]; then
        echo "OS tests Detailed Summary : $OS_DETAILED_HTML"
        echo "OS tests Summary          : $OS_SUMMARY_HTML"
        echo ""
    fi
    if [ $CAPSULE_PROCESSED -eq 1 ]; then
        echo "Capsule Update JSON             : $CAPSULE_JSON"
        echo "Capsule Update Detailed Summary : $HTMLS_DIR/capsule_update_detailed.html"
        echo "Capsule Update Summary          : $HTMLS_DIR/capsule_update_summary.html"
        echo ""
    fi
    if [ $PFDI_PROCESSED -eq 1 ]; then
    echo "PFDI JSON                 : $PFDI_JSON"
    echo "PFDI Detailed Summary     : $HTMLS_DIR/pfdi_detailed.html"
    echo "PFDI Summary              : $HTMLS_DIR/pfdi_summary.html"
    echo ""
    fi
fi

echo "ACS HTML Summary : $ACS_SUMMARY_HTML"

if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    echo " Converting ACS HTML Summary to PDF"
    # Convert ACS Summary HTML to PDF
    if [ -f "$ACS_SUMMARY_HTML" ]; then
        python3 -c "from weasyprint import HTML, CSS; HTML('$ACS_SUMMARY_HTML').write_pdf('$ACS_SUMMARY_PDF', stylesheets=[CSS(string='@page { margin: 0; }')])"
        echo "ACS PDF Summary : $ACS_SUMMARY_PDF"
    fi
fi

echo ""
