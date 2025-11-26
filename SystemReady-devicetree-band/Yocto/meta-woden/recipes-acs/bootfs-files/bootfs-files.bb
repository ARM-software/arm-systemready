LICENSE = "CLOSED"

PACKAGE_ARCH = "${MACHINE_ARCH}"

inherit deploy
DEPENDS = "ebbr-sct pfdi-acs bsa-acs systemready-scripts bsa-acs-drv edk2-test-parser fwts linux-yocto"
S = "${WORKDIR}"

SRC_URI = " file://bsa.nsh \
            file://pfdi.nsh \
            file://debug_dump.nsh \
            file://startup.nsh \
            file://pingtest.nsh \
            file://capsule_update.nsh \
            file://bbsr_startup.nsh \
            file://acs_config_dt.txt \
            file://system_config.txt \
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
   cp pfdi.nsh ${DEPLOYDIR}/
   cp debug_dump.nsh ${DEPLOYDIR}/
   cp startup.nsh ${DEPLOYDIR}/
   cp pingtest.nsh ${DEPLOYDIR}/
   cp capsule_update.nsh ${DEPLOYDIR}/
   cp bbsr_startup.nsh ${DEPLOYDIR}/
   cp acs_config_dt.txt ${DEPLOYDIR}/acs_config.txt
   cp system_config.txt ${DEPLOYDIR}/
   cp ${S}/../../../armv8a-oe-linux/ebbr-sct/1.0/bbr-acs/bbsr/config/BBSRStartup.nsh  ${DEPLOYDIR}/bbsr_SctStartup.nsh

   # create and copy necessary flags to deploy directory
   touch bsa_dt.flag yocto_image.flag
   cp bsa_dt.flag yocto_image.flag ${DEPLOYDIR}/

}

addtask deploy after do_install
