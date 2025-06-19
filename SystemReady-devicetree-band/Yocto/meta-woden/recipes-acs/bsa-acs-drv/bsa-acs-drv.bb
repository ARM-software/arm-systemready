SUMMARY = "BSA-ACS Linux driver"
LICENSE = "GPLv2 & Apache-2.0"
LIC_FILES_CHKSUM = "file://sysarch-acs/LICENSE;md5=86d3f3a95c324c9479bd8986968f4327 \
                    file://linux-acs/acs-drv/files/COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e \
"
COMPATIBLE_MACHINE:genericarm64 = "genericarm64"

inherit module-base

SRC_URI += "git://github.com/ARM-software/sysarch-acs;destsuffix=sysarch-acs;protocol=https;branch=main;name=sysarch-acs \
            git://git.gitlab.arm.com/linux-arm/linux-acs.git;destsuffix=linux-acs;protocol=https;branch=sysarch-acs;name=linux-acs \
            "
SRCREV_FORMAT = "sysarch-acs_linux-acs"
SRCREV_sysarch-acs = "${AUTOREV}"
SRCREV_linux-acs = "${AUTOREV}"

S = "${WORKDIR}"
MODULE_NAME = "bsa_acs"

do_configure(){
    cd ${S}/linux-acs/acs-drv/files/
    ./acs_setup.sh ${S}/sysarch-acs
}

do_compile() {
    export KERNEL_SRC=${STAGING_KERNEL_DIR}
    cd ${S}/linux-acs/acs-drv/files/
    ./linux_acs.sh bsa
}

do_install() {
    install -d ${D}/${base_libdir}/modules/${KERNEL_VERSION}/kernel/${MODULE_NAME}
    install -m 0644 ${S}/linux-acs/acs-drv/files/${MODULE_NAME}.ko \
    ${D}/${base_libdir}/modules/${KERNEL_VERSION}/kernel/${MODULE_NAME}/${MODULE_NAME}.ko
}

FILES:${PN} += "${base_libdir}/* \
"

