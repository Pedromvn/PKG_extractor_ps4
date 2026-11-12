# SPDX-License-Identifier: GPL-2.0-or-later
"""Read supported PS4 fake PKGs and reconstruct their compressed PFS image.

The layout and cryptographic flow follow shadPS4 v0.7.0:
https://github.com/shadps4-emu/shadPS4/blob/v.0.7.0/src/core/file_format/pkg.cpp
"""
from __future__ import annotations

import mmap
import os
import re
import struct
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from pkg_crypto import aes_cbc, derive_iv_key, inflate_block, pfs_keys, unwrap_keys, xts_decrypt


ENTRY_NAMES = {
    0x1: "digests", 0x10: "entry_keys", 0x20: "image_key", 0x80: "general_digests",
    0x100: "metas", 0x200: "entry_names", 0x400: "license.dat", 0x401: "license.info",
    0x402: "nptitle.dat", 0x403: "npbind.dat", 0x408: "origin-deltainfo.dat", 0x409: "psreserved.dat",
    0x1000: "param.sfo", 0x1001: "playgo-chunk.dat", 0x1002: "playgo-chunk.sha",
    0x1003: "playgo-manifest.xml", 0x1004: "pronunciation.xml", 0x1005: "pronunciation.sig",
    0x1006: "pic1.png", 0x100b: "shareparam.json", 0x1200: "icon0.png",
    0x1220: "pic0.png", 0x1280: "icon0.dds", 0x12c0: "pic1.dds", 0x1400: "trophy/trophy00.trp",
}
BLOCK_SIZE = 0x10000
SECTOR_SIZE = 0x1000
INODE_SIZE = 0xA8
Progress = Callable[[int, int, str], None]


@dataclass(frozen=True)
class PFSFile:
    name: str
    size: int
    location: int
    blocks: int


def safe_target(root: Path, name: str) -> Path:
    """Keep package paths and existing symbolic links inside the destination."""
    relative = Path(name)
    if (not name or relative.is_absolute() or ".." in relative.parts
            or "\\" in name or "\0" in name or ":" in name):
        raise ValueError(f"nome de arquivo inseguro: {name!r}")
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"destino fora da pasta de extração: {name!r}")
    return target


