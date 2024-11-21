LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.5.tar.xz"
SRC_URI[sha256sum] = "7a574bbc20802ea76b52ca7faf07267f72045e861b18915c5272a98c27abf884"

do_install(){
    install -d ${D}${bindir}
    cp -r ${S}/linux-6.5/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"