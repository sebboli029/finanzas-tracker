import pandas as pd
import pytest

import data_store


@pytest.fixture(autouse=True)
def _aislar_datos_reales(tmp_path, monkeypatch):
    """Evita que la suite toque data/*.csv de verdad."""
    monkeypatch.setattr(data_store, "PERIODOS_FILE", tmp_path / "periodos.csv")
    monkeypatch.setattr(data_store, "MOVIMIENTOS_FILE", tmp_path / "movimientos.csv")
    monkeypatch.setattr(data_store, "CUENTAS_FILE", tmp_path / "cuentas.csv")
    monkeypatch.setattr(data_store, "INVERSIONES_FILE", tmp_path / "inversiones.csv")
    monkeypatch.setattr(data_store, "MONEDAS_FILE", tmp_path / "monedas.csv")
    monkeypatch.setattr(data_store, "CRIPTOS_FILE", tmp_path / "criptos.csv")
    monkeypatch.setattr(data_store, "ACCIONES_FILE", tmp_path / "acciones.csv")
    monkeypatch.setattr(data_store, "HISTORICO_FILE", tmp_path / "patrimonio_historico.csv")

    # load_periodos() y load_movimientos() hacen pd.read_csv directo, sin el
    # fallback de "si no existe" que sí tienen los demás loaders — hay que
    # sembrar el archivo vacío para que una corrida completa no reviente.
    pd.DataFrame(columns=[
        "periodo_id", "fecha_inicio", "origen", "monto_esperado", "monto_recibido",
    ]).to_csv(data_store.PERIODOS_FILE, index=False)
    pd.DataFrame(columns=[
        "fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta",
    ]).to_csv(data_store.MOVIMIENTOS_FILE, index=False)
