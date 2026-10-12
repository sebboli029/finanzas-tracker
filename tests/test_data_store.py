from datetime import date as _date

import pandas as pd

import config
import data_store
from data_store import (
    activar_periodo,
    ajustar_saldo_cuenta,
    ajustar_saldo_inversion,
    delta_por_tipo,
    efectivo,
    gastado_en_periodo,
    pendiente_por_cobrar,
    periodo_actual,
    regalos_total,
    registrar_compra_activo,
    registrar_snapshot_patrimonio,
    registrar_venta_activo,
    saldo_disponible,
    saldo_restante_periodo,
)


def test_money_formatea_moneda_base_por_defecto_usd():
    assert data_store.money(1234567) == "$1,234,567"


def test_money_usa_separador_de_miles_de_la_moneda_configurada(monkeypatch):
    monkeypatch.setattr(config, "MONEDA_BASE", "COP")
    assert data_store.money(1234567) == "$1.234.567"


def test_formato_moneda_desconocida_cae_a_default():
    fmt = data_store.formato_moneda("XYZ")
    assert fmt["simbolo"] == "$"
    assert fmt["separador_miles"] == ","


def test_guardar_con_respaldo_copia_el_contenido_previo_antes_de_sobreescribir(tmp_path):
    archivo = tmp_path / "datos.csv"
    anterior = pd.DataFrame({"a": [1, 2]})
    anterior.to_csv(archivo, index=False)

    nuevo = pd.DataFrame({"a": [3, 4]})
    data_store.guardar_con_respaldo(archivo, nuevo)

    backups = list((tmp_path / ".backups").glob("datos.*.csv"))
    assert len(backups) == 1
    pd.testing.assert_frame_equal(pd.read_csv(backups[0]), anterior)
    pd.testing.assert_frame_equal(pd.read_csv(archivo), nuevo)


def test_guardar_con_respaldo_primer_guardado_no_crea_respaldo(tmp_path):
    archivo = tmp_path / "nuevo.csv"
    data_store.guardar_con_respaldo(archivo, pd.DataFrame({"a": [1]}))

    assert not (tmp_path / ".backups").exists()
    pd.testing.assert_frame_equal(pd.read_csv(archivo), pd.DataFrame({"a": [1]}))


def test_guardar_con_respaldo_poda_a_max_backups_por_archivo(tmp_path):
    archivo = tmp_path / "datos.csv"
    pd.DataFrame({"a": [0]}).to_csv(archivo, index=False)

    for i in range(1, data_store.MAX_BACKUPS_POR_ARCHIVO + 3):
        data_store.guardar_con_respaldo(archivo, pd.DataFrame({"a": [i]}))

    backups = list((tmp_path / ".backups").glob("datos.*.csv"))
    assert len(backups) == data_store.MAX_BACKUPS_POR_ARCHIVO


def test_deshacer_ultimo_cambio_restaura_y_consume_el_respaldo_mas_reciente(tmp_path):
    archivo = tmp_path / "datos.csv"
    pd.DataFrame({"a": [1]}).to_csv(archivo, index=False)
    data_store.guardar_con_respaldo(archivo, pd.DataFrame({"a": [2]}))
    data_store.guardar_con_respaldo(archivo, pd.DataFrame({"a": [3]}))

    assert data_store.deshacer_ultimo_cambio(archivo) is True
    assert pd.read_csv(archivo)["a"].iloc[0] == 2

    assert data_store.deshacer_ultimo_cambio(archivo) is True
    assert pd.read_csv(archivo)["a"].iloc[0] == 1


def test_deshacer_ultimo_cambio_sin_respaldos_devuelve_false(tmp_path):
    archivo = tmp_path / "solo.csv"
    pd.DataFrame({"a": [1]}).to_csv(archivo, index=False)

    assert data_store.deshacer_ultimo_cambio(archivo) is False


