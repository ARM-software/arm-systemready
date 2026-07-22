#!/bin/sh

# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0

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

CAPSULE_APP_DIR="/mnt/acs_tests/app"
CAPSULE_RESULTS_DIR="/mnt/acs_results_template/fw"
CAPSULE_SIGNED="${CAPSULE_APP_DIR}/signed_capsule.bin"
CAPSULE_UNAUTH="${CAPSULE_APP_DIR}/unauth.bin"
CAPSULE_TAMPERED="${CAPSULE_APP_DIR}/tampered.bin"
CAPSULE_TEST_RESULTS_LOG="${CAPSULE_RESULTS_DIR}/capsule_test_results.log"
CAPSULE_ON_DISK_LOG="${CAPSULE_RESULTS_DIR}/capsule-on-disk.log"
CAPSULE_TOOL="/usr/bin/systemready-scripts/capsule-tool.py"
CAPSULE_CHECK_FLAG="${CAPSULE_APP_DIR}/capsule_update_check.flag"
CAPSULE_UNSUPPORTED_FLAG="${CAPSULE_APP_DIR}/capsule_update_unsupport.flag"
CAPSULE_ERROR_FLAG="${CAPSULE_APP_DIR}/capsule_update_error.flag"
CAPSULE_GENERATION_IN_PROGRESS="${CAPSULE_APP_DIR}/.negative_capsule_generation_in_progress"
CAPSULE_LOW_MEMORY_WARNING="WARNING: Target system does not have sufficient memory to generate unauth.bin and tampered.bin on-device"
CAPSULE_OFFLINE_GUIDANCE="Generate unauth.bin and tampered.bin from the same signed_capsule.bin offline, then copy them into /mnt/acs_tests/app before running capsule update"
# Conservative engineering defaults allow roughly two capsule-sized in-memory
# objects plus Python, construct parsing, and process overhead. They are not
# derived from a platform-specific benchmark and should be tuned after platform
# validation through the service environment when necessary.
CAPSULE_MIN_MEMORY_KIB="${CAPSULE_MIN_MEMORY_KIB:-262144}"
CAPSULE_MEMORY_OVERHEAD_KIB="${CAPSULE_MEMORY_OVERHEAD_KIB:-196608}"
CAPSULE_GENERATION_LOG=""
CAPSULE_UNAUTH_TEMP=""
CAPSULE_TAMPERED_TEMP=""
CAPSULE_GENERATION_TRANSACTION_ACTIVE=0
CAPSULE_PUBLISH_STARTED=0

get_meminfo_kib() {
  awk -v key="$1" '$1 == key ":" { print $2; exit }' /proc/meminfo
}

append_capsule_test_result() {
  echo "$1" >> "$CAPSULE_TEST_RESULTS_LOG"
}

log_capsule_variant_status() {
  echo "$1"
  echo "$1" >> "$CAPSULE_GENERATION_LOG"
}

# Called indirectly by the EXIT trap.
# shellcheck disable=SC2317
cleanup_temporary_files() {
  [ -z "$CAPSULE_GENERATION_LOG" ] || rm -f "$CAPSULE_GENERATION_LOG"
  if [ -n "$CAPSULE_UNAUTH_TEMP" ]; then
    rm -f "$CAPSULE_UNAUTH_TEMP" "${CAPSULE_UNAUTH_TEMP}.tmp"
  fi
  if [ -n "$CAPSULE_TAMPERED_TEMP" ]; then
    rm -f "$CAPSULE_TAMPERED_TEMP" "${CAPSULE_TAMPERED_TEMP}.tmp"
  fi
}

clear_generation_marker_before_publish() {
  if [ "$CAPSULE_GENERATION_TRANSACTION_ACTIVE" -eq 1 ] &&
     [ "$CAPSULE_PUBLISH_STARTED" -eq 0 ]; then
    if rm -f "$CAPSULE_GENERATION_IN_PROGRESS"; then
      CAPSULE_GENERATION_TRANSACTION_ACTIVE=0
      log_capsule_variant_status "Cleared generation marker after controlled pre-publish failure"
      return 0
    else
      log_capsule_variant_status "Failed to clear generation marker after controlled pre-publish failure"
      return 1
    fi
  fi
  return 0
}

