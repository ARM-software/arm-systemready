#!/bin/bash
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

set -euo pipefail

SCRIPT_DIR=$(dirname "$(realpath "$0")")
REPO_ROOT=$(realpath "$SCRIPT_DIR/../..")
OUTPUT_PATH=${1:-"$PWD/systemready-log-parser-standalone.tar.gz"}

# Package the complete parser directory so every suite parser and support file
# is included automatically. The remaining paths are partner documentation.
package_paths=(
    "common/log_parser"
    "docs/acs_schema_guide.md"
    "docs/log_parser_guide.md"
    "LICENSE.md"
)

for relative_path in "${package_paths[@]}"; do
    if [ ! -e "$REPO_ROOT/$relative_path" ]; then
        echo "ERROR: Required package path is missing: $REPO_ROOT/$relative_path" >&2
        exit 1
    fi
done

mkdir -p "$(dirname "$OUTPUT_PATH")"
OUTPUT_PATH=$(realpath -m "$OUTPUT_PATH")
TEMP_DIR=$(mktemp -d)
TEMP_ARCHIVE="$TEMP_DIR/systemready-log-parser-standalone.tar.gz"
trap 'rm -rf "$TEMP_DIR"' EXIT

exclude_args=(
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=common/log_parser/tests"
)
output_relative=$(realpath --relative-to="$REPO_ROOT" "$OUTPUT_PATH")
if [[ "$output_relative" != ../* ]]; then
    exclude_args+=("--exclude=$output_relative" "--exclude=$output_relative.sha256")
fi

tar \
    "${exclude_args[@]}" \
    --transform='s,^,systemready-log-parser/,' \
    -czf "$TEMP_ARCHIVE" \
    -C "$REPO_ROOT" \
    "${package_paths[@]}"

mv "$TEMP_ARCHIVE" "$OUTPUT_PATH"
output_dir=$(dirname "$OUTPUT_PATH")
output_name=$(basename "$OUTPUT_PATH")
(
    cd "$output_dir"
    sha256sum "$output_name" > "$output_name.sha256"
)

echo "Standalone package: $(realpath "$OUTPUT_PATH")"
echo "SHA-256 checksum : $(realpath "$OUTPUT_PATH.sha256")"