def _periodos():
    return pd.DataFrame([
        {"periodo_id": "P1", "fecha_inicio": pd.Timestamp("2026-08-01"),
         "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 600},
        {"periodo_id": "P0", "fecha_inicio": pd.Timestamp("2026-07-01"),
         "origen": "Sueldo", "monto_esperado": 800, "monto_recibido": 800},
    ])


def _movimientos_periodos():
    return pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 40, "periodo_id": "P1", "nota": "", "cuenta": "Efectivo"},
        {"fecha": pd.Timestamp("2026-08-03"), "tipo": "Gasto", "categoria": "🚌 Transporte",
         "monto": 15, "periodo_id": "P1", "nota": "", "cuenta": "Efectivo"},
        {"fecha": pd.Timestamp("2026-07-05"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 30, "periodo_id": "P0", "nota": "", "cuenta": "Efectivo"},
    ])


def test_pendiente_por_cobrar_suma_diferencia_de_todos_los_periodos():
    assert pendiente_por_cobrar(_periodos()) == 400


def test_gastado_en_periodo_filtra_por_id():
    assert gastado_en_periodo(_movimientos_periodos(), "P1") == 55
    assert gastado_en_periodo(_movimientos_periodos(), "P0") == 30


def test_saldo_restante_periodo_resta_gastado_del_recibido():
    assert saldo_restante_periodo(_periodos(), _movimientos_periodos(), "P1") == 600 - 55


