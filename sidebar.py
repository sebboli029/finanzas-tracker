from datetime import date

import pandas as pd
import streamlit as st

from data_store import (
    activar_periodo,
    ajustar_saldo_cuenta,
    delta_por_tipo,
    load_cuentas,
    save_cuentas,
    save_movimientos,
    save_periodos,
)
from widgets import elegir_cuenta, elegir_periodo, elegir_tipo_y_categoria


def render_nuevo_periodo(periodos):
    st.sidebar.header("➕ Nuevo periodo")
    with st.sidebar.form("nuevo_periodo", clear_on_submit=True):
        p_id = st.text_input("ID del periodo", placeholder="P-2026-08").strip()
        p_inicio = st.date_input("Fecha de inicio", value=date.today())
        p_origen = st.text_input("Origen (opcional)", placeholder="Sueldo, freelance, etc.")
        p_monto = st.number_input("Monto esperado", value=1000, step=50)

        if not st.form_submit_button("Crear periodo"):
            return
        if not p_id:
            st.sidebar.error("Ponle un ID al periodo.")
            return
        if p_id in periodos["periodo_id"].values:
            st.sidebar.error("Ya existe un periodo con ese ID.")
            return

        nuevo = pd.DataFrame([{
            "periodo_id": p_id,
            "fecha_inicio": pd.Timestamp(p_inicio),
            "fecha_fin": pd.Timestamp(p_inicio) + pd.Timedelta(days=14),
            "origen": p_origen,
            "monto_esperado": p_monto,
            "monto_recibido": 0,
            "activa": False,
        }])
        actualizados = activar_periodo(pd.concat([periodos, nuevo], ignore_index=True), p_id)
        save_periodos(actualizados)
        st.rerun()


def render_nuevo_movimiento(periodos, movimientos):
    with st.sidebar:
        st.header("📝 Registrar movimiento")
        m_tipo, m_categoria = elegir_tipo_y_categoria(key_prefix="m_")

        with st.form("nuevo_movimiento", clear_on_submit=True):
            m_fecha = st.date_input("Fecha", value=date.today(), key="mfecha")
            m_monto = st.number_input("Monto", min_value=0, step=1)
            m_periodo, es_ingreso_periodico = elegir_periodo(m_tipo, m_categoria, periodos, key_prefix="m_")
            m_cuenta = elegir_cuenta(key_prefix="m_")
            m_nota = st.text_input("Nota (opcional)")

            if not st.form_submit_button("Guardar movimiento"):
                return
            if m_monto <= 0:
                st.error("El monto debe ser mayor a cero.")
                return

            nuevo = pd.DataFrame([{
                "fecha": pd.Timestamp(m_fecha),
                "tipo": m_tipo,
                "categoria": m_categoria,
                "monto": m_monto,
                "periodo_id": m_periodo if m_periodo else pd.NA,
                "nota": m_nota,
                "cuenta": m_cuenta,
            }])
            movimientos = pd.concat([movimientos, nuevo], ignore_index=True)
            save_movimientos(movimientos)
            if es_ingreso_periodico and m_periodo:
                idx = periodos[periodos.periodo_id == m_periodo].index
                periodos.loc[idx, "monto_recibido"] += m_monto
                save_periodos(periodos)
            cuentas = load_cuentas()
            save_cuentas(ajustar_saldo_cuenta(cuentas, m_cuenta, delta_por_tipo(m_tipo, m_monto)))
            st.rerun()
