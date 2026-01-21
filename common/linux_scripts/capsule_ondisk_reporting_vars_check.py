#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Capsule On-Disk Update Reporting Variables Validator.

This module validates UEFI capsule on-disk reporting variables according to the EBBR 2.2.0 specification
and UEFI Specification Section 8.5.6 (Capsule On-Disk Update Reporting Variables).

Test applicability note:
  - If OsIndicationsSupported.EFI_OS_INDICATIONS_FILE_CAPSULE_DELIVERY_SUPPORTED is set,
    the firmware claims capsule "on disk" support and this test is mandatory.
  - Otherwise, this test is not applicable and is skipped.

The module checks for the presence and proper attributes of three types of
EFI variables in the Capsule Report GUID namespace:
  - CapsuleMax: The maximum size supported for capsule data
  - CapsuleLast: The name of the last capsule processed
  - CapsuleNNNN: Individual capsule entries (where NNNN is a 4-digit hex number)

Each variable must have specific EFI variable attributes as per the specification:
  - CapsuleMax: BootService Access + Runtime Access (no Non-Volatile)
  - CapsuleLast: Non-Volatile + BootService Access + Runtime Access
  - CapsuleNNNN: Non-Volatile + BootService Access + Runtime Access

This module is typically run after a capsule update operation to validate that
the firmware correctly implemented capsule on-disk update reporting.
"""

import os
import re
import struct
import sys

# Attribute bits (UEFI Specification 8.2 - GetVariable and SetVariable)
# These define the access and persistence characteristics of EFI variables
EFI_VARIABLE_NON_VOLATILE       = 0x00000001  # Variable persists across boot cycles
EFI_VARIABLE_BOOTSERVICE_ACCESS = 0x00000002  # Variable accessible during Boot Services phase
EFI_VARIABLE_RUNTIME_ACCESS     = 0x00000004  # Variable accessible during Runtime phase

# Expected attributes per UEFI Spec 8.5.6 (Capsule On-Disk Update Reporting Variables)
# CapsuleMax must be accessible but not persistent (cleared on each boot)
EXPECTED_ATTR_CAPSULE_MAX  = EFI_VARIABLE_BOOTSERVICE_ACCESS | EFI_VARIABLE_RUNTIME_ACCESS
# CapsuleLast and CapsuleNNNN must be persistent and accessible in both Boot Services and Runtime
EXPECTED_ATTR_CAPSULE_LAST = EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS | EFI_VARIABLE_RUNTIME_ACCESS
EXPECTED_ATTR_CAPSULE_NNNN = EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS | EFI_VARIABLE_RUNTIME_ACCESS

# Capsule Report GUID per UEFI Specification (Section 8.5.6)
# This GUID identifies the namespace for capsule on-disk update reporting variables
CapsuleReportGuid = "39b68c46-f7fb-441b-b6ec-16b0f69821f3"

# UEFI Global Variable GUID (for OsIndicationsSupported)
GlobalVariableGuid = "8be4df61-93ca-11d2-aa0d-00e098032b8c"

# EFI_OS_INDICATIONS_FILE_CAPSULE_DELIVERY_SUPPORTED bit (UEFI Spec)
EFI_OS_INDICATIONS_FILE_CAPSULE_DELIVERY_SUPPORTED = 0x0000000000000004

# Path to EFI variables in sysfs (requires efivarfs to be mounted)
EFIVAR_PATH = "/sys/firmware/efi/efivars"

# Log file path for test results
LOG_FILE = "/mnt/acs_results_template/fw/capsule_test_results.log"

# Regular expression to match valid capsule variable names (CapsuleNNNN where NNNN is 4 hex digits)
CAPSULE_NAME_RE = re.compile(r"^Capsule[0-9A-Fa-f]{4}$")

def _ensure_log_dir():
    """Ensure the log directory exists, creating it if necessary."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    except (OSError, IOError):
        pass