begin_capsule_test_result() {
  if [ -s "$CAPSULE_TEST_RESULTS_LOG" ]; then
    printf '\n' >> "$CAPSULE_TEST_RESULTS_LOG"
  fi
  append_capsule_test_result "Testing generation of negative capsules from signed_capsule.bin"
}

reset_attempt_state() {
  rm -f \
    "$CAPSULE_CHECK_FLAG" \
    "$CAPSULE_UNSUPPORTED_FLAG" \
    "$CAPSULE_ERROR_FLAG" \
    "$CAPSULE_ON_DISK_LOG"
}

generate_capsule_variants() {
  # Existing pre-generated variants take precedence over on-device generation.
  if [ ! -e "$CAPSULE_GENERATION_IN_PROGRESS" ] &&
     [ -s "$CAPSULE_UNAUTH" ] && [ -s "$CAPSULE_TAMPERED" ]; then
    log_capsule_variant_status "Using existing pre-generated negative capsule variants; skipping on-device generation"
    if [ ! -s "$CAPSULE_SIGNED" ] || [ ! -r "$CAPSULE_SIGNED" ]; then
      log_capsule_variant_status "signed_capsule.bin not present, empty, or unreadable; capsule update cannot proceed"
      return 2
    fi
    return 0
  fi
  if [ -e "$CAPSULE_GENERATION_IN_PROGRESS" ]; then
    log_capsule_variant_status "Previous on-device generation was interrupted; discarding untrusted variants"
    if ! rm -f "$CAPSULE_UNAUTH" "$CAPSULE_TAMPERED"; then
      log_capsule_variant_status "Failed to discard variants from interrupted generation"
      return 1
    fi
    CAPSULE_GENERATION_TRANSACTION_ACTIVE=1
  fi
  if [ ! -s "$CAPSULE_SIGNED" ] || [ ! -r "$CAPSULE_SIGNED" ]; then
    log_capsule_variant_status "signed_capsule.bin not present, empty, or unreadable; skipping on-device capsule variant generation"
    return 2
  fi
  if [ ! -r "$CAPSULE_TOOL" ]; then
    log_capsule_variant_status "capsule-tool.py not found or not readable at ${CAPSULE_TOOL}"
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    log_capsule_variant_status "python3 is not available"
    return 1
  fi
  case "$CAPSULE_MIN_MEMORY_KIB" in
    ''|*[!0-9]*)
      log_capsule_variant_status "Invalid capsule memory threshold configuration"
      return 1
      ;;
  esac
  case "$CAPSULE_MEMORY_OVERHEAD_KIB" in
    ''|*[!0-9]*)
      log_capsule_variant_status "Invalid capsule memory overhead configuration"
      return 1
      ;;
  esac

  capsule_size_bytes=$(stat -Lc %s "$CAPSULE_SIGNED" 2>/dev/null) ||
    capsule_size_bytes=$(wc -c < "$CAPSULE_SIGNED" 2>/dev/null)
  case "$capsule_size_bytes" in
    ''|*[!0-9]*)
      log_capsule_variant_status "Failed to determine signed_capsule.bin size"
      return 1
      ;;
  esac
  capsule_size_kib=$(((capsule_size_bytes + 1023) / 1024))
  required_kib=$((capsule_size_kib * 2 + CAPSULE_MEMORY_OVERHEAD_KIB))
  if [ "$required_kib" -lt "$CAPSULE_MIN_MEMORY_KIB" ]; then
    required_kib=$CAPSULE_MIN_MEMORY_KIB
  fi
  mem_available_kib=$(get_meminfo_kib MemAvailable)
  swap_free_kib=$(get_meminfo_kib SwapFree)
  case "$mem_available_kib" in
    ''|*[!0-9]*)
      log_capsule_variant_status "Failed to determine available memory"
      return 1
      ;;
  esac
  case "$swap_free_kib" in
    ''|*[!0-9]*) swap_free_kib=0 ;;
  esac
  total_available_kib=$((mem_available_kib + swap_free_kib))
  free_space_kib=$(df -Pk "$CAPSULE_APP_DIR" | awk 'NR == 2 { print $4 }')
  case "$free_space_kib" in
    ''|*[!0-9]*)
      log_capsule_variant_status "Failed to determine available storage"
      return 1
      ;;
  esac
  required_space_kib=$((capsule_size_kib * 2 + capsule_size_kib / 5))
  log_capsule_variant_status "signed_capsule.bin size: ${capsule_size_bytes} bytes"
  log_capsule_variant_status "MemAvailable: ${mem_available_kib} KiB, SwapFree: ${swap_free_kib} KiB"
  log_capsule_variant_status "Estimated memory required: ${required_kib} KiB"
  log_capsule_variant_status "Available storage: ${free_space_kib} KiB, required: ${required_space_kib} KiB"
  if [ "$total_available_kib" -lt "$required_kib" ]; then
    log_capsule_variant_status "$CAPSULE_LOW_MEMORY_WARNING"
    log_capsule_variant_status "$CAPSULE_OFFLINE_GUIDANCE"
    return 3
  fi
  if [ "$free_space_kib" -lt "$required_space_kib" ]; then
    log_capsule_variant_status "Insufficient storage to generate capsule variants"
    return 4
  fi

  # Create the transaction marker before either tool invocation. If power is
  # lost during generation, the next run will not trust an older output pair.
  if [ ! -e "$CAPSULE_GENERATION_IN_PROGRESS" ]; then
    if ! touch "$CAPSULE_GENERATION_IN_PROGRESS"; then
      log_capsule_variant_status "Failed to create capsule generation transaction marker"
      return 1
    fi
    CAPSULE_GENERATION_TRANSACTION_ACTIVE=1

    # Make the transaction marker durable before generation starts. This
    # ensures an unexpected reset cannot leave generated outputs without a
    # persistent indication of an incomplete transaction.
    if ! sync; then
      log_capsule_variant_status "Failed to synchronize capsule generation transaction marker"
      return 1
    fi
  fi
  CAPSULE_UNAUTH_TEMP=$(mktemp "${CAPSULE_APP_DIR}/.unauth.bin.XXXXXX") || {
    log_capsule_variant_status "Failed to create temporary file for unauth.bin"
    return 1
  }
  CAPSULE_TAMPERED_TEMP=$(mktemp "${CAPSULE_APP_DIR}/.tampered.bin.XXXXXX") || {
    log_capsule_variant_status "Failed to create temporary file for tampered.bin"
    return 1
  }
  log_capsule_variant_status "Generating unauth.bin from signed_capsule.bin"
  if ! python3 "$CAPSULE_TOOL" \
       --de-authenticate \
       --output "$CAPSULE_UNAUTH_TEMP" \
       "$CAPSULE_SIGNED" \
       >> "$CAPSULE_GENERATION_LOG" 2>&1 ||
     [ ! -s "$CAPSULE_UNAUTH_TEMP" ]; then
    log_capsule_variant_status "Failed to generate valid unauth.bin"
    return 1
  fi
  log_capsule_variant_status "Generating tampered.bin from signed_capsule.bin"
  if ! python3 "$CAPSULE_TOOL" \
       --tamper \
       --output "$CAPSULE_TAMPERED_TEMP" \
       "$CAPSULE_SIGNED" \
       >> "$CAPSULE_GENERATION_LOG" 2>&1 ||
     [ ! -s "$CAPSULE_TAMPERED_TEMP" ]; then
    log_capsule_variant_status "Failed to generate valid tampered.bin"
    return 1
  fi

  if ! mv -f "$CAPSULE_UNAUTH_TEMP" "$CAPSULE_UNAUTH"; then
    log_capsule_variant_status "Failed to publish generated unauth.bin"
    return 1
  fi
  CAPSULE_UNAUTH_TEMP=""
  CAPSULE_PUBLISH_STARTED=1
  if ! mv -f "$CAPSULE_TAMPERED_TEMP" "$CAPSULE_TAMPERED"; then
    log_capsule_variant_status "Failed to publish generated tampered.bin"
    return 1
  fi
  CAPSULE_TAMPERED_TEMP=""

  # Make both published variants durable before removing the transaction
  # marker. An unexpected reset before this completes must leave the marker
  # behind so the next run discards the potentially incomplete output pair.
  if ! sync; then
    log_capsule_variant_status "Failed to synchronize generated capsule variants"
    return 1
  fi

  if ! rm -f "$CAPSULE_GENERATION_IN_PROGRESS"; then
    log_capsule_variant_status "Failed to complete capsule generation transaction"
    return 1
  fi

  # Persist transaction completion before reboot.
  sync

  CAPSULE_GENERATION_TRANSACTION_ACTIVE=0
  CAPSULE_PUBLISH_STARTED=0
  log_capsule_variant_status "Successfully generated unauth.bin and tampered.bin on-device"
  return 0
}
if ! mkdir -p "$CAPSULE_RESULTS_DIR"; then
  echo "Failed to create capsule result directory" >&2
  exit 1
