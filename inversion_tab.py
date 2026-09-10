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
    if moneda == "USD":
        return precio * tasa_usd if tasa_usd is not None else None
    if moneda == config.MONEDA_BASE:
        return precio
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
