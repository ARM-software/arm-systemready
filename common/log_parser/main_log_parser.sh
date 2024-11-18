#!/bin/bash
# Copyright (c) 2024, Arm Limited or its affiliates. All rights reserved.
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

# Determine the base directory of the script
BASE_DIR=$(dirname "$(realpath "$0")")

# Determine paths
SCRIPTS_PATH="$BASE_DIR"

# Check for required arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json] [test_category.json]"
    exit 1
fi

LOGS_PATH=$1
ACS_CONFIG_PATH=$2
SYSTEM_CONFIG_PATH=$3
WAIVER_JSON=$4
test_category=$5

# Check if ACS_CONFIG_PATH is provided
if [ -z "$ACS_CONFIG_PATH" ]; then
    echo "WARNING: ACS information will be affected on summary page as acs_config.txt is not provided"
    echo ""
    echo "If you want ACS information, please use this format: $0 <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json] [test_category.json]"
    echo ""
fi

# Check if SYSTEM_CONFIG_PATH is provided
if [ -z "$SYSTEM_CONFIG_PATH" ]; then
    echo "WARNING: System information may be incomplete as system_config.txt is not provided"
    echo ""
    echo "If you want complete system information, please use this format: $0 <acs_results_directory> [acs_config.txt] [system_config.txt] [waiver.json] [test_category.json]"
    echo ""
fi

# Initialize waiver-related variables
WAIVERS_APPLIED=0

# Check if waiver.json and test_category.json are provided
if [ -n "$WAIVER_JSON" ] && [ -n "$test_category" ]; then
    if [ -f "$WAIVER_JSON" ] && [ -f "$test_category" ]; then
        WAIVERS_APPLIED=1
        echo "Waivers will be applied using:"
        echo "  Waiver File        : $WAIVER_JSON"
        echo "  Output JSON File   : $test_category"
        echo ""
    else
        echo "WARNING: Both waiver.json ('$WAIVER_JSON') and test_category.json ('$test_category') must be provided and exist to apply waivers."
        echo "Waivers will not be applied."
        echo ""
        WAIVER_JSON=""
        test_category=""
    fi
else
    if [ -n "$WAIVER_JSON" ] || [ -n "$test_category" ]; then
        echo "WARNING: Both waiver.json and test_category.json must be provided to apply waivers."
        echo "Waivers will not be applied."
        echo ""
    else
        echo "WARNING: waiver.json and test_category.json not provided. Waivers will not be applied."
        echo ""
    fi
    WAIVER_JSON=""
    test_category=""
fi

# Add the YOCTO_FLAG variable
YOCTO_FLAG="/mnt/yocto_image.flag"

# Check if the YOCTO_FLAG exists
if [ -f "$YOCTO_FLAG" ]; then
    YOCTO_FLAG_PRESENT=1
else
    YOCTO_FLAG_PRESENT=0
fi

# Function to check if a file exists
check_file() {
    if [ ! -f "$1" ]; then
        echo "WARNING: Log file '$(basename "$1")' is not present at the given directory."
        return 1
    fi
    return 0
}

# Function to apply waivers
apply_waivers() {
    local suite_name="$1"
    local json_file="$2"

    if [ "$WAIVERS_APPLIED" -eq 1 ]; then
        python3 "$SCRIPTS_PATH/apply_waivers.py" "$suite_name" "$json_file" "$WAIVER_JSON" "$test_category"
    else
        echo "Waivers not applied for suite '$suite_name' as waiver files are not provided."
    fi
}

# Create directories for JSONs and HTMLs inside acs_summary
ACS_SUMMARY_DIR="$LOGS_PATH/acs_summary"
JSONS_DIR="$ACS_SUMMARY_DIR/acs_jsons"
HTMLS_DIR="$ACS_SUMMARY_DIR/html_detailed_summaries"
mkdir -p "$JSONS_DIR"
mkdir -p "$HTMLS_DIR"

# Initialize processing flags
BSA_PROCESSED=0
SBSA_PROCESSED=0
FWTS_PROCESSED=0
SCT_PROCESSED=0
MVP_PROCESSED=0

# BSA UEFI and Kernel Log Parsing (Processed regardless of the flag)
BSA_LOG="$LOGS_PATH/uefi/BsaResults.log"
BSA_KERNEL_LOG="$LOGS_PATH/linux_acs/bsa_acs_app/BsaResultsKernel.log"
if [ ! -f "$BSA_KERNEL_LOG" ]; then
    BSA_KERNEL_LOG="$LOGS_PATH/linux/BsaResultsKernel.log"