fi
if ! : >> "$CAPSULE_TEST_RESULTS_LOG"; then
  echo "Failed to initialize capsule test results log" >&2
  exit 1
fi
CAPSULE_GENERATION_LOG=$(mktemp) || {
  {
    echo "Testing generation of negative capsules from signed_capsule.bin"
    echo "Test_Info"
    echo "Failed to create temporary capsule generation log"
  } > "$CAPSULE_ON_DISK_LOG"
  begin_capsule_test_result
  append_capsule_test_result "Test_Info"
  append_capsule_test_result "Failed to create temporary capsule generation log"
  rm -f "$CAPSULE_CHECK_FLAG" "$CAPSULE_UNSUPPORTED_FLAG"
  if ! touch "$CAPSULE_ERROR_FLAG"; then
    append_capsule_test_result "Failed to create capsule_update_error.flag"
  fi
  exit 1
}
trap cleanup_temporary_files EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if reset_attempt_state; then
  generate_capsule_variants
  capsule_variant_status=$?
  if [ "$capsule_variant_status" -ne 0 ]; then
    if ! clear_generation_marker_before_publish; then
      capsule_variant_status=1
    fi
  fi
else
  log_capsule_variant_status "Failed to clear state from the previous capsule generation attempt"
  capsule_variant_status=1
