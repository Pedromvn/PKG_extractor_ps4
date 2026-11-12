# SPDX-License-Identifier: GPL-2.0-or-later
"""GUI logic tests use stand-ins for widgets and require no display server."""
import queue
import tempfile
import unittest
from contextlib import chdir
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    import tkinter
    from pkgextract_gui import ExtractorApp, PKG_FILE_TYPES, pkg_dialog_directory, backend_options
except ImportError:
    ExtractorApp = None


def variable(value):
    return SimpleNamespace(get=lambda: value)


@unittest.skipIf(ExtractorApp is None, 'Tcl/Tk libraries unavailable')
class GUICommandTests(unittest.TestCase):
    def test_frozen_windows_uses_embedded_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            pkg = Path(folder) / 'game.pkg'
            pkg.touch()
            state = SimpleNamespace(language='en', pkg=variable(str(pkg)), games_path=variable(''))
            with patch('pkgextract_gui.sys.platform', 'win32'), patch('pkgextract_gui.sys.frozen', True, create=True):
                command = ExtractorApp._command(state, False)
            self.assertEqual(Path(command[0]).name, 'PS4PkgExtractor-backend.exe')
            self.assertEqual(Path(command[0]).parent.name, 'backend')
            self.assertIn('--list', command)

    def test_english_selection_and_backend_language(self):
        with tempfile.TemporaryDirectory() as folder:
            pkg = Path(folder) / 'game.pkg'
            pkg.touch()
            state = SimpleNamespace(language='en', pkg=Mock(), inspect=Mock(), games_path=variable(''))
            state.pkg.get.return_value = str(pkg)
            with patch('pkgextract_gui.filedialog.askopenfilename', return_value=str(pkg)) as dialog:
                ExtractorApp._choose_pkg(state)
            self.assertEqual(dialog.call_args.kwargs['title'], 'Select a PS4 PKG')
            self.assertEqual(dialog.call_args.kwargs['filetypes'][0][0], 'All files')
            command = ExtractorApp._command(state, False)
            self.assertEqual(command[command.index('--language') + 1], 'en')

    def test_windows_worker_uses_utf8_without_console_window(self):
        with patch('pkgextract_gui.sys.platform', 'win32'), patch('pkgextract_gui.subprocess.CREATE_NO_WINDOW', 0x08000000, create=True):
            options = backend_options()
        self.assertEqual(options['encoding'], 'utf-8')
        self.assertEqual(options['env']['PYTHONUTF8'], '1')
        self.assertEqual(options['creationflags'], 0x08000000)

    def test_dialog_opens_beside_external_appimage(self):
        with tempfile.TemporaryDirectory(prefix='PKG com espaços ') as folder:
            with patch.dict('os.environ', {'APPIMAGE': str(Path(folder) / 'Extractor.AppImage')}):
                self.assertEqual(pkg_dialog_directory(), Path(folder).resolve())

    def test_dialog_reopens_selected_pkg_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(pkg_dialog_directory(str(Path(folder) / 'game.pkg')), Path(folder).resolve())

    def test_dialog_shows_all_files_and_selects_pkg(self):
        with tempfile.NamedTemporaryFile(suffix='.pkg') as pkg:
            state = SimpleNamespace(pkg=Mock(), inspect=Mock())
            state.pkg.get.return_value = pkg.name
            with patch('pkgextract_gui.filedialog.askopenfilename', return_value=pkg.name) as dialog:
                ExtractorApp._choose_pkg(state)
            self.assertEqual(dialog.call_args.kwargs['initialdir'], str(Path(pkg.name).parent.resolve()))
            self.assertEqual(dialog.call_args.kwargs['filetypes'][0], ('Todos os arquivos', '*'))
            state.pkg.set.assert_called_once_with(pkg.name)
            state.inspect.assert_called_once()

    def test_tcl_glob_finds_pkg_with_spaces_and_mixed_case(self):
        interpreter = tkinter.Tcl()
        with tempfile.TemporaryDirectory() as folder:
            names = ['Jogo com espaços.pkg', 'Upper.PKG', 'Mixed.PkG', 'sem_extensao']
            for name in names:
                (Path(folder) / name).touch()
            all_pattern = PKG_FILE_TYPES[0][1]
            found = interpreter.call('glob', '-tails', '-directory', folder, '--', all_pattern)
            self.assertEqual(set(found), set(names))
            pkg_patterns = PKG_FILE_TYPES[1][1]
            found = interpreter.call('glob', '-tails', '-directory', folder, '--', *pkg_patterns)
            self.assertEqual(set(found), set(names[:-1]))

    def test_relative_pkg_becomes_absolute_for_backend(self):
        with tempfile.TemporaryDirectory() as folder:
            pkg = Path(folder) / 'game.pkg'
            pkg.touch()
            state = SimpleNamespace(pkg=variable('game.pkg'), games_path=variable(''), separate_update=variable(False))
            with chdir(folder):
                command = ExtractorApp._command(state, False)
            self.assertIn(str(pkg.resolve()), command)

    def test_inspect_does_not_require_games_folder(self):
        with tempfile.NamedTemporaryFile(suffix='.pkg') as pkg:
            state = SimpleNamespace(pkg=variable(pkg.name), games_path=variable(''), separate_update=variable(False))
            self.assertIn('--list', ExtractorApp._command(state, False))
            with self.assertRaises(ValueError):
                ExtractorApp._command(state, True)

    def test_update_option_is_forwarded(self):
        with tempfile.TemporaryDirectory() as games, tempfile.NamedTemporaryFile(suffix='.pkg') as pkg:
            state = SimpleNamespace(pkg=variable(pkg.name), games_path=variable(games), separate_update=variable(True))
            command = ExtractorApp._command(state, True)
            self.assertIn('--separate-update', command)
            self.assertIn('--games-path', command)

    def test_progress_stops_animation_and_does_not_move_backwards(self):
        events = queue.Queue()
        for value in [100, 200, 190, 1000]:
            events.put(('log', f'PROGRESS {value} 1000 Extraindo'))
        widget = Mock()
        state = SimpleNamespace(events=events, progress=widget, progress_indeterminate=True, last_progress=0,
                                status=Mock(), started_at=0.0, after=Mock(), _poll_events=Mock(),
                                _format_duration=lambda _: '0s')
        ExtractorApp._poll_events(state)
        values = [call.kwargs['value'] for call in widget.configure.call_args_list]
        self.assertEqual(values, [100, 200, 200, 1000])
        widget.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
