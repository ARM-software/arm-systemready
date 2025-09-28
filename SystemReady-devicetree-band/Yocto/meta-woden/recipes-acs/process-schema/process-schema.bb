LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.16.tar.xz"
SRC_URI[sha256sum] = "1a4be2fe6b5246aa4ac8987a8a4af34c42a8dd7d08b46ab48516bcc1befbcd83"

do_install(){
    install -d ${D}${bindir}
    cp -r ${S}/linux-6.16/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"
