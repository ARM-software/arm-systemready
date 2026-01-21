#!/usr/bin/env python3
# Copyright (c) 2026, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Runtime Device Mapping Conflict Checker.

This module validates that DTS (Device Tree Source) and MMIO (Memory-Mapped I/O)
regions do not conflict with UEFI runtime memory map as per EBBR 2.2.0 specification.

The validator:
1. Parses UEFI runtime memory segments (RT_Code, RT_Data, MMIO, MMIO_Port)
   from the UEFI memory map log
2. Parses the Linux device tree and extracts MMIO register regions
3. Performs address translation through device tree "ranges" properties
   to convert device tree addresses to physical addresses
4. Detects any overlaps between UEFI runtime regions and DTS MMIO ranges
5. Reports conflicts if any overlapping regions are detected

The check is critical for EBBR compliance as UEFI runtime services require
exclusive access to runtime regions without interference from OS drivers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PAGE_SIZE = 4096

DTS_PATH = Path("/mnt/acs_results_template/acs_results/linux_tools/device_tree.dts")
MEMMAP_PATH = Path("/mnt/acs_results_template/acs_results/uefi_dump/memmap.log")
OUT_LOG_PATH = Path("/mnt/acs_results_template/acs_results/linux_tools/runtime_device_mapping_conflict_test.log")


# ---------------- Data models ----------------

@dataclass(frozen=True)
class MemSeg:
    seg_type: str
    start: int
    end: int
    pages: int
    size: int
    attributes: int

@dataclass
class Node:
    name: str
    path: str
    parent: Optional["Node"]
    props: Dict[str, str]
    children: List["Node"]

@dataclass(frozen=True)
class DtsRange:
    node_path: str
    base: int
    end: int
    size: int
    translated: bool
    note: str

@dataclass(frozen=True)
class Conflict:
    mem_type: str
    mem_start: int
    mem_end: int
    mem_size: int
    dts_path: str
    dts_base: int
    dts_end: int
    dts_size: int
    dts_note: str

# ---------------- Logging ----------------

_LOG_FH = None

def log(msg: str) -> None:
    """
    Append a message to the test results log file.

    Args:
        msg (str): The message to log.

    The log file is lazily opened on first write and flushed after each
    message to ensure output is captured even if the program crashes.
    """
    global _LOG_FH
    if _LOG_FH is None:
        OUT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOG_FH = OUT_LOG_PATH.open("w", encoding="utf-8", errors="replace")
    _LOG_FH.write(msg + "\n")
    _LOG_FH.flush()

def close_log() -> None:
    """Close and flush the log file handle. Called on program termination."""
    global _LOG_FH
    if _LOG_FH is not None:
        _LOG_FH.close()
        _LOG_FH = None


# ============================================================================
# SECTION: Helper Functions - Address Range & Node Filtering
# ============================================================================

