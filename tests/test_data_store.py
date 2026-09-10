from datetime import date

import pandas as pd

import config
import data_store
from data_store import (
    activar_periodo,
    ajustar_saldo_cuenta,
    delta_por_tipo,
    efectivo,
    gastado_en_periodo,
    pendiente_por_cobrar,
    periodo_actual,
    regalos_total,
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


def test_periodo_actual_respeta_un_fecha_fin_mas_largo_que_14_dias():
    hoy = pd.Timestamp(date.today())
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
