# Finanzas Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `mesada-tracker` (a Streamlit allowance tracker) into `finanzas-tracker`, a generalized personal-finance base for a different person — same use cases (budget periods, transactions, accounts, investments, net worth), but with "quincena de mesada" generalized to "periodo de presupuesto" and the currency configurable instead of hardcoded to COP.

**Architecture:** Same architecture as the original — Streamlit + pandas, one CSV per entity under `data/`, backup-on-save with undo, business logic kept in pure functions in `data_store.py` (and small pure helpers in the UI modules) so it's testable without mocking Streamlit.

**Tech Stack:** Python, Streamlit, pandas, plotly, requests, pytest, `streamlit.testing.v1.AppTest`.

**Spec:** `docs/superpowers/specs/2026-09-09-finanzas-tracker-design.md`

## Global Constraints

- All money amounts are stored and displayed in `config.MONEDA_BASE` (default `"USD"`) — never hardcode a currency symbol or COP-style formatting.
- `config.MONEDA_BASE` must always be read as `config.MONEDA_BASE` (module attribute access), never imported as a bare name — tests monkeypatch `config.MONEDA_BASE` and that only works if callers re-read the attribute each time.
- Every CSV write goes through `guardar_con_respaldo` (never `df.to_csv` directly) so the backup/undo mechanism stays consistent.
- Column name `quincena_id` → `periodo_id` everywhere (files, DataFrames, function params). Column `pagador` is dropped; replaced by an optional free-text `origen`.
- Category `💰 Mesada` / `💰 Mesada (adelanto)` → `💰 Ingreso periódico` / `💰 Ingreso periódico (adelanto)`. `👵 Regalo de la abuela` → `🎁 Regalo`.
- No authentication, no multi-user support, no deploy config — single user, run locally via `streamlit run app.py`, exactly like the original.

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `config.py`
- Create: `data/.gitkeep`

**Interfaces:**
- Produces: `config.MONEDA_BASE` (str), `config.FORMATOS_MONEDA` (dict of `{codigo: {"simbolo", "separador_miles", "decimales"}}`) — consumed by `data_store.money()` (Task 2) and `inversion_tab.py` (Task 9).

- [ ] **Step 1: Create `requirements.txt`**

```
streamlit>=1.38
pandas>=2.2
plotly>=5.24
requests>=2.31
pytest>=7.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
pythonpath = .
```

- [ ] **Step 3: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.DS_Store
data/.backups/
```

- [ ] **Step 4: Create `config.py`**

```python
"""Configuración de la app — ajustá esto para adaptarla a otra persona."""

# Moneda en la que se muestran y guardan todos los montos de la app.
# Si la cambiás a algo distinto de "USD", agregá "Dólares" a MONEDAS_DEFAULT
# y MONEDA_A_CODIGO (en inversion_tab.py): la conversión de cripto y acciones
# (que siempre cotizan en USD) necesita esa fila como pivote hacia la moneda
# base.
MONEDA_BASE = "USD"

FORMATOS_MONEDA = {
    "USD": {"simbolo": "$", "separador_miles": ",", "decimales": 0},
    "EUR": {"simbolo": "€", "separador_miles": ".", "decimales": 0},
    "GBP": {"simbolo": "£", "separador_miles": ",", "decimales": 0},
    "COP": {"simbolo": "$", "separador_miles": ".", "decimales": 0},
}
```

- [ ] **Step 5: Create the empty `data/` directory placeholder**

```bash
mkdir -p data && touch data/.gitkeep
```

- [ ] **Step 6: Verify the package installs cleanly**

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: install completes with no errors.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pytest.ini .gitignore config.py data/.gitkeep
git commit -m "Scaffold finanzas-tracker project (config, deps, pytest)"
```

---

## Task 2: `data_store.py` — money formatting + backup/undo mechanism

**Files:**
- Create: `data_store.py`
- Create: `tests/conftest.py`
- Create: `tests/test_data_store.py`

**Interfaces:**
- Consumes: `config.MONEDA_BASE`, `config.FORMATOS_MONEDA` (Task 1).
- Produces: `DATA_DIR`, `MAX_BACKUPS_POR_ARCHIVO` (int), `formato_moneda(codigo) -> dict`, `money(n) -> str`, `guardar_con_respaldo(path, df)`, `deshacer_ultimo_cambio(path) -> bool` — all consumed by every later task.

- [ ] **Step 1: Write `tests/test_data_store.py` with the failing tests for money formatting and backup/undo**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail with `ModuleNotFoundError`/`AttributeError`**

Run: `pytest tests/test_data_store.py -v`
Expected: FAIL — `data_store` module does not exist yet.

- [ ] **Step 3: Create `data_store.py` with the file constants, `money`/`formato_moneda`, and the backup/undo mechanism**

```python
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import config

DATA_DIR = Path(__file__).parent / "data"
PERIODOS_FILE = DATA_DIR / "periodos.csv"
MOVIMIENTOS_FILE = DATA_DIR / "movimientos.csv"
CUENTAS_FILE = DATA_DIR / "cuentas.csv"
INVERSIONES_FILE = DATA_DIR / "inversiones.csv"
MONEDAS_FILE = DATA_DIR / "monedas.csv"
CRIPTOS_FILE = DATA_DIR / "criptos.csv"
ACCIONES_FILE = DATA_DIR / "acciones.csv"
HISTORICO_FILE = DATA_DIR / "patrimonio_historico.csv"

MAX_BACKUPS_POR_ARCHIVO = 5


def _respaldar(path):
    """Copia el archivo actual a path.parent/.backups/ antes de sobreescribirlo.
    No hace nada si el archivo todavía no existe (primer guardado)."""
    if not path.exists():
        return
    carpeta = path.parent / ".backups"
    carpeta.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    shutil.copy2(path, carpeta / f"{path.stem}.{marca}{path.suffix}")
    _purgar_backups_viejos(carpeta, path.stem)


def _purgar_backups_viejos(carpeta, prefijo):
    backups = sorted(carpeta.glob(f"{prefijo}.*.csv"))
    for viejo in backups[:-MAX_BACKUPS_POR_ARCHIVO]:
        viejo.unlink()


def guardar_con_respaldo(path, df):
    _respaldar(path)
    df.to_csv(path, index=False)


def deshacer_ultimo_cambio(path):
    """Restaura el backup más reciente de `path`. Devuelve False si no hay ninguno."""
    carpeta = path.parent / ".backups"
    backups = sorted(carpeta.glob(f"{path.stem}.*.csv"))
    if not backups:
        return False
    shutil.copy2(backups[-1], path)
    backups[-1].unlink()
    return True


def formato_moneda(codigo):
    return config.FORMATOS_MONEDA.get(codigo, {"simbolo": "$", "separador_miles": ",", "decimales": 0})


def money(n):
    fmt = formato_moneda(config.MONEDA_BASE)
    texto = f"{n:,.{fmt['decimales']}f}"
    if fmt["separador_miles"] != ",":
        texto = texto.replace(",", fmt["separador_miles"])
    return f"{fmt['simbolo']}{texto}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_data_store.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Create `tests/conftest.py` with the isolation fixture (no `inversion_tab` reference yet — that's added in Task 9)**

```python
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
```

- [ ] **Step 6: Run the full suite to confirm the fixture doesn't break the Step-4 tests**

Run: `pytest tests/ -v`
Expected: PASS (7 tests, same as Step 4 — the fixture doesn't affect these since they don't touch the file constants).

- [ ] **Step 7: Commit**

```bash
git add data_store.py tests/conftest.py tests/test_data_store.py
git commit -m "Add data_store money formatting and CSV backup/undo mechanism"
```

---

## Task 3: `data_store.py` — periodos (budget periods)

**Files:**
- Modify: `data_store.py`
- Modify: `tests/test_data_store.py`

**Interfaces:**
- Consumes: `PERIODOS_FILE`, `guardar_con_respaldo` (Task 2).
- Produces: `load_periodos() -> DataFrame`, `save_periodos(df)`, `activar_periodo(periodos, periodo_id) -> DataFrame`, `periodo_actual(periodos) -> Series | None`, `pendiente_por_cobrar(periodos) -> float`, `gastado_en_periodo(movimientos, periodo_id) -> float`, `saldo_restante_periodo(periodos, movimientos, periodo_id) -> float` — consumed by `sidebar.py` (Task 8), `resumen_tab.py` (Tasks 10-12), `widgets.py` (Task 7).

- [ ] **Step 1: Append the failing tests to `tests/test_data_store.py`**

```python
from datetime import date

from data_store import (
    activar_periodo,
    gastado_en_periodo,
    pendiente_por_cobrar,
    periodo_actual,
    saldo_restante_periodo,
)


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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_data_store.py -v -k periodo`
Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Append the implementation to `data_store.py`**

```python
def load_periodos():
    df = pd.read_csv(PERIODOS_FILE, parse_dates=["fecha_inicio"])
    if "activa" not in df.columns:
        df["activa"] = False
    if "fecha_fin" not in df.columns:
        df["fecha_fin"] = df["fecha_inicio"] + pd.Timedelta(days=14)
    else:
        df["fecha_fin"] = pd.to_datetime(df["fecha_fin"])
    return df


def activar_periodo(periodos, periodo_id):
    """Marca `periodo_id` como el único periodo activo — desactiva todos los
    demás. No hace nada si `periodo_id` no existe."""
    if periodo_id not in periodos["periodo_id"].values:
        return periodos
    periodos["activa"] = periodos["periodo_id"] == periodo_id
    return periodos


def periodo_actual(periodos):
    """El periodo marcado como activo a mano tiene prioridad. Si ninguno lo
    está, cae al cálculo automático por fecha: el periodo cuyo rango
    (fecha_inicio a fecha_fin) incluye hoy, o si ninguno está en curso, el
    último que arrancó."""
    if periodos.empty:
        return None
    activos = periodos[periodos["activa"]]
    if not activos.empty:
        return activos.iloc[0]
    hoy = pd.Timestamp(date.today())
    en_curso = periodos[(periodos["fecha_inicio"] <= hoy) & (hoy < periodos["fecha_fin"])]
    if not en_curso.empty:
        return en_curso.sort_values("fecha_inicio").iloc[-1]
    return periodos.sort_values("fecha_inicio").iloc[-1]


def pendiente_por_cobrar(periodos):
    return (periodos["monto_esperado"] - periodos["monto_recibido"]).sum()


def gastado_en_periodo(movimientos, periodo_id):
    return movimientos.loc[
        (movimientos.tipo == "Gasto") & (movimientos.periodo_id == periodo_id), "monto"
    ].sum()


def saldo_restante_periodo(periodos, movimientos, periodo_id):
    recibido = periodos.loc[periodos.periodo_id == periodo_id, "monto_recibido"]
    if recibido.empty:
        return 0
    return recibido.iloc[0] - gastado_en_periodo(movimientos, periodo_id)


def save_periodos(df):
    guardar_con_respaldo(PERIODOS_FILE, df)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_data_store.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add data_store.py tests/test_data_store.py
git commit -m "Add periodo (budget period) tracking to data_store"
```

---

## Task 4: `data_store.py` — cuentas (accounts) and movimientos (transactions) base

**Files:**
- Modify: `data_store.py`
- Modify: `tests/test_data_store.py`

**Interfaces:**
- Consumes: `DATA_DIR`, `guardar_con_respaldo` (Task 2).
- Produces: `CUENTAS_DEFAULT`, `CUENTAS_CON_EFECTIVO`, `GASTO_CATEGORIAS`, `INGRESO_CATEGORIAS`, `INGRESO_PERIODICO_CATEGORIAS`, `COLOR_MAP` (constants); `load_movimientos()`, `save_movimientos(df)`, `load_cuentas()`, `save_cuentas(df)`, `regalos_total(movimientos) -> float`, `saldo_disponible(movimientos) -> float`, `efectivo(movimientos, cuentas) -> float`, `delta_por_tipo(tipo, monto) -> float`, `ajustar_saldo_cuenta(cuentas, cuenta, delta) -> DataFrame` — consumed by `sidebar.py`, `widgets.py`, `resumen_tab.py`, `patrimonio.py`.

- [ ] **Step 1: Append the failing tests**

```python
from data_store import (
    ajustar_saldo_cuenta,
    delta_por_tipo,
    efectivo,
    regalos_total,
    saldo_disponible,
)


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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_data_store.py -v -k "regalos or saldo_disponible or efectivo or delta_por_tipo or ajustar_saldo_cuenta or categorias"`
Expected: FAIL.

- [ ] **Step 3: Append the implementation to `data_store.py`**

```python
CUENTAS_DEFAULT = ["Cuenta corriente", "Ahorros", "Tarjeta de crédito"]
CUENTAS_CON_EFECTIVO = CUENTAS_DEFAULT + ["Efectivo"]

