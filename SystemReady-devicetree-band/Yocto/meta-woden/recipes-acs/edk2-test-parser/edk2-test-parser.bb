LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://edk2-test-parser/LICENSE;md5=c0550be4b3b9c0223efd0eaa70dc9085"
S = "${WORKDIR}"

SRC_URI = "git://git.gitlab.arm.com/systemready/edk2-test-parser.git;destsuffix=edk2-test-parser;protocol=https;branch=main;name=edk2-test-parser \
"

SRCREV_edk2-test-parser = "${AUTOREV}"
SYSTEMREADY_COMMIT_LOG ?= "${TOPDIR}/../recipes-acs/bootfs-files/files/systemready-commit.log"

RDEPENDS:${PN} += "bash python3-pyyaml python3-junit-xml python3-packaging"

do_install(){
    install -d ${D}${bindir}
    mkdir -p ${D}/${bindir}/edk2-test-parser
    cp -r ${S}/edk2-test-parser/* ${D}/${bindir}/edk2-test-parser/

    echo "edk2-test-parser" >> "${SYSTEMREADY_COMMIT_LOG}"

    if [ -d "${S}/edk2-test-parser/.git" ]; then
        echo "    URL(edk2-test-parser) = $(git -C "${S}/edk2-test-parser" remote get-url origin)" >> "${SYSTEMREADY_COMMIT_LOG}"
        echo "    commit(edk2-test-parser) = $(git -C "${S}/edk2-test-parser" rev-parse HEAD)" >> "${SYSTEMREADY_COMMIT_LOG}"
    fi
    echo "" >> "${SYSTEMREADY_COMMIT_LOG}"
}
FILES:${PN} += "${bindir}/edk2-test-parser/*"
