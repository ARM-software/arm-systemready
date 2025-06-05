# Block device checks

* Integrity‑checks for storage device which can be used as OS boot medium

---

## 1  Overview

The python scripts discovers **all block devices** attached to the system and performs a **read and write check** to verify if a storage device is suitable and reliable for booting, confirming basic read/write integrity and explicitly avoiding critical partitions to prevent accidental system corruption.

* **Read‑Test** – one‑megabyte raw read from each partition (or entire raw disk) to prove basic I/O.
* **Optional Write‑Test** – a single 512‑byte sector is backed up, overwritten with a signed test pattern, read back for SHA‑256 verification, then **restored** byte‑for‑byte.

Critical partitions (e.g., EFI System, BIOS bootloader) are identified using their partition GUIDs and explicitly skipped from read/write operations.

## 2  Key Features

| Safety guard                      | Mechanism                                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Precious‑partition block‑list** | Two extensible dictionaries: `precious_parts_mbr` (MBR type IDs) and `precious_parts_gpt` (GPT GUIDs). |
| **Platform‑required flag** (GPT)  | Reads attribute LSB; if set, partition is skipped.                                                     |
| **Mount detection**               | Uses `findmnt`; mounted partitions are read‑only checked.                                              |
| **Interactive opt‑in**            | Five‑second `yes/no` prompt (default *no*) before any write.                                           |
| **Full sector restoration**       | Backs up the exact sector, writes pattern, verifies hash, restores backup.                             |
| **Shaded coverage**               | Skips `ram*`, `mtdblock*` and any device without a valid table.                                        |

---

## 3  High‑Level Flow

```text
┌── Enumerate disks (lsblk)
│
├─► For each /dev/<disk>
│     ├─ Identify partition table (gdisk)
│     ├─ Get partition labels (lsblk – Unicode‑safe)
│     │
│     ├─ If RAW → treat whole disk like one partition
│     └─ Else iterate partitions
│           ├─ MBR  : read Id via fdisk
│           ├─ GPT  : read GUID & flags via sgdisk
│           │
│           ├─ Skip if precious / platform‑required / mounted
│           ├─ 1 MiB read test  (dd → /dev/null)
│           └─ Optional write test (backup‑write‑verify‑restore)
└── End report
```

---

## 4  Detailed Behaviour

### 4.1 Device Enumeration

```bash
lsblk -e 7 -d          # lists disk‑type devices (filters loop/dm)
```

Each device is probed with `gdisk -l` to classify as **MBR**, **GPT**, or **RAW** (no partition table).

### 4.2 Partition Parsing

* **MBR** – `fdisk -l` lines after the header row yield the *Id* column (hex).
* **GPT** – `sgdisk -i=<n>` outputs the *Partition GUID code* and *attribute flags*.

`get_partition_labels()` calls `lsblk -rn -o NAME,TYPE` to avoid Unicode box‑drawing characters.

### 4.3 Read Test

```bash
dd if=/dev/<partition> bs=1M count=1 of=/dev/null
```

Non‑fatal; a failed read simply logs an `INFO:` message.

### 4.4 Write Test (when permitted)

1. **Space calculation** – `df -B 512` finds `used_blocks`; the script targets *exactly the last used block*.
2. **Backup** – `dd if=/dev/<partition> of=<label>_backup.bin bs=512 count=1 skip=<used_blocks>`
3. **Write** – padded "Hello!" pattern (512 B) written with `seek=<used_blocks>`.
4. **Verify** – read sector back; compare SHA‑256.
5. **Restore** – overwrite sector with backup.

---

## 5  Running the Tool

```bash
sudo python3 read_write_check_blk_devices.py
```

Root privileges (or `CAP_SYS_RAWIO`) are required for raw block access.

---

## 6  Extending / Customising

| Task                  | Edit                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------- |
| Add precious MBR ID   | `precious_parts_mbr["<label>"] = "0xXX"`                                              |
| Add precious GPT GUID | `precious_parts_gpt["<label>"] = "GUID"`                                              |
| Disable prompts (CI)  | Replace the `input_with_timeout()` call with a hard‑coded "no" or gate write‑test in CI with an environment variable (`NON_INTERACTIVE=1`).. |
| Change pattern size   | Adjust `bs=512 count=1` in all `dd` commands *and* update padding logic.              |
| Prompt timeout        | Second argument of `input_with_timeout(prompt, timeout=…)`.                           |

---

## 7  Dependencies

* **GNU coreutils:** `lsblk`, `fdisk`, `gdisk`, `sgdisk`, `dd`, `df`, `findmnt`, `awk`, `timeout`
* **Python std‑lib:** `subprocess`, `hashlib`, `threading`, `re`, `os`
* Works on any modern **GNU/Linux** distribution with those utilities installed.

---

## 8. Limitations

- **Sector Size Assumption (512 bytes):**
  The script assumes standard 512-byte sectors. Adjustment is necessary for drives with larger native sectors (e.g., 4 KiB sectors).

- **No Logical Volume Support:**
  Intentionally excludes logical volumes such as `dm-crypt` or LVM-managed devices.

- **Performance on Large Drives:**
  Backup and restore operations may be slow on drives with capacities of several terabytes or more.

- **External Dependencies:**
  Relies on external binaries (e.g., `lsblk`, `fdisk`, `sgdisk`, `dd`); ensure these utilities are installed, especially in minimal or containerized environments.


## 9  Conclusion

The utility provides an automated and safe method to verify basic read and write integrity of block devices, explicitly skipping firmware partitions to prevent unintended modifications.

--------------
*Copyright (c) 2025, Arm Limited and Contributors. All rights reserved.*
