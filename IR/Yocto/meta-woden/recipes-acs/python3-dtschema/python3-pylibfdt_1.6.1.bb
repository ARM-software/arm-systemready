SUMMARY = "Python binding for libfdt"
HOMEPAGE = "https://github.com/devicetree-org/pylibfdt"
AUTHOR = "Simon Glass <sjg@chromium.org> <>"
LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://BSD-2-Clause;md5=5d6306d1b08f8df623178dfd81880927"

inherit pypi setuptools3

PYPI_PACKAGE = "pylibfdt"

SRC_URI[sha256sum] = "90c667c5adf44c6ab2f13bdc566598897784c7b781bed91064e7373bd270b778"

S = "${WORKDIR}/pylibfdt-1.6.1"

DEPENDS += "python3-setuptools-scm-native swig-native"
RDEPENDS_${PN} = ""

BBCLASSEXTEND = "native nativesdk"