def directory_entries(data: bytes) -> Iterator[tuple[int, int, str]]:
    """Parse a directory extent, including blocks without repeated dot entries."""
    pos = 0
    while pos + 16 <= len(data):
        ino, kind, name_len, entry_len = struct.unpack_from("<4I", data, pos)
        if ino == 0:
            # Zero padding fills the remainder of each logical block.
            pos = (pos // BLOCK_SIZE + 1) * BLOCK_SIZE
            continue
        if (entry_len < 16 or entry_len % 4 or entry_len > len(data) - pos
                or entry_len > BLOCK_SIZE - pos % BLOCK_SIZE
                or not 0 < name_len <= 255 or name_len > entry_len - 16):
            raise ValueError(f"entrada de diretório PFS inválida em 0x{pos:x}")
        try:
            name = data[pos + 16:pos + 16 + name_len].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("nome PFS não é UTF-8 válido") from error
        if "\0" in name or "/" in name or "\\" in name or ":" in name:
            raise ValueError(f"nome de arquivo PFS inseguro: {name!r}")
        yield ino, kind, name
        pos += entry_len


class FullPKG:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.file = self.path.open("rb")
        self.mapping = None
        self._image = None
        self._index = None
        self._sfo = None
        self._mapped_bytes = 0
        try:
            self.size = os.fstat(self.file.fileno()).st_size
            if self.size < 0x1000:
                raise ValueError("cabeçalho PKG truncado")
            self.mapping = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
            self.header = self._read(0, 0x1000)
            if self.header[:4] != b"\x7fCNT":
                raise ValueError("assinatura PKG inválida")
            self.count = self.u32(0x10)
            self.table = self.u32(0x18)
            if not 0 < self.count <= 1_000_000 or self.table < 0x1000:
                raise ValueError("tabela de entradas PKG inválida")
            self._check_range(self.table, self.count * 32)
            self.content_id = self.header[0x40:0x64].split(b"\0", 1)[0].decode("ascii", "replace")
            match = re.search(r"CUSA\d{5}", self.content_id)
            self.title_id = match[0] if match else ""
            self.content_flags = self.u32(0x78)
            self.entries = [self._entry(i) for i in range(self.count)]
            for values, _ in self.entries:
                self._check_range(values[4], values[5])
            declared_size = struct.unpack_from(">Q", self.header, 0x430)[0]
            if declared_size > self.size:
                raise ValueError("arquivo PKG truncado: tamanho menor que o declarado")
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.mapping is not None:
            self.mapping.close()
        self.file.close()

    def _check_range(self, offset, size):
        if offset < 0 or size < 0 or offset + size > self.size:
            raise ValueError(f"leitura fora do PKG: 0x{offset:x}+0x{size:x}")

    def _read(self, offset, size):
        self._check_range(offset, size)
        data = self.mapping[offset:offset + size]
        self._mapped_bytes += size
        if self._mapped_bytes >= 16 * 1024 * 1024 and hasattr(mmap, "MADV_DONTNEED"):
            # Slices already own their bytes. Release old mapped pages from
            # this process while retaining the kernel's file cache, so a
            # complete extraction does not keep the entire PKG resident.
            self.mapping.madvise(mmap.MADV_DONTNEED)
            self._mapped_bytes = 0
        return data

    def u32(self, offset):
        return struct.unpack_from(">I", self.header, offset)[0]

    def _entry(self, index):
        raw = self._read(self.table + index * 32, 32)
        return struct.unpack(">6I8x", raw), raw

    def entry(self, ident):
        return next((item for values, item in self.entries if values[0] == ident), None)

    def files(self):
        """List outer PKG entries; game payloads are available via game_files()."""
        return [(name, values[5]) for values, _, name in self._named_entries()]

    def _named_entries(self):
        names = self._payload(0x200) if self.entry(0x200) is not None else b""
        for values, raw in self.entries:
            ident, name_offset = values[:2]
            name = ENTRY_NAMES.get(ident, str(ident))
            if name_offset:
                end = names.find(b"\0", name_offset)
                if name_offset >= len(names) or end < 0:
                    raise ValueError(f"nome de entrada PKG inválido: {ident:#x}")
                name = names[name_offset:end].decode("utf-8")
            if name:
                safe_target(Path("."), name)
                yield values, raw, name

    def sfo_values(self):
        if self._sfo is not None:
            return self._sfo
        raw = self._payload(0x1000)
        if len(raw) < 20 or raw[:4] != b"\0PSF":
            raise ValueError("param.sfo inválido")
        _, _, key_offset, data_offset, count = struct.unpack_from("<5I", raw)
        if not 20 + count * 16 <= key_offset <= data_offset <= len(raw):
            raise ValueError("tabela param.sfo inválida")
        values = {}
        for index in range(count):
            key_index, fmt, length, maximum, value_offset = struct.unpack_from("<HHIII", raw, 20 + index * 16)
            key_start = key_offset + key_index
            key_end = raw.find(b"\0", key_start, data_offset)
            start = data_offset + value_offset
            if key_start >= data_offset or key_end < 0 or length > maximum or start + maximum > len(raw):
                raise ValueError("entrada param.sfo truncada")
            key = raw[key_start:key_end].decode("utf-8", "replace")
            value = raw[start:start + length]
            values[key] = struct.unpack("<I", value)[0] if fmt == 0x404 and length == 4 else value.rstrip(b"\0").decode("utf-8", "replace")
        self._sfo = values
        return values

    @property
    def category(self):
        return self.sfo_values().get("CATEGORY", "")

    @property
    def app_version(self):
        return self.sfo_values().get("APP_VER", "")

    @property
    def is_patch(self):
        return bool(self.content_flags & 0x40000000 or self.category == "gp")

    def _payload(self, ident):
        raw = self.entry(ident)
        if raw is None:
            raise ValueError(f"entrada PKG ausente: {ident:#x}")
        values = struct.unpack(">6I8x", raw)
        return self._read(values[4], values[5])

    def _load_pfs(self, progress: Progress | None = None):
        if self._image is not None:
            return self._image
        if progress:
            progress(0, 1000, "Lendo imagem PFS")
        keys = self._payload(0x10)
        key_offset = 32 + 7 * 32 + 3 * 256
        self._dk3, ekpfs = unwrap_keys(self.entry(0x20), keys[key_offset:key_offset + 256], self._payload(0x20))
        pfs_offset, pfs_size = struct.unpack_from(">2Q", self.header, 0x410)
        cache_size = self.u32(0x43c) * 2
        self._check_range(pfs_offset, pfs_size)
        if not 0 < cache_size <= pfs_size or cache_size % SECTOR_SIZE:
            raise ValueError("tamanho de cache PFS inválido")
        data_key, tweak_key = pfs_keys(ekpfs, self._read(pfs_offset + 0x370, 16))
        decrypted = xts_decrypt(data_key, tweak_key, self._read(pfs_offset, cache_size), 0)
        pfsc_offset = next((i for i in range(0x20000, len(decrypted), BLOCK_SIZE) if decrypted[i:i + 4] == b"PFSC"), None)
        if pfsc_offset is None or pfsc_offset + 0x30 > len(decrypted):
            raise ValueError("PFSC não encontrado; PKG cifrado ou formato não suportado")
        block_size, offsets = struct.unpack_from("<2Q", decrypted, pfsc_offset + 0x10)
        data_length = struct.unpack_from("<Q", decrypted, pfsc_offset + 0x28)[0]
        if block_size != BLOCK_SIZE or not data_length or data_length % block_size:
            raise ValueError("geometria PFSC não suportada")
        count = data_length // block_size
        map_start = pfsc_offset + offsets
        if offsets < 0x30 or map_start + (count + 1) * 8 > len(decrypted):
            raise ValueError("mapa de blocos PFSC truncado")
        sector_map = struct.unpack_from(f"<{count + 1}Q", decrypted, map_start)
        if sector_map[0] < offsets + (count + 1) * 8 or sector_map[-1] > pfs_size - pfsc_offset:
            raise ValueError("mapa de blocos PFSC fora da imagem")
        if any(not 0 < end - start <= BLOCK_SIZE for start, end in zip(sector_map, sector_map[1:])):
            raise ValueError("extensão de bloco PFSC inválida")
        self._image = (sector_map, pfsc_offset, data_key, tweak_key, pfs_offset, pfs_size)
        return self._image

    def _block(self, index: int) -> bytes:
        sector_map, pfsc_offset, data_key, tweak_key, pfs_offset, pfs_size = self._load_pfs()
        if not 0 <= index < len(sector_map) - 1:
            raise ValueError(f"índice de bloco PFS inválido: {index}")
        start, end = sector_map[index:index + 2]
        aligned = (pfsc_offset + start) & ~(SECTOR_SIZE - 1)
        skip = pfsc_offset + start - aligned
        read_size = (skip + end - start + SECTOR_SIZE - 1) & ~(SECTOR_SIZE - 1)
        if aligned + read_size > pfs_size:
            raise ValueError(f"bloco PFS truncado: {index}")
        encrypted = self._read(pfs_offset + aligned, read_size)
        data = xts_decrypt(data_key, tweak_key, encrypted, aligned // SECTOR_SIZE)
        return inflate_block(data[skip:skip + end - start])

    def game_files(self, progress: Progress | None = None) -> list[PFSFile]:
        """Index files using directory inode extents, regardless of physical order."""
        if self._index is not None:
            return self._index[0]
        image = self._load_pfs(progress)
        first = self._block(0)
        count = struct.unpack_from("<I", first, 0x30)[0]
        per_block = BLOCK_SIZE // INODE_SIZE
        inode_blocks = (count + per_block - 1) // per_block
        if count < 3 or inode_blocks + 1 >= len(image[0]):
            raise ValueError("quantidade de inodes PFS inválida")
        inodes = []
        for block_index in range(1, inode_blocks + 1):
            block = self._block(block_index)
            for offset in range(0, per_block * INODE_SIZE, INODE_SIZE):
                if len(inodes) == count:
                    break
                mode = struct.unpack_from("<H", block, offset)[0] & 0xF000
                size = struct.unpack_from("<Q", block, offset + 8)[0]
                blocks, location = struct.unpack_from("<2I", block, offset + 0x60)
                if (mode not in (0x4000, 0x8000) or blocks != (size + BLOCK_SIZE - 1) // BLOCK_SIZE
                        or (blocks and (location < inode_blocks + 1 or location + blocks >= len(image[0])))):
                    raise ValueError(f"inode PFS inválido ou não suportado: {len(inodes)}")
                inodes.append((mode, size, blocks, location))

        def read_directory(ino):
            if not 0 <= ino < len(inodes) or inodes[ino][0] != 0x4000:
                raise ValueError(f"inode de diretório PFS inválido: {ino}")
            _, _, blocks, location = inodes[ino]
            return list(directory_entries(b"".join(self._block(location + i) for i in range(blocks))))

        outer_entries = read_directory(0)
        roots = [ino for ino, kind, name in outer_entries if kind == 3 and name == "uroot"]
        if len(roots) != 1:
            raise ValueError("diretório uroot PFS não encontrado")
        root = roots[0]
        pending = [(root, "")]
        directories = []
        seen_dirs = {root}
        referenced = {0, root} | {ino for ino, kind, _ in outer_entries if kind == 2}
        seen_paths = set()
        files = []
        for directory, parent in pending:
            for ino, kind, name in read_directory(directory):
                if name in (".", ".."):
                    if kind != (4 if name == "." else 5):
                        raise ValueError(f"referência de diretório PFS inválida: {name}")
                    continue
                if not 0 < ino < len(inodes) or kind not in (2, 3):
                    raise ValueError(f"entrada PFS não suportada: {name!r} (tipo {kind})")
                path = f"{parent}/{name}" if parent else name
                safe_target(Path("."), path)
                if path in seen_paths:
                    raise ValueError(f"caminho PFS duplicado: {path}")
                seen_paths.add(path)
                referenced.add(ino)
                mode, size, blocks, location = inodes[ino]
                if kind == 3:
                    if ino in seen_dirs or mode != 0x4000:
                        raise ValueError(f"diretório PFS cíclico ou inválido: {path}")
                    seen_dirs.add(ino)
                    directories.append(path)
                    pending.append((ino, path))
                else:
                    if mode != 0x8000:
                        raise ValueError(f"inode de arquivo PFS inválido: {path}")
                    files.append(PFSFile(path, size, location, blocks))
        if len(referenced) != count:
            raise ValueError(f"índice PFS incompleto: {count - len(referenced)} inodes sem caminho")
        if progress:
            progress(100, 1000, f"Índice PFS: {len(files)} arquivos")
        self._index = (files, directories)
        return files

    def _file_chunks(self, item: PFSFile) -> Iterator[bytes]:
        remaining = item.size
        for index in range(item.blocks):
            block = self._block(item.location + index)
            chunk = block[:min(remaining, BLOCK_SIZE)]
            yield chunk
            remaining -= len(chunk)
        if remaining:
            raise ValueError(f"arquivo PFS incompleto: {item.name}")

    def _process_files(self, files, consume, progress, verb):
        total = sum(item.size for item in files)
        completed = 0
        reported_at = 0.0
        for item in files:
            def chunks():
                nonlocal completed, reported_at
                for chunk in self._file_chunks(item):
                    yield chunk
                    completed += len(chunk)
                    now = time.monotonic()
                    if progress and now - reported_at >= 0.1:
                        progress(100 + completed * 900 // max(1, total), 1000, f"{verb} {item.name}")
                        reported_at = now
            consume(item, chunks())
        if progress:
            progress(1000, 1000, "Concluído")

    def verify(self, progress: Progress | None = None):
        """Decode all file blocks and validate sizes without writing a dump."""
        files = self.game_files(progress)
        def consume(item, chunks):
            for _ in chunks:
                pass
        self._process_files(files, consume, progress, "Verificando")
        return len(files), sum(item.size for item in files)

    def extract(self, destination: Path, progress: Progress | None = None):
        files = self.game_files(progress)
        destination = Path(destination).resolve()
        # Validate every output before creating or replacing files.
        for name in self._index[1] + [item.name for item in files]:
            safe_target(destination, name)
        outer = []
        for values, raw, name in self._named_entries():
            ident, _, flags, _, offset, size = values
            if ident in (0x400, 0x401, 0x402, 0x403) and flags & 0x80000000:
                # Entries are stored in padded CBC blocks; retain the declared
                # size after decrypting, including non-aligned npbind.dat.
                iv_key = derive_iv_key(raw, self._dk3)
                data = aes_cbc(iv_key[16:], iv_key[:16], self._read(offset, (size + 15) & ~15))[:size]
            else:
                data = self._read(offset, size)
            outer.append((f"sce_sys/{name}", data))
        for name, _ in outer:
            safe_target(destination, name)
        destination.mkdir(parents=True, exist_ok=True)
        for name in self._index[1]:
            safe_target(destination, name).mkdir(parents=True, exist_ok=True)

        def write_atomic(name, chunks):
            target = safe_target(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="wb", prefix=".pkg-", suffix=".part", dir=target.parent, delete=False) as output:
                    temporary = Path(output.name)
                    for chunk in chunks:
                        output.write(chunk)
                os.replace(temporary, target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        # Write package metadata after validating the PFS layout and paths.
        for name, data in outer:
            write_atomic(name, [data])
        self._process_files(files, lambda item, chunks: write_atomic(item.name, chunks), progress, "Extraindo")
        return destination
