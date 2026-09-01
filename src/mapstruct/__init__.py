"""mapstruct - see what StarCraft's engine thinks your map's terrain is.

    from mapstruct import structure_png, classify, read_chk

    structure_png("(4)Fighting Spirit.scx", "fs.png", scale=4)

or from a shell:

    mapstruct "(4)Fighting Spirit.scx"
"""
from .core import (            # noqa: F401
    __doc__ as _tool_doc,
    TILESET_NAMES,
    classify,
    main,
    read_chk,
    render,
    write_png,
)

__version__ = '1.0.0'
__all__ = ['structure_png', 'classify', 'read_chk', 'render', 'write_png',
           'TILESET_NAMES', 'main', '__version__']


def structure_png(map_path, out_path, scale=4):
    """Render one map's terrain structure to a PNG.

    Returns a small dict of what was drawn: width and height in tiles, and how many tiles this
    build had no tileset entry for (those are drawn magenta - see the README).
    """
    w, h, flags, walk, unknown = classify(read_chk(map_path))
    iw, ih, rows = render(w, h, flags, walk, scale)
    write_png(out_path, iw, ih, rows)
    return {'width': w, 'height': h, 'unknown_tiles': unknown,
            'pixels': (iw, ih)}
