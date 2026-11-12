# SPDX-License-Identifier: GPL-2.0-or-later
"""Installations must reject invalid input before changing destination files."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pkg_checks import PatchDowngradeError, ensure_disk_space, parse_sfo, validate_patch, version_number
from pkg_full import FullPKG
from pkgextract import main
from pkg_fixture import metadata_pkg, sfo_data
from test_pkg import fake_package

CONTENT_ID = 'XX0000-CUSA12345_00-TESTPKG0000000000'


def install_game(root, **overrides):
    game = root / 'CUSA12345'
    (game / 'sce_sys').mkdir(parents=True, exist_ok=True)
    (game / 'eboot.bin').write_bytes(b'base-game')
    values = {'TITLE_ID': 'CUSA12345', 'CONTENT_ID': CONTENT_ID, 'CATEGORY': 'gd', 'APP_VER': '01.00'}
    values.update(overrides)
    (game / 'sce_sys/param.sfo').write_bytes(sfo_data(values))
    return game


def patch_package(**overrides):
    values = {'TITLE_ID': 'CUSA12345', 'CONTENT_ID': CONTENT_ID, 'CATEGORY': 'gp', 'APP_VER': '01.09'}
    values.update(overrides)
    return SimpleNamespace(title_id='CUSA12345', content_id=CONTENT_ID, sfo_values=lambda: values)


class DiskSpaceTests(unittest.TestCase):
    def test_checks_nearest_existing_directory_without_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            destination = root / 'not-created/game'
            with patch('pkg_checks.shutil.disk_usage', return_value=SimpleNamespace(free=10**12)) as usage:
                ensure_disk_space(destination, 3 * 1024**3)
            usage.assert_called_once_with(root)
            self.assertFalse(destination.exists())

    def test_out_of_space_preserves_existing_files_and_creates_nothing(self):
        package, _ = fake_package()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sentinel = root / 'root.bin'
            sentinel.write_bytes(b'existing-file')
            with patch('pkg_checks.shutil.disk_usage', return_value=SimpleNamespace(free=0)):
                with self.assertRaisesRegex(ValueError, 'Espaço insuficiente'):
                    package.extract(root)
            self.assertEqual(sentinel.read_bytes(), b'existing-file')
            self.assertEqual(list(root.iterdir()), [sentinel])

    def test_requires_decoded_files_and_outer_metadata_before_mkdir(self):
        package, _ = fake_package()  # 15 decoded bytes.
        package._named_entries = lambda: iter([((0x1000, 0, 0, 0, 0, 24), b'', 'param.sfo')])
        package._read = lambda offset, size: bytes(size)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'output'
            with patch('pkg_checks.shutil.disk_usage', return_value=SimpleNamespace(free=16*1024**2 + 38)):
                with self.assertRaises(ValueError):
                    package.extract(root)
            self.assertFalse(root.exists())

    def test_sufficient_space_permits_extraction(self):
        package, _ = fake_package()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'output'
            with patch('pkg_checks.shutil.disk_usage', return_value=SimpleNamespace(free=10**9)):
                package.extract(root)
            self.assertEqual((root / 'nested/continuation.bin').read_bytes(), b'second')


class PatchTests(unittest.TestCase):
    def test_valid_newer_and_equal_patches(self):
        with tempfile.TemporaryDirectory() as folder:
            game = install_game(Path(folder))
            validate_patch(patch_package(), game)
            validate_patch(patch_package(APP_VER='1.0.0'), game)

    def test_versions_are_numeric_and_malformed_versions_are_rejected(self):
        self.assertGreater(version_number('01.10'), version_number('01.09'))
        self.assertEqual(version_number('01.00'), version_number('1.0.0'))
        for version in ('', '1.09-beta', 'wrong', None):
            with self.subTest(version=version), self.assertRaises(ValueError):
                version_number(version)

    def test_wrong_title_or_content_is_blocked_even_with_override(self):
        for installed in ({'TITLE_ID': 'CUSA99999'}, {'CONTENT_ID': 'YY0000-CUSA12345_00-OTHERGAME00000000'}):
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as folder:
                game = install_game(Path(folder), **installed)
                with self.assertRaises(ValueError):
                    validate_patch(patch_package(), game, allow_downgrade=True)
        with tempfile.TemporaryDirectory() as folder:
            game = install_game(Path(folder))
            with self.assertRaises(ValueError):
                validate_patch(patch_package(TITLE_ID='CUSA99999'), game)
            with self.assertRaises(ValueError):
                validate_patch(patch_package(CATEGORY='gd'), game)

    def test_missing_or_corrupt_base_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                validate_patch(patch_package(), root / 'missing')
            game = install_game(root)
            (game / 'sce_sys/param.sfo').write_bytes(b'broken')
            with self.assertRaises(ValueError):
                validate_patch(patch_package(), game)

    def test_downgrade_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as folder:
            game = install_game(Path(folder), APP_VER='01.10', CATEGORY='gp')
            with self.assertRaises(PatchDowngradeError) as error:
                validate_patch(patch_package(), game)
            self.assertEqual(error.exception.installed, '01.10')
            self.assertEqual(error.exception.incoming, '01.09')
            validate_patch(patch_package(), game, allow_downgrade=True)

    def test_separate_update_compares_existing_update_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = install_game(root)
            update = root / 'CUSA12345-UPDATE/sce_sys'
            update.mkdir(parents=True)
            update.joinpath('param.sfo').write_bytes(sfo_data({'TITLE_ID': 'CUSA12345', 'CONTENT_ID': CONTENT_ID, 'CATEGORY': 'gp', 'APP_VER': '02.00'}))
            with self.assertRaises(PatchDowngradeError) as error:
                validate_patch(patch_package(), game, separate_update=True)
            self.assertEqual(error.exception.installed, '02.00')
            validate_patch(patch_package(), game, separate_update=True, allow_downgrade=True)
            update.joinpath('param.sfo').write_bytes(sfo_data({'TITLE_ID': 'CUSA99999', 'CATEGORY': 'gp', 'APP_VER': '02.00'}))
            with self.assertRaises(ValueError):
                validate_patch(patch_package(), game, separate_update=True, allow_downgrade=True)

    def test_cli_downgrade_confirmation_precedes_all_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = install_game(root, APP_VER='01.10', CATEGORY='gp')
            before = (game / 'sce_sys/param.sfo').read_bytes()
            package = metadata_pkg(root / 'patch.pkg', CATEGORY='gp', APP_VER='01.09', CONTENT_ID=CONTENT_ID)
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(FullPKG, 'extract') as extract, redirect_stdout(output), redirect_stderr(errors):
                result = main([str(package), '--games-path', str(root), '--language', 'en'])
            self.assertEqual(result, 2)
            extract.assert_not_called()
            self.assertNotIn('CONFIRM_DOWNGRADE', output.getvalue())
            self.assertIn('--allow-downgrade', errors.getvalue())
            self.assertEqual((game / 'sce_sys/param.sfo').read_bytes(), before)
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(FullPKG, 'extract') as extract, redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([str(package), '--games-path', str(root), '--language', 'en', '--gui']), 2)
            extract.assert_not_called()
            confirmation = next(line for line in output.getvalue().splitlines() if line.startswith('CONFIRM_DOWNGRADE '))
            self.assertEqual(json.loads(confirmation.split(' ', 1)[1]), {'installed': '01.10', 'incoming': '01.09'})
            self.assertNotIn('--allow-downgrade', errors.getvalue())
            with patch.object(FullPKG, 'extract', return_value=game) as extract, redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(package), '--games-path', str(root), '--allow-downgrade']), 0)
            extract.assert_called_once()

    def test_cli_wrong_game_never_extracts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install_game(root, TITLE_ID='CUSA99999')
            package = metadata_pkg(root / 'patch.pkg', CATEGORY='gp', CONTENT_ID=CONTENT_ID)
            with patch.object(FullPKG, 'extract') as extract, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(package), '--games-path', str(root), '--allow-downgrade']), 1)
            extract.assert_not_called()
