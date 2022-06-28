inherit core-image

COMPATIBLE_HOST = "aarch64.*-linux"

WKS_FILE = "woden.wks.in"

# Minimal install, don't pull in packagegroup-base
IMAGE_INSTALL = "packagegroup-core-boot \
                 python3 \
                 fwts \
                 bsa-acs-drv \
                 bsa-acs-app \
                 ${CORE_IMAGE_EXTRA_INSTALL}"

EXTRA_IMAGEDEPENDS += "bsa-acs \
                       shell-app \
                       uefi-apps \
                       ebbr-sct \
                       bootfs-files \
"
IMAGE_EFI_BOOT_FILES += "Bsa.efi;EFI/BOOT/bsa/Bsa.efi \
                         bsa.nsh;EFI/BOOT/bsa/bsa.nsh \
                         ir_bsa.flag;EFI/BOOT/bsa/ir_bsa.flag \
                         yocto_image.flag \
                         debug_dump.nsh;EFI/BOOT/debug/debug_dump.nsh \
                         startup.nsh;EFI/BOOT/startup.nsh \
                         CapsuleApp.efi;EFI/BOOT/app/CapsuleApp.efi \
                         Shell.efi;EFI/BOOT/Shell.efi \
"

do_dir_deploy() {
    # copying bbr directory to /boot partition
    wic cp ${DEPLOY_DIR_IMAGE}/bbr ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/

    # create and copy empty acs_results directory to /results partition
    mkdir -p acs_results
    wic cp acs_results ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:3/

    #add bsa/bbr bootloder entry and set it has default boot
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg grub.cfg
    echo "menuentry 'bbr/bsa' {chainloader /EFI/BOOT/Shell.efi}"  >> grub.cfg
    sed -i 's\default=boot\default=bbr/bsa\g' grub.cfg
    sed -i 's\boot\Linux Boot\g' grub.cfg
    wic cp grub.cfg ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg

    # update startup.nsh linux command with command from grub.cfg
    # since PARTUUID method is reliable
    LINUX_BOOT_CMD=`grep -Po 'Image\s+[a-zA-Z]+=.*' < grub.cfg`
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/startup.nsh startup.nsh
    sed -i -E 's/Image\s+[a-zA-Z]+=.*/'"${LINUX_BOOT_CMD}"'/g' startup.nsh
    wic cp startup.nsh ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/startup.nsh

    # remove additional startup.nsh from /boot partition
    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/startup.nsh
}

IMAGE_FEATURES += "empty-root-password"
IMAGE_INSTALL:append = "systemd-init-install \
                        pciutils \
"

addtask dir_deploy before do_populate_lic_deploy after do_image_complete
