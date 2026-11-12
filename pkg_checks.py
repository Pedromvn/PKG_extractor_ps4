# SPDX-License-Identifier: GPL-2.0-or-later
"""Checks performed before an installation changes any destination files."""
from __future__ import annotations

import re
import shutil
import struct
from pathlib import Path

from pkg_i18n import tr


class PatchDowngradeError(ValueError):
    def __init__(self, installed: str, incoming: str):
        self.installed = installed
        self.incoming = incoming
        super().__init__(tr("O patch {incoming} é mais antigo que a versão instalada {installed}.",
                            incoming=incoming, installed=installed))


def parse_sfo(raw: bytes) -> dict:
    if len(raw) < 20 or raw[:4] != b"\0PSF":
        raise ValueError(tr('param.sfo inválido'))
    _, _, key_offset, data_offset, count = struct.unpack_from('<5I', raw)
    if not 20 + count * 16 <= key_offset <= data_offset <= len(raw):
        raise ValueError(tr('tabela param.sfo inválida'))
    values = {}
    for index in range(count):
        key_index, fmt, length, maximum, value_offset = struct.unpack_from('<HHIII', raw, 20 + index * 16)
        key_start = key_offset + key_index
        key_end = raw.find(b'\0', key_start, data_offset)
        start = data_offset + value_offset
        if key_start >= data_offset or key_end < 0 or length > maximum or start + maximum > len(raw):
            raise ValueError(tr('entrada param.sfo truncada'))
        key = raw[key_start:key_end].decode('utf-8', 'replace')
        value = raw[start:start + length]
        values[key] = struct.unpack('<I', value)[0] if fmt == 0x404 and length == 4 else value.rstrip(b'\0').decode('utf-8', 'replace')
    return values


def version_number(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){1,3}', value):
        raise ValueError(tr('APP_VER inválida: {version!r}', version=value))
    parts = [int(part) for part in value.split('.')]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def validate_patch(pkg, game: Path, *, separate_update=False, allow_downgrade=False) -> None:
    sfo = game / 'sce_sys/param.sfo'
    if not (game / 'eboot.bin').is_file() or not sfo.is_file():
        raise ValueError(tr('Jogo base não encontrado em {path}; o patch não foi aplicado.', path=game))
    installed = parse_sfo(sfo.read_bytes())
    incoming = pkg.sfo_values()
    title = installed.get('TITLE_ID')
    if title != pkg.title_id or incoming.get('TITLE_ID') != pkg.title_id:
        raise ValueError(tr('O patch {title} não corresponde ao TITLE_ID do jogo instalado.', title=pkg.title_id))
    if incoming.get('CATEGORY') != 'gp':
        raise ValueError(tr('O pacote não contém uma atualização válida.'))
    installed_content = installed.get('CONTENT_ID')
    incoming_content = incoming.get('CONTENT_ID') or getattr(pkg, 'content_id', None)
    for content in (installed_content, incoming_content):
        if content:
            if not isinstance(content, str) or not re.search(rf'-{re.escape(pkg.title_id)}_', content):
                raise ValueError(tr('CONTENT_ID incompatível com o jogo {title}.', title=pkg.title_id))
    if installed_content and incoming_content and installed_content != incoming_content:
        raise ValueError(tr('O CONTENT_ID do patch é diferente do jogo instalado.'))
    if installed.get('CATEGORY') not in ('gd', 'gp'):
        raise ValueError(tr('O destino não contém um jogo base ou uma atualização válida.'))
    current_version = installed.get('APP_VER')
    target = incoming.get('APP_VER')
    current = version_number(current_version)
    requested = version_number(target)
    # Replacing a separated update must also respect the version already there.
    if separate_update:
        update = game.with_name(game.name + '-UPDATE')
        update_sfo = update / 'sce_sys/param.sfo'
        if update_sfo.exists():
            previous = parse_sfo(update_sfo.read_bytes())
            if previous.get('TITLE_ID') != pkg.title_id:
                raise ValueError(tr('A pasta de atualização contém outro TITLE_ID.'))
            if previous.get('CONTENT_ID') and incoming_content and previous['CONTENT_ID'] != incoming_content:
                raise ValueError(tr('O CONTENT_ID do patch é diferente do jogo instalado.'))
            if previous.get('CATEGORY') != 'gp':
                raise ValueError(tr('O destino não contém um jogo base ou uma atualização válida.'))
            previous_version = previous.get('APP_VER')
            previous_number = version_number(previous_version)
            if previous_number > current:
                current_version, current = previous_version, previous_number
    if requested < current and not allow_downgrade:
        raise PatchDowngradeError(current_version, target)


def ensure_disk_space(destination: Path, payload_bytes: int) -> None:
    """Use the destination filesystem, even if the output folder is not created.

    Reserve the full decoded payload plus 1% (at least 16 MiB) for filesystem
    overhead and temporary writes. Existing files are not credited: they must
    remain intact until each replacement is complete.
    """
    ancestor = destination.resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    required = payload_bytes + max(16 * 1024 * 1024, (payload_bytes + 99) // 100)
    if free < required:
        raise ValueError(tr('Espaço insuficiente em {path}: necessários {required} GiB, disponíveis {free} GiB.',
                            path=ancestor, required=f'{required / 1024**3:.2f}', free=f'{free / 1024**3:.2f}'))
