from datetime import date

import pandas as pd
from streamlit.testing.v1 import AppTest

import charts
import data_store
from data_store import efectivo
from patrimonio import calcular_desglose


def test_calcular_desglose_junta_bancos_efectivo_e_inversion():
    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros", "Corriente"], "saldo": [100, 50]}))
    movimientos = pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-01"), "tipo": "Ingreso", "categoria": "🎒 Saldo inicial",
         "monto": 200, "periodo_id": pd.NA, "nota": "", "cuenta": pd.NA},
    ])
    desglose_inversion = {"FIC": 300, "Cripto": 10}

    resultado = calcular_desglose(movimientos, desglose_inversion)

    cuentas = data_store.load_cuentas()
    assert resultado["Bancos"] == 150
    assert resultado["Efectivo"] == efectivo(movimientos, cuentas)
    assert resultado["FIC"] == 300
    assert resultado["Cripto"] == 10


def _app_render_total():
    import streamlit as st

    import patrimonio
    patrimonio.render_total(st.session_state["desglose"], st.session_state["movimientos"])


def _metric(at, etiqueta):
    return next(m for m in at.metric if m.label == etiqueta)


def test_render_total_muestra_las_metricas_correctas():
    desglose = {"Bancos": 1000, "Efectivo": 50, "FIC": 200}
    movimientos = pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 80, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros"},
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Gasto", "categoria": "🚌 Transporte",
         "monto": 30, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros"},
    ])

    at = AppTest.from_function(_app_render_total)
    at.session_state["desglose"] = desglose
    at.session_state["movimientos"] = movimientos
    at.run()

    assert not at.exception
    assert _metric(at, "🏦 Patrimonio total").value == data_store.money(1250)
    assert _metric(at, "🧾 Gastado de todos los tiempos").value == data_store.money(110)


def test_render_total_registra_snapshot_de_hoy():
    desglose = {"Bancos": 1000}
    movimientos = pd.DataFrame(columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"])

    at = AppTest.from_function(_app_render_total)
    at.session_state["desglose"] = desglose
    at.session_state["movimientos"] = movimientos
    at.run()

    assert not at.exception
    historico = data_store.load_historico()
    fila_hoy = historico[historico.fecha == pd.Timestamp(date.today())]
    assert len(fila_hoy) == 1
    assert fila_hoy.iloc[0]["patrimonio_total"] == 1000


def test_render_total_con_patrimonio_cero_igual_registra_snapshot():
    at = AppTest.from_function(_app_render_total)
    at.session_state["desglose"] = {"Bancos": 0}
    at.session_state["movimientos"] = pd.DataFrame(
        columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
    )
    at.run()

    assert not at.exception
    historico = data_store.load_historico()
    fila_hoy = historico[historico.fecha == pd.Timestamp(date.today())]
    assert len(fila_hoy) == 1
    assert fila_hoy.iloc[0]["patrimonio_total"] == 0


def _app_render_distribucion():
    import streamlit as st

    import patrimonio
    patrimonio.render_distribucion(st.session_state["desglose"])


def test_distribucion_sin_categorias_positivas_muestra_caption_sin_grafico(monkeypatch):
    llamado = []
    monkeypatch.setattr(charts, "barras_horizontales", lambda *a, **k: llamado.append(True))

    at = AppTest.from_function(_app_render_distribucion)
    at.session_state["desglose"] = {"Bancos": 0, "Efectivo": -100}
    at.run()

    assert not at.exception
    assert llamado == []
    assert any("Todavía no hay plata" in c.value for c in at.caption)


def test_distribucion_con_categorias_positivas_llama_al_grafico(monkeypatch):
    llamado = []
    monkeypatch.setattr(charts, "barras_horizontales", lambda *a, **k: llamado.append(True))

    at = AppTest.from_function(_app_render_distribucion)
    at.session_state["desglose"] = {"Bancos": 100, "Cripto": 50}
    at.run()

    assert not at.exception
    assert llamado == [True]


def _app_render_evolucion():
    import patrimonio
    patrimonio.render_evolucion()


def test_evolucion_con_menos_de_2_dias_muestra_caption():
    at = AppTest.from_function(_app_render_evolucion)
    at.run()

    assert not at.exception
    assert any("volvé mañana" in c.value for c in at.caption)


def test_evolucion_con_2_o_mas_dias_renderiza_sin_excepcion():
    data_store.registrar_snapshot_patrimonio(date(2026, 8, 1), 1000)
    data_store.registrar_snapshot_patrimonio(date(2026, 8, 2), 1500)

    at = AppTest.from_function(_app_render_evolucion)
    at.run()

    assert not at.exception
