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
            state = SimpleNamespace(language='en', pkg=Mock(), inspect=Mock(), games_path=variable(''), _save_preferences=Mock())
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
            state = SimpleNamespace(pkg=Mock(), inspect=Mock(), _save_preferences=Mock())
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

@unittest.skipIf(ExtractorApp is None, 'Tcl/Tk libraries unavailable')
class GUIInstallationTests(unittest.TestCase):
    def test_busy_close_leaves_application_and_operation_running(self):
        state = SimpleNamespace(running=True, language='en', _save_preferences=Mock(), destroy=Mock())
        with patch('pkgextract_gui.messagebox.showinfo') as info:
            ExtractorApp._on_close(state)
        state.destroy.assert_not_called()
        state._save_preferences.assert_not_called()
        self.assertTrue(state.running)
        self.assertIn('Wait for the operation', info.call_args.args[1])

    def test_idle_close_saves_preferences_and_closes(self):
        state = SimpleNamespace(running=False, language='en', _save_preferences=Mock(), destroy=Mock())
        ExtractorApp._on_close(state)
        state._save_preferences.assert_called_once()
        state.destroy.assert_called_once()

    def test_remembered_pkg_directory_precedes_application_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            previous = root / 'packages'
            previous.mkdir()
            with patch.dict('os.environ', {'APPIMAGE': str(root / 'App.AppImage')}):
                self.assertEqual(pkg_dialog_directory(remembered=str(previous)), previous.resolve())
                self.assertEqual(pkg_dialog_directory(remembered=str(root / 'missing')), root.resolve())

    def test_preferences_capture_valid_typed_paths(self):
        from pkg_i18n import load_settings
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pkg = root / 'game.pkg'
            pkg.touch()
            games = root / 'games'
            games.mkdir()
            state = SimpleNamespace(language='en', pkg=variable(str(pkg)), games_path=variable(str(games)), _last_pkg_dir='')
            with patch('pkg_i18n.settings_path', return_value=root / 'settings.json'):
                ExtractorApp._save_preferences(state)
                result = load_settings()
            self.assertEqual(result['pkg_directory'], str(root.resolve()))
            self.assertEqual(result['games_directory'], str(games.resolve()))
            self.assertEqual(result['language'], 'en')

    def test_downgrade_retries_only_the_confirmed_command(self):
        for accepted in (True, False):
            with self.subTest(accepted=accepted):
                events = queue.Queue()
                events.put(('log', 'CONFIRM_DOWNGRADE {"installed":"01.10","incoming":"01.09"}\n'))
                events.put(('done', '2'))
                original = ['extractor', 'original.pkg', '--install', '--games-path', 'original-games', '--language', 'en']
                state = SimpleNamespace(events=events, language='en', _pending_downgrade=None,
                    _current_command=original, _finish=Mock(), _start_operation=Mock(), _set_status=Mock(),
                    after=Mock(), _poll_events=Mock(), pkg=variable('different.pkg'))
                with patch('pkgextract_gui.messagebox.askyesno', return_value=accepted) as confirm:
                    ExtractorApp._poll_events(state)
                self.assertIn('Installed version: 01.10', confirm.call_args.args[1])
                self.assertEqual(confirm.call_args.kwargs['default'], 'no')
                state._finish.assert_called_once_with(False)
                if accepted:
                    state._start_operation.assert_called_once_with(original + ['--allow-downgrade'], True)
                else:
                    state._start_operation.assert_not_called()
                    state._set_status.assert_called_with('Operação cancelada.')


if __name__ == '__main__':
    unittest.main()
