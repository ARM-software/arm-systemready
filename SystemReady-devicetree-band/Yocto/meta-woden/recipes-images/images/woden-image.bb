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
                       pfdi-acs \
"
IMAGE_EFI_BOOT_FILES += "Bsa.efi;acs_tests/bsa/Bsa.efi \
                         bsa.nsh;acs_tests/bsa/bsa.nsh \
                         pfdi.efi;acs_tests/pfdi/pfdi.efi \
                         pfdi.nsh;acs_tests/pfdi/pfdi.nsh \
                         pingtest.nsh;acs_tests/debug/pingtest.nsh \
                         capsule_update.nsh;acs_tests/app/capsule_update.nsh \
                         bsa_dt.flag;acs_tests/bsa/bsa_dt.flag \
                         yocto_image.flag \
                         debug_dump.nsh;acs_tests/debug/debug_dump.nsh \
                         startup.nsh;EFI/BOOT/startup.nsh \
                         acs_config.txt;acs_tests/config/acs_config.txt \
                         system_config.txt;acs_tests/config/system_config.txt \
                         bbsr_startup.nsh;EFI/BOOT/bbsr_startup.nsh \
                         bbsr_SctStartup.nsh;acs_tests/bbr/bbsr_SctStartup.nsh \
                         CapsuleApp.efi;acs_tests/app/CapsuleApp.efi \
                         UpdateVars.efi;acs_tests/app/UpdateVars.efi \
                         Shell.efi;EFI/BOOT/Shell.efi \
"

DEPENDS += "sbsigntool-native"

do_sign_images() {
    rm -rf DO_SIGN
    mkdir DO_SIGN
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/ DO_SIGN/

    KEYS_DIR="DO_SIGN/acs_tests/bbsr-keys"
    echo "KEYS_DIR = $KEYS_DIR"

    #Sign the executables
    TEST_DB1_KEY=$KEYS_DIR/TestDB1.key
    TEST_DB1_CRT=$KEYS_DIR/TestDB1.crt

    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/acs_tests/bsa/Bsa.efi --output DO_SIGN/acs_tests/bsa/Bsa.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/acs_tests/pfdi/pfdi.efi --output DO_SIGN/acs_tests/pfdi/pfdi.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/Shell.efi --output DO_SIGN/EFI/BOOT/Shell.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/EFI/BOOT/bootaa64.efi --output DO_SIGN/EFI/BOOT/bootaa64.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/acs_tests/app/CapsuleApp.efi --output DO_SIGN/acs_tests/app/CapsuleApp.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/acs_tests/app/UpdateVars.efi --output DO_SIGN/acs_tests/app/UpdateVars.efi
    sbsign --key $TEST_DB1_KEY --cert $TEST_DB1_CRT DO_SIGN/Image --output DO_SIGN/Image

    echo "Signing images complete."
    wic cp DO_SIGN/EFI ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/
    wic cp DO_SIGN/Image ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/

    # Copy signed EFI binaries back to deploy directory
    wic cp DO_SIGN/acs_tests ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/
    echo "Copy back complete"
}


do_dir_deploy() {

    # copying bbr directory to /boot partition
    mkdir -p acs_tests
    wic cp acs_tests ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/
    wic cp ${DEPLOY_DIR_IMAGE}/bbr ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/acs_tests/
    wic cp ${DEPLOY_DIR_IMAGE}/bbsr-keys ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/acs_tests/
    wic cp ${DEPLOY_DIR_IMAGE}/core-image-initramfs-boot-genericarm64.cpio.gz ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/

    do_sign_images;

    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/acs_tests/bbsr-keys/*.crt
    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/acs_tests/bbsr-keys/*.esl
    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/acs_tests/bbsr-keys/*.key

    # create and copy empty acs_results_template directory to /results partition
    mkdir -p acs_results_template/acs_results
    mkdir -p acs_results_template/os-logs
    mkdir -p acs_results_template/fw
    wic cp acs_results_template ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/

    #add bsa/bbr bootloder entry and set it has default boot

    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg grub.cfg
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg ${DEPLOY_DIR_IMAGE}/grub2.cfg

    LINUX_BOOT_CMD_TEMP=`grep -Po 'Image\s+[a-zA-Z]+=.*' < grub.cfg`
    LINUX_BOOT_CMD=`echo $LINUX_BOOT_CMD_TEMP | head -1`

    sed -i 's\ext4\ext4 earlycon video=efifb:off\g' grub.cfg

    if grep  -Eq "menuentry.*bbr/bsa"  grub.cfg
    then
        echo "grub entry for bbr and bsa already present"
    else
        echo "menuentry 'bbr/bsa' {chainloader /EFI/BOOT/Shell.efi}"  >> grub.cfg
    fi

    sed -i 's\default=boot\default=bbr/bsa\g' grub.cfg
    sed -i 's\boot\Linux Boot\g' grub.cfg

    if grep  -Eq "BBSR Compliance (Automation)"  grub.cfg
    then
        echo "grub entry for BBSR Compliance (Automation) already present"
    else
        echo "menuentry 'BBSR Compliance (Automation)' {chainloader /EFI/BOOT/Shell.efi -nostartup bbsr_startup.nsh}" >> grub.cfg
    fi

    sed -i "/menuentry 'Linux Boot'/,/}/{ /linux /a \
    initrd /core-image-initramfs-boot-genericarm64.cpio.gz
    }" grub.cfg

    wic cp grub.cfg ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/grub.cfg

    # update startup.nsh linux command with command from grub.cfg
    # since PARTUUID method is reliable

    echo "LINUX_BOOT_CMD=$LINUX_BOOT_CMD"
    LINUX_BOOT_CMD1=$(echo "$LINUX_BOOT_CMD" | sed 's/Image/Image initrd=\\\\core-image-initramfs-boot-genericarm64.cpio.gz/')
    echo "LINUX_BOOT_CMD1=$LINUX_BOOT_CMD1"

    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/startup.nsh startup.nsh
    wic cp ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/bbsr_startup.nsh bbsr_startup.nsh

    sed  -i -E 's/Image.*LABEL.*=.*/'"${LINUX_BOOT_CMD1} earlycon video=efifb:off"'/g' startup.nsh
    sed  -i -E 's/Image.*LABEL.*=.*/'"${LINUX_BOOT_CMD1} earlycon video=efifb:off secureboot "'/g' bbsr_startup.nsh

    wic cp startup.nsh ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/startup.nsh
    wic cp bbsr_startup.nsh ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/EFI/BOOT/bbsr_startup.nsh

    # remove additional startup.nsh from /boot partition
    wic rm ${DEPLOY_DIR_IMAGE}/${IMAGE_LINK_NAME}.wic:1/startup.nsh
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
                        pango \
                        cairo \
                        gdk-pixbuf \
                        python3-matplotlib \
                        python3-chardet \
                        python3-jinja2 \
                        systemready-scripts \
                        dejavu-fonts \
                        python3-cssselect2 \
                        python3-fonttools \
                        python3-pydyf \
                        python3-pyphen \
                        python3-tinycss2 \
                        python3-tinyhtml5 \
                        python3-weasyprint \
                        python3-webencodings \
                        tar \
"

addtask dir_deploy before do_populate_lic_deploy after do_image_complete
