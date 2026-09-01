#!/usr/bin/env python3
"""Bundle mapstruct into one runnable file: dist/mapstruct.pyz

    python3 tools/build_pyz.py

The result runs anywhere Python 3.7+ is installed, on any OS:

    python3 mapstruct.pyz map.scx

On Windows, once .pyz is associated with Python, map files can be dropped straight onto it.

This uses only the standard library, deliberately. A packaging step that needs pip is a packaging
step that fails on someone else's machine, and avoiding exactly that is the point of this tool.
Unlike the .exe, a .pyz is platform-independent - there is one of them, not one per OS.
"""
import os
import shutil
import tempfile
import zipapp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, 'src', 'mapstruct')


def main():
    dist = os.path.join(ROOT, 'dist')
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, 'mapstruct.pyz')

    with tempfile.TemporaryDirectory() as stage:
        target = os.path.join(stage, 'mapstruct')
        shutil.copytree(PKG, target, ignore=shutil.ignore_patterns('__pycache__'))
        for fn in ('LICENSE', 'NOTICE.md'):
            src = os.path.join(ROOT, fn)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(target, fn))
        with open(os.path.join(stage, '__main__.py'), 'w') as f:
            f.write('import sys\n'
                    'from mapstruct.core import main\n'
                    'sys.exit(main(sys.argv[1:]))\n')
        zipapp.create_archive(stage, out, interpreter='/usr/bin/env python3')

    os.chmod(out, 0o755)
    print('%s  (%.0f KB)' % (out, os.path.getsize(out) / 1024.0))


if __name__ == '__main__':
    main()
