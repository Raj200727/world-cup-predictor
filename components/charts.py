"""
charts.py

Plotly visualizations for the prediction engine.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

import math_engine as me

from assets.theme import (
    CLR_BG,
    CLR_TEXT,
    CLR_MUTED,
    CLR_BORDER,
    CLR_HOME,
    CLR_DRAW,
    CLR_AWAY,
)

def make_outcome_bar(result: me.MatchResult) -> go.Figure:
    """
    Horizontal probability bar — home / draw / away stacked.
    This is the signature visual: bar widths ARE the probabilities.
    """
    hw = result.home_win_prob
    d  = result.draw_prob
    aw = result.away_win_prob

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[hw], y=[""], orientation="h",
        marker_color=CLR_HOME,
        name=result.home_team,
        text=f"{hw:.0%}",
        textposition="inside",
        textfont=dict(family="Space Mono", size=13, color=CLR_BG),
        hovertemplate=f"<b>{result.home_team} win</b><br>{hw:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=[d], y=[""], orientation="h",
        marker_color=CLR_DRAW,
        name="Draw",
        text=f"{d:.0%}" if d >= 0.10 else "",
        textposition="inside",
        textfont=dict(family="Space Mono", size=13, color=CLR_TEXT),
        hovertemplate=f"<b>Draw</b><br>{d:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=[aw], y=[""], orientation="h",
        marker_color=CLR_AWAY,
        name=result.away_team,
        text=f"{aw:.0%}",
        textposition="inside",
        textfont=dict(family="Space Mono", size=13, color=CLR_TEXT),
        hovertemplate=f"<b>{result.away_team} win</b><br>{aw:.1%}<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        height=70,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False),
    )
    return fig

def make_scoreline_chart(result: me.MatchResult, top_n: int = 8) -> go.Figure:
    """
    Horizontal bar chart of the top N most likely exact scorelines.
    """
    scorelines = result.scorelines[:top_n]
    labels  = [s[0] for s in scorelines][::-1]
    probs   = [s[1] for s in scorelines][::-1]

    # Colour each bar by outcome
    colors = []
    for lbl in labels:
        parts = lbl.replace("–", "-").split("-")
        try:
            h, a = int(parts[0]), int(parts[1])
        except ValueError:
            colors.append(CLR_DRAW)
            continue
        if h > a:
            colors.append(CLR_HOME)
        elif a > h:
            colors.append(CLR_AWAY)
        else:
            colors.append(CLR_DRAW)

    fig = go.Figure(go.Bar(
        x=probs,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{p:.1%}" for p in probs],
        textposition="outside",
        textfont=dict(family="Space Mono", size=11, color=CLR_TEXT),
        hovertemplate="%{y}  →  %{x:.1%}<extra></extra>",
        cliponaxis=False,
    ))

    fig.update_layout(
        height=max(260, top_n * 38),
        margin=dict(l=0, r=60, t=4, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            visible=True,
            showgrid=True,
            gridcolor=CLR_BORDER,
            tickformat=".0%",
            tickfont=dict(family="Space Mono", size=10, color=CLR_MUTED),
            zeroline=False,
            range=[0, max(probs) * 1.35],
        ),
        yaxis=dict(
            tickfont=dict(family="Space Mono", size=12, color=CLR_TEXT),
            gridcolor="rgba(0,0,0,0)",
        ),
        bargap=0.28,
    )
    return fig

def make_scoreline_heatmap(result: me.MatchResult) -> go.Figure:
    """
    Goals probability heatmap — the raw Poisson matrix, capped at 5×5
    for readability.
    """
    matrix = result.matrix[:6, :6]   # 0–5 goals each side
    home   = result.home_team
    away   = result.away_team

    z_text = [[f"{matrix[i, j]:.1%}" for j in range(6)] for i in range(6)]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        text=z_text,
        texttemplate="%{text}",
        textfont=dict(family="Space Mono", size=10),
        colorscale=[
            [0.0,  "#0D1F17"],
            [0.15, "#1A4B2F"],
            [0.40, "#2ECC71"],
            [0.70, "#9EF53A"],
            [1.0,  "#D4F13A"],
        ],
        showscale=False,
        hovertemplate=(
            f"{home} %{{y}}–%{{x}} {away}<br>Probability: %{{text}}<extra></extra>"
        ),
    ))

    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title=dict(text=away, font=dict(family="Space Grotesk", size=12,
                                            color=CLR_MUTED)),
            tickvals=list(range(6)),
            tickfont=dict(family="Space Mono", size=11, color=CLR_TEXT),
        ),
        yaxis=dict(
            title=dict(text=home, font=dict(family="Space Grotesk", size=12,
                                            color=CLR_MUTED)),
            tickvals=list(range(6)),
            tickfont=dict(family="Space Mono", size=11, color=CLR_TEXT),
            autorange="reversed",
        ),
    )
    return fig

def render(result) -> None:
    """
    Render all prediction charts.
    """

    st.markdown(
        '<div class="section-label">Win probability</div>',
        unsafe_allow_html=True,
    )

    st.plotly_chart(
        make_outcome_bar(result),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.markdown(
        '<div class="section-label">Most likely scorelines</div>',
        unsafe_allow_html=True,
    )

    tab_bar, tab_heat = st.tabs(
        [
            "Top scorelines",
            "Goal matrix",
        ]
    )

    with tab_bar:

        n_scorelines = st.slider(
            "Number of scorelines to show",
            min_value=5,
            max_value=15,
            value=8,
            step=1,
            label_visibility="collapsed",
        )

        st.plotly_chart(
            make_scoreline_chart(
                result,
                top_n=n_scorelines,
            ),
            use_container_width=True,
            config={
                "displayModeBar": False,
            },
        )

        st.markdown(
            f"<div style='display:flex;gap:16px;margin-top:4px'>"
            f"<span style='font-size:0.72rem;color:{CLR_HOME};font-family:monospace'>"
            f"■ {result.home_team} win</span>"
            f"<span style='font-size:0.72rem;color:{CLR_DRAW};font-family:monospace'>"
            f"■ Draw</span>"
            f"<span style='font-size:0.72rem;color:{CLR_AWAY};font-family:monospace'>"
            f"■ {result.away_team} win</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with tab_heat:

        st.markdown(
            "<div style='font-size:0.78rem;color:"
            + CLR_MUTED
            + ";margin-bottom:8px'>"
            "Cell shows the probability of each exact scoreline (0–5 goals each side). "
            "Brighter = more likely."
            "</div>",
            unsafe_allow_html=True,
        )

        st.plotly_chart(
            make_scoreline_heatmap(result),
            use_container_width=True,
            config={"displayModeBar": False},
        )