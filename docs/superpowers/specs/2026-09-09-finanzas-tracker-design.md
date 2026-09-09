# Finanzas Tracker — diseño

## Contexto

`mesada-tracker` es una app Streamlit/Python que le sirve a una persona
para llevar el control de la mesada que recibe de sus papás cada quincena:
cuánto le deben, cuánto ha gastado, en qué cuentas tiene la plata, y un
módulo de inversión (FIC manual, dólares/euros, cripto y acciones en vivo)
que se suma a un patrimonio total con su evolución histórica.

Este proyecto (`finanzas-tracker`) reimplementa los mismos casos de uso
para otra persona con finanzas personales más generales — no depende de
que alguien le pague una mesada. Es una base nueva, no una copia con
find-and-replace: el concepto de "quincena de mesada" se generaliza a
"periodo de presupuesto", y la moneda deja de estar fija en pesos
colombianos.

## Alcance

**Se mantiene del original:**
- Cuentas bancarias + efectivo calculado como el resto (no una cuenta más).
- Movimientos (ingresos/gastos) por categoría, con cuenta y periodo
  asociados opcionalmente.
- Periodos de presupuesto con monto esperado/recibido, alertas de
  sobregiro y de saldo bajo.
- Zona de inversión: ítems manuales, monedas extranjeras con tasa en
  vivo, cripto (CoinGecko) y acciones (Yahoo Finance) con cálculo de
  ganancia/pérdida.
- Patrimonio total (cuentas + efectivo + inversión), distribución y
  evolución histórica.
- Historial editable con filtros y función de deshacer.
- Persistencia en CSV con respaldo automático antes de cada guardado
  (mismo mecanismo que `data_store.py`: copia a `.backups/`, máximo 5
  por archivo, deshacer restaura el más reciente).

**Cambia respecto al original:**
- "Quincena" → "Periodo": mismo modelo (rango de fechas, monto esperado,
  monto recibido, activo), pero sin el campo `pagador` (Papá/Mamá/Otro) —
  no aplica a finanzas generales. Se reemplaza por un campo libre
  `origen` (texto opcional, ej. "Sueldo", "Freelance") que no participa
  en ninguna lógica, solo informativo.
- Categoría `💰 Mesada` / `💰 Mesada (adelanto)` → `💰 Ingreso periódico` /
  `💰 Ingreso periódico (adelanto)` (la categoría de ingreso que
  descuenta el pendiente del periodo).
- `👵 Regalo de la abuela` → `🎁 Regalo` (se generaliza, deja de asumir
  un familiar específico).
- Moneda base configurable (`config.py` o fila en `data/config.csv`),
  default `USD`. `money()` formatea según esa moneda en vez de asumir
  COP con puntos como separador de miles.
- Tasa de USD ya no usa la TRM oficial de Colombia (`datos.gov.co`) —
  se cae esa fuente y todas las monedas (incluida la base si no es USD)
  se traen de `open.er-api.com`, igual que ya hacía el euro en el
  original.

**Fuera de alcance:**
- Autenticación / multi-usuario — sigue siendo una app de un solo
  usuario, sin login, igual que el original.
- Deploy — no se decide en este spec; se puede correr local igual que
  el original (`streamlit run app.py`).

## Estructura de archivos

Espejo del original, mismo split por responsabilidad:

```
finanzas-tracker/
  app.py                 # entrypoint, arma tabs
  config.py              # moneda base + tasas iniciales (nuevo)
  data_store.py          # CRUD + lógica pura sobre CSVs
  sidebar.py             # formularios "nuevo periodo" / "nuevo movimiento"
  widgets.py             # selects compartidos entre formularios
  resumen_tab.py         # cuentas, tabla de periodos, gastos, historial
  inversion_tab.py       # ítems manuales, monedas, cripto, acciones
  patrimonio.py          # total, distribución, evolución
  charts.py              # helpers de gráficos (sin cambios de fondo)
  data/                  # CSVs + .backups/
  tests/
```

