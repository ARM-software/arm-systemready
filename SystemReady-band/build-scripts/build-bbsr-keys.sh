#!/bin/sh

# @file
# Copyright (c) 2021-2026, Arm Limited or its affiliates. All rights reserved.
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

#
# This script uses the following environment variables
#
# TOP_DIR - workspace root directory
# KEYS_DIR - directory where secure boot keys are generated

TOP_DIR=`pwd`
DEFAULT_KEYS_DIR=$TOP_DIR/bbsr-keys

# Source the configuration file to get KEYS_DIR from systemready-band-source.cfg
CFG_FILE="$TOP_DIR/../common/config/systemready-band-source.cfg"
if [ -f "$CFG_FILE" ]; then
    . "$CFG_FILE"
    if [ -n "$KEYS_DIR" ]; then
        echo "INFO: Sourced KEYS_DIR from config: KEYS_DIR=$KEYS_DIR"
    fi
fi

# The user can point to an external KEYS_DIR to provide partner-provided keys.
# KEYS_DIR can be set in systemready-band-source.cfg or overridden via environment variable.
# If KEYS_DIR points to an existing external location, use those keys.
# Otherwise, generate keys in the workdir.
GEN_DIR="$DEFAULT_KEYS_DIR"
ENFORCE_EXTERNAL_KEYS=0

# Use the default directory if KEYS_DIR is unset.
if [ -z "$KEYS_DIR" ]; then
    KEYS_DIR="$DEFAULT_KEYS_DIR"
fi

# Remove trailing slash if present
KEYS_DIR="${KEYS_DIR%/}"

# KEYS_DIR must be an absolute path for external partner-provided keys.
if [ -n "$KEYS_DIR" ] && [ "${KEYS_DIR#/}" = "$KEYS_DIR" ]; then
    echo "WARNING: KEYS_DIR=$KEYS_DIR is not an absolute path; using default test key directory $DEFAULT_KEYS_DIR"
    KEYS_DIR="$DEFAULT_KEYS_DIR"
fi

# Check if external KEYS_DIR exists and is a valid directory
if [ -n "$KEYS_DIR" ] && [ "$KEYS_DIR" != "$DEFAULT_KEYS_DIR" ]; then
    if [ ! -d "$KEYS_DIR" ]; then
        echo "WARNING: KEYS_DIR=$KEYS_DIR does not exist, using default test key directory $DEFAULT_KEYS_DIR"
        KEYS_DIR="$DEFAULT_KEYS_DIR"
    else
        echo "INFO: Found KEYS_DIR at $KEYS_DIR, checking for required key files"
        ENFORCE_EXTERNAL_KEYS=1
    fi
fi

# Check if all required key files exist in KEYS_DIR
REQUIRED_FILES="NullPK.auth TestDB1.auth TestDB1.crt TestDB1.der TestDB1.key TestDBX1.auth TestDBX1.crt TestDBX1.der TestDBX1.key TestKEK1.auth TestKEK1.crt TestKEK1.der TestKEK1.key TestPK1.auth TestPK1.crt TestPK1.der TestPK1.key"
ALL_FILES_PRESENT=1
MISSING=""

if [ $ENFORCE_EXTERNAL_KEYS -eq 1 ]; then
    for file in $REQUIRED_FILES; do
        if [ ! -f "$KEYS_DIR/$file" ]; then
            ALL_FILES_PRESENT=0
            MISSING="$MISSING $file"
            echo "WARNING: missing key file: $KEYS_DIR/$file"
        fi
    done
fi

# set the path to pick up the local efitools
export PATH="$TOP_DIR/efitools:$PATH"

do_build()
{
    # Handle case where KEYS_DIR was overwritten by framework.sh sourcing config again
    if [ ! -d "$KEYS_DIR" ] && [ "$KEYS_DIR" != "$DEFAULT_KEYS_DIR" ]; then
        echo "WARNING: KEYS_DIR=$KEYS_DIR does not exist, using default test key directory $DEFAULT_KEYS_DIR"
        KEYS_DIR="$DEFAULT_KEYS_DIR"
        ENFORCE_EXTERNAL_KEYS=0
    fi

    if [ $ALL_FILES_PRESENT -eq 1 ] && [ $ENFORCE_EXTERNAL_KEYS -eq 1 ]; then
        echo "do_build: bbsr-keys: keys already present in KEYS_DIR=$KEYS_DIR"
        # if external directory differs, copy contents into workdir
        if [ "$KEYS_DIR" != "$DEFAULT_KEYS_DIR" ]; then
            echo "copying existing keys into build directory"
            mkdir -p "$DEFAULT_KEYS_DIR"
            cp -r "$KEYS_DIR"/* "$DEFAULT_KEYS_DIR/"
        fi
        echo "skipping key generation"
        return 0
    fi

    # If external keys were enforced but incomplete, fail the build
    if [ $ENFORCE_EXTERNAL_KEYS -eq 1 ] && [ $ALL_FILES_PRESENT -eq 0 ]; then
        echo "KEYS_DIR not provided or incomplete, please generate required keys"
        echo "ERROR: missing keys in $KEYS_DIR:$MISSING; please provide all required keys or unset KEYS_DIR"
        exit 1
    fi

    echo "do_build: bbsr-keys"
    mkdir -p "$KEYS_DIR"
    pushd "$KEYS_DIR"

    # generate TestPK1: DER and signed siglist
    NAME=TestPK1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_PK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c $NAME.crt -k $NAME.key PK $NAME.esl $NAME.auth

    # generate NULLPK.auth to facilitate deletion of PK during development
    NAME=NullPK
    FUTURE_DATE=`date --rfc-3339=date -d "+5 year"`
    cat /dev/null > $NAME.esl
    sign-efi-sig-list -t $FUTURE_DATE -c TestPK1.crt -k TestPK1.key PK $NAME.esl $NAME.auth

    # generate TestKEK1: DER and signed siglist
    NAME=TestKEK1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_KEK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestPK1.crt -k TestPK1.key KEK $NAME.esl $NAME.auth

    # generate TestDB1: DER and signed siglist
    NAME=TestDB1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_DB/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestKEK1.crt -k TestKEK1.key db $NAME.esl $NAME.auth

    # generate TestDBX1: DER and signed siglist
    NAME=TestDBX1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_PK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestKEK1.crt -k TestKEK1.key dbx $NAME.esl $NAME.auth

    popd
}

do_clean()
{
    echo "do_clean: bbsr-keys"
    rm -rf $KEYS_DIR
}

do_package()
{
    echo "do_package: bbsr-keys: nothing to do"
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/framework.sh $@
