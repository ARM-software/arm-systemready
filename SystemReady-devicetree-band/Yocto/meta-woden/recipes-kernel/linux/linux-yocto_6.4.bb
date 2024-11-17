KBRANCH ?= "v6.4/standard/base"

require recipes-kernel/linux/linux-yocto.inc

SRCREV_machine ?= "6995e2de6891c724bfeb2db33d7b87775f913ad1"
SRCREV_meta ?= "be4b1defa25b1560b7d92e1ade1b7c52a226fc38"

# set your preferred provider of linux-yocto to 'linux-yocto-upstream', and you'll
# get the <version>/base branch, which is pure upstream -stable, and the same
# meta SRCREV as the linux-yocto-standard builds. Select your version using the
# normal PREFERRED_VERSION settings.
BBCLASSEXTEND = "devupstream:target"
SRCREV_machine:class-devupstream ?= "3fbf24b73f4a5bc8fd39a6b7a29145451c1039ce"
PN:class-devupstream = "linux-yocto-upstream"
KBRANCH:class-devupstream = "v6.4/base"

SRC_URI = "git://git.yoctoproject.org/linux-yocto.git;name=machine;branch=${KBRANCH}; \
           git://git.yoctoproject.org/yocto-kernel-cache;type=kmeta;name=meta;branch=yocto-6.4;destsuffix=${KMETA} \
           https://gitlab.arm.com/linux-arm/linux-acs/-/raw/master/kernel/src/0001-BSA-ACS-Linux-6.4.patch;patch=1;md5sum=7a4ce9635bc4af637c0463d8fdd038c0 \
           file://0002-Fix-for-CompuLab-IOT-GATE-iMX8-boot-issue.patch;patch=1 \
           file://tpm-tis-spi-Add-hardware-wait-polling.patch;patch=1 \
           file://0001-disable-default-psci-checker-run.patch;patch=1 \
"
FILESEXTRAPATHS:prepend := "${TOPDIR}/../meta-arm/meta-arm/recipes-kernel/linux/files:"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"
LINUX_VERSION ?= "6.4"

DEPENDS += "${@bb.utils.contains('ARCH', 'x86', 'elfutils-native', '', d)}"
DEPENDS += "openssl-native util-linux-native"
DEPENDS += "gmp-native libmpc-native"

PV = "${LINUX_VERSION}+git${SRCPV}"

KMETA = "kernel-meta"
KCONF_BSP_AUDIT_LEVEL = "1"

COMPATIBLE_MACHINE:genericarm64 = "genericarm64"

# Functionality flags
KERNEL_EXTRA_FEATURES ?= "features/netfilter/netfilter.scc"
KERNEL_FEATURES:append = " ${KERNEL_EXTRA_FEATURES}"
KERNEL_FEATURES:append = " ${@bb.utils.contains("TUNE_FEATURES", "mx32", " cfg/x32.scc", "", d)}"
KERNEL_FEATURES:append = " ${@bb.utils.contains("DISTRO_FEATURES", "ptest", " features/scsi/scsi-debug.scc", "", d)}"
KERNEL_FEATURES:append = " ${@bb.utils.contains("DISTRO_FEATURES", "ptest", " features/gpio/mockup.scc", "", d)}"