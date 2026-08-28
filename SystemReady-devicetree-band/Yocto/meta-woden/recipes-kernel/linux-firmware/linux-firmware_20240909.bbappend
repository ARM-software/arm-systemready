# The Scarthgap linux-firmware release predates most of the X1E80100
# firmware.  Backport the platform-wide files without replacing the rest of
# the LTS firmware collection.
X1E80100_FIRMWARE_TAG = "20260810"
PR:append = ".1"
X1E80100_FIRMWARE_URI = "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/qcom/x1e80100"
X1E80100_FIRMWARE_WORKDIR = "${S}/x1e80100-${X1E80100_FIRMWARE_TAG}"

SRC_URI += " \
    ${X1E80100_FIRMWARE_URI}/X1E001DE-DEVKIT-tplg.bin?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E001DE-DEVKIT-tplg.bin;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e001de_devkit_tplg \
    ${X1E80100_FIRMWARE_URI}/X1E80100-CRD-tplg.bin?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-CRD-tplg.bin;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_crd_tplg \
    ${X1E80100_FIRMWARE_URI}/X1E80100-EVK-tplg.bin?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-EVK-tplg.bin;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_evk_tplg \
    ${X1E80100_FIRMWARE_URI}/X1E80100-Romulus-tplg.bin?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-Romulus-tplg.bin;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_romulus_tplg \
    ${X1E80100_FIRMWARE_URI}/X1E80100-TUXEDO-Elite-14-tplg.bin?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-TUXEDO-Elite-14-tplg.bin;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_tuxedo_elite_14_tplg \
    ${X1E80100_FIRMWARE_URI}/X1P42100-Microsoft-Surface-Pro-12in-tplg.bin?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-X1P42100-Microsoft-Surface-Pro-12in-tplg.bin;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1p42100_surface_pro_12_tplg \
    ${X1E80100_FIRMWARE_URI}/adsp.mbn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adsp.mbn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_adsp \
    ${X1E80100_FIRMWARE_URI}/adsp_dtb.mbn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adsp_dtb.mbn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_adsp_dtb \
    ${X1E80100_FIRMWARE_URI}/adspr.jsn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adspr.jsn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_adspr \
    ${X1E80100_FIRMWARE_URI}/adsps.jsn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adsps.jsn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_adsps \
    ${X1E80100_FIRMWARE_URI}/adspua.jsn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adspua.jsn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_adspua \
    ${X1E80100_FIRMWARE_URI}/battmgr.jsn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-battmgr.jsn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_battmgr \
    ${X1E80100_FIRMWARE_URI}/cdsp.mbn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-cdsp.mbn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_cdsp \
    ${X1E80100_FIRMWARE_URI}/cdsp_dtb.mbn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-cdsp_dtb.mbn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_cdsp_dtb \
    ${X1E80100_FIRMWARE_URI}/cdspr.jsn?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-cdspr.jsn;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_cdspr \
    ${X1E80100_FIRMWARE_URI}/qupv3fw.elf?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-qupv3fw.elf;subdir=${BP}/x1e80100-${X1E80100_FIRMWARE_TAG};name=x1e80100_qupv3fw \
    https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/LICENSES/LICENSE.qcom-2?h=${X1E80100_FIRMWARE_TAG};downloadfilename=linux-firmware-${X1E80100_FIRMWARE_TAG}-LICENSE.qcom-2;subdir=${BP};name=x1e80100_qcom2_license \
"