def log(msg=""):
    """
    Append a message to the test results log file.

    Args:
        msg (str): The message to log. Empty string appends a blank line.

    This function safely appends messages to the log file, creating the directory
    if needed and handling any I/O exceptions gracefully.
    """
    try:
        _ensure_log_dir()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except (OSError, IOError):
        pass

def status(ok: bool):
    """
    Convert a boolean test result to a status string.

    Args:
        ok (bool): True if test passed, False if failed

    Returns:
        str: "PASSED" if ok is True, "WARNING" otherwise
    """
    return "PASSED" if ok else "WARNING"

def read_efi_var(var_name, guid=CapsuleReportGuid):
    """
    Read an EFI variable from efivarfs and extract its attributes and value.

    Args:
        var_name (str): The name of the variable to read (without GUID suffix)
        guid (str): EFI variable GUID namespace (lowercase, without braces)

    Returns:
        tuple: (attributes, value) where attributes is an int (4-byte little-endian)
               and value is bytes containing the variable data. Returns (None, None)
               if the variable doesn't exist or cannot be read.

    The EFI variable format in efivarfs is: [4 bytes of attributes][variable data]
    Attributes are stored as a 32-bit little-endian integer.
    """
    path = f"{EFIVAR_PATH}/{var_name}-{guid}"
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None, None
    if len(data) < 4:
        return None, None
    # Extract 4-byte little-endian attributes field
    attrs = struct.unpack("<I", data[:4])[0]
    value = data[4:]
    return attrs, value

def decode_char16_11_no_nul(value):
    """
    Decode a CHAR16[11] (22-byte) UTF-16LE string without null terminator.

    Args:
        value (bytes): Raw bytes containing the CHAR16[11] string

    Returns:
        str: Decoded UTF-16LE string, with replacement characters for invalid sequences

    UEFI Specification defines CapsuleMax and CapsuleLast as CHAR16[11] arrays
    (11 Unicode characters = 22 bytes). These are not null-terminated.
    """
    raw = value[:22]  # CHAR16[11], no NULL terminator
    try:
        return raw.decode("utf-16le")
    except UnicodeDecodeError:
        return raw.decode("utf-16le", errors="replace")

def os_indications_supports_ondisk():
    """
    Check whether the firmware claims capsule on-disk support via OsIndicationsSupported.

    Returns:
        tuple: (supported, value)
            supported (bool): True if EFI_OS_INDICATIONS_FILE_CAPSULE_DELIVERY_SUPPORTED is set
            value (int or None): Raw OsIndicationsSupported value, or None if unavailable
    """
    attrs, value = read_efi_var("OsIndicationsSupported", guid=GlobalVariableGuid)
    if attrs is None or value is None or len(value) < 8:
        return False, None
    indications = struct.unpack("<Q", value[:8])[0]
    return bool(indications & EFI_OS_INDICATIONS_FILE_CAPSULE_DELIVERY_SUPPORTED), indications

def log_attr_test(var_name: str, expected: int, actual):
    """
    Log the results of an EFI variable attribute validation test.

    Args:
        var_name (str): Name of the EFI variable being tested
        expected (int): Expected attribute flags (bitmask of EFI_VARIABLE_*)
        actual (int or None): Actual attribute flags read from the variable,
                              or None if variable is inaccessible

    Returns:
        bool: True if actual attributes match expected, False otherwise

    This function logs both INFO and RESULTS lines according to the test output
    format used by the ACS test suite.
    """
    log(f"INFO: {var_name} Variable Attribute Test: expected attributed value:0x{expected:X}")

    if actual is None:
        log(f"RESULTS: {var_name} Variable Attribute Test: expected attributed value:0x{expected:X}, "
            f"actual attributes Value:<N/A>, Status - WARNING")
        return False

    ok = (actual == expected)
    log(f"RESULTS: {var_name} Variable Attribute Test: expected attributed value:0x{expected:X}, "
        f"actual attributes Value:0x{actual:X}, Status - {status(ok)}")
    return ok