GASTO_CATEGORIAS = ["🚌 Transporte", "🍽️ Comida", "🎮 Ocio", "📦 Otro", "📈 Inversión"]
INGRESO_CATEGORIAS = [
    "💰 Ingreso periódico", "💰 Ingreso periódico (adelanto)", "🎁 Ingreso extra", "🎁 Regalo",
    "🎒 Saldo inicial", "📈 Retiro de inversión",
]

# Categorías que sí cuentan como pago del periodo (descuentan el pendiente del periodo)
INGRESO_PERIODICO_CATEGORIAS = {"💰 Ingreso periódico", "💰 Ingreso periódico (adelanto)"}

COLOR_MAP = {
    "🚌 Transporte": "#2a78d6",
    "🍽️ Comida": "#eb6834",
    "🎮 Ocio": "#1baf7a",
    "📦 Otro": "#eda100",
    "📈 Inversión": "#e87ba4",
}


def load_movimientos():
    return pd.read_csv(MOVIMIENTOS_FILE, parse_dates=["fecha"])


def save_movimientos(df):
    guardar_con_respaldo(MOVIMIENTOS_FILE, df)


def load_cuentas():
    if not CUENTAS_FILE.exists():
        return pd.DataFrame({"cuenta": CUENTAS_DEFAULT, "saldo": [0] * len(CUENTAS_DEFAULT)})
    return pd.read_csv(CUENTAS_FILE)


def save_cuentas(df):
    guardar_con_respaldo(CUENTAS_FILE, df)


def regalos_total(movimientos):
    ingresos = movimientos[movimientos.tipo == "Ingreso"]
    return ingresos.loc[ingresos.categoria == "🎁 Regalo", "monto"].sum()


def saldo_disponible(movimientos):
    ingresos = movimientos.loc[movimientos.tipo == "Ingreso", "monto"].sum()
    gastos = movimientos.loc[movimientos.tipo == "Gasto", "monto"].sum()
    return ingresos - gastos


def efectivo(movimientos, cuentas):
    return saldo_disponible(movimientos) - cuentas["saldo"].sum()


def delta_por_tipo(tipo, monto):
    return monto if tipo == "Ingreso" else -monto


def ajustar_saldo_cuenta(cuentas, cuenta, delta):
    """Suma `delta` al saldo de `cuenta`. No hace nada si `cuenta` no es una
    cuenta bancaria conocida (p.ej. "Efectivo" o sin especificar) — ese caso
    ya queda reflejado solo, porque el efectivo se calcula como el resto."""
    if delta == 0 or cuenta not in cuentas["cuenta"].values:
        return cuentas
    idx = cuentas[cuentas.cuenta == cuenta].index
    cuentas.loc[idx, "saldo"] += delta
    return cuentas
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_data_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data_store.py tests/test_data_store.py
git commit -m "Add accounts and transaction categories to data_store"
```

---

## Task 5: `data_store.py` — investments, currencies, crypto, stocks, net-worth history

**Files:**
- Modify: `data_store.py`
- Modify: `tests/test_data_store.py`

**Interfaces:**
- Consumes: `DATA_DIR`, `guardar_con_respaldo` (Task 2).
- Produces: `INVERSIONES_DEFAULT`, `CRIPTOS_DEFAULT`, `PATRIMONIO_COLOR_MAP` (constants); `load_inversiones()`, `save_inversiones(df)`, `load_monedas()`, `save_monedas(df)`, `load_criptos()`, `save_criptos(df)`, `load_acciones()`, `save_acciones(df)`, `load_historico()`, `registrar_snapshot_patrimonio(fecha, total) -> DataFrame`, `ajustar_saldo_inversion(inversiones, item, delta) -> DataFrame`, `registrar_compra_activo(activos, columna_id, identificador, cantidad_nueva, precio_compra_nuevo) -> DataFrame`, `registrar_venta_activo(activos, columna_id, identificador, cantidad_vendida) -> DataFrame` — consumed by `inversion_tab.py` (Task 9), `patrimonio.py` (Task 13), `resumen_tab.py` (Task 11).

This completes `data_store.py`.

- [ ] **Step 1: Append the failing tests**

```python
from datetime import date as _date

from data_store import (
    ajustar_saldo_inversion,
    registrar_compra_activo,
    registrar_snapshot_patrimonio,
    registrar_venta_activo,
)


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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_data_store.py -v -k "inversion or activo or snapshot"`
Expected: FAIL.

- [ ] **Step 3: Append the implementation to `data_store.py`**

```python
INVERSIONES_DEFAULT = ["FIC", "Inversión"]
CRIPTOS_DEFAULT = [
    {"id": "bitcoin", "simbolo": "BTC", "cantidad": 0.0, "precio_compra": 0.0},
    {"id": "solana", "simbolo": "SOL", "cantidad": 0.0, "precio_compra": 0.0},
]

# Mismo set de 7 colores validado, slots 1-7, para el gráfico de distribución del patrimonio.
PATRIMONIO_COLOR_MAP = {
    "Bancos": "#2a78d6",
    "Efectivo": "#eb6834",
    "FIC": "#1baf7a",
    "Inversión": "#eda100",
    "Monedas extranjeras": "#e87ba4",
    "Cripto": "#008300",
    "Acciones": "#4a3aa7",
}


def load_inversiones():
    if not INVERSIONES_FILE.exists():
        return pd.DataFrame({
            "item": INVERSIONES_DEFAULT,
            "saldo": [0] * len(INVERSIONES_DEFAULT),
            "actualizado": [date.today().isoformat()] * len(INVERSIONES_DEFAULT),
        })
    df = pd.read_csv(INVERSIONES_FILE)
    if "actualizado" not in df.columns:
        df["actualizado"] = date.today().isoformat()
    return df


def save_inversiones(df):
    guardar_con_respaldo(INVERSIONES_FILE, df)


def load_monedas():
    if not MONEDAS_FILE.exists():
        df = pd.DataFrame({"moneda": ["Euros"], "monto": [0.0], "tasa": [0.0]})
    else:
        df = pd.read_csv(MONEDAS_FILE)
    df["monto"] = df["monto"].astype(float)
    df["tasa"] = df["tasa"].astype(float)
    return df


def save_monedas(df):
    guardar_con_respaldo(MONEDAS_FILE, df)


def load_criptos():
    if not CRIPTOS_FILE.exists():
        df = pd.DataFrame(CRIPTOS_DEFAULT)
    else:
        # dtype fuerza "id" a texto: si todas las filas tienen el id vacío,
        # pandas la infiere como float64 (sin nada de texto para deducir el
        # tipo) y el data_editor no deja escribir letras en esa columna.
        df = pd.read_csv(CRIPTOS_FILE, dtype={"id": "object"})
        if "precio_compra" not in df.columns:
            df["precio_compra"] = 0.0
    df["cantidad"] = df["cantidad"].astype(float)
    df["precio_compra"] = df["precio_compra"].fillna(0.0).astype(float)
    return df


def save_criptos(df):
    guardar_con_respaldo(CRIPTOS_FILE, df)


def load_acciones():
    if not ACCIONES_FILE.exists():
        df = pd.DataFrame({
            "ticker": pd.Series(dtype="str"),
            "cantidad": pd.Series(dtype="float"),
            "precio_compra": pd.Series(dtype="float"),
        })
    else:
        df = pd.read_csv(ACCIONES_FILE, dtype={"ticker": "object"})
        if "precio_compra" not in df.columns:
            df["precio_compra"] = 0.0
    df["cantidad"] = df["cantidad"].astype(float)
    df["precio_compra"] = df["precio_compra"].fillna(0.0).astype(float)
    return df


def save_acciones(df):
    guardar_con_respaldo(ACCIONES_FILE, df)


def load_historico():
    if not HISTORICO_FILE.exists():
        return pd.DataFrame({"fecha": pd.Series(dtype="datetime64[ns]"), "patrimonio_total": pd.Series(dtype="float")})
    return pd.read_csv(HISTORICO_FILE, parse_dates=["fecha"])


def registrar_snapshot_patrimonio(fecha, total):
    """Guarda (o actualiza si ya existe) el patrimonio total del día de hoy."""
    historico = load_historico()
    fecha = pd.Timestamp(fecha).normalize()
    coincide = historico["fecha"] == fecha
    if coincide.any():
        historico.loc[coincide, "patrimonio_total"] = total
    else:
        historico = pd.concat(
            [historico, pd.DataFrame([{"fecha": fecha, "patrimonio_total": total}])], ignore_index=True
        )
    historico = historico.sort_values("fecha")
    guardar_con_respaldo(HISTORICO_FILE, historico)
    return historico


def ajustar_saldo_inversion(inversiones, item, delta):
    """Suma `delta` al saldo de un ítem manual de inversiones y marca
    `actualizado` como hoy."""
    idx = inversiones[inversiones.item == item].index
    inversiones.loc[idx, "saldo"] += delta
    inversiones.loc[idx, "actualizado"] = date.today().isoformat()
    return inversiones


def registrar_compra_activo(activos, columna_id, identificador, cantidad_nueva, precio_compra_nuevo):
    """Suma `cantidad_nueva` a la fila de `identificador` en `activos` (cripto
    o acciones) y recalcula `precio_compra` como promedio ponderado entre lo
    que ya había y la compra nueva. Si no había precio de compra cargado
    antes (0) o no había cantidad, no hay costo previo real que promediar —
    el precio de compra queda directo el de la compra nueva. `precio_compra`
    siempre queda en la moneda base de la app, sin importar en qué moneda
    cotice el activo — quien llama es responsable de convertir antes de
    pasarlo."""
    idx = activos[activos[columna_id] == identificador].index
    fila = activos.loc[idx[0]]
    cantidad_vieja, precio_viejo = fila["cantidad"], fila["precio_compra"]
    if precio_viejo == 0 or cantidad_vieja == 0:
        precio_final = precio_compra_nuevo
    else:
        precio_final = (
            cantidad_vieja * precio_viejo + cantidad_nueva * precio_compra_nuevo
        ) / (cantidad_vieja + cantidad_nueva)
    activos.loc[idx, "cantidad"] = cantidad_vieja + cantidad_nueva
    activos.loc[idx, "precio_compra"] = precio_final
    return activos


def registrar_venta_activo(activos, columna_id, identificador, cantidad_vendida):
    """Resta `cantidad_vendida` a la fila de `identificador` en `activos`
    (cripto o acciones). No toca `precio_compra`: vender no cambia el costo
    promedio de lo que queda de la posición, solo comprar sí. Quien llama
    tiene que validar antes que `cantidad_vendida` no supere lo que hay."""
    idx = activos[activos[columna_id] == identificador].index
    activos.loc[idx, "cantidad"] -= cantidad_vendida
    return activos
```

- [ ] **Step 4: Run the full `data_store` suite to verify all pass**

Run: `pytest tests/test_data_store.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add data_store.py tests/test_data_store.py
git commit -m "Add investments, currencies, crypto/stocks, and net-worth history to data_store"
```

---

## Task 6: `charts.py`

**Files:**
- Create: `charts.py`

**Interfaces:**
- Produces: `barras_horizontales(etiquetas, valores, colores, formatear)`, `linea(x, y, nombre="")` — consumed by `resumen_tab.py` (Task 12) and `patrimonio.py` (Task 13).

This is a thin plotly/Streamlit rendering wrapper with no branching logic — the original project has no `test_charts.py` either, so this task has no automated test, matching that precedent.

- [ ] **Step 1: Create `charts.py`**

```python
import plotly.graph_objects as go
import streamlit as st


