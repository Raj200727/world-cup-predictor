"""
sidebar.py

Sidebar controls and application settings.
"""

from __future__ import annotations

import streamlit as st
from components.layout import section
import math_engine as me

MODEL_OPTIONS = {
    "Historical": "historical",
    "Recent Form": "form",
    "Hybrid (Recommended)": "hybrid",
}

MODEL_OPTION_LABELS = list(MODEL_OPTIONS.keys())

DEFAULT_MODEL_LABEL = "Hybrid (Recommended)"


def render() -> tuple[str, dict]:
    """
    Render sidebar controls.

    Returns
    -------
    selected_model
        Internal model identifier.

    model_info
        Metadata describing the selected model.
    """

    section("Prediction Model")

    selected_label = st.radio(
        "Prediction model",
        options=MODEL_OPTION_LABELS,
        index=MODEL_OPTION_LABELS.index(DEFAULT_MODEL_LABEL),
        horizontal=True,
        label_visibility="collapsed",
    )

    selected_model = MODEL_OPTIONS[selected_label]

    model_info = me.describe_model(selected_model)

    return (
        selected_model,
        model_info,
    )
