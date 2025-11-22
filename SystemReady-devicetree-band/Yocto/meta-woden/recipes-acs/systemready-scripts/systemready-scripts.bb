LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://systemready-scripts/LICENSE;md5=85b7d439a311c22626c2e3f05daf628e"
S = "${WORKDIR}"

SRC_URI = "git://git.gitlab.arm.com/systemready/systemready-scripts.git;destsuffix=systemready-scripts;protocol=https;branch=master;name=systemready-scripts \
"
SRCREV_systemready-scripts = "${AUTOREV}"
SYSTEMREADY_COMMIT_LOG ?= "${TOPDIR}/../recipes-acs/bootfs-files/files/systemready-commit.log"

RDEPENDS:${PN} += "bash python3-requests python3-construct tar findutils python3-pyyaml"

do_install(){
    install -d ${D}${bindir}
    mkdir -p ${D}/${bindir}/systemready-scripts
    cp -r ${S}/systemready-scripts/* ${D}/${bindir}/systemready-scripts/

    echo "systemready-scripts" >> "${SYSTEMREADY_COMMIT_LOG}"

    if [ -d "${S}/systemready-scripts/.git" ]; then
        echo "    URL(systemready-scripts) = $(git -C "${S}/systemready-scripts" remote get-url origin)" >> "${SYSTEMREADY_COMMIT_LOG}"
        echo "    commit(systemready-scripts) = $(git -C "${S}/systemready-scripts" rev-parse HEAD)" >> "${SYSTEMREADY_COMMIT_LOG}"
    fi
    echo "" >> "${SYSTEMREADY_COMMIT_LOG}"
}
FILES:${PN} += "${bindir}/systemready-scripts/*"
