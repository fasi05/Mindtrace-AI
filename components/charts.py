"""Plotly figures (all built from stored records only)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from components.ui import C
from models.concepts import CONCEPTS, concept_name
from services import mastery as M


def _style(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["text"], family="Inter, system-ui, sans-serif"),
        margin=dict(l=10, r=10, t=30, b=10), legend=dict(font=dict(color=C["muted"])),
        hoverlabel=dict(bgcolor=C["elevated"], font_color=C["text"]))
    fig.update_xaxes(gridcolor=C["border"], zerolinecolor=C["border"], color=C["muted"])
    fig.update_yaxes(gridcolor=C["border"], zerolinecolor=C["border"], color=C["muted"])
    return fig


def _depth(cid: str) -> int:
    c = CONCEPTS[cid]
    return 0 if not c.prerequisites else 1 + max(_depth(p) for p in c.prerequisites)


def knowledge_map(rows: list) -> go.Figure:
    data = {r.concept_id: r for r in rows}
    layers: dict[int, list[str]] = {}
    for cid in CONCEPTS:
        layers.setdefault(_depth(cid), []).append(cid)
    pos = {}
    for d, ids in layers.items():
        for i, cid in enumerate(ids):
            pos[cid] = (d, (len(ids) - 1) / 2 - i)
    fig = go.Figure()
    for cid, c in CONCEPTS.items():
        for p in c.prerequisites:
            (x0, y0), (x1, y1) = pos[p], pos[cid]
            fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y",
                               showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.2, arrowcolor=C["neutral"],
                               standoff=18, startstandoff=18)
    xs, ys, colors, lines, texts, hover = [], [], [], [], [], []
    for cid in CONCEPTS:
        x, y = pos[cid]
        r = data.get(cid)
        xs.append(x); ys.append(y); texts.append(concept_name(cid).replace(" ", "<br>", 1))
        if r is None:
            colors.append(C["card"]); lines.append(C["neutral"])
            hover.append(f"<b>{concept_name(cid)}</b><br>No data yet")
        elif not M.is_assessed(r.attempts):
            colors.append(C["card"]); lines.append(C["accent"])
            hover.append(f"<b>{concept_name(cid)}</b><br>Insufficient data: {r.attempts}/{M.MIN_EVIDENCE} attempts")
        else:
            colors.append(C["success"] if r.mastery >= .75 else C["warn"] if r.mastery >= .5 else C["error"])
            lines.append(colors[-1])
            hover.append(f"<b>{concept_name(cid)}</b><br>Mastery {r.mastery:.0%} from {r.attempts} attempts")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=texts, textposition="bottom center",
                             textfont=dict(size=11, color=C["text"]), hovertext=hover, hoverinfo="text",
                             marker=dict(size=34, color=colors, line=dict(width=3, color=lines))))
    fig.update_xaxes(visible=False, range=[-.5, max(_depth(c) for c in CONCEPTS) + .5])
    fig.update_yaxes(visible=False, range=[-2.4, 2.2])
    fig.update_layout(showlegend=False)
    return _style(fig, 460)


def accuracy_over_time(att: pd.DataFrame) -> go.Figure:
    df = att.copy().reset_index(drop=True)
    df["n"] = df.index + 1
    df["cum"] = df["correct"].astype(float).expanding().mean()
    fig = go.Figure(go.Scatter(x=df["n"], y=df["cum"], mode="lines+markers", line=dict(color=C["accent"], width=3),
                               marker=dict(color=[C["success"] if c else C["error"] for c in df["correct"]], size=9),
                               hovertemplate="Attempt %{x}<br>Cumulative accuracy %{y:.0%}<extra></extra>"))
    fig.update_yaxes(range=[0, 1.05], tickformat=".0%", title="Cumulative accuracy")
    fig.update_xaxes(title="Attempt number", dtick=1)
    return _style(fig)


def activity_by_day(att: pd.DataFrame) -> go.Figure:
    df = att.copy()
    df["day"] = pd.to_datetime(df["created_at"]).dt.date
    g = df.groupby(["day", "correct"]).size().reset_index(name="n")
    fig = go.Figure()
    for flag, name, col in ((True, "Correct", C["success"]), (False, "Incorrect", C["error"])):
        s = g[g["correct"] == flag]
        fig.add_bar(x=s["day"], y=s["n"], name=name, marker_color=col)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="Attempts", dtick=1)
    return _style(fig)


def mastery_bars(rows: list) -> go.Figure:
    rows = sorted(rows, key=lambda r: r.mastery)
    fig = go.Figure(go.Bar(
        y=[concept_name(r.concept_id) for r in rows], x=[r.mastery for r in rows], orientation="h",
        marker_color=[(C["success"] if r.mastery >= .75 else C["warn"] if r.mastery >= .5 else C["error"])
                      if M.is_assessed(r.attempts) else C["neutral"] for r in rows],
        text=[f"{r.mastery:.0%} · {r.attempts} att." + ("" if M.is_assessed(r.attempts) else " (insufficient)") for r in rows],
        textposition="auto", hovertemplate="%{y}<br>%{x:.0%}<extra></extra>"))
    fig.update_xaxes(range=[0, 1], tickformat=".0%")
    return _style(fig, max(220, 60 * len(rows) + 60))


def misconception_counts(df: pd.DataFrame) -> go.Figure:
    g = df.groupby("misconception_category").size().sort_values().reset_index(name="n")
    fig = go.Figure(go.Bar(y=g["misconception_category"].str.replace("_", " "), x=g["n"], orientation="h",
                           marker_color=[C["warn"] if n >= 2 else C["accent"] for n in g["n"]]))
    fig.update_xaxes(dtick=1, title="Diagnoses")
    return _style(fig, max(200, 50 * len(g) + 80))


def before_after(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=df["label"], y=df["diagnosis"], name="Original answer", marker_color=C["error"])
    fig.add_bar(x=df["label"], y=df["practice"], name="Practice accuracy", marker_color=C["accent"])
    fig.add_bar(x=df["label"], y=df["transfer"], name="Transfer question", marker_color=C["success"])
    fig.update_layout(barmode="group")
    fig.update_yaxes(range=[0, 1.05], tickformat=".0%")
    return _style(fig)
