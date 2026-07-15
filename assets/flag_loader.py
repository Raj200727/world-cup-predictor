from pathlib import Path
import base64
import streamlit as st


@st.cache_data
def load_svg(flag_filename: str) -> str:
    """
    Returns a base64 data URI for an SVG flag.
    """

    if not flag_filename:
        return ""

    svg_path = Path("assets/flags") / flag_filename

    svg_text = svg_path.read_text(encoding="utf-8")

    svg_base64 = base64.b64encode(
        svg_text.encode("utf-8")
    ).decode("utf-8")

    return f"data:image/svg+xml;base64,{svg_base64}"