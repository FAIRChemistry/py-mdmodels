from __future__ import annotations

from pathlib import Path


def load_html_asset(name: str) -> str:
    return (Path(__file__).resolve().parent / "assets" / name).read_text(
        encoding="utf-8"
    )
