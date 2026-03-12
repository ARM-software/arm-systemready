LICENSE = "CLOSED"
PACKAGE_ARCH = "${MACHINE_ARCH}"
inherit deploy
S = "${WORKDIR}"

DEPENDS += "\
    efitools-native \
    help2man-native \
    libfile-slurp-perl-native \
    openssl-native \
    sbsigntool-native \
"

inherit perlnative

do_compile() {

    # Source the configuration file to get KEYS_DIR from systemready-dt-band-source.cfg
    RECIPE_DIR="${FILE_DIRNAME}"
    if [ -z "$RECIPE_DIR" ] && [ -n "$FILE" ]; then
        RECIPE_DIR="$(dirname "$FILE")"
    fi
    CFG_FILE="$RECIPE_DIR/../../../../../common/config/systemready-dt-band-source.cfg"
    echo "INFO: Checking config file at $CFG_FILE"
    if [ -n "$CFG_FILE" ] && [ -f "$CFG_FILE" ]; then
        . "$CFG_FILE"
        if [ -n "$KEYS_DIR" ]; then
            echo "INFO: Sourced KEYS_DIR from config: KEYS_DIR=$KEYS_DIR"
        fi
    fi

    # The user can point to an external KEYS_DIR to provide partner-provided keys.
    # KEYS_DIR can be set in systemready-dt-band-source.cfg or overridden via environment variable.
    # If KEYS_DIR points to an existing external location, use those keys.
    # Otherwise, generate keys in the workdir.
    GEN_DIR="${S}/bbsr-keys"
    ENFORCE_EXTERNAL_KEYS=0

    # Remove trailing slash if present
    KEYS_DIR="${KEYS_DIR%/}"

    # KEYS_DIR must be an absolute path for external partner-provided keys.
    if [ -n "$KEYS_DIR" ] && [ "${KEYS_DIR#/}" = "$KEYS_DIR" ]; then
        echo "WARNING: KEYS_DIR=$KEYS_DIR is not an absolute path; will generate default test keys"
        KEYS_DIR=""
    fi

    # Check if external KEYS_DIR exists and is a valid directory
    if [ -n "$KEYS_DIR" ]; then
        if [ ! -d "$KEYS_DIR" ]; then
            echo "WARNING: KEYS_DIR=$KEYS_DIR does not exist, will generate default test keys"
            KEYS_DIR=""
        else
            echo "INFO: Found KEYS_DIR at $KEYS_DIR, checking for required key files"
            ENFORCE_EXTERNAL_KEYS=1
        fi
    fi

    # Check if all required key files exist in KEYS_DIR
    REQUIRED_FILES="NullPK.auth TestDB1.auth TestDB1.crt TestDB1.der TestDB1.key TestDBX1.auth TestDBX1.crt TestDBX1.der TestDBX1.key TestKEK1.auth TestKEK1.crt TestKEK1.der TestKEK1.key TestPK1.auth TestPK1.crt TestPK1.der TestPK1.key"
    ALL_FILES_PRESENT=1
    MISSING=""

    if [ $ENFORCE_EXTERNAL_KEYS -eq 1 ]; then
        for file in $REQUIRED_FILES; do
            if [ ! -f "$KEYS_DIR/$file" ]; then
                ALL_FILES_PRESENT=0
                MISSING="$MISSING $file"
                echo "WARNING: missing key file: $KEYS_DIR/$file"
            fi
        done
    fi

    if [ $ALL_FILES_PRESENT -eq 1 ] && [ $ENFORCE_EXTERNAL_KEYS -eq 1 ]; then
        echo "do_compile: bbsr-keys: keys already present in KEYS_DIR=$KEYS_DIR"
        # if external directory differs, copy contents into workdir
        if [ "$KEYS_DIR" != "${S}/bbsr-keys" ]; then
            echo "copying existing keys into build directory"
            mkdir -p ${S}/bbsr-keys
            cp -r "$KEYS_DIR"/* ${S}/bbsr-keys/
        fi
        echo "skipping key generation"
        return 0
    fi

    # If external keys were enforced but incomplete, fail the build
    if [ $ENFORCE_EXTERNAL_KEYS -eq 1 ] && [ $ALL_FILES_PRESENT -eq 0 ]; then
        echo "KEYS_DIR not provided or incomplete, please generate required keys"
        bbfatal "ERROR: missing keys in $KEYS_DIR:$MISSING; please provide all required keys or unset KEYS_DIR"
    fi

    # Generate keys in workdir
    echo "Generating default test keys in $GEN_DIR"
    mkdir -p "$GEN_DIR"
    cd "$GEN_DIR"

    # generate TestPK1: DER and signed siglist
    NAME=TestPK1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_PK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c $NAME.crt -k $NAME.key PK $NAME.esl $NAME.auth

    # generate NULLPK.auth to facilitate deletion of PK during development
    NAME=NullPK
    FUTURE_DATE=`date --rfc-3339=date -d "+5 year"`
    cat /dev/null > $NAME.esl
    sign-efi-sig-list -t $FUTURE_DATE -c TestPK1.crt -k TestPK1.key PK $NAME.esl $NAME.auth

    # generate TestKEK1: DER and signed siglist
    NAME=TestKEK1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_KEK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestPK1.crt -k TestPK1.key KEK $NAME.esl $NAME.auth

    # generate TestDB1: DER and signed siglist
    NAME=TestDB1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_DB/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestKEK1.crt -k TestKEK1.key db $NAME.esl $NAME.auth

    # Convert TestDB1 to gpg form and import to gpg toolchain for use in signing grub
    #cat TestDB1.key | PEM2OPENPGP_USAGE_FLAGS=certify,sign pem2openpgp "TestDB1"  > TestDB1.gpgkey
    #gpg --import --allow-secret-key-import TestDB1.gpgkey
    #gpg --export > TestDB1.pubgpg

    # generate TestDBX1: DER and signed siglist
    NAME=TestDBX1
    openssl req -x509 -sha256 -newkey rsa:2048 -subj /CN=TEST_PK/  -keyout $NAME.key -out $NAME.crt -nodes -days 4000
    openssl x509 -outform der -in $NAME.crt -out $NAME.der
    cert-to-efi-sig-list $NAME.crt $NAME.esl
    sign-efi-sig-list -c TestKEK1.crt -k TestKEK1.key dbx $NAME.esl $NAME.auth


}

# no install
do_install[noexec] = "1"

do_deploy() {
   # Copy the files to deploy directory
   KEYS_DIR="${S}/bbsr-keys"
   cp -r $KEYS_DIR ${DEPLOYDIR}/
   echo "Keys deployed ..."
}

addtask deploy after do_install
