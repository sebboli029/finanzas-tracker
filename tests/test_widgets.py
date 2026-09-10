import pandas as pd
from streamlit.testing.v1 import AppTest


def _periodos(*ids, activa=None):
    """Fechas escalonadas (como los periodos reales, 14 días aparte) y en el
    pasado, para que ninguno quede "en curso" por fecha sin querer — así el
    resultado del fallback por fecha no depende de la fecha real en la que
    corre el test."""
    return pd.DataFrame([
        {
            "periodo_id": pid, "fecha_inicio": pd.Timestamp("2020-01-01") + pd.Timedelta(days=14 * i),
            "fecha_fin": pd.Timestamp("2020-01-01") + pd.Timedelta(days=14 * (i + 1)),
            "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0, "activa": pid == activa,
        }
        for i, pid in enumerate(ids)
    ])


def _periodos_vacios():
    return pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])


def _app_elegir_periodo_sin_default():
    import streamlit as st

    from widgets import elegir_periodo
    resultado = elegir_periodo(
        st.session_state["tipo"], st.session_state["categoria"], st.session_state["periodos"], key_prefix="t_",
    )
    st.session_state["resultado"] = resultado


def _app_elegir_periodo_con_default():
    import streamlit as st

    from widgets import elegir_periodo
    resultado = elegir_periodo(
        st.session_state["tipo"], st.session_state["categoria"], st.session_state["periodos"],
        periodo_default=st.session_state["periodo_default"], key_prefix="t_",
    )
    st.session_state["resultado"] = resultado


def test_gasto_sin_ninguno_activo_usa_el_mas_reciente_por_fecha():
    at = AppTest.from_function(_app_elegir_periodo_sin_default)
    at.session_state["tipo"] = "Gasto"
    at.session_state["categoria"] = "🚌 Transporte"
    at.session_state["periodos"] = _periodos("P1", "P2")
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == ("P2", False)


def test_gasto_con_un_periodo_marcado_activo_lo_usa_sin_importar_la_fecha():
    at = AppTest.from_function(_app_elegir_periodo_sin_default)
    at.session_state["tipo"] = "Gasto"
    at.session_state["categoria"] = "🚌 Transporte"
    at.session_state["periodos"] = _periodos("P1", "P2", activa="P1")
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == ("P1", False)


def test_gasto_desmarcando_el_checkbox_no_asocia_periodo():
    at = AppTest.from_function(_app_elegir_periodo_sin_default)
    at.session_state["tipo"] = "Gasto"
    at.session_state["categoria"] = "🚌 Transporte"
    at.session_state["periodos"] = _periodos("P1")
    at.run()

    at.checkbox(key="t_asociar_gasto").uncheck().run()

    assert at.session_state["resultado"] == (None, False)


def test_sin_periodos_siempre_devuelve_none_sin_importar_el_tipo():
    at = AppTest.from_function(_app_elegir_periodo_sin_default)
    at.session_state["tipo"] = "Gasto"
    at.session_state["categoria"] = "🚌 Transporte"
    at.session_state["periodos"] = _periodos_vacios()
    at.run()

    assert at.session_state["resultado"] == (None, False)

    at2 = AppTest.from_function(_app_elegir_periodo_sin_default)
    at2.session_state["tipo"] = "Ingreso"
    at2.session_state["categoria"] = "💰 Ingreso periódico"
    at2.session_state["periodos"] = _periodos_vacios()
    at2.run()

    assert at2.session_state["resultado"] == (None, True)


def test_ingreso_periodico_asocia_el_periodo_seleccionado():
    at = AppTest.from_function(_app_elegir_periodo_sin_default)
    at.session_state["tipo"] = "Ingreso"
    at.session_state["categoria"] = "💰 Ingreso periódico"
    at.session_state["periodos"] = _periodos("P1", "P2")
    at.run()

    assert at.session_state["resultado"] == ("P2", True)


def test_ingreso_no_periodico_no_asocia_periodo_aunque_existan():
    at = AppTest.from_function(_app_elegir_periodo_sin_default)
    at.session_state["tipo"] = "Ingreso"
    at.session_state["categoria"] = "🎁 Ingreso extra"
    at.session_state["periodos"] = _periodos("P1", "P2")
    at.run()

    assert at.session_state["resultado"] == (None, False)


def test_periodo_default_ya_no_existe_no_rompe_cae_al_indice_0():
    at = AppTest.from_function(_app_elegir_periodo_con_default)
    at.session_state["tipo"] = "Gasto"
    at.session_state["categoria"] = "🚌 Transporte"
    at.session_state["periodos"] = _periodos("P1", "P2")
    at.session_state["periodo_default"] = "P_borrado"
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == ("P1", False)


def _app_elegir_tipo_y_categoria():
    import streamlit as st

    from widgets import elegir_tipo_y_categoria
    resultado = elegir_tipo_y_categoria(
        tipo_default=st.session_state["tipo_default"],
        categoria_default=st.session_state["categoria_default"],
        key_prefix="tc_",
    )
    st.session_state["resultado"] = resultado


def test_categoria_default_invalida_cae_a_la_primera_de_la_lista():
    from data_store import GASTO_CATEGORIAS

    at = AppTest.from_function(_app_elegir_tipo_y_categoria)
    at.session_state["tipo_default"] = "Gasto"
    at.session_state["categoria_default"] = "no existe"
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == ("Gasto", GASTO_CATEGORIAS[0])


def test_tipo_default_ingreso_usa_categorias_de_ingreso():
    from data_store import INGRESO_CATEGORIAS

    at = AppTest.from_function(_app_elegir_tipo_y_categoria)
    at.session_state["tipo_default"] = "Ingreso"
    at.session_state["categoria_default"] = None
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == ("Ingreso", INGRESO_CATEGORIAS[0])


def _app_elegir_cuenta():
    import streamlit as st

    from widgets import elegir_cuenta
    resultado = elegir_cuenta(cuenta_default=st.session_state["cuenta_default"], key_prefix="c_")
    st.session_state["resultado"] = resultado


def test_cuenta_default_invalida_cae_a_efectivo():
    at = AppTest.from_function(_app_elegir_cuenta)
    at.session_state["cuenta_default"] = "cuenta que no existe"
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == "Efectivo"


def test_cuenta_default_valida_se_mantiene():
    at = AppTest.from_function(_app_elegir_cuenta)
    at.session_state["cuenta_default"] = "Ahorros"
    at.run()

    assert not at.exception
    assert at.session_state["resultado"] == "Ahorros"
