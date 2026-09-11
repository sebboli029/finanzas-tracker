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


import data_store
from resumen_tab import (
    _aplicar_efecto,
    _aplicar_filtro_historial,
    _campos_iguales,
    _fila_valida,
    _guardar_cambios_historial,
    _revertir_efecto,
    _tiene_periodo,
)
from data_store import GASTO_CATEGORIAS, INGRESO_CATEGORIAS


def test_tiene_periodo_con_nan_es_falso():
    assert _tiene_periodo(pd.NA) is False


def test_tiene_periodo_con_vacio_es_falso():
    assert _tiene_periodo("") is False


def test_tiene_periodo_con_id_real_es_verdadero():
    assert _tiene_periodo("P1") is True


def _fila_ok(**overrides):
    base = {"fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": GASTO_CATEGORIAS[0], "monto": 40}
    base.update(overrides)
    return pd.Series(base)


def test_fila_valida_sin_fecha_da_error():
    assert _fila_valida(_fila_ok(fecha=pd.NaT)) is not None


def test_fila_valida_sin_tipo_da_error():
    assert _fila_valida(_fila_ok(tipo="")) is not None


def test_fila_valida_monto_cero_da_error():
    assert _fila_valida(_fila_ok(monto=0)) is not None


def test_fila_valida_monto_none_da_error():
    assert _fila_valida(_fila_ok(monto=None)) is not None


def test_fila_valida_categoria_no_corresponde_al_tipo_da_error():
    fila = _fila_ok(tipo="Gasto", categoria=INGRESO_CATEGORIAS[0])
    assert _fila_valida(fila) is not None


def test_fila_valida_con_datos_correctos_no_da_error():
    assert _fila_valida(_fila_ok()) is None


def _fila_campos(**overrides):
    base = {
        "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 40.0, "periodo_id": "", "nota": "", "cuenta": "Efectivo",
    }
    base.update(overrides)
    return pd.Series(base)


def test_campos_iguales_tolera_fecha_date_vs_timestamp():
    import datetime
    antes = _fila_campos(fecha=pd.Timestamp("2026-08-01"))
    despues = _fila_campos(fecha=datetime.date(2026, 8, 1))
    assert _campos_iguales(antes, despues) is True


def test_campos_iguales_con_periodo_vacio_en_ambos_es_igual():
    antes = _fila_campos(periodo_id="")
    despues = _fila_campos(periodo_id="")
    assert _campos_iguales(antes, despues) is True


def test_campos_iguales_con_monto_distinto_no_es_igual():
    antes = _fila_campos(monto=40.0)
    despues = _fila_campos(monto=90.0)
    assert _campos_iguales(antes, despues) is False


def _periodo_unico(monto_recibido=600):
    # fecha_fin y activa van acá porque render_periodos_tabla las necesita
    # (load_periodos() real siempre las rellena si faltan) — los tests de
    # _aplicar_efecto/_revertir_efecto no las tocan, así que da igual para
    # ellos.
    return pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp("2026-08-01"),
        "fecha_fin": pd.Timestamp("2026-08-01") + pd.Timedelta(days=14),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": monto_recibido, "activa": False,
    }])


def _cuenta_unica(saldo=1000):
    return pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [saldo]})


def test_aplicar_y_luego_revertir_efecto_es_identidad():
    periodos = _periodo_unico()
    cuentas = _cuenta_unica()
    periodos_original = periodos.copy(deep=True)
    cuentas_original = cuentas.copy(deep=True)
    fila = pd.Series({"tipo": "Ingreso", "categoria": "💰 Ingreso periódico", "monto": 50, "periodo_id": "P1", "cuenta": "Ahorros"})

    _aplicar_efecto(periodos, cuentas, fila)
    _revertir_efecto(periodos, cuentas, fila)

    pd.testing.assert_frame_equal(periodos, periodos_original)
    pd.testing.assert_frame_equal(cuentas, cuentas_original)


def test_gasto_con_periodo_no_toca_monto_recibido():
    periodos = _periodo_unico(monto_recibido=600)
    cuentas = _cuenta_unica(saldo=100)
    fila = pd.Series({"tipo": "Gasto", "categoria": "🚌 Transporte", "monto": 30, "periodo_id": "P1", "cuenta": "Ahorros"})

    _aplicar_efecto(periodos, cuentas, fila)

    assert periodos.loc[0, "monto_recibido"] == 600
    assert cuentas.loc[0, "saldo"] == 70


def test_ingreso_no_periodico_con_periodo_no_toca_monto_recibido():
    periodos = _periodo_unico(monto_recibido=600)
    cuentas = _cuenta_unica(saldo=10)
    fila = pd.Series({"tipo": "Ingreso", "categoria": "🎁 Ingreso extra", "monto": 100, "periodo_id": "P1", "cuenta": "Ahorros"})

    _aplicar_efecto(periodos, cuentas, fila)

    assert periodos.loc[0, "monto_recibido"] == 600
    assert cuentas.loc[0, "saldo"] == 110


