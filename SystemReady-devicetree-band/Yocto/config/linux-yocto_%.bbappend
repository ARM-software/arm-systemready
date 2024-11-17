ARMFILESPATHS := "${THISDIR}/${PN}:"

COMPATIBLE_MACHINE:genericarm64 = "genericarm64"
FILESEXTRAPATHS:prepend:genericarm64 = "${ARMFILESPATHS}"
SRC_URI:append:genericarm64 = " "

FILESEXTRAPATHS:prepend:qemuarm64-sbsa = "${ARMFILESPATHS}"
SRC_URI:append:qemuarm64-sbsa = " \
    file://defconfig.patch \
    "

FILESEXTRAPATHS:prepend:qemuarm64-secureboot = "${ARMFILESPATHS}"
SRC_URI:append:qemuarm64-secureboot = " \
    file://zone_dma_revert.patch \
    file://tee.cfg \
    "
