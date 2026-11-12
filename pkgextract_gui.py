#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Bilingual Tkinter front-end for the PS4 PKG extractor."""
from __future__ import annotations

import os
import json
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pkg_i18n import LANGUAGES, VERSION, load_settings, save_settings, save_language, tr

ROOT = Path(__file__).resolve().parent
EXTRACTOR = ROOT / "pkgextract.py"
PKG_PATTERNS = ("*.pkg", "*.PKG", "*.Pkg", "*.pKg", "*.pkG", "*.PKg", "*.pKG", "*.PkG")


def pkg_file_types(language="pt"):
    return ((tr("Todos os arquivos", language), "*"), (tr("PKG de PS4", language), PKG_PATTERNS))


PKG_FILE_TYPES = pkg_file_types()


def frozen_backend() -> Path:
    if sys.platform == 'win32':
        return ROOT / 'backend' / 'PS4PkgExtractor-backend.exe'
    return Path(sys.executable)


def existing_directory(value: str) -> str:
    try:
        path = Path(value).expanduser()
        return str(path.resolve()) if value and path.is_dir() else ''
    except (OSError, ValueError):
        return ''


def pkg_dialog_directory(current: str = "", remembered: str = "") -> Path:
    """Start beside the selected PKG or the original external executable."""
    if current.strip():
        selected = Path(current.strip()).expanduser().resolve()
        directory = selected if selected.is_dir() else selected.parent
        if directory.is_dir():
            return directory
    previous = existing_directory(remembered)
    if previous:
        return Path(previous)
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        directory = Path(appimage).expanduser().resolve().parent
        if directory.is_dir():
            return directory
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT


def backend_options() -> dict:
    """Keep the worker UTF-8 and avoid flashing a Windows console window."""
    options = {"env": dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"),
               "encoding": "utf-8", "errors": "replace", "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return options


class ExtractorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"PS4 PKG Extractor {VERSION}")
        self.geometry("960x680")
        self.minsize(880, 580)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self.operation_install = False
        self.started_at = 0.0
        self.progress_indeterminate = False
        self.last_progress = 0
        preferences = load_settings()
        self.language = preferences['language']
        self._last_pkg_dir = existing_directory(preferences.get('pkg_directory', ''))
        self._pending_downgrade = None
        self._current_command = []
        self._textvars = {}
        self._status_key = "Selecione um PKG para começar."
        self.language_choice = tk.StringVar(value=LANGUAGES[self.language])
        self.pkg = tk.StringVar()
        self.games_path = tk.StringVar(value=preferences.get('games_directory', ''))
        self.separate_update = tk.BooleanVar()
        self.status = tk.StringVar(value=tr(self._status_key, self.language))
        self._build_ui()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(100, self._poll_events)

    def _save_preferences(self):
        values = {'language': self.language}
        pkg = self.pkg.get().strip()
        if pkg:
            try:
                if Path(pkg).expanduser().is_file():
                    self._last_pkg_dir = str(Path(pkg).expanduser().resolve().parent)
            except (OSError, ValueError):
                pass
        if self._last_pkg_dir:
            values['pkg_directory'] = self._last_pkg_dir
        games = self.games_path.get().strip()
        if not games or existing_directory(games):
            values['games_directory'] = existing_directory(games)
        save_settings(**values)

    def _on_close(self):
        if self.running:
            messagebox.showinfo(tr('Operação em andamento', self.language),
                                tr('Aguarde a conclusão da operação antes de fechar o aplicativo.', self.language),
                                parent=self)
            return
        self._save_preferences()
        self.destroy()

    def _text(self, key):
        if key not in self._textvars:
            self._textvars[key] = tk.StringVar(value=tr(key, self.language))
        return self._textvars[key]

    def _set_status(self, key):
        self._status_key = key
        self.status.set(tr(key, self.language))

    def _change_language(self, _event=None):
        if self.running:
            return
        selected = self.language_choice.get()
        self.language = next((key for key, label in LANGUAGES.items() if label == selected), "pt")
        for key, variable in self._textvars.items():
            variable.set(tr(key, self.language))
        self.status.set(tr(self._status_key, self.language))
        save_language(self.language)

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(4, weight=1)
        ttk.Label(main, text="PS4 PKG Extractor", font=("TkDefaultFont", 17, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))
        languages = ttk.Frame(main)
        languages.grid(row=0, column=2, sticky="e", pady=(0, 16))
        ttk.Label(languages, textvariable=self._text("Idioma")).pack(side="left", padx=(0, 8))
        self.language_selector = ttk.Combobox(languages, textvariable=self.language_choice,
                                             values=tuple(LANGUAGES.values()), state="readonly", width=12)
        self.language_selector.pack(side="left")
        self.language_selector.bind('<<ComboboxSelected>>', self._change_language)

        ttk.Label(main, textvariable=self._text("Arquivo PKG")).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        pkg_entry = ttk.Entry(main, textvariable=self.pkg)
        pkg_entry.grid(row=1, column=1, sticky="ew", pady=5)
        pkg_button = ttk.Button(main, textvariable=self._text("Selecionar"), command=self._choose_pkg)
        pkg_button.grid(row=1, column=2, padx=(8, 0), pady=5)
        ttk.Label(main, textvariable=self._text("Pasta de jogos")).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        games_entry = ttk.Entry(main, textvariable=self.games_path)
        games_entry.grid(row=2, column=1, sticky="ew", pady=5)
        games_button = ttk.Button(main, textvariable=self._text("Selecionar"), command=self._choose_games)
        games_button.grid(row=2, column=2, padx=(8, 0), pady=5)
        update_check = ttk.Checkbutton(main, textvariable=self._text("Separar patch em CUSAxxxxx-UPDATE (mantém o jogo original intacto)"),
                                       variable=self.separate_update)
        update_check.grid(row=3, column=1, columnspan=2, sticky="w", pady=(4, 10))
        self._input_widgets = [pkg_entry, pkg_button, games_entry, games_button, update_check]
        self.log = tk.Text(main, height=12, state="disabled", wrap="word")
        self.log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(4, 10))
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=4, column=3, sticky="ns", pady=(4, 10))
        self.log.configure(yscrollcommand=scrollbar.set)
        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(main, textvariable=self.status).grid(row=6, column=0, columnspan=2, sticky="w")
        buttons = ttk.Frame(main)
        buttons.grid(row=6, column=2, sticky="e")
        self.inspect_button = ttk.Button(buttons, textvariable=self._text("Analisar"), command=self.inspect)
        self.inspect_button.pack(side="left", padx=(0, 8))
        self.install_button = ttk.Button(buttons, textvariable=self._text("Instalar"), command=self.install)
        self.install_button.pack(side="left")

    def _choose_pkg(self) -> None:
        language = getattr(self, 'language', 'pt')
        selected = filedialog.askopenfilename(parent=self, title=tr("Selecionar PKG de PS4", language),
                                             initialdir=str(pkg_dialog_directory(self.pkg.get(), getattr(self, '_last_pkg_dir', ''))),
                                             filetypes=pkg_file_types(language))
        if selected:
            self.pkg.set(selected)
            self._save_preferences()
            self.inspect()

    def _choose_games(self) -> None:
        selected = filedialog.askdirectory(parent=self, title=tr("Selecionar pasta de jogos do shadPS4", self.language),
                                           initialdir=existing_directory(self.games_path.get()) or str(pkg_dialog_directory(remembered=self._last_pkg_dir)))
        if selected:
            self.games_path.set(selected)
            self._save_preferences()

    def _command(self, install: bool) -> list[str]:
        language = getattr(self, 'language', 'pt')
        pkg = Path(self.pkg.get().strip()).expanduser().resolve()
        games = Path(self.games_path.get().strip()).expanduser().resolve()
        if not pkg.is_file():
            raise ValueError(tr("Selecione um arquivo PKG válido.", language))
        if install and (not self.games_path.get().strip() or not games.is_dir()):
            raise ValueError(tr("Selecione uma pasta de jogos existente.", language))
        if getattr(sys, "frozen", False):
            command = [str(frozen_backend()), "--backend", str(pkg)]
        else:
            command = [sys.executable, "-u", str(EXTRACTOR), str(pkg)]
        command += ['--language', language, '--gui']
        if install:
            command += ["--install", "--games-path", str(games)]
            if self.separate_update.get():
                command.append("--separate-update")
        else:
            command.append("--list")
        return command

    def inspect(self) -> None:
        self._run(False)

    def install(self) -> None:
        if self.running:
            return
        if messagebox.askyesno(tr("Confirmar instalação", self.language),
                               tr("A extração pode ocupar dezenas de GB e substituir arquivos existentes. Continuar?", self.language), parent=self):
            self._run(True)

    def _run(self, install: bool) -> None:
        if self.running:
            return
        try:
            command = self._command(install)
        except ValueError as error:
            messagebox.showerror(tr("Dados inválidos", self.language), str(error), parent=self)
            return
        self._save_preferences()
        self._start_operation(command, install)

    def _start_operation(self, command: list[str], install: bool) -> None:
        if self.running:
            return
        self._current_command = list(command)
        self._pending_downgrade = None
        self.running = True
        self.operation_install = install
        self.started_at = time.monotonic()
        self.last_progress = 0
        self.inspect_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.language_selector.configure(state="disabled")
        for widget in self._input_widgets:
            widget.configure(state='disabled')
        self._set_status("Extraindo, aguarde..." if install else "Analisando...")
        if install:
            self.progress.configure(mode="indeterminate", value=0)
            self.progress.start(12)
            self.progress_indeterminate = True
        else:
            self.progress.configure(mode="determinate", maximum=1, value=0)
            self.progress_indeterminate = False
        self._append("$ " + " ".join(command) + "\n")
        threading.Thread(target=self._worker, args=(command,), daemon=True).start()

    def _worker(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       bufsize=1, **backend_options())
            assert process.stdout is not None
            with process.stdout:
                for line in process.stdout:
                    self.events.put(("log", line))
            self.events.put(("done", str(process.wait())))
        except OSError as error:
            self.events.put(("error", str(error)))

    def _finish(self, success):
        self.running = False
        self.progress.stop()
        self.progress_indeterminate = False
        self.inspect_button.configure(state="normal")
        self.install_button.configure(state="normal")
        self.language_selector.configure(state="readonly")
        for widget in self._input_widgets:
            widget.configure(state='normal')
        if success:
            self.progress.configure(mode="determinate", maximum=1, value=1)
        self._set_status("Concluído." if success else "Falhou.")

    def _poll_events(self) -> None:
        language = getattr(self, 'language', 'pt')
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    if value.startswith('CONFIRM_DOWNGRADE '):
                        try:
                            pending = json.loads(value.split(' ', 1)[1])
                            if isinstance(pending, dict) and all(isinstance(pending.get(key), str) for key in ('installed', 'incoming')):
                                self._pending_downgrade = {key: pending[key] for key in ('installed', 'incoming')}
                        except ValueError:
                            pass
                        continue
                    progress = re.match(r"PROGRESS (\d+) (\d+) (.*)", value.strip())
                    if progress:
                        current, total, message = progress.groups()
                        total_value = int(total)
                        if total_value <= 0:
                            continue
                        current_value = min(total_value, max(self.last_progress, int(current)))
                        self.last_progress = current_value
                        if self.progress_indeterminate:
                            self.progress.stop()
                            self.progress_indeterminate = False
                        self.progress.configure(mode="determinate", maximum=total_value, value=current_value)
                        percent = current_value * 100 // total_value
                        eta = ""
                        if current_value:
                            elapsed = time.monotonic() - self.started_at
                            remaining = elapsed * (total_value - current_value) / current_value
                            eta = tr(" - restante ~{duration}", language, duration=self._format_duration(remaining))
                        self.status.set(f"{message} - {percent}%{eta}")
                    else:
                        self._append(value)
                elif kind == "done":
                    success = value == "0"
                    self._finish(success)
                    if value == '2' and self._pending_downgrade:
                        pending = self._pending_downgrade
                        command = list(self._current_command)
                        self._pending_downgrade = None
                        self._set_status('Versão mais antiga')
                        accepted = messagebox.askyesno(tr('Versão mais antiga', language),
                            tr('Versão instalada: {installed}\nVersão do patch: {incoming}\n\nEste patch é mais antigo. Deseja continuar mesmo assim?', language, **pending),
                            parent=self, default=messagebox.NO)
                        if accepted:
                            self._start_operation(command + ['--allow-downgrade'], True)
                        else:
                            self._set_status('Operação cancelada.')
                        continue
                    if success and self.operation_install:
                        messagebox.showinfo(tr("Concluído", language), tr("Operação finalizada.", language), parent=self)
                    elif not success:
                        messagebox.showerror(tr("Erro", language), tr("A operação falhou. Consulte o log.", language), parent=self)
                else:
                    self._finish(False)
                    self._append(tr("ERRO: {error}\n", language, error=value))
                    messagebox.showerror(tr("Erro", language), value, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _format_duration(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"{seconds}s"
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return tr("{minutes}min {seconds:02d}s", self.language, minutes=minutes, seconds=seconds)
        hours, minutes = divmod(minutes, 60)
        return tr("{hours}h {minutes:02d}min", self.language, hours=hours, minutes=minutes)

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    # The Windows GUI has no standard streams. Its embedded worker owns the
    # backend entry point; Linux continues using this executable for both.
    windows_gui = sys.platform == 'win32' and getattr(sys, 'frozen', False)
    if "--backend" in sys.argv and not windows_gui:
        arguments = sys.argv[sys.argv.index("--backend") + 1:]
        from pkgextract import main as backend_main
        # Frozen Python may ignore PYTHONIOENCODING. The parent reads UTF-8
        # pipes on both platforms, including non-ASCII package paths.
        for stream in (sys.stdout, sys.stderr):
            if stream is not None and hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')
        raise SystemExit(backend_main(arguments))
    ExtractorApp().mainloop()
