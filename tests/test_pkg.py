# SPDX-License-Identifier: GPL-2.0-or-later
"""Regression tests for complete directory extents and safe extraction.

Run with: python3 -m unittest discover -s tests -v
"""
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from pkg_crypto import inflate_block
from pkg_full import BLOCK_SIZE, INODE_SIZE, FullPKG, directory_entries, safe_target
from pkgextract import main


def dirent(ino, kind, name):
    encoded = name.encode()
    size = (16 + len(encoded) + 1 + 7) & ~7
    return struct.pack('<4I', ino, kind, len(encoded), size) + encoded + bytes(size - 16 - len(encoded))


def directory(*entries):
    data = b''.join(dirent(*entry) for entry in entries)
    return data + bytes(BLOCK_SIZE - len(data))


def fake_package():
    """Two-block child directory whose continuation does not start with dots."""
    pkg = FullPKG.__new__(FullPKG)
    pkg._index = None
    pkg.entries = []
    header = bytearray(BLOCK_SIZE)
    struct.pack_into('<I', header, 0x30, 7)
    nodes = bytearray(BLOCK_SIZE)
    records = [
        (0x4000, BLOCK_SIZE, 1, 3),
        (0x8000, 0, 0, 0),  # internal flat_path_table
        (0x4000, BLOCK_SIZE, 1, 7),
        (0x4000, 2 * BLOCK_SIZE, 2, 4),
        (0x8000, 4, 1, 8),
        (0x8000, 5, 1, 9),
        (0x8000, 6, 1, 10),
    ]
    for i, (mode, size, count, location) in enumerate(records):
        struct.pack_into('<H', nodes, i * INODE_SIZE, mode)
        struct.pack_into('<Q', nodes, i * INODE_SIZE + 8, size)
        struct.pack_into('<II', nodes, i * INODE_SIZE + 0x60, count, location)
    blocks = {
        0: bytes(header), 1: bytes(nodes),
        3: directory((1, 2, 'flat_path_table'), (2, 3, 'uroot')),
        4: directory((3, 4, '.'), (2, 5, '..'), (5, 2, 'first.bin')),
        5: directory((6, 2, 'continuation.bin')),
        7: directory((2, 4, '.'), (2, 5, '..'), (3, 3, 'nested'), (4, 2, 'root.bin')),
        8: b'root' + bytes(BLOCK_SIZE - 4),
        9: b'first' + bytes(BLOCK_SIZE - 5),
        10: b'second' + bytes(BLOCK_SIZE - 6),
    }
    pkg._load_pfs = lambda progress=None: (tuple(range(12)),)
    pkg._block = lambda index: blocks[index]
    return pkg, blocks