def check_capsulemax():
    """
    Validate the CapsuleMax EFI variable.

    CapsuleMax is a UEFI capsule on-disk update reporting variable that must:
    1. Exist and be readable from the Capsule Report GUID namespace
    2. Contain a CHAR16[11] string value matching the format "Capsule" followed
       by 4 hexadecimal digits (e.g., "Capsule0001")
    3. Have EFI variable attributes: BootService Access + Runtime Access
       (but NOT Non-Volatile, as it is cleared on each boot)

    Per UEFI Specification 8.5.6, CapsuleMax contains the maximum size of capsule
    data supported by the platform for on-disk updates.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    attrs, value = read_efi_var("CapsuleMax")
    if attrs is None:
        log("INFO: CapsuleMax Variable Test: CapsuleMax Variable - Not Found or Not Accessible")
        log("RESULTS: CapsuleMax Variable Test: WARNING")
        log_attr_test("CapsuleMax", EXPECTED_ATTR_CAPSULE_MAX, None)
        return False

    val = decode_char16_11_no_nul(value)
    log(f"INFO: CapsuleMax Variable Test: CapsuleMax - Found, Value - {val}")

    ok_len = (len(value) >= 22)
    ok_fmt = bool(CAPSULE_NAME_RE.fullmatch(val))
    ok_val = ok_len and ok_fmt
    log(f"RESULTS: CapsuleMax Variable Test: {status(ok_val)}")

    ok_attr = log_attr_test("CapsuleMax", EXPECTED_ATTR_CAPSULE_MAX, attrs)
    return ok_val and ok_attr

def check_capsulelast():
    """
    Validate the CapsuleLast EFI variable.

    CapsuleLast is a UEFI capsule on-disk update reporting variable that must:
    1. Exist and be readable from the Capsule Report GUID namespace
    2. Contain a CHAR16[11] string value matching the format "Capsule" followed
       by 4 hexadecimal digits (e.g., "Capsule0001")
    3. Have EFI variable attributes: Non-Volatile + BootService Access + Runtime Access
       (Non-Volatile flag is required so the last capsule processed is persisted)

    Per UEFI Specification 8.5.6, CapsuleLast contains the name of the last capsule
    that was processed during a capsule on-disk update operation.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    attrs, value = read_efi_var("CapsuleLast")
    if attrs is None:
        log("INFO: CapsuleLast Variable Test: CapsuleLast Variable - Not Found or Not Accessible")
        log("RESULTS: CapsuleLast Variable Test: WARNING")
        log_attr_test("CapsuleLast", EXPECTED_ATTR_CAPSULE_LAST, None)
        return False

    val = decode_char16_11_no_nul(value)
    log(f"INFO: CapsuleLast Variable Test: CapsuleLast Variable - Found, Value - {val}")

    ok_len = (len(value) >= 22)
    ok_fmt = bool(CAPSULE_NAME_RE.fullmatch(val))
    ok_val = ok_len and ok_fmt
    log(f"RESULTS: CapsuleLast Variable Test: {status(ok_val)}")

    ok_attr = log_attr_test("CapsuleLast", EXPECTED_ATTR_CAPSULE_LAST, attrs)
    return ok_val and ok_attr

