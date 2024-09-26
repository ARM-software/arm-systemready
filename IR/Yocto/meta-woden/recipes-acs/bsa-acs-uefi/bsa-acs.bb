require recipes-acs/edk2-firmware/edk2-firmware-rev.bb

PROVIDES:remove = "virtual/uefi-firmware"
PROVIDES:remove = "virtual/bootloader"

LICENSE += "& Apache-2.0"
LIC_FILES_CHKSUM += "file://ShellPkg/Application/bsa-acs/LICENSE.md;md5=2a944942e1496af1886903d274dedb13"
COMPATIBLE_MACHINE:genericarm64 = "genericarm64"

SRC_URI += "git://github.com/ARM-software/bsa-acs;destsuffix=edk2/ShellPkg/Application/bsa-acs;protocol=https;branch=main;name=bsa-acs \
            git://github.com/tianocore/edk2-libc;destsuffix=edk2/edk2-libc;protocol=https;branch=master;name=edk2-libc \
            file://ir_bsa.patch \
            file://ir_bsa_hii.patch \
            "

SRCREV_bsa-acs   = "${AUTOREV}"
SRCREV_edk2-libc = "${AUTOREV}"

COMPATIBLE_HOST = "aarch64.*-linux"
EDK2_ARCH = "AARCH64"
EDK2_PLATFORM = "Shell"
EDK2_PLATFORM_DSC = "ShellPkg/ShellPkg.dsc"
EDK2_EXTRA_BUILD = "--module ShellPkg/Application/bsa-acs/uefi_app/BsaAcs.inf"

PACKAGES_PATH .= ":${S}/edk2-libc"

do_install() {
    install -d ${D}/firmware
    install ${B}/Build/${EDK2_PLATFORM}/${EDK2_BUILD_MODE}_${EDK_COMPILER}/*/Bsa.efi ${D}/firmware/
}
