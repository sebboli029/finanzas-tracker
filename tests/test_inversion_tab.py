import pandas as pd

import inversion_tab
from inversion_tab import _precios_de_activos, _valor_activos


def test_precios_de_activos_usa_el_precio_cargado_a_mano():
    activos = pd.DataFrame({
        "id": ["bitcoin"], "cantidad": [2.0], "precio": [12000.0], "precio_compra": [10000.0],
    })

    filas = _precios_de_activos(activos, "id")

    assert filas[0]["precio"] == 12000.0
    assert filas[0]["valor"] == 24000.0
    assert filas[0]["ganancia"] == 4000.0
    assert filas[0]["ganancia_pct"] == 20.0


def test_precios_de_activos_calcula_perdida_cuando_el_precio_bajo():
    activos = pd.DataFrame({
        "ticker": ["AAPL"], "cantidad": [10.0], "precio": [90.0], "precio_compra": [100.0],
    })

    filas = _precios_de_activos(activos, "ticker")

    assert filas[0]["ganancia"] == -100.0
    assert filas[0]["ganancia_pct"] == -10.0


def test_precios_de_activos_sin_precio_compra_no_calcula_ganancia():
    activos = pd.DataFrame({
        "id": ["bitcoin"], "cantidad": [2.0], "precio": [12000.0], "precio_compra": [0.0],
    })

    filas = _precios_de_activos(activos, "id")

    assert filas[0]["valor"] == 24000.0
    assert filas[0]["ganancia"] is None


def test_precios_de_activos_precio_en_cero_deja_valor_none():
    """Precio sin cargar no vale cero: no se puede valorizar la fila, igual
    que antes no se podía cuando fallaba el fetch."""
    activos = pd.DataFrame({
        "id": ["bitcoin"], "cantidad": [2.0], "precio": [0.0], "precio_compra": [10000.0],
    })

    filas = _precios_de_activos(activos, "id")

    assert filas[0]["valor"] is None
    assert filas[0]["ganancia"] is None


def test_precios_de_activos_no_depende_de_que_el_identificador_exista():
    """El precio es el que cargó el usuario, así que un identificador que
    ninguna API reconocería se valoriza igual que cualquier otro."""
    activos = pd.DataFrame({
        "id": ["mi-moneda-inventada"], "cantidad": [10.0], "precio": [5.0], "precio_compra": [0.0],
    })

    assert _precios_de_activos(activos, "id")[0]["valor"] == 50.0


def test_precios_de_activos_ignora_filas_sin_identificador():
    activos = pd.DataFrame({
        "id": ["bitcoin", "", None], "cantidad": [1.0, 1.0, 1.0],
        "precio": [100.0, 100.0, 100.0], "precio_compra": [0.0, 0.0, 0.0],
    })

    filas = _precios_de_activos(activos, "id")

    assert [f["identificador"] for f in filas] == ["bitcoin"]


def test_valor_activos_suma_solo_las_filas_con_precio_cargado():
    activos = pd.DataFrame({
        "id": ["bitcoin", "solana"], "cantidad": [2.0, 10.0],
        "precio": [12000.0, 0.0], "precio_compra": [0.0, 0.0],
    })

    assert _valor_activos(lambda: activos, "id") == 24000.0


def test_inversion_tab_no_consulta_precios_por_internet():
    """La pestaña dejó de traer precios de CoinGecko y Yahoo Finance — lo
    único que sigue saliendo a la red son las tasas de monedas."""
    assert not hasattr(inversion_tab, "_precio_cripto")
    assert not hasattr(inversion_tab, "_precio_accion")
    assert not hasattr(inversion_tab, "precio_activo_de")
