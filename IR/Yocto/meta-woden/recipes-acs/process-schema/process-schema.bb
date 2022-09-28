LICENSE = "CLOSED"

S = "${WORKDIR}"

DEPENDS = "python3-native python3-dtschema-native"

do_install(){
    install -d ${D}${bindir}
    #Download 5.19 code
    wget https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.19.10.tar.xz 
    tar -xf ${S}/linux-5.19.10.tar.xz
    cp -r linux-5.19.10/Documentation/devicetree/bindings ${D}/${bindir}/
    dt-mk-schema -j ${D}/${bindir}/bindings > processed_schema.json
    cp -r ${S}/processed_schema.json ${D}/${bindir}/
}

FILES:${PN} += "${bindir}/*"