SRC_URI[x1e001de_devkit_tplg.sha256sum] = "e9c74273a3b01bfed3ae53ed80694c35c9b24faed367e31b595b9fb1b95eadee"
SRC_URI[x1e80100_crd_tplg.sha256sum] = "e9c74273a3b01bfed3ae53ed80694c35c9b24faed367e31b595b9fb1b95eadee"
SRC_URI[x1e80100_evk_tplg.sha256sum] = "e9c74273a3b01bfed3ae53ed80694c35c9b24faed367e31b595b9fb1b95eadee"
SRC_URI[x1e80100_romulus_tplg.sha256sum] = "aa303397750f883ecaeed874d7547da658500596247676a6d405bf1ec43290b5"
SRC_URI[x1e80100_tuxedo_elite_14_tplg.sha256sum] = "e9c74273a3b01bfed3ae53ed80694c35c9b24faed367e31b595b9fb1b95eadee"
SRC_URI[x1p42100_surface_pro_12_tplg.sha256sum] = "89b731f3f98fc2b84699bca39a56e390925a44a26d5aea80382cf617e00c08d8"
SRC_URI[x1e80100_adsp.sha256sum] = "2e39041c278213f56a9e74c188753f2f33bebbac6b47672e3b329320c9f35298"
SRC_URI[x1e80100_adsp_dtb.sha256sum] = "abe585dc5b0b1093023a203d323895318f637de339611deb25b3a7fe69b6d0ee"
SRC_URI[x1e80100_adspr.sha256sum] = "66ce8531efb7979d234e0f0eabbe18d038ac97da771a8a194f613df8f0724e81"
SRC_URI[x1e80100_adsps.sha256sum] = "12ac2f3ae8ced12aa4b06b3ab3a01bc4d8efe1c92ebea503c002f209a6ec176f"
SRC_URI[x1e80100_adspua.sha256sum] = "982a99853495e34726b8e44697fdfad303334de0a67cbf6cde306c8f1731000b"
SRC_URI[x1e80100_battmgr.sha256sum] = "be8c6fba330908e4683fb6282761cb08485a302d6a66e09721e102e342f27236"
SRC_URI[x1e80100_cdsp.sha256sum] = "3cfd1114c9205abd7975bf9783e57e4cc337bca39617f362308cd64085613df3"
SRC_URI[x1e80100_cdsp_dtb.sha256sum] = "0c3079606a223698cfb2ae8950a4a51ccaf9c6d68cb9920e273acd3ccc98b9c9"
SRC_URI[x1e80100_cdspr.sha256sum] = "6d01cd7dce745204d5de20efe57e2511149ca2a5b48ee562fbedefda573ca465"
SRC_URI[x1e80100_qupv3fw.sha256sum] = "dcb4ca490098f081dd3f85d91ca230c4755d376a4cdca51e6a4ba918fa4ab077"
SRC_URI[x1e80100_qcom2_license.sha256sum] = "8401a2253b19272c59537567194d0b264e7ef466379334ff6cea0beec7b8165d"

LICENSE:append = " & Firmware-qcom-2"
LIC_FILES_CHKSUM += "file://linux-firmware-${X1E80100_FIRMWARE_TAG}-LICENSE.qcom-2;md5=165287851294f2fb8ac8cbc5e24b02b0"
NO_GENERIC_LICENSE[Firmware-qcom-2] = "linux-firmware-${X1E80100_FIRMWARE_TAG}-LICENSE.qcom-2"

PACKAGES:prepend = "${PN}-qcom-x1e80100 ${PN}-qcom-x1e80100-license "

FILES:${PN}-qcom-x1e80100 = "${nonarch_base_libdir}/firmware/qcom/x1e80100/*"
FILES:${PN}-qcom-x1e80100-license = "${nonarch_base_libdir}/firmware/LICENSE.qcom-2"

LICENSE:${PN}-qcom-x1e80100 = "Firmware-qcom-2 & Firmware-linaro"
LICENSE:${PN}-qcom-x1e80100-license = "Firmware-qcom-2"

RDEPENDS:${PN}-qcom-x1e80100 = "${PN}-qcom-x1e80100-license ${PN}-qcom-license"

do_install:append() {
    install -d ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100

    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E001DE-DEVKIT-tplg.bin ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/X1E001DE-DEVKIT-tplg.bin
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-CRD-tplg.bin ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/X1E80100-CRD-tplg.bin
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-EVK-tplg.bin ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/X1E80100-EVK-tplg.bin
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-Romulus-tplg.bin ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/X1E80100-Romulus-tplg.bin
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-X1E80100-TUXEDO-Elite-14-tplg.bin ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/X1E80100-TUXEDO-Elite-14-tplg.bin
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-X1P42100-Microsoft-Surface-Pro-12in-tplg.bin ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/X1P42100-Microsoft-Surface-Pro-12in-tplg.bin
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adsp.mbn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/adsp.mbn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adsp_dtb.mbn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/adsp_dtb.mbn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adspr.jsn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/adspr.jsn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adsps.jsn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/adsps.jsn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-adspua.jsn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/adspua.jsn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-battmgr.jsn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/battmgr.jsn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-cdsp.mbn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/cdsp.mbn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-cdsp_dtb.mbn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/cdsp_dtb.mbn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-cdspr.jsn ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/cdspr.jsn
    install -m 0644 ${X1E80100_FIRMWARE_WORKDIR}/linux-firmware-${X1E80100_FIRMWARE_TAG}-x1e80100-qupv3fw.elf ${D}${nonarch_base_libdir}/firmware/qcom/x1e80100/qupv3fw.elf
    install -m 0644 ${S}/qcom/NOTICE.txt ${D}${nonarch_base_libdir}/firmware/qcom/NOTICE.txt
    install -m 0644 ${S}/linux-firmware-${X1E80100_FIRMWARE_TAG}-LICENSE.qcom-2 ${D}${nonarch_base_libdir}/firmware/LICENSE.qcom-2
}

# Qualcomm firmware may use ELF containers without normal host linkage.
INSANE_SKIP:${PN}-qcom-x1e80100:append = " ldflags"