def _periodos_con_activa():
    return pd.DataFrame([
        {"periodo_id": "P1", "fecha_inicio": pd.Timestamp("2020-01-01"), "fecha_fin": pd.Timestamp("2020-01-15"),
         "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0, "activa": False},
        {"periodo_id": "P2", "fecha_inicio": pd.Timestamp("2020-01-15"), "fecha_fin": pd.Timestamp("2020-01-29"),
         "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0, "activa": False},
    ])


def test_activar_periodo_marca_uno_y_desactiva_los_demas():
    periodos = _periodos_con_activa()
    periodos.loc[periodos.periodo_id == "P1", "activa"] = True

    resultado = activar_periodo(periodos, "P2")

    assert resultado.loc[resultado.periodo_id == "P2", "activa"].iloc[0] == True
    assert resultado.loc[resultado.periodo_id == "P1", "activa"].iloc[0] == False


def test_activar_periodo_id_inexistente_no_hace_nada():
    periodos = _periodos_con_activa()
    periodos.loc[periodos.periodo_id == "P1", "activa"] = True

    resultado = activar_periodo(periodos, "P_borrado")

    assert resultado.loc[resultado.periodo_id == "P1", "activa"].iloc[0] == True


def test_periodo_actual_prioriza_el_marcado_activo_sobre_la_fecha():
    periodos = _periodos_con_activa()
    periodos.loc[periodos.periodo_id == "P1", "activa"] = True

    assert periodo_actual(periodos).periodo_id == "P1"


def test_periodo_actual_sin_ninguno_activo_cae_al_mas_reciente_por_fecha():
    assert periodo_actual(_periodos_con_activa()).periodo_id == "P2"


def test_periodo_actual_vacio_devuelve_none():
    vacio = pd.DataFrame(columns=["periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido", "activa"])
    assert periodo_actual(vacio) is None


def test_load_periodos_sin_columna_activa_la_agrega_en_false(tmp_path, monkeypatch):
    archivo = tmp_path / "periodos.csv"
    pd.DataFrame([
        {"periodo_id": "P1", "fecha_inicio": "2026-08-01", "origen": "Sueldo",
         "monto_esperado": 1000, "monto_recibido": 0},
    ]).to_csv(archivo, index=False)
    monkeypatch.setattr(data_store, "PERIODOS_FILE", archivo)

    cargados = data_store.load_periodos()

    assert cargados.loc[0, "activa"] == False


def test_load_periodos_sin_columna_fecha_fin_la_calcula_como_inicio_mas_14(tmp_path, monkeypatch):
    archivo = tmp_path / "periodos.csv"
    pd.DataFrame([
        {"periodo_id": "P1", "fecha_inicio": "2026-08-01", "origen": "Sueldo",
         "monto_esperado": 1000, "monto_recibido": 0},
    ]).to_csv(archivo, index=False)
    monkeypatch.setattr(data_store, "PERIODOS_FILE", archivo)

    cargados = data_store.load_periodos()

    assert cargados.loc[0, "fecha_fin"] == pd.Timestamp("2026-08-15")


def test_load_periodos_con_columna_fecha_fin_la_respeta(tmp_path, monkeypatch):
    archivo = tmp_path / "periodos.csv"
    pd.DataFrame([
        {"periodo_id": "P1", "fecha_inicio": "2026-08-01", "fecha_fin": "2026-08-17",
         "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0},
    ]).to_csv(archivo, index=False)
    monkeypatch.setattr(data_store, "PERIODOS_FILE", archivo)

    cargados = data_store.load_periodos()

    assert cargados.loc[0, "fecha_fin"] == pd.Timestamp("2026-08-17")


def test_load_periodos_sin_archivo_devuelve_dataframe_vacio_con_columnas_correctas(tmp_path, monkeypatch):
    monkeypatch.setattr(data_store, "PERIODOS_FILE", tmp_path / "no_existe.csv")

    cargados = data_store.load_periodos()

    assert cargados.empty
    assert list(cargados.columns) == [
        "periodo_id", "fecha_inicio", "fecha_fin", "origen", "monto_esperado", "monto_recibido", "activa",
    ]


def test_load_movimientos_sin_archivo_devuelve_dataframe_vacio_con_columnas_correctas(tmp_path, monkeypatch):
    monkeypatch.setattr(data_store, "MOVIMIENTOS_FILE", tmp_path / "no_existe.csv")

    cargados = data_store.load_movimientos()

    assert cargados.empty
    assert list(cargados.columns) == ["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]


def test_periodo_actual_respeta_un_fecha_fin_mas_largo_que_14_dias():
    hoy = pd.Timestamp(_date.today())
    periodos = pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": hoy - pd.Timedelta(days=16), "fecha_fin": hoy + pd.Timedelta(days=1),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": 0, "activa": False,
    }])

    assert periodo_actual(periodos).periodo_id == "P1"


def _movimientos_generales():
    return pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Ingreso", "categoria": "🎁 Regalo",
         "monto": 20, "periodo_id": pd.NA, "nota": "", "cuenta": "Efectivo"},
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Ingreso", "categoria": "🎁 Regalo",
         "monto": 5, "periodo_id": pd.NA, "nota": "", "cuenta": "Efectivo"},
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 8, "periodo_id": pd.NA, "nota": "", "cuenta": "Efectivo"},
    ])


def test_regalos_total_suma_solo_esa_categoria():
    assert regalos_total(_movimientos_generales()) == 25


def test_saldo_disponible_resta_gastos_de_ingresos():
    assert saldo_disponible(_movimientos_generales()) == 25 - 8


def test_efectivo_resta_saldo_de_cuentas_del_disponible():
    cuentas = pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [10]})
    assert efectivo(_movimientos_generales(), cuentas) == (25 - 8) - 10


def test_delta_por_tipo_ingreso_es_positivo_gasto_es_negativo():
    assert delta_por_tipo("Ingreso", 100) == 100
    assert delta_por_tipo("Gasto", 100) == -100


def test_ajustar_saldo_cuenta_suma_delta_a_la_cuenta_correcta():
    cuentas = pd.DataFrame({"cuenta": ["Ahorros", "Corriente"], "saldo": [100, 50]})

    resultado = ajustar_saldo_cuenta(cuentas, "Corriente", 25)

    assert resultado.loc[resultado.cuenta == "Corriente", "saldo"].iloc[0] == 75
    assert resultado.loc[resultado.cuenta == "Ahorros", "saldo"].iloc[0] == 100


