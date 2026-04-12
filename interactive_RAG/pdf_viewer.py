"""
PDF rendering helpers: coordinate transforms, highlight overlay, element hit-testing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

import config


# ---------------------------------------------------------------------------
# Coordinate transforms
# ---------------------------------------------------------------------------

def pdf_coords_to_pixel(
    l: float, b: float, r: float, t: float,
    page_height_pts: float,
    dpi: int = config.RENDER_DPI,
) -> dict:
    """
    Convert a PDF bounding box (bottom-left origin, points) to pixel coords
    in a top-left-origin image rendered at `dpi`.

    PDF space:  origin = bottom-left,  t > b
    Image space: origin = top-left,   y0 < y1
    """
    scale = dpi / 72.0
    return {
        "x0": int(l * scale),
        "y0": int((page_height_pts - t) * scale),
        "x1": int(r * scale),
        "y1": int((page_height_pts - b) * scale),
    }


def pixel_to_pdf_point(
    px_x: int, px_y: int,
    page_height_pts: float,
    dpi: int = config.RENDER_DPI,
) -> tuple[float, float]:
    """Convert image pixel coords back to PDF point space (bottom-left origin)."""
    scale = dpi / 72.0
    pdf_x = px_x / scale
    pdf_y = page_height_pts - (px_y / scale)
    return pdf_x, pdf_y


# ---------------------------------------------------------------------------
# Page image loading
# ---------------------------------------------------------------------------

def get_page_image(page_no: int) -> Image.Image:
    """Load the pre-rendered PNG for page_no (1-based)."""
    path = config.PAGE_IMAGES_DIR / f"page_{page_no:03d}.png"
    if not path.exists():
        raise FileNotFoundError(f"Page image not found: {path}")
    return Image.open(path).convert("RGB")


# ---------------------------------------------------------------------------
# Highlight overlay
# ---------------------------------------------------------------------------

def draw_highlight(
    image: Image.Image,
    pixel_bbox: dict,
    color: tuple = (255, 165, 0, 90),
) -> Image.Image:
    """
    Draw a semi-transparent filled rectangle on `image` at `pixel_bbox`
    ({x0, y0, x1, y1}).  Returns a new image the same mode as `image`.
    """
    img = image.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle(
        [pixel_bbox["x0"], pixel_bbox["y0"], pixel_bbox["x1"], pixel_bbox["y1"]],
        fill=color,
        outline=(255, 140, 0, 255),
        width=3,
    )
    return img


def draw_highlights(
    image: Image.Image,
    pixel_bboxes: list[dict],
    color: tuple = (255, 165, 0, 90),
) -> Image.Image:
    """Same as draw_highlight but draws multiple rectangles in one pass."""
    if not pixel_bboxes:
        return image
    img = image.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    for bbox in pixel_bboxes:
        draw.rectangle(
            [bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]],
            fill=color,
            outline=(255, 140, 0, 255),
            width=3,
        )
    return img


# ---------------------------------------------------------------------------
# Hit-testing: find which element the user clicked on
# ---------------------------------------------------------------------------

def pixel_to_element(
    click_x: int,
    click_y: int,
    elements_on_page: list[dict],
    dpi: int = config.RENDER_DPI,
) -> Optional[dict]:
    """
    Given a click at (click_x, click_y) in image pixels, find the smallest
    element on this page whose bounding box contains the click.
    """
    matches: list[tuple[float, dict]] = []

    for elem in elements_on_page:
        bbox = elem["bbox_pdf"]
        page_h = elem["page_height_pdf"]

        px = pdf_coords_to_pixel(
            bbox["l"], bbox["b"], bbox["r"], bbox["t"],
            page_h, dpi=dpi,
        )

        if px["x0"] <= click_x <= px["x1"] and px["y0"] <= click_y <= px["y1"]:
            area = (px["x1"] - px["x0"]) * (px["y1"] - px["y0"])
            matches.append((area, elem))

    if not matches:
        return None

    # Return the element with the smallest area (most specific / innermost)
    matches.sort(key=lambda t: t[0])
    return matches[0][1]


# ---------------------------------------------------------------------------
# Convenience: get pixel bbox for an element
# ---------------------------------------------------------------------------

def element_pixel_bbox(elem: dict, dpi: int = config.RENDER_DPI) -> dict:
    bbox = elem["bbox_pdf"]
    return pdf_coords_to_pixel(
        bbox["l"], bbox["b"], bbox["r"], bbox["t"],
        elem["page_height_pdf"], dpi=dpi,
    )
