# SPDX-License-Identifier: GPL-2.0-or-later
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pkgextract_backend import run
from pkg_fixture import metadata_pkg


class WorkerTests(unittest.TestCase):
    def test_worker_keeps_localized_metadata_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = metadata_pkg(Path(folder) / 'Jogo com acentuação.pkg')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(run(['--backend', str(path), '--list', '--language', 'en']), 0)
            self.assertIn('Type: GAME/DLC', output.getvalue())

    def test_worker_tolerates_missing_python_standard_streams(self):
        with patch('pkgextract_backend.sys.stdout', None), patch('pkgextract_backend.sys.stderr', None), patch('pkgextract_backend.main', return_value=0) as main:
            self.assertEqual(run(['--backend', '--version']), 0)
            main.assert_called_once_with(['--version'])
