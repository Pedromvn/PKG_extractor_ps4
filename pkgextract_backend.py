#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Console-capable worker embedded inside the windowed Windows application."""
from __future__ import annotations

import sys

from pkgextract import main


def run(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ['--backend']:
        arguments.pop(0)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    return main(arguments)


if __name__ == '__main__':
    raise SystemExit(run())
