SUMMARY = "BSA ACS Linux application"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://bsa-acs/LICENSE.md;md5=2a944942e1496af1886903d274dedb13 \
"

SRC_URI = "git://github.com/ARM-software/bsa-acs;destsuffix=bsa-acs;protocol=https;branch=main;name=bsa-acs \
"
SRCREV_bsa-acs = "${AUTOREV}"

S = "${WORKDIR}"
TARGET_CC_ARCH += "${LDFLAGS}"

do_compile() {
    cd  ${S}/bsa-acs/linux_app/bsa-acs-app
    ${CC} *.c -Iinclude -o ${S}/bsa
}

do_install() {
	install -d ${D}${bindir}
	install -m 0755 bsa ${D}${bindir}
}

FILES:${PN} += "${bindir}/*"