## Modelo de datos (CSV, uno por archivo — igual mecanismo que el original)

- `periodos.csv`: `periodo_id, fecha_inicio, fecha_fin, origen, monto_esperado, monto_recibido, activa`
- `movimientos.csv`: `fecha, tipo, categoria, monto, periodo_id, nota, cuenta`
- `cuentas.csv`: `cuenta, saldo`
- `inversiones.csv`: `item, saldo, actualizado`
- `monedas.csv`: `moneda, monto, tasa`
- `criptos.csv`: `id, simbolo, cantidad, precio_compra`
- `acciones.csv`: `ticker, cantidad, precio_compra`
- `patrimonio_historico.csv`: `fecha, patrimonio_total`
- `config.csv`: `moneda_base` (una sola fila; leída por `money()` y por
  el fetch de tasas)

Categorías (arrays en `data_store.py`, igual que el original):
- `GASTO_CATEGORIAS = ["🚌 Transporte", "🍽️ Comida", "🎮 Ocio", "📦 Otro", "📈 Inversión"]`
- `INGRESO_CATEGORIAS = ["💰 Ingreso periódico", "💰 Ingreso periódico (adelanto)", "🎁 Ingreso extra", "🎁 Regalo", "🎒 Saldo inicial", "📈 Retiro de inversión"]`
- `INGRESO_PERIODICO_CATEGORIAS = {"💰 Ingreso periódico", "💰 Ingreso periódico (adelanto)"}` (antes `MESADA_CATEGORIAS`)

## Lógica de negocio (funciones puras, testeadas — igual enfoque que el original)

Mismas funciones que `data_store.py`, renombradas de quincena→periodo,
sin cambio de comportamiento salvo lo listado en Alcance:
- `periodo_actual`, `pendiente_por_cobrar`, `gastado_en_periodo`,
  `saldo_restante_periodo`, `activar_periodo`.
- `saldo_disponible`, `efectivo`, `delta_por_tipo`, `ajustar_saldo_cuenta`.
- `ajustar_saldo_inversion`, `registrar_compra_activo`,
  `registrar_venta_activo`.
- `registrar_snapshot_patrimonio`.
- `money(n)` ahora lee `config.moneda_base` y formatea según esa moneda
  (separador de miles con coma para USD, con punto si la moneda base
  fuera COP, etc. — una función `formato_moneda(codigo)` chica que
  resuelve el separador, sin volverse un sistema de i18n completo).

## UI / páginas (mismos 3 tabs)

1. **Resumen**: métricas del periodo activo + alerta de sobregiro/saldo
   bajo (umbral 20%, igual que el original), formularios de nuevo
   periodo/movimiento en la sidebar, cuentas + mover dinero entre
   cuentas, tabla editable de periodos, gráfico de gastos por
   categoría, historial editable con filtros y deshacer.
2. **Zona de inversión**: ítems manuales, monedas extranjeras (tasa en
   vivo desde `open.er-api.com`), cripto y acciones en vivo con
   ganancia/pérdida, mover/retirar plata de cuentas a inversión.
3. **Patrimonio**: total, distribución (gráfico de barras), evolución
   histórica (gráfico de línea).

## Testing

Igual enfoque que el original: tests unitarios en `tests/` sobre las
funciones puras de `data_store.py` (periodo actual, saldo restante,
efectivo, ajustes de cuenta/inversión, registrar compra/venta de
activos, formato de moneda). Sin mocks de Streamlit — se testea la
lógica de datos aislada de la UI, igual que hace el original.

## Riesgos / decisiones abiertas

- El campo `origen` del periodo es puramente informativo — si más
  adelante se necesita filtrar o agrupar por origen, se puede promover
  a algo con lógica, pero no en esta base.
- Si la moneda base no es USD ni EUR, el fetch de tasas a
  `open.er-api.com` puede no tener esa moneda como destino directo —
  se maneja igual que el original maneja monedas desconocidas: el
  fetch devuelve `None` y esa fila queda sin tasa hasta que se cargue
  a mano.
