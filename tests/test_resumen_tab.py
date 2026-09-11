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


def test_mover_dinero_entre_cuentas_ajusta_ambos_saldos():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros", "Cuenta corriente"], "saldo": [100, 50]}))

    def _app():
        import pandas as pd

        import resumen_tab
        resumen_tab.render_cuentas(pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()
    at.selectbox(key="mov_origen").select("Ahorros").run()
    at.selectbox(key="mov_destino").select("Cuenta corriente").run()
    at.number_input(key="mov_monto").set_value(30).run()
    next(b for b in at.button if "Mover" == b.label.split(" ", 1)[-1] or b.label.endswith("Mover")).click().run()

    cuentas = data_store.load_cuentas()
    assert cuentas.loc[cuentas.cuenta == "Ahorros", "saldo"].iloc[0] == 70
    assert cuentas.loc[cuentas.cuenta == "Cuenta corriente", "saldo"].iloc[0] == 80


def test_mover_dinero_origen_igual_a_destino_da_error():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [100]}))

    def _app():
        import pandas as pd

        import resumen_tab
        resumen_tab.render_cuentas(pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()
    at.selectbox(key="mov_origen").select("Ahorros").run()
    at.selectbox(key="mov_destino").select("Ahorros").run()
    at.number_input(key="mov_monto").set_value(10).run()
    boton = next(b for b in at.button if b.label.endswith("Mover"))
    boton.click().run()

    assert any("cuentas distintas" in e.value for e in at.error)


def test_ajustar_saldo_base_permite_negativo_para_tarjeta_de_credito():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Tarjeta de crédito"], "saldo": [0]}))

    def _app():
        import pandas as pd

        import resumen_tab
        resumen_tab.render_cuentas(pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()
    at.number_input(key="cuenta_Tarjeta de crédito").set_value(-200).run()
    boton = next(b for b in at.button if "Guardar saldos" in b.label)
    boton.click().run()

    assert data_store.load_cuentas().loc[0, "saldo"] == -200


def test_efectivo_negativo_muestra_advertencia():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [1000]}))

    def _app():
        import pandas as pd

        import resumen_tab
        resumen_tab.render_cuentas(pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()

    assert any("efectivo calculado da negativo" in w.value for w in at.warning)


def test_mover_a_inversion_manual_resta_disponible_y_sube_inversion():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [500]}))
    data_store.save_inversiones(pd.DataFrame({"item": ["FIC"], "saldo": [0], "actualizado": ["2026-01-01"]}))
    movimientos = pd.DataFrame(columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"])

    def _app():
        import streamlit as st

        import resumen_tab
        resumen_tab.render_mover_a_inversion(st.session_state["movimientos"])

    at = AppTest.from_function(_app)
    at.session_state["movimientos"] = movimientos
    at.run()
    at.selectbox(key="mov_inv_origen").select("Ahorros").run()
    at.selectbox(key="mov_inv_destino").select("FIC").run()
    at.number_input(key="mov_inv_monto").set_value(100).run()
    boton = next(b for b in at.button if "Mover a inversión" in b.label)
    boton.click().run()

    assert data_store.load_cuentas().loc[0, "saldo"] == 400
    assert data_store.load_inversiones().loc[0, "saldo"] == 100
    guardado = data_store.load_movimientos()
    assert guardado.iloc[0]["categoria"] == "📈 Inversión"
    assert guardado.iloc[0]["monto"] == 100


def test_mover_a_inversion_monto_cero_da_error():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [500]}))
    data_store.save_inversiones(pd.DataFrame({"item": ["FIC"], "saldo": [0], "actualizado": ["2026-01-01"]}))

    def _app():
        import streamlit as st

        import resumen_tab
        resumen_tab.render_mover_a_inversion(st.session_state["movimientos"])

    at = AppTest.from_function(_app)
    at.session_state["movimientos"] = pd.DataFrame(
        columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
    )
    at.run()
    boton = next(b for b in at.button if "Mover a inversión" in b.label)
    boton.click().run()

    assert len(at.error) == 1
    assert data_store.load_inversiones().loc[0, "saldo"] == 0


def test_retirar_inversion_manual_sube_cuenta_y_baja_inversion():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [0]}))
    data_store.save_inversiones(pd.DataFrame({"item": ["FIC"], "saldo": [300], "actualizado": ["2026-01-01"]}))

    def _app():
        import streamlit as st

        import resumen_tab
        resumen_tab.render_retirar_inversion(st.session_state["movimientos"])

    at = AppTest.from_function(_app)
    at.session_state["movimientos"] = pd.DataFrame(
        columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
    )
    at.run()
    at.selectbox(key="ret_inv_origen").select("FIC").run()
    at.selectbox(key="ret_inv_destino").select("Ahorros").run()
    at.number_input(key="ret_inv_monto").set_value(100).run()
    boton = next(b for b in at.button if "Retirar de inversión" in b.label)
    boton.click().run()

    assert data_store.load_cuentas().loc[0, "saldo"] == 100
    assert data_store.load_inversiones().loc[0, "saldo"] == 200
    guardado = data_store.load_movimientos()
    assert guardado.iloc[0]["categoria"] == "📈 Retiro de inversión"


def test_retirar_inversion_manual_monto_mayor_al_saldo_da_error():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [0]}))
    data_store.save_inversiones(pd.DataFrame({"item": ["FIC"], "saldo": [50], "actualizado": ["2026-01-01"]}))

    def _app():
        import streamlit as st

        import resumen_tab
        resumen_tab.render_retirar_inversion(st.session_state["movimientos"])

    at = AppTest.from_function(_app)
    at.session_state["movimientos"] = pd.DataFrame(
        columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
    )
    at.run()
    at.selectbox(key="ret_inv_origen").select("FIC").run()
    at.number_input(key="ret_inv_monto").set_value(999).run()
    boton = next(b for b in at.button if "Retirar de inversión" in b.label)
    boton.click().run()

    assert len(at.error) == 1
    assert data_store.load_inversiones().loc[0, "saldo"] == 50
