#!/usr/bin/env python3
"""mapstruct - turn a StarCraft map into a picture of what the engine thinks its terrain is.

Point it at a .scm or .scx (or a folder of them) and it writes a PNG per map showing, for every
eighth of a tile, whether you can WALK there, whether you can BUILD there, and how HIGH it is:

    python3 mapstruct.py "(4)Fighting Spirit.scx"
    python3 mapstruct.py Maps/ladder -o pics -s 6

On Windows you can drop map files straight onto the script.

Nothing needs installing. No StarCraft installation, no Python packages, no compiler: the
walkability and height tables for all eight tilesets are built into this file, and everything else
is the standard library. A map file is itself an MPQ archive, and reading one is handled here too.

WHAT THE COLOURS MEAN
  slate    you cannot walk here - cliff faces, water, the sides of ramps
  green    walkable and buildable
  amber    walkable but NOT buildable - ramps, the ground under a mineral line, map decoration
  magenta  this build does not have these tiles (see BUILDS AND NEW TILES below)
  Darker is lower ground and lighter is higher, in three steps. Dark contour lines are drawn
  wherever the height changes, because a real map is usually 80-90% one level and a subtle
  gradient just reads as flat.

The distinction people usually want is the amber one. Unbuildable ground is invisible in the
editor and in game, and it decides where a wall-in can go.

BUILDS AND NEW TILES
Tile data changes between game versions. If a map uses tiles this build does not know, they are
drawn magenta and the count is printed - that is a "get a newer mapstruct", not a broken map. It
is never guessed at, because a guess would put walkable ground where there may be none.
"""

import base64
import io
import lzma
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------------------------------------
# Tileset tables, baked in. Regenerate with tools/build_tileset_blob.py when a patch adds tiles.
# ---------------------------------------------------------------------------------------------
TILESET_BLOB = (
    "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"
    "NgXWlvFEdJvCptYn3oarKjqv2G0QLto1p6I93bVJ3blPi0Vbf3QHl1ioGaIyDx5ylNBnjinMvqObIaEr4PENxoNx3iFdy8BQ+C3o"
    "F9HJoPuvfRfG/f2+SH2tF8ch1xfuNGgz6wFHO1eHF5/sQjmO7WjcvX4PwwI7p1iGfKkyrU1kMfohdJ1AExB8lNQfZm5P8DCckSen"
    "66tKlkIELRbbZGqalTnjMIOdMXH0D1Gpo7IgT13ftXXhgjzAAVphHbv1gXxHzgD1yzDlOzhBeSeYAx9uvi6G9Qw7wlNnQ8TxqkSQ"
    "zwSDJWShxz1ExCLSahRga5UjDYSiDSiruofMQanhZL+YIPoBZ69lT41VOb7bB4bnZbKjmW0loQhrit931HtEtl2gLR8+9ZmBz/Em"
    "MTqMq+RLp8HkpV127lg9h319NYQge9XMb5UKrrEikd5kZjLmMQMmrLi3k351ednUtcmM8ashk+psd+SVLEbOxdYXtgAu2JWEJ2Mm"
    "JoNBHjh69ETer/KMcxykF6mMgf5wu8zJy5nK0KoTqmZqbk/DBHDOIfau+C9SewnvE8zXeWJnPZ2CxIcU4YYD8LDi1BpbE7FkI1gi"
    "HqWZHRQYG26kvB3n6OqkSCifQP3gU+een1kmRwY5Q/p3GddUgUIXYL3p1JUZGvVEpF5f3yporoC55psR/dtQR1+W3OksWPZtW6z+"
    "eyo+lgsv/Jj9ayXEFckk1rvsnl223r3UTqniC8O6zFxU3GdnWWfPv1prdKq/7J8+8gcQSwhNWjR3qa6NPw8LholsiEkLSLJzC9U0"
    "/YaRWxvB0EsEMQQ2n7sjZ5nGpQHVXoEJZa5VVEATHduVfb0DuXkhdJQaJmShKKHNdKKlkl3nhIS+3W6euXLB6FsidzEn6/gZjU/M"
    "5q18aJ2spvikrQ7dGCTnGaDrMx+hxDvG8ovB1XDlqsU9fGicbPPho6XG1YrwzcG/LNkfqJ+FN86ps1of6OAo3aMKf4H9FftYxPDy"
    "M13fDmm7/KPqnkqi7PaXK8Q0Ka1xp5rhu3DTWfu+M6YMmvnpDap3VQpLqglpECignI/Q/9xuvsYleRioNQdF+VHe1OEF9oO93nxD"
    "UpojP/a7cwWDfupF2QpwdrSTy1S5xcnTMamAFQpimWxMGDLggw3LOcsAhBl+NzKMGNrj1WeKpAuCks2NTNKnK3TquLrLftH1PWW/"
    "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"
)   # regenerate with tools/build_tileset_blob.py

