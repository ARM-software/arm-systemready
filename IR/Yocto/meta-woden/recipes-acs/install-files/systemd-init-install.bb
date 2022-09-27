LICENSE = "CLOSED"
inherit systemd

SYSTEMD_AUTO_ENABLE = "enable"
SYSTEMD_SERVICE:${PN} = "acs_run-before-login-prompt.service"

SRC_URI:append = " file://acs_run-before-login-prompt.service \
                   file://init.sh \
                   file://ir_bbr_fwts_tests.ini \
                   file://secure_init.sh \
                   file://bbsr_fwts_tests.ini \
		 "

FILES:${PN} += "${systemd_unitdir}/system"

do_install:append() {
  echo "S is ${S}"
  install -d ${D}${systemd_unitdir}/system
  install -d ${D}${bindir}
  install -m 0770 ${WORKDIR}/init.sh                             ${D}${bindir}
  install -m 0770 ${WORKDIR}/ir_bbr_fwts_tests.ini               ${D}${bindir}
  install -m 0770 ${WORKDIR}/secure_init.sh                      ${D}${bindir}
  install -m 0770 ${WORKDIR}/bbsr_fwts_tests.ini                 ${D}${bindir}
  install -m 0644 ${WORKDIR}/acs_run-before-login-prompt.service ${D}${systemd_unitdir}/system

}
