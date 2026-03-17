LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.19.tar.xz"
SRC_URI[sha256sum] = "303079a8250b8f381f82b03f90463d12ac98d4f6b149b761ea75af1323521357"

do_install(){
    install -d ${D}${bindir}/linux-6.19/bindings
    cp -r ${S}/linux-6.19/Documentation/devicetree/bindings ${D}/${bindir}/linux-6.19/bindings
    dt-mk-schema -j ${D}/${bindir}/linux-6.19/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"
