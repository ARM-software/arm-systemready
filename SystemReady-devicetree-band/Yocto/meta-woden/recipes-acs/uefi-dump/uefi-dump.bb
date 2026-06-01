SUMMARY = "UEFI Dump Application"
DESCRIPTION = "Fetch bbr-acs from GitHub and build UefiDump.efi from the fetched source"

require recipes-acs/edk2-firmware/edk2-firmware-rev.bb

PROVIDES:remove = "virtual/uefi-firmware"
PROVIDES:remove = "virtual/bootloader"

LICENSE = "CLOSED"
COMPATIBLE_MACHINE:genericarm64 = "genericarm64"
COMPATIBLE_HOST = "aarch64.*-linux"

EDK2_ARCH = "AARCH64"
EDK2_PLATFORM = "MdeModule"
EDK2_PLATFORM_DSC = "${WORKDIR}/bbr-acs/ebbr/uefi_app/UefiDump.dsc"

SRC_URI += "git://github.com/ARM-software/bbr-acs;destsuffix=bbr-acs;protocol=https;branch=main;name=bbr-acs"
SRCREV_bbr-acs = "${AUTOREV}"

BBR_ACS_DIR = "${WORKDIR}/bbr-acs"
PACKAGES_PATH .= ":${BBR_ACS_DIR}"

EDK2_EXTRA_BUILD = ""

do_install() {
    install -d ${D}/firmware
    install ${B}/Build/${EDK2_PLATFORM}/${EDK2_BUILD_MODE}_${EDK_COMPILER}/${EDK2_ARCH}/UefiDump.efi ${D}/firmware/
}
