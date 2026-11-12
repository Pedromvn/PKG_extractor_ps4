# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the real packaged GUI subsystem, embedded worker and window startup."""
import ctypes
import os
import struct
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

executable = Path(sys.argv[1]).resolve()
with executable.open('rb') as source:
    source.seek(0x3c)
    pe_offset = struct.unpack('<I', source.read(4))[0]
    source.seek(pe_offset)
    assert source.read(4) == b'PE\0\0'
    source.seek(pe_offset + 24 + 68)
    subsystem = struct.unpack('<H', source.read(2))[0]
assert subsystem == 2, f'GUI must use Windows subsystem (2), got {subsystem}'
archive = CArchiveReader(str(executable))
embedded = {name.replace('\\', '/') for name in archive.toc}
assert 'backend/PS4PkgExtractor-backend.exe' in embedded, 'Embedded worker missing'
assert any(name.startswith('backend/_internal/') and name.endswith('.dll') for name in embedded)

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

with tempfile.TemporaryDirectory(prefix='pkg-windowed-') as folder:
    process = subprocess.Popen([str(executable)], env=dict(os.environ, APPDATA=folder))
    handles = []
    @callback_type
    def find_window(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, len(title))
        if not title.value.startswith('PS4 PKG Extractor'):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return True
        try:
            name = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(name))
            if kernel32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)) and Path(name.value).resolve() == executable:
                handles.append(hwnd)
        finally:
            kernel32.CloseHandle(handle)
        return True
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not handles:
            assert process.poll() is None, f'GUI exited early with code {process.returncode}'
            user32.EnumWindows(find_window, 0)
            time.sleep(0.1)
        assert handles, 'Packaged GUI window did not appear'
        for hwnd in handles:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, only our own app.
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], check=False)
print('Windowed executable verified: GUI subsystem, embedded worker and real window startup.')
