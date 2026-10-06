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
- **📈 Zona de inversión** — posiciones en monedas, cripto y acciones, con
  cotizaciones actualizadas automáticamente.
- **🏦 Patrimonio** — patrimonio total, cómo está distribuido y su evolución en
  el tiempo.

## Configuración

`config.py` define la moneda base de la app (`MONEDA_BASE`, por defecto `USD`) y
los formatos disponibles. Si la cambias a otra moneda, lee el comentario del
archivo: la conversión de cripto y acciones necesita una fila pivote en USD.

Las listas de cuentas, categorías de gasto e ingreso están al principio de
`data_store.py` y se pueden ajustar ahí.

## Cotizaciones

Los precios se consultan en vivo a tres APIs públicas, sin necesidad de API key:

| Dato | Fuente |
| --- | --- |
| Tipos de cambio | [open.er-api.com](https://open.er-api.com/) |
| Cripto | [CoinGecko](https://www.coingecko.com/en/api) |
| Acciones | Yahoo Finance |

Si una consulta falla, la app sigue funcionando con el último valor que tengas
guardado.

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
