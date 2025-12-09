SUMMARY = "Build ledge.efi from ts-testing repo and deploy for image use"
LICENSE = "CLOSED"
inherit deploy

FILESEXTRAPATHS:prepend := "${THISDIR}/:"

# ts-testing repo
SRC_URI = "git://gitlab.com/Linaro/trustedsubstrate/ts-testing.git;protocol=https;branch=main \
           file://ledge-efi-http-label.patch \
          "

SRCREV = "${AUTOREV}"
S = "${WORKDIR}/git"

# Use host-side toolchain to emit a PE/COFF EFI application
DEPENDS = "clang-native"

do_compile() {
    oe_runmake -C ${S}/efi_app
}

do_install[noexec] = "1"

do_deploy() {
    install -d ${DEPLOYDIR}
    install -m 0644 ${S}/efi_app/ledge.efi ${DEPLOYDIR}/ledge.efi
}

addtask deploy after do_compile before do_build
