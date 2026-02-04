SUMMARY = "Firmware testsuite"
DESCRIPTION = "The tool fwts comprises of over fifty tests that are designed to exercise and test different aspects of a machine's firmware. Many of these tests need super user access to read BIOS data and ACPI tables, so the tool requires running with super user privileges (e.g. with sudo)."
HOMEPAGE = "https://wiki.ubuntu.com/Kernel/Reference/fwts"

LICENSE = "GPL-2.0-or-later"
LIC_FILES_CHKSUM = "file://src/main.c;beginline=1;endline=16;md5=79533a427253d19fae2d2c094ebcf28a"

S = "${WORKDIR}/${BP}/fwts-${PV}"

SRC_URI = "https://fwts.ubuntu.com/release/fwts-V${PV}.tar.gz;subdir=${BP} \
           file://0001-Add-correct-printf-qualifier-for-off_t.patch \
           file://0004-Define-__SWORD_TYPE-if-not-defined-by-libc.patch \
           file://0005-Undefine-PAGE_SIZE.patch \
           file://0001-uefi-esrt-Added-esrt_test2-for-EBBR.patch \
           file://0007-smccc-downgrade-fails-to-warnings.patch \
           "

SRC_URI[sha256sum] = "25565fd007b378bf29581eb0bc36a03a2f0c49326bb6084f980fee9c5921f289"

COMPATIBLE_HOST = "(i.86|x86_64|aarch64|powerpc64).*-linux"

DEPENDS = "libpcre glib-2.0 dtc bison-native libbsd virtual/kernel"
DEPENDS:append:libc-musl = " libexecinfo"

inherit autotools bash-completion pkgconfig module-base

# Map aarch64 → arm64; otherwise fall back to TARGET_ARCH
KERNEL_ARCH ?= "${@bb.utils.contains('TUNE_FEATURES', 'aarch64', 'arm64', d.getVar('TARGET_ARCH'), d)}"

LDFLAGS:append:libc-musl = " -lexecinfo"

# We end up linker barfing with undefined symbols on ppc64 but not on other arches
# surprisingly
ASNEEDED:powerpc64le = ""

SMCCC_SRC_DIR ?= "${S}/smccc_test"
MODULE_NAME ?= "smccc_test"

do_compile:append() {
    if [ -d "${SMCCC_SRC_DIR}" ]; then
        export KERNEL_SRC=${STAGING_KERNEL_DIR}
        bbnote "Building smccc_test kernel module in ${SMCCC_SRC_DIR}"
        oe_runmake -C "${STAGING_KERNEL_DIR}" \
            M="${SMCCC_SRC_DIR}" \
            ARCH="${KERNEL_ARCH}" \
            CROSS_COMPILE="${TARGET_PREFIX}" \
            modules
    else
        bbwarn "SMCCC source directory not found: ${SMCCC_SRC_DIR}"
    fi
}

do_install:append() {
    install -d ${D}${base_libdir}/modules/${KERNEL_VERSION}/kernel/${MODULE_NAME}
    install -m 0644 ${SMCCC_SRC_DIR}/${MODULE_NAME}.ko \
        ${D}${base_libdir}/modules/${KERNEL_VERSION}/kernel/${MODULE_NAME}/${MODULE_NAME}.ko
}

FILES:${PN} += "${base_libdir}/modules/${KERNEL_VERSION}/kernel/${MODULE_NAME}/${MODULE_NAME}.ko"
FILES:${PN} += "${libdir}/fwts/lib*${SOLIBS}"
FILES:${PN}-dev += "${libdir}/fwts/lib*${SOLIBSDEV} ${libdir}/fwts/lib*.la"
FILES:${PN}-staticdev += "${libdir}/fwts/lib*a"

RDEPENDS:${PN} += "dtc"
