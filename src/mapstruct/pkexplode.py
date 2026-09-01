#!/usr/bin/env python3
"""PKWARE Data Compression Library "explode", in pure Python.

MPQ archives - which includes every .scm/.scx map file, since a map IS an MPQ - store some
sectors with PKWARE DCL implode (compression flag 0x100). Reading them was the one thing in this
toolchain that needed a C compiler: tools/mpq_chk.py loads tools/pklib/libblast.so through ctypes,
so anyone wanting to look at a map first had to build a shared library. That is a poor trade for
a tool aimed at map makers, so this is the same algorithm with nothing underneath it but the
standard library.

Ported from tools/pklib/blast.c (Mark Adler's blast, zlib licence), and checked against it byte
for byte on the sectors in the game's own archives - see tests/pkexplode_test.py.

The one deliberate difference: blast.c keeps a 4096-byte sliding window because it is written to
stream through fixed memory. Here the output is just a list that grows, so the window bookkeeping
and its wrap-around copy loop are gone. The decoded bytes are identical either way.
"""

MAXBITS = 13

# Compact code-length tables, exactly as blast.c carries them: each byte is a repeat count in the
# high nibble (plus one) and a bit length in the low nibble.
_LITLEN = bytes([
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173])
_LENLEN = bytes([2, 35, 36, 53, 38, 23])
_DISTLEN = bytes([2, 20, 53, 230, 247, 151, 248])

_BASE = (3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264)
_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8)


def _construct(rep):
    """Expand the compact table into (count-per-length, symbols-sorted-by-length)."""
    length = []
    for b in rep:
        length.extend([b & 15] * ((b >> 4) + 1))
    count = [0] * (MAXBITS + 1)
    for l in length:
        count[l] += 1
    offs = [0] * (MAXBITS + 2)
    for l in range(1, MAXBITS):
        offs[l + 1] = offs[l] + count[l]
    symbol = [0] * len(length)
    for sym, l in enumerate(length):
        if l:
            symbol[offs[l]] = sym
            offs[l] += 1
    return count, symbol


_LITCODE = _construct(_LITLEN)
_LENCODE = _construct(_LENLEN)
_DISTCODE = _construct(_DISTLEN)


class _State(object):
    __slots__ = ('data', 'pos', 'bitbuf', 'bitcnt')

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.bitbuf = 0
        self.bitcnt = 0

    def byte(self):
        if self.pos >= len(self.data):
            raise ValueError('pkexplode: out of input')
        b = self.data[self.pos]
        self.pos += 1
        return b


def _bits(st, need):
    """Bits arrive low-order first, and a code is never split across the whole buffer - blast.c
    keeps at most seven bits of carry, and so does this."""
    val = st.bitbuf
    while st.bitcnt < need:
        val |= st.byte() << st.bitcnt
        st.bitcnt += 8
    st.bitbuf = val >> need
    st.bitcnt -= need
    return val & ((1 << need) - 1)


def _decode(st, code):
    """Walk the canonical Huffman code one bit at a time. The bits are INVERTED relative to the
    usual convention, which is the `^ 1` below and the reason this cannot be swapped for a
    standard Huffman decoder."""
    count, symbol = code
    bitbuf = st.bitbuf
    left = st.bitcnt
    c = first = index = 0
    ln = 1
    while True:
        while left > 0:
            left -= 1
            c |= (bitbuf & 1) ^ 1
            bitbuf >>= 1
            cnt = count[ln]
            if c < first + cnt:
                st.bitbuf = bitbuf
                st.bitcnt = (st.bitcnt - ln) & 7
                return symbol[index + (c - first)]
            index += cnt
            first = (first + cnt) << 1
            c <<= 1
            ln += 1
        left = (MAXBITS + 1) - ln
        if left == 0:
            break
        bitbuf = st.byte()
        if left > 8:
            left = 8
    raise ValueError('pkexplode: ran out of codes')


def explode(data):
    """Decompress one PKWARE DCL stream. Returns bytes."""
    st = _State(data)
    lit = _bits(st, 8)
    if lit > 1:
        raise ValueError('pkexplode: bad literal flag %d' % lit)
    dict_bits = _bits(st, 8)
    if not 4 <= dict_bits <= 6:
        raise ValueError('pkexplode: bad dictionary size %d' % dict_bits)

    out = bytearray()
    while True:
        if _bits(st, 1):
            sym = _decode(st, _LENCODE)
            length = _BASE[sym] + _bits(st, _EXTRA[sym])
            if length == 519:          # the end-of-stream code
                break
            # A length of 2 always uses a 2-bit distance, whatever the dictionary size.
            shift = 2 if length == 2 else dict_bits
            dist = (_decode(st, _DISTCODE) << shift) + _bits(st, shift) + 1
            if dist > len(out):
                raise ValueError('pkexplode: distance %d reaches before the start' % dist)
            start = len(out) - dist
            # Appending one byte at a time is what makes an overlapping copy work: a run can
            # legitimately reference bytes this very copy is still producing.
            for i in range(length):
                out.append(out[start + i])
        else:
            out.append(_decode(st, _LITCODE) if lit else _bits(st, 8))
    return bytes(out)


if __name__ == '__main__':
    import sys
    sys.stdout.buffer.write(explode(sys.stdin.buffer.read()))
