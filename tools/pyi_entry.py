"""Entry point for the PyInstaller build. Not used by anything else.

src/mapstruct/__main__.py cannot serve as the frozen entry script. PyInstaller runs the entry as
a TOP-LEVEL script called __main__, with no parent package, so the relative `from .core import
main` inside it raises

    ImportError: attempted relative import with no known parent package

which is a build that succeeds and a binary that dies on first run. It is reproducible without
PyInstaller at all - `python3 src/mapstruct/__main__.py` fails the same way - and it is why
.github/workflows/build.yml executes each binary before uploading it.

So the frozen build starts here instead, and imports the package by absolute name.
"""
import sys

from mapstruct.core import main

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