def test_efecto_sobre_cuenta_desconocida_no_rompe_nada():
    periodos = _periodo_unico()
    cuentas = _cuenta_unica()
    cuentas_original = cuentas.copy(deep=True)
    fila = pd.Series({"tipo": "Gasto", "categoria": "🍽️ Comida", "monto": 20, "periodo_id": pd.NA, "cuenta": "Efectivo"})

    _aplicar_efecto(periodos, cuentas, fila)

    pd.testing.assert_frame_equal(cuentas, cuentas_original)
    assert periodos.loc[0, "monto_recibido"] == 600


def _app_guardar_historial():
    import streamlit as st

    import resumen_tab
    # _guardar_cambios_historial llama st.rerun() al final si hubo cambios.
    # Acá se llama fuera de un callback de botón, así que cada rerun volvería
    # a disparar exactamente el mismo guardado: sin esto, entra en loop
    # infinito hasta el timeout de AppTest. Los saves ya ocurrieron antes de
    # la línea st.rerun(), así que anularlo no afecta lo que se está probando.
    st.rerun = lambda: None
    resumen_tab._guardar_cambios_historial(
        st.session_state["periodos"], st.session_state["movimientos"],
        st.session_state["original"], st.session_state["editado"],
    )


def _correr_guardado(periodos, movimientos, original, editado):
    import data_store as ds
    at = AppTest.from_function(_app_guardar_historial)
    at.session_state["periodos"] = periodos
    at.session_state["movimientos"] = movimientos
    at.session_state["original"] = original
    at.session_state["editado"] = editado
    at.run()
    assert not at.exception
    return at, ds


def test_guardar_historial_edita_monto_de_una_fila():
    import data_store as ds

    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 40, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros",
    }])
    ds.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [420]}))
    periodos = pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])

    original = pd.DataFrame([{
        "_id": 0, "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 40, "periodo_id": "", "cuenta": "Ahorros", "nota": "",
    }])
    editado = original.copy(deep=True)
    editado.loc[0, "monto"] = 25

    _correr_guardado(periodos, movimientos, original, editado)

    guardado = ds.load_movimientos()
    assert guardado.iloc[0]["monto"] == 25
    assert ds.load_cuentas().loc[0, "saldo"] == 435


def test_guardar_historial_borra_una_fila():
    import data_store as ds

    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 40, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros",
    }])
    ds.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [420]}))
    periodos = pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])

    original = pd.DataFrame([{
        "_id": 0, "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 40, "periodo_id": "", "cuenta": "Ahorros", "nota": "",
    }])
    editado = original.drop(index=0)

    _correr_guardado(periodos, movimientos, original, editado)

    guardado = ds.load_movimientos()
    assert len(guardado) == 0
    assert ds.load_cuentas().loc[0, "saldo"] == 460


def test_guardar_historial_agrega_una_fila_nueva():
    import data_store as ds

    movimientos = pd.DataFrame(columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"])
    ds.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [100]}))
    periodos = pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])

    original = pd.DataFrame(columns=["_id", "fecha", "tipo", "categoria", "monto", "periodo_id", "cuenta", "nota"])
    editado = pd.DataFrame([{
        "_id": pd.NA, "fecha": pd.Timestamp("2026-08-05"), "tipo": "Gasto", "categoria": "🍽️ Comida",
        "monto": 30, "periodo_id": "", "cuenta": "Ahorros", "nota": "",
    }])

    _correr_guardado(periodos, movimientos, original, editado)

    guardado = ds.load_movimientos()
    assert len(guardado) == 1
    assert guardado.iloc[0]["monto"] == 30
    assert ds.load_cuentas().loc[0, "saldo"] == 70


