#!/usr/bin/env python3
"""Bake the tileset walkability/height tables into src/mapstruct/core.py.

mapstruct is meant to run with nothing installed - no StarCraft, no packages, no compiler - so
the tables it needs travel inside it. Only cv5 (tile id -> megatile) and vf4 (per-minitile
walkable / mid / high flags) are included: those are the functional data the structure view is
made of. None of the ARTWORK is taken - no vr4, no vx4, no palette - so nothing here can draw the
game's terrain, only describe it.

    tools/build_tileset_blob.py <dir-of-tileset-files>

<dir> is anywhere holding the tileset's .cv5 and .vf4 files - a StarCraft installation's
extracted tileset directory, for instance. Only those two extensions are read; no artwork is
touched.

Run this again when a patch adds tiles, and ship the new mapstruct.
"""
import base64
import lzma
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, 'src', 'mapstruct')
sys.path.insert(0, PKG)

NAMES = ('badlands', 'platform', 'install', 'ashworld', 'jungle', 'Desert', 'Ice', 'Twilight')


def loader(src):
    """Read cv5/vf4 out of a directory of loose tileset files.

    Deliberately only the loose-file form. Pulling them out of a StarCraft installation's MPQ
    archives is a job for the bw-decomp repository this was extracted from; here, the input is
    whatever files you already have.
    """
    if not src:
        raise SystemExit(__doc__.strip().splitlines()[2].strip())
    loose = {}
    for base, _d, files in os.walk(src):
        for fn in files:
            loose[fn.lower()] = os.path.join(base, fn)

    def get(name, ext):
        hit = loose.get(('%s.%s' % (name, ext)).lower())
        return open(hit, 'rb').read() if hit else None
    return get


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    get = loader(src)

    index, blobs = [], []
    for name in NAMES:
        cv5 = get(name, 'cv5')
        vf4 = get(name, 'vf4')
        if not cv5 or not vf4:
            print('  %-10s MISSING - skipped' % name)
            continue
        index.append((name, len(cv5), len(vf4)))
        blobs.append(cv5)
        blobs.append(vf4)
        print('  %-10s cv5 %7d  vf4 %7d  (%d groups)' % (name, len(cv5), len(vf4), len(cv5) // 52))
    if not index:
        raise SystemExit('no tilesets found')

    head = struct.pack('<H', len(index))
    for name, cl, vl in index:
        head += struct.pack('<B', len(name)) + name.encode('ascii') + struct.pack('<II', cl, vl)
    raw = head + b''.join(blobs)
    packed = base64.b64encode(lzma.compress(raw, preset=9)).decode('ascii')
    print('\n%d tilesets, %d bytes raw -> %d bytes base64+lzma' % (len(index), len(raw), len(packed)))

    dest = os.path.join(PKG, 'core.py')
    lines = open(dest, encoding='utf-8').read().splitlines(True)

    # The assignment spans many lines once it holds a real blob, so find where it starts and
    # where it ends rather than replacing a single line - doing the latter leaves the previous
    # blob's continuation lines behind and produces a file that will not parse.
    first = next((i for i, l in enumerate(lines) if l.startswith('TILESET_BLOB')), None)
    if first is None:
        raise SystemExit('TILESET_BLOB assignment not found in core.py')
    last = next((i for i in range(first, len(lines))
                 if lines[i].startswith('TILESET_NAMES')), None)
    if last is None:
        raise SystemExit('could not find the end of the TILESET_BLOB assignment')

    body = ('TILESET_BLOB = (\n'
            + ''.join('    "%s"\n' % packed[j:j + 100] for j in range(0, len(packed), 100))
            + ')   # regenerate with tools/build_tileset_blob.py\n\n')
    lines[first:last] = [body]
    open(dest, 'w', encoding='utf-8').write(''.join(lines))

    print('baked into %s' % dest)


if __name__ == '__main__':
    main()
