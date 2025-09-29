require recipes-acs/edk2-firmware/edk2-firmware-rev.bb

PROVIDES:remove = "virtual/uefi-firmware"
PROVIDES:remove = "virtual/bootloader"

LICENSE += "& Apache-2.0"
COMPATIBLE_MACHINE:genericarm64 = "genericarm64"

SRC_URI += "git://github.com/ARM-software/sysarch-acs;destsuffix=edk2/ShellPkg/Application/sysarch-acs;protocol=https;branch=main;name=sysarch-acs \
            git://github.com/tianocore/edk2-libc;destsuffix=edk2/edk2-libc;protocol=https;branch=master;name=edk2-libc \
            file://edk2_pfdi.patch \
            "

SRCREV_sysarch-acs = "${AUTOREV}"

SRCREV_edk2-libc = "${AUTOREV}"

COMPATIBLE_HOST = "aarch64.*-linux"
EDK2_ARCH = "AARCH64"
EDK2_PLATFORM = "Shell"
EDK2_PLATFORM_DSC = "ShellPkg/ShellPkg.dsc"
EDK2_EXTRA_BUILD = "--module ShellPkg/Application/sysarch-acs/apps/uefi/Pfdi.inf"

PACKAGES_PATH .= ":${S}/edk2-libc"

do_compile:prepend() {
    export ACS_PATH="${S}/ShellPkg/Application/sysarch-acs"
    export PATH="${STAGING_BINDIR_TOOLCHAIN}:${PATH}"
}

do_install() {
    install -d ${D}/firmware
    install ${B}/Build/${EDK2_PLATFORM}/${EDK2_BUILD_MODE}_${EDK_COMPILER}/*/pfdi.efi ${D}/firmware/pfdi.efi
}
