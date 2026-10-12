from datetime import date

import pandas as pd
import streamlit as st

import charts
import data_store
from data_store import (
    COLOR_MAP,
    CUENTAS_CON_EFECTIVO,
    GASTO_CATEGORIAS,
    INGRESO_CATEGORIAS,
    INGRESO_PERIODICO_CATEGORIAS,
    activar_periodo,
    ajustar_saldo_cuenta,
    ajustar_saldo_inversion,
    delta_por_tipo,
    deshacer_ultimo_cambio,
    efectivo,
    gastado_en_periodo,
    load_acciones,
    load_criptos,
    load_cuentas,
    load_inversiones,
    money,
    pendiente_por_cobrar,
    periodo_actual,
    regalos_total,
    registrar_compra_activo,
    registrar_venta_activo,
    saldo_restante_periodo,
    save_acciones,
    save_criptos,
    save_cuentas,
    save_inversiones,
    save_movimientos,
    save_periodos,
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


def _precio_cargado(opcion):
    """Precio que el usuario cargó a mano para un activo de cripto/acciones,
    en la moneda base. None si todavía está en cero: sin precio no se puede
    convertir un monto en cantidad ni valorizar la posición."""
    activos = load_criptos() if opcion["tipo"] == "cripto" else load_acciones()
    columna_id = "id" if opcion["tipo"] == "cripto" else "ticker"
    fila = activos.loc[activos[columna_id] == opcion["identificador"]]
    if fila.empty:
        return None
    precio = fila["precio"].iloc[0]
    return precio if precio else None


def _error_sin_precio(opcion):
    st.error(
        f"Cargá primero el precio de {opcion['etiqueta']} en la pestaña "
        "\"Zona de inversión\" — sin precio no puedo convertir el monto en cantidad."
    )


def _guardar_transferencia_inversion(origen, opcion, monto, movimientos):
    if opcion["tipo"] == "manual":
        save_inversiones(ajustar_saldo_inversion(load_inversiones(), opcion["identificador"], monto))
    else:
        precio_unitario = _precio_cargado(opcion)
        if precio_unitario is None:
            _error_sin_precio(opcion)
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
    directo para un ítem manual, o cantidad × el precio que cargó el usuario
    para cripto/acciones. Devuelve None si ese precio no está cargado."""
    if opcion["tipo"] == "manual":
        inversiones = load_inversiones()
        return inversiones.loc[inversiones.item == opcion["identificador"], "saldo"].iloc[0]

    precio_unitario = _precio_cargado(opcion)
    if precio_unitario is None:
        return None
    activos = load_criptos() if opcion["tipo"] == "cripto" else load_acciones()
    columna_id = "id" if opcion["tipo"] == "cripto" else "ticker"
    cantidad = activos.loc[activos[columna_id] == opcion["identificador"], "cantidad"].iloc[0]
    return cantidad * precio_unitario


def _guardar_retiro_inversion(destino, opcion, monto, movimientos):
    disponible = _valor_disponible_inversion(opcion)
    if disponible is None:
        _error_sin_precio(opcion)
        return
    if monto > disponible:
        st.error(f"No podés retirar más de lo que hay en {opcion['etiqueta']} ({money(disponible)}).")
        return

    if opcion["tipo"] == "manual":
        save_inversiones(ajustar_saldo_inversion(load_inversiones(), opcion["identificador"], -monto))
    else:
        precio_unitario = _precio_cargado(opcion)
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
            "Por día restante": money(disponible / dias_restantes if dias_restantes else disponible),
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
            "Por día restante": st.column_config.TextColumn("Por día restante", disabled=True),
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
    if pd.isna(fila.fecha) or not fila.tipo or pd.isna(fila.monto) or fila.monto <= 0:
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
    st.caption(
        "Restaura la última versión guardada de movimientos, periodos y cuentas — "
        "si hiciste varios cambios distintos seguidos (ej. mover dinero y después editar un periodo), "
        "puede deshacer más de uno a la vez."
    )


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
