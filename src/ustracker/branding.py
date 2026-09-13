from __future__ import annotations

import io
from pathlib import Path
from PIL import Image, ImageOps

KINDS = {'logo': (1024, 1024), 'favicon': (256, 256), 'icon': (512, 512)}


def asset_dir(root: Path | str) -> Path:
    path = Path(root) / 'UserData' / 'Public' / 'production' / 'assets'
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_brand_asset(root: Path | str, kind: str, data: bytes) -> dict:
    kind = str(kind).lower()
    if kind not in KINDS:
        raise ValueError('branding kind must be logo, favicon or icon')
    if len(data) > 10 * 1024 * 1024:
        raise ValueError('branding image exceeds 10 MiB')
    with Image.open(io.BytesIO(data)) as im:
        if getattr(im, 'n_frames', 1) != 1:
            raise ValueError('animated branding images are not supported')
        if im.width * im.height > 20_000_000:
            raise ValueError('branding image exceeds 20 MP')
        im = ImageOps.exif_transpose(im).convert('RGBA')
        im.thumbnail(KINDS[kind], Image.Resampling.LANCZOS)
        path = asset_dir(root) / f'{kind}.png'
        tmp = path.with_suffix('.tmp')
        im.save(tmp, format='PNG', optimize=True)
        tmp.replace(path)
    return {'kind': kind, 'url': f'/public-assets/{kind}.png'}


def available_assets(root: Path | str) -> dict:
    directory = asset_dir(root)
    return {kind: f'/public-assets/{kind}.png' for kind in KINDS if (directory / f'{kind}.png').exists()}
