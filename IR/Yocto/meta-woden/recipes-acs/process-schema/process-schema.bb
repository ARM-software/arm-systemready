LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native"

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.2.tar.xz"
SRC_URI[sha256sum] = "ee41f3c4f599b2f46f08aae428c9243db403e7292eb2c9f04ee34909b038d1ae"

do_install(){
    install -d ${D}${bindir}
    cp -r ${S}/linux-6.1.2/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"