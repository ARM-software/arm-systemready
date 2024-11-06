TEST_LIST += "\
    dt \
"

RDEPENDS_${PN} += " perl-modules perl-module-io-handle "


do_install:append(){

    KERNEL_SRC_DIR="${S}/../../../../../work-shared/genericarm64/kernel-source"
    rm -f ${D}/usr/kernel-selftest/dt/compatible_list
    python3 $KERNEL_SRC_DIR/scripts/dtc/dt-extract-compatibles -d $KERNEL_SRC_DIR > ${D}/usr/kernel-selftest/dt/compatible_list
}