TILESET_NAMES = ('badlands', 'platform', 'install', 'ashworld',
                 'jungle', 'Desert', 'Ice', 'Twilight')

_tilesets = None


def tilesets():
    """{name: (cv5 bytes, vf4 bytes)} decoded from the embedded blob, once."""
    global _tilesets
    if _tilesets is None:
        if not TILESET_BLOB:
            raise SystemExit('mapstruct: this build has no tileset tables compiled in')
        raw = lzma.decompress(base64.b64decode(TILESET_BLOB))
        out, off = {}, 0
        (count,) = struct.unpack_from('<H', raw, off); off += 2
        index = []
        for _ in range(count):
            (nlen,) = struct.unpack_from('<B', raw, off); off += 1
            name = raw[off:off + nlen].decode('ascii'); off += nlen
            cl, vl = struct.unpack_from('<II', raw, off); off += 8
            index.append((name, cl, vl))
        for name, cl, vl in index:
            cv5 = raw[off:off + cl]; off += cl
            vf4 = raw[off:off + vl]; off += vl
            out[name] = (cv5, vf4)
        _tilesets = out
    return _tilesets


# ---------------------------------------------------------------------------------------------
# Reading a map. A .scm/.scx is an MPQ archive holding one file, staredit\scenario.chk.
# ---------------------------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _helpers():
    """The MPQ reader and the PKWARE explode, however this file happens to be running.

    mapstruct is used three ways - a loose script next to its two helpers, a zipapp, and an
    installed package - and only the last of those puts the helpers in a package namespace. Try
    the package form first when there IS a package, and plain imports otherwise."""
    if __package__:
        from . import mpyq as _mpyq, pkexplode as _pkexplode
        return _mpyq, _pkexplode
    import mpyq as _mpyq
    import pkexplode as _pkexplode
    return _mpyq, _pkexplode


def read_chk(path):
    """The scenario.chk out of a map archive."""
    mpyq, pkexplode = _helpers()

    arch = mpyq.MPQArchive(path, listfile=False)
    name = 'staredit\\scenario.chk'
    if not arch.get_hash_table_entry(name):
        raise ValueError('no scenario.chk - is this a StarCraft map?')
    return _read_mpq_file(arch, name, pkexplode.explode)


