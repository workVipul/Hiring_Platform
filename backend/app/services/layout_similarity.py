from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence


ImageInput = tuple[str, bytes, str] | bytes | Path | str


@dataclass
class ImageFeatures:
    width: int
    height: int
    density: float
    whitespace_ratio: float
    palette: list[tuple[int, int, int]]
    region_count: int
    occupancy: set[tuple[int, int]]
    top_density: float
    bottom_density: float


def compute_similarity(reference_images: Sequence[ImageInput], rendered_images: Sequence[ImageInput]) -> dict[str, Any]:
    """Compare rendered template images to uploaded reference images using structural signals."""
    reference_features = [_extract_features(image) for image in reference_images]
    rendered_features = [_extract_features(image) for image in rendered_images]

    reference_count = len(reference_features)
    rendered_count = len(rendered_features)
    page_count_match = reference_count == rendered_count and reference_count > 0
    comparable_pages = min(reference_count, rendered_count)

    if comparable_pages == 0:
        return {
            "score": 0,
            "similarity_score": 0,
            "page_count_match": False,
            "density_match": 0.0,
            "color_match": 0.0,
            "region_match": 0.0,
            "reference_page_count": reference_count,
            "rendered_page_count": rendered_count,
            "whitespace_ratio": None,
        }

    density_match = mean(
        _ratio_similarity(reference_features[index].density, rendered_features[index].density)
        for index in range(comparable_pages)
    )
    color_match = mean(
        _palette_similarity(reference_features[index].palette, rendered_features[index].palette)
        for index in range(comparable_pages)
    )
    region_match = mean(
        _region_similarity(reference_features[index], rendered_features[index])
        for index in range(comparable_pages)
    )
    whitespace_ratio = round(mean(feature.whitespace_ratio for feature in rendered_features), 3)
    score = round(
        100
        * (
            (0.35 * region_match)
            + (0.25 * density_match)
            + (0.30 * color_match)
            + (0.10 * _header_footer_similarity(reference_features, rendered_features, comparable_pages))
        ),
        2,
    )
    return {
        "score": score,
        "similarity_score": score,
        "page_count_match": page_count_match,
        "density_match": round(density_match, 3),
        "color_match": round(color_match, 3),
        "region_match": round(region_match, 3),
        "reference_page_count": reference_count,
        "rendered_page_count": rendered_count,
        "whitespace_ratio": whitespace_ratio,
    }


def _extract_features(image: ImageInput) -> ImageFeatures:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for layout similarity analysis") from exc

    with Image.open(BytesIO(_image_bytes(image))) as opened:
        rgb = opened.convert("RGB")
        width, height = rgb.size
        sample = rgb.resize((120, max(1, int(120 * height / max(width, 1)))))
        pixels = list(sample.getdata())
        non_white = [_is_content_pixel(pixel) for pixel in pixels]
        density = sum(non_white) / max(len(non_white), 1)
        palette = _dominant_palette(sample)
        occupancy = _grid_occupancy(sample)
        top_density = _band_density(sample, 0.0, 0.18)
        bottom_density = _band_density(sample, 0.82, 1.0)
        return ImageFeatures(
            width=width,
            height=height,
            density=round(density, 4),
            whitespace_ratio=round(1.0 - density, 4),
            palette=palette,
            region_count=_region_count_from_occupancy(occupancy),
            occupancy=occupancy,
            top_density=top_density,
            bottom_density=bottom_density,
        )


def _image_bytes(image: ImageInput) -> bytes:
    if isinstance(image, tuple):
        return image[1]
    if isinstance(image, bytes):
        return image
    return Path(image).read_bytes()


def _is_content_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    if r > 245 and g > 245 and b > 245:
        return False
    return max(pixel) - min(pixel) > 8 or sum(pixel) / 3 < 238


def _dominant_palette(image: Any) -> list[tuple[int, int, int]]:
    quantized = image.resize((80, max(1, int(80 * image.height / max(image.width, 1))))).quantize(colors=8)
    palette = quantized.getpalette() or []
    colors = quantized.getcolors(maxcolors=8) or []
    dominant: list[tuple[int, int, int]] = []
    for _count, color_index in sorted(colors, reverse=True):
        offset = int(color_index) * 3
        if offset + 2 >= len(palette):
            continue
        color = (palette[offset], palette[offset + 1], palette[offset + 2])
        if _is_content_pixel(color):
            dominant.append(color)
    return dominant[:5]


def _grid_occupancy(image: Any, cols: int = 12, rows: int = 16) -> set[tuple[int, int]]:
    occupancy: set[tuple[int, int]] = set()
    cell_width = max(image.width // cols, 1)
    cell_height = max(image.height // rows, 1)
    for row in range(rows):
        for col in range(cols):
            left = col * cell_width
            upper = row * cell_height
            right = image.width if col == cols - 1 else min(image.width, left + cell_width)
            lower = image.height if row == rows - 1 else min(image.height, upper + cell_height)
            crop = image.crop((left, upper, right, lower))
            pixels = list(crop.getdata())
            density = sum(1 for pixel in pixels if _is_content_pixel(pixel)) / max(len(pixels), 1)
            if density > 0.08:
                occupancy.add((row, col))
    return occupancy


def _region_count_from_occupancy(occupancy: set[tuple[int, int]]) -> int:
    remaining = set(occupancy)
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            row, col = stack.pop()
            neighbors = ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))
            for neighbor in neighbors:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def _band_density(image: Any, start_pct: float, end_pct: float) -> float:
    top = int(image.height * start_pct)
    bottom = max(top + 1, int(image.height * end_pct))
    crop = image.crop((0, top, image.width, min(image.height, bottom)))
    pixels = list(crop.getdata())
    return round(sum(1 for pixel in pixels if _is_content_pixel(pixel)) / max(len(pixels), 1), 4)


def _ratio_similarity(reference: float, rendered: float) -> float:
    return max(0.0, 1.0 - abs(reference - rendered) / max(reference, rendered, 0.05))


def _palette_similarity(reference_palette: Iterable[tuple[int, int, int]], rendered_palette: Iterable[tuple[int, int, int]]) -> float:
    reference = list(reference_palette)
    rendered = list(rendered_palette)
    if not reference or not rendered:
        return 0.0
    matches = []
    for color in reference:
        distance = min(_color_distance(color, candidate) for candidate in rendered)
        matches.append(max(0.0, 1.0 - distance / 441.7))
    return sum(matches) / max(len(matches), 1)


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((left[index] - right[index]) ** 2 for index in range(3)) ** 0.5


def _region_similarity(reference: ImageFeatures, rendered: ImageFeatures) -> float:
    union = reference.occupancy | rendered.occupancy
    overlap = len(reference.occupancy & rendered.occupancy) / max(len(union), 1)
    region_count_match = _ratio_similarity(float(reference.region_count), float(rendered.region_count))
    return (0.7 * overlap) + (0.3 * region_count_match)


def _header_footer_similarity(reference: list[ImageFeatures], rendered: list[ImageFeatures], pages: int) -> float:
    return mean(
        (
            _ratio_similarity(reference[index].top_density, rendered[index].top_density)
            + _ratio_similarity(reference[index].bottom_density, rendered[index].bottom_density)
        )
        / 2
        for index in range(pages)
    )
