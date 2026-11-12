# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise a packaged executable's real backend and translated UTF-8 output."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pkg_fixture import metadata_pkg

executable = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='pkg-smoke-') as folder:
    pkg = metadata_pkg(Path(folder) / 'Jogo com acentuação.PkG')
    for language, expected in [('en', 'Type: GAME/DLC'), ('pt', 'Tipo: JOGO/DLC')]:
        result = subprocess.run([executable, '--backend', str(pkg), '--list', '--language', language],
                                capture_output=True, encoding='utf-8', errors='replace', timeout=120,
                                env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
        assert result.returncode == 0, result.stdout + result.stderr
        assert expected in result.stdout, result.stdout
        assert 'param.sfo' in result.stdout, result.stdout
    pkg.write_bytes(b'broken')
    result = subprocess.run([executable, '--backend', str(pkg), '--list', '--language', 'en'],
                            capture_output=True, encoding='utf-8', timeout=120)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'truncated PKG header' in result.stderr, result.stderr
print('Packaged backend smoke tests passed (Portuguese, English, Unicode paths, invalid input).')
