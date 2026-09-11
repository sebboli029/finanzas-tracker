from datetime import date

import streamlit as st

import charts
from data_store import (
    PATRIMONIO_COLOR_MAP,
    efectivo,
    load_cuentas,
    load_historico,
    money,
    registrar_snapshot_patrimonio,
)


def calcular_desglose(movimientos, desglose_inversion):
    cuentas = load_cuentas()
    return {
        "Bancos": cuentas["saldo"].sum(),
        "Efectivo": efectivo(movimientos, cuentas),
        **desglose_inversion,
    }


def render_total(desglose, movimientos):
    total = sum(desglose.values())
    gastos = movimientos[movimientos.tipo == "Gasto"]
    gastado_historico = gastos.loc[gastos.categoria != "📈 Inversión", "monto"].sum()

    col1, col2 = st.columns(2)
    col1.metric("🏦 Patrimonio total", money(total))
    col2.metric("🧾 Gastado de todos los tiempos", money(gastado_historico))
    st.caption("Cuentas + efectivo + inversión, todo junto.")
    registrar_snapshot_patrimonio(date.today(), total)
    return total


def render_distribucion(desglose):
    st.subheader("📊 Distribución del patrimonio")
    positivos = {k: v for k, v in desglose.items() if v > 0}
    if not positivos:
        st.caption("Todavía no hay plata registrada en ninguna categoría.")
        return

    orden = sorted(positivos.items(), key=lambda kv: kv[1])
    etiquetas = [k for k, _ in orden]
    valores = [v for _, v in orden]
    colores = [PATRIMONIO_COLOR_MAP.get(k, "#898781") for k in etiquetas]
    charts.barras_horizontales(etiquetas, valores, colores, money)


def render_evolucion():
    st.subheader("📈 Evolución del patrimonio")
    historico = load_historico()
    if len(historico) < 2:
        st.caption("Todavía hay muy pocos días registrados — volvé mañana para empezar a ver la evolución.")
        return

    charts.linea(historico["fecha"], historico["patrimonio_total"], nombre="Patrimonio")


def render(movimientos, desglose_inversion):
    desglose = calcular_desglose(movimientos, desglose_inversion)
    render_total(desglose, movimientos)
    st.divider()
    render_distribucion(desglose)
    st.divider()
    render_evolucion()
