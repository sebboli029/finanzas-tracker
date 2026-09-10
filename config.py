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
