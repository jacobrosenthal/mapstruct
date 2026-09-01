#!/usr/bin/env python3
"""Build a standalone executable that does not need Python installed.

    pip install pyinstaller
    python3 tools/build_exe.py

PyInstaller does NOT cross-compile. It freezes for the platform it runs on, so this produces:

    Windows   -> dist/mapstruct.exe        runs on Windows, no Python needed
    macOS     -> dist/mapstruct-macos      runs on macOS of the same architecture
    Linux     -> dist/mapstruct-linux      needs that glibc version or newer

To get all three without owning all three machines, let CI do it: .github/workflows/build.yml
runs this on windows-latest, macos-latest and ubuntu-latest and attaches the results to the
release. That is the intended way to ship the .exe.

Two things to warn users about, since neither binary is code-signed: Windows SmartScreen will
interrupt the first run, and macOS Gatekeeper will refuse it until the user allows it in
System Settings. Signing needs a paid certificate on both platforms.
"""
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUFFIX = {'Windows': '.exe', 'Darwin': '-macos', 'Linux': '-linux'}


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit('PyInstaller is not installed.  pip install pyinstaller')

    name = 'mapstruct' + SUFFIX.get(platform.system(), '')
    # NOT src/mapstruct/__main__.py: PyInstaller runs the entry as a top-level script with no
    # parent package, so its relative imports fail at run time. See tools/pyi_entry.py.
    entry = os.path.join(ROOT, 'tools', 'pyi_entry.py')

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--noconfirm',
        '--clean',
        '--name', name,
        # The package is under src/, and __main__.py imports it by name.
        '--paths', os.path.join(ROOT, 'src'),
        # mapstruct.core resolves its helpers at run time, so PyInstaller's import scan needs
        # telling about them explicitly or they are dropped from the bundle.
        '--hidden-import', 'mapstruct.mpyq',
        '--hidden-import', 'mapstruct.pkexplode',
        '--hidden-import', 'mapstruct.core',
        '--console',
        entry,
    ]
    print(' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    built = os.path.join(ROOT, 'dist', name)
    if not os.path.exists(built):
        raise SystemExit('PyInstaller reported success but %s is missing' % built)
    print('\n%s  (%.1f MB)' % (built, os.path.getsize(built) / 1048576.0))
    print('This binary runs on %s only - see the docstring.' % platform.system())

    # A build artifact left in build/ is just noise once the binary exists.
    shutil.rmtree(os.path.join(ROOT, 'build'), ignore_errors=True)


if __name__ == '__main__':
    main()