fi

BSA_JSON="$JSONS_DIR/BSA.json"

BSA_LOGS=()

if check_file "$BSA_LOG"; then
    BSA_LOGS+=("$BSA_LOG")
fi

if check_file "$BSA_KERNEL_LOG"; then
    BSA_LOGS+=("$BSA_KERNEL_LOG")
fi

if [ ${#BSA_LOGS[@]} -gt 0 ]; then
    BSA_PROCESSED=1
    python3 "$SCRIPTS_PATH/bsa/logs_to_json.py" "${BSA_LOGS[@]}" "$BSA_JSON"
    # Apply waivers
    apply_waivers "BSA" "$BSA_JSON"
    python3 "$SCRIPTS_PATH/bsa/json_to_html.py" "$BSA_JSON" "$HTMLS_DIR/BSA_detailed.html" "$HTMLS_DIR/BSA_summary.html"
else
    echo "WARNING: Skipping BSA log parsing as the log files are missing."
    echo ""
fi

# SBSA UEFI and Kernel Log Parsing (Process only if the flag is not present)
SBSA_LOG="$LOGS_PATH/uefi/SbsaResults.log"
SBSA_KERNEL_LOG="$LOGS_PATH/linux/SbsaResultsKernel.log"

SBSA_JSON="$JSONS_DIR/SBSA.json"

SBSA_LOGS=()

if [ $YOCTO_FLAG_PRESENT -eq 0 ]; then
    if check_file "$SBSA_LOG"; then
        SBSA_LOGS+=("$SBSA_LOG")
    fi

    if check_file "$SBSA_KERNEL_LOG"; then
        SBSA_LOGS+=("$SBSA_KERNEL_LOG")
    fi

    if [ ${#SBSA_LOGS[@]} -gt 0 ]; then
        SBSA_PROCESSED=1
        python3 "$SCRIPTS_PATH/bsa/logs_to_json.py" "${SBSA_LOGS[@]}" "$SBSA_JSON"
        # Apply waivers
        apply_waivers "SBSA" "$SBSA_JSON"
        python3 "$SCRIPTS_PATH/bsa/json_to_html.py" "$SBSA_JSON" "$HTMLS_DIR/SBSA_detailed.html" "$HTMLS_DIR/SBSA_summary.html"
    else
        echo "WARNING: Skipping SBSA log parsing as the log files are missing."
        echo ""
    fi
fi

# FWTS UEFI Log Parsing (Processed regardless of the flag)
FWTS_LOG="$LOGS_PATH/fwts/FWTSResults.log"
FWTS_JSON="$JSONS_DIR/FWTSResults.json"
if check_file "$FWTS_LOG"; then
    FWTS_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/fwts/logs_to_json.py" "$FWTS_LOG" "$FWTS_JSON"
    # Apply waivers
    apply_waivers "FWTS" "$FWTS_JSON"
    python3 "$SCRIPTS_PATH/bbr/fwts/json_to_html.py" "$FWTS_JSON" "$HTMLS_DIR/fwts_detailed.html" "$HTMLS_DIR/fwts_summary.html"
else
    echo "WARNING: Skipping FWTS log parsing as the log file is missing."
    echo ""
fi

# SCT Log Parsing (Processed regardless of the flag)
SCT_LOG="$LOGS_PATH/sct_results/Overall/Summary.log"
SCT_JSON="$JSONS_DIR/SCT.json"
if check_file "$SCT_LOG"; then
    SCT_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/sct/logs_to_json.py" "$SCT_LOG" "$SCT_JSON"
    # Apply waivers
    apply_waivers "SCT" "$SCT_JSON"
    python3 "$SCRIPTS_PATH/bbr/sct/json_to_html.py" "$SCT_JSON" "$HTMLS_DIR/SCT_detailed.html" "$HTMLS_DIR/SCT_summary.html"
else
    echo "WARNING: Skipping SCT log parsing as the log file is missing."
    echo ""
fi

# MVP Logs Parsing (Process only if the flag is present)
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    LINUX_TOOLS_LOGS_PATH="$LOGS_PATH/linux_tools"

    # Paths for MVP logs and JSON files
    DT_KSELFTEST_LOG="$LINUX_TOOLS_LOGS_PATH/dt_kselftest.log"
    DT_VALIDATE_LOG="$LINUX_TOOLS_LOGS_PATH/dt-validate.log"
    ETHTOOL_TEST_LOG="$LINUX_TOOLS_LOGS_PATH/ethtool-test.log"
    READ_WRITE_CHECK_LOG="$LINUX_TOOLS_LOGS_PATH/read_write_check_blk_devices.log"

    DT_KSELFTEST_JSON="$JSONS_DIR/dt_kselftest.json"
    DT_VALIDATE_JSON="$JSONS_DIR/dt_validate.json"
    ETHTOOL_TEST_JSON="$JSONS_DIR/ethtool_test.json"
    READ_WRITE_CHECK_JSON="$JSONS_DIR/read_write_check_blk_devices.json"

    MVP_JSONS=()

    # Process each MVP log
    if check_file "$DT_KSELFTEST_LOG"; then
        python3 "$SCRIPTS_PATH/mvp/logs_to_json.py" "$DT_KSELFTEST_LOG" "$DT_KSELFTEST_JSON"
        MVP_JSONS+=("$DT_KSELFTEST_JSON")
        # Apply waivers
        apply_waivers "MVP" "$DT_KSELFTEST_JSON"
    fi

    if check_file "$DT_VALIDATE_LOG"; then
        python3 "$SCRIPTS_PATH/mvp/logs_to_json.py" "$DT_VALIDATE_LOG" "$DT_VALIDATE_JSON"
        MVP_JSONS+=("$DT_VALIDATE_JSON")
        # Apply waivers
        apply_waivers "MVP" "$DT_VALIDATE_JSON"
    fi

    if check_file "$ETHTOOL_TEST_LOG"; then
        python3 "$SCRIPTS_PATH/mvp/logs_to_json.py" "$ETHTOOL_TEST_LOG" "$ETHTOOL_TEST_JSON"
        MVP_JSONS+=("$ETHTOOL_TEST_JSON")
        # Apply waivers
        apply_waivers "MVP" "$ETHTOOL_TEST_JSON"
    fi

    if check_file "$READ_WRITE_CHECK_LOG"; then
        python3 "$SCRIPTS_PATH/mvp/logs_to_json.py" "$READ_WRITE_CHECK_LOG" "$READ_WRITE_CHECK_JSON"
        MVP_JSONS+=("$READ_WRITE_CHECK_JSON")
        # Apply waivers
        apply_waivers "MVP" "$READ_WRITE_CHECK_JSON"
    fi

    # Generate combined MVP detailed and summary HTML reports
    MVP_DETAILED_HTML="$HTMLS_DIR/MVP_detailed.html"
    MVP_SUMMARY_HTML="$HTMLS_DIR/MVP_summary.html"

    if [ ${#MVP_JSONS[@]} -gt 0 ]; then
        MVP_PROCESSED=1
        python3 "$SCRIPTS_PATH/mvp/json_to_html.py" "${MVP_JSONS[@]}" "$MVP_DETAILED_HTML" "$MVP_SUMMARY_HTML" --include-drop-down
    fi
fi

# Paths for UEFI version log and Device Tree DTS
UEFI_VERSION_LOG="$LOGS_PATH/uefi_dump/uefi_version.log"
DEVICE_TREE_DTS="$LOGS_PATH/linux_tools/device_tree.dts"

# Check if UEFI_VERSION_LOG exists
if [ ! -f "$UEFI_VERSION_LOG" ]; then
    echo "WARNING: UEFI version log '$(basename "$UEFI_VERSION_LOG")' not found."
    UEFI_VERSION_LOG=""
fi

if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    # Check if DEVICE_TREE_DTS exists
    if [ ! -f "$DEVICE_TREE_DTS" ]; then
        echo "WARNING: Device Tree DTS file '$(basename "$DEVICE_TREE_DTS")' not found."
        DEVICE_TREE_DTS=""
    fi
fi

# Generate ACS Summary
ACS_SUMMARY_HTML="$HTMLS_DIR/acs_summary.html"

# Build the command to call generate_acs_summary.py
GENERATE_ACS_SUMMARY_CMD="python3 \"$SCRIPTS_PATH/generate_acs_summary.py\""

# Include BSA summary (always processed)
GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/BSA_summary.html\""

# Include SBSA summary only if processed
if [ $SBSA_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/SBSA_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include FWTS summary (always processed)
GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/fwts_summary.html\""

# Include SCT summary (always processed)
GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/SCT_summary.html\""

# Include MVP summary only if processed
if [ $MVP_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$MVP_SUMMARY_HTML\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Add the output HTML path
GENERATE_ACS_SUMMARY_CMD+=" \"$ACS_SUMMARY_HTML\""

# Add optional arguments
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

# Execute the generate_acs_summary.py script
eval $GENERATE_ACS_SUMMARY_CMD

# Summary Prints

# Always print BSA messages
if [ $BSA_PROCESSED -eq 1 ]; then
    echo "BSA UEFI Log          : $BSA_LOG"
    echo "BSA JSON              : $BSA_JSON"
    echo "BSA Detailed Summary  : $HTMLS_DIR/BSA_detailed.html"
    echo "BSA Summary           : $HTMLS_DIR/BSA_summary.html"
    echo ""
fi

# Print SBSA messages only if processed
if [ $SBSA_PROCESSED -eq 1 ]; then
    echo "SBSA UEFI Log         : $SBSA_LOG"
    echo "SBSA JSON             : $SBSA_JSON"
    echo "SBSA Detailed Summary : $HTMLS_DIR/SBSA_detailed.html"
    echo "SBSA Summary          : $HTMLS_DIR/SBSA_summary.html"
    echo ""
fi

# Always print FWTS messages
if [ $FWTS_PROCESSED -eq 1 ]; then
    echo "FWTS Log              : $FWTS_LOG"
    echo "FWTS JSON             : $FWTS_JSON"
    echo "FWTS Detailed Summary : $HTMLS_DIR/fwts_detailed.html"
    echo "FWTS Summary          : $HTMLS_DIR/fwts_summary.html"
    echo ""
fi

# Always print SCT messages
if [ $SCT_PROCESSED -eq 1 ]; then
    echo "SCT Log               : $SCT_LOG"
    echo "SCT JSON              : $SCT_JSON"
    echo "SCT Detailed Summary  : $HTMLS_DIR/SCT_detailed.html"
    echo "SCT Summary           : $HTMLS_DIR/SCT_summary.html"
    echo ""
fi

# Print MVP messages only if processed
if [ $MVP_PROCESSED -eq 1 ]; then
    echo "MVP Logs Processed"
    echo "MVP Detailed Summary : $MVP_DETAILED_HTML"
    echo "MVP Summary          : $MVP_SUMMARY_HTML"
    echo ""
fi

echo "ACS Summary  : $ACS_SUMMARY_HTML"
echo ""

# Output merged JSON file
MERGED_JSON="$JSONS_DIR/merged_results.json"

# Build list of existing JSON files
JSON_FILES=()

# Include BSA JSON file
if [ -f "$BSA_JSON" ]; then
    JSON_FILES+=("$BSA_JSON")
else
    echo "WARNING: $(basename "$BSA_JSON") not found. Skipping this file."
fi

# Include SBSA JSON file only if processed
if [ $SBSA_PROCESSED -eq 1 ] && [ -f "$SBSA_JSON" ]; then
    JSON_FILES+=("$SBSA_JSON")
elif [ $SBSA_PROCESSED -eq 1 ]; then
    echo "WARNING: $(basename "$SBSA_JSON") not found. Skipping this file."
fi

# Include FWTS JSON file
if [ -f "$FWTS_JSON" ]; then
    JSON_FILES+=("$FWTS_JSON")
else
    echo "WARNING: $(basename "$FWTS_JSON") not found. Skipping this file."
fi

# Include SCT JSON file
if [ -f "$SCT_JSON" ]; then
    JSON_FILES+=("$SCT_JSON")
else
    echo "WARNING: $(basename "$SCT_JSON") not found. Skipping this file."
fi

# Include MVP JSON files only if processed
if [ $MVP_PROCESSED -eq 1 ] && [ ${#MVP_JSONS[@]} -gt 0 ]; then
    JSON_FILES+=("${MVP_JSONS[@]}")
elif [ $MVP_PROCESSED -eq 1 ]; then
    echo "WARNING: No MVP JSON files found. Skipping MVP files."
fi

# Merge all existing JSON files into one
if [ ${#JSON_FILES[@]} -gt 0 ]; then
    python3 "$SCRIPTS_PATH/merge_jsons.py" "$MERGED_JSON" "${JSON_FILES[@]}"
    echo "Merged JSON created at: $MERGED_JSON"
else
    echo "No JSON files to merge."
fi

echo ""
