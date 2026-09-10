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