def test_ajustar_saldo_cuenta_ignora_cuenta_desconocida():
    cuentas = pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [100]})

    resultado = ajustar_saldo_cuenta(cuentas, "Efectivo", 25)

    assert resultado.loc[resultado.cuenta == "Ahorros", "saldo"].iloc[0] == 100


def test_gasto_inversion_esta_en_categorias_y_tiene_color():
    assert "📈 Inversión" in data_store.GASTO_CATEGORIAS
    assert "📈 Inversión" in data_store.COLOR_MAP


def test_retiro_inversion_esta_en_categorias_de_ingreso():
    assert "📈 Retiro de inversión" in data_store.INGRESO_CATEGORIAS
    assert "📈 Retiro de inversión" not in data_store.INGRESO_PERIODICO_CATEGORIAS


def test_ajustar_saldo_inversion_suma_delta_y_marca_actualizado_hoy():
    inversiones = pd.DataFrame({
        "item": ["FIC", "Inversión"], "saldo": [1000, 500],
        "actualizado": ["2026-01-01", "2026-01-01"],
    })

    resultado = ajustar_saldo_inversion(inversiones, "Inversión", 300)

    assert resultado.loc[resultado.item == "Inversión", "saldo"].iloc[0] == 800
    assert resultado.loc[resultado.item == "Inversión", "actualizado"].iloc[0] == _date.today().isoformat()
    assert resultado.loc[resultado.item == "FIC", "saldo"].iloc[0] == 1000


def test_registrar_compra_activo_promedia_precio_de_compra_ponderado():
    activos = pd.DataFrame({"id": ["bitcoin"], "cantidad": [1.0], "precio_compra": [40000.0]})

    resultado = registrar_compra_activo(activos, "id", "bitcoin", cantidad_nueva=1.0, precio_compra_nuevo=60000.0)

    assert resultado.loc[0, "cantidad"] == 2.0
    assert resultado.loc[0, "precio_compra"] == 50000.0


def test_registrar_compra_activo_sin_precio_previo_usa_el_precio_nuevo():
    activos = pd.DataFrame({"id": ["bitcoin"], "cantidad": [1.0], "precio_compra": [0.0]})

    resultado = registrar_compra_activo(activos, "id", "bitcoin", cantidad_nueva=0.5, precio_compra_nuevo=70000.0)

    assert resultado.loc[0, "cantidad"] == 1.5
    assert resultado.loc[0, "precio_compra"] == 70000.0


def test_registrar_compra_activo_sin_cantidad_previa_usa_el_precio_nuevo():
    activos = pd.DataFrame({"ticker": ["AAPL"], "cantidad": [0.0], "precio_compra": [0.0]})

    resultado = registrar_compra_activo(activos, "ticker", "AAPL", cantidad_nueva=2.0, precio_compra_nuevo=200.0)

    assert resultado.loc[0, "cantidad"] == 2.0
    assert resultado.loc[0, "precio_compra"] == 200.0


def test_registrar_venta_activo_resta_cantidad():
    activos = pd.DataFrame({"id": ["bitcoin"], "cantidad": [2.0], "precio_compra": [40000.0]})

    resultado = registrar_venta_activo(activos, "id", "bitcoin", cantidad_vendida=0.5)

    assert resultado.loc[0, "cantidad"] == 1.5


def test_registrar_venta_activo_no_cambia_precio_compra():
    activos = pd.DataFrame({"ticker": ["AAPL"], "cantidad": [3.0], "precio_compra": [150.0]})

    resultado = registrar_venta_activo(activos, "ticker", "AAPL", cantidad_vendida=1.0)

    assert resultado.loc[0, "precio_compra"] == 150.0


def test_registrar_snapshot_patrimonio_agrega_fila_nueva(tmp_path, monkeypatch):
    archivo = tmp_path / "historico.csv"
    monkeypatch.setattr(data_store, "HISTORICO_FILE", archivo)

    resultado = registrar_snapshot_patrimonio(_date(2026, 8, 1), 1000)

    assert resultado.loc[0, "patrimonio_total"] == 1000


