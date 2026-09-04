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

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

try:
    import libfdt
except ImportError as error:
    libfdt = None
    LIBFDT_IMPORT_ERROR = error
else:
    LIBFDT_IMPORT_ERROR = None

#Improve failure reporting so each failure says which node or Memory Reservation Block entry failed, the expected type, and the uncovered or mismatched memmap ranges.

DEFAULT_MEMMAP_PATH = Path(
    "/mnt/acs_results_template/"
    "acs_results/uefi_dump/memmap.log"
)

DEFAULT_DTB_PATH = Path(
    "/mnt/acs_results_template/"
    "acs_results/uefi/BsaDevTree.dtb"
)

DEFAULT_OUT_LOG_PATH = Path(
    "/mnt/acs_results_template/acs_results/linux_tools/"
    "reserved_memory_map_test.log"
)

MEMMAP_PATH = DEFAULT_MEMMAP_PATH
DTB_PATH = DEFAULT_DTB_PATH
OUT_LOG_PATH = DEFAULT_OUT_LOG_PATH


@dataclass(frozen=True)
class MemSeg:
    memory_type: str
    start: int
    end: int


@dataclass(frozen=True)
class ReservedRange:
    node_name: str
    start: int
    end: int
    size: int
    expected_type: str


_LOG_FH = None


def log(message: str) -> None:
    """Append one message to the reserved-memory test log."""
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
    """Flush and close the test log."""
    global _LOG_FH

    if _LOG_FH is not None:
        _LOG_FH.flush()
        _LOG_FH.close()
        _LOG_FH = None