def test_guardar_historial_mueve_ingreso_periodico_de_un_periodo_a_otro_sin_duplicar():
    import data_store as ds

    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp("2026-08-01"), "tipo": "Ingreso", "categoria": "💰 Ingreso periódico",
        "monto": 500, "periodo_id": "P0", "nota": "", "cuenta": pd.NA,
    }])
    ds.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [0]}))
    periodos = pd.DataFrame([
        {"periodo_id": "P0", "fecha_inicio": pd.Timestamp("2026-07-01"),
         "origen": "Sueldo", "monto_esperado": 800, "monto_recibido": 500},
        {"periodo_id": "P1", "fecha_inicio": pd.Timestamp("2026-08-01"),
         "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0},
    ])

    original = pd.DataFrame([{
        "_id": 0, "fecha": pd.Timestamp("2026-08-01"), "tipo": "Ingreso", "categoria": "💰 Ingreso periódico",
        "monto": 500, "periodo_id": "P0", "cuenta": "", "nota": "",
    }])
    editado = original.copy(deep=True)
    editado.loc[0, "periodo_id"] = "P1"

    _correr_guardado(periodos, movimientos, original, editado)

    guardados = ds.load_periodos()
    assert guardados.loc[guardados.periodo_id == "P0", "monto_recibido"].iloc[0] == 0
    assert guardados.loc[guardados.periodo_id == "P1", "monto_recibido"].iloc[0] == 500


def test_guardar_historial_fila_invalida_no_bloquea_las_demas():
    import data_store as ds

    movimientos = pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 40, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros"},
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Gasto", "categoria": "🚌 Transporte",
         "monto": 15, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros"},
    ])
    ds.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [200]}))
    periodos = pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])

    original = pd.DataFrame([
        {"_id": 0, "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 40, "periodo_id": "", "cuenta": "Ahorros", "nota": ""},
        {"_id": 1, "fecha": pd.Timestamp("2026-08-02"), "tipo": "Gasto", "categoria": "🚌 Transporte",
         "monto": 15, "periodo_id": "", "cuenta": "Ahorros", "nota": ""},
    ])
    editado = original.copy(deep=True)
    editado.loc[0, "monto"] = 35  # válido
    editado.loc[1, "monto"] = 0  # inválido

    at, ds_mod = _correr_guardado(periodos, movimientos, original, editado)

    assert len(at.error) == 1
    guardado = ds_mod.load_movimientos()
    assert guardado.loc[guardado["categoria"] == "🍽️ Comida", "monto"].iloc[0] == 35
    assert guardado.loc[guardado["categoria"] == "🚌 Transporte", "monto"].iloc[0] == 15


def test_guardar_historial_no_permite_editar_fila_de_inversion():
    import data_store as ds

    movimientos = pd.DataFrame([{
        "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "📈 Inversión",
        "monto": 100, "periodo_id": pd.NA, "nota": "Transferencia a FIC", "cuenta": "Ahorros",
    }])
    # La fila de Inversión se rechaza sin aplicar ningún cambio, así que
    # _guardar_cambios_historial nunca llega a guardar — sin este seed, el
    # archivo en disco quedaría con el CSV vacío que siembra el fixture de
    # aislamiento y el assert de abajo explotaría por índice fuera de rango.
    ds.save_movimientos(movimientos)
    ds.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [50]}))
    periodos = pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido"])

    original = pd.DataFrame([{
        "_id": 0, "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "📈 Inversión",
        "monto": 100, "periodo_id": "", "cuenta": "Ahorros", "nota": "Transferencia a FIC",
    }])
    editado = original.copy(deep=True)
    editado.loc[0, "monto"] = 50

    at, ds_mod = _correr_guardado(periodos, movimientos, original, editado)

    assert len(at.error) == 1
    assert ds_mod.load_movimientos().iloc[0]["monto"] == 100


def test_filtro_sin_criterios_devuelve_todo():
    tabla = pd.DataFrame({"fecha": [pd.Timestamp("2026-08-01")], "categoria": ["🍽️ Comida"], "cuenta": ["Ahorros"]})
    assert len(_aplicar_filtro_historial(tabla, None, None, [], [])) == 1


def test_filtro_por_categoria():
    tabla = pd.DataFrame({
        "fecha": [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-02")],
        "categoria": ["🍽️ Comida", "🚌 Transporte"],
        "cuenta": ["Ahorros", "Ahorros"],
    })
    resultado = _aplicar_filtro_historial(tabla, None, None, ["🍽️ Comida"], [])
    assert len(resultado) == 1
    assert resultado.iloc[0]["categoria"] == "🍽️ Comida"


def test_filtro_por_cuenta():
    tabla = pd.DataFrame({
        "fecha": [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-02")],
        "categoria": ["🍽️ Comida", "🚌 Transporte"],
        "cuenta": ["Ahorros", "Corriente"],
    })
    resultado = _aplicar_filtro_historial(tabla, None, None, [], ["Corriente"])
    assert len(resultado) == 1
    assert resultado.iloc[0]["cuenta"] == "Corriente"


def test_deshacer_historial_sin_nada_para_deshacer_avisa():
    def _app():
        import resumen_tab
        resumen_tab.render_deshacer_historial()

    at = AppTest.from_function(_app)
    at.run()
    boton = next(b for b in at.button if "Deshacer" in b.label)
    boton.click().run()

    assert any("No hay nada para deshacer" in i.value for i in at.info)


def test_render_periodos_tabla_no_explota_con_datos_sembrados():
    # AppTest.from_function() solo serializa el cuerpo de `_app` — no tiene
    # acceso a los nombres del módulo de test que la rodea (como
    # _periodo_unico), así que el fixture se pasa por session_state en vez
    # de llamarse directo adentro de `_app`.
    def _app():
        import pandas as pd
        import streamlit as st

        import resumen_tab
        resumen_tab.render_periodos_tabla(st.session_state["periodos"], pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.session_state["periodos"] = _periodo_unico()
    at.run()
    assert not at.exception


def test_render_historial_no_explota_con_datos_sembrados():
    def _app():
        import pandas as pd
        import streamlit as st

        import resumen_tab
        resumen_tab.render_historial(st.session_state["periodos"], pd.DataFrame([{
            "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
            "monto": 40, "periodo_id": "P1", "nota": "", "cuenta": "Ahorros",
        }]))

    at = AppTest.from_function(_app)
    at.session_state["periodos"] = _periodo_unico()
    at.run()
    assert not at.exception
