# SPDX-License-Identifier: GPL-2.0-or-later
import ast
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from string import Formatter
from unittest.mock import patch

from pkg_i18n import ENGLISH, language_context, load_language, save_language, tr
from pkg_full import FullPKG
from pkgextract import main
from pkg_fixture import metadata_pkg


class LanguageTests(unittest.TestCase):
    def test_translation_preserves_format_parameters(self):
        for source, translated in ENGLISH.items():
            original = {field for _, field, _, _ in Formatter().parse(source) if field}
            target = {field for _, field, _, _ in Formatter().parse(translated) if field}
            self.assertEqual(original, target, source)

    def test_all_backend_diagnostics_have_english_translation(self):
        root = Path(__file__).resolve().parents[1]
        for file in ('pkg_full.py', 'pkg_crypto.py'):
            for node in ast.walk(ast.parse((root / file).read_text(encoding='utf-8'))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr':
                    if node.args and isinstance(node.args[0], ast.Constant):
                        message = node.args[0].value
                        self.assertTrue(message in ENGLISH or message == '{value0} {value1}', message)

    def test_language_is_restored_after_cli_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.pkg'
            path.write_bytes(b'bad')
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(main([str(path), '--list', '--language', 'en']), 1)
            self.assertIn('truncated PKG header', output.getvalue())
            self.assertEqual(tr('Erro'), 'Erro')

    def test_cli_lists_in_english(self):
        with tempfile.TemporaryDirectory() as folder:
            path = metadata_pkg(Path(folder) / 'Jogo.pkg')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path), '--list', '--language', 'en']), 0)
            self.assertIn('Type: GAME/DLC', output.getvalue())
            self.assertIn('Version: 01.00', output.getvalue())

    def test_settings_roundtrip_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'settings.json'
            with patch('pkg_i18n.settings_path', return_value=target):
                self.assertEqual(load_language(), 'pt')
                self.assertTrue(save_language('en'))
                self.assertEqual(load_language(), 'en')
                self.assertFalse(save_language('unsupported'))
                for data in ('bad json', '[]', '{"language": "unknown"}', '{"language": []}'):
                    target.write_text(data, encoding='utf-8')
                    self.assertEqual(load_language(), 'pt')

    def test_no_mmap_reader_handles_windows_without_resident_pages(self):
        package = FullPKG.__new__(FullPKG)
        package.file = io.BytesIO(b'0123456789')
        package.size = 10
        package.mapping = None
        self.assertEqual(package._read(3, 4), b'3456')
        with self.assertRaises(ValueError):
            package._read(9, 2)
