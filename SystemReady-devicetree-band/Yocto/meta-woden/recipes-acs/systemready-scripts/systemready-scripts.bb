LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://systemready-scripts/LICENSE;md5=85b7d439a311c22626c2e3f05daf628e"
S = "${WORKDIR}"

SRC_URI = "git://git.gitlab.arm.com/systemready/systemready-scripts.git;destsuffix=systemready-scripts;protocol=https;branch=master;name=systemready-scripts \
"
SRC_URI[systemready-scripts.sha256sum] = "80b79a5e2e79ed997772b93593d573f6192757254599a20f15812595d3d7ae7a"

SRCREV_systemready-scripts = "${AUTOREV}"

RDEPENDS:${PN} += "bash "

do_install(){
    install -d ${D}${bindir}
    mkdir -p ${D}/${bindir}/systemready-scripts
    cp -r ${S}/systemready-scripts/* ${D}/${bindir}/systemready-scripts/

}
FILES:${PN} += "${bindir}/systemready-scripts/*"