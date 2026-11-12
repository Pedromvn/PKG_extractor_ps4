# PS4 PKG Extractor

**English** | [Português](README.pt-BR.md)

A PS4 PKG extractor written in Python, featuring a Portuguese/English desktop
interface, a command-line interface, a Linux AppImage and a Windows executable.

Reconstructs files from fake PKGs (FPKGs) supported by the shadPS4 0.7.0
extraction flow, preserving the `CUSAxxxxx/` directory layout. Supports
multi-block PFS directories, package metadata and updates installed into the
base game or a separate update folder.

## Download the application

Download the files from the [latest release](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest):

| Platform | Download |
| --- | --- |
| Linux x86_64 | [PS4PkgExtractor-x86_64.AppImage](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest/download/PS4PkgExtractor-x86_64.AppImage) |
| Windows 10/11 x64 | [PS4PkgExtractor-windows-x64.exe](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest/download/PS4PkgExtractor-windows-x64.exe) |
| SHA-256 checksums | [SHA256SUMS.txt](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest/download/SHA256SUMS.txt) |

On Windows, run the `.exe`; Python installation is not required. On Linux:

```bash
chmod +x PS4PkgExtractor-x86_64.AppImage
./PS4PkgExtractor-x86_64.AppImage
# If FUSE is unavailable:
APPIMAGE_EXTRACT_AND_RUN=1 ./PS4PkgExtractor-x86_64.AppImage
```

Use the **Idioma / Language** selector at the top of the window to switch
between **Português** and **English**. The preference is saved in your user
configuration folder, outside the executable. Buttons, dialogs, messages and
progress follow the selected language. Switching is available while no
operation is running; previously displayed log entries are preserved.

## Requirements and source installation

- Python **3.11 or newer**.
- `cryptography`, installed through the requirements file.
- Tcl/Tk for the GUI. Linux packages are commonly named `python3-tk` on
  Debian/Ubuntu or `tk` on Arch/CachyOS.

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.
The CLI works without Tcl/Tk. Both packaged applications include their own
Python and GUI dependencies.

## Graphical interface

With the virtual environment active:

```bash
python pkgextract_gui.py
```

On Linux, `./run_gui.sh` is also available. Select the PKG and games folder,
then click **Install**. **Analyze** displays package metadata without requiring
an output folder. The file picker starts beside the application or the last
selected PKG and displays all files by default.

## Command line

```bash
# List outer package metadata in English.
python pkgextract.py game.pkg --list --language en

# List all files inside the PFS too.
python pkgextract.py game.pkg --list-files --language en

# Validate every block without writing an extraction.
python pkgextract.py game.pkg --verify --language en

# Extract directly into dump/.
python pkgextract.py game.pkg --output dump --language en

# Install into games/CUSAxxxxx/.
python pkgextract.py game.pkg --games-path games --language en

# Equivalent installation using --output.
python pkgextract.py game.pkg --install --output games --language en

# English help (Portuguese is the default).
python pkgextract.py --help --language en
```

`--verify` decrypts and decompresses the blocks and checks their structure
and sizes. It does not validate signatures or compare hashes with another dump.

## Updates

The base game must already contain `eboot.bin` and `sce_sys/param.sfo`.
Update packages are detected automatically.

```bash
# Replace the corresponding installed game files.
python pkgextract.py update.pkg --games-path games --language en

# Write the patch into games/CUSAxxxxx-UPDATE/.
python pkgextract.py update.pkg --games-path games --separate-update --language en
```

Each file is written to a temporary file and replaced on completion.
Completed files remain in the destination if a later file fails; the entire
installation is not a single transaction.

## Build a Linux AppImage

Building requires Linux x86_64, Python with Tcl/Tk, and packaging tools.
Install the build dependencies and download `appimagetool` from its
[official releases](https://github.com/AppImage/appimagetool/releases).

```bash
python -m pip install -r requirements-build.txt
chmod +x /path/to/appimagetool
APPIMAGETOOL=/path/to/appimagetool ./build_appimage.sh
```

The default output is `PS4PkgExtractor-x86_64.AppImage`.

| Environment variable | Purpose |
| --- | --- |
| `APPIMAGETOOL` | Path to the executable packaging tool. |
| `APPIMAGE_RUNTIME` | Optional local runtime from the [official project](https://github.com/AppImage/type2-runtime/releases). |
| `OUTPUT_APPIMAGE` | Full output path; its parent directory must exist. |
| `SKIP_DEPENDENCIES=1` | Reuse installed build-environment dependencies. |
| `TK_ROOT` | Locally extracted Tcl/Tk libraries, without system installation. |

`TK_ROOT` expects `usr/lib/x86_64-linux-gnu` and
`usr/share/tcltk/{tcl8.6,tk8.6}`. The script also discovers local dependencies
under `build-appimage/{appimagetool,runtime-x86_64,tkroot}`. These separately
obtained files are not included in the repository.

Build specifications are generated inside `build-appimage/`. The final
AppImage replaces an existing output only after packaging succeeds.

## Build the Windows executable

On Windows x64 with Python installed, run in PowerShell:

```powershell
./build_windows.ps1
```

The output is `build-windows/dist/PS4PkgExtractor-windows-x64.exe`, a single
executable containing Python, Tcl/Tk and the runtime dependencies. Build it
on Windows; this is not a cross-compilation setup.

The **Build executables** GitHub Actions workflow can also be run manually.
It tests the real GUI on both platforms, builds the applications, and tests
the packaged backend in Portuguese and English with a synthetic PKG.
Pushing a `v*` tag builds both platforms and publishes their executables and
checksums in a release after both jobs pass.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic data and require no games or local PKGs. GUI logic tests
need Tcl/Tk libraries but no display, and are skipped if the libraries are
unavailable. GitHub Actions installs Tcl/Tk and runs the suite on Python
3.11, 3.12, 3.13 and 3.14. Release builds additionally exercise the real GUI.

| File | Responsibility |
| --- | --- |
| `pkgextract.py` | CLI and installation. |
| `pkgextract_gui.py` | Tkinter desktop interface. |
| `pkg_full.py` | PKG reading, PFS indexing and extraction. |
| `pkg_crypto.py` | Cryptographic operations and decompression. |
| `pkg_i18n.py` | Translations and saved language preference. |
| `tests/` | Parser, CLI, GUI and packaging regression checks. |
| `build_appimage.sh` | Linux application build. |
| `build_windows.ps1` | Windows application build. |

## Compatibility

Supports fake PKGs compatible with the implemented extraction flow.
Commercial packages requiring other keys are unsupported. Successful
extraction does not guarantee compatibility with a particular emulator version.
DLC installation into a separate add-on folder is not implemented yet;
`--addons-path` is reserved for that future integration.

## License and credits

Licensed under **GPL-2.0-or-later**; see [LICENSE](LICENSE).
The parser and cryptographic flow reference the shadPS4 0.7.0 project.
See [NOTICE.md](NOTICE.md) for credits and references.
