LICENSE = "CLOSED"

PACKAGE_ARCH = "${MACHINE_ARCH}"

inherit deploy

S = "${WORKDIR}"

SRC_URI = " file://bsa.nsh \
            file://debug_dump.nsh \
            file://startup.nsh \
            file://sie_startup.nsh \
            file://sie_SctStartup.nsh \
            "

# no configure step
do_configure[noexec] = "1"

# no compile
do_compile[noexec] = "1"

# no install
do_install[noexec] = "1"

do_deploy() {
   # Copy the files to deploy directory
   cp bsa.nsh ${DEPLOYDIR}/
   cp debug_dump.nsh ${DEPLOYDIR}/
   cp startup.nsh ${DEPLOYDIR}/
   cp sie_startup.nsh ${DEPLOYDIR}/
   cp sie_SctStartup.nsh ${DEPLOYDIR}/

   # create and copy necessary flags to deploy directory
   touch ir_bsa.flag yocto_image.flag
   cp ir_bsa.flag yocto_image.flag ${DEPLOYDIR}/

}

addtask deploy after do_install
