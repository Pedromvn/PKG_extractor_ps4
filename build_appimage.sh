#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build-appimage"
VENV="$BUILD/venv"
APPDIR="$BUILD/PS4PkgExtractor.AppDir"
APPIMAGETOOL="${APPIMAGETOOL:-$BUILD/appimagetool}"
OUTPUT_APPIMAGE="${OUTPUT_APPIMAGE:-$ROOT/PS4PkgExtractor-x86_64.AppImage}"
if [[ -z "${TK_ROOT:-}" && -d "$BUILD/tkroot" ]]; then
  TK_ROOT="$BUILD/tkroot"
fi
if [[ -z "${APPIMAGE_RUNTIME:-}" && -f "$BUILD/runtime-x86_64" ]]; then
  APPIMAGE_RUNTIME="$BUILD/runtime-x86_64"
fi

if [[ -n "${TK_ROOT:-}" ]]; then
  export TCL_LIBRARY="$TK_ROOT/usr/share/tcltk/tcl8.6"
  export TK_LIBRARY="$TK_ROOT/usr/share/tcltk/tk8.6"
  export LD_LIBRARY_PATH="$TK_ROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

python3 -m venv "$VENV"
if [[ "${SKIP_DEPENDENCIES:-0}" != 1 ]]; then
  "$VENV/bin/pip" install -r "$ROOT/requirements-build.txt"
fi
"$VENV/bin/pyinstaller" --noconfirm --clean --onedir --name PS4PkgExtractor \
  --hidden-import pkg_full --hidden-import pkg_crypto \
  --hidden-import pkg_i18n \
  --specpath "$BUILD" \
  --distpath "$BUILD/dist" --workpath "$BUILD/work" \
  "$ROOT/pkgextract_gui.py"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -a "$BUILD/dist/PS4PkgExtractor/." "$APPDIR/usr/bin/"
cp "$ROOT/README.md" "$APPDIR/README.md"
cp "$ROOT/README.pt-BR.md" "$APPDIR/README.pt-BR.md"
cp "$ROOT/LICENSE" "$ROOT/NOTICE.md" "$APPDIR/"
cp "$ROOT/AppRun" "$APPDIR/AppRun"
cp "$ROOT/PS4PkgExtractor.desktop" "$APPDIR/PS4PkgExtractor.desktop"
cp "$ROOT/icon.svg" "$APPDIR/PS4PkgExtractor.svg"
ln -s PS4PkgExtractor.svg "$APPDIR/.DirIcon"
chmod +x "$APPDIR/AppRun"

if [[ ! -x "$APPIMAGETOOL" ]]; then
  printf '%s\n' "Baixe appimagetool e defina APPIMAGETOOL=/caminho/appimagetool." >&2
  exit 1
fi
# Build beside the destination and rename only after successful packaging.
# This also permits rebuilding while an older AppImage is still open.
TEMP_APPIMAGE="$(mktemp "${OUTPUT_APPIMAGE}.XXXXXXXX.AppImage")"
trap 'rm -f "$TEMP_APPIMAGE"' EXIT
RUNTIME_ARGS=()
if [[ -n "${APPIMAGE_RUNTIME:-}" ]]; then
  RUNTIME_ARGS=(--runtime-file "$APPIMAGE_RUNTIME")
fi
APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "${RUNTIME_ARGS[@]}" "$APPDIR" "$TEMP_APPIMAGE"
chmod +x "$TEMP_APPIMAGE"
mv -f "$TEMP_APPIMAGE" "$OUTPUT_APPIMAGE"
printf 'AppImage criado: %s\n' "$OUTPUT_APPIMAGE"
