#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.






import argparse
import re
import sys
from pathlib import Path


DEFAULT_DMEM_LOG = Path(
    "/mnt/acs_results_template/"
    "acs_results/uefi_dump/dmem.log"
)

DEFAULT_OUT_LOG_PATH = Path(
    "/mnt/acs_results_template/"
    "acs_results/linux_tools/dtb_alignment_test.log"
)


DMEM_LOG = DEFAULT_DMEM_LOG
OUT_LOG_PATH = DEFAULT_OUT_LOG_PATH

_LOG_FH = None


def read_text_smart(path: Path) -> str:
    """Read UEFI shell output while tolerating common firmware encodings."""
    content = path.read_bytes()

    if content.startswith(b"\xff\xfe") or content.startswith(b"\xfe\xff"):
        return content.decode("utf-16", errors="replace")

    if content.count(b"\x00") > max(16, len(content) // 10):
        try:
            return content.decode("utf-16-le", errors="replace")
        except UnicodeDecodeError:
            return content.decode("utf-16", errors="replace")

    return content.decode("utf-8-sig", errors="replace")


def log(message: str) -> None:
    """Write one message to the DTB alignment test log."""
    global _LOG_FH

    if _LOG_FH is None:
        OUT_LOG_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        _LOG_FH = OUT_LOG_PATH.open(
            "w",
            encoding="utf-8",
            errors="replace",
        )

    _LOG_FH.write(message + "\n")
    _LOG_FH.flush()


def close_log() -> None:
    """Flush and close the DTB alignment test log."""
    global _LOG_FH

    if _LOG_FH is not None:
        _LOG_FH.flush()
        _LOG_FH.close()
        _LOG_FH = None


def report(message: str) -> None:
    """Print a message to console and write it to the log."""
    print(message)
    log(message)


def configure_paths_from_args(args: argparse.Namespace) -> None:
    """Apply CLI path overrides."""
    global DMEM_LOG, OUT_LOG_PATH

    DMEM_LOG = args.dmem_log
    OUT_LOG_PATH = args.out


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check that the DTB address is 8-byte aligned."
    )

    parser.add_argument(
        "--dmem-log",
        "--dmem_log",
        dest="dmem_log",
        type=Path,
        default=DEFAULT_DMEM_LOG,
        help=(
            "Path to the dmem.log input. "
            f"Default: {DEFAULT_DMEM_LOG}"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_LOG_PATH,
        help=(
            "Path to the output log file. "
            f"Default: {DEFAULT_OUT_LOG_PATH}"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """Check the DTB address reported in dmem.log."""
    try:
        report(f"-"*60)
        report("INFO: Starting DTB alignment test")

        if not DMEM_LOG.is_file():
            report(f"ERROR: dmem.log not found: {DMEM_LOG}")
            report("RESULT: FAIL")
            report(
                "REASON: DTB alignment could not be checked "
                "because dmem.log is missing"
            )
            return 1

        content = read_text_smart(DMEM_LOG)

        #
        # Expected dmem output, for example:
        #
        # DTB Table                     00000000FCEAD000
        #
        match = re.search(
            r"^\s*DTB Table\s+(?:0[xX])?([0-9A-Fa-f]+)\s*$",
            content,
            re.MULTILINE,
        )

        if match is None:
            
            report(
                "ERROR: DTB Table entry not found in dmem.log"
            )
            report("RESULT: FAIL")
            return 1

        dtb_address = int(match.group(1), 16)

        report(
            f"INFO: DTB address is 0x{dtb_address:X}"
        )
        report(
            "INFO: Required alignment is 8 bytes"
        )

        if dtb_address == 0:
            
            report("ERROR: DTB address is NULL")
            report("RESULT: FAIL")
            return 1

        if (dtb_address & 0x7) != 0:
            
            report(
                f"ERROR: DTB address 0x{dtb_address:X} "
                "is not 8-byte aligned"
            )
            report("RESULT: FAIL")
            return 1

        
        report(
            f"INFO: DTB address 0x{dtb_address:X} "
            "is 8-byte aligned"
        )
        report("RESULT: PASS")

        return 0

    except Exception as error:
        print(f"ERROR: {error}")

        try:
            log(f"ERROR: {error}")
            
            log(
                "ERROR: Unexpected error while checking DTB alignment"
            )
            log("RESULT: FAIL")
        except Exception as log_error:
            print(f"LOG ERROR: {log_error}")

        return 1

    finally:
        close_log()


if __name__ == "__main__":
    configure_paths_from_args(parse_args())
    sys.exit(main())