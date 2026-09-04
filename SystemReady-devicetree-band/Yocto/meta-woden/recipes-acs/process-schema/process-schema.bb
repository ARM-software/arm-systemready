LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.2.3.tar.xz"
SRC_URI[sha256sum] = "8ba259e8e7b13ec6ef0941c8a39ad90b24bd4a4d6c0010ba6bafb794550ecd03"

do_install(){
    install -d ${D}${bindir}/linux-7.2.3/bindings
    cp -r ${S}/linux-7.2.3/Documentation/devicetree/bindings ${D}/${bindir}/linux-7.2.3/bindings
    dt-mk-schema -j ${D}/${bindir}/linux-7.2.3/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"