def test_registrar_snapshot_patrimonio_actualiza_la_fila_de_hoy_si_ya_existe(tmp_path, monkeypatch):
    archivo = tmp_path / "historico.csv"
    monkeypatch.setattr(data_store, "HISTORICO_FILE", archivo)
    registrar_snapshot_patrimonio(_date(2026, 8, 1), 1000)

    resultado = registrar_snapshot_patrimonio(_date(2026, 8, 1), 1500)

    assert len(resultado) == 1
    assert resultado.loc[0, "patrimonio_total"] == 1500


def test_load_criptos_sin_archivo_trae_columna_precio_en_cero():
    df = data_store.load_criptos()

    assert "precio" in df.columns
    assert (df["precio"] == 0.0).all()


def test_load_criptos_migra_csv_viejo_sin_columna_precio():
    """Los CSV creados antes del precio manual no tienen la columna — se
    rellena en cero para que la fila siga cargando y se muestre como "sin
    precio" hasta que el usuario la complete."""
    pd.DataFrame({"id": ["bitcoin"], "simbolo": ["BTC"], "cantidad": [0.5], "precio_compra": [88000.0]}).to_csv(
        data_store.CRIPTOS_FILE, index=False
    )

    df = data_store.load_criptos()

    assert df.loc[0, "precio"] == 0.0


def test_load_criptos_lee_el_precio_guardado():
    pd.DataFrame({
        "id": ["bitcoin"], "simbolo": ["BTC"], "cantidad": [0.5],
        "precio": [95000.0], "precio_compra": [88000.0],
    }).to_csv(data_store.CRIPTOS_FILE, index=False)

    df = data_store.load_criptos()

    assert df.loc[0, "precio"] == 95000.0


def test_load_criptos_precio_vacio_queda_en_cero():
    pd.DataFrame({
        "id": ["bitcoin"], "simbolo": ["BTC"], "cantidad": [0.5],
        "precio": [None], "precio_compra": [88000.0],
    }).to_csv(data_store.CRIPTOS_FILE, index=False)

    df = data_store.load_criptos()

    assert df.loc[0, "precio"] == 0.0


def test_load_acciones_sin_archivo_trae_columna_precio():
    assert "precio" in data_store.load_acciones().columns


def test_load_acciones_migra_csv_viejo_sin_columna_precio():
    pd.DataFrame({"ticker": ["AAPL"], "cantidad": [3.0], "precio_compra": [150.0]}).to_csv(
        data_store.ACCIONES_FILE, index=False
    )

    df = data_store.load_acciones()

    assert df.loc[0, "precio"] == 0.0


def test_load_acciones_lee_el_precio_guardado():
    pd.DataFrame({"ticker": ["AAPL"], "cantidad": [3.0], "precio": [220.5], "precio_compra": [150.0]}).to_csv(
        data_store.ACCIONES_FILE, index=False
    )

    assert data_store.load_acciones().loc[0, "precio"] == 220.5


def test_load_criptos_migrado_deja_precio_antes_de_precio_compra():
    """El orden de columnas es el orden que ve el usuario en el data_editor:
    un CSV migrado tiene que quedar igual que uno nuevo, con el precio actual
    antes del precio de compra."""
    pd.DataFrame({"id": ["bitcoin"], "simbolo": ["BTC"], "cantidad": [0.5], "precio_compra": [88000.0]}).to_csv(
        data_store.CRIPTOS_FILE, index=False
    )

    columnas = list(data_store.load_criptos().columns)

    assert columnas.index("precio") < columnas.index("precio_compra")


def test_load_acciones_migrado_deja_precio_antes_de_precio_compra():
    pd.DataFrame({"ticker": ["AAPL"], "cantidad": [3.0], "precio_compra": [150.0]}).to_csv(
        data_store.ACCIONES_FILE, index=False
    )

    columnas = list(data_store.load_acciones().columns)

    assert columnas.index("precio") < columnas.index("precio_compra")
