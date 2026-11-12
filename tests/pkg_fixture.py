# SPDX-License-Identifier: GPL-2.0-or-later
"""Tiny synthetic PKG metadata fixture; contains no game data or keys."""
import struct
from pathlib import Path


def sfo_data(values: dict) -> bytes:
    keys = bytearray()
    payloads = bytearray()
    entries = bytearray()
    for key, value in values.items():
        key_index = len(keys)
        keys += key.encode() + b'\0'
        data = value.encode() + b'\0'
        entries += struct.pack('<HHIII', key_index, 0x204, len(data), len(data), len(payloads))
        payloads += data
    key_offset = 20 + len(entries)
    data_offset = key_offset + len(keys)
    return struct.pack('<5I', 0x46535000, 0x101, key_offset, data_offset, len(values)) + entries + keys + payloads


def metadata_pkg(path: Path, **overrides):
    values = {'TITLE_ID': 'CUSA12345', 'CATEGORY': 'gd', 'APP_VER': '01.00'}
    values.update(overrides)
    sfo = sfo_data(values)
    names = b'\0param.sfo\0'
    header = bytearray(0x1000)
    header[:4] = b'\x7fCNT'
    struct.pack_into('>I', header, 0x10, 2)
    struct.pack_into('>I', header, 0x18, 0x1000)
    content_id = b'XX0000-CUSA12345_00-TESTPKG0000000000'
    header[0x40:0x40 + len(content_id)] = content_id
    table = struct.pack('>6I8x', 0x200, 0, 0, 0, 0x1040, len(names))
    table += struct.pack('>6I8x', 0x1000, 1, 0, 0, 0x1040 + len(names), len(sfo))
    path.write_bytes(header + table + names + sfo)
    return path
