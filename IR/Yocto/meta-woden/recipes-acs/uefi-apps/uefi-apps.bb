SUMMARY = "UEFI Applications"
DESCRIPTION = "This recipe builds UEFI Applications and deploys CapsuleApp"

require recipes-acs/edk2-firmware/edk2-firmware-rev.bb

PROVIDES:remove = "virtual/uefi-firmware"
PROVIDES:remove = "virtual/bootloader"

LICENSE = "CLOSED"
COMPATIBLE_MACHINE:generic-arm64 = "generic-arm64"

COMPATIBLE_HOST = "aarch64.*-linux"
EDK2_ARCH = "AARCH64"
EDK2_PLATFORM = "MdeModule"
EDK2_PLATFORM_DSC = "MdeModulePkg/MdeModulePkg.dsc"

do_install() {
    install -d ${D}/firmware
    install ${B}/Build/${EDK2_PLATFORM}/${EDK2_BUILD_MODE}_${EDK_COMPILER}/${EDK2_ARCH}/CapsuleApp.efi ${D}/firmware/
}
