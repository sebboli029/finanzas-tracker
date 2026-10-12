import pandas as pd
from streamlit.testing.v1 import AppTest


def _boton(at, etiqueta):
    return next(b for b in at.button if b.label == etiqueta)


def _texto(at, etiqueta):
    return next(t for t in at.text_input if t.label == etiqueta)


def _numero(at, etiqueta):
    return next(n for n in at.number_input if n.label == etiqueta)


def _periodos_vacios():
    return pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])


def _movimientos_vacios():
    return pd.DataFrame(columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"])


def _app_render_nuevo_periodo():
    import streamlit as st

    import sidebar
    sidebar.render_nuevo_periodo(st.session_state["periodos"])


def test_nuevo_periodo_alta_valida_se_guarda():
    import data_store

    at = AppTest.from_function(_app_render_nuevo_periodo)
    at.session_state["periodos"] = _periodos_vacios()
    at.run()

    _texto(at, "ID del periodo").set_value("P-2026-08").run()
    _boton(at, "Crear periodo").click().run()

    guardados = data_store.load_periodos()
    assert len(guardados) == 1
    assert guardados.iloc[0]["periodo_id"] == "P-2026-08"
    assert guardados.iloc[0]["monto_recibido"] == 0
    assert guardados.iloc[0]["monto_esperado"] == 1000
    assert guardados.iloc[0]["fecha_fin"] == guardados.iloc[0]["fecha_inicio"] + pd.Timedelta(days=14)


def test_nuevo_periodo_id_vacio_da_error():
    import data_store

    at = AppTest.from_function(_app_render_nuevo_periodo)
    at.session_state["periodos"] = _periodos_vacios()
    at.run()

    _boton(at, "Crear periodo").click().run()

    assert len(at.error) == 1
    assert len(data_store.load_periodos()) == 0


def test_nuevo_periodo_id_duplicado_da_error():
    import data_store

    periodos = pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp("2026-08-01"),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0,
    }])
    data_store.save_periodos(periodos)

    at = AppTest.from_function(_app_render_nuevo_periodo)
    at.session_state["periodos"] = periodos
    at.run()

    _texto(at, "ID del periodo").set_value("P1").run()
    _boton(at, "Crear periodo").click().run()

    assert len(at.error) == 1
    assert len(data_store.load_periodos()) == 1


def _app_render_nuevo_movimiento():
    import streamlit as st

    import sidebar
    sidebar.render_nuevo_movimiento(st.session_state["periodos"], st.session_state["movimientos"])


def _periodo_p1(monto_recibido=200):
    return pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp("2026-08-01"), "fecha_fin": pd.Timestamp("2026-08-15"),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": monto_recibido, "activa": False,
    }])


def test_gasto_con_periodo_y_cuenta_bancaria_resta_saldo_no_toca_recibido():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [500]}))
    periodos = _periodo_p1(monto_recibido=200)
    data_store.save_periodos(periodos)

    at = AppTest.from_function(_app_render_nuevo_movimiento)
    at.session_state["periodos"] = periodos
    at.session_state["movimientos"] = _movimientos_vacios()
    at.run()

    _numero(at, "Monto").set_value(30).run()
    at.selectbox(key="m_cuenta").select("Ahorros").run()
    _boton(at, "Guardar movimiento").click().run()

    guardado = data_store.load_movimientos()
    assert len(guardado) == 1
    assert guardado.iloc[0]["tipo"] == "Gasto"
    assert guardado.iloc[0]["monto"] == 30
    assert guardado.iloc[0]["periodo_id"] == "P1"
    assert data_store.load_cuentas().loc[0, "saldo"] == 470
    assert data_store.load_periodos().loc[0, "monto_recibido"] == 200


def test_ingreso_periodico_con_periodo_suma_saldo_y_recibido():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [50]}))
    at = AppTest.from_function(_app_render_nuevo_movimiento)
    at.session_state["periodos"] = _periodo_p1(monto_recibido=200)
    at.session_state["movimientos"] = _movimientos_vacios()
    at.run()

    at.radio(key="m_tipo").set_value("Ingreso").run()
    _numero(at, "Monto").set_value(500).run()
    at.selectbox(key="m_cuenta").select("Ahorros").run()
    _boton(at, "Guardar movimiento").click().run()

    guardado = data_store.load_movimientos()
    assert len(guardado) == 1
    assert guardado.iloc[0]["tipo"] == "Ingreso"
    assert guardado.iloc[0]["categoria"] == "💰 Ingreso periódico"
    assert data_store.load_cuentas().loc[0, "saldo"] == 550
    assert data_store.load_periodos().loc[0, "monto_recibido"] == 700


def test_monto_cero_da_error_y_no_guarda_nada():
    import data_store

    at = AppTest.from_function(_app_render_nuevo_movimiento)
    at.session_state["periodos"] = _periodos_vacios()
    at.session_state["movimientos"] = _movimientos_vacios()
    at.run()

    _boton(at, "Guardar movimiento").click().run()

    assert len(at.error) == 1
    assert len(data_store.load_movimientos()) == 0


def test_cuenta_efectivo_no_modifica_cuentas_csv():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [50]}))
    at = AppTest.from_function(_app_render_nuevo_movimiento)
    at.session_state["periodos"] = _periodos_vacios()
    at.session_state["movimientos"] = _movimientos_vacios()
    at.run()

    _numero(at, "Monto").set_value(20).run()
    _boton(at, "Guardar movimiento").click().run()

    assert len(data_store.load_movimientos()) == 1
    assert data_store.load_movimientos().iloc[0]["cuenta"] == "Efectivo"
    assert data_store.load_cuentas().loc[0, "saldo"] == 50


def test_gasto_sin_asociar_a_periodo_deja_periodo_id_vacio():
    import data_store

    at = AppTest.from_function(_app_render_nuevo_movimiento)
    at.session_state["periodos"] = _periodo_p1()
    at.session_state["movimientos"] = _movimientos_vacios()
    at.run()

    at.checkbox(key="m_asociar_gasto").uncheck().run()
    _numero(at, "Monto").set_value(30).run()
    _boton(at, "Guardar movimiento").click().run()

    guardado = data_store.load_movimientos()
    assert len(guardado) == 1
    assert pd.isna(guardado.iloc[0]["periodo_id"])
