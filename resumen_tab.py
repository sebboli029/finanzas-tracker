from datetime import date

import pandas as pd
import streamlit as st

from data_store import (
    gastado_en_periodo,
    money,
    pendiente_por_cobrar,
    periodo_actual,
    regalos_total,
    saldo_restante_periodo,
)

UMBRAL_ALERTA_RESTANTE_PCT = 0.20  # advertir con menos del 20% del recibido restante


def _estado_alerta_periodo(recibido, restante):
    """None si todo bien; ("error", msg) si se pasó del presupuesto;
    ("warning", msg) si queda poco. El chequeo de negativo va primero y no
    depende de `recibido` — un periodo sin nada cobrado todavía pero con
    gasto ya cargado contra él también tiene que alertar."""
    if restante < 0:
        return "error", f"Te pasaste del saldo del periodo por {money(-restante)}."
    if recibido > 0 and restante < recibido * UMBRAL_ALERTA_RESTANTE_PCT:
        return "warning", f"Queda menos del {int(UMBRAL_ALERTA_RESTANTE_PCT * 100)}% del periodo — {money(restante)} disponibles."
    return None


def render_alerta_periodo(periodos, movimientos):
    p_actual = periodo_actual(periodos)
    if p_actual is None:
        return
    restante = saldo_restante_periodo(periodos, movimientos, p_actual.periodo_id)
    estado = _estado_alerta_periodo(p_actual.monto_recibido, restante)
    if estado is None:
        return
    nivel, mensaje = estado
    (st.error if nivel == "error" else st.warning)(mensaje)


def render_metricas(periodos, movimientos):
    p_actual = periodo_actual(periodos)
    if p_actual is not None:
        restante = money(saldo_restante_periodo(periodos, movimientos, p_actual.periodo_id))
        gastado = money(gastado_en_periodo(movimientos, p_actual.periodo_id))
        etiqueta_gastado = f"🧾 Gastado en el periodo ({p_actual.periodo_id})"
    else:
        restante = "—"
        gastado = "—"
        etiqueta_gastado = "🧾 Gastado en el periodo"

    metricas = [
        ("📅 Saldo restante del periodo", restante),
        (etiqueta_gastado, gastado),
        ("⏳ Pendiente por cobrar", money(pendiente_por_cobrar(periodos))),
        ("🎁 Regalos recibidos", money(regalos_total(movimientos))),
    ]
    for col, (label, valor) in zip(st.columns(len(metricas)), metricas):
        col.metric(label, valor)


def render_header(periodos, movimientos):
    st.subheader("🏠 Inicio")
    render_metricas(periodos, movimientos)
    render_alerta_periodo(periodos, movimientos)
