SUMMARY = "UEFI Self Certification Tests (SCT) for IR systems"
DESCRIPTION = "UEFI SCT tests to check for compliance against the EBBR recipe"
HOMEPAGE = "https://github.com/ARM-software/bbr-acs"

inherit deploy

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://bbr-acs/LICENSE.md;md5=2a944942e1496af1886903d274dedb13"

SRC_URI += "git://github.com/ARM-software/bbr-acs;destsuffix=bbr-acs;protocol=https;branch=main;name=bbr-acs \
            git://github.com/tianocore/edk2-test;;destsuffix=edk2-test;protocol=https;nobranch=1;name=edk2-test \
            gitsm://github.com/tianocore/edk2.git;destsuffix=edk2-test/edk2;protocol=https;nobranch=1;name=edk2 \
            file://sctversion.patch;patch=1;patchdir=edk2-test \
"

S = "${WORKDIR}"

SRCREV_FORMAT    = "edk2-test_edk2_bbr-acs"
SRCREV_edk2 = "${AUTOREV}"
SRCREV_edk2-test = "${AUTOREV}"
SRCREV_bbr-acs   = "${AUTOREV}"

# set variables as required by edk2 based build
SBBR_TEST_DIR         = "${S}/bbr-acs/common/sct-tests/sbbr-tests"
UEFI_BUILD_MODE       = "DEBUG"
EDK2_ARCH             = "AARCH64"
UEFI_TOOLCHAIN        = "GCC5"
export PYTHON_COMMAND = "python3"


do_configure() {
    cd ${S}/edk2-test
    # patch edk2-test
    echo "Applying SCT patch ..."
    patch  -p1  < ${S}/bbr-acs/common/patches/edk2-test-bbr.patch

    # Copy sbbr-test cases from bbr-acs to uefi-sct
    cp -r ${SBBR_TEST_DIR}/SbbrBootServices uefi-sct/SctPkg/TestCase/UEFI/EFI/BootServices/
    cp -r ${SBBR_TEST_DIR}/SbbrEfiSpecVerLvl ${SBBR_TEST_DIR}/SbbrRequiredUefiProtocols ${SBBR_TEST_DIR}/SbbrSmbios ${SBBR_TEST_DIR}/SbbrSysEnvConfig uefi-sct/SctPkg/TestCase/UEFI/EFI/Generic/
    cp -r ${SBBR_TEST_DIR}/SBBRRuntimeServices uefi-sct/SctPkg/TestCase/UEFI/EFI/RuntimeServices/
    cp ${SBBR_TEST_DIR}/BBR_SCT.dsc uefi-sct/SctPkg/UEFI/
    cp ${SBBR_TEST_DIR}/build_bbr.sh uefi-sct/SctPkg/
    cp ${S}/bbr-acs/ebbr/config/EfiCompliant_EBBR.ini uefi-sct/SctPkg/UEFI/
}

do_compile() {
    cd ${S}/edk2-test
    # create softlink to SctPkg
    ln -sf ${S}/edk2-test/uefi-sct/SctPkg SctPkg
    chmod +x SctPkg/build_bbr.sh
    # modify build_bbr.sh script to set CROSS_COMPILE to desired TARGET_PREFIX
    sed -i 's/TEMP_CROSS_COMPILE=aarch64-linux-gnu-/TEMP_CROSS_COMPILE='${TARGET_PREFIX}'/g' SctPkg/build_bbr.sh
    # build ebbr
    ./SctPkg/build_bbr.sh ${EDK2_ARCH} GCC
}

do_install() {
    install -d ${D}/bbr/SCT
    cd ${S}/edk2-test
    cp -r Build/bbrSct/${UEFI_BUILD_MODE}_${UEFI_TOOLCHAIN}/SctPackage${EDK2_ARCH}/${EDK2_ARCH}/* ${D}/bbr/SCT/
    cp ${S}/bbr-acs/ebbr/config/EBBRStartup.nsh ${D}/bbr/SctStartup.nsh
    cp ${S}/bbr-acs/ebbr/config/EBBR_manual.seq ${D}/bbr/SCT/Sequence/EBBR_manual.seq
    cp ${S}/bbr-acs/ebbr/config/EBBR.seq ${D}/bbr/SCT/Sequence/EBBR.seq
    cp SctPkg/UEFI/EfiCompliant_EBBR.ini ${D}/bbr/SCT/Dependency/EfiCompliantBBTest/EfiCompliant.ini
}

# include files to be packaged.
FILES:${PN} += "/bbr"

do_deploy() {
    # copy SCT output files to deploy directory
    install -d ${DEPLOYDIR}
    cp -r ${D}/bbr ${DEPLOYDIR}/bbr
}

addtask deploy after do_install
