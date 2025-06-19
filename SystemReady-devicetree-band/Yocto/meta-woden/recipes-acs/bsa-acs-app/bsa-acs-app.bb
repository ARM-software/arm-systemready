SUMMARY = "BSA ACS Linux application"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://sysarch-acs/LICENSE;md5=86d3f3a95c324c9479bd8986968f4327 \
"

SRC_URI = "git://github.com/ARM-software/sysarch-acs;destsuffix=sysarch-acs;protocol=https;branch=main;name=sysarch-acs \
"
SRCREV_sysarch-acs = "${AUTOREV}"

S = "${WORKDIR}"
TARGET_CC_ARCH += "${LDFLAGS}"

do_compile() {
    cd  ${S}/sysarch-acs/apps/linux/bsa-acs-app
    ${CC} *.c -Iinclude -o ${S}/bsa
}

do_install() {
	install -d ${D}${bindir}
	install -m 0755 bsa ${D}${bindir}
}

FILES:${PN} += "${bindir}/*"

