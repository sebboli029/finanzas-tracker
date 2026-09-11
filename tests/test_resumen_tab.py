from datetime import date

import pandas as pd
from streamlit.testing.v1 import AppTest

from data_store import money
from resumen_tab import _estado_alerta_periodo


def _periodo_activo_hoy():
    return pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp(date.today()),
        "fecha_fin": pd.Timestamp(date.today()) + pd.Timedelta(days=14),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 600, "activa": False,
    }])


def _movimientos_con_gasto_frecuente():
    filas = []
    for _ in range(2):
        filas.append({"fecha": pd.Timestamp(date.today()), "tipo": "Gasto", "categoria": "🍽️ Comida",
                       "monto": 15, "periodo_id": "P1", "nota": "", "cuenta": "Efectivo"})
    return pd.DataFrame(filas)


def _app_header():
    import streamlit as st

    import resumen_tab
    resumen_tab.render_header(st.session_state["periodos"], st.session_state["movimientos"])


def test_render_header_muestra_las_4_metricas_sin_excepciones():
    at = AppTest.from_function(_app_header)
    at.session_state["periodos"] = _periodo_activo_hoy()
    at.session_state["movimientos"] = _movimientos_con_gasto_frecuente()
    at.run()
    assert not at.exception
    assert len(at.metric) == 4


def test_alerta_restante_negativo_con_recibido_positivo_da_error():
    nivel, mensaje = _estado_alerta_periodo(recibido=100, restante=-5)
    assert nivel == "error"
    assert money(5) in mensaje


def test_alerta_restante_negativo_con_recibido_cero_sigue_dando_error():
    nivel, mensaje = _estado_alerta_periodo(recibido=0, restante=-3)
    assert nivel == "error"


def test_alerta_restante_cero_con_recibido_positivo_da_warning():
    estado = _estado_alerta_periodo(recibido=100, restante=0)
    assert estado[0] == "warning"


def test_alerta_restante_justo_en_el_borde_del_umbral_no_da_warning():
    # 20% de 100 es 20 — restante == 20 no es "menos del 20%".
    estado = _estado_alerta_periodo(recibido=100, restante=20)
    assert estado is None


def test_alerta_restante_comodo_no_da_nada():
    estado = _estado_alerta_periodo(recibido=100, restante=80)
    assert estado is None


def test_alerta_recibido_cero_y_restante_cero_no_da_nada():
    estado = _estado_alerta_periodo(recibido=0, restante=0)
    assert estado is None


def _app_alerta():
    import streamlit as st

    import resumen_tab
    resumen_tab.render_alerta_periodo(st.session_state["periodos"], st.session_state["movimientos"])


def test_render_alerta_sin_periodos_no_muestra_nada():
    at = AppTest.from_function(_app_alerta)
    at.session_state["periodos"] = pd.DataFrame(
        columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"]
    )
    at.session_state["movimientos"] = pd.DataFrame(
        columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
    )
    at.run()
    assert not at.exception
    assert len(at.error) == 0
    assert len(at.warning) == 0


def test_render_alerta_con_restante_negativo_muestra_error():
    periodos = pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp(date.today()),
        "fecha_fin": pd.Timestamp(date.today()) + pd.Timedelta(days=14),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 10, "activa": False,
    }])
    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp(date.today()), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 15, "periodo_id": "P1", "nota": "", "cuenta": "Efectivo",
    }])
    at = AppTest.from_function(_app_alerta)
    at.session_state["periodos"] = periodos
    at.session_state["movimientos"] = movimientos
    at.run()
    assert not at.exception
    assert len(at.error) == 1


def test_render_alerta_con_poco_restante_muestra_warning():
    periodos = pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp(date.today()),
        "fecha_fin": pd.Timestamp(date.today()) + pd.Timedelta(days=14),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 100, "activa": False,
    }])
    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp(date.today()), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 90, "periodo_id": "P1", "nota": "", "cuenta": "Efectivo",
    }])
    at = AppTest.from_function(_app_alerta)
    at.session_state["periodos"] = periodos
    at.session_state["movimientos"] = movimientos
    at.run()
    assert not at.exception
    assert len(at.warning) == 1


def test_render_alerta_con_restante_comodo_no_muestra_nada():
    periodos = pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp(date.today()),
        "fecha_fin": pd.Timestamp(date.today()) + pd.Timedelta(days=14),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 100, "activa": False,
    }])
    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp(date.today()), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 10, "periodo_id": "P1", "nota": "", "cuenta": "Efectivo",
    }])
    at = AppTest.from_function(_app_alerta)
    at.session_state["periodos"] = periodos
    at.session_state["movimientos"] = movimientos
    at.run()
    assert not at.exception
    assert len(at.error) == 0
    assert len(at.warning) == 0
