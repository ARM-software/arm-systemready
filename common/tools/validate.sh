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

SCHEMA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="$SCHEMA_DIR/acs-merged-schema.json"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage:"
    echo "  $0 <merged_results.json> [schema.json]"
    echo ""
    echo "Arguments:"
    echo "  <merged_results.json>   Path to merged results JSON (required)"
    echo "  [schema.json]           Path to JSON schema (optional)"
    echo ""
    echo "Notes:"
    echo "  If schema.json is omitted, defaults to:"
    echo "    $SCHEMA_FILE"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/merged_results.json"
    echo "  $0 /path/to/merged_results.json /path/to/acs-merged-schema-doc.json"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help"
}

if [ $# -eq 0 ]; then
    echo -e "${RED}Error: Missing JSON file argument${NC}"
    usage
    exit 1
fi

case "$1" in
    -h|--help)
        usage
        exit 0
        ;;
esac

JSON_FILE="$1"
if [ $# -ge 2 ]; then
    SCHEMA_FILE="$2"
fi

if [ ! -f "$JSON_FILE" ]; then
    echo -e "${RED}Error: File not found: $JSON_FILE${NC}"
    exit 1
fi

if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}Error: Schema file not found: $SCHEMA_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}JSON Schema Validation${NC}"
echo -e "${BLUE}=====================================${NC}\n"

# Run validation with concise, readable errors (path + message)
output=$(python3 - "$JSON_FILE" "$SCHEMA_FILE" <<'PY'
import json
import sys
from jsonschema import Draft7Validator

# ANSI colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

def fmt_path(path):
    parts = []
    for p in path:
        if isinstance(p, int):
            parts.append(f"[{p}]")
        else:
            if parts:
                parts.append("." + str(p))
            else:
                parts.append(str(p))
    return "".join(parts) if parts else "<root>"

def suite_from_path(path):
    if not path:
        return "<root>"
    first = path[0]
    if isinstance(first, str) and first.startswith("Suite_Name:"):
        return first
    return "<root>"

json_file = sys.argv[1]
schema_file = sys.argv[2]

with open(schema_file, "r", encoding="utf-8") as sf:
    schema = json.load(sf)
with open(json_file, "r", encoding="utf-8") as jf:
    instance = json.load(jf)

v = Draft7Validator(schema)
errors = sorted(v.iter_errors(instance), key=lambda e: list(e.path))
if not errors:
    sys.exit(0)

suite_errors = {}
for err in errors:
    suite = suite_from_path(list(err.path))
    key = (suite, err.message)
    suite_errors.setdefault(key, []).append(err)

suites = [k for k in instance.keys() if isinstance(k, str) and k.startswith("Suite_Name:")]
suites = sorted(suites)
suite_counts = {s: 0 for s in suites}

reported = set()
for suite in suites:
    any_err = False
    for (s, message), errs in suite_errors.items():
        if s != suite:
            continue
        any_err = True
        suite_counts[suite] += len(errs)
        reported.add((s, message))
        paths = [fmt_path(e.path) for e in errs]
        print(f"{RED}*suite={suite} issue={message} count={len(paths)}{NC}")
        for p in paths[:5]:
            print(f"{YELLOW}  *at={p}{NC}")
        if len(paths) > 5:
            print(f"{YELLOW}  *... and {len(paths) - 5} more{NC}")
    if not any_err:
        print(f"{GREEN}*suite={suite} no errors{NC}")

# Root-level errors (not tied to a suite)
for (s, message), errs in suite_errors.items():
    if s != "<root>":
        continue
    if (s, message) in reported:
        continue
    paths = [fmt_path(e.path) for e in errs]
    print(f"{RED}*suite=<root> issue={message} count={len(paths)}{NC}")
    for p in paths[:5]:
        print(f"{YELLOW}  *at={p}{NC}")
    if len(paths) > 5:
        print(f"{YELLOW}  *... and {len(paths) - 5} more{NC}")

print()
print(f"{BLUE}--- Error Counts by Suite ---{NC}")
for s in suites:
    count = suite_counts.get(s, 0)
    color = GREEN if count == 0 else RED
    print(f"{color}{s}: {count}{NC}")

if any(k[0] == "<root>" for k in suite_errors):
    root_count = sum(len(errs) for (s, _), errs in suite_errors.items() if s == "<root>")
    color = GREEN if root_count == 0 else RED
    print(f"{color}<root>: {root_count}{NC}")

sys.exit(1)
PY
)
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ Schema validation PASSED${NC}\n"
else
    echo -e "${RED}✗ Schema validation FAILED${NC}\n"
    if [ -n "$output" ]; then
        echo -e "${RED}Errors:${NC}"
        echo "$output" | while read line; do
            echo "$line"
        done
        echo
    fi
fi

echo -e "${BLUE}File: $JSON_FILE${NC}"
echo -e "${BLUE}Schema: $SCHEMA_FILE${NC}\n"

exit $exit_code
