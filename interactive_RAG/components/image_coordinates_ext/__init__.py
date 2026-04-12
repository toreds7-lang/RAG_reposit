"""
Vendored fork of streamlit_image_coordinates that also emits modifier-key
state (shiftKey, ctrlKey/metaKey) on click. Used by app.py to implement
Ctrl/Shift+click multi-select on the PDF page image.

The component is named "image_coordinates_ext" so Streamlit's component
cache does not collide with the upstream package.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components
from PIL import Image


_frontend_dir = (Path(__file__).parent / "frontend").absolute()
_component_func = components.declare_component(
    "image_coordinates_ext", path=str(_frontend_dir)
)


def streamlit_image_coordinates_ext(
    source: Image.Image,
    key: Optional[str] = None,
    use_column_width: str | bool | None = None,
) -> Optional[dict]:
    """
    Display `source` (PIL image) and return the latest click as a dict:
    {x, y, width, height, shiftKey, ctrlKey, unix_time} — or None before any
    click has occurred.
    """
    buffered = BytesIO()
    source.save(buffered, format="PNG", compress_level=0)
    src = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")

    return _component_func(
        src=src,
        use_column_width=use_column_width,
        key=key,
    )
