LICENSE = "CLOSED"
PACKAGE_ARCH = "${MACHINE_ARCH}"
inherit deploy
S = "${WORKDIR}"

SRC_URI = "git://git.kernel.org/pub/scm/linux/kernel/git/jejb/efitools.git;destsuffix=efitools;protocol=https;nobranch=1;name=efitools"

DEPENDS += "help2man-native libfile-slurp-perl-native"

inherit perlnative

SRCREV_efitools = "392836a46ce3c92b55dc88a1aebbcfdfc5dcddce"

# no configure step
#do_configure[noexec] = "1"
do_configure() {
    echo "Building efitools..."
    export PATH="${PATH}:/usr/bin"
    echo "TARGET_PREFIX = ${TARGET_PREFIX} , OLD_TARGET_PREFIX=${OLD_TARGET_PREFIX}, CROSS_COMPILE = ${CROSS_COMPILE} BUILD_CC=${BUILD_CC} $BUILD_LD"
    cd ${S}/efitools
    sed -i -e "1s:#!.*:#!/usr/bin/env nativeperl:" xxdi.pl
    sed -i  '1 i\CC = ${BUILD_CC}' ${S}/efitools/Make.rules
    sed -i  '1 i\LD = ${BUILD_LD}' ${S}/efitools/Make.rules

    make clean
    echo " =================Clean done===================="
    make
    echo "efitools is built successfully"
}

do_compile() {

    KEYS_DIR="${S}/security-interface-extension-keys"
    echo "do_compile: security-interface-extension-keys"
    mkdir -p $KEYS_DIR
    cd $KEYS_DIR

    #For openssl
    echo "S is ${S}"
    export PATH="${S}/efitools:/usr/bin:${PATH}"
    echo "New Path: $PATH";

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

    # Convert TestDB1 to gpg form and import to gpg toolchain for use in signing grub
    #cat TestDB1.key | PEM2OPENPGP_USAGE_FLAGS=certify,sign pem2openpgp "TestDB1"  > TestDB1.gpgkey
    #gpg --import --allow-secret-key-import TestDB1.gpgkey
    #gpg --export > TestDB1.pubgpg

    # generate TestDBX1: DER and signed siglist
    NAME=TestDBX1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_PK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestKEK1.crt -k TestKEK1.key dbx $NAME.esl $NAME.auth


}

# no install
do_install[noexec] = "1"

do_deploy() {
   # Copy the files to deploy directory
   KEYS_DIR="${S}/security-interface-extension-keys"
   cp -r $KEYS_DIR ${DEPLOYDIR}/
   echo "Keys deployed ..."
}

addtask deploy after do_install
