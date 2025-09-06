LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://systemready-scripts/LICENSE;md5=85b7d439a311c22626c2e3f05daf628e"
S = "${WORKDIR}"

SRC_URI = "git://git.gitlab.arm.com/systemready/systemready-scripts.git;destsuffix=systemready-scripts;protocol=https;branch=3.0.1;name=systemready-scripts \
"
SRCREV_systemready-scripts = "${AUTOREV}"

RDEPENDS:${PN} += "bash python3-requests python3-construct tar findutils python3-pyyaml"

do_install(){
    install -d ${D}${bindir}
    mkdir -p ${D}/${bindir}/systemready-scripts
    cp -r ${S}/systemready-scripts/* ${D}/${bindir}/systemready-scripts/

}
FILES:${PN} += "${bindir}/systemready-scripts/*"
