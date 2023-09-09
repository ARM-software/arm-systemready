DESCRIPTION = "Tooling for devicetree validation using YAML and jsonschema"
HOMEPAGE = "https://github.com/kyrus/python-junit-xml"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE.txt;md5=0ec4326265b988497f17c3bf20d2898c"
inherit pypi setuptools3
SRC_URI[sha256sum] = "de16a051990d4e25a3982b2dd9e89d671067548718866416faec14d9de56db9f"

PYPI_PACKAGE = "junit-xml"

DEPENDS += "python3-setuptools-scm-native"

BBCLASSEXTEND = "native nativesdk"