def check_capsule_nnnn():
    """
    Validate all CapsuleNNNN EFI variables in the Capsule Report GUID namespace.

    CapsuleNNNN variables are UEFI capsule on-disk update reporting variables where
    NNNN is a 4-digit hexadecimal number. For each CapsuleNNNN found, this function:
    1. Verifies the variable can be read from efivarfs
    2. Validates it has the correct EFI variable attributes:
       Non-Volatile + BootService Access + Runtime Access

    Per UEFI Specification 8.5.6, CapsuleNNNN variables store information about
    individual capsule payloads processed during on-disk update operations. Multiple
    capsule entries can exist for a single update operation.

    The check iterates through all variables in the Capsule Report GUID namespace,
    filters for those matching the CapsuleNNNN pattern, and validates each one.
    If no CapsuleNNNN variables are found at all, the check passes (firmware may
    not have processed any capsules yet).

    Returns:
        bool: True if all found CapsuleNNNN variables are valid, or if none are
              found. False if any CapsuleNNNN variables fail validation.
    """
    suffix = "-" + CapsuleReportGuid

    try:
        entries = os.listdir(EFIVAR_PATH)
    except OSError:
        log("RESULTS: CapsuleNNNN Variable Test: efivarfs not accessible - WARNING")
        return False

    any_failed = False
    found_any = False

    # Iterate through all variables in efivarfs and filter for CapsuleNNNN entries
    for name in sorted(entries):
        if not name.endswith(suffix):
            continue

        # Extract variable name by removing the GUID suffix
        var = name[:-len(suffix)]
        # Check if variable name matches the CapsuleNNNN pattern (Capsule + 4 hex digits)
        if not CAPSULE_NAME_RE.fullmatch(var):
            continue

        found_any = True

        attrs, _value = read_efi_var(var)
        if attrs is None:
            log(f"INFO: CapsuleNNNN Variable Test: {var} - Not Accessible")
            log(f"RESULTS: CapsuleNNNN Variable Test: {var} Variable Test: WARNING")
            if not log_attr_test(var, EXPECTED_ATTR_CAPSULE_NNNN, None):
                any_failed = True
            continue

        log(f"INFO: CapsuleNNNN Variable Test: {var} - Found")
        log(f"RESULTS: CapsuleNNNN Variable Test: {var} Variable Test: PASSED")

        if not log_attr_test(var, EXPECTED_ATTR_CAPSULE_NNNN, attrs):
            any_failed = True

    if not found_any:
        log("RESULTS: CapsuleNNNN Variable Test: No CapsuleNNNN reporting variables found - WARNING")
        return True

    return not any_failed

def main():
    """
    Main entry point for capsule on-disk update reporting variables validation.

    This function orchestrates the validation of three types of capsule reporting
    variables in the following order:
    1. CapsuleMax - maximum capsule size supported
    2. CapsuleLast - name of the last processed capsule
    3. CapsuleNNNN - individual capsule entry variables

    Before any checks are run, this function verifies that efivarfs is mounted
    at /sys/firmware/efi/efivars, which is required to read EFI variables.

    Returns:
        int: Exit code for the script
            - 0 if all checks pass
            - 1 if efivarfs is not available
            - 2 if on-disk is not supported (checks skipped)
            - 3 if any of the capsule variable checks fail and on-disk is supported
    """
    log("\n")
    log("================================================================================================")
    log("Testing Capsule On-Disk Update Reporting Variables")
    log("================================================================================================")

    if not os.path.isdir(EFIVAR_PATH):
        log(f"RESULTS: {EFIVAR_PATH} not present. Please ensure efivarfs is enabled and mounted - WARNING")
        return 1

    on_disk_supported, os_indications_value = os_indications_supports_ondisk()
    if os_indications_value is None:
        log("INFO: OsIndicationsSupported not found or unreadable; capsule on-disk support not claimed")
    else:
        log(f"INFO: OsIndicationsSupported value: 0x{os_indications_value:X}")

    if not on_disk_supported:
        log("RESULTS: Capsule on-disk reporting variables test is not applicable - WARNING")
        exit_code = 2
        log(f"INFO: Exit code: {exit_code}")
        return exit_code

    log("INFO: OsIndicationsSupported indicates capsule on-disk support; running recommended  checks")

    failed = False

    if not check_capsulemax():
        failed = True
    log()

    if not check_capsulelast():
        failed = True
    log()

    if not check_capsule_nnnn():
        failed = True
    log()

    exit_code = 3 if failed else 0
    log(f"INFO: Exit code: {exit_code}")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
