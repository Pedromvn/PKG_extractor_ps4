#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Inspect, verify and extract supported PS4 fake PKG packages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


class PkgError(ValueError):
    """Raised when a package is malformed or unsupported."""


def report_progress(current: int, total: int, message: str) -> None:
    print(f"PROGRESS {current} {total} {message}", flush=True)


def main(argv: list[str] | None = None) -> int:
    from pkg_full import FullPKG

    parser = argparse.ArgumentParser(description="Lista e extrai arquivos de um PKG de PS4")
    parser.add_argument("pkg", type=Path, help="arquivo .pkg de entrada")
    parser.add_argument("-o", "--output", type=Path, default=Path("extracted"), help="diretório de saída")
    inspection = parser.add_mutually_exclusive_group()
    inspection.add_argument("-l", "--list", action="store_true", help="lista os metadados externos do PKG")
    inspection.add_argument("--list-files", action="store_true", help="lista também todos os arquivos do PFS")
    inspection.add_argument("--verify", action="store_true", help="valida todos os blocos PFS sem gravar arquivos")
    parser.add_argument(
        "--install",
        action="store_true",
        help="cria uma pasta com o Content ID dentro do diretório de saída",
    )
    parser.add_argument("--games-path", type=Path, help="diretório de jogos do shadPS4")
    parser.add_argument("--addons-path", type=Path, help="diretório de DLCs do shadPS4")
    parser.add_argument(
        "--separate-update",
        action="store_true",
        help="instala o patch em CUSAxxxxx-UPDATE em vez de misturá-lo ao jogo",
    )
    args = parser.parse_args(argv)

    try:
        pkg = FullPKG(args.pkg)
        try:
            files = pkg.files()
            print(f"Content ID: {pkg.content_id}")
            print(f"Tipo: {'PATCH' if pkg.is_patch else 'JOGO/DLC'}")
            if pkg.app_version:
                print(f"Versão: {pkg.app_version}")
            print(f"Arquivos: {len(files)}")
            for name, size in files:
                print(f"{size:>12} {name}")
            if args.list_files or args.verify:
                payloads = pkg.game_files(progress=report_progress)
                print(f"Arquivos PFS: {len(payloads)}")
                print(f"Tamanho PFS: {sum(item.size for item in payloads)} bytes")
                if args.list_files:
                    for item in payloads:
                        print(f"{item.size:>12} {item.name}")
                else:
                    count, size = pkg.verify(progress=report_progress)
                    print(f"PFS verificado: {count} arquivos, {size} bytes (sem gravar)")
            elif not args.list:
                root = args.games_path or args.output
                if (args.install or args.games_path or pkg.is_patch) and not pkg.title_id:
                    raise PkgError("Title ID CUSA inválido; não é possível instalar o pacote")
                if pkg.is_patch:
                    game = root / pkg.title_id
                    if not (game / "eboot.bin").is_file() or not (game / "sce_sys/param.sfo").is_file():
                        print(
                            f"aviso: jogo {pkg.title_id} não encontrado em {root}; "
                            "o patch não foi aplicado",
                            file=sys.stderr,
                        )
                        return 1
                    output = root / f"{pkg.title_id}-UPDATE" if args.separate_update else game
                else:
                    output = root / pkg.title_id if args.install or args.games_path else root
                pkg.extract(output, progress=report_progress)
                print(f"Extraído em: {output}")
        finally:
            pkg.close()
    except (OSError, PkgError, ValueError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
