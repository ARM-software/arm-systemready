# Append fwts source URI and version to the SystemReady commit log
SYSTEMREADY_COMMIT_LOG ?= "${TOPDIR}/../recipes-acs/bootfs-files/files/systemready-commit.log"

# Compute first non-file SRC_URI at parse time to avoid shell parsing issues
FWTS_LOG_SRC_URI ?= "${@next((u for u in (d.getVar('SRC_URI') or '').split() if not u.startswith('file://')), '')}"

do_compile:append() {
    echo "fwts" >> "${SYSTEMREADY_COMMIT_LOG}"
    if [ -n "${FWTS_LOG_SRC_URI}" ]; then
        echo "    SRC_URI(fwts) = ${FWTS_LOG_SRC_URI}" >> "${SYSTEMREADY_COMMIT_LOG}"
    fi
    echo "    version(fwts) = ${PV}" >> "${SYSTEMREADY_COMMIT_LOG}"
    echo "" >> "${SYSTEMREADY_COMMIT_LOG}"
}
