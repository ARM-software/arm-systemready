#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
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
"""Public exports for the ACS test framework runner package."""

from .mock_loader import _resolve_runner_module_from_stack, stateful_run_router
from .mock_loader import ConfigError as MockLoaderConfigError
from .mock_helpers import (
    build_char16_payload,
    build_df_output,
    build_efi_var_bytes,
    build_ethtool_ip_address_output,
    build_ethtool_ip_link_line,
    build_ethtool_ip_link_show_line,
    build_fdisk_output,
    build_os_indications_var,
    build_run_result_from_outcome,
    build_sgdisk_partition_output,
    check_output_router,
    default_device_path,
    noop,
    normalize_ethtool_tool_path,
    passthrough_router,
    route_gateway,
    run_router,
    scenario_truthy,
    which_router,
)
from .case_data_builders import CaseBuildError, render_post_check_path
from .case_data_builders import expand_template as base_expand_template
from .runner_checks import (
    DEFAULT_CLI_TIMEOUT_SEC,
    DESTRUCTIVE_TEST_ENV,
    REAL_SUBPROCESS_RUN,
    ConfigError,
    CommandRunResult,
    detect_project_root,
    ensure_list,
    ensure_list_of_strings,
    ensure_string_or_list_of_strings,
    RunCaseOptions,
    SkipCase,
    TestMeta,
    TestOutcome,
    create_outcome,
    collect_function_names,
    create_runner_temp_dir,
    format_outcome_message,
    load_yaml_config,
    merge_mappings,
    normalize_suites,
    resolve_target_path,
    run_single_check,
    sanitize_name,
    load_module_from_path,
    normalize_completed_stream,
    read_source,
    sanitize_xml_text,
)
from .runner_reporting import (
    append_combined_case_log,
    append_run_header,
    build_config_error_outcome,
    build_report_path,
    cleanup_old_pytest_xml_reports,
    create_placeholder_xml,
    print_group_summary,
    remove_placeholder_xml,
    write_case_log,
    write_junit_xml,
)
__all__ = [
    "MockLoaderConfigError",
    "stateful_run_router",

    "build_char16_payload",
    "build_df_output",
    "build_efi_var_bytes",
    "build_ethtool_ip_address_output",
    "build_ethtool_ip_link_line",
    "build_ethtool_ip_link_show_line",
    "build_fdisk_output",
    "build_os_indications_var",
    "build_run_result_from_outcome",
    "build_sgdisk_partition_output",
    "check_output_router",
    "default_device_path",
    "noop",
    "normalize_ethtool_tool_path",
    "passthrough_router",
    "route_gateway",
    "run_router",
    "scenario_truthy",
    "which_router",
    "base_expand_template",

    "CaseBuildError",
    "render_post_check_path",

    "DEFAULT_CLI_TIMEOUT_SEC",
    "DESTRUCTIVE_TEST_ENV",
    "REAL_SUBPROCESS_RUN",
    "ConfigError",
    "CommandRunResult",
    "detect_project_root",
    "ensure_list",
    "ensure_list_of_strings",
    "ensure_string_or_list_of_strings",
    "RunCaseOptions",
    "SkipCase",
    "TestMeta",
    "TestOutcome",
    "create_outcome",
    "collect_function_names",
    "create_runner_temp_dir",
    "format_outcome_message",
    "load_yaml_config",
    "merge_mappings",
    "normalize_suites",
    "resolve_target_path",
    "run_single_check",
    "sanitize_name",
    "load_module_from_path",
    "normalize_completed_stream",
    "read_source",
    "sanitize_xml_text",

    "append_combined_case_log",
    "append_run_header",
    "build_config_error_outcome",
    "build_report_path",
    "cleanup_old_pytest_xml_reports",
    "create_placeholder_xml",
    "print_group_summary",
    "remove_placeholder_xml",
    "write_case_log",
    "write_junit_xml",
]
