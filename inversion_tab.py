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


def _precios_de_activos(activos, columna_id):
    """Para cada fila con un identificador, calcula valor y ganancia/pérdida
    a partir del precio que cargó el usuario. Precio y precio_compra están
    los dos en la moneda base de la app, así que no hay ninguna conversión
    que hacer. `valor` queda en None si el precio todavía no se cargó
    (precio == 0): no se puede valorizar la fila, y tratarla como cero
    mentiría en el total. `ganancia` queda en None si no se cargó un precio
    de compra."""
    filas = []
    for _, fila in activos.dropna(subset=[columna_id]).iterrows():
        identificador = str(fila[columna_id]).strip()
        if not identificador:
            continue
        precio = fila.get("precio", 0.0)
        cantidad = fila["cantidad"]
        precio_compra = fila.get("precio_compra", 0.0)
        valor = precio * cantidad if precio else None
        ganancia = ganancia_pct = None
        if valor is not None and precio_compra:
            costo = precio_compra * cantidad
            ganancia = valor - costo
            ganancia_pct = (ganancia / costo * 100) if costo else None
        filas.append({
            "identificador": identificador, "precio": precio,
            "valor": valor, "ganancia": ganancia, "ganancia_pct": ganancia_pct,
        })
    return filas


def _valor_activos(cargar, columna_id):
    filas = _precios_de_activos(cargar(), columna_id)
    return sum(f["valor"] for f in filas if f["valor"] is not None)


def _render_activos(titulo, etiqueta_total, ayuda, cargar, guardar, columna_id, columna_id_label):
    st.subheader(titulo)
    st.caption(ayuda)

    activos = cargar()
    editado = st.data_editor(
        activos, num_rows="dynamic", use_container_width=True, hide_index=True,
        key=f"editor_{columna_id}",
        column_config={
            columna_id: st.column_config.TextColumn(columna_id_label),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.0001, format="%.6f"),
            "precio": st.column_config.NumberColumn(
                f"Precio actual (en {config.MONEDA_BASE})", min_value=0.0, step=0.01, format="%.4f"
            ),
            "precio_compra": st.column_config.NumberColumn(
                f"Precio de compra (en {config.MONEDA_BASE}, opcional)", min_value=0.0, step=0.01, format="%.4f"
            ),
        },
    )
    editado["cantidad"] = editado["cantidad"].fillna(0.0)
    editado["precio"] = editado["precio"].fillna(0.0)
    editado["precio_compra"] = editado["precio_compra"].fillna(0.0)
    if not editado.equals(activos):
        guardar(editado)

    filas_precio = _precios_de_activos(editado, columna_id)
    filas = []
    for f in filas_precio:
        if f["valor"] is None:
            filas.append({
                columna_id_label: f["identificador"], "Precio": "—",
                "Valor": "— (cargá el precio)", "Ganancia/pérdida": "—",
            })
            continue
        if f["ganancia"] is None:
            ganancia = "—"
        else:
            ganancia = f"{money(f['ganancia'])} ({f['ganancia_pct']:+.1f}%)"
        filas.append({
            columna_id_label: f["identificador"],
            "Precio": f"{f['precio']:,.2f}",
            "Valor": money(f["valor"]),
            "Ganancia/pérdida": ganancia,
        })

    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        total = sum(f["valor"] for f in filas_precio if f["valor"] is not None)
        st.metric(f"{etiqueta_total} ({config.MONEDA_BASE})", money(total))


def render_inversiones():
    st.subheader("📈 Inversiones")
    st.caption("Editá el saldo a mano, o movele plata sobrante desde \"Mover a inversión\" en la pestaña Resumen.")
    inversiones = load_inversiones()
    if inversiones.empty:
        st.caption("No hay ítems de inversión manual cargados.")
        return

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


def render_criptos():
    _render_activos(
        titulo="🪙 Cripto",
        etiqueta_total="Total cripto",
        ayuda=(
            "Agregá o quitá monedas con los botones de la tabla (+ al final, 🗑️ en la fila). "
            f"El precio lo cargás vos, en {config.MONEDA_BASE} — la app no lo cambia sola. "
            "Si cargás también el precio de compra, te calculo la ganancia o pérdida."
        ),
        cargar=load_criptos, guardar=save_criptos,
        columna_id="id", columna_id_label="Moneda",
    )


def render_acciones():
    _render_activos(
        titulo="📊 Acciones",
        etiqueta_total="Total acciones",
        ayuda=(
            "Agregá o quitá acciones con los botones de la tabla. "
            f"El precio lo cargás vos, en {config.MONEDA_BASE} — la app no lo cambia sola. "
            "Si cargás también el precio de compra, te calculo la ganancia o pérdida."
        ),
        cargar=load_acciones, guardar=save_acciones,
        columna_id="ticker", columna_id_label="Ticker",
    )


def desglose_patrimonio_inversion():
    """Valor en la moneda base de cada categoría de la Zona de inversión —
    lo usa el total de arriba de todo y el gráfico de distribución del
    patrimonio."""
    monedas = _actualizar_tasas_del_dia(load_monedas())
    desglose = {fila["item"]: fila["saldo"] for _, fila in load_inversiones().iterrows()}
    desglose["Monedas extranjeras"] = (monedas["monto"] * monedas["tasa"]).sum()
    desglose["Cripto"] = _valor_activos(load_criptos, "id")
    desglose["Acciones"] = _valor_activos(load_acciones, "ticker")
    return desglose


def total_patrimonio_inversion():
    return sum(desglose_patrimonio_inversion().values())


def render():
    render_inversiones()
    st.divider()
    render_monedas()
    st.divider()
    render_criptos()
    st.divider()
    render_acciones()