def read_text_smart(p: Path) -> str:
    """Smart encoding detection for text files.

    Automatically detects UTF-8, UTF-16LE, UTF-16BE, or UTF-16 encoding
    based on BOM markers and null-byte frequency patterns. Falls back to
    UTF-8 with error replacement for maximum robustness.

    IMPORTANT: Memmap files from UEFI firmware are often UTF-16LE encoded,
    while DTS files are typically UTF-8. This function handles both.
    """
    b = p.read_bytes()

    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        return b.decode("utf-16", errors="replace")

    if b.count(b"\x00") > max(16, len(b) // 10):
        try:
            return b.decode("utf-16-le", errors="replace")
        except (UnicodeDecodeError, Exception):
            return b.decode("utf-16", errors="replace")

    return b.decode("utf-8", errors="replace")


def to_int(token: str) -> int | None:
    """Convert a UEFI memmap hexadecimal address into an integer."""
    token = token.strip()

    if not token:
        return None

    if token.lower().startswith("0x"):
        token = token[2:]

    try:
        return int(token, 16)
    except ValueError:
        return None


def join_cells(cells: list[int]) -> int:
    """Combine big-endian 32-bit Devicetree cells."""
    value = 0

    for cell in cells:
        value = (value << 32) | (cell & 0xFFFFFFFF)

    return value


def iter_subnodes(
    fdt: libfdt.Fdt,
    parent_offset: int,
) -> Iterator[int]:
    """Yield all direct child-node offsets."""
    child_offset = fdt.first_subnode(
        parent_offset,
        quiet=libfdt.QUIET_NOTFOUND,
    )

    while child_offset >= 0:
        yield child_offset

        child_offset = fdt.next_subnode(
            child_offset,
            quiet=libfdt.QUIET_NOTFOUND,
        )


def get_prop_or_none(
    fdt: libfdt.Fdt,
    node_offset: int,
    prop_name: str,
):
    """Return a property object if present, otherwise None.

    The Python libfdt binding does not expose `hasprop()`, so presence checks
    must be performed by attempting `getprop()`.
    """
    try:
        return fdt.getprop(node_offset, prop_name)
    except libfdt.FdtException:
        return None


def get_mem_rsv_entry(
    fdt: libfdt.Fdt,
    index: int,
) -> tuple[int, int]:
    """Read one Memory Reservation Block entry from the Python binding.

    Different libfdt Python bindings may return either:
    - (address, size)
    - (status, address, size)

    Normalize both forms here.
    """
    entry = fdt.get_mem_rsv(index)

    if isinstance(entry, (tuple, list)):
        if len(entry) == 2:
            start, size = entry
            return int(start), int(size)

        if len(entry) == 3:
            status, start, size = entry
            if status not in (0, None):
                raise ValueError(
                    f"Memory Reservation Block entry {index} "
                    f"returned libfdt status {status}"
                )
            return int(start), int(size)

    raise ValueError(
        f"Unexpected get_mem_rsv({index}) return value: {entry!r}"
    )


def parse_memmap(memmap_text: str) -> list[MemSeg]:
    """Extract Reserved and BS_Data ranges from a UEFI memmap log."""
    wanted = {
        "Reserved",
        "BS_Data",
    }

    uniq: dict[tuple[str, int, int], MemSeg] = {}
    skipped_count = 0

    for line_num, raw_line in enumerate(
        memmap_text.splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        parts = line.split()

        # We only need:
        # parts[0] = memory type
        # parts[1] = start-end range
        if len(parts) < 2:
            continue

        memory_type = parts[0]

        # Ignore headings and unrelated memory types.
        if memory_type not in wanted:
            continue

        range_text = parts[1]

        if "-" not in range_text:
            log(
                "INFO: Skipped malformed relevant memmap line "
                f"{line_num}: {line[:80]}"
            )
            skipped_count += 1
            continue

        start_text, end_text = range_text.split("-", maxsplit=1)

        start = to_int(start_text)
        end = to_int(end_text)

        if start is None or end is None:
            log(
                "INFO: Skipped memmap line with invalid address "
                f"at line {line_num}: {line[:80]}"
            )
            skipped_count += 1
            continue

        if end < start:
            log(
                "INFO: Skipped memmap line with reversed range "
                f"at line {line_num}: {line[:80]}"
            )
            skipped_count += 1
            continue

        key = (memory_type, start, end)

        uniq[key] = MemSeg(
            memory_type=memory_type,
            start=start,
            end=end,
        )

    if skipped_count > 0:
        log(
            f"INFO: Skipped {skipped_count} malformed "
            "relevant lines from memmap"
        )

    return sorted(
        uniq.values(),
        key=lambda segment: (
            segment.start,
            segment.end,
            segment.memory_type,
        ),
    )


def extract_reserved_ranges(
    dtb_path: Path,
) -> list[ReservedRange]:
    """Extract fixed /reserved-memory ranges from a raw DTB.

    Static regions with a reg property are returned for UEFI memmap
    validation. Dynamic regions with a size property but no fixed reg
    address are skipped because there is no fixed physical range to
    compare.
    """
    if libfdt is None:
        raise RuntimeError(
            "libfdt is not available. Install python3-pylibfdt "
            "or run this checker in the DT ACS image."
        ) from LIBFDT_IMPORT_ERROR

    if not dtb_path.is_file():
        raise FileNotFoundError(
            f"DTB not found: {dtb_path}"
        )

    blob = dtb_path.read_bytes()

    if not blob:
        raise ValueError(
            f"DTB is empty: {dtb_path}"
        )

    try:
        fdt = libfdt.Fdt(blob)
    except libfdt.FdtException as error:
        raise ValueError(
            f"Invalid DTB at {dtb_path}: {error}"
        ) from error

    reserved_offset = fdt.path_offset(
        "/reserved-memory",
        quiet=libfdt.QUIET_NOTFOUND,
    )

    if reserved_offset < 0:
        return []

    try:
        address_cells = fdt.getprop(
            reserved_offset,
            "#address-cells",
        ).as_uint32()

        size_cells = fdt.getprop(
            reserved_offset,
            "#size-cells",
        ).as_uint32()

    except (libfdt.FdtException, ValueError) as error:
        raise ValueError(
            "/reserved-memory has missing or malformed "
            "#address-cells/#size-cells properties"
        ) from error

    if address_cells <= 0:
        raise ValueError(
            "/reserved-memory has invalid #address-cells: "
            f"{address_cells}"
        )

    if size_cells <= 0:
        raise ValueError(
            "/reserved-memory has invalid #size-cells: "
            f"{size_cells}"
        )

    cells_per_tuple = address_cells + size_cells
    results: list[ReservedRange] = []

    for child_offset in iter_subnodes(
        fdt,
        reserved_offset,
    ):
        node_name = fdt.get_name(child_offset)

        #
        # Only available reserved-memory nodes are considered.
        #
        # No status property means the node is available.
        # "okay" and "ok" are also treated as available.
        # Other values such as disabled, reserved, fail,
        # or fail-* are skipped.
        #
        status_prop = get_prop_or_none(
            fdt,
            child_offset,
            "status",
        )

        if status_prop is not None:
            try:
                status = status_prop.as_str()
            except ValueError as error:
                raise ValueError(
                    f"{node_name}: malformed status property"
                ) from error

            if status.casefold() not in ("okay", "ok"):
                log(
                    f"INFO: Skipping {node_name} because "
                    f"status is '{status}'"
                )
                continue

        #
        # Static reserved-memory regions have a fixed reg property.
        #
        # Dynamic reserved-memory regions normally provide a size
        # property but no reg property because the address is allocated
        # dynamically. Since there is no fixed physical address in the
        # DTB, those regions cannot be compared directly with memmap.
        #
        reg_prop = get_prop_or_none(
            fdt,
            child_offset,
            "reg",
        )

        size_prop = get_prop_or_none(
            fdt,
            child_offset,
            "size",
        )

        if reg_prop is None:
            if size_prop is not None:
                log(
                    f"INFO: Skipping dynamic reserved-memory node "
                    f"{node_name}: size is present but no fixed "
                    "reg address is available"
                )
            else:
                log(
                    f"INFO: Skipping reserved-memory node "
                    f"{node_name}: no reg property is present"
                )

            continue

        #
        # no-map regions must appear as EfiReservedMemoryType,
        # shown as "Reserved" in the UEFI shell memmap.
        #
        # Other static reserved-memory regions must appear as
        # EfiBootServicesData, shown as "BS_Data".
        #
        expected_type = (
            "Reserved"
            if get_prop_or_none(
                fdt,
                child_offset,
                "no-map",
            ) is not None
            else "BS_Data"
        )

        reg_bytes = bytes(reg_prop)

        if not reg_bytes:
            raise ValueError(
                f"{node_name}: reg property is empty"
            )

        if len(reg_bytes) % 4 != 0:
            raise ValueError(
                f"{node_name}: malformed reg property; "
                "length is not a multiple of 4 bytes"
            )

        reg_cells = [
            int.from_bytes(
                reg_bytes[offset:offset + 4],
                byteorder="big",
            )
            for offset in range(0, len(reg_bytes), 4)
        ]

        if len(reg_cells) % cells_per_tuple != 0:
            raise ValueError(
                f"{node_name}: malformed reg property; "
                f"found {len(reg_cells)} cells, but each tuple "
                f"requires {cells_per_tuple}"
            )

        #
        # A reg property may contain multiple address/size tuples.
        # Validate each fixed range independently.
        #
        for offset in range(
            0,
            len(reg_cells),
            cells_per_tuple,
        ):
            address_end = offset + address_cells
            tuple_end = address_end + size_cells

            start = join_cells(
                reg_cells[offset:address_end]
            )

            size = join_cells(
                reg_cells[address_end:tuple_end]
            )

            if size == 0:
                log(
                    f"INFO: Skipping zero-sized range in "
                    f"{node_name}"
                )
                continue

            end = start + size - 1

            results.append(
                ReservedRange(
                    node_name=node_name,
                    start=start,
                    end=end,
                    size=size,
                    expected_type=expected_type,
                )
            )

    return sorted(
        results,
        key=lambda region: (
            region.start,
            region.end,
            region.node_name,
        ),
    )


def extract_memory_reservation_ranges(
    dtb_path: Path,
) -> list[ReservedRange]:
    """Extract all ranges from the DTB Memory Reservation Block."""
    if libfdt is None:
        raise RuntimeError(
            "libfdt is not available. Install python3-pylibfdt "
            "or run this checker in the DT ACS image."
        ) from LIBFDT_IMPORT_ERROR

    results: list[ReservedRange] = []

    if not dtb_path.is_file():
        raise FileNotFoundError(
            f"DTB not found: {dtb_path}"
        )

    blob = dtb_path.read_bytes()

    if not blob:
        raise ValueError(
            f"DTB is empty: {dtb_path}"
        )

    try:
        fdt = libfdt.Fdt(blob)
    except libfdt.FdtException as error:
        raise ValueError(
            f"Invalid DTB at {dtb_path}: {error}"
        ) from error

    entry_count = fdt.num_mem_rsv()

    for index in range(entry_count):
        start, size = get_mem_rsv_entry(
            fdt,
            index,
        )

        if size == 0:
            log(
                "INFO: Skipping zero-sized Memory Reservation "
                f"Block entry {index}"
            )
            continue

        end = start + size - 1

        results.append(
            ReservedRange(
                node_name=(
                    f"Memory Reservation Block entry {index}"
                ),
                start=start,
                end=end,
                size=size,
                expected_type="Reserved",
            )
        )

    return results


def mem_map_check(
    dtb_range: tuple[int, int],
    memmap_res_list: list[MemSeg],
    expected_type: str,
) -> bool:
    """Check whether the DT range is fully covered by the expected type."""

    if expected_type not in ("Reserved", "BS_Data"):
        raise ValueError(
            f"Unsupported memory type: {expected_type!r}"
        )

    dtb_start, dtb_end = dtb_range

    if dtb_end < dtb_start:
        return False

    matching_segments = sorted(
        (
            segment
            for segment in memmap_res_list
            if segment.memory_type == expected_type
        ),
        key=lambda segment: (
            segment.start,
            segment.end,
        ),
    )

    cursor = dtb_start

    for segment in matching_segments:
        # This segment is entirely before the uncovered part.
        if segment.end < cursor:
            continue

        # A gap exists between the cursor and this segment.
        if segment.start > cursor:
            return False

        # This segment covers the cursor. Advance past its end.
        cursor = max(cursor, segment.end + 1)

        # Every byte of the DT range is now covered.
        if cursor > dtb_end:
            return True

    return False


def parse_args() -> argparse.Namespace:
    """Parse optional CLI overrides for manual and fixture testing."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that reserved-memory regions and Memory Reservation "
            "Block entries are represented correctly in a UEFI memmap log."
        )
    )

    parser.add_argument(
        "--memmap",
        type=Path,
        default=DEFAULT_MEMMAP_PATH,
        help=(
            "Path to the memmap.log input. "
            f"Default: {DEFAULT_MEMMAP_PATH}"
        ),
    )

    parser.add_argument(
        "--dtb",
        type=Path,
        default=DEFAULT_DTB_PATH,
        help=(
            "Path to the DTB input. "
            f"Default: {DEFAULT_DTB_PATH}"
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


def configure_paths_from_args(args: argparse.Namespace) -> None:
    """Apply CLI path overrides while preserving current defaults."""
    global MEMMAP_PATH, DTB_PATH, OUT_LOG_PATH

    MEMMAP_PATH = args.memmap
    DTB_PATH = args.dtb
    OUT_LOG_PATH = args.out


def main() -> None:
    """Check reserved-memory ranges against the UEFI memory map."""
    reserved_failures = 0
    mrb_failures = 0

    try:
        log("=" * 60)
        log("Testing Devicetree Reserved Memory Map Compliance Test")
        log("=" * 60)

        log(f"INFO: Using DTB: {DTB_PATH}")
        log(f"INFO: Using memmap: {MEMMAP_PATH}")
        log(f"INFO: Writing log to: {OUT_LOG_PATH}")

        #
        # Validate required input files.
        #
        if not MEMMAP_PATH.is_file():
            log(f"DEBUG: Memmap file not found: {MEMMAP_PATH}")
            log("RESULTS: WARNINGS")
            return

        if not DTB_PATH.is_file():
            log(f"DEBUG: DTB file not found: {DTB_PATH}")
            log("RESULTS: WARNINGS")
            return

        #
        # Read and parse UEFI memory map.
        #
        memmap_text = read_text_smart(MEMMAP_PATH)
        memmap_segments = parse_memmap(memmap_text)

        #
        # Extract DT ranges before deciding whether an empty
        # relevant UEFI memory map is a failure or not.
        #
        reserved_ranges = extract_reserved_ranges(DTB_PATH)

        memory_reservation_ranges = (
            extract_memory_reservation_ranges(DTB_PATH)
        )

        if not memmap_segments:
            log(
                "DEBUG: No Reserved or BS_Data segments "
                "could be parsed from the UEFI memory map"
            )

            if reserved_ranges or memory_reservation_ranges:
                log(
                    "ERROR: Applicable reserved-memory or "
                    "Memory Reservation Block ranges are present "
                    "in the DTB, but no matching Reserved or "
                    "BS_Data descriptors were found in the "
                    "UEFI memory map"
                )
                log("RESULTS: FAILED")
            else:
                log(
                    "INFO: No applicable reserved-memory or "
                    "Memory Reservation Block ranges were found"
                )
                log("RESULTS: SKIPPED")

            return

        #
        # Check /reserved-memory ranges.
        #
        log("")
        log("INFO: Checking /reserved-memory ranges")

        if not reserved_ranges:
            log(
                "INFO: No static /reserved-memory ranges "
                "requiring validation were found"
            )

        for reserved in reserved_ranges:
            dtb_range = (
                reserved.start,
                reserved.end,
            )

            is_covered = mem_map_check(
                dtb_range,
                memmap_segments,
                reserved.expected_type,
            )

            if not is_covered:
                reserved_failures += 1

                log(
                    f"ERROR: Reserved-memory range "
                    f"{reserved.node_name} "
                    f"({reserved.start:#x}-{reserved.end:#x}) "
                    f"is not fully covered by "
                    f"{reserved.expected_type} segments in memmap."
                )

            else:
                log(
                    f"INFO: Reserved-memory range "
                    f"{reserved.node_name} "
                    f"({reserved.start:#x}-{reserved.end:#x}) "
                    f"is fully covered by "
                    f"{reserved.expected_type} segments in memmap."
                )

        #
        # Report /reserved-memory requirement result.
        #
        if reserved_failures == 0:
            if not reserved_ranges:
                log(
                    "INFO: Reserved Memory Map Compliance Test: "
                    "SKIPPED (no /reserved-memory ranges present)"
                )
            else:
                log(
                    "INFO: Reserved Memory Map Compliance Test: PASSED"
                )
        else:
            log(
                "INFO: Reserved Memory Map Compliance Test: FAILED"
            )

        #
        # Check Memory Reservation Block ranges.
        #
        log("")
        log("INFO: Checking Memory Reservation Block entries")
        skip_mrb=0

        if not memory_reservation_ranges:
            log(
                "INFO: Memory Reservation Block entries are not "
                "present in this DTB; no MRB ranges require "
                "validation"
            )
            skip_mrb=1

        for reservation in memory_reservation_ranges:
            dtb_range = (
                reservation.start,
                reservation.end,
            )

            is_covered = mem_map_check(
                dtb_range,
                memmap_segments,
                "Reserved",
            )

            if not is_covered:
                mrb_failures += 1

                log(
                    f"ERROR: {reservation.node_name} "
                    f"({reservation.start:#x}-"
                    f"{reservation.end:#x}) "
                    "is not fully covered by Reserved "
                    "segments in memmap."
                )

            else:
                log(
                    f"INFO: {reservation.node_name} "
                    f"({reservation.start:#x}-"
                    f"{reservation.end:#x}) "
                    "is fully covered by Reserved "
                    "segments in memmap."
                )

        #
        # Report Memory Reservation Block requirement result.
        #
        if mrb_failures == 0:
            if not memory_reservation_ranges:
                log(
                    "INFO: Memory Reservation Block "
                    "Compliance Test: SKIPPED "
                    "(no MRB entries present)"
                )
            else:
                log(
                    "INFO: Memory Reservation Block "
                    "Compliance Test: PASSED"
                )
        else:
            log(
                "INFO: Memory Reservation Block "
                "Compliance Test: FAILED"
            )

        #
        # Final test summary.
        #
        log("")
        log("=" * 60)
        log("Devicetree Reserved Memory Map Test Summary")
        log("=" * 60)

        log(
            "INFO: /reserved-memory ranges checked: "
            f"{len(reserved_ranges)}"
        )

        log(
            "INFO: Memory Reservation Block entries checked: "
            f"{len(memory_reservation_ranges)}"
        )

        log(
            "INFO: /reserved-memory failures: "
            f"{reserved_failures}"
        )

        log(
            "INFO: Memory Reservation Block failures: "
            f"{mrb_failures}"
        )

        #
        # One final ACS result line.
        #
        if reserved_failures or mrb_failures:
            log("RESULTS: FAILED")
        else:
            if not reserved_ranges and not memory_reservation_ranges:
                log("RESULTS: SKIPPED")
            else:
                log("RESULTS: PASSED")

    except Exception as error:
        log(f"ERROR: {error}")
        log("RESULTS: FAILED")

    finally:
        close_log()


if __name__ == "__main__":
    configure_paths_from_args(parse_args())
    main()