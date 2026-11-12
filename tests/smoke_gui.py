# SPDX-License-Identifier: GPL-2.0-or-later
"""Open real Tk widgets, switch languages and run the real backend (Xvfb on Linux)."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pkg_fixture import metadata_pkg
from pkgextract_gui import ExtractorApp

with tempfile.TemporaryDirectory(prefix='pkg-gui-') as folder:
    os.environ['XDG_CONFIG_HOME'] = folder
    os.environ['APPDATA'] = folder
    app = ExtractorApp()
    app.withdraw()
    try:
        for label, expected in [('English', 'Analyze'), ('Português', 'Analisar')]:
            app.language_choice.set(label)
            app._change_language()
            app.update_idletasks()
            assert app._textvars['Analisar'].get() == expected
        app.language_choice.set('English')
        app._change_language()
        pkg = metadata_pkg(Path(folder) / 'Jogo com acentuação.pkg')
        app.pkg.set(str(pkg))
        app.inspect()
        deadline = time.monotonic() + 30
        while app.running and time.monotonic() < deadline:
            app.update()
            time.sleep(0.02)
        assert not app.running, 'Backend did not finish'
        assert app.status.get() == 'Completed.', app.status.get()
        assert 'Type: GAME/DLC' in app.log.get('1.0', 'end')
        print('GUI smoke test passed (language switch, saved preference, real backend).')
    finally:
        app.destroy()
