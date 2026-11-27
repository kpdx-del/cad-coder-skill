"""Exact installed-font resolution and glyph metrics; no silent substitution."""
from functools import lru_cache
from pathlib import Path
import os
import re

from ezdxf.fonts import fonts
from fontTools.ttLib import TTFont


@lru_cache(maxsize=32)
def resolve_font(name):
    path = Path(name)
    if path.is_file():
        return path.resolve()
    if path.is_absolute():
        raise FileNotFoundError(f"Required font not found: {name}")
    roots = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
    roots += [Path(p) for p in os.environ.get("CAD_FONT_DIRS", "").split(os.pathsep) if p]
    from matplotlib.font_manager import findSystemFonts
    import matplotlib
    candidates = [p for root in roots if root.is_dir() for p in root.iterdir()]
    candidates += [Path(p) for p in findSystemFonts()]
    candidates += list((Path(matplotlib.get_data_path()) / "fonts" / "ttf").glob("*"))
    for candidate in candidates:
        if candidate.name.casefold() == path.name.casefold():
            return candidate.resolve()
    raise FileNotFoundError(f"Required font not found: {name}; install it or set CAD_FONT_DIRS")


@lru_cache(maxsize=32)
def register_font(name):
    path = resolve_font(name)
    if not fonts.font_manager.has_font(path.name):
        fonts.font_manager.scan_folder(path.parent)
    if not fonts.font_manager.has_font(path.name):
        raise ValueError(f"ezdxf could not load font: {path}")
    return path.name


def visible_text(text):
    """Decode the CAD diameter/degree/plus-minus escapes used by the helpers."""
    return re.sub(r"%%[cCdDpP]", lambda m: {"c": "φ", "d": "°", "p": "±"}[m[0][-1].lower()], str(text))


@lru_cache(maxsize=32)
def _glyphs(font):
    with TTFont(resolve_font(font), fontNumber=0) as face:
        return frozenset(face.getBestCmap())


def check_glyphs(text, font):
    missing = sorted({ch for ch in visible_text(text) if not ch.isspace() and ord(ch) not in _glyphs(font)})
    if missing:
        raise ValueError(f"Font {font} lacks glyphs: {''.join(missing)}")


def text_width(text, font, height=3.5):
    text = visible_text(text)
    check_glyphs(text, font)
    return fonts.sideload_ttf(resolve_font(font), cap_height=height).text_width(text)


def style_for(text):
    return "CAD_CJK" if any("\u3400" <= c <= "\u9fff" for c in text) else "CAD_TEXT"


def add_text(msp, text, insert, height=3.5, **attrs):
    style = attrs.pop("style", style_for(text))
    font = msp.doc.styles.get(style).dxf.font
    check_glyphs(text, font)
    return msp.add_text(text, dxfattribs={"height": height, "layer": "DIM", "style": style,
                                        "insert": insert, **attrs})


def text_rect(entity):
    """Rendered text bounds, including MTEXT fractions instead of flattened text."""
    if entity.dxftype()=="MTEXT":
        from ezdxf.tools.text_size import mtext_size
        size=mtext_size(entity)
        column=(entity.dxf.attachment_point-1)%3
        row=(entity.dxf.attachment_point-1)//3
        left=-column*size.total_width/2
        top=row*size.total_height/2
        ucs=entity.ucs()
        points=[ucs.to_wcs((x,y)) for x in (left,left+size.total_width)
                for y in (top-size.total_height,top)]
        return min(p.x for p in points),min(p.y for p in points),max(p.x for p in points),max(p.y for p in points)
    from ezdxf.addons.text2path import make_paths_from_entity
    from ezdxf.path import bbox
    box=bbox(make_paths_from_entity(entity),fast=False)
    if not box.has_data:
        return None
    return box.extmin.x,box.extmin.y,box.extmax.x,box.extmax.y
