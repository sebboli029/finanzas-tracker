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
