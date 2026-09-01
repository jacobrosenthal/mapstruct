#!/usr/bin/env python3
"""Tests that need nothing but the package itself.

No StarCraft data and no map files - both are Blizzard's and neither can be committed - so these
check the parts that can be checked in isolation: the PKWARE decompressor against a published
known answer, the embedded tileset tables, terrain classification against a map built here in
memory, and that the PNG written is a real PNG.

The complementary test lives in the bw-decomp repository, where mapstruct's classification is
compared tile for tile against a decompilation of the game's own map loader on real maps. That is
the one that proves the RULES are right; this one proves the code implements them and still runs.

    python3 tests/test_mapstruct.py
"""
import os
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import mapstruct                       # noqa: E402
from mapstruct import core             # noqa: E402
from mapstruct import pkexplode        # noqa: E402

FAILS = []


def check(cond, what):
    if cond:
        print('  ok   %s' % what)
    else:
        print('  FAIL %s' % what)
        FAILS.append(what)


def test_pkexplode():
    print('pkexplode')
    # From blast.c's own header comment: this stream decompresses to "AIAIAIAIAIAIA". Ben
    # Rudiak-Gould's original example had the distance wrong; this is Mark Adler's correction,
    # which makes it a genuine third-party known answer rather than something generated here.
    got = pkexplode.explode(bytes([0x00, 0x04, 0x82, 0x24, 0x25, 0x8f, 0x80, 0x7f]))
    check(got == b'AIAIAIAIAIAIA', 'known-answer vector -> %r' % got)

    # A literal-coded stream (first byte 1) is the other mode, and a bad header must be rejected
    # rather than producing plausible garbage.
    for bad, why in ((b'\x02\x04rest', 'literal flag > 1'), (b'\x00\x03rest', 'dictionary < 4'),
                     (b'\x00\x07rest', 'dictionary > 6')):
        try:
            pkexplode.explode(bad)
            check(False, 'rejects %s' % why)
        except ValueError:
            check(True, 'rejects %s' % why)


def test_tilesets():
    print('tileset tables')
    check(bool(core.TILESET_BLOB), 'a tileset blob is compiled in')
    if not core.TILESET_BLOB:
        return
    ts = core.tilesets()
    check(len(ts) >= 5, 'decodes %d tilesets' % len(ts))
    for name, (cv5, vf4) in sorted(ts.items()):
        ok = len(cv5) % 52 == 0 and len(vf4) % 32 == 0 and len(cv5) and len(vf4)
        check(ok, '%-9s %d groups, %d megatiles' % (name, len(cv5) // 52, len(vf4) // 32))
    check(core.TILESET_NAMES[4] == 'jungle', 'tileset 4 is jungle (ERA ordering)')


def _chk(era, w, h, tile_ids):
    """A minimal CHK: the three chunks mapstruct reads."""
    def chunk(tag, payload):
        return tag + struct.pack('<I', len(payload)) + payload
    return (chunk(b'ERA ', struct.pack('<H', era))
            + chunk(b'DIM ', struct.pack('<HH', w, h))
            + chunk(b'MTXM', struct.pack('<%dH' % len(tile_ids), *tile_ids)))


def test_classify():
    print('classification')
    if not core.TILESET_BLOB:
        return
    w = h = 8
    # Tile id 0 is the tileset's first group, subtile 0 - a real, resolvable tile.
    flat = _chk(4, w, h, [0] * (w * h))
    ww, hh, flags, walk, unknown = core.classify(flat)
    check((ww, hh) == (w, h), 'reads DIM as %dx%d' % (ww, hh))
    check(unknown == 0, 'resolvable tiles are not reported unknown')
    check(len(walk) == w * 4 * h * 4, 'walkability is per eighth-of-a-tile (%d entries)' % len(walk))

    # A group far past the end of any tileset cannot be described, and must be REPORTED rather
    # than guessed at - a guess would invent walkable ground.
    bogus = _chk(4, w, h, [0x7ff << 4] * (w * h))
    _ww, _hh, bflags, bwalk, bunknown = core.classify(bogus)
    check(bunknown == w * h, 'unknown tiles are all counted (%d)' % bunknown)
    check(all(f & 0x80000000 for f in bflags), 'unknown tiles are flagged as such')
    check(not any(bwalk), 'unknown tiles are never called walkable')

    # The loader forces the bottom edge unwalkable and unbuildable - a hard border, not something
    # the tileset says. Without it the last two rows of every map are wrong.
    last_row = [walk[(h * 4 - 1) * (w * 4) + x] for x in range(w * 4)]
    check(not any(last_row), 'the bottom edge is patched unwalkable')
    check(all(flags[(h - 1) * w + x] & 0x800000 for x in range(w)),
          'the bottom edge is patched unbuildable')


def test_png():
    print('png output')
    if not core.TILESET_BLOB:
        return
    w = h = 8
    ww, hh, flags, walk, _u = core.classify(_chk(4, w, h, [0] * (w * h)))
    scale = 3
    iw, ih, rows = core.render(ww, hh, flags, walk, scale)
    check((iw, ih) == (w * 4 * scale, h * 4 * scale), 'image is %dx%d px' % (iw, ih))
    check(len(rows) == ih, 'one scanline per pixel row')
    check(all(len(r) == iw * 3 for r in rows), 'every scanline is 3 bytes per pixel')

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'out.png')
        core.write_png(p, iw, ih, rows)
        raw = open(p, 'rb').read()
        check(raw[:8] == b'\x89PNG\r\n\x1a\n', 'writes a PNG signature')
        # Walk the chunks and verify every CRC, which is what a decoder will do.
        i, seen, crc_ok = 8, [], True
        while i < len(raw):
            (ln,) = struct.unpack_from('>I', raw, i)
            tag = raw[i + 4:i + 8]
            body = raw[i + 8:i + 8 + ln]
            (want,) = struct.unpack_from('>I', raw, i + 8 + ln)
            if zlib.crc32(tag + body) & 0xffffffff != want:
                crc_ok = False
            seen.append(tag)
            i += 12 + ln
        check(crc_ok, 'every chunk CRC is correct')
        check(seen == [b'IHDR', b'IDAT', b'IEND'], 'chunks are %s' % [t.decode() for t in seen])
        (pw, ph, depth, colour) = struct.unpack_from('>IIBB', raw, 16)
        check((pw, ph, depth, colour) == (iw, ih, 8, 2), 'IHDR says %dx%d 8-bit truecolour' % (pw, ph))


def test_api():
    print('public api')
    for name in ('structure_png', 'classify', 'read_chk', 'render', 'write_png'):
        check(hasattr(mapstruct, name), 'mapstruct.%s is exported' % name)
    check(bool(mapstruct.__version__), 'version is %s' % mapstruct.__version__)


def main():
    for t in (test_pkexplode, test_tilesets, test_classify, test_png, test_api):
        t()
    print()
    if FAILS:
        print('FAILED %d check(s)' % len(FAILS))
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