def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Check if two address ranges overlap (inclusive boundaries)."""
    return a_start <= b_end and b_start <= a_end

def node_is_disabled(node: Node) -> bool:
    """Check if a node has status='disabled' property."""
    v = node.props.get("status", "")
    return "disabled" in v.lower()

def is_disabled_in_ancestry(node: Node) -> bool:
    """Recursively check if node or any ancestor in tree is disabled."""
    cur = node
    while cur is not None:
        if node_is_disabled(cur):
            return True
        cur = cur.parent
    return False

def strip_comments(line: str) -> str:
    """Remove C-style block and line comments from DTS source lines."""
    line = re.sub(r"/\*.*?\*/", "", line)
    line = re.sub(r"//.*$", "", line)
    return line.strip()

def to_int(tok: str) -> Optional[int]:
    """Parse integer token in hex (0x prefix) or decimal format."""
    tok = tok.strip()
    if not tok:
        return None
    try:
        if tok.lower().startswith("0x"):
            return int(tok, 16)
        if tok.isdigit():
            return int(tok, 10)
        if re.fullmatch(r"[0-9a-fA-F]+", tok):
            return int(tok, 16)
    except ValueError:
        return None
    return None

def extract_cells_from_angle_list(blob: str) -> List[int]:
    """Extract cell values from <...> angle bracket notation.

    Strictly parses only explicit formats:
    - 0xHEXVAL (hex with 0x prefix)
    - DECIMAL (digits only)

    Excludes ambiguous hex-like strings without 0x prefix to avoid
    silent parsing errors with undefined variables or identifiers.
    """
    toks = re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", blob)
    out: List[int] = []
    for t in toks:
        v = to_int(t)
        if v is not None:
            out.append(v)
    return out

def parse_reg_names(prop: str) -> List[str]:
    """Extract DTS reg-names property value list.

    Handles quoted strings and null-separated values as used in DTS.
    Example: reg-names = "fspi_base\0fspi_mmap"; → ["fspi_base", "fspi_mmap"]
    """
    # Extract quoted strings and split on \0 (DTS uses \0 inside string literals)
    # Example: reg-names = "fspi_base\0fspi_mmap";
    if not prop:
        return []
    m = re.findall(r'"([^"]*)"', prop)
    if not m:
        return []
    joined = "".join(m)
    return [s for s in joined.split("\\0") if s != ""]


def join_u32_cells(cells: List[int]) -> int:
    """Combine multiple 32-bit cell values into single address/value.

    Device tree uses variable-width address/size formats via #address-cells
    and #size-cells properties. This joins multiple 32-bit cells left-shifted.
    Example: [0x1234, 0x5678] → 0x1234_5678 (64-bit address)
    """
    v = 0
    for c in cells:
        v = (v << 32) | (c & 0xFFFFFFFF)
    return v

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


# ---------------- Memmap parsing ----------------

def parse_memmap(memmap_text: str) -> List[MemSeg]:
    """
    Parse UEFI memory map log and extract runtime memory segments.

    Filters for RT_Code, RT_Data, MMIO, and MMIO_Port segments from the
    UEFI memory map. Deduplicates entries and returns sorted list.

    Args:
        memmap_text (str): Raw text from UEFI memory map log file.

    Returns:
        List[MemSeg]: Sorted list of memory segments.
    """
    wanted = {"RT_Code", "RT_Data", "MMIO", "MMIO_Port"}
    uniq: Dict[Tuple[str, int, int], MemSeg] = {}
    skipped_count = 0

    for line_num, raw in enumerate(memmap_text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 4:
            log(f"DEBUG: Skipped malformed memmap line {line_num} (only {len(parts)} fields): {line[:60]}")
            skipped_count += 1
            continue

        seg_type = parts[0]
        if seg_type not in wanted:
            continue

        rng = parts[1]
        if "-" not in rng:
            continue

        start_s, end_s = rng.split("-", 1)
        start = to_int(start_s)
        end   = to_int(end_s)
        pages = to_int(parts[2])
        attr  = to_int(parts[3])

        if None in (start, end, pages, attr):
            continue

        size_by_range = (end - start + 1) if end >= start else 0
        size_by_pages = pages * PAGE_SIZE
        size = size_by_range if size_by_range else size_by_pages

        uniq[(seg_type, start, end)] = MemSeg(seg_type, start, end, pages, size, attr)

    if skipped_count > 0:
        log(f"DEBUG: Skipped {skipped_count} malformed lines from memmap")

    return sorted(uniq.values(), key=lambda x: (x.seg_type, x.start))


# ============================================================================
# SECTION: DTS Parsing - Node & Property Extraction
# ============================================================================

_NODE_OPEN_RE = re.compile(r"""^(?:(?P<label>[A-Za-z_]\w*)\s*:\s*)?(?P<name>[A-Za-z0-9,._+\-@]+)\s*\{.*$""")
_NODE_CLOSE_RE = re.compile(r"^\s*\}\s*;?\s*$")

# IMPORTANT: allow '#' in property names (#address-cells/#size-cells)
_PROP_ASSIGN_RE = re.compile(r"^([#A-Za-z0-9,_\-\.\+]+)\s*=\s*(.*);\s*$")
_PROP_FLAG_RE   = re.compile(r"^([#A-Za-z0-9,_\-\.\+]+)\s*;\s*$")

def parse_dts_tree(dts_text: str) -> Node:
    """
    Parse device tree source into a tree of nodes and properties.

    Handles DTS syntax including node definitions, properties with various
    value formats (<...>, "...", etc.), and nested nodes. Strips comments
    and handles multi-line properties correctly.

    Args:
        dts_text (str): Raw DTS file content.

    Returns:
        Node: Root node of parsed device tree.
    """
    root = Node(name="/", path="/", parent=None, props={}, children=[])
    stack: List[Node] = [root]
    lines = dts_text.splitlines()

    i = 0
    while i < len(lines):
        line = strip_comments(lines[i])
        if not line:
            i += 1
            continue

        mopen = _NODE_OPEN_RE.match(line)
        if mopen:
            name = mopen.group("name")
            parent = stack[-1]
            path = (parent.path.rstrip("/") + "/" + name).replace("//", "/")
            node = Node(name=name, path=path, parent=parent, props={}, children=[])
            parent.children.append(node)
            stack.append(node)
            i += 1
            continue

        if _NODE_CLOSE_RE.match(line):
            if len(stack) > 1:
                stack.pop()
            i += 1
            continue

        mprop = _PROP_ASSIGN_RE.match(line)
        if mprop:
            key = mprop.group(1)
            val = mprop.group(2).strip()

            # multi-line <...> values
            if "<" in val and ">" not in val:
                blob = val
                while i + 1 < len(lines):
                    i += 1
                    nxt = strip_comments(lines[i])
                    blob += " " + nxt
                    if ">" in nxt:
                        break
                val = blob.strip()

            stack[-1].props[key] = val
            i += 1
            continue

        mflag = _PROP_FLAG_RE.match(line)
        if mflag:
            stack[-1].props[mflag.group(1)] = ""
            i += 1
            continue

        i += 1

    return root

def iter_nodes(root: Node) -> List[Node]:
    """Depth-first traversal of device tree, returning all nodes in order."""
    out: List[Node] = []
    st = [root]
    while st:
        n = st.pop()
        out.append(n)
        for c in reversed(n.children):
            st.append(c)
    return out


# ============================================================================
# SECTION: Address Translation - Cell Properties & Ranges Parsing
# ============================================================================

def get_prop_int(node: Node, key: str) -> Optional[int]:
    """Extract single integer value from device tree property."""
    v = node.props.get(key)
    if v is None:
        return None
    cells = extract_cells_from_angle_list(v)
    return cells[0] if cells else None

def inherited_cells(node: Node, key: str, root_default: int) -> int:
    """Get property value from node, or recursively from ancestors.

    Device tree properties like #address-cells and #size-cells are often
    inherited from parent nodes. This walks up the tree to find them.
    Returns root_default if not found anywhere in ancestry.
    """
    cur = node
    while cur is not None:
        v = get_prop_int(cur, key)
        if v is not None and 0 <= v <= 4:
            return v
        cur = cur.parent
    return root_default

def addr_cells(node: Node) -> int:
    """Get #address-cells property for node (inherited from ancestors, default 2)."""
    return inherited_cells(node, "#address-cells", 2)

def size_cells(node: Node) -> int:
    """Get #size-cells property for node (inherited from ancestors, default 2)."""
    return inherited_cells(node, "#size-cells", 2)

def get_bus_ranges(bus: Node) -> Tuple[bool, List[Tuple[int, int, int]]]:
    """Parse device tree 'ranges' property for address translation.

    Returns:
        (present, mappings) tuple where:
        - present: bool indicating if 'ranges' property exists
        - mappings: list of (child_base, parent_base, size) tuples
          - missing ranges => present=False, mappings=[]
          - 'ranges;' (explicit identity) => present=True, mappings=[]
          - 'ranges=<...>' (explicit mapping) => present=True, mappings parsed
    """
    if "ranges" not in bus.props:
        return (False, [])

    val = bus.props.get("ranges", "")
    if val.strip() == "":
        return (True, [])  # explicit identity

    cells = extract_cells_from_angle_list(val)
    if not cells:
        return (True, [])

    child_ac = addr_cells(bus)
    child_sc = size_cells(bus)
    parent = bus.parent
    # If parent is None, use root default address-cells (typically 2)
    parent_ac = addr_cells(parent) if parent is not None else 2

    t = child_ac + parent_ac + child_sc
    if t <= 0 or len(cells) < t:
        return (True, [])

    maps: List[Tuple[int, int, int]] = []
    for off in range(0, len(cells) - t + 1, t):
        c_base = join_u32_cells(cells[off : off + child_ac])
        p_base = join_u32_cells(cells[off + child_ac : off + child_ac + parent_ac])
        sz = join_u32_cells(cells[off + child_ac + parent_ac : off + t])
        if sz:
            maps.append((c_base, p_base, sz))

    return (True, maps)

def translate_up_to_root(addr: int, parent_bus: Node) -> Tuple[Optional[int], str]:
    """Translate device tree address to physical (root) address via ranges.

    Walks up the device tree hierarchy applying 'ranges' translations at each
    level until reaching the root node. Implements strict validation:
      - If ranges present and non-empty => address must match a window
      - If ranges missing or empty => identity (pass-through) translation

    Args:
        addr (int): Device tree address to translate
        parent_bus (Node): Node whose parent bus will be traversed

    Returns:
        (phys_addr, notes): tuple of translated physical address (or None on error)
                           and comma-separated translation notes for debugging
    """
    cur_addr = addr
    bus = parent_bus
    notes: List[str] = []

    while bus is not None:
        if bus.parent is None:
            # Root node - no further translation needed
            break

        present, maps = get_bus_ranges(bus)

        if not present:
            notes.append(f"{bus.path}:ranges-missing->identity")
            bus = bus.parent
            continue

        if not maps:
            notes.append(f"{bus.path}:identity")
            bus = bus.parent
            continue

        mapped = False
        for c_base, p_base, sz in maps:
            # Include the end address (c_base + sz - 1) for inclusive range check
            if c_base <= cur_addr <= (c_base + sz - 1):
                cur_addr = p_base + (cur_addr - c_base)
                notes.append(f"{bus.path}:mapped")
                mapped = True
                break

        if not mapped:
            return (None, f"{bus.path}:no-range-match")

        bus = bus.parent

    return (cur_addr, ",".join(notes) if notes else "no-translation-needed")


# ============================================================================
# SECTION: MMIO Range Extraction - Device Tree Traversal with Translation
# ============================================================================

def is_memory_like(node: Node) -> bool:
    """Check if node represents memory (not MMIO registers).

    Memory nodes should be excluded from MMIO conflict checking as they
    represent system RAM, not device register regions.
    """
    if node.name.startswith("memory@"):
        return True
    if "/reserved-memory" in node.path:
        return True
    dev_type = node.props.get("device_type", "")
    return ("\"memory\"" in dev_type) or ("'memory'" in dev_type)

def extract_dts_mmio_ranges(root: Node) -> List[DtsRange]:
    """Extract MMIO register ranges from device tree with address translation.

    Walks the device tree, finds nodes with "reg" properties (excluding
    memory and reserved-memory nodes), and translates their addresses to
    physical addresses by following "ranges" properties up to the root.

    IMPORTANT: Handles complex DTS patterns like syscon sub-registers where
    child node address is an offset within parent MMIO window. Detects and
    properly translates these cases by walking up to find parent's physical base.

    Args:
        root (Node): Root node of parsed device tree.

    Returns:
        List[DtsRange]: Sorted list of MMIO ranges with physical addresses.
    """
    uniq: Dict[Tuple[str, int, int], DtsRange] = {}

    for n in iter_nodes(root):
        if n is root:
            continue
        if is_memory_like(n):
            continue
        if is_disabled_in_ancestry(n):
            continue
        if "reg" not in n.props:
            continue

        parent_bus = n.parent if n.parent is not None else root
        ac = addr_cells(parent_bus)
        sc = size_cells(parent_bus)
        t = ac + sc

        reg_cells = extract_cells_from_angle_list(n.props.get("reg", ""))
        reg_names = parse_reg_names(n.props.get("reg-names", ""))
        if not reg_cells or len(reg_cells) < t:
            continue

        for off in range(0, len(reg_cells) - t + 1, t):
            child_addr = join_u32_cells(reg_cells[off : off + ac])
            sz = join_u32_cells(reg_cells[off + ac : off + t])
            if not sz:
                continue
            reg_name = reg_names[off // t] if reg_names and (off // t) < len(reg_names) else None
            if reg_name and ('mmap' in reg_name.lower()):
                continue

            phys, note = translate_up_to_root(child_addr, parent_bus)
            if phys is None:
                continue

            # Handle common DTS pattern where a child node's reg address is an offset within
            # the parent's MMIO window (e.g., syscon/efuse sub-registers). If the immediate
            # parent bus has no ranges (identity translation), treat child_addr as offset
            # when it fits inside the parent's reg size.
            if phys == child_addr and "ranges-missing->identity" in note:
                preg = parent_bus.props.get("reg", "")
                preg_cells = extract_cells_from_angle_list(preg)
                pac = addr_cells(parent_bus)
                psc = size_cells(parent_bus)
                pt = pac + psc
                if preg_cells and len(preg_cells) >= pt:
                    p_child_base = join_u32_cells(preg_cells[0:pac])
                    p_sz = join_u32_cells(preg_cells[pac:pt])
                    if p_sz and child_addr < p_sz:
                        # parent reg is expressed in its parent's address space
                        start_bus = parent_bus.parent if parent_bus.parent is not None else parent_bus
                        p_phys, _p_note = translate_up_to_root(p_child_base, start_bus)
                        if p_phys is not None:
                            phys = p_phys + child_addr
                            note = note + ",offset-in-parent-reg"

            end = phys + sz - 1
            r = DtsRange(
                node_path=(n.path + (f"<{reg_name}>" if reg_name else "")),
                base=phys,
                end=end,
                size=sz,
                translated=(note != "no-translation-needed"),
                note=note,
            )
            uniq[(r.node_path, r.base, r.end)] = r

    return sorted(uniq.values(), key=lambda x: (x.base, x.size, x.node_path))


# ============================================================================
# SECTION: Main Entry Point - Orchestration & Reporting
# ============================================================================

def main() -> None:
    """
    Main entry point for runtime device mapping conflict detection.

    Orchestrates:
    1. File validation and reading
    2. UEFI memory map parsing
    3. Device tree parsing and MMIO range extraction
    4. Conflict detection between UEFI regions and DTS MMIO ranges
    5. Test result reporting

    Results are written to the log file with detailed information about
    all checked segments and any detected conflicts.
    """
    log("============================================================")
    log("Testing Runtime Device Mapping Conflict Test")
    log("============================================================")

    log(f"INFO: Using DTS: {DTS_PATH}")
    log(f"INFO: Using memmap: {MEMMAP_PATH}")
    log(f"INFO: Writing log to: {OUT_LOG_PATH}")

    if not DTS_PATH.exists():
        log(f"RESULTS: DTS file not found: {DTS_PATH} - WARNING")
        close_log()
        return
    if not MEMMAP_PATH.exists():
        log(f"RESULTS: Memmap file not found: {MEMMAP_PATH} - WARNING")
        close_log()
        return

    # Read files (memmap often UTF-16LE)
    dts_text = read_text_smart(DTS_PATH)
    mem_text = read_text_smart(MEMMAP_PATH)

    # Parse
    mem_segs = parse_memmap(mem_text)
    root = parse_dts_tree(dts_text)
    dts_regs = extract_dts_mmio_ranges(root)

    # Print ALL UEFI segments checked (without pages/attr)
    log("")
    log("INFO: ============================================================")
    log("INFO: All UEFI Memmap segments CHECKED (RT_Code/RT_Data/MMIO/MMIO_Port)")
    log("INFO: ============================================================")
    if not mem_segs:
        log("INFO: No matching segments found in memmap.")
        # Debug help: show first few lines that start with RT_/MMIO
        dbg = [ln.strip() for ln in mem_text.splitlines()
               if ln.strip().startswith(("RT_", "MMIO"))]
        if dbg:
            log("INFO: Found RT_/MMIO lines in memmap (debug):")
            for ln in dbg[:10]:
                log("INFO: " + ln)
    else:
        log(f"INFO: Total segments checked: {len(mem_segs)}")
        for s in mem_segs:
            log(
                f"INFO: {s.seg_type:9s} "
                f"0x{s.start:016x}-0x{s.end:016x} "
                f"size=0x{s.size:x}"
            )

    # Print ALL DTS MMIO ranges checked
    log("")
    log("INFO: ============================================================")
    log("INFO: All DTS MMIO ranges CHECKED (extracted from reg + ranges translation)")
    log("INFO: ============================================================")
    if not dts_regs:
        log("INFO: No DTS MMIO ranges extracted.")
    else:
        log(f"INFO: Total DTS ranges checked: {len(dts_regs)}")
        for r in dts_regs:
            tag = "T" if r.translated else "-"
            log(
                f"INFO: [{tag}] {r.node_path:60s} "
                f"0x{r.base:016x}-0x{r.end:016x} "
                f"size=0x{r.size:x}"
            )

    # Verify + report conflicts
    conflicts: List[Conflict] = []
    for s in mem_segs:
        for r in dts_regs:
            if overlaps(s.start, s.end, r.base, r.end):
                conflicts.append(
                    Conflict(
                        mem_type=s.seg_type,
                        mem_start=s.start,
                        mem_end=s.end,
                        mem_size=s.size,
                        dts_path=r.node_path,
                        dts_base=r.base,
                        dts_end=r.end,
                        dts_size=r.size,
                        dts_note=r.note,
                    )
                )

    log("")
    log("RESULTS: ============================================================")
    log("RESULTS: Runtime Device Mapping Conflict Test Summary")
    log("RESULTS: ============================================================")

    if not conflicts:
        log("RESULTS: No overlaps found between UEFI runtime regions and DTS MMIO ranges - PASSED")
    else:
        log("RESULTS: Conflicting regions:")
        for c in conflicts:
            log(
                    "RESULTS: "
                    f"UEFI {c.mem_type} 0x{c.mem_start:016x}-0x{c.mem_end:016x} "
                    f"overlaps DTS {c.dts_path} "
                    f"0x{c.dts_base:016x}-0x{c.dts_end:016x} "
                    f"(RT size=0x{c.mem_size:x}, DTS size=0x{c.dts_size:x})"
                    )
        log(f"RESULTS: Detected {len(conflicts)} conflict(s) - WARNING")

    close_log()

if __name__ == "__main__":
    main()
