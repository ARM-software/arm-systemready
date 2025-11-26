FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append:genericarm64 = " file://systemready.cfg"
#This file is defined to add this path to all the linux-yocto recipe
FILESEXTRAPATHS:prepend := "${TOPDIR}/../meta-arm/meta-arm/recipes-kernel/linux/files:"

SYSTEMREADY_COMMIT_LOG ?= "${TOPDIR}/../recipes-acs/bootfs-files/files/systemready-commit.log"

LINUX_YOCTO_LOG_SRC_URI ?= "${@next((u for u in (d.getVar('SRC_URI') or '').split() if not u.startswith('file://')), '')}"

do_compile:append() {
    echo "linux-yocto" >> "${SYSTEMREADY_COMMIT_LOG}"
    if [ -n "${LINUX_YOCTO_LOG_SRC_URI}" ]; then
        echo "    SRC_URI(linux-yocto) = ${LINUX_YOCTO_LOG_SRC_URI}" >> "${SYSTEMREADY_COMMIT_LOG}"
    fi
    echo "    version(linux-yocto) = ${PV}" >> "${SYSTEMREADY_COMMIT_LOG}"
    echo "" >> "${SYSTEMREADY_COMMIT_LOG}"
}