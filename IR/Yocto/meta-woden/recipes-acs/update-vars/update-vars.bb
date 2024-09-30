LICENSE = "CLOSED"
inherit deploy autotools
S = "${WORKDIR}"

SRC_URI = " git://git.code.sf.net/p/gnu-efi/code;destsuffix=gnu-efi;protocol=https;branch=master;name=gnu-efi  \
            git://git.kernel.org/pub/scm/linux/kernel/git/jejb/efitools.git;destsuffix=efitools;branch=master;protocol=https;name=efitools  \
            file://0001-UpdateVar-updates-for-SecureBoot-automatic-provision.patch;patch=1;patchdir=efitools  "

SRCREV_FORMAT = "gnu-efi efitools "

SRCREV_gnu-efi = "183ec634eec7aee214e4e2baa728bc9c68c492f0"
SRCREV_efitools = "392836a46ce3c92b55dc88a1aebbcfdfc5dcddce"


COMPATIBLE_MACHINE:genericarm64 = "genericarm64"

do_configure() {
    echo "Building gnu-efi..."
    export prefix=""
    export CROSS_COMPILE="${TARGET_PREFIX}"
    export CPPFLAGS="-I${STAGING_DIR_TARGET}/usr/include"
    cd ${S}/gnu-efi
    echo "make clean"
    make clean
    echo "make"
    make
    export STAGING_DIR_TARGET=${STAGING_DIR_TARGET}

    echo "Building efitools..."
    cd ../efitools
    echo "target at efitool ${TARGET_PREFIX}"
    echo "CPPFLAGS=${CFLAGS}"
    export STAGING_INCDIR=${STAGING_INCDIR}/../..
    export TARGET_PREFIX=${TARGET_PREFIX}
    echo "efitools make clean"
    make clean
    echo "efitools make"
    make

}
do_compile[noexec] = "1"
do_install[noexec] = "1"

do_deploy() {
    echo "S = ${S} DEPLOYDIR = ${DEPLOYDIR}"
    install -d ${DEPLOYDIR}
    cp ${S}/efitools/UpdateVars.efi ${DEPLOYDIR}
    echo "Deploy done..."
}

addtask deploy after do_install