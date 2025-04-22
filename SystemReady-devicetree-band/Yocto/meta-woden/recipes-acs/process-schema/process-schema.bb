LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native "

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.10.tar.xz"
SRC_URI[sha256sum] = "774698422ee54c5f1e704456f37c65c06b51b4e9a8b0866f34580d86fef8e226"

do_install(){
    install -d ${D}${bindir}
    cp -r ${S}/linux-6.10/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"