def barras_horizontales(etiquetas, valores, colores, formatear):
    fig = go.Figure(go.Bar(
        x=list(valores), y=list(etiquetas), orientation="h",
        marker_color=list(colores),
        text=[formatear(v) for v in valores], textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(
        margin=dict(l=0, r=10, t=10, b=0), height=320,
        xaxis=dict(visible=False),
        yaxis=dict(title=None),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")


def linea(x, y, nombre=""):
    fig = go.Figure(go.Scatter(
        x=list(x), y=list(y), mode="lines+markers",
        line=dict(width=3), marker=dict(size=7), name=nombre,
    ))
    fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), height=300, showlegend=False)
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python3 -c "import charts"`
Expected: no output, exit code 0 (a `st.plotly_chart` call itself would need a Streamlit run context, but a bare import must succeed).

- [ ] **Step 3: Commit**

```bash
git add charts.py
git commit -m "Add charts helper module"
```

---

## Task 7: `widgets.py` — shared form selects

**Files:**
- Create: `widgets.py`
- Create: `tests/test_widgets.py`

**Interfaces:**
- Consumes: `data_store.CUENTAS_CON_EFECTIVO`, `GASTO_CATEGORIAS`, `INGRESO_CATEGORIAS`, `INGRESO_PERIODICO_CATEGORIAS`, `periodo_actual` (Tasks 3-4).
- Produces: `elegir_tipo_y_categoria(tipo_default="Gasto", categoria_default=None, key_prefix="") -> (tipo, categoria)`, `elegir_periodo(tipo, categoria, periodos, periodo_default=_SIN_ESPECIFICAR, key_prefix="") -> (periodo_id | None, es_ingreso_periodico)`, `elegir_cuenta(cuenta_default=None, key_prefix="") -> cuenta` — consumed by `sidebar.py` (Task 8).

- [ ] **Step 1: Write `tests/test_widgets.py` with the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_widgets.py -v`
Expected: FAIL — `widgets` module does not exist yet.

- [ ] **Step 3: Create `widgets.py`**

```python
import pandas as pd
import streamlit as st

from data_store import (
    CUENTAS_CON_EFECTIVO,
    GASTO_CATEGORIAS,
    INGRESO_CATEGORIAS,
    INGRESO_PERIODICO_CATEGORIAS,
    periodo_actual,
)

# Widgets compartidos entre el formulario de "nuevo movimiento" (sidebar.py)
# y un futuro editor de movimiento existente — misma lógica, distinto valor
# por defecto según si estás creando o editando.

# Sentinel para distinguir "creando movimiento nuevo" (sin periodo_default)
# de "editando uno existente sin periodo" (periodo_default = NaN).
_SIN_ESPECIFICAR = object()


def elegir_tipo_y_categoria(tipo_default="Gasto", categoria_default=None, key_prefix=""):
    tipo = st.radio(
        "Tipo", ["Gasto", "Ingreso"], horizontal=True,
        index=0 if tipo_default == "Gasto" else 1, key=f"{key_prefix}tipo",
    )
    categorias = GASTO_CATEGORIAS if tipo == "Gasto" else INGRESO_CATEGORIAS
    actual = categoria_default if categoria_default in categorias else categorias[0]
    categoria = st.selectbox(
        "Categoría", categorias, index=categorias.index(actual), key=f"{key_prefix}categoria"
    )
    return tipo, categoria


def elegir_periodo(tipo, categoria, periodos, periodo_default=_SIN_ESPECIFICAR, key_prefix=""):
    es_ingreso_periodico = tipo == "Ingreso" and categoria in INGRESO_PERIODICO_CATEGORIAS
    opciones = periodos["periodo_id"].tolist()
    tenia_periodo = periodo_default is _SIN_ESPECIFICAR or pd.notna(periodo_default)

    if periodo_default is _SIN_ESPECIFICAR:
        activo = periodo_actual(periodos)
        periodo_default = activo.periodo_id if activo is not None else None

    if tipo == "Gasto" and opciones:
        asociar = st.checkbox(
            "💰 Este gasto es de este periodo", value=tenia_periodo, key=f"{key_prefix}asociar_gasto",
        )
        if not asociar:
            st.caption("Este gasto no se resta de ningún periodo — queda aparte.")
            return None, es_ingreso_periodico

    if (tipo == "Gasto" or es_ingreso_periodico) and opciones:
        idx = opciones.index(periodo_default) if periodo_default in opciones else 0
        periodo = st.selectbox(
            "Periodo asociado", opciones, index=idx, key=f"{key_prefix}periodo"
        )
        return periodo, es_ingreso_periodico
    st.caption("Este ingreso no descuenta el pendiente de ningún periodo — se suma aparte a tu saldo.")
    return None, es_ingreso_periodico


def elegir_cuenta(cuenta_default=None, key_prefix=""):
    idx = (
        CUENTAS_CON_EFECTIVO.index(cuenta_default)
        if cuenta_default in CUENTAS_CON_EFECTIVO
        else CUENTAS_CON_EFECTIVO.index("Efectivo")
    )
    return st.selectbox("¿En qué cuenta?", CUENTAS_CON_EFECTIVO, index=idx, key=f"{key_prefix}cuenta")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_widgets.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add widgets.py tests/test_widgets.py
git commit -m "Add shared form widgets (tipo/categoria, periodo, cuenta selectors)"
```

---

## Task 8: `sidebar.py` — new-period and new-transaction forms

**Files:**
- Create: `sidebar.py`
- Create: `tests/test_sidebar.py`

**Interfaces:**
- Consumes: `data_store.activar_periodo`, `ajustar_saldo_cuenta`, `delta_por_tipo`, `load_cuentas`, `save_cuentas`, `save_movimientos`, `save_periodos` (Tasks 3-4); `widgets.elegir_cuenta`, `elegir_periodo`, `elegir_tipo_y_categoria` (Task 7).
- Produces: `render_nuevo_periodo(periodos)`, `render_nuevo_movimiento(periodos, movimientos)` — consumed by `app.py` (Task 14).

- [ ] **Step 1: Write `tests/test_sidebar.py` with the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_sidebar.py -v`
Expected: FAIL — `sidebar` module does not exist yet.

- [ ] **Step 3: Create `sidebar.py`**

```python
from datetime import date

import pandas as pd
import streamlit as st

from data_store import (
    activar_periodo,
    ajustar_saldo_cuenta,
    delta_por_tipo,
    load_cuentas,
    save_cuentas,
    save_movimientos,
    save_periodos,
)
from widgets import elegir_cuenta, elegir_periodo, elegir_tipo_y_categoria


def render_nuevo_periodo(periodos):
    st.sidebar.header("➕ Nuevo periodo")
    with st.sidebar.form("nuevo_periodo", clear_on_submit=True):
        p_id = st.text_input("ID del periodo", placeholder="P-2026-08").strip()
        p_inicio = st.date_input("Fecha de inicio", value=date.today())
        p_origen = st.text_input("Origen (opcional)", placeholder="Sueldo, freelance, etc.")
        p_monto = st.number_input("Monto esperado", value=1000, step=50)

        if not st.form_submit_button("Crear periodo"):
            return
        if not p_id:
            st.sidebar.error("Ponle un ID al periodo.")
            return
        if p_id in periodos["periodo_id"].values:
            st.sidebar.error("Ya existe un periodo con ese ID.")
            return

        nuevo = pd.DataFrame([{
            "periodo_id": p_id,
            "fecha_inicio": pd.Timestamp(p_inicio),
            "fecha_fin": pd.Timestamp(p_inicio) + pd.Timedelta(days=14),
            "origen": p_origen,
            "monto_esperado": p_monto,
            "monto_recibido": 0,
            "activa": False,
        }])
        actualizados = activar_periodo(pd.concat([periodos, nuevo], ignore_index=True), p_id)
        save_periodos(actualizados)
        st.rerun()


def render_nuevo_movimiento(periodos, movimientos):
    with st.sidebar:
        st.header("📝 Registrar movimiento")
        m_tipo, m_categoria = elegir_tipo_y_categoria(key_prefix="m_")

        with st.form("nuevo_movimiento", clear_on_submit=True):
            m_fecha = st.date_input("Fecha", value=date.today(), key="mfecha")
            m_monto = st.number_input("Monto", min_value=0, step=1)
            m_periodo, es_ingreso_periodico = elegir_periodo(m_tipo, m_categoria, periodos, key_prefix="m_")
            m_cuenta = elegir_cuenta(key_prefix="m_")
            m_nota = st.text_input("Nota (opcional)")

            if not st.form_submit_button("Guardar movimiento"):
                return
            if m_monto <= 0:
                st.error("El monto debe ser mayor a cero.")
                return

            nuevo = pd.DataFrame([{
                "fecha": pd.Timestamp(m_fecha),
                "tipo": m_tipo,
                "categoria": m_categoria,
                "monto": m_monto,
                "periodo_id": m_periodo if m_periodo else pd.NA,
                "nota": m_nota,
                "cuenta": m_cuenta,
            }])
            movimientos = pd.concat([movimientos, nuevo], ignore_index=True)
            save_movimientos(movimientos)
            if es_ingreso_periodico and m_periodo:
                idx = periodos[periodos.periodo_id == m_periodo].index
                periodos.loc[idx, "monto_recibido"] += m_monto
                save_periodos(periodos)
            cuentas = load_cuentas()
            save_cuentas(ajustar_saldo_cuenta(cuentas, m_cuenta, delta_por_tipo(m_tipo, m_monto)))
            st.rerun()
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_sidebar.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add sidebar.py tests/test_sidebar.py
git commit -m "Add sidebar forms for new period and new transaction"
```

---

## Task 9: `inversion_tab.py` — investment zone (manual items, currencies, crypto, stocks)

**Files:**
- Create: `inversion_tab.py`
- Create: `tests/test_inversion_tab.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: `config.MONEDA_BASE` (Task 1); `data_store.load_acciones`, `load_criptos`, `load_inversiones`, `load_monedas`, `money`, `save_acciones`, `save_criptos`, `save_inversiones`, `save_monedas` (Tasks 4-5).
- Produces: `precio_activo_de(tipo, identificador) -> (precio, moneda) | None`, `precio_unitario_base(precio, moneda, tasa_usd) -> float | None`, `tasa_usd_a_base() -> float | None`, `desglose_patrimonio_inversion() -> dict`, `total_patrimonio_inversion() -> float`, `render()` — consumed by `resumen_tab.py` (Task 11), `patrimonio.py` (Task 13), `app.py` (Task 14).

**Design note (from the spec's Riesgos section):** `tasa_usd_a_base()` is `1.0` for free whenever `config.MONEDA_BASE == "USD"` (the shipped default) — no fetch needed. If the base currency is changed to something else, it pivots off a `"Dólares"` row in `monedas.csv` (exactly like the original pivoted USD/EUR off COP); if that row isn't there, it returns `None` and downstream code treats it like any other failed price fetch.

- [ ] **Step 1: Write `tests/test_inversion_tab.py` with the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_inversion_tab.py -v`
Expected: FAIL — `inversion_tab` module does not exist yet.

- [ ] **Step 3: Create `inversion_tab.py`**

```python
from datetime import date

import pandas as pd
import requests
import streamlit as st

import config
from data_store import (
    load_acciones,
    load_criptos,
    load_inversiones,
    load_monedas,
    money,
    save_acciones,
    save_criptos,
    save_inversiones,
    save_monedas,
)

MONEDA_A_CODIGO = {"Euros": "EUR", "Dólares": "USD", "Libras": "GBP"}
DIAS_AVISO_DESACTUALIZADO = 15


@st.cache_data(ttl=86400, show_spinner=False)
def _tasa_en_vivo(codigo, moneda_destino):
    try:
        r = requests.get(f"https://open.er-api.com/v6/latest/{codigo}", timeout=5)
        r.raise_for_status()
        return round(r.json()["rates"][moneda_destino], 4)
    except Exception:
        return None


def _actualizar_tasas_del_dia(monedas):
    cambiado = False
    for i, fila in monedas.iterrows():
        tasa_hoy = _tasa_en_vivo(MONEDA_A_CODIGO[fila["moneda"]], config.MONEDA_BASE)
        if tasa_hoy is not None and tasa_hoy != fila["tasa"]:
            monedas.loc[i, "tasa"] = tasa_hoy
            cambiado = True
    if cambiado:
        save_monedas(monedas)
    return monedas


def tasa_usd_a_base():
    """Tasa USD -> moneda_base, usada para convertir cripto/acciones (siempre
    cotizadas en USD por las APIs que usamos) a la moneda base de la app. Si
    la moneda base ya es USD, es 1.0 sin necesidad de fetch. Si no, se apoya
    en la fila "Dólares" de monedas.csv (por eso, si tu moneda base no es
    USD, agregá "Dólares" a la lista de monedas rastreadas en render_monedas
    — MONEDA_A_CODIGO ya trae su código listo)."""
    if config.MONEDA_BASE == "USD":
        return 1.0
    monedas = _actualizar_tasas_del_dia(load_monedas())
    fila = monedas.loc[monedas.moneda == "Dólares"]
    if fila.empty:
        return None
    return fila["tasa"].iloc[0]


@st.cache_data(ttl=300, show_spinner=False)
def _precio_cripto(id_coingecko):
    """CoinGecko siempre cotiza en USD."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": id_coingecko, "vs_currencies": "usd"}, timeout=5,
        )
        r.raise_for_status()
        return r.json()[id_coingecko]["usd"], "USD"
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _precio_accion(ticker):
    """Yahoo Finance cotiza cada ticker en la moneda de su propia bolsa — un
    ADR en NYSE (ej. "EC") sale en USD, pero el mismo papel en la bolsa local
    (ej. "ECOPETROL.CL") sale en la moneda de esa bolsa."""
    try:
        r = requests.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=5,
        )
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        return meta["regularMarketPrice"], meta.get("currency") or "USD"
    except Exception:
        return None


def precio_unitario_base(precio, moneda, tasa_usd):
    """Convierte un precio cotizado en `moneda` a la moneda base de la app.
    Soporta USD (vía tasa_usd) y la moneda base misma (pasa directo). Un
    ticker en otra moneda (ej. EUR cuando la base es USD) queda sin poder
    valorizarse — se trata igual que un fetch fallido en vez de asumir una
    tasa que no tenemos."""
    if moneda == config.MONEDA_BASE:
        return precio
    if moneda == "USD":
        return precio * tasa_usd if tasa_usd is not None else None
    return None


MONEDAS_MOSTRAR = [config.MONEDA_BASE] if config.MONEDA_BASE == "USD" else [config.MONEDA_BASE, "USD"]


def _convertir_base_a(valor_base, moneda_mostrar, tasa_usd):
    if moneda_mostrar == config.MONEDA_BASE:
        return valor_base
    return valor_base / tasa_usd


def _money_en(moneda_mostrar):
    if moneda_mostrar == config.MONEDA_BASE:
        return money
    return lambda n: f"${n:,.2f}"


def precio_activo_de(tipo, identificador):
    """Dispatcher público para pedir el precio en vivo de un activo por su
    tipo ("cripto" o "accion"), para que otros módulos no tengan que saber
    cuál de los dos fetchs privados usar. Normaliza el identificador (cripto
    en minúsculas como lo espera CoinGecko, acción en mayúsculas como el
    ticker de Yahoo Finance). Devuelve (precio, moneda) o None si falló el
    fetch — la moneda depende del activo, no siempre es USD."""
    if tipo == "cripto":
        return _precio_cripto(str(identificador).strip().lower())
    return _precio_accion(str(identificador).strip().upper())


def _precios_de_activos(activos, columna_id, fetch_precio, tasa_usd):
    """Para cada fila con un identificador, trae el precio (en la moneda
    nativa del activo) y calcula valor y ganancia/pérdida en la moneda base.
    valor_base queda en None si no se pudo traer el precio, o si vino en una
    moneda que no sabemos convertir. ganancia_base queda en None si no se
    cargó un precio de compra (precio_compra == 0). precio_compra siempre
    queda en la moneda base (así se guarda desde "Mover a inversión" y desde
    acá), sin importar en qué moneda cotice el activo."""
    filas = []
    for _, fila in activos.dropna(subset=[columna_id]).iterrows():
        identificador = str(fila[columna_id]).strip()
        if not identificador:
            continue
        resultado = fetch_precio(identificador.lower() if columna_id == "id" else identificador.upper())
        precio, moneda = resultado if resultado is not None else (None, None)
        cantidad = fila["cantidad"]
        precio_compra = fila.get("precio_compra", 0.0)
        precio_unitario_base_ = precio_unitario_base(precio, moneda, tasa_usd) if precio is not None else None
        valor_base = precio_unitario_base_ * cantidad if precio_unitario_base_ is not None else None
        ganancia_base = ganancia_pct = None
        if valor_base is not None and precio_compra:
            costo_base = precio_compra * cantidad
            ganancia_base = valor_base - costo_base
            ganancia_pct = (ganancia_base / costo_base * 100) if costo_base else None
        filas.append({
            "identificador": identificador, "precio": precio, "moneda": moneda, "valor_base": valor_base,
            "ganancia_base": ganancia_base, "ganancia_pct": ganancia_pct,
        })
    return filas


def _valor_activos_base(cargar, columna_id, fetch_precio, tasa_usd):
    filas = _precios_de_activos(cargar(), columna_id, fetch_precio, tasa_usd)
    return sum(f["valor_base"] for f in filas if f["valor_base"] is not None)


def _render_activos_en_vivo(
    titulo, etiqueta_total, ayuda, cargar, guardar, columna_id, columna_id_label, fetch_precio, tasa_usd,
    moneda_mostrar,
):
    st.subheader(titulo)
    st.caption(ayuda)

    activos = cargar()
    editado = st.data_editor(
        activos, num_rows="dynamic", use_container_width=True, hide_index=True,
        key=f"editor_{columna_id}",
        column_config={
            columna_id: st.column_config.TextColumn(columna_id_label),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.0001, format="%.6f"),
            "precio_compra": st.column_config.NumberColumn(
                f"Precio de compra (en {config.MONEDA_BASE}, opcional)", min_value=0.0, step=0.01, format="%.4f"
            ),
        },
    )
    editado["cantidad"] = editado["cantidad"].fillna(0.0)
    editado["precio_compra"] = editado["precio_compra"].fillna(0.0)
    if not editado.equals(activos):
        guardar(editado)

    filas_precio = _precios_de_activos(editado, columna_id, fetch_precio, tasa_usd)
    etiqueta_valor = f"Valor ({moneda_mostrar})"
    formatear = _money_en(moneda_mostrar)
    filas = []
    for f in filas_precio:
        if f["valor_base"] is None:
            filas.append({columna_id_label: f["identificador"], "Precio": "—", etiqueta_valor: "—", "Ganancia/pérdida": "—"})
            continue
        valor_mostrado = _convertir_base_a(f["valor_base"], moneda_mostrar, tasa_usd)
        if f["ganancia_base"] is None:
            ganancia = "—"
        else:
            ganancia_mostrada = _convertir_base_a(f["ganancia_base"], moneda_mostrar, tasa_usd)
            ganancia = f"{formatear(ganancia_mostrada)} ({f['ganancia_pct']:+.1f}%)"
        filas.append({
            columna_id_label: f["identificador"],
            "Precio": f"{f['precio']:,.2f} {f['moneda']}",
            etiqueta_valor: formatear(valor_mostrado),
            "Ganancia/pérdida": ganancia,
        })

    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        total_base = sum(f["valor_base"] for f in filas_precio if f["valor_base"] is not None)
        st.metric(f"{etiqueta_total} ({moneda_mostrar})", formatear(_convertir_base_a(total_base, moneda_mostrar, tasa_usd)))


def render_inversiones():
    st.subheader("📈 Inversiones")
    st.caption("Editá el saldo a mano, o movele plata sobrante desde \"Mover a inversión\" en la pestaña Resumen.")
    inversiones = load_inversiones()

    with st.form("inversiones_form"):
        cols = st.columns(len(inversiones))
        nuevos_saldos = []
        for col, (_, fila) in zip(cols, inversiones.iterrows()):
            nuevos_saldos.append(
                col.number_input(
                    fila["item"], min_value=0, step=10, value=int(fila["saldo"]), key=f"inv_{fila['item']}"
                )
            )
        if st.form_submit_button("💾 Guardar inversiones"):
            cambiaron = inversiones["saldo"].values != nuevos_saldos
            inversiones["saldo"] = nuevos_saldos
            inversiones.loc[cambiaron, "actualizado"] = date.today().isoformat()
            save_inversiones(inversiones)
            st.rerun()

    hoy = date.today()
    for _, fila in inversiones.iterrows():
        dias = (hoy - date.fromisoformat(fila["actualizado"])).days
        if dias > DIAS_AVISO_DESACTUALIZADO:
            st.warning(f"⚠️ \"{fila['item']}\" no se actualiza hace {dias} días — revisalo en la app del banco.")
        else:
            st.caption(f"{fila['item']}: actualizado hace {dias} día{'s' if dias != 1 else ''}.")


def render_monedas():
    st.subheader("💱 Monedas extranjeras")
    monedas = _actualizar_tasas_del_dia(load_monedas())
    st.caption(
        f"Las tasas se traen de open.er-api.com hacia {config.MONEDA_BASE}, una vez al día — si no hay "
        "internet, se usa la última tasa que quedó guardada."
    )

    with st.form("monedas_form"):
        nuevos_montos, nuevas_tasas = [], []
        for _, fila in monedas.iterrows():
            c1, c2 = st.columns(2)
            nuevos_montos.append(
                c1.number_input(
                    f"{fila['moneda']} (monto)", min_value=0.0, step=1.0,
                    value=float(fila["monto"]), key=f"moneda_{fila['moneda']}",
                )
            )
            nuevas_tasas.append(
                c2.number_input(
                    f"Tasa {fila['moneda']} → {config.MONEDA_BASE}", min_value=0.0, step=0.01,
                    value=float(fila["tasa"]), key=f"tasa_{fila['moneda']}",
                )
            )
        if st.form_submit_button("💾 Guardar"):
            monedas["monto"] = nuevos_montos
            monedas["tasa"] = nuevas_tasas
            save_monedas(monedas)
            st.rerun()

    valor_base = monedas["monto"] * monedas["tasa"]
    cols = st.columns(len(monedas) + 1)
    for col, (_, fila) in zip(cols, monedas.iterrows()):
        col.metric(fila["moneda"], money(fila["monto"] * fila["tasa"]))
    cols[-1].metric(f"Total en {config.MONEDA_BASE}", money(valor_base.sum()))


def render_criptos(tasa_usd, moneda_mostrar):
    _render_activos_en_vivo(
        titulo="🪙 Cripto (tiempo real)",
        etiqueta_total="Total cripto",
        ayuda=(
            "Agregá o quitá monedas con los botones de la tabla (+ al final, 🗑️ en la fila). "
            "El ID tiene que ser el que usa CoinGecko, por ejemplo: bitcoin, solana, dogecoin, cardano. "
            "Si cargás el precio de compra, te calculo la ganancia o pérdida."
        ),
        cargar=load_criptos, guardar=save_criptos,
        columna_id="id", columna_id_label="ID (CoinGecko)",
        fetch_precio=_precio_cripto, tasa_usd=tasa_usd, moneda_mostrar=moneda_mostrar,
    )


def render_acciones(tasa_usd, moneda_mostrar):
    _render_activos_en_vivo(
        titulo="📊 Acciones (tiempo real)",
        etiqueta_total="Total acciones",
        ayuda=(
            "Agregá o quitá acciones con los botones de la tabla. El ticker es el de Yahoo Finance, ej: "
            "AAPL, TSLA, o el de la bolsa local si cotiza ahí, ej: ECOPETROL.CL. "
            "Si cargás el precio de compra, te calculo la ganancia o pérdida."
        ),
        cargar=load_acciones, guardar=save_acciones,
        columna_id="ticker", columna_id_label="Ticker",
        fetch_precio=_precio_accion, tasa_usd=tasa_usd, moneda_mostrar=moneda_mostrar,
    )


def desglose_patrimonio_inversion():
    """Valor en la moneda base de cada categoría de la Zona de inversión —
    lo usa el total de arriba de todo y el gráfico de distribución del
    patrimonio."""
    monedas = _actualizar_tasas_del_dia(load_monedas())
    tasa_usd = tasa_usd_a_base()
    desglose = {fila["item"]: fila["saldo"] for _, fila in load_inversiones().iterrows()}
    desglose["Monedas extranjeras"] = (monedas["monto"] * monedas["tasa"]).sum()
    desglose["Cripto"] = _valor_activos_base(load_criptos, "id", _precio_cripto, tasa_usd)
    desglose["Acciones"] = _valor_activos_base(load_acciones, "ticker", _precio_accion, tasa_usd)
    return desglose


def total_patrimonio_inversion():
    return sum(desglose_patrimonio_inversion().values())


def render():
    render_inversiones()
    st.divider()
    render_monedas()
    st.divider()
    tasa_usd = tasa_usd_a_base()
    moneda_mostrar = st.radio(
        "Mostrar valor y ganancia de cripto/acciones en",
        MONEDAS_MOSTRAR, horizontal=True, key="moneda_mostrar_inversion",
    )
    render_criptos(tasa_usd, moneda_mostrar)
    st.divider()
    render_acciones(tasa_usd, moneda_mostrar)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_inversion_tab.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Extend `tests/conftest.py` with the network-isolation fixture, now that `inversion_tab` exists**

Append to `tests/conftest.py`:

```python
import inversion_tab


@pytest.fixture(autouse=True)
def _sin_red_inversion(monkeypatch):
    """Simula estar sin internet para toda la suite: la app ya sabe seguir
    con la última tasa o valor guardado cuando el fetch en vivo devuelve
    None. Sin esto, correr la suite sin conexión sería flaky."""
    monkeypatch.setattr(inversion_tab, "_tasa_en_vivo", lambda codigo, moneda_destino: None)
    monkeypatch.setattr(inversion_tab, "_precio_cripto", lambda id_coingecko: None)
    monkeypatch.setattr(inversion_tab, "_precio_accion", lambda ticker: None)
```

- [ ] **Step 6: Run the full suite to confirm nothing broke**

Run: `pytest tests/ -v`
Expected: PASS (all tests so far, across all modules).

- [ ] **Step 7: Commit**

```bash
git add inversion_tab.py tests/test_inversion_tab.py tests/conftest.py
git commit -m "Add investment zone: manual items, foreign currencies, live crypto/stocks"
```

---

## Task 10: `resumen_tab.py` — header (metrics + alert)

**Files:**
- Create: `resumen_tab.py` (this task starts it; Tasks 11-12 append to it)
- Create: `tests/test_resumen_tab.py` (this task starts it; Tasks 11-12 append to it)

**Interfaces:**
- Consumes: `data_store.gastado_en_periodo`, `money`, `pendiente_por_cobrar`, `periodo_actual`, `regalos_total`, `saldo_restante_periodo` (Tasks 3-4).
- Produces: `_estado_alerta_periodo(recibido, restante) -> (nivel, mensaje) | None`, `render_alerta_periodo(periodos, movimientos)`, `render_metricas(periodos, movimientos)`, `render_header(periodos, movimientos)` — `render_header` is consumed by `app.py` (Task 14), called before the tabs are created (mirrors the original's standalone `inicio.py`, folded into `resumen_tab.py` per the spec's file list).

- [ ] **Step 1: Write `tests/test_resumen_tab.py` with the failing header tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_resumen_tab.py -v`
Expected: FAIL — `resumen_tab` module does not exist yet.

- [ ] **Step 3: Create `resumen_tab.py` with just the header section**

```python
from datetime import date

import pandas as pd
import streamlit as st

from data_store import (
    gastado_en_periodo,
    money,
    pendiente_por_cobrar,
    periodo_actual,
    regalos_total,
    saldo_restante_periodo,
)

UMBRAL_ALERTA_RESTANTE_PCT = 0.20  # advertir con menos del 20% del recibido restante


def _estado_alerta_periodo(recibido, restante):
    """None si todo bien; ("error", msg) si se pasó del presupuesto;
    ("warning", msg) si queda poco. El chequeo de negativo va primero y no
    depende de `recibido` — un periodo sin nada cobrado todavía pero con
    gasto ya cargado contra él también tiene que alertar."""
    if restante < 0:
        return "error", f"Te pasaste del saldo del periodo por {money(-restante)}."
    if recibido > 0 and restante < recibido * UMBRAL_ALERTA_RESTANTE_PCT:
        return "warning", f"Queda menos del {int(UMBRAL_ALERTA_RESTANTE_PCT * 100)}% del periodo — {money(restante)} disponibles."
    return None


def render_alerta_periodo(periodos, movimientos):
    p_actual = periodo_actual(periodos)
    if p_actual is None:
        return
    restante = saldo_restante_periodo(periodos, movimientos, p_actual.periodo_id)
    estado = _estado_alerta_periodo(p_actual.monto_recibido, restante)
    if estado is None:
        return
    nivel, mensaje = estado
    (st.error if nivel == "error" else st.warning)(mensaje)


def render_metricas(periodos, movimientos):
    p_actual = periodo_actual(periodos)
    if p_actual is not None:
        restante = money(saldo_restante_periodo(periodos, movimientos, p_actual.periodo_id))
        gastado = money(gastado_en_periodo(movimientos, p_actual.periodo_id))
        etiqueta_gastado = f"🧾 Gastado en el periodo ({p_actual.periodo_id})"
    else:
        restante = "—"
        gastado = "—"
        etiqueta_gastado = "🧾 Gastado en el periodo"

    metricas = [
        ("📅 Saldo restante del periodo", restante),
        (etiqueta_gastado, gastado),
        ("⏳ Pendiente por cobrar", money(pendiente_por_cobrar(periodos))),
        ("🎁 Regalos recibidos", money(regalos_total(movimientos))),
    ]
    for col, (label, valor) in zip(st.columns(len(metricas)), metricas):
        col.metric(label, valor)


def render_header(periodos, movimientos):
    st.subheader("🏠 Inicio")
    render_metricas(periodos, movimientos)
    render_alerta_periodo(periodos, movimientos)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_resumen_tab.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add resumen_tab.py tests/test_resumen_tab.py
git commit -m "Add resumen_tab header: period metrics and budget alert"
```

---

## Task 11: `resumen_tab.py` — accounts, move money, invest/withdraw transfers

**Files:**
- Modify: `resumen_tab.py`
- Modify: `tests/test_resumen_tab.py`

**Interfaces:**
- Consumes: `data_store.CUENTAS_CON_EFECTIVO`, `ajustar_saldo_cuenta`, `ajustar_saldo_inversion`, `efectivo`, `load_acciones`, `load_criptos`, `load_cuentas`, `load_inversiones`, `money`, `registrar_compra_activo`, `registrar_venta_activo`, `save_acciones`, `save_criptos`, `save_cuentas`, `save_inversiones`, `save_movimientos` (Tasks 4-5); `inversion_tab.precio_activo_de`, `precio_unitario_base`, `tasa_usd_a_base` (Task 9).
- Produces: `render_cuentas(movimientos)`, `render_mover_a_inversion(movimientos)`, `render_retirar_inversion(movimientos)` — consumed by this file's own `render()` (Task 12).

- [ ] **Step 1: Append the failing tests to `tests/test_resumen_tab.py`**

```python
def test_mover_dinero_entre_cuentas_ajusta_ambos_saldos():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros", "Corriente"], "saldo": [100, 50]}))

    def _app():
        import resumen_tab
        resumen_tab.render_cuentas(pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()
    at.selectbox(key="mov_origen").select("Ahorros").run()
    at.selectbox(key="mov_destino").select("Corriente").run()
    at.number_input(key="mov_monto").set_value(30).run()
    next(b for b in at.button if "Mover" == b.label.split(" ", 1)[-1] or b.label.endswith("Mover")).click().run()

    cuentas = data_store.load_cuentas()
    assert cuentas.loc[cuentas.cuenta == "Ahorros", "saldo"].iloc[0] == 70
    assert cuentas.loc[cuentas.cuenta == "Corriente", "saldo"].iloc[0] == 80


def test_mover_dinero_origen_igual_a_destino_da_error():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros"], "saldo": [100]}))

    def _app():
        import resumen_tab
        resumen_tab.render_cuentas(pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()
    at.number_input(key="mov_monto").set_value(10).run()
    at.button(key="mover_dinero_form-Mover").run() if False else None
    boton = next(b for b in at.button if b.label.endswith("Mover"))
    boton.click().run()

    assert any("cuentas distintas" in e.value for e in at.error)


def test_ajustar_saldo_base_permite_negativo_para_tarjeta_de_credito():
    import data_store

    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Tarjeta de crédito"], "saldo": [0]}))

    def _app():
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_resumen_tab.py -v -k "mover or retirar or ajustar_saldo_base or efectivo_negativo"`
Expected: FAIL — `render_cuentas`/`render_mover_a_inversion`/`render_retirar_inversion` don't exist yet.

- [ ] **Step 3: Append the implementation to `resumen_tab.py`**

```python
from data_store import (
    CUENTAS_CON_EFECTIVO,
    ajustar_saldo_cuenta,
    ajustar_saldo_inversion,
    efectivo,
    load_acciones,
    load_criptos,
    load_cuentas,
    load_inversiones,
    registrar_compra_activo,
    registrar_venta_activo,
    save_acciones,
    save_criptos,
    save_cuentas,
    save_inversiones,
    save_movimientos,
)
from inversion_tab import precio_activo_de, precio_unitario_base, tasa_usd_a_base


def render_cuentas(movimientos):
    st.subheader("💵 Mis cuentas")
    cuentas = load_cuentas()

    cols = st.columns(len(cuentas) + 1)
    for col, (_, fila) in zip(cols, cuentas.iterrows()):
        col.metric(fila.cuenta, money(fila.saldo))
    efvo = efectivo(movimientos, cuentas)
    cols[-1].metric("💶 Efectivo", money(efvo))
    if efvo < 0:
        st.warning(
            "El efectivo calculado da negativo — revisa el saldo base de tus cuentas o el historial."
        )

    with st.expander("🔁 Mover dinero entre cuentas", expanded=True):
        with st.form("mover_dinero_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            origen = c1.selectbox("Desde", CUENTAS_CON_EFECTIVO, index=0, key="mov_origen")
            destino = c2.selectbox("Hacia", CUENTAS_CON_EFECTIVO, index=len(CUENTAS_CON_EFECTIVO) - 1, key="mov_destino")
            monto_mover = c3.number_input("Monto", min_value=0, step=10, key="mov_monto")
            if st.form_submit_button("🔁 Mover"):
                if monto_mover <= 0:
                    st.error("El monto debe ser mayor a cero.")
                elif origen == destino:
                    st.error("Elige dos cuentas distintas.")
                else:
                    cuentas = ajustar_saldo_cuenta(cuentas, origen, -monto_mover)
                    cuentas = ajustar_saldo_cuenta(cuentas, destino, monto_mover)
                    save_cuentas(cuentas)
                    st.success(f"Moviste {money(monto_mover)} de {origen} a {destino}.")
                    st.rerun()

    render_mover_a_inversion(movimientos)
    render_retirar_inversion(movimientos)

    with st.expander("✏️ Ajustar saldo base de una cuenta"):
        with st.form("cuentas_form"):
            ccols = st.columns(len(cuentas))
            nuevos_saldos = []
            for col, (_, fila) in zip(ccols, cuentas.iterrows()):
                nuevos_saldos.append(
                    # Sin min_value: una tarjeta de crédito se guarda como cuenta
                    # con saldo negativo (la deuda), y ese negativo tiene que
                    # poder corregirse a mano.
                    col.number_input(
                        fila.cuenta, step=10, value=int(fila.saldo), key=f"cuenta_{fila.cuenta}"
                    )
                )
            if st.form_submit_button("💾 Guardar saldos"):
                cuentas["saldo"] = nuevos_saldos
                save_cuentas(cuentas)
                st.rerun()


def _opciones_transferencia_inversion():
    """Junta las inversiones existentes para usar como destino de "Mover a
    inversión" u origen de "Retirar de inversión": los ítems manuales de
    inversiones.csv, más cripto/acciones ya cargadas en sus tablas (no se
    pueden crear ítems nuevos desde acá)."""
    opciones = []
    for _, fila in load_inversiones().iterrows():
        opciones.append({"tipo": "manual", "identificador": fila["item"], "etiqueta": fila["item"]})
    for _, fila in load_criptos().iterrows():
        if pd.notna(fila["id"]) and str(fila["id"]).strip():
            identificador = str(fila["id"]).strip()
            opciones.append({"tipo": "cripto", "identificador": identificador, "etiqueta": f"🪙 {fila['simbolo']}"})
    for _, fila in load_acciones().iterrows():
        if pd.notna(fila["ticker"]) and str(fila["ticker"]).strip():
            identificador = str(fila["ticker"]).strip()
            opciones.append({"tipo": "accion", "identificador": identificador, "etiqueta": f"📊 {identificador}"})
    return opciones


def _guardar_transferencia_inversion(origen, opcion, monto, movimientos):
    if opcion["tipo"] == "manual":
        save_inversiones(ajustar_saldo_inversion(load_inversiones(), opcion["identificador"], monto))
    else:
        resultado = precio_activo_de(opcion["tipo"], opcion["identificador"])
        precio, moneda = resultado if resultado is not None else (None, None)
        precio_unitario = precio_unitario_base(precio, moneda, tasa_usd_a_base()) if precio is not None else None
        if precio_unitario is None:
            st.error("No se pudo traer el precio en vivo, intentá de nuevo en un momento.")
            return
        cantidad_nueva = monto / precio_unitario
        if opcion["tipo"] == "cripto":
            save_criptos(registrar_compra_activo(
                load_criptos(), "id", opcion["identificador"], cantidad_nueva, precio_unitario
            ))
        else:
            save_acciones(registrar_compra_activo(
                load_acciones(), "ticker", opcion["identificador"], cantidad_nueva, precio_unitario
            ))

    save_cuentas(ajustar_saldo_cuenta(load_cuentas(), origen, -monto))

    nuevo = pd.DataFrame([{
        "fecha": pd.Timestamp(date.today()), "tipo": "Gasto", "categoria": "📈 Inversión",
        "monto": monto, "periodo_id": pd.NA, "nota": f"Transferencia a {opcion['etiqueta']}", "cuenta": origen,
    }])
    save_movimientos(pd.concat([movimientos, nuevo], ignore_index=True))

    st.success(
        f"Moviste {money(monto)} de {origen} a {opcion['etiqueta']}. "
        "Recordá hacer la transferencia real en el banco/exchange si todavía no la hiciste."
    )
    st.rerun()


def render_mover_a_inversion(movimientos):
    with st.expander("📈 Mover a inversión"):
        opciones = _opciones_transferencia_inversion()
        if not opciones:
            st.info("Todavía no hay ningún ítem de inversión para transferir.")
            return

        with st.form("mover_a_inversion_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            origen = c1.selectbox("Desde", CUENTAS_CON_EFECTIVO, index=0, key="mov_inv_origen")
            etiquetas = [o["etiqueta"] for o in opciones]
            destino_etiqueta = c2.selectbox("Hacia", etiquetas, index=0, key="mov_inv_destino")
            monto_mover = c3.number_input("Monto", min_value=0, step=10, key="mov_inv_monto")

            if not st.form_submit_button("📈 Mover a inversión"):
                return
            if monto_mover <= 0:
                st.error("El monto debe ser mayor a cero.")
                return

            opcion = next(o for o in opciones if o["etiqueta"] == destino_etiqueta)
            _guardar_transferencia_inversion(origen, opcion, monto_mover, movimientos)


def _valor_disponible_inversion(opcion):
    """Cuánto se puede retirar hoy de `opcion`, en la moneda base: el saldo
    directo para un ítem manual, o cantidad × precio de hoy para
    cripto/acciones. Devuelve None si no se pudo traer el precio en vivo."""
    if opcion["tipo"] == "manual":
        inversiones = load_inversiones()
        return inversiones.loc[inversiones.item == opcion["identificador"], "saldo"].iloc[0]

    resultado = precio_activo_de(opcion["tipo"], opcion["identificador"])
    precio, moneda = resultado if resultado is not None else (None, None)
    precio_unitario = precio_unitario_base(precio, moneda, tasa_usd_a_base()) if precio is not None else None
    if precio_unitario is None:
        return None
    activos = load_criptos() if opcion["tipo"] == "cripto" else load_acciones()
    columna_id = "id" if opcion["tipo"] == "cripto" else "ticker"
    cantidad = activos.loc[activos[columna_id] == opcion["identificador"], "cantidad"].iloc[0]
    return cantidad * precio_unitario


def _guardar_retiro_inversion(destino, opcion, monto, movimientos):
    disponible = _valor_disponible_inversion(opcion)
    if disponible is None:
        st.error("No se pudo traer el precio en vivo, intentá de nuevo en un momento.")
        return
    if monto > disponible:
        st.error(f"No podés retirar más de lo que hay en {opcion['etiqueta']} ({money(disponible)}).")
        return

    if opcion["tipo"] == "manual":
        save_inversiones(ajustar_saldo_inversion(load_inversiones(), opcion["identificador"], -monto))
    else:
        resultado = precio_activo_de(opcion["tipo"], opcion["identificador"])
        precio, moneda = resultado
        precio_unitario = precio_unitario_base(precio, moneda, tasa_usd_a_base())
        cantidad_vendida = monto / precio_unitario
        if opcion["tipo"] == "cripto":
            save_criptos(registrar_venta_activo(load_criptos(), "id", opcion["identificador"], cantidad_vendida))
        else:
            save_acciones(registrar_venta_activo(load_acciones(), "ticker", opcion["identificador"], cantidad_vendida))

    save_cuentas(ajustar_saldo_cuenta(load_cuentas(), destino, monto))

    nuevo = pd.DataFrame([{
        "fecha": pd.Timestamp(date.today()), "tipo": "Ingreso", "categoria": "📈 Retiro de inversión",
        "monto": monto, "periodo_id": pd.NA, "nota": f"Retiro desde {opcion['etiqueta']}", "cuenta": destino,
    }])
    save_movimientos(pd.concat([movimientos, nuevo], ignore_index=True))

    st.success(
        f"Retiraste {money(monto)} de {opcion['etiqueta']} a {destino}. "
        "Recordá hacer el retiro real en el banco/exchange si todavía no lo hiciste."
    )
    st.rerun()


def render_retirar_inversion(movimientos):
    with st.expander("💵 Retirar de inversión"):
        opciones = _opciones_transferencia_inversion()
        if not opciones:
            st.info("Todavía no hay ningún ítem de inversión del que retirar.")
            return

        with st.form("retirar_inversion_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            etiquetas = [o["etiqueta"] for o in opciones]
            origen_etiqueta = c1.selectbox("Desde", etiquetas, index=0, key="ret_inv_origen")
            destino = c2.selectbox("Hacia", CUENTAS_CON_EFECTIVO, index=0, key="ret_inv_destino")
            monto_retirar = c3.number_input("Monto", min_value=0, step=10, key="ret_inv_monto")

            if not st.form_submit_button("💵 Retirar de inversión"):
                return
            if monto_retirar <= 0:
                st.error("El monto debe ser mayor a cero.")
                return

            opcion = next(o for o in opciones if o["etiqueta"] == origen_etiqueta)
            _guardar_retiro_inversion(destino, opcion, monto_retirar, movimientos)
```

Add `from datetime import date` and `import pandas as pd` to the top of `resumen_tab.py` if not already there from Task 10 (Task 10's header code already imports `pandas as pd`? — it does not; add both imports now alongside the existing `import streamlit as st`).

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_resumen_tab.py -v`
Expected: PASS (all tests, including Task 10's).

- [ ] **Step 5: Commit**

```bash
git add resumen_tab.py tests/test_resumen_tab.py
git commit -m "Add accounts view, inter-account transfers, and invest/withdraw flows"
```

---

## Task 12: `resumen_tab.py` — periods table, expense chart, transaction history, undo

**Files:**
- Modify: `resumen_tab.py`
- Modify: `tests/test_resumen_tab.py`

**Interfaces:**
- Consumes: `data_store.CUENTAS_CON_EFECTIVO`, `GASTO_CATEGORIAS`, `INGRESO_CATEGORIAS`, `INGRESO_PERIODICO_CATEGORIAS`, `COLOR_MAP`, `activar_periodo`, `ajustar_saldo_cuenta`, `delta_por_tipo`, `deshacer_ultimo_cambio`, `save_movimientos`, `save_periodos` (Tasks 3-4); `charts.barras_horizontales` (Task 6); module-level `data_store` import for `data_store.MOVIMIENTOS_FILE`/`PERIODOS_FILE`/`CUENTAS_FILE`.
- Produces: `_tiene_periodo(valor) -> bool`, `_fila_valida(fila) -> str | None`, `_campos_iguales(antes, despues) -> bool`, `_aplicar_efecto(periodos, cuentas, fila)`, `_revertir_efecto(periodos, cuentas, fila)`, `_aplicar_filtro_historial(tabla, fecha_desde, fecha_hasta, categorias, cuentas) -> DataFrame`, `render_periodos_tabla(periodos, movimientos)`, `render_gastos_chart(movimientos)`, `render_deshacer_historial()`, `render_historial(periodos, movimientos)`, `render(periodos, movimientos)` — `render` is consumed by `app.py` (Task 14).

This completes `resumen_tab.py`.

- [ ] **Step 1: Append the failing tests to `tests/test_resumen_tab.py`**

```python
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
    return pd.DataFrame([{
        "periodo_id": "P1", "fecha_inicio": pd.Timestamp("2026-08-01"),
        "origen": "Sueldo", "monto_esperado": 1000, "monto_recibido": monto_recibido,
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
    def _app():
        import resumen_tab
        resumen_tab.render_periodos_tabla(_periodo_unico(), pd.DataFrame(
            columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
        ))

    at = AppTest.from_function(_app)
    at.run()
    assert not at.exception


def test_render_historial_no_explota_con_datos_sembrados():
    def _app():
        import resumen_tab
        resumen_tab.render_historial(_periodo_unico(), pd.DataFrame([{
            "fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
            "monto": 40, "periodo_id": "P1", "nota": "", "cuenta": "Ahorros",
        }]))

    at = AppTest.from_function(_app)
    at.run()
    assert not at.exception
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_resumen_tab.py -v -k "tiene_periodo or fila_valida or campos_iguales or efecto or guardar_historial or filtro or deshacer_historial or periodos_tabla or render_historial"`
Expected: FAIL — none of these functions exist yet.

- [ ] **Step 3: Append the implementation to `resumen_tab.py`**

```python
from data_store import (
    INGRESO_CATEGORIAS,
    INGRESO_PERIODICO_CATEGORIAS,
    activar_periodo,
    deshacer_ultimo_cambio,
)
import charts
import data_store


def _guardar_cambios_periodos(periodos, editado):
    """Aplica a `periodos` los valores editables (Origen/Inicio/Fin/
    Esperado/Recibido/Activa) que vuelven de la tabla y guarda si hubo algún
    cambio real. El id del periodo queda fijo — no se puede renombrar desde
    acá, porque el historial referencia periodos por ese id.

    "Fin" es un campo propio (no se recalcula solo) para poder alargar o
    acortar un periodo puntual.

    Si alguna fila pasó de inactiva a activa en esta edición, se fuerza la
    exclusividad (esa gana, el resto queda desactivado) aunque el usuario
    haya tildado más de una a la vez."""
    original = periodos.set_index("periodo_id")
    periodos = original.copy()
    hubo_cambios = False
    activadas = []

    for _, fila in editado.iterrows():
        pid = fila["Periodo"]
        nueva_fecha = pd.Timestamp(fila["Inicio"])
        nueva_fin = pd.Timestamp(fila["Fin"])
        actual = original.loc[pid]
        sin_cambios = (
            (actual.origen or "") == (fila["Origen"] or "")
            and pd.Timestamp(actual.fecha_inicio).normalize() == nueva_fecha.normalize()
            and pd.Timestamp(actual.fecha_fin).normalize() == nueva_fin.normalize()
            and float(actual.monto_esperado) == float(fila["Esperado"])
            and float(actual.monto_recibido) == float(fila["Recibido"])
            and bool(actual.activa) == bool(fila["Activa"])
        )
        if sin_cambios:
            continue
        periodos.loc[pid, ["origen", "fecha_inicio", "fecha_fin", "monto_esperado", "monto_recibido", "activa"]] = [
            fila["Origen"], nueva_fecha, nueva_fin, fila["Esperado"], fila["Recibido"], bool(fila["Activa"]),
        ]
        hubo_cambios = True
        if bool(fila["Activa"]) and not bool(actual.activa):
            activadas.append(pid)

    if not hubo_cambios:
        return
    if len(activadas) == 1:
        periodos = activar_periodo(periodos.reset_index(), activadas[0]).set_index("periodo_id")
    save_periodos(periodos.reset_index())
    st.rerun()


def render_periodos_tabla(periodos, movimientos):
    st.subheader("📅 Periodos")
    st.caption("Origen, fechas y montos se pueden editar directo en la tabla.")

    filas = []
    for _, p in periodos.iterrows():
        fin = p.fecha_fin
        gastado = movimientos.loc[
            (movimientos.periodo_id == p.periodo_id) & (movimientos.tipo == "Gasto"), "monto"
        ].sum()
        dias_restantes = max((fin.date() - date.today()).days + 1, 0)
        disponible = p.monto_recibido - gastado
        filas.append({
            "Periodo": p.periodo_id,
            "Activa": bool(p.activa),
            "Origen": p.origen if pd.notna(p.origen) else "",
            "Inicio": p.fecha_inicio.date(),
            "Esperado": p.monto_esperado,
            "Recibido": p.monto_recibido,
            "Fin": fin.date(),
            "Pendiente": money(p.monto_esperado - p.monto_recibido),
            "Gastado": money(gastado),
            "Disponible": money(disponible),
            "Días restantes": dias_restantes,
            "$/día restante": money(disponible / dias_restantes if dias_restantes else disponible),
        })

    editado = st.data_editor(
        pd.DataFrame(filas), hide_index=True, use_container_width=True, num_rows="fixed", key="periodos_editor",
        column_config={
            "Periodo": st.column_config.TextColumn("Periodo", disabled=True),
            "Activa": st.column_config.CheckboxColumn("Activa"),
            "Origen": st.column_config.TextColumn("Origen"),
            "Inicio": st.column_config.DateColumn("Inicio"),
            "Esperado": st.column_config.NumberColumn("Esperado", min_value=0, step=50),
            "Recibido": st.column_config.NumberColumn("Recibido", min_value=0, step=50),
            "Fin": st.column_config.DateColumn("Fin"),
            "Pendiente": st.column_config.TextColumn("Pendiente", disabled=True),
            "Gastado": st.column_config.TextColumn("Gastado", disabled=True),
            "Disponible": st.column_config.TextColumn("Disponible", disabled=True),
            "Días restantes": st.column_config.NumberColumn("Días restantes", disabled=True),
            "$/día restante": st.column_config.TextColumn("$/día restante", disabled=True),
        },
    )

    _guardar_cambios_periodos(periodos, editado)


def render_gastos_chart(movimientos):
    st.subheader("📊 Gastos por categoría")

    gastos = movimientos[movimientos.tipo == "Gasto"]
    if gastos.empty:
        st.info("Aún no hay gastos registrados.")
        return

    resumen = gastos.groupby("categoria")["monto"].sum().reindex(GASTO_CATEGORIAS).dropna()
    charts.barras_horizontales(resumen.index, resumen.values, [COLOR_MAP[c] for c in resumen.index], money)


def _tiene_periodo(valor):
    return pd.notna(valor) and valor != ""


def _revertir_efecto(periodos, cuentas, fila):
    if fila.tipo == "Ingreso" and fila.categoria in INGRESO_PERIODICO_CATEGORIAS and _tiene_periodo(fila.periodo_id):
        pi = periodos[periodos.periodo_id == fila.periodo_id].index
        periodos.loc[pi, "monto_recibido"] -= fila.monto
    ajustar_saldo_cuenta(cuentas, fila.cuenta, -delta_por_tipo(fila.tipo, fila.monto))


def _aplicar_efecto(periodos, cuentas, fila):
    if fila.tipo == "Ingreso" and fila.categoria in INGRESO_PERIODICO_CATEGORIAS and _tiene_periodo(fila.periodo_id):
        pi = periodos[periodos.periodo_id == fila.periodo_id].index
        periodos.loc[pi, "monto_recibido"] += fila.monto
    ajustar_saldo_cuenta(cuentas, fila.cuenta, delta_por_tipo(fila.tipo, fila.monto))


def _fila_valida(fila):
    if pd.isna(fila.fecha) or not fila.tipo or fila.monto is None or fila.monto <= 0:
        return "Faltan datos: revisá que tenga fecha, tipo y un monto mayor a cero."
    categorias_validas = GASTO_CATEGORIAS if fila.tipo == "Gasto" else INGRESO_CATEGORIAS
    if fila.categoria not in categorias_validas:
        return f"La categoría \"{fila.categoria}\" no corresponde a un {fila.tipo.lower()}."
    return None


def _campos_iguales(antes, despues):
    """Compara fila por fila tolerando que la fecha vuelva de la tabla como
    datetime.date en vez de Timestamp — un .equals() estricto los ve
    distintos aunque el usuario no haya tocado nada, y eso dispararía
    guardados de más."""
    return (
        pd.Timestamp(antes.fecha).normalize() == pd.Timestamp(despues.fecha).normalize()
        and antes.tipo == despues.tipo
        and antes.categoria == despues.categoria
        and float(antes.monto) == float(despues.monto)
        and (antes.periodo_id or "") == (despues.periodo_id or "")
        and (antes.nota or "") == (despues.nota or "")
        and antes.cuenta == despues.cuenta
    )


MSG_INVERSION_NO_EDITABLE = (
    "Los movimientos de categoría 📈 Inversión no se pueden editar ni borrar desde acá — "
    "corregí el saldo del ítem de inversión directamente en la pestaña Zona de inversión."
)


def _guardar_cambios_historial(periodos, movimientos, original, editado):
    cuentas = load_cuentas()
    movimientos = movimientos.copy()
    hubo_cambios = False

    ids_originales = set(original["_id"])
    ids_editados = set(editado["_id"].dropna().astype(int))

    for id_ in ids_originales - ids_editados:
        fila = movimientos.loc[id_]
        if fila.categoria == "📈 Inversión":
            st.error(MSG_INVERSION_NO_EDITABLE)
            continue
        _revertir_efecto(periodos, cuentas, fila)
        movimientos = movimientos.drop(index=id_)
        hubo_cambios = True

    original_por_id = original.set_index("_id")
    editado_con_id = editado.dropna(subset=["_id"]).copy()
    editado_con_id["_id"] = editado_con_id["_id"].astype(int)
    editado_por_id = editado_con_id.set_index("_id")

    for id_ in ids_originales & ids_editados:
        antes, despues = original_por_id.loc[id_], editado_por_id.loc[id_]
        if _campos_iguales(antes, despues):
            continue
        if antes.categoria == "📈 Inversión":
            st.error(MSG_INVERSION_NO_EDITABLE)
            continue
        error = _fila_valida(despues)
        if error:
            st.error(f"{despues.fecha}: {error}")
            continue
        _revertir_efecto(periodos, cuentas, movimientos.loc[id_])
        movimientos.loc[id_, ["fecha", "tipo", "categoria", "monto", "nota", "cuenta"]] = [
            pd.Timestamp(despues.fecha), despues.tipo, despues.categoria, despues.monto,
            despues.nota, despues.cuenta,
        ]
        movimientos.loc[id_, "periodo_id"] = despues.periodo_id if despues.periodo_id else pd.NA
        _aplicar_efecto(periodos, cuentas, movimientos.loc[id_])
        hubo_cambios = True

    for _, fila in editado[editado["_id"].isna()].iterrows():
        error = _fila_valida(fila)
        if error:
            st.error(f"Fila nueva: {error}")
            continue
        nueva = {
            "fecha": pd.Timestamp(fila.fecha), "tipo": fila.tipo, "categoria": fila.categoria,
            "monto": fila.monto, "periodo_id": fila.periodo_id if fila.periodo_id else pd.NA,
            "nota": fila.nota, "cuenta": fila.cuenta,
        }
        movimientos = pd.concat([movimientos, pd.DataFrame([nueva])], ignore_index=True)
        _aplicar_efecto(periodos, cuentas, pd.Series(nueva))
        hubo_cambios = True

    if not hubo_cambios:
        return
    save_movimientos(movimientos)
    save_periodos(periodos)
    save_cuentas(cuentas)
    st.rerun()


def render_deshacer_historial():
    if st.button("↩️ Deshacer el último guardado del historial"):
        restaurado = any([
            deshacer_ultimo_cambio(data_store.MOVIMIENTOS_FILE),
            deshacer_ultimo_cambio(data_store.PERIODOS_FILE),
            deshacer_ultimo_cambio(data_store.CUENTAS_FILE),
        ])
        if restaurado:
            st.success("Se deshizo el último cambio.")
            st.rerun()
        else:
            st.info("No hay nada para deshacer.")


def _aplicar_filtro_historial(tabla, fecha_desde, fecha_hasta, categorias, cuentas):
    """Filtro puro y display-only sobre `tabla` (que ya trae `_id`). Sin
    filtros (None/[]) devuelve todo. Filtrar `original` y `editado` de forma
    idéntica antes de pasarlos a `_guardar_cambios_historial` es lo que evita
    que una fila fuera del filtro se interprete como borrada."""
    mask = pd.Series(True, index=tabla.index)
    if fecha_desde is not None:
        mask &= tabla["fecha"] >= pd.Timestamp(fecha_desde)
    if fecha_hasta is not None:
        mask &= tabla["fecha"] <= pd.Timestamp(fecha_hasta)
    if categorias:
        mask &= tabla["categoria"].isin(categorias)
    if cuentas:
        mask &= tabla["cuenta"].isin(cuentas)
    return tabla[mask]


def render_historial(periodos, movimientos):
    st.subheader("📖 Historial de movimientos")
    st.caption(
        "Editá cualquier campo directo en la tabla, o borrala seleccionándola con el check de la "
        "izquierda y el ícono de basura. También podés agregar filas con el + de abajo."
    )

    tabla = movimientos.sort_values("fecha", ascending=False).reset_index().rename(columns={"index": "_id"})
    tabla["periodo_id"] = tabla["periodo_id"].fillna("")
    tabla["nota"] = tabla["nota"].fillna("")
    tabla["cuenta"] = tabla["cuenta"].fillna("Efectivo")

    with st.expander("🔎 Filtrar historial"):
        c1, c2 = st.columns(2)
        fecha_desde = c1.date_input("Desde", value=None, key="hist_fecha_desde")
        fecha_hasta = c2.date_input("Hasta", value=None, key="hist_fecha_hasta")
        categorias_sel = st.multiselect(
            "Categoría", GASTO_CATEGORIAS + INGRESO_CATEGORIAS, key="hist_categorias"
        )
        cuentas_sel = st.multiselect("Cuenta", CUENTAS_CON_EFECTIVO, key="hist_cuentas")

    tabla_mostrada = _aplicar_filtro_historial(tabla, fecha_desde, fecha_hasta, categorias_sel, cuentas_sel)
    if len(tabla_mostrada) < len(tabla):
        st.caption(f"Mostrando {len(tabla_mostrada)} de {len(tabla)} movimientos.")

    editado = st.data_editor(
        tabla_mostrada, hide_index=True, use_container_width=True, num_rows="dynamic", key="historial_editor",
        column_order=["fecha", "tipo", "categoria", "monto", "periodo_id", "cuenta", "nota"],
        column_config={
            "fecha": st.column_config.DateColumn("Fecha"),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Ingreso"]),
            "categoria": st.column_config.SelectboxColumn(
                "Categoría", options=GASTO_CATEGORIAS + INGRESO_CATEGORIAS
            ),
            "monto": st.column_config.NumberColumn("Monto", min_value=0, step=1),
            "periodo_id": st.column_config.SelectboxColumn(
                "Periodo", options=[""] + periodos["periodo_id"].tolist()
            ),
            "cuenta": st.column_config.SelectboxColumn("Cuenta", options=CUENTAS_CON_EFECTIVO),
            "nota": st.column_config.TextColumn("Nota"),
        },
    )

    _guardar_cambios_historial(periodos, movimientos, tabla_mostrada, editado)


def render(periodos, movimientos):
    render_cuentas(movimientos)
    st.divider()
    render_periodos_tabla(periodos, movimientos)
    st.divider()
    render_gastos_chart(movimientos)
    st.divider()
    render_deshacer_historial()
    render_historial(periodos, movimientos)
```

Also add `save_periodos` to the `data_store` import list at the top of `resumen_tab.py` (used by `_guardar_cambios_periodos` and `_guardar_cambios_historial` — it wasn't needed by Tasks 10-11).

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_resumen_tab.py -v`
Expected: PASS (all tests, including Tasks 10-11's).

- [ ] **Step 5: Run the entire suite to confirm nothing regressed**

Run: `pytest tests/ -v`
Expected: PASS (every test written so far).

- [ ] **Step 6: Commit**

```bash
git add resumen_tab.py tests/test_resumen_tab.py
git commit -m "Add periods table, expense chart, transaction history, and undo"
```

---

## Task 13: `patrimonio.py` — net worth total, distribution, evolution

**Files:**
- Create: `patrimonio.py`
- Create: `tests/test_patrimonio.py`

**Interfaces:**
- Consumes: `data_store.PATRIMONIO_COLOR_MAP`, `efectivo`, `load_cuentas`, `load_historico`, `money`, `registrar_snapshot_patrimonio` (Tasks 4-5); `charts.barras_horizontales`, `linea` (Task 6).
- Produces: `calcular_desglose(movimientos, desglose_inversion) -> dict`, `render_total(desglose, movimientos) -> float`, `render_distribucion(desglose)`, `render_evolucion()`, `render(movimientos, desglose_inversion)` — `render` is consumed by `app.py` (Task 14).

- [ ] **Step 1: Write `tests/test_patrimonio.py` with the failing tests**

```python
from datetime import date

import pandas as pd
from streamlit.testing.v1 import AppTest

import charts
import data_store
from data_store import efectivo
from patrimonio import calcular_desglose


def test_calcular_desglose_junta_bancos_efectivo_e_inversion():
    data_store.save_cuentas(pd.DataFrame({"cuenta": ["Ahorros", "Corriente"], "saldo": [100, 50]}))
    movimientos = pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-01"), "tipo": "Ingreso", "categoria": "🎒 Saldo inicial",
         "monto": 200, "periodo_id": pd.NA, "nota": "", "cuenta": pd.NA},
    ])
    desglose_inversion = {"FIC": 300, "Cripto": 10}

    resultado = calcular_desglose(movimientos, desglose_inversion)

    cuentas = data_store.load_cuentas()
    assert resultado["Bancos"] == 150
    assert resultado["Efectivo"] == efectivo(movimientos, cuentas)
    assert resultado["FIC"] == 300
    assert resultado["Cripto"] == 10


def _app_render_total():
    import streamlit as st

    import patrimonio
    patrimonio.render_total(st.session_state["desglose"], st.session_state["movimientos"])


def _metric(at, etiqueta):
    return next(m for m in at.metric if m.label == etiqueta)


def test_render_total_muestra_las_metricas_correctas():
    desglose = {"Bancos": 1000, "Efectivo": 50, "FIC": 200}
    movimientos = pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-01"), "tipo": "Gasto", "categoria": "🍽️ Comida",
         "monto": 80, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros"},
        {"fecha": pd.Timestamp("2026-08-02"), "tipo": "Gasto", "categoria": "🚌 Transporte",
         "monto": 30, "periodo_id": pd.NA, "nota": "", "cuenta": "Ahorros"},
    ])

    at = AppTest.from_function(_app_render_total)
    at.session_state["desglose"] = desglose
    at.session_state["movimientos"] = movimientos
    at.run()

    assert not at.exception
    assert _metric(at, "🏦 Patrimonio total").value == data_store.money(1250)
    assert _metric(at, "🧾 Gastado de todos los tiempos").value == data_store.money(110)


def test_render_total_registra_snapshot_de_hoy():
    desglose = {"Bancos": 1000}
    movimientos = pd.DataFrame(columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"])

    at = AppTest.from_function(_app_render_total)
    at.session_state["desglose"] = desglose
    at.session_state["movimientos"] = movimientos
    at.run()

    assert not at.exception
    historico = data_store.load_historico()
    fila_hoy = historico[historico.fecha == pd.Timestamp(date.today())]
    assert len(fila_hoy) == 1
    assert fila_hoy.iloc[0]["patrimonio_total"] == 1000


def test_render_total_con_patrimonio_cero_igual_registra_snapshot():
    at = AppTest.from_function(_app_render_total)
    at.session_state["desglose"] = {"Bancos": 0}
    at.session_state["movimientos"] = pd.DataFrame(
        columns=["fecha", "tipo", "categoria", "monto", "periodo_id", "nota", "cuenta"]
    )
    at.run()

    assert not at.exception
    historico = data_store.load_historico()
    fila_hoy = historico[historico.fecha == pd.Timestamp(date.today())]
    assert len(fila_hoy) == 1
    assert fila_hoy.iloc[0]["patrimonio_total"] == 0


def _app_render_distribucion():
    import streamlit as st

    import patrimonio
    patrimonio.render_distribucion(st.session_state["desglose"])


def test_distribucion_sin_categorias_positivas_muestra_caption_sin_grafico(monkeypatch):
    llamado = []
    monkeypatch.setattr(charts, "barras_horizontales", lambda *a, **k: llamado.append(True))

    at = AppTest.from_function(_app_render_distribucion)
    at.session_state["desglose"] = {"Bancos": 0, "Efectivo": -100}
    at.run()

    assert not at.exception
    assert llamado == []
    assert any("Todavía no hay plata" in c.value for c in at.caption)


def test_distribucion_con_categorias_positivas_llama_al_grafico(monkeypatch):
    llamado = []
    monkeypatch.setattr(charts, "barras_horizontales", lambda *a, **k: llamado.append(True))

    at = AppTest.from_function(_app_render_distribucion)
    at.session_state["desglose"] = {"Bancos": 100, "Cripto": 50}
    at.run()

    assert not at.exception
    assert llamado == [True]


def _app_render_evolucion():
    import patrimonio
    patrimonio.render_evolucion()


def test_evolucion_con_menos_de_2_dias_muestra_caption():
    at = AppTest.from_function(_app_render_evolucion)
    at.run()

    assert not at.exception
    assert any("volvé mañana" in c.value for c in at.caption)


def test_evolucion_con_2_o_mas_dias_renderiza_sin_excepcion():
    data_store.registrar_snapshot_patrimonio(date(2026, 8, 1), 1000)
    data_store.registrar_snapshot_patrimonio(date(2026, 8, 2), 1500)

    at = AppTest.from_function(_app_render_evolucion)
    at.run()

    assert not at.exception
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_patrimonio.py -v`
Expected: FAIL — `patrimonio` module does not exist yet.

- [ ] **Step 3: Create `patrimonio.py`**

```python
from datetime import date

import streamlit as st

import charts
from data_store import (
    PATRIMONIO_COLOR_MAP,
    efectivo,
    load_cuentas,
    load_historico,
    money,
    registrar_snapshot_patrimonio,
)


def calcular_desglose(movimientos, desglose_inversion):
    cuentas = load_cuentas()
    return {
        "Bancos": cuentas["saldo"].sum(),
        "Efectivo": efectivo(movimientos, cuentas),
        **desglose_inversion,
    }


def render_total(desglose, movimientos):
    total = sum(desglose.values())
    gastos = movimientos[movimientos.tipo == "Gasto"]
    gastado_historico = gastos.loc[gastos.categoria != "📈 Inversión", "monto"].sum()

    col1, col2 = st.columns(2)
    col1.metric("🏦 Patrimonio total", money(total))
    col2.metric("🧾 Gastado de todos los tiempos", money(gastado_historico))
    st.caption("Cuentas + efectivo + inversión, todo junto.")
    registrar_snapshot_patrimonio(date.today(), total)
    return total


def render_distribucion(desglose):
    st.subheader("📊 Distribución del patrimonio")
    positivos = {k: v for k, v in desglose.items() if v > 0}
    if not positivos:
        st.caption("Todavía no hay plata registrada en ninguna categoría.")
        return

    orden = sorted(positivos.items(), key=lambda kv: kv[1])
    etiquetas = [k for k, _ in orden]
    valores = [v for _, v in orden]
    colores = [PATRIMONIO_COLOR_MAP.get(k, "#898781") for k in etiquetas]
    charts.barras_horizontales(etiquetas, valores, colores, money)


def render_evolucion():
    st.subheader("📈 Evolución del patrimonio")
    historico = load_historico()
    if len(historico) < 2:
        st.caption("Todavía hay muy pocos días registrados — volvé mañana para empezar a ver la evolución.")
        return

    charts.linea(historico["fecha"], historico["patrimonio_total"], nombre="Patrimonio")


def render(movimientos, desglose_inversion):
    desglose = calcular_desglose(movimientos, desglose_inversion)
    render_total(desglose, movimientos)
    st.divider()
    render_distribucion(desglose)
    st.divider()
    render_evolucion()
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_patrimonio.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add patrimonio.py tests/test_patrimonio.py
git commit -m "Add net worth total, distribution chart, and evolution chart"
```

---

## Task 14: `app.py` — wire everything together, final smoke test

**Files:**
- Create: `app.py`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: `data_store.load_movimientos`, `load_periodos` (Tasks 3-4); `sidebar.render_nuevo_periodo`, `render_nuevo_movimiento` (Task 8); `inversion_tab.render`, `desglose_patrimonio_inversion` (Task 9); `resumen_tab.render_header`, `render` (Tasks 10-12); `patrimonio.render` (Task 13).
- Produces: the runnable app — no functions consumed by anything else, this is the top of the dependency graph.

- [ ] **Step 1: Write `tests/test_app.py` with the failing smoke tests**

```python
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_completo_corre_sin_excepciones():
    at = AppTest.from_file(str(Path(__file__).parent.parent / "app.py"))
    at.run(timeout=30)
    assert not at.exception


def test_la_portada_aparece_antes_de_las_pestanas():
    at = AppTest.from_file(str(Path(__file__).parent.parent / "app.py"))
    at.run(timeout=30)
    subheaders = [s.value for s in at.subheader]
    assert "🏠 Inicio" in subheaders
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_app.py -v`
Expected: FAIL — `app.py` does not exist yet.

- [ ] **Step 3: Create `app.py`**

```python
import streamlit as st

import inversion_tab
import patrimonio
import resumen_tab
import sidebar
from data_store import load_movimientos, load_periodos

st.set_page_config(page_title="Mis Finanzas 💸", page_icon="💸", layout="wide")

periodos = load_periodos()
movimientos = load_movimientos()

st.title("💸 Mis Finanzas — Panel de control")

resumen_tab.render_header(periodos, movimientos)
st.divider()

sidebar.render_nuevo_periodo(periodos)
sidebar.render_nuevo_movimiento(periodos, movimientos)

tab_resumen, tab_inversion, tab_patrimonio = st.tabs(["🏠 Resumen", "📈 Zona de inversión", "🏦 Patrimonio"])

with tab_resumen:
    resumen_tab.render(periodos, movimientos)

with tab_inversion:
    inversion_tab.render()

with tab_patrimonio:
    patrimonio.render(movimientos, inversion_tab.desglose_patrimonio_inversion())
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_app.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the entire test suite one final time**

Run: `pytest tests/ -v`
Expected: PASS — every test across every module, with no leftover references to `quincena`, `mesada`, or COP-only formatting.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "Wire app.py entrypoint; add end-to-end smoke test"
```

- [ ] **Step 7: Manual QA pass — run the real app and click through every use case**

Run: `streamlit run app.py`

Walk through, confirming each works and the money amounts render with the configured currency symbol (`$`, USD by default):
1. Create a new periodo from the sidebar; confirm it appears in the "📅 Periodos" table on the Resumen tab.
2. Register a `💰 Ingreso periódico` transaction linked to that periodo; confirm "Recibido" and the header's "Pendiente por cobrar" metric update.
3. Register a `Gasto`; confirm the account balance and "Gastado en el periodo" update, and that unchecking "Este gasto es de este periodo" leaves it unassociated.
4. Move money between two accounts in "🔁 Mover dinero entre cuentas"; confirm both balances update.
5. In the "📈 Zona de inversión" tab, set a manual FIC balance, add a crypto row (e.g. `bitcoin`) and a stock row (e.g. `AAPL`) — confirm prices load (or show `—` gracefully if offline).
6. Use "📈 Mover a inversión" to move money from an account into the FIC item; confirm the account balance drops and the FIC balance rises, and a `📈 Inversión` transaction appears in the historial that can't be edited or deleted.
7. Check the "🏦 Patrimonio" tab: confirm the total matches accounts + cash + investments, the distribution chart renders, and (after running the app on a second day) the evolution chart appears.
8. Edit a row directly in "📖 Historial de movimientos", delete another, and add a new one via the `+` row; confirm balances stay consistent.
9. Click "↩️ Deshacer el último guardado del historial" and confirm the last historial change is reverted.

Report any step that doesn't work as a bug to fix before considering the port done — this manual pass is the only check on the actual rendered UI, since Tasks 1-14 test pure logic and form-submission behavior but not visual layout.

---

## Plan self-review

**Spec coverage:** Every item in the spec's "Se mantiene del original" and "Cambia respecto al original" lists has a task: accounts+cash (Task 11), transactions/categories (Tasks 4, 8, 12), periods with alerts (Tasks 3, 10), investment zone (Task 9), net worth (Task 13), editable history + undo (Tasks 2, 12), configurable currency (Tasks 1-2, 9), generalized period/category naming (Tasks 3-4, throughout). The "Fuera de alcance" items (auth, deploy) have no tasks, correctly.

**Placeholder scan:** No TBD/TODO markers; every step has runnable code, not a description of code.

**Type consistency:** Verified `periodo_id` (not `quincena_id`) is used consistently in every DataFrame column, test fixture, and column_config across Tasks 2-14. Verified `precio_unitario_base`/`tasa_usd_a_base`/`valor_base`/`ganancia_base` (not the `_cop` originals) are used consistently between Task 9's `inversion_tab.py` and Task 11's `resumen_tab.py` transfer functions. Verified `INGRESO_PERIODICO_CATEGORIAS` (not `MESADA_CATEGORIAS`) is the name used in both Task 4 (definition) and Task 12 (`_aplicar_efecto`/`_revertir_efecto`).

