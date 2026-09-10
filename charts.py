import plotly.graph_objects as go
import streamlit as st


def barras_horizontales(etiquetas, valores, colores, formatear):
    fig = go.Figure(go.Bar(
        x=list(valores), y=list(etiquetas), orientation="h",
        marker_color=list(colores),
        text=[formatear(v) for v in valores], textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(
        margin=dict(l=0, r=10, t=10, b=0), height=320,
        xaxis=dict(visible=False),
        yaxis=dict(title=None),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")


def linea(x, y, nombre=""):
    fig = go.Figure(go.Scatter(
        x=list(x), y=list(y), mode="lines+markers",
        line=dict(width=3), marker=dict(size=7), name=nombre,
    ))
    fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), height=300, showlegend=False)
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
