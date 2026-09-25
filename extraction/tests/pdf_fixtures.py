"""Shared helpers: build synthetic PDFs with precise, known layouts."""

from __future__ import annotations

import io

import pymupdf
from PIL import Image


def solid_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """A solid-color PNG as raw bytes."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def new_page(width: float = 595, height: float = 842) -> tuple[pymupdf.Document, pymupdf.Page]:
    """A new single-page PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    return doc, page


def place_image(page: pymupdf.Page, rect: tuple[float, float, float, float], png: bytes) -> None:
    page.insert_image(pymupdf.Rect(*rect), stream=png)


def add_text(page: pymupdf.Page, text: str, point: tuple[float, float], fontsize: float = 11) -> None:
    page.insert_text(pymupdf.Point(*point), text, fontsize=fontsize)
