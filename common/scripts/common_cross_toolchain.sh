#!/usr/bin/env bash

check_arch() {
	if [[ ! ${ARCH+x} ]]; then
		# ARCH are not set
		if [[ ! ${CROSS_COMPILE+x} ]]; then
			# ARCH and CROSS_COMPILE are not set, we set ARCH to arm64 by default
			export ARCH=arm64
		else
			export ARCH=arm64
			if [ $(echo $CROSS_COMPILE | grep 'gnueabi' | grep -q arm) ]; then
				# CROSS_COMPILE are set with arm toolchain (arm 32bits)
				export ARCH=arm
			fi
		fi
	fi
}

dump_cross_toolchain() {
	# print ARCH
	echo "TOOLCHAIN information:"
	echo "    ARCH=$ARCH"
	if [[ ${GCC+x} ]]; then
		echo "    GCC=$GCC"
	fi
	if [[ ${CROSS_COMPILE+x} ]]; then
		echo "    CROSS_COMPILE=$CROSS_COMPILE"
	fi
}

set_toolchain() {
	# to set the toolchain parameter, we nned to have the ARCH defined
	case $ARCH in
	arm)
		if [[ ! ${CROSS_COMPILE+x} ]]; then
			GCC=tools/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-
			CROSS_COMPILE=$TOP_DIR/$GCC
			CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
			PATH="$PATH:$CROSS_COMPILE_DIR"
		fi
		export ARCH CROSS_COMPILE
		;;
	arm64)
		if [[ ! ${CROSS_COMPILE+x} ]]; then
			GCC=tools/gcc-linaro-${LINARO_TOOLS_VERSION}-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-
			CROSS_COMPILE=$TOP_DIR/$GCC
			CROSS_COMPILE_DIR=$(dirname $CROSS_COMPILE)
			PATH="$PATH:$CROSS_COMPILE_DIR"
		fi
		export ARCH CROSS_COMPILE
		;;
	aarch64)
		# arm64 native build
		;;
	esac
}


check_arch
set_toolchain
#dump_cross_toolchain
