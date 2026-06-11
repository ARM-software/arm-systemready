#!/bin/sh
set -eu

cat > edk2-test-parser.log <<EOF
| name | set guid | guid | result | updated by |
|------|----------|------|--------|------------|
| TestA | AAAA-BBBB | 1111-2222 | PASS | parser |
EOF

python3 "$1" "$PWD/edk2-test-parser.log" "$PWD/out.json"
