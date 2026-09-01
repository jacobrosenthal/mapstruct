# Third-party code and data

## mpyq — BSD 2-Clause
`src/mapstruct/mpyq.py` is Aku Kotkavuo's [mpyq](https://github.com/eagleflo/mpyq), vendored
unchanged so that installing mapstruct pulls in nothing. Its licence is in
`src/mapstruct/mpyq-LICENSE`.

## blast — zlib licence
`src/mapstruct/pkexplode.py` is a Python port of `blast.c`, Copyright (C) 2003, 2012, 2013 Mark
Adler, version 1.3. It is a reimplementation rather than a copy - no C source is included - but
the algorithm and its code-length tables come from that work and the debt is real.

## StarCraft tileset data — Blizzard Entertainment
`src/mapstruct/core.py` carries a compressed table built from the `cv5` and `vf4` files of
StarCraft: Brood War, which are Blizzard Entertainment's. Only **functional** data is included:
`cv5` maps a tile id to a megatile, and `vf4` records, per eighth of a tile, whether it is
walkable and how high it is. That is what makes the tool work without an installed copy of the
game.

No artwork is included. There is no `vr4`, no `vx4`, no `wpe` palette - so mapstruct can describe
what terrain *is*, and is incapable of drawing what it *looks like*. If that distinction does not
sit right with you, build your own table from your own installation:

    python3 tools/build_tileset_blob.py /path/to/tileset/files

StarCraft and Brood War are trademarks of Blizzard Entertainment. This project is not affiliated
with or endorsed by Blizzard.
