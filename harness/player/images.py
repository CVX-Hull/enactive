"""A small explicit player-selected view of actual captured PNG pixels."""
from __future__ import annotations

import hashlib
import io
import warnings

from PIL import Image

from harness.computer.protocol import GEOMETRY_KEYS, source as validate_source
from .contracts import PlayerError, bounded_integer, json_object


def program_view(source: dict, png: bytes, selection: dict, interpretation: dict, remaining: dict) -> dict:
    try:
        source = json_object(source)
        validate_source(source)
        selection = json_object(selection)
        if set(selection) != {'crop', 'size'}:
            raise PlayerError('Selection requires exactly crop and size')
        size = selection['size']
        if type(size) is not list or len(size) != 2:
            raise PlayerError('Selection size requires two dimensions')
        for n in size:
            bounded_integer(n, 1, 96)
        width, height = source['width'], source['height']
        crop = selection['crop']
        if crop is None:
            crop = [0, 0, width, height]
        if type(crop) is not list or len(crop) != 4:
            raise PlayerError('Crop requires x,y,width,height')
        for n in crop[:2]:
            bounded_integer(n, 0, 16383)
        for n in crop[2:]:
            bounded_integer(n, 1, 16384)
        x, y, w, h = crop
        if x + w > width or y + h > height:
            raise PlayerError('Crop exceeds the captured image')
        if type(png) is not bytes or len(png) > 64 * 1024 * 1024 or hashlib.sha256(png).hexdigest() != source['sha256']:
            raise PlayerError('Captured PNG differs from original source SHA')
        if width * height * 4 > 64 * 1024 * 1024:
            raise PlayerError('Decoded capture exceeds 64 MiB')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(png), formats=['PNG']) as image:
                if image.size != (width, height) or getattr(image, 'n_frames', 1) != 1:
                    raise PlayerError('PNG dimensions or frame count differ from source')
                image.load()
                rgba = image.crop((x, y, x + w, y + h)).convert('RGBA')
                black = Image.new('RGBA', rgba.size, (0, 0, 0, 255))
                rgb = Image.alpha_composite(black, rgba).convert('RGB')
                ratio = min(1, size[0] / w, size[1] / h)
                dimensions = (max(1, int(w * ratio)), max(1, int(h * ratio)))
                sampled = rgb.resize(dimensions, Image.Resampling.NEAREST)
                channels = list(sampled.tobytes())
        omissions = []
        if crop != [0, 0, width, height]:
            omissions.append('Pixels outside selected crop omitted; full PNG remains separately readable')
        if dimensions != (w, h):
            omissions.append('Nearest-neighbour sampling omits original pixels; no inferred detail')
        omissions.append('Alpha composited on black; original alpha retained only in full PNG')
        return dict(schema='program-view/3', source=source,
                    image=dict(width=dimensions[0], height=dimensions[1], rgb=channels,
                               original_geometry={k: source[k] for k in sorted(GEOMETRY_KEYS)}, crop=crop,
                               sampling='nearest', alpha='composited-on-black', omissions=omissions,
                               full_reference=dict(source_id=source['source_id'], sha256=source['sha256'])),
                    interpretation=json_object(interpretation), remaining=json_object(remaining))
    except (ValueError, TypeError, OSError, OverflowError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise PlayerError(f'Cannot derive player image view: {exc}') from exc