class PFSTests(unittest.TestCase):
    def test_reads_continuation_and_out_of_order_directories(self):
        pkg, _ = fake_package()
        files = pkg.game_files()
        self.assertEqual({f.name for f in files}, {'root.bin', 'nested/first.bin', 'nested/continuation.bin'})
        self.assertEqual(pkg.verify(), (3, 15))

    def test_extracts_every_file_with_monotonic_progress(self):
        pkg, _ = fake_package()
        events = []
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pkg.extract(root, lambda value, total, message: events.append(value))
            self.assertEqual((root / 'nested/continuation.bin').read_bytes(), b'second')
            self.assertEqual((root / 'nested/first.bin').read_bytes(), b'first')
            self.assertEqual((root / 'root.bin').read_bytes(), b'root')
            self.assertFalse(list(root.rglob('*.part')))
        self.assertEqual(events, sorted(events))
        self.assertEqual(events[-1], 1000)

    def test_rejects_unlinked_inodes(self):
        pkg, blocks = fake_package()
        blocks[5] = bytes(BLOCK_SIZE)
        with self.assertRaisesRegex(ValueError, 'incompleto'):
            pkg.game_files()

    def test_rejects_directory_cycles(self):
        pkg, blocks = fake_package()
        blocks[5] = directory((3, 3, 'cycle'))
        with self.assertRaisesRegex(ValueError, 'cíclico'):
            pkg.game_files()

    def test_rejects_parent_traversal_before_writing(self):
        pkg, blocks = fake_package()
        blocks[5] = directory((6, 2, '..'))
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'output'
            with self.assertRaises(ValueError):
                pkg.extract(output)
            self.assertFalse(output.exists())

    def test_failed_file_preserves_existing_file(self):
        pkg, _ = fake_package()
        pkg.game_files()
        def fail(item):
            yield b'incomplete'
            raise ValueError('damaged block')
        pkg._file_chunks = fail
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'root.bin').write_bytes(b'original')
            with self.assertRaisesRegex(ValueError, 'damaged block'):
                pkg.extract(root)
            self.assertEqual((root / 'root.bin').read_bytes(), b'original')
            self.assertFalse(list(root.rglob('*.part')))

    def test_rejects_symlink_outside_destination(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'root'
            root.mkdir()
            (root / 'escape').symlink_to(Path(d), target_is_directory=True)
            with self.assertRaises(ValueError):
                safe_target(root, 'escape/file.bin')

    def test_rejects_malformed_dirent(self):
        raw = struct.pack('<4I', 3, 2, 90, 16) + bytes(100)
        with self.assertRaises(ValueError):
            list(directory_entries(raw))

    def test_padded_directory_continuation_is_read(self):
        data = directory((3, 4, '.'), (2, 5, '..')) + directory((4, 2, 'second'))
        self.assertEqual(list(directory_entries(data))[-1], (4, 2, 'second'))

    def test_named_entries_include_patch_metadata(self):
        pkg = FullPKG.__new__(FullPKG)
        names = b'\0changeinfo/changeinfo.xml\0app/playgo-chunk.dat\0'
        pkg._payload = lambda ident: names
        pkg.entry = lambda ident: b'entry'
        pkg.entries = [((0x1260, 1, 0, 0, 0, 10), b''), ((0x1008, 27, 0, 0, 0, 12), b''), ((0x408, 0, 0, 0, 0, 13), b'')]
        self.assertEqual(pkg.files(), [('changeinfo/changeinfo.xml', 10), ('app/playgo-chunk.dat', 12), ('origin-deltainfo.dat', 13)])

    def test_final_xts_read_stays_inside_image(self):
        pkg = FullPKG.__new__(FullPKG)
        # The final uncompressed block ends exactly at the PFS image boundary.
        start = 0x1234
        end = start + BLOCK_SIZE
        pfs_size = (end + 4095) & ~4095
        pkg._load_pfs = lambda: ((start, end), 0, b'', b'', 0, pfs_size)
        def read(offset, size):
            self.assertLessEqual(offset + size, pfs_size)
            self.assertEqual(size % 4096, 0)
            return b'a' * size
        pkg._read = read
        with patch('pkg_full.xts_decrypt', side_effect=lambda dk, tk, data, sector: data):
            self.assertEqual(pkg._block(0), b'a' * BLOCK_SIZE)


class CompressionTests(unittest.TestCase):
    def test_valid_compressed_and_uncompressed_blocks(self):
        raw = b'a' * BLOCK_SIZE
        self.assertEqual(inflate_block(zlib.compress(raw)), raw)
        self.assertEqual(inflate_block(raw), raw)

    def test_rejects_corrupt_truncated_and_oversized_blocks(self):
        for raw in [b'bad', zlib.compress(b'short'), zlib.compress(b'a' * (BLOCK_SIZE + 1)), zlib.compress(b'a' * BLOCK_SIZE)[:-2]]:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                inflate_block(raw)


class CLITests(unittest.TestCase):
    def test_invalid_package_returns_error_without_traceback(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'bad'); f.flush()
            self.assertEqual(main([f.name, '--list']), 1)

    def test_games_path_implies_install_folder(self):
        with tempfile.TemporaryDirectory() as d:
            pkg, _ = fake_package()
            pkg.content_id = 'TEST-CUSA12345'
            pkg.title_id = 'CUSA12345'
            pkg.content_flags = 0
            pkg._sfo = {'APP_VER': '01.00', 'CATEGORY': 'gd'}
            pkg.close = lambda: None
            with patch('pkg_full.FullPKG', return_value=pkg):
                self.assertEqual(main(['fake.pkg', '--games-path', d]), 0)
            self.assertTrue((Path(d) / 'CUSA12345/root.bin').is_file())


if __name__ == '__main__':
    unittest.main()
