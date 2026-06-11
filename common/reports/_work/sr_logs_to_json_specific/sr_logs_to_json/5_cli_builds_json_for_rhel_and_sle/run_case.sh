#!/bin/sh
set -eu

mkdir -p oslogs/rhel oslogs/sle

cat > oslogs/rhel/cat-etc-os-release.txt <<EOF
NAME="Red Hat Enterprise Linux"
VERSION_ID="9.3"
EOF

cat > oslogs/sle/cat-etc-os-release.txt <<EOF
NAME="SLES"
VERSION_ID="15"
EOF

cat > post-script.log <<EOF
INFO ok
EOF

python3 "$1" "$PWD/oslogs" "$PWD/post-script.log" "$PWD/out.json"
