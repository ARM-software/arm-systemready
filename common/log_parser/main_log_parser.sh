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

# Define color codes
YELLOW='\033[1;33m' # Yellow for WARNING
RED='\033[0;31m'   # Red for ERROR
NC='\033[0m' # No Color (Reset)

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
YOCTO_FLAG="/mnt/c/Users/cherat01/ATEG/LOG_POST_SCRIPTS/yocto_image.flag"

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

# Check if waiver.json and test_category.json are provided
if [ -n "$WAIVER_JSON" ];  then
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
        echo -e "${YELLOW}WARNING: Log file '$(basename "$1")' is not present at the given directory.${NC}"
        return 1
    fi
    return 0
}

# Function to apply waivers
apply_waivers() {
    local suite_name="$1"
    local json_file="$2"

    if [ "$WAIVERS_APPLIED" -eq 1 ]; then
        python3 "$SCRIPTS_PATH/apply_waivers.py" "$suite_name" "$json_file" "$WAIVER_JSON" "$test_category" --quiet
 #   else
 #       echo "Waivers not applied for suite '$suite_name' as waiver files are not provided."
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
BBSR_FWTS_PROCESSED=0
BBSR_SCT_PROCESSED=0
Standalone_PROCESSED=0
OS_TESTS_PROCESSED=0
CAPSULE_PROCESSED=0


# BSA UEFI and Kernel Log Parsing
#################################
BSA_LOG="$LOGS_PATH/uefi/BsaResults.log"
BSA_KERNEL_LOG="$LOGS_PATH/linux_acs/bsa_acs_app/BsaResultsKernel.log"
if [ ! -f "$BSA_KERNEL_LOG" ]; then
    BSA_KERNEL_LOG="$LOGS_PATH/linux/BsaResultsKernel.log"
fi
BSA_JSON="$JSONS_DIR/bsa.json"
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
    if [ $? -ne 0 ]; then
        BSA_PROCESSED=0
        echo -e "${RED}ERROR: BSA logs parsing to json failed.${NC}"
    else
        # Apply waivers
        apply_waivers "BSA" "$BSA_JSON"
        python3 "$SCRIPTS_PATH/bsa/json_to_html.py" "$BSA_JSON" "$HTMLS_DIR/bsa_detailed.html" "$HTMLS_DIR/bsa_summary.html"
    fi
else
    echo -e "${YELLOW}WARNING: Skipping BSA log parsing as the log files are missing.${NC}"
    echo ""
fi


# SBSA UEFI and Kernel Log Parsing
##################################
if [ $YOCTO_FLAG_PRESENT -eq 0 ]; then

    SBSA_LOG="$LOGS_PATH/uefi/SbsaResults.log"
    SBSA_KERNEL_LOG="$LOGS_PATH/linux/SbsaResultsKernel.log"
    SBSA_JSON="$JSONS_DIR/sbsa.json"
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
            if [ $? -ne 0 ]; then
                SBSA_PROCESSED=0
                echo -e "${RED}ERROR: SBSA logs parsing to json failed.${NC}"
            else
	        # Apply waivers
                apply_waivers "SBSA" "$SBSA_JSON"
                python3 "$SCRIPTS_PATH/bsa/json_to_html.py" "$SBSA_JSON" "$HTMLS_DIR/sbsa_detailed.html" "$HTMLS_DIR/sbsa_summary.html"
	    fi
        else
            echo -e "${YELLOW}WARNING: Skipping SBSA log parsing as the log files are missing.${NC}"
            echo ""
        fi
    fi
fi


# FWTS UEFI Log Parsing
#######################
FWTS_LOG="$LOGS_PATH/fwts/FWTSResults.log"
FWTS_JSON="$JSONS_DIR/fwts.json"
if check_file "$FWTS_LOG"; then
    FWTS_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/fwts/logs_to_json.py" "$FWTS_LOG" "$FWTS_JSON"
    if [ $? -ne 0 ]; then
        FWTS_PROCESSED=0
        echo -e "${RED}ERROR: FWTS logs parsing to json failed.${NC}"
    else
        # Apply waivers
        apply_waivers "FWTS" "$FWTS_JSON"
        python3 "$SCRIPTS_PATH/bbr/fwts/json_to_html.py" "$FWTS_JSON" "$HTMLS_DIR/fwts_detailed.html" "$HTMLS_DIR/fwts_summary.html"
    fi
else
    echo -e "${YELLOW}WARNING: Skipping FWTS log parsing as the log file is missing.${NC}"
    echo ""
fi


# SCT Log Parsing
#################
SCT_LOG="$LOGS_PATH/sct_results/Overall/Summary.log"
SCT_JSON="$JSONS_DIR/sct.json"
if check_file "$SCT_LOG"; then
    SCT_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/sct/logs_to_json.py" "$SCT_LOG" "$SCT_JSON"
    if [ $? -ne 0 ]; then
        SCT_PROCESSED=0
        echo -e "${RED}ERROR: SCT logs parsing to json failed.${NC}"
    else
        # Apply waivers
        apply_waivers "SCT" "$SCT_JSON"
        python3 "$SCRIPTS_PATH/bbr/sct/json_to_html.py" "$SCT_JSON" "$HTMLS_DIR/sct_detailed.html" "$HTMLS_DIR/sct_summary.html"
    fi
else
    echo -e "${YELLOW}WARNING: Skipping SCT log parsing as the log file is missing.${NC}"
    echo ""
fi


# BBSR FWTS Log Parsing
#######################
BBSR_FWTS_LOG="$LOGS_PATH/BBSR/fwts/FWTSResults.log"
BBSR_FWTS_JSON="$JSONS_DIR/bbsr_fwts.json"
if check_file "$BBSR_FWTS_LOG"; then
    BBSR_FWTS_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/fwts/logs_to_json.py" "$BBSR_FWTS_LOG" "$BBSR_FWTS_JSON"
    # Apply waivers
    apply_waivers "BBSR-FWTS" "$BBSR_FWTS_JSON"
    python3 "$SCRIPTS_PATH/bbr/fwts/json_to_html.py" "$BBSR_FWTS_JSON" "${HTMLS_DIR}/bbsr_fwts_detailed.html" "${HTMLS_DIR}/bbsr_fwts_summary.html"
else
    echo -e "${YELLOW}WARNING: Skipping BBSR FWTS log parsing as the log file is missing.${NC}"
    echo ""
fi


# BBSR SCT Log Parsing
######################
BBSR_SCT_LOG="$LOGS_PATH/BBSR/sct_results/Overall/Summary.log"
BBSR_SCT_JSON="$JSONS_DIR/bbsr_sct.json"
if check_file "$BBSR_SCT_LOG"; then
    BBSR_SCT_PROCESSED=1
    python3 "$SCRIPTS_PATH/bbr/sct/logs_to_json.py" "$BBSR_SCT_LOG" "$BBSR_SCT_JSON"
    # Apply waivers
    apply_waivers "BBSR-SCT" "$BBSR_SCT_JSON"
    python3 "$SCRIPTS_PATH/bbr/sct/json_to_html.py" "$BBSR_SCT_JSON" "${HTMLS_DIR}/bbsr_sct_detailed.html" "${HTMLS_DIR}/bbsr_sct_summary.html"
else
    echo -e "${YELLOW}WARNING: Skipping BBSR SCT log parsing as the log file is missing.${NC}"
    echo ""
fi


# Standalone tests Logs Parsing
##################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    LINUX_TOOLS_LOGS_PATH="$LOGS_PATH/linux_tools"

    # Paths for Standalone tests logs and JSON files
    DT_KSELFTEST_LOG="$LINUX_TOOLS_LOGS_PATH/dt_kselftest.log"
    DT_VALIDATE_LOG="$LINUX_TOOLS_LOGS_PATH/dt-validate.log"
    ETHTOOL_TEST_LOG="$LINUX_TOOLS_LOGS_PATH/ethtool-test.log"
    READ_WRITE_CHECK_LOG="$LINUX_TOOLS_LOGS_PATH/read_write_check_blk_devices.log"

    DT_KSELFTEST_JSON="$JSONS_DIR/dt_kselftest.json"
    DT_VALIDATE_JSON="$JSONS_DIR/dt_validate.json"
    ETHTOOL_TEST_JSON="$JSONS_DIR/ethtool_test.json"
    READ_WRITE_CHECK_JSON="$JSONS_DIR/read_write_check_blk_devices.json"

    Standalone_JSONS=()

    # Process each Standalone tests log
    if check_file "$DT_KSELFTEST_LOG"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" "$DT_KSELFTEST_LOG" "$DT_KSELFTEST_JSON"
        Standalone_JSONS+=("$DT_KSELFTEST_JSON")
        # Apply waivers
        apply_waivers "Standalone_tests" "$DT_KSELFTEST_JSON"
    fi
    if check_file "$DT_VALIDATE_LOG"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" "$DT_VALIDATE_LOG" "$DT_VALIDATE_JSON"
        Standalone_JSONS+=("$DT_VALIDATE_JSON")
        # Apply waivers
        apply_waivers "Standalone_tests" "$DT_VALIDATE_JSON"
    fi
    if check_file "$ETHTOOL_TEST_LOG"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" "$ETHTOOL_TEST_LOG" "$ETHTOOL_TEST_JSON"
        Standalone_JSONS+=("$ETHTOOL_TEST_JSON")
        # Apply waivers
        apply_waivers "Standalone_tests" "$ETHTOOL_TEST_JSON"
    fi
    if check_file "$READ_WRITE_CHECK_LOG"; then
        python3 "$SCRIPTS_PATH/standalone_tests/logs_to_json.py" "$READ_WRITE_CHECK_LOG" "$READ_WRITE_CHECK_JSON"
        Standalone_JSONS+=("$READ_WRITE_CHECK_JSON")
        # Apply waivers
        apply_waivers "Standalone_tests" "$READ_WRITE_CHECK_JSON"
    fi
    # Generate combined Standalone detailed and summary HTML reports
    Standalone_DETAILED_HTML="$HTMLS_DIR/standalone_tests_detailed.html"
    Standalone_SUMMARY_HTML="$HTMLS_DIR/standalone_tests_summary.html"

    if [ ${#Standalone_JSONS[@]} -gt 0 ]; then
        Standalone_PROCESSED=1
        python3 "$SCRIPTS_PATH/standalone_tests/json_to_html.py" "${Standalone_JSONS[@]}" "$Standalone_DETAILED_HTML" "$Standalone_SUMMARY_HTML" --include-drop-down
    fi
fi


# OS Tests Logs Parsing
###########################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then

    OS_LOGS_PATH="$(dirname "$LOGS_PATH")/os-logs"
    OS_JSONS_DIR="$JSONS_DIR"
    mkdir -p "$OS_JSONS_DIR"
    OS_JSONS=()
    BOOT_SOURCES_PATHS=()  # Initialize array for boot_sources_paths
    # Find all directories under os-logs starting with 'linux'
    if [ -d "$OS_LOGS_PATH" ]; then
        for OS_DIR in "$OS_LOGS_PATH"/linux*; do
            if [ -d "$OS_DIR" ]; then
                OS_NAME=$(basename "$OS_DIR")
                ETH_TOOL_LOG="$OS_DIR/ethtool_test.log"
                BOOT_SOURCES_LOG="$OS_DIR/boot_sources.log"  # Path to boot_sources.log

                if [ -f "$ETH_TOOL_LOG" ]; then
                    # Generate output JSON file path
                    OUTPUT_JSON="$OS_JSONS_DIR/ethtool_test_${OS_NAME}.json"
                    # Call logs_to_json.py
                    python3 "$SCRIPTS_PATH/os_tests/logs_to_json.py" "$ETH_TOOL_LOG" "$OUTPUT_JSON" "$OS_NAME"
                    # Add to list of JSONs
                    OS_JSONS+=("$OUTPUT_JSON")
                    # Apply waivers if necessary
                    apply_waivers "os Tests" "$OUTPUT_JSON"
                    OS_TESTS_PROCESSED=1
                    # Add BOOT_SOURCES_LOG path to BOOT_SOURCES_PATHS
                    if [ -f "$BOOT_SOURCES_LOG" ]; then
                        BOOT_SOURCES_PATHS+=("$BOOT_SOURCES_LOG")
                    else
                        BOOT_SOURCES_PATHS+=("Unknown")
                    fi
                else
                    echo "WARNING: ethtool_test.log not found in $OS_DIR"
                fi
            fi
        done
    else
        echo -e "${YELLOW}WARNING: os-logs directory not found at $OS_LOGS_PATH${NC}"
    fi
    # Generate combined OS tests detailed and summary HTML reports
    if [ ${#OS_JSONS[@]} -gt 0 ]; then
        OS_DETAILED_HTML="$HTMLS_DIR/os_tests_detailed.html"
        OS_SUMMARY_HTML="$HTMLS_DIR/os_tests_summary.html"
        # Pass the boot_sources_paths as arguments
        python3 "$SCRIPTS_PATH/os_tests/json_to_html.py" "${OS_JSONS[@]}" "$OS_DETAILED_HTML" "$OS_SUMMARY_HTML" --include-drop-down --boot-sources-paths "${BOOT_SOURCES_PATHS[@]}"
    fi
fi


# Capsule Update Logs Parsing
#############################
if [ $YOCTO_FLAG_PRESENT -eq 1 ]; then
    # We no longer need to define logs directory or pass arguments since paths are hardcoded in the script
    CAPSULE_JSON="$JSONS_DIR/capsule_update.json"
    # Run the logs_to_json.py script
    python3 "$SCRIPTS_PATH/capsule_update/logs_to_json.py" \
        --capsule_update_log "$(dirname "$LOGS_PATH")/fw/capsule-update.log" \
        --capsule_on_disk_log "$(dirname "$LOGS_PATH")/fw/capsule-on-disk.log" \
        --capsule_test_results_log "$LOGS_PATH/app_output/capsule_test_results.log" \
        --output_file "$CAPSULE_JSON"
    # Check if the JSON file was created
    if [ -f "$CAPSULE_JSON" ]; then
        CAPSULE_PROCESSED=1
        # Apply waivers if necessary
        apply_waivers "Capsule Update" "$CAPSULE_JSON"
        # Generate HTML reports
        python3 "$SCRIPTS_PATH/capsule_update/json_to_html.py" "$CAPSULE_JSON" "$HTMLS_DIR/capsule_update_detailed.html" "$HTMLS_DIR/capsule_update_summary.html"
        echo ""
    else
        echo -e "${YELLOW}WARNING: Capsule Update JSON file not created. Skipping Capsule Update log parsing.${NC}"
        echo ""
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
if [ $BSA_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bsa_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include SBSA summary only if processed
if [ $SBSA_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/sbsa_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include FWTS summary (always processed)
if [ $FWTS_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/fwts_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include SCT summary (always processed)
if [ $SCT_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/sct_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include BBSR-FWTS summary (always processed)
if [ $BBSR_FWTS_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bbsr_fwts_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include BBSR-SCT summary (always processed)
if [ $BBSR_SCT_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/bbsr_sct_summary.html\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include Standalone summary only if processed
if [ $Standalone_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$Standalone_SUMMARY_HTML\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include OS Tests summary only if processed
if [ $OS_TESTS_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$OS_SUMMARY_HTML\""
else
    GENERATE_ACS_SUMMARY_CMD+=" \"\""
fi

# Include Capsule Update summary only if processed
if [ $CAPSULE_PROCESSED -eq 1 ]; then
    GENERATE_ACS_SUMMARY_CMD+=" \"$HTMLS_DIR/capsule_update_summary.html\""
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

print_path=0  # For debug only

if [ $print_path -eq 1 ]; then
# Always print BSA messages
if [ $BSA_PROCESSED -eq 1 ]; then
#    echo "BSA UEFI Log              : $BSA_LOG"
    echo "BSA JSON                  : $BSA_JSON"
    echo "BSA Detailed Summary      : $HTMLS_DIR/bsa_detailed.html"
    echo "BSA Summary               : $HTMLS_DIR/bsa_summary.html"
    echo ""
fi

# Print SBSA messages only if processed
if [ $SBSA_PROCESSED -eq 1 ]; then
#    echo "SBSA UEFI Log             : $SBSA_LOG"
    echo "SBSA JSON                 : $SBSA_JSON"
    echo "SBSA Detailed Summary     : $HTMLS_DIR/sbsa_detailed.html"
    echo "SBSA Summary               : $HTMLS_DIR/sbsa_summary.html"
    echo ""
fi

# Always print FWTS messages
if [ $FWTS_PROCESSED -eq 1 ]; then
#    echo "FWTS Log                  : $FWTS_LOG"
    echo "FWTS JSON                 : $FWTS_JSON"
    echo "FWTS Detailed Summary     : $HTMLS_DIR/fwts_detailed.html"
    echo "FWTS Summary              : $HTMLS_DIR/fwts_summary.html"
    echo ""
fi

# Always print SCT messages
if [ $SCT_PROCESSED -eq 1 ]; then
#    echo "SCT Log                   : $SCT_LOG"
    echo "SCT JSON                  : $SCT_JSON"
    echo "SCT Detailed Summary      : $HTMLS_DIR/sct_detailed.html"
    echo "SCT Summary               : $HTMLS_DIR/sct_summary.html"
    echo ""
fi

# Print BBSR FWTS messages
if [ $BBSR_FWTS_PROCESSED -eq 1 ]; then
#    echo "BBSR FWTS Log             : $BBSR_FWTS_LOG"
    echo "BBSR FWTS JSON            : $BBSR_FWTS_JSON"
    echo "BBSR FWTS Detailed Summary: $HTMLS_DIR/bbsr_fwts_detailed.html"
    echo "BBSR FWTS Summary         : $HTMLS_DIR/bbsr_fwts_summary.html"
    echo ""
fi

# Print BBSR SCT messages
if [ $BBSR_SCT_PROCESSED -eq 1 ]; then
#    echo "BBSR SCT Log              : $BBSR_SCT_LOG"
    echo "BBSR SCT JSON             : $BBSR_SCT_JSON"
    echo "BBSR SCT Detailed Summary : $HTMLS_DIR/bbsr_sct_detailed.html"
    echo "BBSR SCT Summary          : $HTMLS_DIR/bbsr_sct_summary.html"
    echo ""
fi

# Print Standalone messages only if processed
if [ $Standalone_PROCESSED -eq 1 ]; then
    echo "Standalone tests Detailed Summary      : $Standalone_DETAILED_HTML"
    echo "Standalone tests Summary               : $Standalone_SUMMARY_HTML"
    echo ""
fi

# Print OS Tests messages only if processed
if [ $OS_TESTS_PROCESSED -eq 1 ]; then
    echo "OS tests Detailed Summary : $OS_DETAILED_HTML"
    echo "OS tests Summary          : $OS_SUMMARY_HTML"
    echo ""
fi

# Print Capsule Update messages only if processed
if [ $CAPSULE_PROCESSED -eq 1 ]; then
 #   echo "Capsule Update Log              : $CAPSULE_LOG"
    echo "Capsule Update JSON             : $CAPSULE_JSON"
    echo "Capsule Update Detailed Summary : $HTMLS_DIR/capsule_update_detailed.html"
    echo "Capsule Update Summary          : $HTMLS_DIR/capsule_update_summary.html"
    echo ""
fi

fi
echo "ACS Summary    : $ACS_SUMMARY_HTML"
echo ""

# Output merged JSON file
MERGED_JSON="$JSONS_DIR/merged_results.json"

# Build list of existing JSON files
JSON_FILES=()

# Include BSA JSON file
if [ -f "$BSA_JSON" ]; then
    JSON_FILES+=("$BSA_JSON")
else
    echo -e "${YELLOW}WARNING: NO bsa tests json file found. Skipping this file.${NC}."
fi

# Include SBSA JSON file only if processed
if [ $SBSA_PROCESSED -eq 1 ] && [ -f "$SBSA_JSON" ]; then
    JSON_FILES+=("$SBSA_JSON")
elif [ $SBSA_PROCESSED -eq 1 ]; then
    echo -e "${YELLOW}WARNING: NO sbsa tests json file found. Skipping this file.${NC}"
fi

# Include FWTS JSON file
if [ -f "$FWTS_JSON" ]; then
    JSON_FILES+=("$FWTS_JSON")
else
    echo -e "${YELLOW}WARNING: NO fwts tests json file found. Skipping this file.${NC}"
fi

# Include SCT JSON file
if [ -f "$SCT_JSON" ]; then
    JSON_FILES+=("$SCT_JSON")
else
    echo -e "${YELLOW}WARNING: NO sct tests json file found. Skipping this file.${NC}"
fi

# Include BBSR FWTS JSON file
if [ $BBSR_FWTS_PROCESSED -eq 1 ] && [ -f "$BBSR_FWTS_JSON" ]; then
    JSON_FILES+=("$BBSR_FWTS_JSON")
else
    echo -e "${YELLOW}WARNING: NO bbsr fwts tests json file found. Skipping this file.${NC}"
fi

# Include BBSR SCT JSON file
if [ $BBSR_SCT_PROCESSED -eq 1 ] && [ -f "$BBSR_SCT_JSON" ]; then
    JSON_FILES+=("$BBSR_SCT_JSON")
else
    echo -e "${YELLOW}WARNING: NO bbsr sct tests json file found. Skipping this file.${NC}"
fi

# Include Standalone JSON files only if processed
if [ $Standalone_PROCESSED -eq 1 ] && [ ${#Standalone_JSONS[@]} -gt 0 ]; then
    JSON_FILES+=("${Standalone_JSONS[@]}")
elif [ $Standalone_PROCESSED -eq 1 ]; then
    echo -e "${YELLOW}WARNING: NO Standalone tests json files found. Skipping this files.${NC}"
fi

# Include OS tests JSON files in merged JSON
if [ $OS_TESTS_PROCESSED -eq 1 ] && [ ${#OS_JSONS[@]} -gt 0 ]; then
    JSON_FILES+=("${OS_JSONS[@]}")
elif [ $OS_TESTS_PROCESSED -eq 1 ]; then
    echo -e "${YELLOW}WARNING: NO OS tests json files found. Skipping this files.${NC}"
fi

# Include Capsule Update JSON file
if [ $CAPSULE_PROCESSED -eq 1 ] && [ -f "$CAPSULE_JSON" ]; then
    JSON_FILES+=("$CAPSULE_JSON")
elif [ $CAPSULE_PROCESSED -eq 1 ]; then
    echo -e "${YELLOW}WARNING: NO capsule test json file found. Skipping this file.${NC}"
fi

# Merge all existing JSON files into one
if [ ${#JSON_FILES[@]} -gt 0 ]; then
    python3 "$SCRIPTS_PATH/merge_jsons.py" "$MERGED_JSON" "${JSON_FILES[@]}"
    echo "ACS Merged JSON: $MERGED_JSON"
else
    echo "No JSON files to merge."
fi

echo ""
