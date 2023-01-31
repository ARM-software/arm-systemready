LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native"

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.2.tar.xz"
SRC_URI[sha256sum] = "67dab932e85f9b9062ced666c8ea888230a1dadfd624b05aead6b6ebc6d3bdd5"

do_install(){
    install -d ${D}${bindir}
    cp -r ${S}/linux-5.19.10/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"