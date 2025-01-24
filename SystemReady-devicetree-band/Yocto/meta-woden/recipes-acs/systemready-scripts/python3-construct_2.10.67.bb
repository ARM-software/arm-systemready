DESCRIPTION = "Python declarative parser for binary data"
HOMEPAGE = "http://construct.readthedocs.org/en/latest/"
SECTION = "devel/python"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=202b39559c1c79fe4715ce81e9e0ac02"

SRC_URI[md5sum] = "ecc7bf4f083caf634f10241e87e58c75"
SRC_URI[sha256sum] = "730235fedf4f2fee5cfadda1d14b83ef1bf23790fb1cc579073e10f70a050883"

PYPI_PACKAGE = "construct"
inherit pypi setuptools3
RDEPENDS_${PN} += "python3-core python3-six python3-debugger"