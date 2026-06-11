#!/bin/sh
set -eu
mkdir -p oslogs/rhel

cat > oslogs/rhel/cat-etc-os-release.txt <<EOF
NAME="Red Hat Enterprise Linux"
VERSION_ID="9.2"
EOF

python3 "$1" "$PWD/oslogs" "$PWD/missing-post-script.log" "$PWD/out.json"
