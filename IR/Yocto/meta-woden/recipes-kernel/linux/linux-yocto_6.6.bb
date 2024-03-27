KBRANCH ?= "v6.6/standard/base"

require recipes-kernel/linux/linux-yocto.inc

SRCREV_machine ?= "195b2994f955071be3dd16ff61127dbc6b2e0069"
SRCREV_meta ?= "8ab17895c185426442d80a60829619270f9ac51d"

# set your preferred provider of linux-yocto to 'linux-yocto-upstream', and you'll
# get the <version>/base branch, which is pure upstream -stable, and the same
# meta SRCREV as the linux-yocto-standard builds. Select your version using the
# normal PREFERRED_VERSION settings.
BBCLASSEXTEND = "devupstream:target"
SRCREV_machine:class-devupstream ?= "a06ca85b22f6c7f4e6dd1447ca50ded6f54ebb5e"
PN:class-devupstream = "linux-yocto-upstream"
KBRANCH:class-devupstream = "v6.6/base"

SRC_URI = "git://git.yoctoproject.org/linux-yocto.git;name=machine;branch=${KBRANCH}; \
           git://git.yoctoproject.org/yocto-kernel-cache;type=kmeta;name=meta;branch=yocto-6.6;destsuffix=${KMETA} \
           https://gitlab.arm.com/linux-arm/linux-acs/-/raw/master/kernel/src/0001-BSA-ACS-Linux-6.6.patch;patch=1;md5sum=89b6c420ece275846f79c8b6f6f9cb09 \
           file://0001-KSelfTest.patch;patch=1 \
           file://0001-dt-extract-compatibles.patch;patch=1 \
           file://0001-disable-default-psci-checker-run.patch;patch=1 \
"
FILESEXTRAPATHS:prepend := "${TOPDIR}/../meta-arm/meta-arm/recipes-kernel/linux/files:"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"
LINUX_VERSION ?= "6.6.12"

DEPENDS += "${@bb.utils.contains('ARCH', 'x86', 'elfutils-native', '', d)}"
DEPENDS += "openssl-native util-linux-native"
DEPENDS += "gmp-native libmpc-native"

PV = "${LINUX_VERSION}+git${SRCPV}"

KMETA = "kernel-meta"
KCONF_BSP_AUDIT_LEVEL = "1"

COMPATIBLE_MACHINE:generic-arm64 = "generic-arm64"


# Functionality flags
KERNEL_EXTRA_FEATURES ?= "features/netfilter/netfilter.scc"
KERNEL_FEATURES:append = " ${KERNEL_EXTRA_FEATURES}"
KERNEL_FEATURES:append = " ${@bb.utils.contains("TUNE_FEATURES", "mx32", " cfg/x32.scc", "", d)}"
KERNEL_FEATURES:append = " ${@bb.utils.contains("DISTRO_FEATURES", "ptest", " features/scsi/scsi-debug.scc", "", d)}"
KERNEL_FEATURES:append = " ${@bb.utils.contains("DISTRO_FEATURES", "ptest", " features/gpio/mockup.scc", "", d)}"

#added extra
PACKAGECONFIG[dt] = ",,, bash"