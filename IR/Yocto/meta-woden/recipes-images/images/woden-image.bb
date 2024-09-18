inherit core-image

COMPATIBLE_HOST = "aarch64.*-linux"

WKS_FILE = "woden.wks.in"

# Minimal install, don't pull in packagegroup-base
IMAGE_INSTALL = "packagegroup-core-boot \
                 python3 \
                 fwts \
                 bsa-acs-drv \
                 bsa-acs-app \
                 mokutil \
                 tpm2-tools \
                 tpm2-abrmd \
                 rng-tools \
                 gptfdisk \
                 coreutils \
                 ${CORE_IMAGE_EXTRA_INSTALL} \
"

EXTRA_IMAGEDEPENDS += "bsa-acs \
                       shell-app \
                       uefi-apps \
                       update-vars \
                       ebbr-sct \
                       bootfs-files \
"
IMAGE_EFI_BOOT_FILES += "Bsa.efi;EFI/BOOT/bsa/Bsa.efi \
                         bsa.nsh;EFI/BOOT/bsa/bsa.nsh \
                         pingtest.nsh;EFI/BOOT/debug/pingtest.nsh \
                         ir_bsa.flag;EFI/BOOT/bsa/ir_bsa.flag \
                         yocto_image.flag \
                         debug_dump.nsh;EFI/BOOT/debug/debug_dump.nsh \
                         startup.nsh;EFI/BOOT/startup.nsh \
                         sie_startup.nsh;EFI/BOOT/sie_startup.nsh \
                         sie_SctStartup.nsh;EFI/BOOT/bbr/sie_SctStartup.nsh \
                         CapsuleApp.efi;EFI/BOOT/app/CapsuleApp.efi \
                         UpdateVars.efi;EFI/BOOT/app/UpdateVars.efi \
                         Shell.efi;EFI/BOOT/Shell.efi \
"

DEPENDS += "sbsigntool-native"

do_sign_images() {
    rm -rf DO_SIGN
    mkdir DO_SIGN
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/ DO_SIGN/

    KEYS_DIR="DO_SIGN/security-interface-extension-keys"
    echo "KEYS_DIR = $KEYS_DIR"

    #Sign the executables
    TEST_DB1_KEY=$KEYS_DIR/TestDB1.key
    TEST_DB1_CRT=$KEYS_DIR/TestDB1.crt

    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/bsa/Bsa.efi --output DO_SIGN/EFI/BOOT/bsa/Bsa.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/Shell.efi --output DO_SIGN/EFI/BOOT/Shell.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/bootaa64.efi --output DO_SIGN/EFI/BOOT/bootaa64.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/app/CapsuleApp.efi --output DO_SIGN/EFI/BOOT/app/CapsuleApp.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/app/UpdateVars.efi --output DO_SIGN/EFI/BOOT/app/UpdateVars.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/Image --output DO_SIGN/Image

    echo "Signing images complete."
    wic cp DO_SIGN/EFI ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/
    wic cp DO_SIGN/Image ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/

    echo "Copy back complete"
}


do_dir_deploy() {

    # copying bbr directory to /boot partition
    wic cp ${DEPLOY_DIR_IMAGE}/bbr ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/
    wic cp ${DEPLOY_DIR_IMAGE}/security-interface-extension-keys ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/

    do_sign_images;

    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/security-interface-extension-keys/*.crt
    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/security-interface-extension-keys/*.esl
    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/security-interface-extension-keys/*.key

    # create and copy empty acs_results directory to /results partition
    mkdir -p acs_results
    wic cp acs_results ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/

    #add bsa/bbr bootloder entry and set it has default boot

    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg grub.cfg

    LINUX_BOOT_CMD_TEMP=`grep -Po 'Image\s+[a-zA-Z]+=.*' < grub.cfg`
    LINUX_BOOT_CMD=`echo $LINUX_BOOT_CMD_TEMP | head -1`

    if grep  -Eq "menuentry.*bbr/bsa"  grub.cfg
    then
        echo "grub entry for bbr and bsa already present"
    else
        echo "menuentry 'bbr/bsa' {chainloader /EFI/BOOT/Shell.efi}"  >> grub.cfg
    fi

    sed -i 's\default=boot\default=bbr/bsa\g' grub.cfg
    sed -i 's\boot\Linux Boot\g' grub.cfg

    if grep  -Eq "SCT for Security Interface Extension"  grub.cfg
    then
        echo "grub entry for SCT for Security Interface Extension already present"
    else
        echo "menuentry 'SCT for Security Interface Extension (optional)' {chainloader /EFI/BOOT/Shell.efi -nostartup sie_startup.nsh}" >> grub.cfg
    fi

    if grep  -Eq "Linux Boot for Security Interface Extension"  grub.cfg
    then
        echo "grub entry for Linux Boot for Security Interface Extension already present"
    else
        awk '/menuentry '\''Linux Boot'\''/, /ext4/' grub.cfg | sed 's/Linux Boot/Linux Boot for Security Interface Extension (optional)/' | sed 's/ext4/ext4 secureboot/' >> grub.cfg
        echo "}" >> grub.cfg
    fi

    wic cp grub.cfg ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg

    # update startup.nsh linux command with command from grub.cfg
    # since PARTUUID method is reliable
    echo "LINUX_BOOT_CMD= $LINUX_BOOT_CMD"

    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/startup.nsh startup.nsh
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/sie_startup.nsh sie_startup.nsh

    sed  -i -E 's/Image.*LABEL.*=.*/'"${LINUX_BOOT_CMD}"'/g' startup.nsh
    sed  -i -E 's/Image.*LABEL.*=.*/'"${LINUX_BOOT_CMD} secureboot"'/g' sie_startup.nsh

    wic cp startup.nsh ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/startup.nsh
    wic cp sie_startup.nsh ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/sie_startup.nsh

    # remove additional startup.nsh from /boot partition
    # wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/startup.nsh
}

IMAGE_FEATURES += "empty-root-password"
IMAGE_INSTALL:append = "systemd-init-install \
                        pciutils \
                        python3-dtschema \
                        process-schema \
                        dmidecode \
                        efibootmgr \
                        ethtool \
                        tree \
                        util-linux \
                        lshw \
                        usbutils \
                        edk2-test-parser \
                        xz \
                        zip \
                        openssh \
                        openssh-sftp \
                        openssh-sftp-server \
                        kernel-module-tpm-ftpm-tee \
                        curl \
                        fwupd \
                        fwupd-efi \
                        udisks2 \
"

addtask dir_deploy before do_populate_lic_deploy after do_image_complete
