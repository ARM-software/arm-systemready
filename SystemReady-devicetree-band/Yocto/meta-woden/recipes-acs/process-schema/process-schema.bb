LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.tar.xz"
SRC_URI[sha256sum] = "9106a4605da9e31ff17659d958782b815f9591ab308d03b0ee21aad6c7dced4b"

do_install(){
    install -d ${D}${bindir}/linux-6.18/bindings
    cp -r ${S}/linux-6.18/Documentation/devicetree/bindings ${D}/${bindir}/linux-6.18/bindings
    dt-mk-schema -j ${D}/${bindir}/linux-6.18/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"
