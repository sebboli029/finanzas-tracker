import pandas as pd

import config
import data_store


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
