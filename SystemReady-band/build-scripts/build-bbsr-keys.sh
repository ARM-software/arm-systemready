#!/bin/sh

# @file
# Copyright (c) 2021-2024, Arm Limited or its affiliates. All rights reserved.
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
KEYS_DIR=$TOP_DIR/bbsr-keys

# set the path to pick up the local efitools
export PATH="$TOP_DIR/efitools:$PATH"

do_build()
{
    echo "do_build: bbsr-keys"
    mkdir -p $KEYS_DIR
    pushd $KEYS_DIR

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

