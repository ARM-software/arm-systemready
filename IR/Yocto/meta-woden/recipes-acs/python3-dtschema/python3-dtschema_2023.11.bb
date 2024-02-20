DESCRIPTION = "Tooling for devicetree validation using YAML and jsonschema"
HOMEPAGE = "https://github.com/devicetree-org/dt-schema"
LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://LICENSE.txt;md5=457495c8fa03540db4a576bf7869e811"

inherit pypi setuptools3

PYPI_PACKAGE = "dtschema"

SRC_URI[sha256sum] = "cf9a449ea743c0a955cf6034ef246668fa5ea177684977c61fef7604af5f273b"

DEPENDS += "python3-setuptools-scm-native"
RDEPENDS:${PN} += "python3-ruamel-yaml python3-jsonschema python3-rfc3987 python3-pylibfdt"

BBCLASSEXTEND = "native nativesdk"

do_configure:prepend() {
cat > ${S}/setup.py <<-EOF
from setuptools import setup

setup(
       name="${PYPI_PACKAGE}",
       version="${PV}",
       license="${LICENSE}",
)
EOF
}