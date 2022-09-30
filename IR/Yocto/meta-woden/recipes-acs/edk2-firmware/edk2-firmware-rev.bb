
SRCREV_edk2           ?= "${AUTOREV}"
SRCREV_edk2-platforms ?= "${AUTOREV}"

FILESEXTRAPATHS:prepend := "${TOPDIR}/../meta-arm/meta-arm/recipes-bsp/uefi/files:"

require recipes-bsp/uefi/edk2-firmware.inc

SRC_URI:remove = "file://unaligned.patch"
SRC_URI:append = " file://allow_capsule_on_disk.patch "