fi
check_flag_failed=0

if [ "$capsule_variant_status" -eq 0 ]; then
  if rm -f "$CAPSULE_UNSUPPORTED_FLAG" "$CAPSULE_ERROR_FLAG" &&
     touch "$CAPSULE_CHECK_FLAG"; then
    begin_capsule_test_result
    cat "$CAPSULE_GENERATION_LOG" >> "$CAPSULE_TEST_RESULTS_LOG"
    echo "Successfully created capsule update check flag"
    exit 0
  fi

  echo "Failed to create capsule update check flag, skipping capsule update."
  capsule_variant_status=1
  check_flag_failed=1
fi

if [ "$capsule_variant_status" -ne 0 ]; then
  {
    echo "Testing generation of negative capsules from signed_capsule.bin"
    echo "Test_Info"
  } > "$CAPSULE_ON_DISK_LOG"
  begin_capsule_test_result
  append_capsule_test_result "Test_Info"
  cat "$CAPSULE_GENERATION_LOG" >> "$CAPSULE_TEST_RESULTS_LOG"
  if [ "$check_flag_failed" -eq 1 ]; then
    append_capsule_test_result "Failed to create capsule update check flag, skipping capsule update."
  fi
fi

if [ "$capsule_variant_status" -eq 1 ] && [ "$check_flag_failed" -eq 0 ]; then
  append_capsule_test_result "Capsule variant generation or setup failed on-device"
elif [ "$capsule_variant_status" -eq 2 ]; then
  echo "signed_capsule.bin not present" >> "$CAPSULE_ON_DISK_LOG"
  append_capsule_test_result "signed_capsule.bin not present; Copy the partner-provided capsule into /mnt/acs_tests/app"
elif [ "$capsule_variant_status" -eq 3 ]; then
  append_capsule_test_result "Insufficient memory for on-device capsule variant generation"
  append_capsule_test_result "$CAPSULE_OFFLINE_GUIDANCE"
elif [ "$capsule_variant_status" -eq 4 ]; then
  append_capsule_test_result "Insufficient storage for on-device capsule variant generation"
  append_capsule_test_result "$CAPSULE_OFFLINE_GUIDANCE"
fi

rm -f "$CAPSULE_CHECK_FLAG"
if [ "$capsule_variant_status" -eq 3 ] || [ "$capsule_variant_status" -eq 4 ]; then
  failure_flag=$CAPSULE_UNSUPPORTED_FLAG
  stale_failure_flag=$CAPSULE_ERROR_FLAG
else
  failure_flag=$CAPSULE_ERROR_FLAG
  stale_failure_flag=$CAPSULE_UNSUPPORTED_FLAG
fi
rm -f "$stale_failure_flag"
if ! touch "$failure_flag"; then
  append_capsule_test_result "Failed to persist capsule generation failure state"
  exit 1
fi
exit "$capsule_variant_status"
