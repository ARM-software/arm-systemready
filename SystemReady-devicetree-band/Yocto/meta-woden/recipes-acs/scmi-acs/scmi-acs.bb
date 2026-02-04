SUMMARY = "SCMI ACS Linux application"
DESCRIPTION = "Builds the scmi-acs suite from Arm GitLab and installs test artifacts."
HOMEPAGE = "https://git.gitlab.arm.com/tests/scmi-tests"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE.md;md5=2a944942e1496af1886903d274dedb13"

PV = "1.0+git${SRCDATE}"
PR = "r0"

SRC_URI = "git://git.gitlab.arm.com/tests/scmi-tests.git;protocol=https;branch=master;destsuffix=scmi-tests"
SRCREV = "${AUTOREV}"

S = "${WORKDIR}/scmi-tests"
DEPENDS += "virtual/libc"
PARALLEL_MAKE = "-j1"
SCMI_INSTALL_DIR = "${datadir}/scmi-tests"

do_compile() {
    bbnote "Building scmi-acs with Yocto toolchain (CROSS_COMPILE=${TARGET_PREFIX}, CC=${CC})"

    export CROSS_COMPILE="${TARGET_PREFIX}"

    oe_runmake -C "${S}" clean

    oe_runmake -C "${S}" \
        CC="${CC}" CXX="${CXX}" CPP="${CPP}" \
        AR="${AR}" LD="${LD}" STRIP="${STRIP}" RANLIB="${RANLIB}" \
        CFLAGS="${CFLAGS} ${CPPFLAGS} -DVERBOSE_LEVEL=3 -DVERBOSE=3" \
        CPPFLAGS="${CPPFLAGS}" LDFLAGS="${LDFLAGS}" \
        TRANS=raw \
        PLAT=linux \
        TARGET=generic_scmi \
        PROTOCOLS="base,clock,power_domain,system_power,performance,powercap,sensor,reset,voltage,pin_control" \
        VERBOSE=3
}

do_install() {
    install -d ${D}${bindir}
    cd ${S}
    install -m 0755 scmi_test_agent ${D}${bindir}/scmi_test_agent
}

FILES:${PN} += "${bindir}/scmi_test_agent"
