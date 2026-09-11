import streamlit as st

import inversion_tab
import patrimonio
import resumen_tab
import sidebar
from data_store import load_movimientos, load_periodos

st.set_page_config(page_title="Mis Finanzas 💸", page_icon="💸", layout="wide")

periodos = load_periodos()
movimientos = load_movimientos()

st.title("💸 Mis Finanzas — Panel de control")

resumen_tab.render_header(periodos, movimientos)
st.divider()

sidebar.render_nuevo_periodo(periodos)
sidebar.render_nuevo_movimiento(periodos, movimientos)

tab_resumen, tab_inversion, tab_patrimonio = st.tabs(["🏠 Resumen", "📈 Zona de inversión", "🏦 Patrimonio"])

with tab_resumen:
    resumen_tab.render(periodos, movimientos)

with tab_inversion:
    inversion_tab.render()

with tab_patrimonio:
    patrimonio.render(movimientos, inversion_tab.desglose_patrimonio_inversion())
