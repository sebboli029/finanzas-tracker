import pandas as pd

import config
import inversion_tab
from inversion_tab import _precios_de_activos, precio_unitario_base, tasa_usd_a_base


def test_precio_unitario_base_moneda_igual_a_base_pasa_directo():
    assert precio_unitario_base(100, config.MONEDA_BASE, tasa_usd=1.0) == 100


def test_precio_unitario_base_usd_convierte_con_la_tasa():
    assert precio_unitario_base(100, "USD", tasa_usd=4000) == 400000


def test_precio_unitario_base_moneda_desconocida_devuelve_none():
    assert precio_unitario_base(100, "JPY", tasa_usd=4000) is None


def test_tasa_usd_a_base_es_uno_si_la_moneda_base_es_usd():
    assert config.MONEDA_BASE == "USD"
    assert tasa_usd_a_base() == 1.0


def test_tasa_usd_a_base_usa_la_fila_dolares_si_la_base_no_es_usd(monkeypatch):
    monkeypatch.setattr(config, "MONEDA_BASE", "EUR")
    monedas = pd.DataFrame({"moneda": ["Dólares"], "monto": [0.0], "tasa": [0.92]})
    monkeypatch.setattr(inversion_tab, "load_monedas", lambda: monedas)
    monkeypatch.setattr(inversion_tab, "_actualizar_tasas_del_dia", lambda m: m)

    assert tasa_usd_a_base() == 0.92


def test_tasa_usd_a_base_sin_fila_dolares_devuelve_none(monkeypatch):
    monkeypatch.setattr(config, "MONEDA_BASE", "EUR")
    monedas = pd.DataFrame({"moneda": ["Libras"], "monto": [0.0], "tasa": [1.1]})
    monkeypatch.setattr(inversion_tab, "load_monedas", lambda: monedas)
    monkeypatch.setattr(inversion_tab, "_actualizar_tasas_del_dia", lambda m: m)

    assert tasa_usd_a_base() is None


def test_precios_de_activos_calcula_valor_y_ganancia():
    activos = pd.DataFrame({"id": ["bitcoin"], "cantidad": [2.0], "precio_compra": [10000.0]})

    filas = _precios_de_activos(activos, "id", lambda ident: (12000.0, "USD"), tasa_usd=1.0)

    assert filas[0]["valor_base"] == 24000.0
    assert filas[0]["ganancia_base"] == 4000.0
    assert filas[0]["ganancia_pct"] == 20.0


def test_precios_de_activos_sin_precio_compra_no_calcula_ganancia():
    activos = pd.DataFrame({"id": ["bitcoin"], "cantidad": [2.0], "precio_compra": [0.0]})

    filas = _precios_de_activos(activos, "id", lambda ident: (12000.0, "USD"), tasa_usd=1.0)

    assert filas[0]["valor_base"] == 24000.0
    assert filas[0]["ganancia_base"] is None


def test_precios_de_activos_fetch_fallido_deja_valor_none():
    activos = pd.DataFrame({"id": ["bitcoin"], "cantidad": [2.0], "precio_compra": [10000.0]})

    filas = _precios_de_activos(activos, "id", lambda ident: None, tasa_usd=1.0)

    assert filas[0]["valor_base"] is None