def _read_mpq_file(arch, name, explode):
    """One file out of an MPQ. mpyq covers the archive structure; the parts it does not cover -
    PKWARE-imploded sectors, encrypted files, Storm leaving the last 1-3 bytes of a sector
    unencrypted - are handled here. This mirrors tools/mpq_chk.py, which is the same logic against
    the C explode, and the two are checked against each other by tests/pkexplode_test.py."""
    import bz2
    mpyq, _ = _helpers()

    he = arch.get_hash_table_entry(name)
    if he is None:
        raise KeyError(name)
    be = arch.block_table[he.block_table_index]
    if not be.flags & mpyq.MPQ_FILE_EXISTS:
        raise KeyError(name)
    arch.file.seek(be.offset + arch.header['offset'])
    raw = arch.file.read(be.archived_size)

    key = None
    if be.flags & mpyq.MPQ_FILE_ENCRYPTED:
        base = name.replace('/', '\\').split('\\')[-1]
        key = arch._hash(base, 'TABLE')
        if be.flags & mpyq.MPQ_FILE_FIX_KEY:
            key = ((key + be.offset) ^ be.size) & 0xffffffff

    def decrypt(data, k):
        n = len(data) & ~3          # mpyq decrypts whole dwords; Storm leaves the tail alone
        return arch._decrypt(data[:n], k) + data[n:]

    def multi(data):
        m = data[0]
        if m == 0x08:
            return explode(data[1:])
        if m == 0x02:
            return zlib.decompress(data[1:])
        if m == 0x10:
            return bz2.decompress(data[1:])
        raise ValueError('unsupported compression mask 0x%02x' % m)

    compressed = be.flags & (mpyq.MPQ_FILE_COMPRESS | mpyq.MPQ_FILE_IMPLODE)

    def unpack(sector, plain_len):
        if compressed and len(sector) < plain_len:
            if be.flags & mpyq.MPQ_FILE_IMPLODE:
                return explode(sector)
            return multi(sector)
        return sector

    if be.flags & mpyq.MPQ_FILE_SINGLE_UNIT:
        data = decrypt(raw, key) if key is not None else raw
        return unpack(data, be.size)[:be.size]

    sector_size = 512 << arch.header['sector_size_shift']
    nsect = (be.size + sector_size - 1) // sector_size
    if compressed:
        extra = 1 if be.flags & mpyq.MPQ_FILE_SECTOR_CRC else 0
        tab_len = 4 * (nsect + 1 + extra)
        tab = raw[:tab_len]
        if key is not None:
            tab = decrypt(tab, (key - 1) & 0xffffffff)      # the offset table uses key - 1
        pos = struct.unpack('<%dI' % (tab_len // 4), tab)
    else:
        pos = [i * sector_size for i in range(nsect + 1)]

    out = bytearray()
    left = be.size
    for i in range(nsect):
        sector = raw[pos[i]:pos[i + 1]]
        if key is not None:
            sector = decrypt(sector, (key + i) & 0xffffffff)
        plain = min(sector_size, left)
        out += unpack(sector, plain)[:plain]
        left -= plain
    return bytes(out)


def walk_chk(chk):
    """CHK is a flat run of {4-byte tag, 4-byte length, payload}."""
    off = 0
    while off + 8 <= len(chk):
        tag = chk[off:off + 4].decode('latin1')
        (ln,) = struct.unpack_from('<I', chk, off + 4)
        yield tag, off + 8, ln
        off += 8 + ln


def map_info(chk):
    era = w = h = 0
    mtxm = b''
    for tag, off, ln in walk_chk(chk):
        if tag == 'ERA ':
            era = struct.unpack_from('<H', chk, off)[0] & 7
        elif tag == 'DIM ':
            w, h = struct.unpack_from('<HH', chk, off)
        elif tag == 'MTXM':
            # Later MTXM chunks override earlier ones, and the last is the real one.
            mtxm = chk[off:off + ln]
    if not (w and h and mtxm):
        raise ValueError('map has no dimensions or no tile data')
    return era, w, h, mtxm


# ---------------------------------------------------------------------------------------------
# Terrain classification. Same rules the decompiled loader uses.
# ---------------------------------------------------------------------------------------------
def megatile_flags(vf4):
    """Per megatile, the tile-level flags, decided by a VOTE of its 16 minitiles: a megatile is
    walkable if more than 12 of them are, high ground if at least 12 are, and so on. That vote is
    why a tile can read as buildable while a corner of it is not walkable."""
    out = []
    for i in range(len(vf4) // 32):
        fl = struct.unpack_from('<16H', vf4, i * 32)
        wk = sum(1 for f in fl if f & 1)
        mid = sum(1 for f in fl if f & 2)
        hi = sum(1 for f in fl if f & 4)
        f = 0x10000 if wk > 12 else 0x40000
        if hi < 12 and mid + hi >= 12:
            f |= 0x2000000
        if hi >= 12:
            f |= 0x4000000
        out.append(f)
    return out


def classify(chk):
    """-> (w, h, per-tile flags, per-minitile walkable, unknown-tile count)."""
    era, w, h, mtxm = map_info(chk)
    name = TILESET_NAMES[era]
    tsets = tilesets()
    if name not in tsets:
        raise ValueError('no table for tileset %r in this build' % name)
    cv5, vf4 = tsets[name]

    mf = megatile_flags(vf4)
    groups = len(cv5) // 52
    ids = struct.unpack_from('<%dH' % (w * h), mtxm)

    flags = [0] * (w * h)
    walk = bytearray(w * 4 * h * 4)
    unknown = 0
    for t, i in enumerate(ids):
        g = (i >> 4) & 0x7ff
        sub = i & 0xf
        if g >= groups:
            # Nothing is known about this tile. Call it unwalkable and unbuildable rather than
            # invent connectivity that may not exist.
            flags[t] = 0x40000 | 0x800000 | 0x80000000
            unknown += 1
            continue
        mega = struct.unpack_from('<H', cv5, g * 52 + 0x14 + sub * 2)[0] & 0x7fff
        cflags = struct.unpack_from('<H', cv5, g * 52 + 2)[0]
        if mega >= len(mf):
            flags[t] = 0x40000 | 0x800000 | 0x80000000
            unknown += 1
            continue
        flags[t] = mf[mega] | ((cflags & ~0x2705 & 0xffff) << 16)

        tx, ty = t % w, t // w
        base = mega * 32
        for my in range(4):
            row = (ty * 4 + my) * (w * 4) + tx * 4
            for mx in range(4):
                (mfl,) = struct.unpack_from('<H', vf4, base + (my * 4 + mx) * 2)
                walk[row + mx] = 1 if (mfl & 1) else 0

    # The loader patches the bottom edge after building the flags: the whole last row, and the
    # outermost five tiles of the row above it, are forced unwalkable and unbuildable. It is a
    # hard border, not something the tileset says, and without it the last two rows of every map
    # come out wrong - which is exactly the 81 tiles this differed by before it was added.
    def patch(x, y, pw, ph):
        for j in range(y, y + ph):
            for k in range(x, x + pw):
                t = j * w + k
                # Note this CLEARS the walkable bit without setting the unwalkable one, so
                # the tile-level pair reads as neither. Walkability for the picture comes
                # from the per-minitile array below, which is zeroed here instead.
                flags[t] = (flags[t] & ~(0x10000 | 0x400000 | 0x20000000)) | 0x800000
                for my in range(4):
                    row = (j * 4 + my) * (w * 4) + k * 4
                    for mx in range(4):
                        walk[row + mx] = 0

    if h >= 2:
        patch(0, h - 2, min(5, w), 1)
        patch(max(0, w - 5), h - 2, min(5, w), 1)
    if h >= 1:
        patch(0, h - 1, w, 1)
    return w, h, flags, walk, unknown


# ---------------------------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------------------------
PALETTE = (
    ((0x15, 0x1a, 0x21), (0x2b, 0x33, 0x3e), (0x4a, 0x56, 0x66)),   # not walkable
    ((0x1c, 0x45, 0x2c), (0x4e, 0x91, 0x52), (0x99, 0xd4, 0x7f)),   # walkable, buildable
    ((0x53, 0x37, 0x11), (0x96, 0x70, 0x2a), (0xdd, 0xb0, 0x4e)),   # walkable, unbuildable
)
UNKNOWN = (0xd9, 0x2b, 0x8f)


def render(w, h, flags, walk, scale):
    """-> (width, height, list of PNG scanlines as raw RGB).

    One pixel block per MINITILE - an eighth of a tile - because walkability is stored that
    finely, and the difference between a ramp you can walk and the cliff beside it is often a
    single minitile. Height contours are drawn on the TILE grid instead, since height is a
    per-tile property."""
    mw, mh = w * 4, h * 4
    iw, ih = mw * scale, mh * scale

    def level(tx, ty):
        f = flags[ty * w + tx]
        return 2 if (f & 0x4000000) else (1 if (f & 0x2000000) else 0)

    rows = []
    for my in range(mh):
        ty = my // 4
        # Two variants of the row: the first pixel line of the minitile carries any contour along
        # its TOP edge, the rest do not. Both carry the contour along their LEFT edge.
        top = bytearray(iw * 3)
        body = bytearray(iw * 3)
        for mx in range(mw):
            tx = mx // 4
            f = flags[ty * w + tx]
            lv = level(tx, ty)
            if f & 0x80000000:
                col = UNKNOWN
            else:
                cls = 0 if not walk[my * mw + mx] else (2 if (f & 0x800000) else 1)
                col = PALETTE[cls][lv]
            dark = (col[0] // 5, col[1] // 5, col[2] // 5)

            contour_left = (mx % 4) == 0 and tx > 0 and level(tx - 1, ty) != lv
            contour_top = (my % 4) == 0 and ty > 0 and level(tx, ty - 1) != lv

            for dx in range(scale):
                o = (mx * scale + dx) * 3
                edge = dark if (contour_left and dx == 0) else col
                body[o:o + 3] = bytes(edge)
                top[o:o + 3] = bytes(dark if contour_top else edge)

        rows.append(bytes(top))
        for _ in range(scale - 1):
            rows.append(bytes(body))
    return iw, ih, rows


def write_png(path, iw, ih, rows):
    def chunk(tag, data):
        out = struct.pack('>I', len(data)) + tag + data
        return out + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    raw = b''.join(b'\x00' + r for r in rows)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', iw, ih, 8, 2, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(raw, 6)))
        f.write(chunk(b'IEND', b''))


# ---------------------------------------------------------------------------------------------
def collect(args):
    maps = []
    for a in args:
        if os.path.isdir(a):
            for base, _d, files in os.walk(a):
                for fn in sorted(files):
                    if fn.lower().endswith(('.scm', '.scx')):
                        maps.append(os.path.join(base, fn))
        elif a.lower().endswith(('.scm', '.scx')):
            maps.append(a)
        else:
            print('skipping %s (not a .scm or .scx)' % a)
    return maps


def main(argv):
    args, out_dir, scale = [], '.', 4
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('-o', '--out') and i + 1 < len(argv):
            out_dir = argv[i + 1]; i += 2
        elif a in ('-s', '--scale') and i + 1 < len(argv):
            scale = max(1, min(16, int(argv[i + 1]))); i += 2
        elif a in ('-h', '--help'):
            print(__doc__); return 0
        else:
            args.append(a); i += 1

    if not args:
        print(__doc__)
        return 2

    maps = collect(args)
    if not maps:
        print('no .scm or .scx files found')
        return 2
    if out_dir != '.':
        os.makedirs(out_dir, exist_ok=True)

    failed = 0
    for n, path in enumerate(maps, 1):
        stem = os.path.splitext(os.path.basename(path))[0]
        dest = os.path.join(out_dir, stem + '.png')
        try:
            w, h, flags, walk, unknown = classify(read_chk(path))
            iw, ih, rows = render(w, h, flags, walk, scale)
            write_png(dest, iw, ih, rows)
        except Exception as e:
            print('[%d/%d] %-44s FAILED: %s' % (n, len(maps), stem[:44], e))
            failed += 1
            continue
        note = ''
        if unknown:
            note = ('  -- %d tiles (%.1f%%) are not in this build, drawn magenta; a newer '
                    'mapstruct may know them' % (unknown, 100.0 * unknown / (w * h)))
        print('[%d/%d] %-44s %dx%d tiles -> %s%s'
              % (n, len(maps), stem[:44], w, h, dest, note))
    return 1 if failed else 0


def _console():
    """Entry point for the installed `mapstruct` command (see pyproject.toml)."""
    return main(sys.argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
