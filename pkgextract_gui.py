#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tkinter front-end for the PS4 PKG extractor."""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parent
EXTRACTOR = ROOT / "pkgextract.py"
PKG_FILE_TYPES = (
    ("Todos os arquivos", "*"),
    ("PKG de PS4", ("*.pkg", "*.PKG", "*.Pkg", "*.pKg", "*.pkG", "*.PKg", "*.pKG", "*.PkG")),
)


def pkg_dialog_directory(current: str = "") -> Path:
    """Start beside the selected PKG or the original, external AppImage."""
    if current.strip():
        selected = Path(current.strip()).expanduser().resolve()
        directory = selected if selected.is_dir() else selected.parent
        if directory.is_dir():
            return directory
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        directory = Path(appimage).expanduser().resolve().parent
        if directory.is_dir():
            return directory
    return Path.cwd() if getattr(sys, "frozen", False) else ROOT


class ExtractorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PS4 PKG Extractor")
        self.geometry("920x680")
        self.minsize(820, 580)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self.operation_install = False
        self.started_at = 0.0
        self.progress_indeterminate = False
        self.last_progress = 0

        self.pkg = tk.StringVar()
        self.games_path = tk.StringVar()
        self.separate_update = tk.BooleanVar()
        self.status = tk.StringVar(value="Selecione um PKG para começar.")
        self._build_ui()
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(4, weight=1)

        ttk.Label(main, text="PS4 PKG Extractor", font=("TkDefaultFont", 17, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16)
        )
        ttk.Label(main, text="Arquivo PKG").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(main, textvariable=self.pkg).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(main, text="Selecionar", command=self._choose_pkg).grid(row=1, column=2, padx=(8, 0), pady=5)

        ttk.Label(main, text="Pasta de jogos").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(main, textvariable=self.games_path).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Button(main, text="Selecionar", command=self._choose_games).grid(row=2, column=2, padx=(8, 0), pady=5)

        ttk.Checkbutton(
            main,
            text="Separar patch em CUSAxxxxx-UPDATE (mantém o jogo original intacto)",
            variable=self.separate_update,
        ).grid(row=3, column=1, sticky="w", pady=(4, 10))

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
        self.inspect_button = ttk.Button(buttons, text="Analisar", command=self.inspect)
        self.inspect_button.pack(side="left", padx=(0, 8))
        self.install_button = ttk.Button(buttons, text="Instalar", command=self.install)
        self.install_button.pack(side="left")

    def _choose_pkg(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Selecionar PKG de PS4",
            initialdir=str(pkg_dialog_directory(self.pkg.get())),
            filetypes=PKG_FILE_TYPES,
        )
        if selected:
            self.pkg.set(selected)
            self.inspect()

    def _choose_games(self) -> None:
        selected = filedialog.askdirectory(title="Selecionar pasta de jogos do shadPS4")
        if selected:
            self.games_path.set(selected)

    def _command(self, install: bool) -> list[str]:
        pkg = Path(self.pkg.get().strip()).expanduser().resolve()
        games = Path(self.games_path.get().strip()).expanduser().resolve()
        if not pkg.is_file():
            raise ValueError("Selecione um arquivo PKG válido.")
        if install and (not self.games_path.get().strip() or not games.is_dir()):
            raise ValueError("Selecione uma pasta de jogos existente.")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--backend", str(pkg)]
        else:
            command = [sys.executable, "-u", str(EXTRACTOR), str(pkg)]
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
        if not messagebox.askyesno(
            "Confirmar instalação",
            "A extração pode ocupar dezenas de GB e substituir arquivos existentes. Continuar?",
        ):
            return
        self._run(True)

    def _run(self, install: bool) -> None:
        if self.running:
            return
        try:
            command = self._command(install)
        except ValueError as error:
            messagebox.showerror("Dados inválidos", str(error))
            return
        self.running = True
        self.operation_install = install
        self.started_at = time.monotonic()
        self.last_progress = 0
        self.inspect_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.status.set("Analisando..." if not install else "Extraindo, aguarde...")
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
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.events.put(("log", line))
            result = process.wait()
            self.events.put(("done", str(result)))
        except OSError as error:
            self.events.put(("error", str(error)))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
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
                        percent = current_value * 100 // total_value if total_value else 0
                        eta = ""
                        if current_value:
                            elapsed = time.monotonic() - self.started_at
                            remaining = elapsed * (total_value - current_value) / current_value
                            eta = f" - restante ~{self._format_duration(remaining)}"
                        self.status.set(f"{message} - {percent}%{eta}")
                    else:
                        self._append(value)
                elif kind == "done":
                    self.running = False
                    self.progress.stop()
                    self.progress_indeterminate = False
                    self.inspect_button.configure(state="normal")
                    self.install_button.configure(state="normal")
                    success = value == "0"
                    if success:
                        self.progress.configure(mode="determinate", maximum=1, value=1)
                    self.status.set("Concluído." if success else "Falhou.")
                    if success and self.operation_install:
                        messagebox.showinfo("Concluído", "Operação finalizada.")
                    elif not success:
                        messagebox.showerror("Erro", "A operação falhou. Consulte o log.")
                else:
                    self.running = False
                    self.progress.stop()
                    self.progress_indeterminate = False
                    self.inspect_button.configure(state="normal")
                    self.install_button.configure(state="normal")
                    self.status.set("Falhou.")
                    self._append("ERRO: " + value + "\n")
                    messagebox.showerror("Erro", value)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"{seconds}s"
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}min {seconds:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}min"

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    if "--backend" in sys.argv:
        from pkgextract import main as backend_main

        raise SystemExit(backend_main(sys.argv[sys.argv.index("--backend") + 1:]))
    ExtractorApp().mainloop()
