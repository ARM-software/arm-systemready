# Matplotlib expects a vendored qhull tree in ${S}/build during build_ext.
# The unpacked auxiliary source is not present anymore by do_compile time in
# this environment, so restore it from DL_DIR before invoking setup.py.
do_compile:prepend() {
    if [ ! -d ${S}/build/qhull-2020.2 ]; then
        mkdir -p ${S}/build
        tar -xzf ${DL_DIR}/qhull-2020-src-8.0.2.tgz -C ${S}/build
    fi
}
