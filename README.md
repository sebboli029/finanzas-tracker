# 💸 Finanzas Tracker

Panel de control de finanzas personales hecho con [Streamlit](https://streamlit.io/).
Organiza los gastos por períodos (por ejemplo, de un pago al siguiente), lleva el
saldo de cada cuenta y calcula el patrimonio total sumando efectivo, monedas,
cripto y acciones.

Todos los datos se guardan en CSV dentro de `data/`, en tu propia máquina. No hay
base de datos ni servidor: la app lee y escribe esos archivos directamente.

## Instalación

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/sebboli029/finanzas-tracker.git
cd finanzas-tracker

python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

Se abre en el navegador (por defecto `http://localhost:8501`). La primera vez los
CSV todavía no existen: se crean solos al registrar el primer período y el primer
movimiento desde la barra lateral.

## Las tres pestañas

- **🏠 Resumen** — períodos de gasto, saldo restante, historial de movimientos y
  gráficos de gastos por categoría. Incluye deshacer el último cambio.
- **📈 Zona de inversión** — posiciones en monedas, cripto y acciones. Los
  precios de cripto y acciones los cargás vos a mano; las tasas de cambio de
  monedas extranjeras se actualizan solas.
- **🏦 Patrimonio** — patrimonio total, cómo está distribuido y su evolución en
  el tiempo.

## Configuración

`config.py` define la moneda base de la app (`MONEDA_BASE`, por defecto `USD`) y
los formatos disponibles. Todos los montos se guardan y se muestran en esa
moneda, incluidos los precios de cripto y acciones que cargas a mano.

Las listas de cuentas, categorías de gasto e ingreso están al principio de
`data_store.py` y se pueden ajustar ahí.

## Precios y cotizaciones

**Cripto y acciones: precio manual.** Vos cargás el precio de cada posición en
su tabla, en la moneda base, y la app no lo cambia nunca. Una fila sin precio
no se puede valorizar: muestra `—` y no suma al total, en lugar de contarse
como cero y mentir en el patrimonio.

**Monedas extranjeras: tasa automática.** Es lo único que sale a internet. Las
tasas se traen de [open.er-api.com](https://open.er-api.com/) una vez al día,
sin API key. Si la consulta falla, se usa la última tasa guardada.

## Datos y respaldos

Los CSV de `data/` están en `.gitignore`, así que tus cifras nunca se suben al
repositorio. Cada vez que se guarda un archivo, la versión anterior se copia a
`data/.backups/` (se conservan las 5 últimas de cada archivo), y desde la pestaña
de resumen puedes deshacer el último cambio.

## Tests

```bash
python -m pytest
```

## Licencia

Proyecto personal, sin licencia definida.
