SUMMARY = "UEFI Shell Application"
DESCRIPTION = "This recipe builds UEFI Shell Application"

require recipes-acs/edk2-firmware/edk2-firmware-rev.bb

PROVIDES:remove = "virtual/uefi-firmware"
PROVIDES:remove = "virtual/bootloader"

LICENSE = "CLOSED"
COMPATIBLE_MACHINE:genericarm64 = "genericarm64"

COMPATIBLE_HOST = "aarch64.*-linux"
EDK2_ARCH = "AARCH64"
EDK2_PLATFORM = "Shell"
EDK2_PLATFORM_DSC = "ShellPkg/ShellPkg.dsc"
EDK2_BUILD_MODE = "RELEASE"

do_install() {
    install -d ${D}/firmware
    install ${B}/Build/${EDK2_PLATFORM}/${EDK2_BUILD_MODE}_${EDK_COMPILER}/${EDK2_ARCH}/ShellPkg/Application/Shell/Shell/OUTPUT/Shell.efi ${D}/firmware/
}
