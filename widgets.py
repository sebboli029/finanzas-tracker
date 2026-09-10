import pandas as pd
import streamlit as st

from data_store import (
    CUENTAS_CON_EFECTIVO,
    GASTO_CATEGORIAS,
    INGRESO_CATEGORIAS,
    INGRESO_PERIODICO_CATEGORIAS,
    periodo_actual,
)

# Widgets compartidos entre el formulario de "nuevo movimiento" (sidebar.py)
# y un futuro editor de movimiento existente — misma lógica, distinto valor
# por defecto según si estás creando o editando.

# Sentinel para distinguir "creando movimiento nuevo" (sin periodo_default)
# de "editando uno existente sin periodo" (periodo_default = NaN).
_SIN_ESPECIFICAR = object()


def elegir_tipo_y_categoria(tipo_default="Gasto", categoria_default=None, key_prefix=""):
    tipo = st.radio(
        "Tipo", ["Gasto", "Ingreso"], horizontal=True,
        index=0 if tipo_default == "Gasto" else 1, key=f"{key_prefix}tipo",
    )
    categorias = GASTO_CATEGORIAS if tipo == "Gasto" else INGRESO_CATEGORIAS
    actual = categoria_default if categoria_default in categorias else categorias[0]
    categoria = st.selectbox(
        "Categoría", categorias, index=categorias.index(actual), key=f"{key_prefix}categoria"
    )
    return tipo, categoria


def elegir_periodo(tipo, categoria, periodos, periodo_default=_SIN_ESPECIFICAR, key_prefix=""):
    es_ingreso_periodico = tipo == "Ingreso" and categoria in INGRESO_PERIODICO_CATEGORIAS
    opciones = periodos["periodo_id"].tolist()
    tenia_periodo = periodo_default is _SIN_ESPECIFICAR or pd.notna(periodo_default)

    if periodo_default is _SIN_ESPECIFICAR:
        activo = periodo_actual(periodos)
        periodo_default = activo.periodo_id if activo is not None else None

    if tipo == "Gasto" and opciones:
        asociar = st.checkbox(
            "💰 Este gasto es de este periodo", value=tenia_periodo, key=f"{key_prefix}asociar_gasto",
        )
        if not asociar:
            st.caption("Este gasto no se resta de ningún periodo — queda aparte.")
            return None, es_ingreso_periodico

    if (tipo == "Gasto" or es_ingreso_periodico) and opciones:
        idx = opciones.index(periodo_default) if periodo_default in opciones else 0
        periodo = st.selectbox(
            "Periodo asociado", opciones, index=idx, key=f"{key_prefix}periodo"
        )
        return periodo, es_ingreso_periodico
    st.caption("Este ingreso no descuenta el pendiente de ningún periodo — se suma aparte a tu saldo.")
    return None, es_ingreso_periodico


def elegir_cuenta(cuenta_default=None, key_prefix=""):
    idx = (
        CUENTAS_CON_EFECTIVO.index(cuenta_default)
        if cuenta_default in CUENTAS_CON_EFECTIVO
        else CUENTAS_CON_EFECTIVO.index("Efectivo")
    )
    return st.selectbox("¿En qué cuenta?", CUENTAS_CON_EFECTIVO, index=idx, key=f"{key_prefix}cuenta")
