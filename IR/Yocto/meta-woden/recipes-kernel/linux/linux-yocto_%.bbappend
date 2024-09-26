FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append:genericarm64 = " file://systemready.cfg"
#This file is defined to add this path to all the linux-yocto recipe
FILESEXTRAPATHS:prepend := "${TOPDIR}/../meta-arm/meta-arm/recipes-kernel/linux/files:"