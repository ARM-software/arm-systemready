#!/bin/sh
set -eu

mkdir -p oslogs/rhel oslogs/sle oslogs/ubuntu

cat > oslogs/rhel/cat-etc-os-release.txt <<EOF
NAME="Red Hat Enterprise Linux"
VERSION_ID="9.1"
EOF

cat > oslogs/sle/cat-etc-os-release.txt <<EOF
NAME="SUSE Linux Enterprise Server"
VERSION_ID="15"
EOF

cat > oslogs/ubuntu/cat-etc-os-release.txt <<EOF
NAME="Ubuntu"
VERSION_ID="22.04"
EOF

cat > post-script.log <<EOF
ERROR os-logs rhel: failure on required OS: fatal issue
ERROR os-logs ubuntu: issue on extra OS: non-fatal issue
EOF

python3 "$1" "$PWD/oslogs" "$PWD/post-script.log" "$PWD/out.json"
