LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.12.tar.xz"
SRC_URI[sha256sum] = "b1a2562be56e42afb3f8489d4c2a7ac472ac23098f1ef1c1e40da601f54625eb"

do_install(){
    install -d ${D}${bindir}
    cp -r ${S}/linux-6.12/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"