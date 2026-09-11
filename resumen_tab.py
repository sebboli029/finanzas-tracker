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
