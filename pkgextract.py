#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Inspect, verify and extract supported PS4 fake PKG packages."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pkg_i18n import VERSION, language_context, tr


class PkgError(ValueError):
    """Raised when a package is malformed or unsupported."""


def report_progress(current: int, total: int, message: str) -> None:
    print(f"PROGRESS {current} {total} {message}", flush=True)


def main(argv: list[str] | None = None) -> int:
    # Parse the language first so --help is also available in either language.
    preliminary = argparse.ArgumentParser(add_help=False)
    preliminary.add_argument('--language', choices=('pt', 'en'), default=os.environ.get('PS4PKG_LANGUAGE', 'pt'))
    language = preliminary.parse_known_args(argv)[0].language
    with language_context(language):
        return _main(argv)


def _main(argv: list[str] | None) -> int:
    from pkg_full import FullPKG

    parser = argparse.ArgumentParser(description=tr("Lista e extrai arquivos de um PKG de PS4"))
    parser.add_argument('--version', action='version', version=f'PS4 PKG Extractor {VERSION}')
    parser.add_argument('--language', choices=('pt', 'en'), default='pt', help=tr('idioma das mensagens'))
    parser.add_argument("pkg", type=Path, help=tr("arquivo .pkg de entrada"))
    parser.add_argument("-o", "--output", type=Path, default=Path("extracted"), help=tr("diretório de saída"))
    inspection = parser.add_mutually_exclusive_group()
    inspection.add_argument("-l", "--list", action="store_true", help=tr("lista os metadados externos do PKG"))
    inspection.add_argument("--list-files", action="store_true", help=tr("lista também todos os arquivos do PFS"))
    inspection.add_argument("--verify", action="store_true", help=tr("valida todos os blocos PFS sem gravar arquivos"))
    parser.add_argument("--install", action="store_true", help=tr("cria uma pasta com o Title ID dentro do diretório de saída"))
    parser.add_argument("--games-path", type=Path, help=tr("diretório de jogos do shadPS4"))
    parser.add_argument("--addons-path", type=Path, help=tr("diretório de DLCs do shadPS4"))
    parser.add_argument("--separate-update", action="store_true", help=tr("instala o patch em CUSAxxxxx-UPDATE em vez de misturá-lo ao jogo"))
    args = parser.parse_args(argv)

    try:
        with FullPKG(args.pkg) as pkg:
            files = pkg.files()
            print(f"Content ID: {pkg.content_id}")
            print(tr("Tipo: {kind}", kind='PATCH' if pkg.is_patch else tr('JOGO/DLC')))
            if pkg.app_version:
                print(tr("Versão: {version}", version=pkg.app_version))
            print(tr("Arquivos: {count}", count=len(files)))
            for name, size in files:
                print(f"{size:>12} {name}")
            if args.list_files or args.verify:
                payloads = pkg.game_files(progress=report_progress)
                print(tr("Arquivos PFS: {count}", count=len(payloads)))
                print(tr("Tamanho PFS: {size} bytes", size=sum(item.size for item in payloads)))
                if args.list_files:
                    for item in payloads:
                        print(f"{item.size:>12} {item.name}")
                else:
                    count, size = pkg.verify(progress=report_progress)
                    print(tr("PFS verificado: {count} arquivos, {size} bytes (sem gravar)", count=count, size=size))
            elif not args.list:
                root = args.games_path or args.output
                if (args.install or args.games_path or pkg.is_patch) and not pkg.title_id:
                    raise PkgError(tr("Title ID CUSA inválido; não é possível instalar o pacote"))
                if pkg.is_patch:
                    game = root / pkg.title_id
                    if not (game / "eboot.bin").is_file() or not (game / "sce_sys/param.sfo").is_file():
                        print(tr("aviso: jogo {title} não encontrado em {root}; o patch não foi aplicado", title=pkg.title_id, root=root), file=sys.stderr)
                        return 1
                    output = root / f"{pkg.title_id}-UPDATE" if args.separate_update else game
                else:
                    output = root / pkg.title_id if args.install or args.games_path else root
                pkg.extract(output, progress=report_progress)
                print(tr("Extraído em: {path}", path=output))
    except (OSError, ValueError) as error:
        print(tr("erro: {error}", error=error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
